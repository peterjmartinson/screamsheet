# Weather Patterns & Teleconnections V2 — Institutional Memory Database

## Overview

V2 of the **Weather Patterns / Teleconnections Screamsheet** (`WeatherPatternsScreamsheet`) extends V1 by adding persistent SQLite storage in `screamsheet.db` (`src/screamsheet/db/weather_patterns_db.py`).

Core architectural principle:

> **NOAA tells us what happened. The local database tells us what Screamsheet knew, when it knew it, and how the outlook changed.**

Rather than treating SQLite merely as an ephemeral API response cache, V2 preserves:
1. **Normalized historical observations** across large-scale indices and configured local stations.
2. **Multi-run forecast vintages**, never overwriting earlier model runs simply because they targeted the same `valid_time`.
3. **Deterministic forecast-evolution metrics** (`signals.py`) and visual convergence charts (`charts.py`).
4. **Post-event forecast verification and historical analog groundwork**.

---

## 1. SQLite Schema (`src/screamsheet/db/weather_patterns_db.py`)

All tables share the unified SQLAlchemy `_Base` in `src/screamsheet/db/_nhl_db_shared.py` (`~/database/screamsheet.db` or `$SCREAMSHEET_DB`):

| Table Name | ORM Class | Uniqueness Constraint | Purpose |
| :--- | :--- | :--- | :--- |
| `weather_patterns_schema_meta` | `_WeatherSchemaMeta` | `id` (PK) | Tracks active schema version (`WEATHER_PATTERNS_SCHEMA_VERSION = 2`) and migration timestamps. |
| `weather_teleconnection_observations` | `_TeleconnectionObservation` | `(index_name, obs_date, source)` | Daily CDAS standardized anomaly observations (`SD`) for `AO` (1000 hPa), `NAO` (500 hPa), and `PNA` (500 hPa). |
| `weather_stratosphere_observations` | `_StratosphereObservation` | `(obs_date, level_hpa, latitude_deg, source)` | Daily MERRA-2 reanalysis 10-hPa 60°N zonal wind (`m/s`) and 60–90°N polar cap temperature (`K`). |
| `weather_mjo_observations` | `_MJOObservation` | `(obs_date, product)` | Daily NOAA PSL ROMI `component_1`, `component_2`, `raw_pc1`, `raw_pc2`, `amplitude`, `phase` (`1..8`), and `active` flag (`>= 1.0`). |
| `weather_enso_observations` | `_ENSOObservation` | `(period, source)` | Monthly/seasonal Niño 3.4 SST anomaly (`°C`), total SST, ONI, RONI, and bi-monthly MEI.v2. |
| `weather_local_daily_observations` | `_LocalDailyObservation` | `(location_name, station_id, obs_date)` | Daily local station max/min/avg temperature (`°F`), 1991–2020 NCEI normal & departure, precipitation (`in`), snow depth (`in`), snowfall (`in`), and daily mean/min/max sea-level pressure (`hPa`). |
| `weather_local_pressure_observations` | `_LocalPressureObservation` | `(location_name, station_id, obs_timestamp)` | Hourly NWS station barometric/sea-level pressure (`hPa`), temperature, dewpoint, and wind, extending local pressure history beyond the rolling 7-day NWS API window. |
| `weather_forecasts` | `_WeatherForecastVintage` | `(metric, model, model_run_time, valid_time, location)` | **Forecast Vintage Table**: Preserves every model initialization (`model_run_time`) targeting a `valid_time`. Stores `lead_days`, `lead_hours`, `value`, `ensemble_mean`, `ensemble_min`, `ensemble_max`, `ensemble_p25`, `ensemble_p75`, `ensemble_std`, `member_count`, `members_json` (31 GEFS members), and `deterministic_value`. |

---

## 2. Daily Ingestion & Forecast-Vintage Workflow

When `WeatherPatternsScreamsheet.collect_data_bundle()` runs:

1. **Fetch & Normalize**: Retrieves authoritative data from NOAA CPC (CDAS & GEFS 120-day CSVs), NOAA PSL (ROMI, MEI.v2), NASA GSFC (MERRA-2 / GEOS-5 FP), NOAA RCC-ACIS (1991–2020 normals & snow), and NWS API (observations, grid forecasts, AFD) across all configured locations.
   - `TeleconnectionProvider.parse_gefs_csv_multi_vintages()` extracts up to 12 recent daily 00Z GEFS initialization runs from the CPC 120-day ensemble file so multi-run forecast history is populated immediately.
2. **Persist Observations & Current Forecast Vintages**: Calls `persist_weather_patterns_bundle()`.
   - **Staleness / Failure Guard**: If any remote forecast endpoint failed and fell back to a stale cache entry (`is_stale = True`) or is unavailable, `persist_weather_patterns_bundle()` refuses to manufacture a synthetic forecast vintage.
3. **Query Historical Database**:
   - Retrieves recent forecast vintages via `get_forecast_vintages_for_metric()` for `AO`, `NAO`, `PNA`, and `U60N_10HPA`.
   - Backfills observation series from the local database if a live feed returned empty data.
   - Computes lead-day verification statistics via `compute_teleconnection_verification_stats()`.
4. **Compute Deterministic Forecast Evolution (`signals.py`)**:
   - `_compute_teleconnection_forecast_evolution()`: Calculates target date, `current_run`, `previous_run`, `three_runs_ago`, `five_runs_ago`, 24h / 3-run / 5-run changes, consecutive runs supporting a negative/positive/strong regime, first run introducing a strong (`>= 1.0 SD`) signal, ensemble IQR spread trend (`narrowing` vs. `widening`), and detects when a previously forecast signal disappears.
   - `_compute_stratosphere_forecast_evolution()`: Tracks predicted minimum 10-hPa 60°N zonal wind across runs, first/latest run showing a `< 0 m/s` reversal, consecutive runs forecasting reversal, crossing date, and explicit detection when a previously forecast reversal disappears.
   - `_build_what_changed_categories()`: Separates deterministic bullets into `OBSERVED`, `FORECAST`, `MODEL_TREND`, and `STRATOSPHERE`.
5. **Render Visuals & Narrative**:
   - Page 1 renders the **Forecast Evolution (Multi-Run Trend)** table and **Chart 5 (V2): Forecast Vintage Evolution** (`build_forecast_evolution_chart()`), plotting successive model runs by valid date.
   - `bundle.to_llm_packet()` passes the structured `FORECAST_EVOLUTION`, `WHAT_CHANGED`, and `teleconnections` / `stratosphere` evolution blocks to `WeatherPatternsSummarizer` under strict V2 epistemic rules (`src/screamsheet/llm/prompts/weather_patterns.txt`).

---

## 3. Maintenance, Backfill & Verification

- **`uv run db_update` (`src/screamsheet/db/db_update.py`)**:
  - Runs `purge_expired_weather_raw_cache()` to clean up expired raw HTTP cache blobs in `weather_data_cache` while **never** purging normalized observations or forecast vintages.
  - Runs `sync_weather_patterns_db()` to pragmatically backfill ~1.5 years (540 days) of daily AO/NAO/PNA and MJO observations, 5 years (60 months) of ENSO history, current/prior NH season stratosphere observations, recent GEFS forecast vintages, and local station observations/forecasts.
- **Verification & Analogs**:
  - `compute_teleconnection_verification_stats(index_name)` computes MAE, RMSE, bias, Pearson correlation, and sign accuracy at `D+3`, `D+5`, `D+7`, `D+10`, and `D+14`, always storing `sample_count` alongside each metric and withholding skill summaries until `sample_count >= min_samples_for_skill_claim` (default `10`).
  - `find_historical_teleconnection_analogs(ao_target, nao_target, pna_target)` finds historical dates in the local DB with the smallest 3D Euclidean distance in standardized index space.

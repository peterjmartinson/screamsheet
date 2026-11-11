# Weather Patterns & Teleconnections Screamsheet

The **Weather Patterns & Teleconnections** screamsheet (`WeatherPatternsScreamsheet`) produces a print-friendly 2–3 page morning meteorological briefing combining objective large-scale atmospheric and climate indices, model forecasts, local NWS station observations and forecasts, NCEI 1991–2020 climatological anomalies, snow-stake/snowfall tracking, B&W vector charts, and a strictly grounded LLM meteorological interpretation.

Core architectural principle:

> **Data first, interpretation second.**
> Every quantitative value, delta, anomaly, and regime flag is computed deterministically by the application before the LLM is called. The LLM receives only a structured JSON packet of verified numbers and is prohibited from inventing or extrapolating meteorological data.

---

## 1. Authoritative Data Sources, Products, Update Frequency & Units

| Domain | Authority / Provider Class | Exact Product & Endpoint URL | Update Frequency | Units & Notes |
| :--- | :--- | :--- | :--- | :--- |
| **AO, NAO, PNA (Observed)** | NOAA Climate Prediction Center (`TeleconnectionProvider`) | `https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.{ao,nao,pna}.cdas.{z1000,z500}.19500101_current.csv` | Daily | Standardized anomaly (`SD`). AO at 1000 hPa; NAO & PNA at 500 hPa. |
| **AO, NAO, PNA (Forecast)** | NOAA CPC / NCEP GEFS (`TeleconnectionProvider`) | `https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.{ao,nao,pna}.gefs.{z1000,z500}.120days.csv` | Daily (00Z init) | Standardized anomaly (`SD`). Preserves all 31 GEFS ensemble members through 14–15 days to compute ensemble mean, min, max, std, and interquartile spread (`p25`–`p75`). |
| **MJO** | Australian Bureau of Meteorology & NOAA PSL (`MJOProvider`) | • Primary (Wheeler–Hendon RMM): `http://www.bom.gov.au/clim_data/IDCKGEM000/rmm.74toRealtime.txt`<br>• Fallback (ROMI): `https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt` | Daily | Standardized Wheeler–Hendon `(RMM1, RMM2)` (or fallback PSL ROMI `comp1 = PC2`, `comp2 = -PC1`) converted into Wheeler–Hendon phase space (Phases 1–8) and amplitude (`sqrt(comp1² + comp2²)`). Active threshold: `amplitude >= 1.0`. |
| **Local Teleconnection Climatology** | Teleconnections ERA5 Climatology DB (`TeleconnectionEffectsProvider`) | Local SQLite database (`~/database/climate.db` or `TELECLIM_DB`), populated by the sibling `teleconnections` repository (`bootstrap_location.py`) using ERA5 1979–present daily reanalysis (`t2m_mean`, `t2m_max`, `t2m_min`, `precip_mm`). | Pre-computed / Auto-bootstrapped per location | Lagged composite anomalies (`mean_effect`, `median_effect`, `std_effect`, `p25`–`p75`, `prob_above_normal`, `prob_below_normal`, `p_value`, `significant`, `n_events`, `n_days`) across 12 overlapping 3-month seasons (`DJF`–`NDJ`) and lag windows (`0`, `1–5`, `6–10`, `11–15` days) for `AO`, `NAO`, `PNA`, `NINO34`, and `MJO`. |
| **ENSO** | NOAA CPC & NOAA PSL (`ENSOProvider`) | • Niño 3.4: `https://www.cpc.ncep.noaa.gov/data/indices/detrend.nino34.ascii.txt`<br>• ONI: `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`<br>• RONI: `https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt`<br>• MEI.v2: `https://psl.noaa.gov/enso/mei/data/meiv2.data` | Monthly / Seasonal | SST anomaly in `°C` (ERSSTv5 1991–2020 base period for Niño 3.4/ONI/RONI) and standardized bi-monthly index (`SD`) for MEI.v2. |
| **Stratospheric Polar Vortex / SSW** | NASA GSFC / GMAO via NOAA CPC Stratosphere Portal (`StratosphereProvider`) | `POST https://acd-ext.gsfc.nasa.gov/cgi-bin/datareq.pl` (`source=merra2`, `v04=on` [U 60°N], `v14=on` [T 60–90°N], `p10=on` [10 hPa], `north=on`) | Daily | Zonal-mean zonal wind $U$ at 10 hPa, 60°N (`m/s`, positive = westerly, negative = easterly) and polar cap temperature $T$ at 10 hPa, 60–90°N (`K`). Combines MERRA-2 reanalysis through current date with ~8-day GEOS-5 FP deterministic forecasts. |
| **Local Observations, Grid Forecast & AFD** | National Weather Service API (`NWSWeatherPatternsProvider`) | • `https://api.weather.gov/points/{lat},{lon}`<br>• `/stations/{stationId}/observations?limit=500`<br>• `/gridpoints/{wfo}/{x},{y}/forecast`<br>• `/gridpoints/{wfo}/{x},{y}`<br>• `/products/types/AFD/locations/{wfo}` | Hourly / Synoptic | Temp & dewpoint (`°F`), sea-level/barometric pressure (`hPa`), wind (`mph`), PoP (`%`), QPF (`inches`), raw gridpoint `snowfallAmount` (`inches`), and WFO Area Forecast Discussion synopsis. |
| **Historical Local Climate & Normals** | NOAA / NCEI Regional Climate Centers ACIS (`ClimateHistoryProvider`) | `POST https://data.rcc-acis.org/StnData` (`elems`: `maxt`, `mint`, `avgt`, `avgt` normal/departure, `pcpn`, `pcpn` normal) | Daily | Temperature (`°F`) and precipitation (`inches`) compared strictly against official **1991–2020 NCEI Climatological Normals**. |
| **Snow Observations** | NOAA / NCEI RCC-ACIS & NWS Grid (`SnowProvider`) | `POST https://data.rcc-acis.org/StnMeta` & `StnData` (`elems`: `snow`, `snwd`) | Daily | Snow depth (`snwd`, `inches`) and daily snowfall (`snow`, `inches`). Automatically discovers nearby active snow-reporting stations (preferring high-elevation snow stakes such as Mount Mansfield `USC00435416` at 3,950 ft near Stowe, VT). |

---

## 2. Index Meanings & Synoptic Context

- **AO (Arctic Oscillation, 1000 hPa)**: Measures surface pressure anomalies between the Arctic basin and mid-latitudes. Strongly negative AO (`<= -1.5 SD`) indicates high-latitude blocking and a weaker, more meridional polar jet stream allowing Arctic air masses to spill southward into mid-latitudes.
- **NAO (North Atlantic Oscillation, 500 hPa)**: Measures the height gradient between the Icelandic Low and Azores High. Negative NAO (`< 0 SD`) reflects Greenland/North Atlantic blocking, favoring colder air and coastal storm tracking near eastern North America.
- **PNA (Pacific–North American Pattern, 500 hPa)**: Positive PNA (`> 0 SD`) corresponds to an amplified western North America ridge and downstream eastern North America trough (favorable for East Coast cold intrusions). Negative PNA corresponds to western troughing and southeastern ridging.
- **MJO (Madden–Julian Oscillation, PSL ROMI)**: Eastward-propagating tropical convective dipole across Phases 1–8 (`1/8`: Western Hemisphere & Africa; `2–3`: Indian Ocean; `4–5`: Maritime Continent; `6–7`: Western Pacific). When active (`amplitude >= 1.0`), Phases 8, 1, and 2 statistically favor lagged high-latitude blocking and colder eastern US regimes ~1–2 weeks later, whereas Phases 4–6 favor milder eastern US patterns. When `amplitude < 1.0` (inside the unit circle), the MJO is weak/incoherent and phase is not interpreted aggressively.
- **ENSO (El Niño–Southern Oscillation)**: Slow-moving seasonal ocean-atmosphere background state in the equatorial Pacific (`+/- 0.5°C` Niño 3.4 / ONI threshold).
- **Stratospheric Polar Vortex (10 hPa, 60°N)**: Normally characterized by strong westerly circumpolar winds (`+20` to `+50 m/s`) in winter. Rapid deceleration or reversal to easterly (`< 0 m/s`) during a Sudden Stratospheric Warming (SSW) can propagate downward over 1–3 weeks, pushing the tropospheric AO/NAO negative.

---

## 3. Deterministic Signal-Change Calculations & Rule-Based Flags

`compute_derived_signals()` in `src/screamsheet/weather_patterns/signals.py` calculates all quantitative deltas and boolean flags before rendering or LLM summarization:

- `ao_strongly_negative` / `ao_strongly_positive`: Current CDAS AO `<= -1.5 SD` / `>= +1.5 SD`
- `nao_strongly_negative` / `nao_strongly_positive`: Current CDAS NAO `<= -1.5 SD` / `>= +1.5 SD`
- `pna_strongly_positive` / `pna_strongly_negative`: Current CDAS PNA `>= +1.5 SD` / `<= -1.5 SD`
- `mjo_active`: Latest ROMI amplitude `>= 1.0`
- `polar_vortex_rapidly_weakening`: 7-day observed 10-hPa 60°N wind change `<= -10.0 m/s` OR forecast drop `<= -15.0 m/s`
- `polar_vortex_reversal_observed`: Latest observed winter (Nov–Mar) 10-hPa 60°N zonal wind `< 0.0 m/s`
- `polar_vortex_reversal_forecast`: Forecast minimum winter 10-hPa 60°N zonal wind `< 0.0 m/s`
- `major_ssw_criteria_met`: **Strict WMO / Charlton & Polvani (2007) diagnostic check**:
  1. Extended winter season (Nov–Mar; excludes Apr–May final warming),
  2. Observed 10-hPa 60°N zonal-mean zonal wind reverses to easterly (`< 0.0 m/s`) for at least 2 recent days, **AND**
  3. 10-hPa 60–90°N polar cap temperature rises by `>= +8.0 K` over 7 days (confirming dynamic polar-cap warming alongside wind reversal).
  *A forecast crossing zero or a single slightly negative point never triggers `major_ssw_criteria_met`.*
- `pressure_persistently_high`: Primary location 7-day mean sea-level pressure `>= 1024.0 hPa` and current pressure `>= 1022.0 hPa`
- `major_pattern_change`: Any of AO, NAO, PNA has `|7d observed change| >= 1.5 SD`, `|7d GEFS forecast change| >= 1.5 SD`, or a sign flip with `|change| >= 1.0 SD`
- `signals_conflicting`: High-latitude blocking indicators (AO/NAO) and Pacific/tropical indicators (PNA, MJO, or stratospheric trend) point in opposing synoptic directions.

---

## 4. Known Limitations

1. **Stratospheric Ensemble Spread**: NOAA CPC's SSW monitoring page publishes PNG images rather than current CSV files. We retrieve numerical 10-hPa 60°N zonal wind and 60–90°N temperature from the CPC-linked NASA GSFC / GMAO MERRA-2 + GEOS-5 FP ASCII service (`datareq.pl`). Because GEOS-5 FP provides deterministic 8-day forecast leads without ensemble members, we display the deterministic forecast without manufacturing uncertainty bounds.
2. **NWS Station Observation Retention**: `https://api.weather.gov/stations/{id}/observations` retains ~7 days of hourly observations. Local sea-level pressure history is therefore shown over the 7-day NWS window, and we report actual pressure history and 24-hour tendency without claiming a 30-year climatological pressure anomaly.
3. **MJO Index Selection**: We standardize on the Australian Bureau of Meteorology's Wheeler–Hendon Real-time Multivariate MJO (**RMM**) index (`http://www.bom.gov.au/clim_data/IDCKGEM000/rmm.74toRealtime.txt`) so live daily phase/amplitude values match the historical MJO composites in `climate.db`, with NOAA PSL's Real-time OLR MJO Index (**ROMI**, `romi.cpcolr.1x.txt`) retained as an automatic fallback if BOM is unreachable.

---

## 5. Persistent Institutional Memory Database (V2) & Caching

V2 extends the V1 screamsheet with a persistent SQLite database layer (`src/screamsheet/db/weather_patterns_db.py`, unified in `screamsheet.db`) so Screamsheet tracks not only what NOAA says happened, but **what Screamsheet knew, when it knew it, and how model guidance evolved across runs**:

- **Forecast Vintage Preservation (`weather_forecasts`)**:
  - Uniqueness is keyed by `(metric, model, model_run_time, valid_time, location)` — **never** merely `metric + valid_time`.
  - Successive model runs (e.g., Nov 3, Nov 4, Nov 5, Nov 6 GEFS runs all predicting Nov 15 NAO, or successive GEOS-5 FP runs predicting 10-hPa 60°N zonal wind) are stored side-by-side without overwriting prior vintages.
  - Preserves ensemble mean, min, max, IQR (`p25`–`p75`), standard deviation, and serialized 31-member values where available.
- **Normalized Observation Tables**:
  - `weather_teleconnection_observations` (AO, NAO, PNA daily CDAS series)
  - `weather_stratosphere_observations` (10-hPa 60°N zonal wind & 60–90°N polar cap temperature)
  - `weather_mjo_observations` (daily PSL ROMI PC1/PC2, phase, amplitude, active status)
  - `weather_enso_observations` (monthly Niño 3.4, ONI, RONI, MEI.v2)
  - `weather_local_daily_observations` & `weather_local_pressure_observations` (persists local station hourly pressure beyond the rolling 7-day NWS API window, plus daily max/min/avg temperature, 1991–2020 departures, precipitation, snow depth, and snowfall for every configured location).
- **Deterministic Forecast-Evolution & Consistency Metrics**:
  - Computes 24-hour, 3-run, and 5-run forecast changes for a target valid date, ensemble IQR spread narrowing/widening, consecutive runs supporting a regime, and threshold-crossing persistence (e.g., first run, latest run, consecutive runs forecasting a `< 0 m/s` 10-hPa wind reversal, or explicit detection when a previously forecast reversal disappears).
  - Populates the Page 1 **Forecast Evolution (Multi-Run Trend)** table, **Chart 5 (V2): Forecast Vintage Evolution**, upgraded `WHAT_CHANGED` categories (`OBSERVED`, `FORECAST`, `MODEL_TREND`, `STRATOSPHERE`), and the V2 LLM packet.
- **Verification & Analog Groundwork**:
  - `compute_teleconnection_verification_stats()` compares archived forecast vintages against subsequently observed values by lead day (`D+3`, `D+5`, `D+7`, `D+10`, `D+14`), computing `sample_count`, MAE, RMSE, bias, Pearson correlation, and sign accuracy, while suppressing skill claims until `sample_count` reaches a meaningful threshold.
  - `find_historical_teleconnection_analogs()` queries historical `(AO, NAO, PNA)` states by Euclidean distance in SD space to support historical analog exploration.
- **Failure & Staleness Safeguards**:
  - Raw API responses remain cached in `weather_data_cache` (`src/screamsheet/db/weather_cache_db.py`) with fresh and stale fallback TTLs.
  - If today's remote fetch fails and falls back to stale cache (`is_stale = True`), V2 retains historical DB records, marks the source stale/unavailable, and **refuses to manufacture a fake forecast vintage** from stale data.

---

## 6. Configuration & Standalone Execution

### Configuration (`config.yaml`)

```yaml
weather_patterns:
  locations:
    - name: "Philadelphia"
      lat: 39.9526
      lon: -75.1652
      station: "KPHL"

    - name: "Stowe, VT"
      lat: 44.4654
      lon: -72.6874
      # Optional: station and snow_station are auto-discovered if omitted

  history_days: 60
  forecast_days: 14

  charts:
    teleconnections: true
    polar_vortex: true
    mjo: true
    enso: true
    local_pressure: true
    local_temperature: true
    snow: true

  narrative:
    enabled: true
    max_words: 200
    include_afd: true
```

### Generating the Screamsheet

```bash
# Run standalone via CLI:
uv run screamsheet --single "Weather Patterns"

# Bypass cache or force refresh:
uv run screamsheet --single "Weather Patterns" --refresh-cache
```

Or programmatically via `ScreamsheetFactory`:

```python
from screamsheet.config import load_config
from screamsheet.factory import ScreamsheetFactory

cfg = load_config()
sheet = ScreamsheetFactory.create_weather_patterns_screamsheet(
    output_filename="Files/WEATHER_PATTERNS.pdf",
    weather_patterns_config=cfg.weather_patterns,
)
sheet.generate()
```

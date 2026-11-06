"""Persistent SQLite database for Weather Patterns / Teleconnections (V2).

Preserves institutional memory for Screamsheet:
  1. Historical objective observations (AO, NAO, PNA, MJO, ENSO, Stratosphere,
     and local NWS/NCEI temperature, pressure, precipitation, snow).
  2. Multi-run forecast vintages (never overwriting past model runs that targeted
     the same valid date) so Screamsheet can compute run-to-run forecast evolution,
     threshold-crossing persistence, and post-event verification skill.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path
from ..weather_patterns.models import (
    DailyClimatePoint,
    ENSOBundle,
    HourlyPressurePoint,
    LocalLocationBundle,
    MJOBundle,
    MJODailyPoint,
    SnowDailyPoint,
    StratosphereBundle,
    StratosphereDailyPoint,
    TeleconnectionDailyObs,
    TeleconnectionForecastDay,
    TeleconnectionIndexBundle,
    WeatherPatternsDataBundle,
)

logger = logging.getLogger("screamsheet.weather_patterns.db")

WEATHER_PATTERNS_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# ORM Models (Unified under screamsheet.db _Base)
# ---------------------------------------------------------------------------

class _WeatherSchemaMeta(_Base):
    """Schema version & migration metadata for Weather Patterns tables."""
    __tablename__ = "weather_patterns_schema_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_version = Column(Integer, nullable=False)
    updated_at = Column(String(40), nullable=False)
    notes = Column(String(255), nullable=True)


class _TeleconnectionObservation(_Base):
    """Daily objective teleconnection index observations (AO, NAO, PNA)."""
    __tablename__ = "weather_teleconnection_observations"
    __table_args__ = (
        UniqueConstraint("index_name", "obs_date", "source", name="uq_tele_obs_idx_date_src"),
        Index("ix_tele_obs_idx_date", "index_name", "obs_date"),
        Index("ix_tele_obs_date", "obs_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_name = Column(String(20), nullable=False)       # "AO" | "NAO" | "PNA"
    obs_date = Column(String(20), nullable=False)         # YYYY-MM-DD
    value = Column(Float, nullable=False)                 # SD units
    units = Column(String(20), nullable=False, default="SD")
    level_label = Column(String(30), nullable=True)       # "1000 hPa" | "500 hPa"
    source = Column(String(100), nullable=False, default="NOAA CPC")
    product = Column(String(120), nullable=False, default="CDAS")
    retrieved_at = Column(String(40), nullable=False)


class _StratosphereObservation(_Base):
    """Daily stratospheric polar vortex reanalysis observations (10 hPa 60°N U & 60-90°N T)."""
    __tablename__ = "weather_stratosphere_observations"
    __table_args__ = (
        UniqueConstraint("obs_date", "level_hpa", "latitude_deg", "source", name="uq_strat_obs_date_lvl"),
        Index("ix_strat_obs_date", "obs_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    obs_date = Column(String(20), nullable=False)                  # YYYY-MM-DD
    level_hpa = Column(Integer, nullable=False, default=10)
    latitude_deg = Column(Integer, nullable=False, default=60)
    zonal_wind_ms = Column(Float, nullable=False)                  # m/s
    polar_cap_temp_k = Column(Float, nullable=True)                # Kelvin (60-90°N)
    wind_units = Column(String(20), nullable=False, default="m/s")
    temp_units = Column(String(20), nullable=False, default="K")
    source = Column(String(100), nullable=False, default="NASA GSFC / GMAO")
    product = Column(String(120), nullable=False, default="MERRA-2")
    retrieved_at = Column(String(40), nullable=False)


class _MJOObservation(_Base):
    """Daily MJO phase-space observations (NOAA PSL ROMI)."""
    __tablename__ = "weather_mjo_observations"
    __table_args__ = (
        UniqueConstraint("obs_date", "product", name="uq_mjo_obs_date_prod"),
        Index("ix_mjo_obs_date", "obs_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    obs_date = Column(String(20), nullable=False)          # YYYY-MM-DD
    component_1 = Column(Float, nullable=False)            # RMM1-equiv (PC2(ROMI))
    component_2 = Column(Float, nullable=False)            # RMM2-equiv (-PC1(ROMI))
    raw_pc1 = Column(Float, nullable=False)
    raw_pc2 = Column(Float, nullable=False)
    amplitude = Column(Float, nullable=False)
    phase = Column(Integer, nullable=False)                # 1..8
    active = Column(Integer, nullable=False, default=0)    # 1 if amplitude >= 1.0 else 0
    units = Column(String(20), nullable=False, default="SD")
    source = Column(String(100), nullable=False, default="NOAA PSL")
    product = Column(String(120), nullable=False, default="ROMI (CPC OLR)")
    retrieved_at = Column(String(40), nullable=False)


class _ENSOObservation(_Base):
    """Monthly / seasonal ENSO background observations (Niño 3.4, ONI, RONI, MEI.v2)."""
    __tablename__ = "weather_enso_observations"
    __table_args__ = (
        UniqueConstraint("period", "source", name="uq_enso_obs_period_src"),
        Index("ix_enso_obs_period", "period"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(20), nullable=False)            # YYYY-MM
    nino34_anomaly = Column(Float, nullable=False)         # °C
    nino34_total = Column(Float, nullable=True)            # °C
    oni_anomaly = Column(Float, nullable=True)             # °C
    roni_anomaly = Column(Float, nullable=True)            # °C
    meiv2 = Column(Float, nullable=True)                   # SD
    units = Column(String(20), nullable=False, default="degC")
    source = Column(String(100), nullable=False, default="NOAA CPC / PSL")
    product = Column(String(120), nullable=False, default="ERSSTv5 Nino3.4 / ONI / MEI.v2")
    retrieved_at = Column(String(40), nullable=False)


class _LocalDailyObservation(_Base):
    """Daily local station climate & snow observations ( supports analog & local correlation queries)."""
    __tablename__ = "weather_local_daily_observations"
    __table_args__ = (
        UniqueConstraint("location_name", "station_id", "obs_date", name="uq_local_daily_loc_stn_date"),
        Index("ix_local_daily_loc_date", "location_name", "obs_date"),
        Index("ix_local_daily_date", "obs_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_name = Column(String(100), nullable=False)
    station_id = Column(String(40), nullable=False)
    obs_date = Column(String(20), nullable=False)          # YYYY-MM-DD
    max_temp_f = Column(Float, nullable=True)
    min_temp_f = Column(Float, nullable=True)
    avg_temp_f = Column(Float, nullable=True)
    normal_temp_f = Column(Float, nullable=True)
    temp_departure_f = Column(Float, nullable=True)
    precip_in = Column(Float, nullable=True)
    normal_precip_in = Column(Float, nullable=True)
    snow_depth_in = Column(Float, nullable=True)
    snowfall_in = Column(Float, nullable=True)
    snow_station_id = Column(String(40), nullable=True)
    mean_pressure_hpa = Column(Float, nullable=True)
    min_pressure_hpa = Column(Float, nullable=True)
    max_pressure_hpa = Column(Float, nullable=True)
    source = Column(String(100), nullable=False, default="NOAA RCC-ACIS / NWS")
    product = Column(String(120), nullable=False, default="Daily Station Summary & 1991-2020 Normals")
    retrieved_at = Column(String(40), nullable=False)


class _LocalPressureObservation(_Base):
    """Hourly local station barometric/sea-level pressure observations (persists beyond 7d NWS window)."""
    __tablename__ = "weather_local_pressure_observations"
    __table_args__ = (
        UniqueConstraint("location_name", "station_id", "obs_timestamp", name="uq_local_press_loc_stn_ts"),
        Index("ix_local_press_loc_ts", "location_name", "obs_timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_name = Column(String(100), nullable=False)
    station_id = Column(String(40), nullable=False)
    obs_timestamp = Column(String(40), nullable=False)     # ISO-8601
    pressure_hpa = Column(Float, nullable=False)
    temp_f = Column(Float, nullable=True)
    dewpoint_f = Column(Float, nullable=True)
    wind_mph = Column(Float, nullable=True)
    units = Column(String(20), nullable=False, default="hPa")
    source = Column(String(100), nullable=False, default="NWS API")
    product = Column(String(120), nullable=False, default="Station Hourly Observation")
    retrieved_at = Column(String(40), nullable=False)


class _WeatherForecastVintage(_Base):
    """Multi-run forecast vintage storage.

    CRITICAL DESIGN PRINCIPLE:
    Never overwrite a historical forecast run simply because it shares ``metric`` + ``valid_time``.
    Uniqueness includes ``model_run_time`` (initialization vintage) so successive model runs
    targeting the same valid date are preserved side-by-side.
    """
    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "metric",
            "model",
            "model_run_time",
            "valid_time",
            "location",
            name="uq_weather_forecast_vintage",
        ),
        Index("ix_fcst_metric_model_run", "metric", "model", "model_run_time"),
        Index("ix_fcst_metric_valid", "metric", "valid_time"),
        Index("ix_fcst_metric_loc_run", "metric", "location", "model_run_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String(50), nullable=False)            # e.g. "AO", "NAO", "PNA", "U60N_10HPA", "NWS_HIGH_F", "NWS_SNOW_IN"
    product = Column(String(120), nullable=False)          # e.g. "GEFS 31-Member Ensemble", "GEOS-5 FP", "NWS Grid Forecast"
    source = Column(String(100), nullable=False)           # e.g. "NOAA CPC", "NASA GSFC", "NWS API"
    model = Column(String(60), nullable=False)             # e.g. "GEFS", "GEOS5_FP", "NWS_NDFD"
    model_run_time = Column(String(40), nullable=False)    # e.g. "2026-11-04T00:00Z" (forecast vintage key)
    retrieved_at = Column(String(40), nullable=False)      # ISO-8601 UTC retrieval time
    valid_time = Column(String(40), nullable=False)        # YYYY-MM-DD
    lead_days = Column(Integer, nullable=False)            # integer days from model_run_time to valid_time
    lead_hours = Column(Integer, nullable=False)           # lead_days * 24 (or exact forecast hours)
    location = Column(String(100), nullable=False, default="GLOBAL")
    value = Column(Float, nullable=False)                  # primary forecast value (ensemble mean or deterministic)
    ensemble_mean = Column(Float, nullable=True)
    ensemble_min = Column(Float, nullable=True)
    ensemble_max = Column(Float, nullable=True)
    ensemble_p25 = Column(Float, nullable=True)
    ensemble_p75 = Column(Float, nullable=True)
    ensemble_std = Column(Float, nullable=True)
    member_count = Column(Integer, nullable=True)
    members_json = Column(Text, nullable=True)             # JSON list of float ensemble members when available
    deterministic_value = Column(Float, nullable=True)     # e.g. deterministic GFS or secondary variable (polar cap T)
    units = Column(String(20), nullable=False)             # "SD", "m/s", "degF", "in", "%"


# ---------------------------------------------------------------------------
# Engine & Schema Initialization / Versioning
# ---------------------------------------------------------------------------

def _get_engine(db_path: Optional[Path] = None):
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_weather_patterns_db(db_path: Optional[Path] = None):
    """Initialize all Weather Patterns V2 tables, indexes, and schema version record."""
    engine = _get_engine(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        meta = (
            session.query(_WeatherSchemaMeta)
            .order_by(_WeatherSchemaMeta.schema_version.desc())
            .first()
        )
        if not meta or meta.schema_version < WEATHER_PATTERNS_SCHEMA_VERSION:
            session.add(
                _WeatherSchemaMeta(
                    schema_version=WEATHER_PATTERNS_SCHEMA_VERSION,
                    updated_at=now_iso,
                    notes="V2 institutional memory: observations + forecast vintages + verification",
                )
            )
            session.commit()
    return engine


def get_weather_schema_version(db_path: Optional[Path] = None) -> int:
    """Return the active Weather Patterns schema version."""
    engine = init_weather_patterns_db(db_path)
    with Session(engine) as session:
        meta = (
            session.query(_WeatherSchemaMeta)
            .order_by(_WeatherSchemaMeta.schema_version.desc())
            .first()
        )
        return int(meta.schema_version) if meta else 0


# ---------------------------------------------------------------------------
# Idempotent Ingestion: Observations
# ---------------------------------------------------------------------------

def save_teleconnection_observations(
    index_name: str,
    observations: List[TeleconnectionDailyObs],
    level_label: str = "",
    source: str = "NOAA CPC",
    product: str = "CDAS",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Idempotently persist daily teleconnection observations (AO, NAO, PNA)."""
    if not observations:
        return 0
    engine = init_weather_patterns_db(db_path)
    idx_key = index_name.upper().strip()
    ret_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    count = 0

    with Session(engine) as session:
        existing_rows = (
            session.query(_TeleconnectionObservation)
            .filter(
                _TeleconnectionObservation.index_name == idx_key,
                _TeleconnectionObservation.source == source,
            )
            .all()
        )
        by_date = {r.obs_date: r for r in existing_rows}

        for pt in observations:
            if not pt.date or pt.value is None or math.isnan(pt.value):
                continue
            existing = by_date.get(pt.date)
            if existing is not None:
                if abs(existing.value - float(pt.value)) > 1e-6:
                    existing.value = float(pt.value)
                    existing.retrieved_at = ret_ts
                    count += 1
            else:
                row = _TeleconnectionObservation(
                    index_name=idx_key,
                    obs_date=pt.date,
                    value=float(pt.value),
                    units="SD",
                    level_label=level_label,
                    source=source,
                    product=product,
                    retrieved_at=ret_ts,
                )
                session.add(row)
                by_date[pt.date] = row
                count += 1
        session.commit()
    return count


def save_stratosphere_observations(
    observations: List[StratosphereDailyPoint],
    level_hpa: int = 10,
    latitude_deg: int = 60,
    source: str = "NASA GSFC / GMAO",
    product: str = "MERRA-2",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Idempotently persist daily 10-hPa 60°N zonal wind and 60–90°N cap temperature observations."""
    obs_only = [p for p in observations if not p.is_forecast]
    if not obs_only:
        return 0
    engine = init_weather_patterns_db(db_path)
    ret_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    count = 0

    with Session(engine) as session:
        existing_rows = (
            session.query(_StratosphereObservation)
            .filter(
                _StratosphereObservation.level_hpa == level_hpa,
                _StratosphereObservation.latitude_deg == latitude_deg,
                _StratosphereObservation.source == source,
            )
            .all()
        )
        by_date = {r.obs_date: r for r in existing_rows}

        for pt in obs_only:
            if not pt.date or pt.zonal_wind_10hpa_60n is None:
                continue
            existing = by_date.get(pt.date)
            t_val = (
                float(pt.polar_cap_temp_10hpa_60_90n)
                if pt.polar_cap_temp_10hpa_60_90n is not None
                else None
            )
            if existing is not None:
                changed = abs(existing.zonal_wind_ms - float(pt.zonal_wind_10hpa_60n)) > 1e-5
                if t_val is not None and (
                    existing.polar_cap_temp_k is None
                    or abs(existing.polar_cap_temp_k - t_val) > 1e-5
                ):
                    existing.polar_cap_temp_k = t_val
                    changed = True
                if changed:
                    existing.zonal_wind_ms = float(pt.zonal_wind_10hpa_60n)
                    existing.retrieved_at = ret_ts
                    count += 1
            else:
                row = _StratosphereObservation(
                    obs_date=pt.date,
                    level_hpa=level_hpa,
                    latitude_deg=latitude_deg,
                    zonal_wind_ms=float(pt.zonal_wind_10hpa_60n),
                    polar_cap_temp_k=t_val,
                    wind_units="m/s",
                    temp_units="K",
                    source=source,
                    product=product,
                    retrieved_at=ret_ts,
                )
                session.add(row)
                by_date[pt.date] = row
                count += 1
        session.commit()
    return count


def save_mjo_observations(
    points: List[MJODailyPoint],
    source: str = "NOAA PSL",
    product: str = "ROMI (CPC OLR)",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Idempotently persist daily MJO ROMI observations."""
    if not points:
        return 0
    engine = init_weather_patterns_db(db_path)
    ret_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    count = 0

    with Session(engine) as session:
        existing_rows = (
            session.query(_MJOObservation)
            .filter(_MJOObservation.product == product)
            .all()
        )
        by_date = {r.obs_date: r for r in existing_rows}

        for pt in points:
            if not pt.date:
                continue
            existing = by_date.get(pt.date)
            if existing is not None:
                if (
                    abs(existing.amplitude - float(pt.amplitude)) > 1e-5
                    or existing.phase != int(pt.phase)
                ):
                    existing.component_1 = float(pt.component_1)
                    existing.component_2 = float(pt.component_2)
                    existing.raw_pc1 = float(pt.raw_pc1)
                    existing.raw_pc2 = float(pt.raw_pc2)
                    existing.amplitude = float(pt.amplitude)
                    existing.phase = int(pt.phase)
                    existing.active = 1 if pt.active else 0
                    existing.retrieved_at = ret_ts
                    count += 1
            else:
                row = _MJOObservation(
                    obs_date=pt.date,
                    component_1=float(pt.component_1),
                    component_2=float(pt.component_2),
                    raw_pc1=float(pt.raw_pc1),
                    raw_pc2=float(pt.raw_pc2),
                    amplitude=float(pt.amplitude),
                    phase=int(pt.phase),
                    active=1 if pt.active else 0,
                    units="SD",
                    source=source,
                    product=product,
                    retrieved_at=ret_ts,
                )
                session.add(row)
                by_date[pt.date] = row
                count += 1
        session.commit()
    return count


def save_enso_observations(
    bundle: ENSOBundle,
    source: str = "NOAA CPC / PSL",
    product: str = "ERSSTv5 Nino3.4 / ONI / MEI.v2",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Idempotently persist monthly ENSO observations."""
    if not bundle or not bundle.nino34_series:
        return 0
    engine = init_weather_patterns_db(db_path)
    ret_ts = retrieved_at or (bundle.provenance.retrieved_at if bundle.provenance else datetime.now(timezone.utc).isoformat())
    count = 0

    with Session(engine) as session:
        existing_rows = (
            session.query(_ENSOObservation)
            .filter(_ENSOObservation.source == source)
            .all()
        )
        by_period = {r.period: r for r in existing_rows}

        for pt in bundle.nino34_series:
            if not pt.period or pt.nino34_anomaly is None:
                continue
            existing = by_period.get(pt.period)
            if existing is not None:
                changed = abs(existing.nino34_anomaly - float(pt.nino34_anomaly)) > 1e-5
                for attr in ("nino34_total", "oni_anomaly", "roni_anomaly", "meiv2"):
                    new_v = getattr(pt, attr)
                    old_v = getattr(existing, attr)
                    if new_v is not None and (old_v is None or abs(old_v - float(new_v)) > 1e-5):
                        setattr(existing, attr, float(new_v))
                        changed = True
                if changed:
                    existing.nino34_anomaly = float(pt.nino34_anomaly)
                    existing.retrieved_at = ret_ts
                    count += 1
            else:
                row = _ENSOObservation(
                    period=pt.period,
                    nino34_anomaly=float(pt.nino34_anomaly),
                    nino34_total=float(pt.nino34_total) if pt.nino34_total is not None else None,
                    oni_anomaly=float(pt.oni_anomaly) if pt.oni_anomaly is not None else None,
                    roni_anomaly=float(pt.roni_anomaly) if pt.roni_anomaly is not None else None,
                    meiv2=float(pt.meiv2) if pt.meiv2 is not None else None,
                    units="degC",
                    source=source,
                    product=product,
                    retrieved_at=ret_ts,
                )
                session.add(row)
                by_period[pt.period] = row
                count += 1
        session.commit()
    return count


def save_local_location_observations(
    loc: LocalLocationBundle,
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Idempotently persist local hourly pressure observations and daily climate/snow series."""
    if not loc:
        return 0
    engine = init_weather_patterns_db(db_path)
    ret_ts = (
        retrieved_at
        or (loc.nws_provenance.retrieved_at if loc.nws_provenance else None)
        or datetime.now(timezone.utc).isoformat()
    )
    stn_id = loc.station_id or loc.name
    count = 0

    with Session(engine) as session:
        # 1. Hourly pressure observations
        if loc.pressure_series:
            existing_p = (
                session.query(_LocalPressureObservation)
                .filter(
                    _LocalPressureObservation.location_name == loc.name,
                    _LocalPressureObservation.station_id == stn_id,
                )
                .all()
            )
            p_by_ts = {r.obs_timestamp: r for r in existing_p}
            for hp in loc.pressure_series:
                if not hp.timestamp or hp.pressure_hpa is None:
                    continue
                if hp.timestamp not in p_by_ts:
                    is_latest = (loc.obs_timestamp and hp.timestamp == loc.obs_timestamp)
                    row = _LocalPressureObservation(
                        location_name=loc.name,
                        station_id=stn_id,
                        obs_timestamp=hp.timestamp,
                        pressure_hpa=float(hp.pressure_hpa),
                        temp_f=float(loc.current_temp_f) if (is_latest and loc.current_temp_f is not None) else None,
                        dewpoint_f=float(loc.current_dewpoint_f) if (is_latest and loc.current_dewpoint_f is not None) else None,
                        wind_mph=float(loc.current_wind_mph) if (is_latest and loc.current_wind_mph is not None) else None,
                        units="hPa",
                        source="NWS API",
                        product="Station Hourly Observation",
                        retrieved_at=ret_ts,
                    )
                    session.add(row)
                    p_by_ts[hp.timestamp] = row
                    count += 1

        # Group hourly pressure by YYYY-MM-DD to enrich daily local observations
        daily_press_map: Dict[str, List[float]] = {}
        for hp in loc.pressure_series:
            if hp.timestamp and len(hp.timestamp) >= 10 and hp.pressure_hpa is not None:
                d_key = hp.timestamp[:10]
                daily_press_map.setdefault(d_key, []).append(float(hp.pressure_hpa))

        # Index snow points by date
        snow_by_date: Dict[str, SnowDailyPoint] = {}
        snow_stn_id: Optional[str] = None
        if loc.snow and loc.snow.daily_series:
            snow_stn_id = loc.snow.station_id
            for sp in loc.snow.daily_series:
                if sp.date:
                    snow_by_date[sp.date] = sp

        # Index climate points by date
        clim_by_date: Dict[str, DailyClimatePoint] = {
            cp.date: cp for cp in (loc.climate_series or []) if cp.date
        }

        all_dates = sorted(set(clim_by_date.keys()) | set(snow_by_date.keys()) | set(daily_press_map.keys()))
        if all_dates:
            existing_d = (
                session.query(_LocalDailyObservation)
                .filter(
                    _LocalDailyObservation.location_name == loc.name,
                    _LocalDailyObservation.station_id == stn_id,
                )
                .all()
            )
            d_by_date = {r.obs_date: r for r in existing_d}

            for d_str in all_dates:
                cp = clim_by_date.get(d_str)
                sp = snow_by_date.get(d_str)
                p_vals = daily_press_map.get(d_str)

                mean_p = round(sum(p_vals) / len(p_vals), 2) if p_vals else None
                min_p = round(min(p_vals), 2) if p_vals else None
                max_p = round(max(p_vals), 2) if p_vals else None

                existing_row = d_by_date.get(d_str)
                if existing_row is not None:
                    updated = False
                    if cp:
                        for col_attr, val in (
                            ("max_temp_f", cp.max_temp_f),
                            ("min_temp_f", cp.min_temp_f),
                            ("avg_temp_f", cp.avg_temp_f),
                            ("normal_temp_f", cp.normal_temp_f),
                            ("temp_departure_f", cp.temp_departure_f),
                            ("precip_in", cp.precip_in),
                            ("normal_precip_in", cp.normal_precip_in),
                        ):
                            if val is not None and getattr(existing_row, col_attr) != float(val):
                                setattr(existing_row, col_attr, float(val))
                                updated = True
                    if sp:
                        if sp.snow_depth_in is not None and existing_row.snow_depth_in != float(sp.snow_depth_in):
                            existing_row.snow_depth_in = float(sp.snow_depth_in)
                            updated = True
                        if sp.snowfall_in is not None and existing_row.snowfall_in != float(sp.snowfall_in):
                            existing_row.snowfall_in = float(sp.snowfall_in)
                            updated = True
                        if snow_stn_id and existing_row.snow_station_id != snow_stn_id:
                            existing_row.snow_station_id = snow_stn_id
                            updated = True
                    if mean_p is not None and existing_row.mean_pressure_hpa != mean_p:
                        existing_row.mean_pressure_hpa = mean_p
                        existing_row.min_pressure_hpa = min_p
                        existing_row.max_pressure_hpa = max_p
                        updated = True
                    if updated:
                        existing_row.retrieved_at = ret_ts
                        count += 1
                else:
                    row = _LocalDailyObservation(
                        location_name=loc.name,
                        station_id=stn_id,
                        obs_date=d_str,
                        max_temp_f=float(cp.max_temp_f) if (cp and cp.max_temp_f is not None) else None,
                        min_temp_f=float(cp.min_temp_f) if (cp and cp.min_temp_f is not None) else None,
                        avg_temp_f=float(cp.avg_temp_f) if (cp and cp.avg_temp_f is not None) else None,
                        normal_temp_f=float(cp.normal_temp_f) if (cp and cp.normal_temp_f is not None) else None,
                        temp_departure_f=float(cp.temp_departure_f) if (cp and cp.temp_departure_f is not None) else None,
                        precip_in=float(cp.precip_in) if (cp and cp.precip_in is not None) else None,
                        normal_precip_in=float(cp.normal_precip_in) if (cp and cp.normal_precip_in is not None) else None,
                        snow_depth_in=float(sp.snow_depth_in) if (sp and sp.snow_depth_in is not None) else None,
                        snowfall_in=float(sp.snowfall_in) if (sp and sp.snowfall_in is not None) else None,
                        snow_station_id=snow_stn_id,
                        mean_pressure_hpa=mean_p,
                        min_pressure_hpa=min_p,
                        max_pressure_hpa=max_p,
                        source="NOAA RCC-ACIS / NWS",
                        product="Daily Station Summary & 1991-2020 Normals",
                        retrieved_at=ret_ts,
                    )
                    session.add(row)
                    d_by_date[d_str] = row
                    count += 1

        session.commit()
    return count


# ---------------------------------------------------------------------------
# Idempotent Ingestion: Forecast Vintages (Preserves Run History!)
# ---------------------------------------------------------------------------

def _normalize_run_time(init_str: str) -> str:
    """Normalize a forecast initialization timestamp to YYYY-MM-DDTHH:MMZ."""
    s = init_str.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s}T00:00Z"
    if " " in s and "Z" in s:
        # e.g. "2026-11-04 00Z"
        parts = s.split()
        d_part = parts[0]
        hr_part = parts[1].replace("Z", "").zfill(2)
        return f"{d_part}T{hr_part}:00Z"
    return s


def save_teleconnection_forecast_vintage(
    index_name: str,
    forecasts: List[TeleconnectionForecastDay],
    source: str = "NOAA CPC / NCEP GEFS",
    product: Optional[str] = None,
    model: str = "GEFS",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist GEFS teleconnection forecast vintage rows without overwriting prior model runs."""
    if not forecasts:
        return 0
    engine = init_weather_patterns_db(db_path)
    metric = index_name.upper().strip()
    prod_name = product or f"{metric} GEFS 31-Member Ensemble"
    ret_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    count = 0

    with Session(engine) as session:
        for f in forecasts:
            if not f.init_date or not f.valid_date:
                continue
            run_time = _normalize_run_time(f.init_date)
            existing = (
                session.query(_WeatherForecastVintage)
                .filter(
                    _WeatherForecastVintage.metric == metric,
                    _WeatherForecastVintage.model == model,
                    _WeatherForecastVintage.model_run_time == run_time,
                    _WeatherForecastVintage.valid_time == f.valid_date,
                    _WeatherForecastVintage.location == "GLOBAL",
                )
                .first()
            )
            members_str = json.dumps([round(m, 3) for m in f.members]) if f.members else None
            if existing is not None:
                # Same model_run_time + valid_time: update only if values changed
                if abs(existing.value - float(f.ensemble_mean)) > 1e-5:
                    existing.value = float(f.ensemble_mean)
                    existing.ensemble_mean = float(f.ensemble_mean)
                    existing.ensemble_min = float(f.ensemble_min)
                    existing.ensemble_max = float(f.ensemble_max)
                    existing.ensemble_p25 = float(f.ensemble_p25)
                    existing.ensemble_p75 = float(f.ensemble_p75)
                    existing.ensemble_std = float(f.ensemble_std)
                    existing.member_count = int(f.member_count)
                    existing.members_json = members_str
                    existing.deterministic_value = (
                        float(f.deterministic_gfs) if f.deterministic_gfs is not None else None
                    )
                    existing.retrieved_at = ret_ts
                    count += 1
            else:
                row = _WeatherForecastVintage(
                    metric=metric,
                    product=prod_name,
                    source=source,
                    model=model,
                    model_run_time=run_time,
                    retrieved_at=ret_ts,
                    valid_time=f.valid_date,
                    lead_days=int(f.lead_days),
                    lead_hours=int(f.lead_days) * 24,
                    location="GLOBAL",
                    value=float(f.ensemble_mean),
                    ensemble_mean=float(f.ensemble_mean),
                    ensemble_min=float(f.ensemble_min),
                    ensemble_max=float(f.ensemble_max),
                    ensemble_p25=float(f.ensemble_p25),
                    ensemble_p75=float(f.ensemble_p75),
                    ensemble_std=float(f.ensemble_std),
                    member_count=int(f.member_count),
                    members_json=members_str,
                    deterministic_value=(
                        float(f.deterministic_gfs) if f.deterministic_gfs is not None else None
                    ),
                    units="SD",
                )
                session.add(row)
                count += 1
        session.commit()
    return count


def save_stratosphere_forecast_vintage(
    bundle: StratosphereBundle,
    run_date: Optional[str] = None,
    source: str = "NASA GSFC / GMAO",
    product: str = "GEOS-5 FP 10-hPa 60N Forecast",
    model: str = "GEOS5_FP",
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist stratospheric 10-hPa 60°N zonal wind & polar cap temp forecast vintage."""
    if not bundle or not bundle.forecasts:
        return 0
    # Determine model initialization date from latest observation date or explicit run_date
    init_d = run_date
    if not init_d and bundle.observations:
        init_d = bundle.observations[-1].date
    if not init_d:
        init_d = bundle.forecasts[0].date
    run_time = _normalize_run_time(init_d)
    init_dt = datetime.strptime(run_time[:10], "%Y-%m-%d")

    ret_ts = (
        retrieved_at
        or (bundle.provenance.retrieved_at if bundle.provenance else None)
        or datetime.now(timezone.utc).isoformat()
    )
    engine = init_weather_patterns_db(db_path)
    count = 0

    with Session(engine) as session:
        for pt in bundle.forecasts:
            if not pt.date or pt.zonal_wind_10hpa_60n is None:
                continue
            try:
                valid_dt = datetime.strptime(pt.date[:10], "%Y-%m-%d")
                lead_d = max(1, (valid_dt - init_dt).days)
            except Exception:
                lead_d = 1

            # Store U60N_10HPA
            existing_u = (
                session.query(_WeatherForecastVintage)
                .filter(
                    _WeatherForecastVintage.metric == "U60N_10HPA",
                    _WeatherForecastVintage.model == model,
                    _WeatherForecastVintage.model_run_time == run_time,
                    _WeatherForecastVintage.valid_time == pt.date,
                    _WeatherForecastVintage.location == "GLOBAL",
                )
                .first()
            )
            t_val = (
                float(pt.polar_cap_temp_10hpa_60_90n)
                if pt.polar_cap_temp_10hpa_60_90n is not None
                else None
            )
            if existing_u is not None:
                if abs(existing_u.value - float(pt.zonal_wind_10hpa_60n)) > 1e-5:
                    existing_u.value = float(pt.zonal_wind_10hpa_60n)
                    existing_u.deterministic_value = t_val
                    existing_u.retrieved_at = ret_ts
                    count += 1
            else:
                session.add(
                    _WeatherForecastVintage(
                        metric="U60N_10HPA",
                        product=product,
                        source=source,
                        model=model,
                        model_run_time=run_time,
                        retrieved_at=ret_ts,
                        valid_time=pt.date,
                        lead_days=lead_d,
                        lead_hours=lead_d * 24,
                        location="GLOBAL",
                        value=float(pt.zonal_wind_10hpa_60n),
                        deterministic_value=t_val,
                        units="m/s",
                    )
                )
                count += 1
        session.commit()
    return count


def save_nws_local_forecast_vintage(
    loc: LocalLocationBundle,
    report_date: str,
    retrieved_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist local NWS 7-day forecast vintage (High/Low temp, PoP, QPF, Snow) per location."""
    if not loc or not loc.daily_forecasts:
        return 0
    # Use report_date (or obs_timestamp date) as the daily NWS forecast vintage key
    init_date = report_date[:10] if report_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_time = _normalize_run_time(init_date)
    init_dt = datetime.strptime(init_date, "%Y-%m-%d")
    ret_ts = (
        retrieved_at
        or (loc.nws_provenance.retrieved_at if loc.nws_provenance else None)
        or datetime.now(timezone.utc).isoformat()
    )
    engine = init_weather_patterns_db(db_path)
    count = 0

    with Session(engine) as session:
        for df in loc.daily_forecasts:
            if not df.date:
                continue
            try:
                valid_dt = datetime.strptime(df.date[:10], "%Y-%m-%d")
                lead_d = max(0, (valid_dt - init_dt).days)
            except Exception:
                lead_d = 0

            metrics_to_save: List[Tuple[str, Optional[float], str]] = [
                ("NWS_HIGH_F", df.high_f, "degF"),
                ("NWS_LOW_F", df.low_f, "degF"),
                ("NWS_POP_PCT", float(df.pop_pct) if df.pop_pct is not None else None, "%"),
                ("NWS_QPF_IN", df.qpf_in, "in"),
                ("NWS_SNOW_IN", df.snow_in, "in"),
            ]
            for m_name, m_val, m_unit in metrics_to_save:
                if m_val is None:
                    continue
                existing = (
                    session.query(_WeatherForecastVintage)
                    .filter(
                        _WeatherForecastVintage.metric == m_name,
                        _WeatherForecastVintage.model == "NWS_NDFD",
                        _WeatherForecastVintage.model_run_time == run_time,
                        _WeatherForecastVintage.valid_time == df.date,
                        _WeatherForecastVintage.location == loc.name,
                    )
                    .first()
                )
                if existing is not None:
                    if abs(existing.value - float(m_val)) > 1e-5:
                        existing.value = float(m_val)
                        existing.retrieved_at = ret_ts
                        count += 1
                else:
                    session.add(
                        _WeatherForecastVintage(
                            metric=m_name,
                            product=f"NWS 7-Day Grid Forecast ({loc.grid_id or 'WFO'})",
                            source="NWS API",
                            model="NWS_NDFD",
                            model_run_time=run_time,
                            retrieved_at=ret_ts,
                            valid_time=df.date,
                            lead_days=lead_d,
                            lead_hours=lead_d * 24,
                            location=loc.name,
                            value=float(m_val),
                            units=m_unit,
                        )
                    )
                    count += 1
        session.commit()
    return count


def persist_weather_patterns_bundle(
    bundle: WeatherPatternsDataBundle,
    db_path: Optional[Path] = None,
    allow_stale_forecast_vintages: bool = False,
) -> Dict[str, int]:
    """Persist all observations and non-stale forecast vintages from a normalized bundle.

    Failure / Staleness Safeguard:
    - If a forecast source failed today and fell back to stale cache (`is_stale=True`),
      or is marked unavailable (`available=False`), we do NOT manufacture a new forecast
      vintage unless ``allow_stale_forecast_vintages`` is explicitly True.
    """
    counts: Dict[str, int] = {
        "teleconnection_obs": 0,
        "teleconnection_forecasts": 0,
        "stratosphere_obs": 0,
        "stratosphere_forecasts": 0,
        "mjo_obs": 0,
        "enso_obs": 0,
        "local_obs": 0,
        "local_forecasts": 0,
    }
    engine = init_weather_patterns_db(db_path)
    _ = engine  # ensure initialized

    # 1. Teleconnections
    for code, tb in (bundle.teleconnections or {}).items():
        obs_prov = tb.obs_provenance
        if tb.observations and (obs_prov is None or obs_prov.available):
            counts["teleconnection_obs"] += save_teleconnection_observations(
                index_name=code,
                observations=tb.observations,
                level_label=tb.level_label,
                retrieved_at=obs_prov.retrieved_at if obs_prov else None,
                db_path=db_path,
            )
        fcst_prov = tb.fcst_provenance
        is_fresh_fcst = (
            (tb.forecasts or tb.recent_vintages)
            and (fcst_prov is None or (fcst_prov.available and (not fcst_prov.is_stale or allow_stale_forecast_vintages)))
        )
        if is_fresh_fcst:
            vintages_to_save = tb.recent_vintages if tb.recent_vintages else tb.forecasts
            counts["teleconnection_forecasts"] += save_teleconnection_forecast_vintage(
                index_name=code,
                forecasts=vintages_to_save,
                retrieved_at=fcst_prov.retrieved_at if fcst_prov else None,
                db_path=db_path,
            )

    # 2. Stratosphere
    if bundle.stratosphere:
        st_prov = bundle.stratosphere.provenance
        if bundle.stratosphere.observations and (st_prov is None or st_prov.available):
            counts["stratosphere_obs"] += save_stratosphere_observations(
                observations=bundle.stratosphere.observations,
                level_hpa=bundle.stratosphere.level_hpa,
                latitude_deg=bundle.stratosphere.latitude_deg,
                retrieved_at=st_prov.retrieved_at if st_prov else None,
                db_path=db_path,
            )
        st_fresh = (
            bundle.stratosphere.forecasts
            and (st_prov is None or (st_prov.available and (not st_prov.is_stale or allow_stale_forecast_vintages)))
        )
        if st_fresh:
            counts["stratosphere_forecasts"] += save_stratosphere_forecast_vintage(
                bundle=bundle.stratosphere,
                retrieved_at=st_prov.retrieved_at if st_prov else None,
                db_path=db_path,
            )

    # 3. MJO
    if bundle.mjo and bundle.mjo.history:
        mjo_prov = bundle.mjo.provenance
        if mjo_prov is None or mjo_prov.available:
            counts["mjo_obs"] += save_mjo_observations(
                points=bundle.mjo.history,
                product=bundle.mjo.index_name,
                retrieved_at=mjo_prov.retrieved_at if mjo_prov else None,
                db_path=db_path,
            )

    # 4. ENSO
    if bundle.enso and bundle.enso.nino34_series:
        enso_prov = bundle.enso.provenance
        if enso_prov is None or enso_prov.available:
            counts["enso_obs"] += save_enso_observations(
                bundle=bundle.enso,
                retrieved_at=enso_prov.retrieved_at if enso_prov else None,
                db_path=db_path,
            )

    # 5. Local Locations
    for loc in bundle.locations or []:
        counts["local_obs"] += save_local_location_observations(
            loc=loc,
            db_path=db_path,
        )
        nws_prov = loc.nws_provenance
        nws_fresh = (
            loc.daily_forecasts
            and (nws_prov is None or (nws_prov.available and (not nws_prov.is_stale or allow_stale_forecast_vintages)))
        )
        if nws_fresh:
            counts["local_forecasts"] += save_nws_local_forecast_vintage(
                loc=loc,
                report_date=bundle.report_date,
                retrieved_at=nws_prov.retrieved_at if nws_prov else None,
                db_path=db_path,
            )

    return counts


# ---------------------------------------------------------------------------
# Query Functions: Historical Observations & Forecast Vintages
# ---------------------------------------------------------------------------

def get_teleconnection_obs_history(
    index_name: str,
    limit_days: int = 90,
    up_to_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[TeleconnectionDailyObs]:
    """Query stored teleconnection observations from the local database."""
    engine = init_weather_patterns_db(db_path)
    idx_key = index_name.upper().strip()
    with Session(engine) as session:
        q = session.query(_TeleconnectionObservation).filter(
            _TeleconnectionObservation.index_name == idx_key
        )
        if up_to_date:
            q = q.filter(_TeleconnectionObservation.obs_date <= up_to_date[:10])
        rows = q.order_by(_TeleconnectionObservation.obs_date.desc()).limit(limit_days).all()
        rows.reverse()
        return [TeleconnectionDailyObs(date=r.obs_date, value=float(r.value)) for r in rows]


def get_stratosphere_obs_history(
    limit_days: int = 90,
    up_to_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[StratosphereDailyPoint]:
    """Query stored 10-hPa 60°N stratosphere observations from the local database."""
    engine = init_weather_patterns_db(db_path)
    with Session(engine) as session:
        q = session.query(_StratosphereObservation)
        if up_to_date:
            q = q.filter(_StratosphereObservation.obs_date <= up_to_date[:10])
        rows = q.order_by(_StratosphereObservation.obs_date.desc()).limit(limit_days).all()
        rows.reverse()
        return [
            StratosphereDailyPoint(
                date=r.obs_date,
                zonal_wind_10hpa_60n=float(r.zonal_wind_ms),
                polar_cap_temp_10hpa_60_90n=(
                    float(r.polar_cap_temp_k) if r.polar_cap_temp_k is not None else None
                ),
                is_forecast=False,
            )
            for r in rows
        ]


def get_local_pressure_history(
    location_name: str,
    station_id: Optional[str] = None,
    limit_hours: int = 240,
    up_to_timestamp: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[HourlyPressurePoint]:
    """Query stored local station hourly pressure series (extends beyond 7d NWS retention)."""
    engine = init_weather_patterns_db(db_path)
    with Session(engine) as session:
        q = session.query(_LocalPressureObservation).filter(
            _LocalPressureObservation.location_name == location_name
        )
        if station_id:
            q = q.filter(_LocalPressureObservation.station_id == station_id)
        if up_to_timestamp:
            q = q.filter(_LocalPressureObservation.obs_timestamp <= up_to_timestamp)
        rows = q.order_by(_LocalPressureObservation.obs_timestamp.desc()).limit(limit_hours).all()
        rows.reverse()
        return [
            HourlyPressurePoint(timestamp=r.obs_timestamp, pressure_hpa=float(r.pressure_hpa))
            for r in rows
        ]


def get_forecast_vintages_for_metric(
    metric: str,
    model: Optional[str] = None,
    location: str = "GLOBAL",
    up_to_run_time: Optional[str] = None,
    max_runs: int = 10,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return the most recent ``max_runs`` forecast vintages for ``metric``.

    Returns a list of dicts ordered chronologically by ``model_run_time`` ascending
    (oldest of the recent runs first, latest run last):
        [
            {
                "model_run_time": "2026-11-01T00:00Z",
                "run_date": "2026-11-01",
                "model": "GEFS",
                "retrieved_at": "...",
                "points": [
                    {
                        "valid_time": "2026-11-08",
                        "lead_days": 7,
                        "value": -1.2,
                        "ensemble_mean": -1.2,
                        "ensemble_p25": -1.6,
                        "ensemble_p75": -0.8,
                        "ensemble_std": 0.45,
                        "ensemble_min": -2.1,
                        "ensemble_max": -0.2,
                        "member_count": 31,
                        "members": [...],
                        "deterministic_value": ...,
                    },
                    ...
                ]
            },
            ...
        ]
    """
    engine = init_weather_patterns_db(db_path)
    m_key = metric.upper().strip()

    with Session(engine) as session:
        q = session.query(_WeatherForecastVintage).filter(
            _WeatherForecastVintage.metric == m_key,
            _WeatherForecastVintage.location == location,
        )
        if model:
            q = q.filter(_WeatherForecastVintage.model == model)
        if up_to_run_time:
            norm_cutoff = _normalize_run_time(up_to_run_time)
            q = q.filter(_WeatherForecastVintage.model_run_time <= norm_cutoff)

        all_rows = q.order_by(
            _WeatherForecastVintage.model_run_time.asc(),
            _WeatherForecastVintage.valid_time.asc(),
        ).all()

    if not all_rows:
        return []

    by_run: Dict[str, List[_WeatherForecastVintage]] = {}
    for r in all_rows:
        by_run.setdefault(r.model_run_time, []).append(r)

    run_keys = sorted(by_run.keys())
    if max_runs > 0 and len(run_keys) > max_runs:
        run_keys = run_keys[-max_runs:]

    vintages: List[Dict[str, Any]] = []
    for rk in run_keys:
        pts_rows = by_run[rk]
        pts_list: List[Dict[str, Any]] = []
        for r in pts_rows:
            members: List[float] = []
            if r.members_json:
                try:
                    members = [float(x) for x in json.loads(r.members_json)]
                except Exception:
                    members = []
            pts_list.append(
                {
                    "valid_time": r.valid_time,
                    "lead_days": r.lead_days,
                    "lead_hours": r.lead_hours,
                    "value": float(r.value),
                    "ensemble_mean": float(r.ensemble_mean) if r.ensemble_mean is not None else float(r.value),
                    "ensemble_min": float(r.ensemble_min) if r.ensemble_min is not None else None,
                    "ensemble_max": float(r.ensemble_max) if r.ensemble_max is not None else None,
                    "ensemble_p25": float(r.ensemble_p25) if r.ensemble_p25 is not None else None,
                    "ensemble_p75": float(r.ensemble_p75) if r.ensemble_p75 is not None else None,
                    "ensemble_std": float(r.ensemble_std) if r.ensemble_std is not None else None,
                    "member_count": int(r.member_count) if r.member_count is not None else None,
                    "members": members,
                    "deterministic_value": (
                        float(r.deterministic_value) if r.deterministic_value is not None else None
                    ),
                }
            )
        vintages.append(
            {
                "model_run_time": rk,
                "run_date": rk[:10],
                "model": pts_rows[0].model,
                "product": pts_rows[0].product,
                "source": pts_rows[0].source,
                "retrieved_at": pts_rows[0].retrieved_at,
                "units": pts_rows[0].units,
                "points": pts_list,
            }
        )
    return vintages


# ---------------------------------------------------------------------------
# Forecast Verification & Skill Groundwork (V2)
# ---------------------------------------------------------------------------

def compute_teleconnection_verification_stats(
    index_name: str,
    lead_days_list: Tuple[int, ...] = (3, 5, 7, 10, 14),
    model: str = "GEFS",
    min_samples_for_skill_claim: int = 10,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compare archived forecast vintages against subsequently observed values by lead day.

    Computes for each lead day in ``lead_days_list``:
      - ``sample_count`` (always stored alongside statistics!)
      - ``mae`` (Mean Absolute Error, SD)
      - ``rmse`` (Root Mean Squared Error, SD)
      - ``bias`` (Mean Forecast minus Observed, SD)
      - ``correlation`` (Pearson r when n >= 3)
      - ``sign_accuracy`` (fraction of pairs where forecast & obs share the same sign)
      - ``threshold_accuracy_1sd`` (fraction of pairs correctly predicting |index| >= 1.0 SD of same sign)
      - ``has_meaningful_sample`` (True only when sample_count >= min_samples_for_skill_claim)
    """
    engine = init_weather_patterns_db(db_path)
    idx_key = index_name.upper().strip()

    with Session(engine) as session:
        obs_rows = (
            session.query(_TeleconnectionObservation)
            .filter(_TeleconnectionObservation.index_name == idx_key)
            .all()
        )
        obs_by_date = {r.obs_date: float(r.value) for r in obs_rows}

        fcst_rows = (
            session.query(_WeatherForecastVintage)
            .filter(
                _WeatherForecastVintage.metric == idx_key,
                _WeatherForecastVintage.model == model,
                _WeatherForecastVintage.location == "GLOBAL",
                _WeatherForecastVintage.lead_days.in_(lead_days_list),
            )
            .all()
        )

    pairs_by_lead: Dict[int, List[Tuple[float, float]]] = {ld: [] for ld in lead_days_list}
    for f in fcst_rows:
        if f.valid_time in obs_by_date and f.lead_days in pairs_by_lead:
            pairs_by_lead[f.lead_days].append((float(f.value), obs_by_date[f.valid_time]))

    by_lead_stats: Dict[str, Dict[str, Any]] = {}
    total_verified_pairs = 0

    for ld in lead_days_list:
        pairs = pairs_by_lead[ld]
        n = len(pairs)
        total_verified_pairs += n
        key = f"D+{ld}"
        if n == 0:
            by_lead_stats[key] = {
                "lead_days": ld,
                "sample_count": 0,
                "has_meaningful_sample": False,
                "mae": None,
                "rmse": None,
                "bias": None,
                "correlation": None,
                "sign_accuracy": None,
            }
            continue

        abs_errs = [abs(fc - ob) for fc, ob in pairs]
        sq_errs = [(fc - ob) ** 2 for fc, ob in pairs]
        diffs = [(fc - ob) for fc, ob in pairs]

        mae = round(sum(abs_errs) / n, 3)
        rmse = round(math.sqrt(sum(sq_errs) / n), 3)
        bias = round(sum(diffs) / n, 3)

        same_sign = sum(1 for fc, ob in pairs if (fc >= 0 and ob >= 0) or (fc < 0 and ob < 0))
        sign_acc = round(same_sign / n, 3)

        corr: Optional[float] = None
        if n >= 3:
            mean_f = sum(fc for fc, _ in pairs) / n
            mean_o = sum(ob for _, ob in pairs) / n
            var_f = sum((fc - mean_f) ** 2 for fc, _ in pairs)
            var_o = sum((ob - mean_o) ** 2 for _, ob in pairs)
            if var_f > 1e-9 and var_o > 1e-9:
                cov = sum((fc - mean_f) * (ob - mean_o) for fc, ob in pairs)
                corr = round(cov / math.sqrt(var_f * var_o), 3)

        by_lead_stats[key] = {
            "lead_days": ld,
            "sample_count": n,
            "has_meaningful_sample": n >= min_samples_for_skill_claim,
            "mae": mae,
            "rmse": rmse,
            "bias": bias,
            "correlation": corr,
            "sign_accuracy": sign_acc,
        }

    # Generate an honest trust summary ONLY if sample sizes are meaningful
    meaningful_leads = [
        st for st in by_lead_stats.values() if st["has_meaningful_sample"]
    ]
    trust_summary: Optional[str] = None
    if meaningful_leads:
        d7 = by_lead_stats.get("D+7")
        d10 = by_lead_stats.get("D+10")
        if d7 and d7["has_meaningful_sample"] and d10 and d10["has_meaningful_sample"]:
            trust_summary = (
                f"{model} {idx_key} local archive ({d7['sample_count']} verified runs): "
                f"D+7 MAE={d7['mae']:.2f} SD (r={d7['correlation'] if d7['correlation'] is not None else 'N/A'}), "
                f"D+10 MAE={d10['mae']:.2f} SD (r={d10['correlation'] if d10['correlation'] is not None else 'N/A'})."
            )
        else:
            best = meaningful_leads[0]
            trust_summary = (
                f"{model} {idx_key} local archive (D+{best['lead_days']} n={best['sample_count']}): "
                f"MAE={best['mae']:.2f} SD."
            )

    return {
        "metric": idx_key,
        "model": model,
        "min_samples_required": min_samples_for_skill_claim,
        "total_verified_pairs": total_verified_pairs,
        "has_sufficient_data_for_display": bool(meaningful_leads),
        "by_lead": by_lead_stats,
        "trust_summary": trust_summary,
    }


# ---------------------------------------------------------------------------
# Analog / Historical-Pattern Query Helper (Foundation for V3)
# ---------------------------------------------------------------------------

def find_historical_teleconnection_analogs(
    ao_target: float,
    nao_target: float,
    pna_target: float,
    max_distance_sd: float = 1.0,
    exclude_recent_days: int = 21,
    reference_date: Optional[str] = None,
    limit: int = 10,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Find historical dates in the local DB where (AO, NAO, PNA) closely matched the target state.

    Computes Euclidean distance in 3D standardized index space:
        d = sqrt((AO - ao_t)^2 + (NAO - nao_t)^2 + (PNA - pna_t)^2)
    """
    engine = init_weather_patterns_db(db_path)
    with Session(engine) as session:
        rows = session.query(_TeleconnectionObservation).all()

    by_date: Dict[str, Dict[str, float]] = {}
    for r in rows:
        by_date.setdefault(r.obs_date, {})[r.index_name] = float(r.value)

    cutoff_str: Optional[str] = None
    if reference_date:
        try:
            from datetime import timedelta
            ref_dt = datetime.strptime(reference_date[:10], "%Y-%m-%d")
            cutoff_str = (ref_dt - timedelta(days=exclude_recent_days)).strftime("%Y-%m-%d")
        except Exception:
            cutoff_str = reference_date[:10]

    matches: List[Dict[str, Any]] = []
    for dt_str, vals in by_date.items():
        if cutoff_str and dt_str > cutoff_str:
            continue
        if "AO" not in vals or "NAO" not in vals or "PNA" not in vals:
            continue
        dist = math.sqrt(
            (vals["AO"] - ao_target) ** 2
            + (vals["NAO"] - nao_target) ** 2
            + (vals["PNA"] - pna_target) ** 2
        )
        if dist <= max_distance_sd:
            matches.append(
                {
                    "date": dt_str,
                    "ao": round(vals["AO"], 2),
                    "nao": round(vals["NAO"], 2),
                    "pna": round(vals["PNA"], 2),
                    "distance_sd": round(dist, 3),
                }
            )

    matches.sort(key=lambda m: (m["distance_sd"], m["date"]))
    return matches[:limit]


# ---------------------------------------------------------------------------
# Pragmatic Historical Backfill & Sync Entry Point (for db_update)
# ---------------------------------------------------------------------------

def sync_weather_patterns_db(
    db_path: Optional[Path] = None,
    backfill_days: int = 540,
) -> int:
    """Sync and pragmatically backfill Weather Patterns observations & current forecast vintages.

    - Teleconnections (AO, NAO, PNA): backfills ~1.5 years (540 days) of CDAS daily observations
      plus all available recent GEFS initialization runs in the CPC 120-day file.
    - ENSO: backfills 5 years (60 months) of Niño 3.4, ONI, RONI, and MEI.v2.
    - MJO: backfills ~1.5 years (540 days) of PSL ROMI.
    - Stratosphere: backfills current & prior NH season 10-hPa 60°N zonal wind & cap temp.
    - Local configured locations: persists current NWS observations/forecasts, ACIS climate, and snow.
    """
    from ..config import load_config
    from ..providers.climate_history_provider import ClimateHistoryProvider
    from ..providers.enso_provider import ENSOProvider
    from ..providers.mjo_provider import MJOProvider
    from ..providers.nws_patterns_provider import NWSWeatherPatternsProvider
    from ..providers.snow_provider import SnowProvider
    from ..providers.stratosphere_provider import StratosphereProvider
    from ..providers.teleconnection_provider import TeleconnectionProvider

    init_weather_patterns_db(db_path)
    total_rows = 0

    try:
        cfg = load_config().weather_patterns
    except Exception:
        from ..config import WeatherPatternsConfig
        cfg = WeatherPatternsConfig()

    # 1. Teleconnections (~1.5 years observation backfill + multi-vintage GEFS ingest)
    tele_prov = TeleconnectionProvider(
        history_days=backfill_days,
        forecast_days=max(14, cfg.forecast_days),
        use_cache=True,
    )
    tele_bundles = tele_prov.get_all_teleconnections()
    for code, tb in tele_bundles.items():
        total_rows += save_teleconnection_observations(
            index_name=code,
            observations=tb.observations,
            level_label=tb.level_label,
            db_path=db_path,
        )
        if (tb.forecasts or tb.recent_vintages) and (tb.fcst_provenance is None or not tb.fcst_provenance.is_stale):
            total_rows += save_teleconnection_forecast_vintage(
                index_name=code,
                forecasts=tb.recent_vintages if tb.recent_vintages else tb.forecasts,
                db_path=db_path,
            )

    # 2. MJO (~1.5 years backfill)
    mjo_prov = MJOProvider(history_days=backfill_days, use_cache=True)
    mjo_bundle = mjo_prov.get_mjo_bundle()
    if mjo_bundle.history:
        total_rows += save_mjo_observations(mjo_bundle.history, db_path=db_path)

    # 3. ENSO (60 months = 5 years backfill)
    enso_prov = ENSOProvider(months_to_keep=60, use_cache=True)
    enso_bundle = enso_prov.get_enso_bundle()
    if enso_bundle.nino34_series:
        total_rows += save_enso_observations(enso_bundle, db_path=db_path)

    # 4. Stratosphere
    strat_prov = StratosphereProvider(
        history_days=min(backfill_days, 365),
        forecast_days=max(10, cfg.forecast_days),
        use_cache=True,
    )
    strat_bundle = strat_prov.get_stratosphere_bundle()
    if strat_bundle.observations:
        total_rows += save_stratosphere_observations(strat_bundle.observations, db_path=db_path)
    if strat_bundle.forecasts and (strat_bundle.provenance is None or not strat_bundle.provenance.is_stale):
        total_rows += save_stratosphere_forecast_vintage(strat_bundle, db_path=db_path)

    # 5. Configured Local Locations
    nws_prov = NWSWeatherPatternsProvider(include_afd=False, use_cache=True)
    clim_prov = ClimateHistoryProvider(history_days=90, use_cache=True)
    snow_prov = SnowProvider(history_days=90, use_cache=True)
    for loc_cfg in cfg.locations:
        try:
            loc_bundle = nws_prov.get_location_nws_bundle(
                name=loc_cfg.name,
                lat=loc_cfg.lat,
                lon=loc_cfg.lon,
                station_override=loc_cfg.station,
            )
            clim_prov.enrich_location_climate(loc_bundle)
            snow_prov.enrich_location_snow(loc_bundle, explicit_snow_station=loc_cfg.snow_station)
            total_rows += save_local_location_observations(loc_bundle, db_path=db_path)
            if loc_bundle.daily_forecasts and (
                loc_bundle.nws_provenance is None or not loc_bundle.nws_provenance.is_stale
            ):
                total_rows += save_nws_local_forecast_vintage(
                    loc_bundle,
                    report_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    db_path=db_path,
                )
        except Exception as exc:
            logger.warning("Local weather DB sync failed for %s: %s", loc_cfg.name, exc)

    return total_rows


def purge_expired_weather_raw_cache(db_path: Optional[Path] = None) -> int:
    """Purge expired raw API payload cache entries past their stale_until TTL.

    Note: Normalized observations and forecast vintages in ``weather_forecasts``
    and ``weather_*_observations`` are institutional memory and are NEVER purged here.
    """
    from .weather_cache_db import _WeatherDataCache, _get_engine as _get_cache_engine

    engine = _get_cache_engine(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        res = session.execute(
            text("DELETE FROM weather_data_cache WHERE stale_until < :now"),
            {"now": now_iso},
        )
        session.commit()
        return int(res.rowcount or 0)

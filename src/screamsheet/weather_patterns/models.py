"""Normalized domain models for the Weather Patterns / Teleconnections screamsheet.

Every data source records full provenance:
  - source name and URL/product
  - retrieval timestamp
  - valid / observation date or period
  - forecast initialization timestamp (where applicable)
  - cache / staleness metadata
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceProvenance:
    """Provenance and freshness metadata for a single data product."""
    source_name: str
    product: str
    url: str
    retrieved_at: str
    valid_through: Optional[str] = None
    forecast_init: Optional[str] = None
    from_cache: bool = False
    is_stale: bool = False
    age_hours: float = 0.0
    available: bool = True
    error: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class TeleconnectionDailyObs:
    """Single day of observed CDAS teleconnection index."""
    date: str          # YYYY-MM-DD
    value: float       # standardized index (SD units)


@dataclass
class TeleconnectionForecastDay:
    """Single valid date of GEFS ensemble teleconnection forecast."""
    valid_date: str               # YYYY-MM-DD
    lead_days: int
    init_date: str                # YYYY-MM-DD (00Z initialization)
    ensemble_mean: float
    ensemble_min: float
    ensemble_max: float
    ensemble_p25: float
    ensemble_p75: float
    ensemble_std: float
    member_count: int
    members: List[float] = field(default_factory=list)
    deterministic_gfs: Optional[float] = None


@dataclass
class TeleconnectionIndexBundle:
    """Complete history + GEFS forecast for one teleconnection index (AO, NAO, or PNA)."""
    index_name: str                                    # "AO" | "NAO" | "PNA"
    level_label: str                                   # e.g. "1000 hPa" | "500 hPa"
    observations: List[TeleconnectionDailyObs] = field(default_factory=list)
    forecasts: List[TeleconnectionForecastDay] = field(default_factory=list)
    obs_provenance: Optional[SourceProvenance] = None
    fcst_provenance: Optional[SourceProvenance] = None


@dataclass
class MJODailyPoint:
    """Single daily point for the MJO (NOAA PSL ROMI)."""
    date: str          # YYYY-MM-DD
    component_1: float # RMM1-equivalent (PC2(ROMI))
    component_2: float # RMM2-equivalent (-PC1(ROMI))
    raw_pc1: float
    raw_pc2: float
    amplitude: float
    phase: int         # 1..8
    active: bool       # amplitude >= 1.0


@dataclass
class MJOBundle:
    """Complete MJO time series and provenance."""
    index_name: str = "ROMI (CPC OLR)"
    amplitude_threshold: float = 1.0
    history: List[MJODailyPoint] = field(default_factory=list)
    provenance: Optional[SourceProvenance] = None


@dataclass
class ENSOMonthlyPoint:
    """Monthly or 3-month seasonal ENSO observation."""
    period: str                 # e.g. "2026-10" or "ASO 2026"
    nino34_anomaly: float       # °C anomaly
    nino34_total: Optional[float] = None
    oni_anomaly: Optional[float] = None
    roni_anomaly: Optional[float] = None
    meiv2: Optional[float] = None


@dataclass
class ENSOBundle:
    """Complete ENSO background state and provenance."""
    nino34_series: List[ENSOMonthlyPoint] = field(default_factory=list)
    latest_period: Optional[str] = None
    latest_nino34: Optional[float] = None
    latest_oni: Optional[float] = None
    latest_oni_season: Optional[str] = None
    latest_roni: Optional[float] = None
    latest_roni_season: Optional[str] = None
    latest_meiv2: Optional[float] = None
    latest_meiv2_season: Optional[str] = None
    enso_state_label: str = "Unavailable"
    provenance: Optional[SourceProvenance] = None


@dataclass
class StratosphereDailyPoint:
    """Daily 10-hPa 60°N zonal wind and 60-90°N polar cap temperature."""
    date: str                         # YYYY-MM-DD
    zonal_wind_10hpa_60n: float       # m/s (positive = westerly, negative = easterly)
    polar_cap_temp_10hpa_60_90n: Optional[float] = None  # Kelvin
    is_forecast: bool = False


@dataclass
class StratosphereBundle:
    """Stratospheric polar vortex diagnostic series and provenance."""
    level_hpa: int = 10
    latitude_deg: int = 60
    observations: List[StratosphereDailyPoint] = field(default_factory=list)
    forecasts: List[StratosphereDailyPoint] = field(default_factory=list)
    provenance: Optional[SourceProvenance] = None


@dataclass
class HourlyPressurePoint:
    """Single barometric/sea-level pressure observation at a local station."""
    timestamp: str      # ISO-8601
    pressure_hpa: float


@dataclass
class DailyForecastSummary:
    """Single day of local NWS forecast."""
    date: str                             # YYYY-MM-DD
    day_name: str
    high_f: Optional[float] = None
    low_f: Optional[float] = None
    pop_pct: Optional[int] = None
    qpf_in: Optional[float] = None
    snow_in: Optional[float] = None
    short_forecast: str = ""
    wind_summary: str = ""


@dataclass
class DailyClimatePoint:
    """Single day of historical local station observations & 1991-2020 normals."""
    date: str                             # YYYY-MM-DD
    max_temp_f: Optional[float] = None
    min_temp_f: Optional[float] = None
    avg_temp_f: Optional[float] = None
    normal_temp_f: Optional[float] = None
    temp_departure_f: Optional[float] = None
    precip_in: Optional[float] = None
    normal_precip_in: Optional[float] = None


@dataclass
class SnowDailyPoint:
    """Single day of snow observation at a snow-capable station."""
    date: str                             # YYYY-MM-DD
    snow_depth_in: Optional[float] = None
    snowfall_in: Optional[float] = None
    swe_in: Optional[float] = None
    max_temp_f: Optional[float] = None
    min_temp_f: Optional[float] = None


@dataclass
class SnowLocationBundle:
    """Snowpack & recent snowfall observations for a location (omitted if no useful snow data)."""
    station_id: str
    station_name: str
    elevation_ft: Optional[float] = None
    current_depth_in: Optional[float] = None
    change_7d_in: Optional[float] = None
    snowfall_24h_in: Optional[float] = None
    snowfall_7d_in: Optional[float] = None
    forecast_snow_7d_in: Optional[float] = None
    daily_series: List[SnowDailyPoint] = field(default_factory=list)
    has_useful_snow_data: bool = False
    provenance: Optional[SourceProvenance] = None


@dataclass
class LocalLocationBundle:
    """Combined NWS observations, forecast, AFD, climate anomalies, and snow for one location."""
    name: str
    lat: float
    lon: float
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    grid_id: Optional[str] = None
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    # Latest NWS station observation
    obs_timestamp: Optional[str] = None
    current_temp_f: Optional[float] = None
    current_dewpoint_f: Optional[float] = None
    current_pressure_hpa: Optional[float] = None
    current_wind_mph: Optional[float] = None
    current_wind_dir_deg: Optional[int] = None
    current_conditions: Optional[str] = None
    # Recent pressure series (~7 days from NWS API)
    pressure_series: List[HourlyPressurePoint] = field(default_factory=list)
    pressure_min_7d_hpa: Optional[float] = None
    pressure_max_7d_hpa: Optional[float] = None
    pressure_mean_7d_hpa: Optional[float] = None
    pressure_change_24h_hpa: Optional[float] = None
    # 7-day NWS forecast
    daily_forecasts: List[DailyForecastSummary] = field(default_factory=list)
    # Historical climate series & anomalies (via NOAA RCC-ACIS 1991-2020 normals)
    climate_station_name: Optional[str] = None
    climate_series: List[DailyClimatePoint] = field(default_factory=list)
    temp_anomaly_7d_f: Optional[float] = None
    temp_anomaly_14d_f: Optional[float] = None
    precip_30d_in: Optional[float] = None
    precip_30d_normal_in: Optional[float] = None
    precip_30d_pct_normal: Optional[float] = None
    # Optional snow observations
    snow: Optional[SnowLocationBundle] = None
    # Optional NWS Area Forecast Discussion
    afd_office: Optional[str] = None
    afd_issued_at: Optional[str] = None
    afd_synopsis: Optional[str] = None
    # Provenance
    nws_provenance: Optional[SourceProvenance] = None
    climate_provenance: Optional[SourceProvenance] = None


@dataclass
class DerivedSignals:
    """Deterministic derived signal-change metrics and rule-based flags."""
    # Quantitative changes
    ao: Dict[str, Any] = field(default_factory=dict)
    nao: Dict[str, Any] = field(default_factory=dict)
    pna: Dict[str, Any] = field(default_factory=dict)
    polar_vortex: Dict[str, Any] = field(default_factory=dict)
    mjo: Dict[str, Any] = field(default_factory=dict)
    enso: Dict[str, Any] = field(default_factory=dict)
    # Rule-based boolean flags
    flags: Dict[str, bool] = field(default_factory=dict)
    # Human-readable summary bullets of triggered flags / notable changes
    notable_changes: List[str] = field(default_factory=list)


@dataclass
class WeatherPatternsDataBundle:
    """Top-level normalized bundle passed to renderers and the LLM narrative generator."""
    report_date: str                                     # YYYY-MM-DD
    teleconnections: Dict[str, TeleconnectionIndexBundle] = field(default_factory=dict)
    stratosphere: Optional[StratosphereBundle] = None
    mjo: Optional[MJOBundle] = None
    enso: Optional[ENSOBundle] = None
    locations: List[LocalLocationBundle] = field(default_factory=list)
    derived: DerivedSignals = field(default_factory=DerivedSignals)
    narrative_text: str = ""
    provenance_list: List[SourceProvenance] = field(default_factory=list)

    def to_llm_packet(self, include_afd: bool = True) -> Dict[str, Any]:
        """Construct the compact, strictly separated structured packet for the LLM.

        Sections:
          - OBSERVATIONS
          - MODEL_FORECASTS
          - DERIVED_CHANGES
          - LOCAL_WEATHER
          - OFFICIAL_FORECASTER_DISCUSSION (optional)
          - SOURCE_TIMESTAMPS
        """
        observations: Dict[str, Any] = {}
        model_forecasts: Dict[str, Any] = {}

        # Teleconnections
        tc_obs: Dict[str, Any] = {}
        tc_fcst: Dict[str, Any] = {}
        for key, bundle in self.teleconnections.items():
            if bundle.observations:
                latest = bundle.observations[-1]
                recent_7 = bundle.observations[-8:]
                tc_obs[key] = {
                    "latest_date": latest.date,
                    "latest_value_sd": round(latest.value, 2),
                    "recent_values": [
                        {"date": pt.date, "value_sd": round(pt.value, 2)}
                        for pt in recent_7
                    ],
                }
            if bundle.forecasts:
                day7 = next((f for f in bundle.forecasts if f.lead_days == 7), bundle.forecasts[min(6, len(bundle.forecasts) - 1)])
                day14 = next((f for f in bundle.forecasts if f.lead_days == 14), bundle.forecasts[-1])
                tc_fcst[key] = {
                    "init_date": bundle.forecasts[0].init_date,
                    "day7_valid": day7.valid_date,
                    "day7_gefs_mean_sd": round(day7.ensemble_mean, 2),
                    "day7_gefs_iqr_sd": [round(day7.ensemble_p25, 2), round(day7.ensemble_p75, 2)],
                    "day14_valid": day14.valid_date,
                    "day14_gefs_mean_sd": round(day14.ensemble_mean, 2),
                    "day14_gefs_iqr_sd": [round(day14.ensemble_p25, 2), round(day14.ensemble_p75, 2)],
                }
        observations["teleconnections"] = tc_obs
        model_forecasts["teleconnections_gefs"] = tc_fcst

        # Stratosphere
        if self.stratosphere and self.stratosphere.observations:
            latest_s = self.stratosphere.observations[-1]
            observations["stratospheric_polar_vortex"] = {
                "diagnostic": "10 hPa 60N zonal-mean zonal wind (m/s) and 60-90N polar cap temperature (K)",
                "latest_date": latest_s.date,
                "zonal_wind_10hpa_60n_ms": round(latest_s.zonal_wind_10hpa_60n, 2),
                "polar_cap_temp_10hpa_60_90n_k": (
                    round(latest_s.polar_cap_temp_10hpa_60_90n, 2)
                    if latest_s.polar_cap_temp_10hpa_60_90n is not None
                    else None
                ),
            }
            if self.stratosphere.forecasts:
                model_forecasts["stratospheric_polar_vortex_geos_fp"] = [
                    {
                        "valid_date": pt.date,
                        "zonal_wind_10hpa_60n_ms": round(pt.zonal_wind_10hpa_60n, 2),
                        "polar_cap_temp_10hpa_60_90n_k": (
                            round(pt.polar_cap_temp_10hpa_60_90n, 2)
                            if pt.polar_cap_temp_10hpa_60_90n is not None
                            else None
                        ),
                    }
                    for pt in self.stratosphere.forecasts
                ]

        # MJO
        if self.mjo and self.mjo.history:
            latest_m = self.mjo.history[-1]
            observations["mjo"] = {
                "index": self.mjo.index_name,
                "latest_date": latest_m.date,
                "phase": latest_m.phase,
                "amplitude": round(latest_m.amplitude, 2),
                "active": latest_m.active,
                "component_1": round(latest_m.component_1, 2),
                "component_2": round(latest_m.component_2, 2),
            }

        # ENSO
        if self.enso and self.enso.latest_nino34 is not None:
            observations["enso"] = {
                "latest_period": self.enso.latest_period,
                "nino34_anomaly_c": round(self.enso.latest_nino34, 2),
                "oni_anomaly_c": round(self.enso.latest_oni, 2) if self.enso.latest_oni is not None else None,
                "oni_season": self.enso.latest_oni_season,
                "roni_anomaly_c": round(self.enso.latest_roni, 2) if self.enso.latest_roni is not None else None,
                "meiv2": round(self.enso.latest_meiv2, 2) if self.enso.latest_meiv2 is not None else None,
                "state_summary": self.enso.enso_state_label,
            }

        # Local weather
        local_weather: List[Dict[str, Any]] = []
        forecaster_discussions: List[Dict[str, Any]] = []
        for loc in self.locations:
            loc_dict: Dict[str, Any] = {
                "location": loc.name,
                "station": loc.station_id,
                "current_obs": {
                    "timestamp": loc.obs_timestamp,
                    "temp_f": loc.current_temp_f,
                    "dewpoint_f": loc.current_dewpoint_f,
                    "pressure_hpa": loc.current_pressure_hpa,
                    "wind_mph": loc.current_wind_mph,
                    "conditions": loc.current_conditions,
                },
                "recent_anomalies_and_trends": {
                    "temp_anomaly_7d_f": loc.temp_anomaly_7d_f,
                    "temp_anomaly_14d_f": loc.temp_anomaly_14d_f,
                    "precip_30d_in": loc.precip_30d_in,
                    "precip_30d_normal_in": loc.precip_30d_normal_in,
                    "precip_30d_pct_normal": loc.precip_30d_pct_normal,
                    "pressure_7d_min_hpa": loc.pressure_min_7d_hpa,
                    "pressure_7d_max_hpa": loc.pressure_max_7d_hpa,
                    "pressure_24h_change_hpa": loc.pressure_change_24h_hpa,
                },
                "nws_7day_forecast": [
                    {
                        "date": d.date,
                        "day": d.day_name,
                        "high_f": d.high_f,
                        "low_f": d.low_f,
                        "pop_pct": d.pop_pct,
                        "snow_in": d.snow_in,
                        "forecast": d.short_forecast,
                    }
                    for d in loc.daily_forecasts[:7]
                ],
            }
            if loc.snow and loc.snow.has_useful_snow_data:
                loc_dict["snow_observations"] = {
                    "station": loc.snow.station_name,
                    "elevation_ft": loc.snow.elevation_ft,
                    "current_snow_depth_in": loc.snow.current_depth_in,
                    "depth_change_7d_in": loc.snow.change_7d_in,
                    "snowfall_7d_in": loc.snow.snowfall_7d_in,
                    "nws_forecast_snow_7d_in": loc.snow.forecast_snow_7d_in,
                }
            local_weather.append(loc_dict)

            if include_afd and loc.afd_synopsis:
                forecaster_discussions.append(
                    {
                        "location": loc.name,
                        "nws_office": loc.afd_office,
                        "issued_at": loc.afd_issued_at,
                        "excerpt": loc.afd_synopsis,
                    }
                )

        timestamps = [
            {
                "source": p.source_name,
                "product": p.product,
                "valid_through": p.valid_through,
                "forecast_init": p.forecast_init,
                "retrieved_at": p.retrieved_at,
                "is_stale": p.is_stale,
                "available": p.available,
            }
            for p in self.provenance_list
        ]

        packet: Dict[str, Any] = {
            "REPORT_DATE": self.report_date,
            "OBSERVATIONS": observations,
            "MODEL_FORECASTS": model_forecasts,
            "DERIVED_CHANGES": asdict(self.derived),
            "LOCAL_WEATHER": local_weather,
            "SOURCE_TIMESTAMPS": timestamps,
        }
        if forecaster_discussions:
            packet["OFFICIAL_FORECASTER_DISCUSSION"] = forecaster_discussions
        return packet

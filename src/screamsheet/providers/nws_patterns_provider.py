"""Extended National Weather Service (NWS) Local Observations, Grid Forecast & AFD Provider.

Authoritative Source:
  - National Weather Service API: https://api.weather.gov
  - Endpoints used per configured location:
      1. ``GET /points/{lat},{lon}`` -> resolves ``gridId``, ``gridX``, ``gridY``,
         ``forecast``, ``forecastGridData``, ``observationStations``
      2. ``GET /gridpoints/{wfo}/{x},{y}/stations`` -> discovers nearest observation station
         when no explicit ``station`` is configured
      3. ``GET /stations/{stationId}/observations?limit=500`` -> retrieves ~7 days of hourly
         station observations (temperature, dewpoint, barometric/sea-level pressure, wind, conditions)
      4. ``GET /gridpoints/{wfo}/{x},{y}/forecast`` & ``GET /gridpoints/{wfo}/{x},{y}`` ->
         7-day daily High/Low, Probability of Precipitation (PoP), Quantitative Precipitation (QPF),
         and Snowfall Amount
      5. ``GET /products/types/AFD/locations/{wfo}`` -> latest NWS Area Forecast Discussion
         (extracts KEY MESSAGES / SYNOPSIS / WHAT HAS CHANGED / NEAR TERM)
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import (
    DailyForecastSummary,
    HourlyPressurePoint,
    LocalLocationBundle,
    SourceProvenance,
)

logger = logging.getLogger(__name__)

NWS_BASE_URL = "https://api.weather.gov"
NWS_GEOJSON_HEADERS = {
    "User-Agent": "DailyScreamSheet (peter.j.martinson@gmail.com)",
    "Accept": "application/geo+json",
}


def _c_to_f(val_c: Optional[float]) -> Optional[float]:
    if val_c is None:
        return None
    return round(val_c * 9.0 / 5.0 + 32.0, 1)


def _pa_to_hpa(val_pa: Optional[float]) -> Optional[float]:
    if val_pa is None:
        return None
    return round(val_pa / 100.0, 1)


def _kmh_to_mph(val_kmh: Optional[float]) -> Optional[float]:
    if val_kmh is None:
        return None
    return round(val_kmh * 0.621371, 1)


def _mm_to_inches(val_mm: Optional[float]) -> Optional[float]:
    if val_mm is None:
        return None
    return round(val_mm / 25.4, 2)


class NWSWeatherPatternsProvider(DataProvider):
    """Fetches local NWS station observations, 7-day forecast, raw grid QPF/snow, and AFD."""

    def __init__(
        self,
        include_afd: bool = True,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.include_afd = include_afd
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def extract_afd_synopsis(product_text: str, max_chars: int = 1100) -> str:
        """Extract the most informative synopsis/key-messages section from an NWS AFD."""
        if not product_text:
            return ""
        text = product_text.replace("\r\n", "\n")

        # Look for .KEY MESSAGES..., .SYNOPSIS..., .WHAT HAS CHANGED..., or .NEAR TERM... / .SHORT TERM...
        sections: Dict[str, str] = {}
        for m in re.finditer(
            r"\.([A-Z][A-Z0-9 /&-]{2,30})\.\.\.\s*(.*?)(?=\n\.[A-Z]|\n&&|\Z)",
            text,
            flags=re.DOTALL,
        ):
            sec_name = m.group(1).strip().upper()
            sec_body = re.sub(r"\s+", " ", m.group(2)).strip()
            if sec_body and sec_name not in sections:
                sections[sec_name] = sec_body

        key_msg_sentences: List[str] = []
        parts: List[str] = []
        for priority_key in (
            "SYNOPSIS",
            "KEY MESSAGES",
            "WHAT HAS CHANGED",
            "DISCUSSION",
            "NEAR TERM",
            "SHORT TERM",
        ):
            for k, v in sections.items():
                if priority_key in k and v not in parts:
                    v_low = v.lower()
                    if k == "WHAT HAS CHANGED":
                        if (
                            "no major change" in v_low
                            or "no significant change" in v_low
                            or v_low in ("none.", "none", "n/a")
                            or (len(v) < 60 and "taf" in v_low)
                        ):
                            continue
                    cleaned_v = v
                    if k == "KEY MESSAGES":
                        cleaned_v = re.sub(r"(?:^|\s)-\s*\d+\)\s*", " ", cleaned_v).strip()
                        for s in re.split(r"(?<=[.!?])\s+", cleaned_v):
                            if len(s.strip()) > 15:
                                key_msg_sentences.append(s.strip())
                    elif k == "DISCUSSION":
                        cleaned_v = re.sub(r"KEY MESSAGE\s*\d+\.{2,}\s*", "", cleaned_v, flags=re.IGNORECASE).strip()
                        for km_s in key_msg_sentences:
                            if cleaned_v.lower().startswith(km_s.lower()):
                                cleaned_v = cleaned_v[len(km_s) :].strip()
                    if cleaned_v:
                        parts.append(f"[{k}] {cleaned_v}")
                    break
            if sum(len(p) for p in parts) >= max_chars:
                break

        combined = " ".join(parts).strip()
        if not combined:
            # Fallback: strip header lines and take first paragraph
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            body_lines = [
                ln for ln in lines[5:]
                if not ln.startswith("&&") and not ln.startswith("$$")
            ]
            combined = " ".join(body_lines)

        if len(combined) > max_chars:
            cut = combined[:max_chars]
            if "." in cut:
                combined = cut[: cut.rfind(".") + 1]
            else:
                combined = cut.rsplit(" ", 1)[0] + "..."
        return combined

    @staticmethod
    def parse_observations_features(
        features: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[HourlyPressurePoint]]:
        """Parse NWS GeoJSON station observation features into latest obs + pressure series."""
        latest_info: Dict[str, Any] = {}
        pressure_pts: List[HourlyPressurePoint] = []

        for idx, feat in enumerate(features):
            props = feat.get("properties") or {}
            ts = props.get("timestamp")
            if not ts:
                continue

            slp = (props.get("seaLevelPressure") or {}).get("value")
            baro = (props.get("barometricPressure") or {}).get("value")
            p_pa = slp if slp is not None else baro
            p_hpa = _pa_to_hpa(p_pa)
            if p_hpa is not None and 900.0 <= p_hpa <= 1080.0:
                pressure_pts.append(HourlyPressurePoint(timestamp=str(ts), pressure_hpa=p_hpa))

            if not latest_info:
                temp_c = (props.get("temperature") or {}).get("value")
                dew_c = (props.get("dewpoint") or {}).get("value")
                w_spd = (props.get("windSpeed") or {}).get("value")
                w_unit = (props.get("windSpeed") or {}).get("unitCode", "")
                if w_spd is not None and "m_s-1" in w_unit:
                    wind_mph = round(float(w_spd) * 2.23694, 1)
                else:
                    wind_mph = _kmh_to_mph(w_spd)
                w_dir = (props.get("windDirection") or {}).get("value")
                latest_info = {
                    "timestamp": str(ts),
                    "temp_f": _c_to_f(temp_c),
                    "dewpoint_f": _c_to_f(dew_c),
                    "pressure_hpa": p_hpa,
                    "wind_mph": wind_mph,
                    "wind_dir_deg": int(w_dir) if w_dir is not None else None,
                    "conditions": str(props.get("textDescription") or "").strip() or None,
                }

        pressure_pts.sort(key=lambda p: p.timestamp)
        return latest_info, pressure_pts

    @staticmethod
    def parse_forecast_and_grid(
        periods: List[Dict[str, Any]],
        grid_props: Optional[Dict[str, Any]] = None,
    ) -> List[DailyForecastSummary]:
        """Combine NWS 7-day prose periods with raw gridpoint QPF and snowfall totals by date."""
        daily_qpf_in: Dict[str, float] = defaultdict(float)
        daily_snow_in: Dict[str, float] = defaultdict(float)

        if grid_props:
            qpf_vals = (grid_props.get("quantitativePrecipitation") or {}).get("values") or []
            for item in qpf_vals:
                vt = str(item.get("validTime") or "")
                val = item.get("value")
                if val is not None and len(vt) >= 10:
                    d_str = vt[:10]
                    in_val = _mm_to_inches(float(val))
                    if in_val is not None:
                        daily_qpf_in[d_str] = round(daily_qpf_in[d_str] + in_val, 2)

            snow_vals = (grid_props.get("snowfallAmount") or {}).get("values") or []
            for item in snow_vals:
                vt = str(item.get("validTime") or "")
                val = item.get("value")
                if val is not None and len(vt) >= 10:
                    d_str = vt[:10]
                    in_val = _mm_to_inches(float(val))
                    if in_val is not None:
                        daily_snow_in[d_str] = round(daily_snow_in[d_str] + in_val, 2)

        by_date: Dict[str, DailyForecastSummary] = {}
        for p in periods:
            start_time = str(p.get("startTime") or "")
            if len(start_time) < 10:
                continue
            d_str = start_time[:10]
            is_day = bool(p.get("isDaytime", True))
            temp = p.get("temperature")
            pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
            short_fcst = str(p.get("shortForecast") or "").strip()
            wind_str = f"{p.get('windDirection', '')} {p.get('windSpeed', '')}".strip()

            if d_str not in by_date:
                try:
                    dt_obj = datetime.strptime(d_str, "%Y-%m-%d")
                    day_label = dt_obj.strftime("%a")
                except ValueError:
                    day_label = str(p.get("name") or d_str)[:3]
                by_date[d_str] = DailyForecastSummary(
                    date=d_str,
                    day_name=day_label,
                    qpf_in=daily_qpf_in.get(d_str),
                    snow_in=daily_snow_in.get(d_str),
                )

            entry = by_date[d_str]
            if is_day:
                if temp is not None:
                    entry.high_f = float(temp)
                if short_fcst:
                    entry.short_forecast = short_fcst
                if wind_str:
                    entry.wind_summary = wind_str
            else:
                if temp is not None:
                    entry.low_f = float(temp)
                if not entry.short_forecast and short_fcst:
                    entry.short_forecast = short_fcst

            if pop is not None:
                entry.pop_pct = max(entry.pop_pct or 0, int(pop))

        out = [by_date[k] for k in sorted(by_date.keys())]
        return out[:7]

    def get_location_nws_bundle(
        self,
        name: str,
        lat: float,
        lon: float,
        station_override: Optional[str] = None,
        target_date: Optional[datetime] = None,
    ) -> LocalLocationBundle:
        """Fetch NWS observations, 7-day forecast, raw grid forecast, and AFD for one location."""
        points_url = f"{NWS_BASE_URL}/points/{lat:.4f},{lon:.4f}"
        safe_slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        today_str = (target_date or datetime.now()).strftime("%Y-%m-%d")

        def _fetch_all() -> Dict[str, Any]:
            r_pt = requests.get(points_url, headers=NWS_GEOJSON_HEADERS, timeout=15)
            r_pt.raise_for_status()
            pt_props = r_pt.json().get("properties") or {}

            grid_id = pt_props.get("gridId")
            grid_x = pt_props.get("gridX")
            grid_y = pt_props.get("gridY")
            forecast_url = pt_props.get("forecast")
            grid_data_url = pt_props.get("forecastGridData")
            stations_url = pt_props.get("observationStations")

            station_id = station_override
            station_name = station_override
            if not station_id and stations_url:
                try:
                    r_st = requests.get(stations_url, headers=NWS_GEOJSON_HEADERS, timeout=15)
                    if r_st.ok:
                        feats = r_st.json().get("features") or []
                        if feats:
                            s_props = feats[0].get("properties") or {}
                            station_id = s_props.get("stationIdentifier")
                            station_name = s_props.get("name") or station_id
                except Exception as exc:
                    logger.debug("Station discovery failed for %s: %s", name, exc)

            obs_features: List[Dict[str, Any]] = []
            if station_id:
                try:
                    obs_url = f"{NWS_BASE_URL}/stations/{station_id}/observations?limit=500"
                    r_obs = requests.get(obs_url, headers=NWS_GEOJSON_HEADERS, timeout=20)
                    if r_obs.ok:
                        obs_features = r_obs.json().get("features") or []
                except Exception as exc:
                    logger.warning("Observations fetch failed for %s (%s): %s", name, station_id, exc)

            latest_obs, pressure_pts = self.parse_observations_features(obs_features)
            # Thin hourly pressure series to ~1 point every 2 hours so cache JSON stays compact
            if len(pressure_pts) > 120:
                step = max(1, len(pressure_pts) // 100)
                thinned = pressure_pts[::step]
                if pressure_pts[-1] not in thinned:
                    thinned.append(pressure_pts[-1])
                pressure_pts = thinned

            periods: List[Dict[str, Any]] = []
            if forecast_url:
                try:
                    r_fc = requests.get(forecast_url, headers=NWS_GEOJSON_HEADERS, timeout=15)
                    if r_fc.ok:
                        periods = (r_fc.json().get("properties") or {}).get("periods") or []
                except Exception as exc:
                    logger.warning("Forecast fetch failed for %s: %s", name, exc)

            grid_props: Optional[Dict[str, Any]] = None
            if grid_data_url:
                try:
                    r_gd = requests.get(grid_data_url, headers=NWS_GEOJSON_HEADERS, timeout=15)
                    if r_gd.ok:
                        grid_props = r_gd.json().get("properties") or {}
                except Exception as exc:
                    logger.debug("Gridpoint raw forecast fetch failed for %s: %s", name, exc)

            daily_fcsts = self.parse_forecast_and_grid(periods, grid_props)

            afd_issued: Optional[str] = None
            afd_synopsis: Optional[str] = None
            if self.include_afd and grid_id:
                try:
                    afd_list_url = f"{NWS_BASE_URL}/products/types/AFD/locations/{grid_id}"
                    r_al = requests.get(afd_list_url, headers=NWS_GEOJSON_HEADERS, timeout=15)
                    if r_al.ok:
                        graph = r_al.json().get("@graph") or []
                        if graph:
                            afd_id = graph[0].get("id")
                            if afd_id:
                                r_afd = requests.get(
                                    f"{NWS_BASE_URL}/products/{afd_id}",
                                    headers=NWS_GEOJSON_HEADERS,
                                    timeout=15,
                                )
                                if r_afd.ok:
                                    afd_js = r_afd.json()
                                    afd_issued = afd_js.get("issuanceTime")
                                    afd_synopsis = self.extract_afd_synopsis(
                                        str(afd_js.get("productText") or "")
                                    )
                except Exception as exc:
                    logger.debug("AFD fetch failed for %s (%s): %s", name, grid_id, exc)

            return {
                "grid_id": grid_id,
                "grid_x": grid_x,
                "grid_y": grid_y,
                "station_id": station_id,
                "station_name": station_name,
                "latest_obs": latest_obs,
                "pressure_series": [
                    {"timestamp": p.timestamp, "pressure_hpa": p.pressure_hpa}
                    for p in pressure_pts
                ],
                "daily_forecasts": [
                    {
                        "date": d.date,
                        "day_name": d.day_name,
                        "high_f": d.high_f,
                        "low_f": d.low_f,
                        "pop_pct": d.pop_pct,
                        "qpf_in": d.qpf_in,
                        "snow_in": d.snow_in,
                        "short_forecast": d.short_forecast,
                        "wind_summary": d.wind_summary,
                    }
                    for d in daily_fcsts
                ],
                "afd_issued_at": afd_issued,
                "afd_synopsis": afd_synopsis,
            }

        res = weather_cache_fetch(
            cache_key=f"nws_local_{safe_slug}_{today_str}",
            source_url=points_url,
            fetcher=_fetch_all,
            fresh_hours=2.0,
            max_stale_hours=48.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        bundle = LocalLocationBundle(
            name=name,
            lat=lat,
            lon=lon,
            station_id=station_override,
        )

        if res.data:
            d = res.data
            bundle.grid_id = d.get("grid_id")
            bundle.grid_x = d.get("grid_x")
            bundle.grid_y = d.get("grid_y")
            bundle.station_id = d.get("station_id") or station_override
            bundle.station_name = d.get("station_name") or bundle.station_id

            obs = d.get("latest_obs") or {}
            bundle.obs_timestamp = obs.get("timestamp")
            bundle.current_temp_f = obs.get("temp_f")
            bundle.current_dewpoint_f = obs.get("dewpoint_f")
            bundle.current_pressure_hpa = obs.get("pressure_hpa")
            bundle.current_wind_mph = obs.get("wind_mph")
            bundle.current_wind_dir_deg = obs.get("wind_dir_deg")
            bundle.current_conditions = obs.get("conditions")

            p_pts = [
                HourlyPressurePoint(
                    timestamp=str(item["timestamp"]),
                    pressure_hpa=float(item["pressure_hpa"]),
                )
                for item in d.get("pressure_series") or []
            ]
            bundle.pressure_series = p_pts
            if p_pts:
                vals = [p.pressure_hpa for p in p_pts]
                bundle.pressure_min_7d_hpa = round(min(vals), 1)
                bundle.pressure_max_7d_hpa = round(max(vals), 1)
                bundle.pressure_mean_7d_hpa = round(sum(vals) / len(vals), 1)
                # Estimate 24h change
                try:
                    latest_dt = datetime.fromisoformat(p_pts[-1].timestamp)
                    target_24h = latest_dt - timedelta(hours=24)
                    best_pt = min(
                        p_pts,
                        key=lambda x: abs((datetime.fromisoformat(x.timestamp) - target_24h).total_seconds()),
                    )
                    if abs((datetime.fromisoformat(best_pt.timestamp) - target_24h).total_seconds()) <= 6 * 3600:
                        bundle.pressure_change_24h_hpa = round(
                            p_pts[-1].pressure_hpa - best_pt.pressure_hpa, 1
                        )
                except Exception:
                    pass

            bundle.daily_forecasts = [
                DailyForecastSummary(
                    date=str(fc["date"]),
                    day_name=str(fc["day_name"]),
                    high_f=float(fc["high_f"]) if fc.get("high_f") is not None else None,
                    low_f=float(fc["low_f"]) if fc.get("low_f") is not None else None,
                    pop_pct=int(fc["pop_pct"]) if fc.get("pop_pct") is not None else None,
                    qpf_in=float(fc["qpf_in"]) if fc.get("qpf_in") is not None else None,
                    snow_in=float(fc["snow_in"]) if fc.get("snow_in") is not None else None,
                    short_forecast=str(fc.get("short_forecast") or ""),
                    wind_summary=str(fc.get("wind_summary") or ""),
                )
                for fc in d.get("daily_forecasts") or []
            ]

            bundle.afd_office = bundle.grid_id
            bundle.afd_issued_at = d.get("afd_issued_at")
            bundle.afd_synopsis = d.get("afd_synopsis")

        bundle.nws_provenance = SourceProvenance(
            source_name="NOAA / NWS API",
            product=f"Station {bundle.station_id or 'N/A'} Obs, Grid Forecast ({bundle.grid_id or 'N/A'}) & AFD",
            url=points_url,
            retrieved_at=res.fetched_at,
            valid_through=bundle.obs_timestamp or (bundle.daily_forecasts[-1].date if bundle.daily_forecasts else None),
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=bool(bundle.daily_forecasts or bundle.pressure_series),
            error=res.error if not (bundle.daily_forecasts or bundle.pressure_series) else None,
        )
        return bundle

    get_location_bundle = get_location_nws_bundle

    def get_data(self) -> Dict[str, Any]:
        return {}


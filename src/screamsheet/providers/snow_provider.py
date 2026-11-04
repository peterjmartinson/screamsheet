"""NOAA / NCEI Regional Climate Centers ACIS & NWS Snow Observation Provider.

Authoritative Sources:
  - NOAA RCC-ACIS Web Services:
      - Station metadata discovery: https://data.rcc-acis.org/StnMeta
      - Daily snow depth (``snwd``) and snowfall (``snow``): https://data.rcc-acis.org/StnData
  - NWS API raw gridpoint ``snowfallAmount`` forecast (already extracted into ``LocalLocationBundle``).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import (
    LocalLocationBundle,
    SnowDailyPoint,
    SnowLocationBundle,
    SourceProvenance,
)
from .climate_history_provider import (
    ACIS_STNDATA_URL,
    ACIS_STNMETA_URL,
    _parse_acis_float,
)

logger = logging.getLogger(__name__)


class SnowProvider(DataProvider):
    """Fetches authoritative daily snow depth and snowfall observations from NOAA ACIS."""

    def __init__(
        self,
        history_days: int = 45,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.history_days = max(history_days, 30)
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def parse_acis_snow_data(
        resp_json: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[float], List[SnowDailyPoint]]:
        """Parse ACIS StnData JSON response for ``snow`` and ``snwd`` elements."""
        meta = resp_json.get("meta") or {}
        stn_name = meta.get("name")
        elev_ft = _parse_acis_float(meta.get("elev"))
        rows = resp_json.get("data") or []
        points: List[SnowDailyPoint] = []

        for row in rows:
            if not isinstance(row, list) or len(row) < 3:
                continue
            d_str = str(row[0]).strip()
            snow_in = _parse_acis_float(row[1], trace_as_zero=True)
            snwd_in = _parse_acis_float(row[2], trace_as_zero=True)
            points.append(
                SnowDailyPoint(
                    date=d_str,
                    snowfall_in=snow_in,
                    snow_depth_in=snwd_in,
                )
            )
        points.sort(key=lambda p: p.date)
        return stn_name, elev_ft, points

    @staticmethod
    def select_candidate_snow_stations(
        meta_json: Dict[str, Any],
        target_lat: float,
        target_lon: float,
        min_end_year: int,
    ) -> List[str]:
        """Rank candidate snow stations from ACIS StnMeta response."""
        stations = meta_json.get("meta") or []
        scored: List[Tuple[float, str]] = []

        for stn in stations:
            sids = stn.get("sids") or []
            if not sids:
                continue
            chosen_sid = str(sids[0]).split()[0]
            for sid_entry in sids:
                parts = str(sid_entry).split()
                if len(parts) >= 2 and parts[1] == "6":
                    chosen_sid = parts[0]
                    break

            valid_daterange = stn.get("valid_daterange") or []
            snow_active = False
            snwd_active = False
            if len(valid_daterange) >= 1 and valid_daterange[0]:
                end_str = str(valid_daterange[0][-1])
                if end_str[:4].isdigit() and int(end_str[:4]) >= min_end_year:
                    snow_active = True
            if len(valid_daterange) >= 2 and valid_daterange[1]:
                end_str = str(valid_daterange[1][-1])
                if end_str[:4].isdigit() and int(end_str[:4]) >= min_end_year:
                    snwd_active = True

            if not (snow_active or snwd_active):
                continue

            ll = stn.get("ll") or [target_lon, target_lat]
            stn_lon = float(ll[0]) if len(ll) >= 2 else target_lon
            stn_lat = float(ll[1]) if len(ll) >= 2 else target_lat
            dist_deg = ((stn_lat - target_lat) ** 2 + (stn_lon - target_lon) ** 2) ** 0.5
            elev_ft = _parse_acis_float(stn.get("elev")) or 0.0

            score = (
                (1000.0 if snwd_active else 0.0)
                + (300.0 if snow_active else 0.0)
                + min(elev_ft / 10.0, 500.0)
                - (dist_deg * 500.0)
            )
            scored.append((score, chosen_sid))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [sid for _, sid in scored[:4]]

    def _fetch_station_snow(
        self, sid: str, sdate: str, edate: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
        payload = {
            "sid": sid,
            "sdate": sdate,
            "edate": edate,
            "elems": [
                {"name": "snow"},
                {"name": "snwd"},
            ],
            "meta": ["name", "sids", "elev", "ll"],
        }

        def _fetch() -> Dict[str, Any]:
            resp = requests.post(
                ACIS_STNDATA_URL,
                json=payload,
                timeout=20,
                headers={"User-Agent": "screamsheet-weather-patterns/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"ACIS error for {sid}: {data['error']}")
            return data

        cached = weather_cache_fetch(
            cache_key=f"acis:snow:{sid}:{sdate}:{edate}",
            source_url=ACIS_STNDATA_URL,
            fresh_hours=6.0,
            max_stale_hours=168.0,
            fetcher=_fetch,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        if not cached.data:
            return None, cached
        if isinstance(cached.data, dict):
            return cached.data, cached
        try:
            return json.loads(cached.data), cached
        except Exception:
            return None, cached

    def _discover_candidate_stations(
        self, lat: float, lon: float, min_end_year: int
    ) -> List[str]:
        bbox = f"{lon - 0.22:.4f},{lat - 0.22:.4f},{lon + 0.22:.4f},{lat + 0.22:.4f}"
        payload = {
            "bbox": bbox,
            "elems": "snow,snwd",
            "meta": "name,sids,ll,elev,valid_daterange",
        }

        def _fetch() -> Dict[str, Any]:
            resp = requests.post(
                ACIS_STNMETA_URL,
                json=payload,
                timeout=20,
                headers={"User-Agent": "screamsheet-weather-patterns/1.0"},
            )
            resp.raise_for_status()
            return resp.json()

        cached = weather_cache_fetch(
            cache_key=f"acis:snow_meta:{round(lat, 3)},{round(lon, 3)}",
            source_url=ACIS_STNMETA_URL,
            fresh_hours=168.0,
            max_stale_hours=720.0,
            fetcher=_fetch,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        if not cached.data:
            return []
        try:
            meta_json = cached.data if isinstance(cached.data, dict) else json.loads(cached.data)
            return self.select_candidate_snow_stations(
                meta_json, target_lat=lat, target_lon=lon, min_end_year=min_end_year
            )
        except Exception as exc:
            logger.warning("Failed to parse ACIS snow StnMeta near %s,%s: %s", lat, lon, exc)
            return []

    @staticmethod
    def build_snow_bundle(
        station_id: Optional[str],
        station_name: Optional[str],
        elevation_ft: Optional[float],
        points: List[SnowDailyPoint],
        forecast_snow_7d_in: Optional[float],
        provenance: Optional[SourceProvenance] = None,
    ) -> SnowLocationBundle:
        """Compute summary snow metrics and determine if snow data are useful to display."""
        valid_depth_pts = [p for p in points if p.snow_depth_in is not None]
        current_depth: Optional[float] = (
            valid_depth_pts[-1].snow_depth_in if valid_depth_pts else None
        )
        depth_7d_change: Optional[float] = None
        if len(valid_depth_pts) >= 2:
            ref_idx = max(0, len(valid_depth_pts) - 8)
            if (
                current_depth is not None
                and valid_depth_pts[ref_idx].snow_depth_in is not None
            ):
                depth_7d_change = round(
                    current_depth - float(valid_depth_pts[ref_idx].snow_depth_in), 1
                )

        last2 = points[-2:] if len(points) >= 2 else points
        last7 = points[-7:] if len(points) >= 7 else points

        snow_24h_vals = [p.snowfall_in for p in last2 if p.snowfall_in is not None]
        snow_7d_vals = [p.snowfall_in for p in last7 if p.snowfall_in is not None]

        snow_24h = round(snow_24h_vals[-1], 1) if snow_24h_vals else None
        snow_7d = round(sum(snow_7d_vals), 1) if snow_7d_vals else None

        any_positive_depth = any((p.snow_depth_in or 0.0) > 0.0 for p in points)
        any_positive_snowfall = (
            (snow_7d or 0.0) > 0.0
            or any((p.snowfall_in or 0.0) > 0.0 for p in points)
        )
        any_positive_forecast = (forecast_snow_7d_in or 0.0) >= 0.1

        has_useful = bool(
            any_positive_depth or any_positive_snowfall or any_positive_forecast
        )

        return SnowLocationBundle(
            station_id=station_id or "N/A",
            station_name=station_name or station_id or "Local Station",
            elevation_ft=elevation_ft,
            current_depth_in=current_depth,
            change_7d_in=depth_7d_change,
            snowfall_24h_in=snow_24h,
            snowfall_7d_in=snow_7d,
            forecast_snow_7d_in=forecast_snow_7d_in,
            daily_series=points,
            has_useful_snow_data=has_useful,
            provenance=provenance,
        )

    def enrich_location_snow(
        self,
        loc: LocalLocationBundle,
        explicit_snow_station: Optional[str] = None,
        target_date: Optional[datetime] = None,
    ) -> LocalLocationBundle:
        """Populate ``loc.snow`` in-place and return ``loc``."""
        end_dt = (target_date or datetime.now()).date()
        start_dt = end_dt - timedelta(days=self.history_days)
        sdate = start_dt.strftime("%Y-%m-%d")
        edate = end_dt.strftime("%Y-%m-%d")

        fcst_snow_vals = [
            f.snow_in
            for f in loc.daily_forecasts[:7]
            if f.snow_in is not None
        ]
        fcst_snow_7d: Optional[float] = (
            round(sum(fcst_snow_vals), 1) if fcst_snow_vals else None
        )

        candidates: List[str] = []
        if explicit_snow_station:
            candidates.append(explicit_snow_station.strip())
        discovered = self._discover_candidate_stations(
            lat=loc.lat, lon=loc.lon, min_end_year=end_dt.year - 1
        )
        for sid in discovered:
            if sid not in candidates:
                candidates.append(sid)
        if loc.station_id and loc.station_id not in candidates:
            candidates.append(loc.station_id)

        chosen_sid: Optional[str] = None
        chosen_name: Optional[str] = None
        chosen_elev: Optional[float] = None
        chosen_points: List[SnowDailyPoint] = []
        chosen_cached: Optional[Any] = None

        for sid in candidates:
            resp_json, cached = self._fetch_station_snow(sid, sdate, edate)
            if not resp_json:
                continue
            stn_name, elev_ft, pts = self.parse_acis_snow_data(resp_json)
            has_any_obs = any(
                p.snow_depth_in is not None or p.snowfall_in is not None for p in pts
            )
            if not has_any_obs:
                continue

            if chosen_sid is None:
                chosen_sid = sid
                chosen_name = stn_name
                chosen_elev = elev_ft
                chosen_points = pts
                chosen_cached = cached
                if any(p.snow_depth_in is not None for p in pts) and any(
                    p.snowfall_in is not None for p in pts
                ):
                    break
            else:
                if not any(p.snowfall_in is not None for p in chosen_points) and any(
                    p.snowfall_in is not None for p in pts
                ):
                    snow_by_date = {p.date: p.snowfall_in for p in pts if p.snowfall_in is not None}
                    for cp in chosen_points:
                        if cp.snowfall_in is None and cp.date in snow_by_date:
                            cp.snowfall_in = snow_by_date[cp.date]
                    break

        prov: Optional[SourceProvenance] = None
        if chosen_sid and chosen_cached:
            valid_dates = [
                p.date
                for p in chosen_points
                if p.snow_depth_in is not None or p.snowfall_in is not None
            ]
            prov = SourceProvenance(
                source_name="NOAA / NCEI RCC-ACIS",
                product=f"Daily Snow Depth & Snowfall ({chosen_name or chosen_sid})",
                url=ACIS_STNDATA_URL,
                retrieved_at=chosen_cached.fetched_at,
                valid_through=valid_dates[-1] if valid_dates else None,
                from_cache=chosen_cached.from_cache,
                is_stale=chosen_cached.is_stale,
                age_hours=chosen_cached.age_hours,
                available=bool(valid_dates),
                error=chosen_cached.error,
                notes=f"Elev {chosen_elev:.0f} ft" if chosen_elev is not None else None,
            )

        loc.snow = self.build_snow_bundle(
            station_id=chosen_sid,
            station_name=chosen_name,
            elevation_ft=chosen_elev,
            points=chosen_points,
            forecast_snow_7d_in=fcst_snow_7d,
            provenance=prov,
        )
        return loc

    def fetch_data(self) -> Dict[str, Any]:
        return {}

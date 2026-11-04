"""NOAA / NCEI Regional Climate Centers ACIS Historical Observations & Normals Provider.

Authoritative Source:
  - NOAA RCC-ACIS Web Services: https://data.rcc-acis.org/StnData
  - Retrieves daily station observations and official 1991–2020 NCEI Climatological Normals:
      - ``maxt``, ``mint``, ``avgt`` (°F)
      - ``avgt`` 1991–2020 normal and daily departure (°F)
      - ``pcpn`` (inches) and ``pcpn`` 1991–2020 daily normal (inches)
  - Computes true climatological anomalies:
      - 7-day and 14-day mean temperature anomaly (°F vs 1991–2020 normal)
      - 30-day total precipitation and % of 1991–2020 normal
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import (
    DailyClimatePoint,
    LocalLocationBundle,
    SourceProvenance,
)

logger = logging.getLogger(__name__)

ACIS_STNDATA_URL = "https://data.rcc-acis.org/StnData"
ACIS_STNMETA_URL = "https://data.rcc-acis.org/StnMeta"


def _parse_acis_float(val: Any, trace_as_zero: bool = True) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().upper()
    if not s or s in ("M", "S", "A", "-999", "NAN"):
        return None
    if s == "T":
        return 0.0 if trace_as_zero else None
    # Strip trailing flags if any
    s_clean = re.sub(r"[^0-9.+-]", "", s)
    if not s_clean:
        return None
    try:
        return float(s_clean)
    except ValueError:
        return None


class ClimateHistoryProvider(DataProvider):
    """Fetches historical local station observations and 1991–2020 NCEI normals from NOAA ACIS."""

    def __init__(
        self,
        history_days: int = 35,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.history_days = max(history_days, 35)
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def parse_acis_stndata(
        resp_json: Dict[str, Any],
    ) -> Tuple[Optional[str], List[DailyClimatePoint]]:
        """Parse ACIS StnData JSON response into station name and daily climate points."""
        meta = resp_json.get("meta") or {}
        stn_name = meta.get("name")
        rows = resp_json.get("data") or []
        points: List[DailyClimatePoint] = []

        for row in rows:
            if not isinstance(row, list) or len(row) < 8:
                continue
            d_str = str(row[0]).strip()
            max_t = _parse_acis_float(row[1])
            min_t = _parse_acis_float(row[2])
            avg_t = _parse_acis_float(row[3])
            norm_t = _parse_acis_float(row[4])
            dep_t = _parse_acis_float(row[5])
            pcpn = _parse_acis_float(row[6], trace_as_zero=True)
            norm_pcpn = _parse_acis_float(row[7], trace_as_zero=True)

            if dep_t is None and avg_t is not None and norm_t is not None:
                dep_t = round(avg_t - norm_t, 1)

            points.append(
                DailyClimatePoint(
                    date=d_str,
                    max_temp_f=max_t,
                    min_temp_f=min_t,
                    avg_temp_f=avg_t,
                    normal_temp_f=norm_t,
                    temp_departure_f=dep_t,
                    precip_in=pcpn,
                    normal_precip_in=norm_pcpn,
                )
            )
        points.sort(key=lambda p: p.date)
        return stn_name, points

    @staticmethod
    def compute_anomalies(
        points: List[DailyClimatePoint],
    ) -> Dict[str, Optional[float]]:
        """Compute 7d/14d temperature anomalies and 30d precipitation % of normal."""
        valid_temp_pts = [p for p in points if p.temp_departure_f is not None]
        temp_7d: Optional[float] = None
        temp_14d: Optional[float] = None
        if len(valid_temp_pts) >= 5:
            last7 = valid_temp_pts[-7:]
            temp_7d = round(sum(p.temp_departure_f for p in last7 if p.temp_departure_f is not None) / len(last7), 1)
        if len(valid_temp_pts) >= 10:
            last14 = valid_temp_pts[-14:]
            temp_14d = round(sum(p.temp_departure_f for p in last14 if p.temp_departure_f is not None) / len(last14), 1)

        valid_pcpn_pts = [
            p for p in points[-31:]
            if p.precip_in is not None and p.normal_precip_in is not None
        ]
        pcpn_30d: Optional[float] = None
        pcpn_norm_30d: Optional[float] = None
        pcpn_pct_30d: Optional[float] = None
        if len(valid_pcpn_pts) >= 20:
            last30 = valid_pcpn_pts[-30:]
            pcpn_30d = round(sum(p.precip_in or 0.0 for p in last30), 2)
            pcpn_norm_30d = round(sum(p.normal_precip_in or 0.0 for p in last30), 2)
            if pcpn_norm_30d and pcpn_norm_30d > 0.1:
                pcpn_pct_30d = round((pcpn_30d / pcpn_norm_30d) * 100.0, 0)

        return {
            "temp_anomaly_7d_f": temp_7d,
            "temp_anomaly_14d_f": temp_14d,
            "precip_30d_in": pcpn_30d,
            "precip_30d_normal_in": pcpn_norm_30d,
            "precip_30d_pct_normal": pcpn_pct_30d,
        }

    def enrich_location_climate(
        self,
        bundle: LocalLocationBundle,
        target_date: Optional[datetime] = None,
    ) -> LocalLocationBundle:
        """Populate ``bundle`` with ACIS historical climate series and 1991–2020 anomalies."""
        ref_date = target_date or datetime.now()
        sdate = (ref_date - timedelta(days=self.history_days)).strftime("%Y-%m-%d")
        edate = ref_date.strftime("%Y-%m-%d")
        sid = bundle.station_id
        safe_slug = re.sub(r"[^a-z0-9]+", "_", (sid or bundle.name).lower()).strip("_")

        def _fetch() -> Dict[str, Any]:
            chosen_sid = sid
            if not chosen_sid:
                # Discover nearby station with ACIS temperature normals via bbox
                bbox = f"{bundle.lon - 0.35:.3f},{bundle.lat - 0.35:.3f},{bundle.lon + 0.35:.3f},{bundle.lat + 0.35:.3f}"
                r_meta = requests.post(
                    ACIS_STNMETA_URL,
                    json={"bbox": bbox, "meta": "name,sids,valid_daterange", "elems": "avgt,pcpn"},
                    timeout=15,
                )
                if r_meta.ok:
                    for stn in r_meta.json().get("meta") or []:
                        sids = stn.get("sids") or []
                        vdr = stn.get("valid_daterange") or []
                        if sids and any(r and r[1] >= edate[:4] for r in vdr):
                            chosen_sid = sids[0].split()[0]
                            break

            if not chosen_sid:
                raise RuntimeError(f"No ACIS station ID found for {bundle.name}")

            payload = {
                "sid": chosen_sid,
                "sdate": sdate,
                "edate": edate,
                "elems": [
                    {"name": "maxt"},
                    {"name": "mint"},
                    {"name": "avgt"},
                    {"name": "avgt", "normal": "1"},
                    {"name": "avgt", "normal": "departure"},
                    {"name": "pcpn"},
                    {"name": "pcpn", "normal": "1"},
                ],
            }
            resp = requests.post(ACIS_STNDATA_URL, json=payload, timeout=20)
            resp.raise_for_status()
            js = resp.json()
            if not js.get("data"):
                raise RuntimeError(f"Empty ACIS StnData for {chosen_sid}")
            return js

        res = weather_cache_fetch(
            cache_key=f"acis_climate_{safe_slug}_{edate}",
            source_url=ACIS_STNDATA_URL,
            fetcher=_fetch,
            fresh_hours=12.0,
            max_stale_hours=168.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        valid_date: Optional[str] = None
        if res.data:
            stn_name, pts = self.parse_acis_stndata(res.data)
            bundle.climate_station_name = stn_name
            bundle.climate_series = pts
            anoms = self.compute_anomalies(pts)
            bundle.temp_anomaly_7d_f = anoms["temp_anomaly_7d_f"]
            bundle.temp_anomaly_14d_f = anoms["temp_anomaly_14d_f"]
            bundle.precip_30d_in = anoms["precip_30d_in"]
            bundle.precip_30d_normal_in = anoms["precip_30d_normal_in"]
            bundle.precip_30d_pct_normal = anoms["precip_30d_pct_normal"]
            valid_pts = [p for p in pts if p.avg_temp_f is not None or p.precip_in is not None]
            if valid_pts:
                valid_date = valid_pts[-1].date

        bundle.climate_provenance = SourceProvenance(
            source_name="NOAA / NCEI RCC-ACIS",
            product=f"Daily Station Normals (1991–2020) & Anomalies ({bundle.climate_station_name or sid or 'N/A'})",
            url=ACIS_STNDATA_URL,
            retrieved_at=res.fetched_at,
            valid_through=valid_date,
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=bool(bundle.climate_series),
            error=res.error if not bundle.climate_series else None,
        )
        return bundle

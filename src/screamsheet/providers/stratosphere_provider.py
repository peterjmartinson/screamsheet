"""Stratospheric Polar Vortex / SSW Provider (10 hPa 60°N Zonal Wind & 60–90°N Polar Cap Temp).

Authoritative Source:
  - NASA GSFC Atmospheric Chemistry and Dynamics Laboratory / NOAA CPC partner portal:
    - Static NH Annual MERRA-2 + GEOS-5 FP ASCII tables:
      https://acd-ext.gsfc.nasa.gov/Data_services/met/metdata/annual/merra2/wind/u60n_10_{year}_merra2.txt
      https://acd-ext.gsfc.nasa.gov/Data_services/met/metdata/annual/merra2/temp/t60_90n_10_{year}_merra2.txt
    - CGI fallback: https://acd-ext.gsfc.nasa.gov/cgi-bin/datareq.pl (linked from NOAA CPC
      https://www.cpc.ncep.noaa.gov/products/stratosphere/)
  - Provides daily machine-readable fixed-width ASCII tables of:
      1. 10-hPa 60°N zonal-mean zonal wind U (m/s)
      2. 10-hPa 60–90°N polar cap temperature T (K)
    from MERRA-2 reanalysis supplemented with near-real-time GEOS-5 FP analysis and
    10-day deterministic forecasts.

Limitation Note:
  - NOAA CPC's SSW monitoring page (https://www.cpc.ncep.noaa.gov/products/stratosphere/SSW/)
    publishes PNG graphics rather than current public CSV/ASCII time series (legacy FTP
    directory ``wd53rl/cpc_zonal`` stopped updating in 2021). Rather than scraping PNG images,
    we query the official NASA GSFC / GMAO MERRA-2 + GEOS-5 FP ASCII service linked directly
    from the CPC Stratosphere page. Because GEOS-5 FP provides deterministic forecast leads
    without ensemble members, we do not manufacture ensemble spread bounds for this chart.
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
    SourceProvenance,
    StratosphereBundle,
    StratosphereDailyPoint,
)

logger = logging.getLogger(__name__)

GSFC_DATAREQ_URL = "https://acd-ext.gsfc.nasa.gov/cgi-bin/datareq.pl"
GSFC_ANNUAL_U60N_10_URL_TMPL = (
    "https://acd-ext.gsfc.nasa.gov/Data_services/met/metdata/annual/merra2/wind/"
    "u60n_10_{year}_merra2.txt"
)
GSFC_ANNUAL_T60_90N_10_URL_TMPL = (
    "https://acd-ext.gsfc.nasa.gov/Data_services/met/metdata/annual/merra2/temp/"
    "t60_90n_10_{year}_merra2.txt"
)
_DATE_LINE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s+([-\d.]+)\s+([-\d.]+)")


class StratosphereProvider(DataProvider):
    """Fetches and normalizes 10-hPa 60°N zonal wind and 60–90°N polar cap temperature."""

    def __init__(
        self,
        history_days: int = 60,
        forecast_days: int = 14,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.history_days = history_days
        self.forecast_days = forecast_days
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def parse_gsfc_ascii(
        raw_text: str,
        target_date: Optional[datetime] = None,
        history_days: int = 60,
        forecast_days: int = 14,
    ) -> Tuple[List[StratosphereDailyPoint], List[StratosphereDailyPoint]]:
        """Parse fixed-width ASCII table from ``datareq.pl`` into (observations, forecasts).

        When both ``v14`` (T 60_90N) and ``v04`` (U 60N) are requested at ``p10`` (10 hPa),
        columns are ordered by variable: ``Date | T (60_90 N, K) | U (60 N, m/s)``.
        If only ``v04`` is present, ``Date | U (60 N, m/s)``.
        """
        today_str = (target_date or datetime.now()).strftime("%Y-%m-%d")
        lines = raw_text.strip().splitlines()

        # Detect column order from header lines
        has_temp_first = True
        for line in lines[:6]:
            tokens = line.split()
            if "T" in tokens and "U" in tokens:
                has_temp_first = tokens.index("T") < tokens.index("U")
                break

        obs: List[StratosphereDailyPoint] = []
        fcst: List[StratosphereDailyPoint] = []

        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            date_str = parts[0]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                continue
            try:
                if len(parts) >= 3:
                    val1 = float(parts[1])
                    val2 = float(parts[2])
                    t_val = val1 if has_temp_first else val2
                    u_val = val2 if has_temp_first else val1
                else:
                    t_val = None
                    u_val = float(parts[1])

                # Filter missing values (-99999.00 or similar)
                if u_val <= -900.0 or abs(u_val) > 250.0:
                    continue
                if t_val is not None and (t_val <= 100.0 or t_val >= 350.0):
                    t_val = None

                is_fcst = date_str > today_str
                pt = StratosphereDailyPoint(
                    date=date_str,
                    zonal_wind_10hpa_60n=u_val,
                    polar_cap_temp_10hpa_60_90n=t_val,
                    is_forecast=is_fcst,
                )
                if is_fcst:
                    fcst.append(pt)
                else:
                    obs.append(pt)
            except ValueError:
                continue

        obs.sort(key=lambda p: p.date)
        fcst.sort(key=lambda p: p.date)
        if history_days > 0 and len(obs) > history_days:
            obs = obs[-history_days:]
        if forecast_days > 0 and len(fcst) > forecast_days:
            fcst = fcst[:forecast_days]
        return obs, fcst

    @staticmethod
    def parse_annual_merra2_txt(raw_text: str) -> Dict[str, Tuple[float, int]]:
        """Parse static GSFC annual MERRA-2/GEOS-FP ``.txt`` table into ``{date: (value, fcst_hr)}``."""
        out: Dict[str, Tuple[float, int]] = {}
        for line in raw_text.strip().splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            date_str = parts[0]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                continue
            try:
                val = float(parts[1])
                if val <= -900.0:
                    continue
                fcst_hr = int(float(parts[9])) if len(parts) >= 10 else 0
                if fcst_hr < 0:
                    continue
                out[date_str] = (val, fcst_hr)
            except ValueError:
                continue
        return out

    def _fetch_static_annual_series(
        self,
        start_dt: datetime,
        end_dt: datetime,
        ref_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch static NH annual ``u60n_10`` and ``t60_90n_10`` ASCII files from GSFC."""
        season_yr = ref_date.year if ref_date.month >= 7 else ref_date.year - 1
        years = [season_yr]
        if start_dt < datetime(season_yr, 7, 1):
            years.insert(0, season_yr - 1)

        u_map: Dict[str, Tuple[float, int]] = {}
        t_map: Dict[str, Tuple[float, int]] = {}
        for yr in years:
            u_url = GSFC_ANNUAL_U60N_10_URL_TMPL.format(year=yr)
            r_u = requests.get(u_url, timeout=(5, 10))
            if r_u.ok:
                u_map.update(self.parse_annual_merra2_txt(r_u.text))
            t_url = GSFC_ANNUAL_T60_90N_10_URL_TMPL.format(year=yr)
            try:
                r_t = requests.get(t_url, timeout=(5, 10))
                if r_t.ok:
                    t_map.update(self.parse_annual_merra2_txt(r_t.text))
            except Exception as exc:
                logger.debug("Optional 10-hPa polar cap temp file failed (%s): %s", yr, exc)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        rows: List[Dict[str, Any]] = []
        for d_str in sorted(u_map.keys()):
            if d_str < start_str or d_str > end_str:
                continue
            u_val, fcst_hr = u_map[d_str]
            t_entry = t_map.get(d_str)
            t_val = t_entry[0] if t_entry is not None else None
            rows.append(
                {
                    "date": d_str,
                    "u": u_val,
                    "t": t_val,
                    "fcst_hr": fcst_hr,
                }
            )
        return rows

    def get_stratosphere_bundle(
        self,
        target_date: Optional[datetime] = None,
    ) -> StratosphereBundle:
        """Fetch 10-hPa 60°N zonal wind and 60–90°N temperature series."""
        ref_date = target_date or datetime.now()
        start_dt = ref_date - timedelta(days=max(self.history_days + 10, 75))
        end_dt = ref_date + timedelta(days=max(self.forecast_days + 5, 16))
        today_str = ref_date.strftime("%Y-%m-%d")
        season_yr = ref_date.year if ref_date.month >= 7 else ref_date.year - 1
        primary_url = GSFC_ANNUAL_U60N_10_URL_TMPL.format(year=season_yr)

        def _fetch() -> List[Dict[str, Any]]:
            # 1. Prefer fast static annual MERRA-2 / GEOS-5 FP ASCII tables
            try:
                static_rows = self._fetch_static_annual_series(start_dt, end_dt, ref_date)
                if static_rows:
                    return static_rows
            except Exception as exc:
                logger.debug("Static GSFC annual stratosphere fetch failed, trying CGI: %s", exc)

            # 2. Fallback to GSFC datareq.pl CGI endpoint
            form_data = {
                "source": "merra2",
                "when": "range",
                "range_begday": f"{start_dt.day:02d}",
                "range_begmon": f"{start_dt.month:02d}",
                "range_begyr": f"{start_dt.year:04d}",
                "range_endday": f"{end_dt.day:02d}",
                "range_endmon": f"{end_dt.month:02d}",
                "range_endyr": f"{end_dt.year:04d}",
                "v14": "on",  # Temperature 60-90°N (K)
                "v04": "on",  # Zonal Wind 60°N (m/s)
                "north": "on",
                "p10": "on",  # 10 hPa
            }
            resp = requests.post(GSFC_DATAREQ_URL, data=form_data, timeout=(6, 12))
            resp.raise_for_status()
            if "Input Errors" in resp.text:
                raise RuntimeError("GSFC datareq.pl returned input error page")
            obs_pts, fcst_pts = self.parse_gsfc_ascii(
                resp.text,
                target_date=ref_date,
                history_days=120,
                forecast_days=20,
            )
            all_pts = obs_pts + fcst_pts
            if not all_pts:
                raise RuntimeError("No valid data rows parsed from GSFC datareq.pl")
            return [
                {
                    "date": p.date,
                    "u": p.zonal_wind_10hpa_60n,
                    "t": p.polar_cap_temp_10hpa_60_90n,
                }
                for p in all_pts
            ]

        res = weather_cache_fetch(
            cache_key=f"stratosphere_merra2_10hpa_{today_str}",
            source_url=primary_url,
            fetcher=_fetch,
            fresh_hours=8.0,
            max_stale_hours=168.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        obs: List[StratosphereDailyPoint] = []
        fcst: List[StratosphereDailyPoint] = []
        if res.data:
            for item in res.data:
                d_str = str(item["date"])
                fcst_hr = int(item.get("fcst_hr", 0) or 0)
                is_f = (d_str > today_str) or (fcst_hr > 0)
                pt = StratosphereDailyPoint(
                    date=d_str,
                    zonal_wind_10hpa_60n=float(item["u"]),
                    polar_cap_temp_10hpa_60_90n=(
                        float(item["t"]) if item.get("t") is not None else None
                    ),
                    is_forecast=is_f,
                )
                if is_f:
                    fcst.append(pt)
                else:
                    obs.append(pt)
            if self.history_days > 0 and len(obs) > self.history_days:
                obs = obs[-self.history_days:]
            if self.forecast_days > 0 and len(fcst) > self.forecast_days:
                fcst = fcst[:self.forecast_days]

        prov = SourceProvenance(
            source_name="NASA GSFC / GMAO (CPC Partner)",
            product="MERRA-2 & GEOS-5 FP 10-hPa 60°N Zonal Wind & 60–90°N Temp",
            url=primary_url,
            retrieved_at=res.fetched_at,
            valid_through=obs[-1].date if obs else None,
            forecast_init=f"{obs[-1].date} 00Z (GEOS-5 FP)" if (obs and fcst) else None,
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=bool(obs),
            error=res.error if not obs else None,
            notes="Deterministic GEOS-5 FP forecast through ~10 days; ensemble spread not exposed by ASCII endpoint.",
        )

        return StratosphereBundle(
            level_hpa=10,
            latitude_deg=60,
            observations=obs,
            forecasts=fcst,
            provenance=prov,
        )

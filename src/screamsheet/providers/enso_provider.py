"""NOAA CPC / PSL ENSO Provider (Niño 3.4, ONI, RONI, MEI.v2).

Authoritative Sources:
  - Monthly Niño 3.4 (ERSSTv5 1991-2020 centered base periods, 1950-present):
    https://www.cpc.ncep.noaa.gov/data/indices/detrend.nino34.ascii.txt
  - Oceanic Niño Index (ONI, 3-month running mean ERSSTv5 Niño 3.4 anomaly):
    https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
  - Relative Oceanic Niño Index (RONI, 3-month running mean relative to tropical mean):
    https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt
  - Multivariate ENSO Index Version 2 (MEI.v2, NOAA PSL bi-monthly):
    https://psl.noaa.gov/enso/mei/data/meiv2.data
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import ENSOBundle, ENSOMonthlyPoint, SourceProvenance

logger = logging.getLogger(__name__)

CPC_NINO34_URL = "https://www.cpc.ncep.noaa.gov/data/indices/detrend.nino34.ascii.txt"
CPC_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
CPC_RONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"
PSL_MEIV2_URL = "https://psl.noaa.gov/enso/mei/data/meiv2.data"

MEI_SEASONS = ["DJ", "JF", "FM", "MA", "AM", "MJ", "JJ", "JA", "AS", "SO", "ON", "ND"]


def classify_enso_state(nino34_anom: Optional[float], oni_anom: Optional[float] = None) -> str:
    """Classify slow-moving ENSO background state using standard NOAA +/-0.5°C thresholds."""
    val = oni_anom if oni_anom is not None else nino34_anom
    if val is None:
        return "Unavailable"
    if val >= 1.5:
        return "Strong El Niño"
    if val >= 1.0:
        return "Moderate El Niño"
    if val >= 0.5:
        return "Weak El Niño / El Niño Advisory"
    if val <= -1.5:
        return "Strong La Niña"
    if val <= -1.0:
        return "Moderate La Niña"
    if val <= -0.5:
        return "Weak La Niña / La Niña Advisory"
    return "ENSO-Neutral"


class ENSOProvider(DataProvider):
    """Fetches and caches monthly/seasonal ENSO indices from NOAA CPC and PSL."""

    def __init__(
        self,
        months_to_keep: int = 24,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.months_to_keep = months_to_keep
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def parse_nino34_ascii(
        raw_text: str,
        target_date: Optional[datetime] = None,
        months_to_keep: int = 24,
    ) -> List[ENSOMonthlyPoint]:
        """Parse CPC detrend.nino34.ascii.txt into monthly points."""
        cutoff_ym = target_date.strftime("%Y-%m") if target_date else None
        pts: List[ENSOMonthlyPoint] = []
        for line in raw_text.strip().splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0].upper() == "YR":
                continue
            try:
                yr = int(parts[0])
                mon = int(parts[1])
                total = float(parts[2])
                anom = float(parts[4])
                if anom <= -90.0:
                    continue
                period = f"{yr:04d}-{mon:02d}"
                if cutoff_ym and period > cutoff_ym:
                    continue
                pts.append(
                    ENSOMonthlyPoint(
                        period=period,
                        nino34_anomaly=anom,
                        nino34_total=total,
                    )
                )
            except (ValueError, IndexError):
                continue

        pts.sort(key=lambda p: p.period)
        if months_to_keep > 0 and len(pts) > months_to_keep:
            pts = pts[-months_to_keep:]
        return pts

    @staticmethod
    def parse_oni_ascii(raw_text: str) -> List[Tuple[str, int, float]]:
        """Parse CPC oni.ascii.txt into (season, year, anomaly) tuples."""
        rows: List[Tuple[str, int, float]] = []
        for line in raw_text.strip().splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0].upper() == "SEAS":
                continue
            try:
                seas = parts[0].upper()
                yr = int(parts[1])
                anom = float(parts[3])
                if anom <= -90.0:
                    continue
                rows.append((seas, yr, anom))
            except (ValueError, IndexError):
                continue
        return rows

    @staticmethod
    def parse_roni_ascii(raw_text: str) -> List[Tuple[str, int, float]]:
        """Parse CPC RONI.ascii.txt into (season, year, anomaly) tuples."""
        rows: List[Tuple[str, int, float]] = []
        for line in raw_text.strip().splitlines():
            parts = line.split()
            if len(parts) < 3 or parts[0].upper() == "SEAS":
                continue
            try:
                seas = parts[0].upper()
                yr = int(parts[1])
                anom = float(parts[2])
                if anom <= -90.0:
                    continue
                rows.append((seas, yr, anom))
            except (ValueError, IndexError):
                continue
        return rows

    @staticmethod
    def parse_meiv2_data(raw_text: str) -> List[Tuple[str, int, float]]:
        """Parse PSL meiv2.data into (bi_monthly_season, year, value) tuples."""
        rows: List[Tuple[str, int, float]] = []
        lines = raw_text.strip().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 13:
                continue
            try:
                yr = int(parts[0])
                if yr < 1950 or yr > 2100:
                    continue
                for idx, val_str in enumerate(parts[1:13]):
                    val = float(val_str)
                    if val <= -90.0:
                        continue
                    rows.append((MEI_SEASONS[idx], yr, val))
            except (ValueError, IndexError):
                continue
        return rows

    def get_enso_bundle(self, target_date: Optional[datetime] = None) -> ENSOBundle:
        """Fetch and assemble the complete ENSO bundle (cached with 24h fresh TTL)."""
        def _fetch_all() -> Dict[str, Any]:
            r_nino = requests.get(CPC_NINO34_URL, timeout=20)
            r_nino.raise_for_status()
            nino_pts = self.parse_nino34_ascii(r_nino.text, target_date=None, months_to_keep=48)

            oni_rows: List[Tuple[str, int, float]] = []
            try:
                r_oni = requests.get(CPC_ONI_URL, timeout=15)
                if r_oni.ok:
                    oni_rows = self.parse_oni_ascii(r_oni.text)[-24:]
            except Exception as exc:
                logger.debug("Optional ONI fetch failed: %s", exc)

            roni_rows: List[Tuple[str, int, float]] = []
            try:
                r_roni = requests.get(CPC_RONI_URL, timeout=15)
                if r_roni.ok:
                    roni_rows = self.parse_roni_ascii(r_roni.text)[-24:]
            except Exception as exc:
                logger.debug("Optional RONI fetch failed: %s", exc)

            mei_rows: List[Tuple[str, int, float]] = []
            try:
                r_mei = requests.get(PSL_MEIV2_URL, timeout=15)
                if r_mei.ok:
                    mei_rows = self.parse_meiv2_data(r_mei.text)[-24:]
            except Exception as exc:
                logger.debug("Optional MEI.v2 fetch failed: %s", exc)

            return {
                "nino34": [
                    {
                        "period": p.period,
                        "nino34_anomaly": p.nino34_anomaly,
                        "nino34_total": p.nino34_total,
                    }
                    for p in nino_pts
                ],
                "oni": oni_rows,
                "roni": roni_rows,
                "meiv2": mei_rows,
            }

        res = weather_cache_fetch(
            cache_key="cpc_psl_enso_bundle",
            source_url=CPC_NINO34_URL,
            fetcher=_fetch_all,
            fresh_hours=24.0,
            max_stale_hours=336.0,  # 14 days stale tolerance for monthly dataset
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        cutoff_ym = target_date.strftime("%Y-%m") if target_date else None
        series: List[ENSOMonthlyPoint] = []
        latest_oni: Optional[float] = None
        latest_oni_season: Optional[str] = None
        latest_roni: Optional[float] = None
        latest_roni_season: Optional[str] = None
        latest_mei: Optional[float] = None
        latest_mei_season: Optional[str] = None

        if res.data:
            for item in res.data.get("nino34", []):
                if cutoff_ym and item["period"] > cutoff_ym:
                    continue
                series.append(
                    ENSOMonthlyPoint(
                        period=item["period"],
                        nino34_anomaly=float(item["nino34_anomaly"]),
                        nino34_total=float(item["nino34_total"]) if item.get("nino34_total") is not None else None,
                    )
                )
            if self.months_to_keep > 0 and len(series) > self.months_to_keep:
                series = series[-self.months_to_keep:]

            oni_list = res.data.get("oni", [])
            if oni_list:
                last_o = oni_list[-1]
                latest_oni_season = f"{last_o[0]} {last_o[1]}"
                latest_oni = float(last_o[2])

            roni_list = res.data.get("roni", [])
            if roni_list:
                last_r = roni_list[-1]
                latest_roni_season = f"{last_r[0]} {last_r[1]}"
                latest_roni = float(last_r[2])

            mei_list = res.data.get("meiv2", [])
            if mei_list:
                last_m = mei_list[-1]
                latest_mei_season = f"{last_m[0]} {last_m[1]}"
                latest_mei = float(last_m[2])

        latest_period = series[-1].period if series else None
        latest_nino34 = series[-1].nino34_anomaly if series else None
        state_label = classify_enso_state(latest_nino34, latest_oni)

        prov = SourceProvenance(
            source_name="NOAA CPC / PSL",
            product="ERSSTv5 Niño 3.4, ONI, RONI & MEI.v2",
            url=CPC_NINO34_URL,
            retrieved_at=res.fetched_at,
            valid_through=latest_period,
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=bool(series),
            error=res.error if not series else None,
        )

        return ENSOBundle(
            nino34_series=series,
            latest_period=latest_period,
            latest_nino34=latest_nino34,
            latest_oni=latest_oni,
            latest_oni_season=latest_oni_season,
            latest_roni=latest_roni,
            latest_roni_season=latest_roni_season,
            latest_meiv2=latest_mei,
            latest_meiv2_season=latest_mei_season,
            enso_state_label=state_label,
            provenance=prov,
        )

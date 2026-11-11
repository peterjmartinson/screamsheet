"""NOAA Physical Sciences Laboratory (PSL) Real-Time OLR MJO Index (ROMI) Provider.

Authoritative Source:
  - NOAA PSL Real-time OLR MJO Index (ROMI, Kiladis et al. 2014):
    https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt

Convention Note (per NOAA PSL documentation):
  - Raw columns: ``year month day hour PC1 PC2 amplitude``
  - To match the standard Wheeler-Hendon (2004) RMM phase-space diagram:
      - ``component_1`` (x-axis, RMM1-equivalent) = ``PC2(ROMI)``
      - ``component_2`` (y-axis, RMM2-equivalent) = ``-PC1(ROMI)``
  - Phase (1..8) is determined from the angle ``atan2(component_2, component_1)``:
      - Phase 1: (-180°, -135°]
      - Phase 2: (-135°, -90°]
      - Phase 3: (-90°, -45°]
      - Phase 4: (-45°, 0°]
      - Phase 5: (0°, 45°]
      - Phase 6: (45°, 90°]
      - Phase 7: (90°, 135°]
      - Phase 8: (135°, 180°]
  - Active threshold: ``amplitude >= 1.0``
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import MJOBundle, MJODailyPoint, SourceProvenance

logger = logging.getLogger(__name__)

PSL_ROMI_URL = "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt"
BOM_RMM_URL = "http://www.bom.gov.au/clim_data/IDCKGEM000/rmm.74toRealtime.txt"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/plain,text/html,*/*;q=0.8",
}


def compute_wh_phase(comp1: float, comp2: float) -> int:
    """Compute Wheeler-Hendon MJO phase (1..8) from (comp1, comp2) = (RMM1, RMM2)."""
    deg = math.degrees(math.atan2(comp2, comp1))  # [-180.0, 180.0]
    if deg < 0:
        deg += 360.0  # [0.0, 360.0)
    # 0..45 -> Phase 5, 45..90 -> Phase 6, 90..135 -> Phase 7, 135..180 -> Phase 8,
    # 180..225 -> Phase 1, 225..270 -> Phase 2, 270..315 -> Phase 3, 315..360 -> Phase 4
    octant = int(math.floor(deg / 45.0)) % 8
    phase_map = [5, 6, 7, 8, 1, 2, 3, 4]
    return phase_map[octant]


class MJOProvider(DataProvider):
    """Fetches and normalizes NOAA PSL Real-time OLR MJO Index (ROMI) data."""

    def __init__(
        self,
        history_days: int = 60,
        amplitude_threshold: float = 1.0,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.history_days = history_days
        self.amplitude_threshold = amplitude_threshold
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @classmethod
    def parse_romi_text(
        cls,
        raw_text: str,
        target_date: Optional[datetime] = None,
        history_days: int = 60,
        amplitude_threshold: float = 1.0,
    ) -> List[MJODailyPoint]:
        """Parse PSL ROMI ASCII text into sorted MJODailyPoint instances."""
        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None
        lines = raw_text.strip().splitlines()
        if len(lines) > 500:
            lines = lines[-max(history_days * 4, 400):]

        points: List[MJODailyPoint] = []
        for line in lines:
            parts = line.split()
            if len(parts) < 6:
                continue
            try:
                y = int(parts[0])
                m = int(parts[1])
                d = int(parts[2])
                # Some PSL files have 4 date columns (year month day hour), others 3 (year month day)
                if len(parts) >= 7:
                    pc1 = float(parts[4])
                    pc2 = float(parts[5])
                    amp = float(parts[6])
                else:
                    pc1 = float(parts[3])
                    pc2 = float(parts[4])
                    amp = float(parts[5])

                if pc1 <= -90.0 or pc2 <= -90.0 or amp < 0.0:
                    continue

                date_str = f"{y:04d}-{m:02d}-{d:02d}"
                if cutoff_str and date_str > cutoff_str:
                    continue

                # Convert ROMI (PC1, PC2) to Wheeler-Hendon RMM phase-space (comp1, comp2)
                comp1 = pc2
                comp2 = -pc1
                calc_amp = math.hypot(comp1, comp2)
                if abs(amp - calc_amp) > 0.05:
                    amp = calc_amp
                phase = compute_wh_phase(comp1, comp2)
                points.append(
                    MJODailyPoint(
                        date=date_str,
                        component_1=comp1,
                        component_2=comp2,
                        raw_pc1=pc1,
                        raw_pc2=pc2,
                        amplitude=amp,
                        phase=phase,
                        active=bool(amp >= amplitude_threshold),
                    )
                )
            except (ValueError, IndexError):
                continue

        points.sort(key=lambda p: p.date)
        if history_days > 0 and len(points) > history_days:
            points = points[-history_days:]
        return points

    @classmethod
    def parse_bom_rmm_text(
        cls,
        raw_text: str,
        target_date: Optional[datetime] = None,
        history_days: int = 60,
        amplitude_threshold: float = 1.0,
    ) -> List[MJODailyPoint]:
        """Parse Australian BOM rmm.74toRealtime.txt into sorted MJODailyPoint instances."""
        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None
        lines = raw_text.strip().splitlines()
        if len(lines) > 600:
            lines = lines[-max(history_days * 4, 400):]

        points: List[MJODailyPoint] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped[0].isalpha():
                continue
            parts = stripped.replace(",", " ").split()
            if len(parts) < 7:
                continue
            try:
                y = int(parts[0])
                m = int(parts[1])
                d = int(parts[2])
                rmm1 = float(parts[3])
                rmm2 = float(parts[4])
                phase = int(float(parts[5]))
                amp = float(parts[6])

                if (
                    abs(rmm1) >= 90.0
                    or abs(rmm2) >= 90.0
                    or amp >= 90.0
                    or amp < 0.0
                    or phase < 1
                    or phase > 8
                ):
                    continue

                date_str = f"{y:04d}-{m:02d}-{d:02d}"
                if cutoff_str and date_str > cutoff_str:
                    continue

                points.append(
                    MJODailyPoint(
                        date=date_str,
                        component_1=rmm1,
                        component_2=rmm2,
                        raw_pc1=-rmm2,
                        raw_pc2=rmm1,
                        amplitude=amp,
                        phase=phase,
                        active=bool(amp >= amplitude_threshold),
                    )
                )
            except (ValueError, IndexError):
                continue

        points.sort(key=lambda p: p.date)
        if history_days > 0 and len(points) > history_days:
            points = points[-history_days:]
        return points

    def get_mjo_bundle(self, target_date: Optional[datetime] = None) -> MJOBundle:
        """Fetch MJO RMM history (Australian BOM primary, NOAA PSL ROMI fallback) and provenance."""
        def _fetch() -> List[Dict[str, Any]]:
            try:
                resp = requests.get(BOM_RMM_URL, headers=_BROWSER_HEADERS, timeout=20)
                resp.raise_for_status()
                pts = self.parse_bom_rmm_text(
                    resp.text,
                    target_date=None,
                    history_days=180,
                    amplitude_threshold=self.amplitude_threshold,
                )
                if pts:
                    return [
                        {
                            "date": p.date,
                            "component_1": p.component_1,
                            "component_2": p.component_2,
                            "raw_pc1": p.raw_pc1,
                            "raw_pc2": p.raw_pc2,
                            "amplitude": p.amplitude,
                            "phase": p.phase,
                            "active": p.active,
                            "source_name": "Australian BOM",
                            "product": "Real-time Multivariate MJO (RMM)",
                            "url": BOM_RMM_URL,
                        }
                        for p in pts
                    ]
            except Exception as exc:
                logger.warning("BOM RMM fetch failed (%s), falling back to NOAA PSL ROMI", exc)

            resp = requests.get(PSL_ROMI_URL, timeout=20)
            resp.raise_for_status()
            pts = self.parse_romi_text(
                resp.text,
                target_date=None,
                history_days=180,
                amplitude_threshold=self.amplitude_threshold,
            )
            return [
                {
                    "date": p.date,
                    "component_1": p.component_1,
                    "component_2": p.component_2,
                    "raw_pc1": p.raw_pc1,
                    "raw_pc2": p.raw_pc2,
                    "amplitude": p.amplitude,
                    "phase": p.phase,
                    "active": p.active,
                    "source_name": "NOAA PSL",
                    "product": "Real-time OLR MJO Index (ROMI)",
                    "url": PSL_ROMI_URL,
                }
                for p in pts
            ]

        res = weather_cache_fetch(
            cache_key="bom_mjo_rmm",
            source_url=BOM_RMM_URL,
            fetcher=_fetch,
            fresh_hours=12.0,
            max_stale_hours=168.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None
        history: List[MJODailyPoint] = []
        src_name = "Australian BOM"
        prod_name = "Real-time Multivariate MJO (RMM)"
        src_url = BOM_RMM_URL
        if res.data:
            first_item = res.data[0]
            src_name = str(first_item.get("source_name") or src_name)
            prod_name = str(first_item.get("product") or prod_name)
            src_url = str(first_item.get("url") or src_url)
            for item in res.data:
                if cutoff_str and item["date"] > cutoff_str:
                    continue
                history.append(
                    MJODailyPoint(
                        date=item["date"],
                        component_1=float(item["component_1"]),
                        component_2=float(item["component_2"]),
                        raw_pc1=float(item["raw_pc1"]),
                        raw_pc2=float(item["raw_pc2"]),
                        amplitude=float(item["amplitude"]),
                        phase=int(item["phase"]),
                        active=bool(item["active"]),
                    )
                )
            if self.history_days > 0 and len(history) > self.history_days:
                history = history[-self.history_days:]

        prov = SourceProvenance(
            source_name=src_name,
            product=prod_name,
            url=src_url,
            retrieved_at=res.fetched_at,
            valid_through=history[-1].date if history else None,
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=bool(history),
            error=res.error if not history else None,
        )

        return MJOBundle(
            index_name="RMM (BOM)" if "BOM" in src_name else "ROMI (CPC OLR)",
            amplitude_threshold=self.amplitude_threshold,
            history=history,
            provenance=prov,
        )

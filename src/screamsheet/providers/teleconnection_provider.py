"""NOAA Climate Prediction Center (CPC) Daily Teleconnections Provider (AO, NAO, PNA).

Authoritative Sources:
  - CDAS Observations (1950-present):
      - AO (1000 hPa): https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv
      - NAO (500 hPa): https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv
      - PNA (500 hPa): https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv
  - GEFS 31-Member Ensemble Forecasts (0-15 day leads):
      - AO:  https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.gefs.z1000.120days.csv
      - NAO: https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.gefs.z500.120days.csv
      - PNA: https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.gefs.z500.120days.csv
  - GFS Deterministic Forecasts (optional comparison):
      - AO:  https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.gfs.z1000.120days.csv
      - NAO: https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.gfs.z500.120days.csv
      - PNA: https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.gfs.z500.120days.csv
"""
from __future__ import annotations

import csv
import io
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import (
    SourceProvenance,
    TeleconnectionDailyObs,
    TeleconnectionForecastDay,
    TeleconnectionIndexBundle,
)

logger = logging.getLogger(__name__)

CPC_CWLINKS_BASE = "https://ftp.cpc.ncep.noaa.gov/cwlinks"

TELECONNECTION_SPECS: Dict[str, Dict[str, str]] = {
    "AO": {
        "level": "1000 hPa",
        "cdas_file": "norm.daily.ao.cdas.z1000.19500101_current.csv",
        "gefs_file": "norm.daily.ao.gefs.z1000.120days.csv",
        "gfs_file": "norm.daily.ao.gfs.z1000.120days.csv",
    },
    "NAO": {
        "level": "500 hPa",
        "cdas_file": "norm.daily.nao.cdas.z500.19500101_current.csv",
        "gefs_file": "norm.daily.nao.gefs.z500.120days.csv",
        "gfs_file": "norm.daily.nao.gfs.z500.120days.csv",
    },
    "PNA": {
        "level": "500 hPa",
        "cdas_file": "norm.daily.pna.cdas.z500.19500101_current.csv",
        "gefs_file": "norm.daily.pna.gefs.z500.120days.csv",
        "gfs_file": "norm.daily.pna.gfs.z500.120days.csv",
    },
}


def _percentile(sorted_vals: List[float], q: float) -> float:
    """Compute linear-interpolated percentile for a pre-sorted list (0 <= q <= 1)."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


class TeleconnectionProvider(DataProvider):
    """Fetches and normalizes NOAA CPC daily AO, NAO, and PNA observations and GEFS forecasts."""

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
    def parse_cdas_csv(
        csv_text: str,
        target_date: Optional[datetime] = None,
        history_days: int = 60,
    ) -> List[TeleconnectionDailyObs]:
        """Parse a CPC CDAS daily teleconnection CSV into sorted observations."""
        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None
        rows: List[TeleconnectionDailyObs] = []

        # Only need the tail of a 75-year file if it's huge, but keep enough lines for history_days
        lines = csv_text.strip().splitlines()
        if not lines:
            return []

        header = lines[0]
        tail_lines = [header] + lines[-max(history_days * 4, 400):] if len(lines) > 500 else lines
        reader = csv.DictReader(io.StringIO("\n".join(tail_lines)))
        for row in reader:
            try:
                y = int(row["year"])
                m = int(row["month"])
                d = int(row["day"])
                date_str = f"{y:04d}-{m:02d}-{d:02d}"
                if cutoff_str and date_str > cutoff_str:
                    continue
                # Find the index value column (e.g. ao_index_cdas, nao_index_cdas, pna_index_cdas)
                val_str = None
                for k, v in row.items():
                    if k not in ("year", "month", "day") and v is not None:
                        val_str = v.strip()
                        break
                if not val_str or val_str in ("", "NaN", "-999", "-99.9"):
                    continue
                val = float(val_str)
                if math.isnan(val) or abs(val) > 50.0:
                    continue
                rows.append(TeleconnectionDailyObs(date=date_str, value=val))
            except (KeyError, ValueError, TypeError):
                continue

        rows.sort(key=lambda x: x.date)
        if history_days > 0 and len(rows) > history_days:
            rows = rows[-history_days:]
        return rows

    @staticmethod
    def parse_gefs_csv(
        gefs_csv_text: str,
        gfs_csv_text: Optional[str] = None,
        target_date: Optional[datetime] = None,
        forecast_days: int = 14,
    ) -> List[TeleconnectionForecastDay]:
        """Parse a CPC GEFS 120-day ensemble CSV for the latest initialization <= target_date.

        Preserves all 31 ensemble members per lead day and computes mean, min, max,
        IQR (25th–75th percentile), and standard deviation.
        """
        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None

        # Group by init_date -> lead_days -> (valid_date, list of member values)
        by_init: Dict[str, Dict[int, Tuple[str, List[float]]]] = defaultdict(dict)
        reader = csv.DictReader(io.StringIO(gefs_csv_text.strip()))
        for row in reader:
            try:
                lead = int(row["lead"])
                init_time = str(row["time"]).strip()
                valid_time = str(row["valid_time"]).strip()
                if cutoff_str and init_time > cutoff_str:
                    continue
                val_str = None
                for k, v in row.items():
                    if k not in ("lead", "member", "time", "valid_time") and v is not None:
                        val_str = v.strip()
                        break
                if not val_str or val_str in ("", "NaN"):
                    continue
                val = float(val_str)
                if math.isnan(val) or abs(val) > 50.0:
                    continue
                if lead not in by_init[init_time]:
                    by_init[init_time][lead] = (valid_time, [])
                by_init[init_time][lead][1].append(val)
            except (KeyError, ValueError, TypeError):
                continue

        if not by_init:
            return []

        latest_init = max(by_init.keys())
        leads_map = by_init[latest_init]

        # Optional deterministic GFS lookup for the same initialization date
        gfs_by_lead: Dict[int, float] = {}
        if gfs_csv_text:
            gfs_reader = csv.DictReader(io.StringIO(gfs_csv_text.strip()))
            for row in gfs_reader:
                try:
                    if str(row.get("time", "")).strip() != latest_init:
                        continue
                    lead = int(row["lead"])
                    for k, v in row.items():
                        if k not in ("lead", "time", "valid_time") and v is not None:
                            val = float(v.strip())
                            if not math.isnan(val) and abs(val) <= 50.0:
                                gfs_by_lead[lead] = val
                            break
                except (KeyError, ValueError, TypeError):
                    continue

        results: List[TeleconnectionForecastDay] = []
        for lead in sorted(leads_map.keys()):
            if lead < 1 or (forecast_days > 0 and lead > forecast_days):
                continue
            valid_date, members = leads_map[lead]
            if not members:
                continue
            s_members = sorted(members)
            n = len(s_members)
            mean_val = sum(s_members) / n
            variance = sum((x - mean_val) ** 2 for x in s_members) / n
            std_val = math.sqrt(variance)
            results.append(
                TeleconnectionForecastDay(
                    valid_date=valid_date,
                    lead_days=lead,
                    init_date=latest_init,
                    ensemble_mean=mean_val,
                    ensemble_min=s_members[0],
                    ensemble_max=s_members[-1],
                    ensemble_p25=_percentile(s_members, 0.25),
                    ensemble_p75=_percentile(s_members, 0.75),
                    ensemble_std=std_val,
                    member_count=n,
                    members=s_members,
                    deterministic_gfs=gfs_by_lead.get(lead),
                )
            )
        return results

    def get_index_bundle(
        self,
        index_name: str,
        target_date: Optional[datetime] = None,
    ) -> TeleconnectionIndexBundle:
        """Fetch CDAS observations and GEFS forecasts for a single index (AO, NAO, or PNA)."""
        key = index_name.upper()
        spec = TELECONNECTION_SPECS[key]
        cdas_url = f"{CPC_CWLINKS_BASE}/{spec['cdas_file']}"
        gefs_url = f"{CPC_CWLINKS_BASE}/{spec['gefs_file']}"

        def _fetch_cdas() -> List[Dict[str, Any]]:
            resp = requests.get(cdas_url, timeout=20)
            resp.raise_for_status()
            # Keep last 400 lines so we don't store 28,000 rows in SQLite cache
            lines = resp.text.strip().splitlines()
            trimmed = "\n".join([lines[0]] + lines[-400:]) if len(lines) > 405 else resp.text
            obs_list = self.parse_cdas_csv(trimmed, target_date=None, history_days=365)
            return [{"date": o.date, "value": o.value} for o in obs_list]

        cdas_res = weather_cache_fetch(
            cache_key=f"cpc_cdas_{key.lower()}",
            source_url=cdas_url,
            fetcher=_fetch_cdas,
            fresh_hours=6.0,
            max_stale_hours=168.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        obs: List[TeleconnectionDailyObs] = []
        cutoff_str = target_date.strftime("%Y-%m-%d") if target_date else None
        if cdas_res.data:
            for item in cdas_res.data:
                if cutoff_str and item["date"] > cutoff_str:
                    continue
                obs.append(TeleconnectionDailyObs(date=item["date"], value=float(item["value"])))
            if self.history_days > 0 and len(obs) > self.history_days:
                obs = obs[-self.history_days:]

        obs_prov = SourceProvenance(
            source_name="NOAA CPC",
            product=f"{key} CDAS ({spec['level']})",
            url=cdas_url,
            retrieved_at=cdas_res.fetched_at,
            valid_through=obs[-1].date if obs else None,
            from_cache=cdas_res.from_cache,
            is_stale=cdas_res.is_stale,
            age_hours=cdas_res.age_hours,
            available=bool(obs),
            error=cdas_res.error if not obs else None,
        )

        def _fetch_gefs() -> List[Dict[str, Any]]:
            resp = requests.get(gefs_url, timeout=25)
            resp.raise_for_status()
            fcst_list = self.parse_gefs_csv(
                resp.text,
                target_date=target_date,
                forecast_days=max(self.forecast_days, 15),
            )
            return [
                {
                    "valid_date": f.valid_date,
                    "lead_days": f.lead_days,
                    "init_date": f.init_date,
                    "ensemble_mean": f.ensemble_mean,
                    "ensemble_min": f.ensemble_min,
                    "ensemble_max": f.ensemble_max,
                    "ensemble_p25": f.ensemble_p25,
                    "ensemble_p75": f.ensemble_p75,
                    "ensemble_std": f.ensemble_std,
                    "member_count": f.member_count,
                    "members": f.members,
                }
                for f in fcst_list
            ]

        gefs_res = weather_cache_fetch(
            cache_key=f"cpc_gefs_{key.lower()}_{cutoff_str or 'latest'}",
            source_url=gefs_url,
            fetcher=_fetch_gefs,
            fresh_hours=6.0,
            max_stale_hours=168.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        fcsts: List[TeleconnectionForecastDay] = []
        if gefs_res.data:
            for item in gefs_res.data:
                if self.forecast_days > 0 and int(item["lead_days"]) > self.forecast_days:
                    continue
                fcsts.append(
                    TeleconnectionForecastDay(
                        valid_date=item["valid_date"],
                        lead_days=int(item["lead_days"]),
                        init_date=item["init_date"],
                        ensemble_mean=float(item["ensemble_mean"]),
                        ensemble_min=float(item["ensemble_min"]),
                        ensemble_max=float(item["ensemble_max"]),
                        ensemble_p25=float(item["ensemble_p25"]),
                        ensemble_p75=float(item["ensemble_p75"]),
                        ensemble_std=float(item["ensemble_std"]),
                        member_count=int(item["member_count"]),
                        members=[float(m) for m in item.get("members", [])],
                    )
                )

        fcst_prov = SourceProvenance(
            source_name="NOAA CPC / NCEP GEFS",
            product=f"{key} GEFS 31-Member Ensemble ({spec['level']})",
            url=gefs_url,
            retrieved_at=gefs_res.fetched_at,
            valid_through=fcsts[-1].valid_date if fcsts else None,
            forecast_init=f"{fcsts[0].init_date} 00Z" if fcsts else None,
            from_cache=gefs_res.from_cache,
            is_stale=gefs_res.is_stale,
            age_hours=gefs_res.age_hours,
            available=bool(fcsts),
            error=gefs_res.error if not fcsts else None,
        )

        return TeleconnectionIndexBundle(
            index_name=key,
            level_label=spec["level"],
            observations=obs,
            forecasts=fcsts,
            obs_provenance=obs_prov,
            fcst_provenance=fcst_prov,
        )

    def get_all_teleconnections(
        self,
        target_date: Optional[datetime] = None,
    ) -> Dict[str, TeleconnectionIndexBundle]:
        """Fetch AO, NAO, and PNA bundles."""
        out: Dict[str, TeleconnectionIndexBundle] = {}
        for idx_name in ("AO", "NAO", "PNA"):
            try:
                out[idx_name] = self.get_index_bundle(idx_name, target_date=target_date)
            except Exception as exc:
                logger.error("TeleconnectionProvider failed for %s: %s", idx_name, exc)
        return out

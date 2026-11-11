"""Local Teleconnection & MJO Historical Effects Provider (Consumer of climate.db).

Reads precomputed local teleconnection and MJO historical lag effects from the
Teleconnection Climatology SQLite database (``~/database/climate.db``) built by
the ``teleconnections`` project.

Boundary Contract (per Issue #147 / teleconnections#1):
  - Screamsheet never calculates ERA5 climatology or historical statistical composites.
  - Screamsheet converts current and forecast teleconnection indices (AO, NAO, PNA,
    NINO34, MJO) into their canonical states/phases and queries ``location``,
    ``teleconnection_effect``, and ``mjo_effect`` read-only.
  - Only exception: if a requested location does not exist or its ``bootstrap_status``
    is not ``complete``, Screamsheet invokes ``scripts/bootstrap_location.py`` in the
    ``teleconnections`` project as a subprocess, waits for exit code 0, and then
    queries SQLite.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import DataProvider
from ..weather_patterns.models import (
    ENSOBundle,
    LocalLocationBundle,
    MJOBundle,
    SourceProvenance,
    TeleconnectionIndexBundle,
)

logger = logging.getLogger(__name__)

# Canonical mapping from calendar month (1..12) to its centered 3-month season in climate.db
SEASON_FOR_MONTH: Dict[int, str] = {
    1: "DJF",
    2: "JFM",
    3: "FMA",
    4: "MAM",
    5: "AMJ",
    6: "MJJ",
    7: "JJA",
    8: "JAS",
    9: "ASO",
    10: "SON",
    11: "OND",
    12: "NDJ",
}


def slugify_location_id(name: str) -> str:
    """Convert a display name like 'Bryn Mawr, PA' into 'bryn_mawr_pa'."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "location"


def classify_teleconnection_state(code: str, value: float) -> str:
    """Map a numeric teleconnection index value to its canonical climate.db state string."""
    code_u = code.upper().strip()
    if code_u == "NINO34":
        if value <= -1.5:
            return "strong_la_nina"
        if value <= -0.5:
            return "la_nina"
        if value < 0.5:
            return "neutral"
        if value < 1.5:
            return "el_nino"
        return "strong_el_nino"

    # AO, NAO, PNA
    if value <= -1.5:
        return "strong_negative"
    if value <= -0.5:
        return "negative"
    if value < 0.5:
        return "neutral"
    if value < 1.5:
        return "positive"
    return "strong_positive"


def get_climate_db_path(explicit_path: Optional[str | Path] = None) -> Path:
    """Resolve the path to the teleconnection climatology SQLite database (climate.db).

    Resolution order (matching get_db_path() for screamsheet.db):
      1. ``TELECLIM_DB`` environment variable (if set)
      2. ``explicit_path`` from config (if non-empty and not ``__DB_PATH__``)
      3. Platform default: ``~/database/climate.db`` (Linux/macOS) or ``C:/database/climate.db`` (Windows)
    """
    env_val = os.environ.get("TELECLIM_DB")
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser()

    if explicit_path:
        s = str(explicit_path).strip()
        if s and s != "__DB_PATH__":
            return Path(s).expanduser()

    if sys.platform.startswith("win"):
        return Path("C:/database/climate.db")
    return Path.home() / "database" / "climate.db"


def get_teleconnections_dir(explicit_dir: Optional[str | Path] = None) -> Path:
    """Resolve the path to the teleconnections builder repository for location bootstrapping.

    Resolution order:
      1. ``TELECONNECTIONS_DIR`` environment variable (if set)
      2. ``explicit_dir`` from config (if non-empty)
      3. ``~/Code/teleconnections_live`` (if deployed via release symlink)
      4. ``~/Code/teleconnections``
    """
    env_val = os.environ.get("TELECONNECTIONS_DIR")
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser()

    if explicit_dir:
        s = str(explicit_dir).strip()
        if s:
            return Path(s).expanduser()

    live_candidate = Path.home() / "Code" / "teleconnections_live"
    if live_candidate.exists():
        return live_candidate
    return Path.home() / "Code" / "teleconnections"


def _format_lag_effects(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Group variable rows by lag window (0-5, 6-10, 11-15, 16-20) into compact dicts."""
    by_lag: Dict[tuple[int, int], Dict[str, Any]] = {}
    for r in rows:
        l_start = int(r["lag_start_days"])
        l_end = int(r["lag_end_days"])
        key = (l_start, l_end)
        entry = by_lag.setdefault(
            key,
            {
                "lag_days": f"{l_start}-{l_end}",
                "lag_start_days": l_start,
                "lag_end_days": l_end,
                "sample_count": int(r["sample_count"]),
            },
        )
        var_name = str(r["variable"])
        mean_eff = float(r["mean_effect"]) if r["mean_effect"] is not None else None
        med_eff = float(r["median_effect"]) if r["median_effect"] is not None else None
        p_val = float(r["p_value"]) if r["p_value"] is not None else None
        conf = str(r["confidence"])

        if var_name == "tmean_anomaly_c":
            entry["temp_anomaly_mean_c"] = round(mean_eff, 2) if mean_eff is not None else None
            entry["temp_anomaly_mean_f"] = round(mean_eff * 1.8, 2) if mean_eff is not None else None
            entry["temp_anomaly_median_c"] = round(med_eff, 2) if med_eff is not None else None
            entry["temp_p_value"] = round(p_val, 4) if p_val is not None else None
            entry["temp_confidence"] = conf
        elif var_name == "precip_mm":
            entry["precip_anomaly_mean_mm_day"] = round(mean_eff, 2) if mean_eff is not None else None
            entry["precip_anomaly_median_mm_day"] = round(med_eff, 2) if med_eff is not None else None
            entry["precip_p_value"] = round(p_val, 4) if p_val is not None else None
            entry["precip_confidence"] = conf

    return [by_lag[k] for k in sorted(by_lag.keys())]


class TeleconnectionEffectsProvider(DataProvider):
    """Queries precomputed local teleconnection & MJO effects from climate.db and auto-bootstraps missing locations."""

    def __init__(
        self,
        climate_db_path: Optional[str | Path] = None,
        teleconnections_dir: Optional[str | Path] = None,
        auto_bootstrap: bool = True,
        bootstrap_timeout_sec: int = 180,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.climate_db_path = get_climate_db_path(climate_db_path)
        self.teleconnections_dir = get_teleconnections_dir(teleconnections_dir)
        self.auto_bootstrap = auto_bootstrap
        self.bootstrap_timeout_sec = bootstrap_timeout_sec

    def _connect_readonly_or_rw(self) -> Optional[sqlite3.Connection]:
        if not self.climate_db_path.exists() or self.climate_db_path.stat().st_size == 0:
            return None
        try:
            conn = sqlite3.connect(
                f"file:{self.climate_db_path}?mode=ro",
                uri=True,
                timeout=15.0,
            )
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            logger.warning(
                "Unable to open teleconnection climatology DB at %s: %s",
                self.climate_db_path,
                exc,
            )
            return None

    def _resolve_bootstrapped_location_id(
        self,
        location_id: str,
        lat: float,
        lon: float,
        tolerance_deg: float = 0.15,
    ) -> Optional[str]:
        """Return matching location_id if bootstrapped by exact ID or nearby coordinates."""
        conn = self._connect_readonly_or_rw()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT id, bootstrap_status FROM location WHERE id = ?;",
                (location_id,),
            ).fetchone()
            if row and row["bootstrap_status"] == "complete":
                return str(row["id"])

            # Check if an already-bootstrapped location exists within tolerance_deg
            rows = conn.execute(
                """
                SELECT id, latitude, longitude
                FROM location
                WHERE bootstrap_status = 'complete'
                  AND ABS(latitude - ?) <= ?
                  AND ABS(longitude - ?) <= ?
                ORDER BY (latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?) ASC
                LIMIT 1;
                """,
                (lat, tolerance_deg, lon, tolerance_deg, lat, lat, lon, lon),
            ).fetchone()
            if rows:
                return str(rows["id"])
            return None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def _trigger_location_bootstrap(
        self,
        location_id: str,
        name: str,
        lat: float,
        lon: float,
    ) -> bool:
        """Invoke teleconnections/scripts/bootstrap_location.py as a subprocess and wait for exit code 0."""
        script_path = self.teleconnections_dir / "scripts" / "bootstrap_location.py"
        if not script_path.exists():
            logger.warning(
                "Teleconnections bootstrap script not found at %s; skipping auto-bootstrap for %s",
                script_path,
                location_id,
            )
            return False

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/bootstrap_location.py",
            "--id",
            location_id,
            "--name",
            name,
            "--lat",
            str(lat),
            "--lon",
            str(lon),
            "--db",
            str(self.climate_db_path),
        ]
        # Prefer --no-sync if .venv already exists in teleconnections_dir (avoids network checks)
        if (self.teleconnections_dir / ".venv").exists():
            cmd = [
                "uv",
                "run",
                "--no-sync",
                "python",
                "scripts/bootstrap_location.py",
                "--id",
                location_id,
                "--name",
                name,
                "--lat",
                str(lat),
                "--lon",
                str(lon),
                "--db",
                str(self.climate_db_path),
            ]

        logger.info("Bootstrapping missing location '%s' (%s) via %s", location_id, name, " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.teleconnections_dir),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.bootstrap_timeout_sec,
            )
            if proc.returncode != 0:
                logger.error(
                    "bootstrap_location.py failed for %s (exit %d): %s",
                    location_id,
                    proc.returncode,
                    (proc.stderr or proc.stdout or "").strip(),
                )
                return False
            return True
        except Exception as exc:
            logger.error("Subprocess bootstrap_location.py raised an error for %s: %s", location_id, exc)
            return False

    def enrich_location_teleconnection_effects(
        self,
        loc: LocalLocationBundle,
        teleconnections: Dict[str, TeleconnectionIndexBundle],
        mjo: Optional[MJOBundle],
        enso: Optional[ENSOBundle],
        target_date: Optional[datetime] = None,
    ) -> LocalLocationBundle:
        """Query climate.db for historical local teleconnection & MJO effects and attach to ``loc``."""
        ref_dt = target_date or datetime.now()
        season = SEASON_FOR_MONTH.get(ref_dt.month, "DJF")
        requested_id = slugify_location_id(loc.name)
        now_iso = datetime.now(timezone.utc).isoformat()

        if not self.climate_db_path.exists() or self.climate_db_path.stat().st_size == 0:
            logger.warning(
                "Teleconnection climatology DB not found at %s; continuing without historical local teleconnection effects for '%s'.",
                self.climate_db_path,
                loc.name,
            )
            loc.teleconnection_effects = None
            loc.teleconnection_effects_provenance = SourceProvenance(
                source_name="Teleconnection Climatology DB",
                product=f"ERA5 Local Teleconnection & MJO Effects ({requested_id})",
                url=str(self.climate_db_path),
                retrieved_at=now_iso,
                available=False,
                error=f"Climate database not found at {self.climate_db_path}",
            )
            return loc

        resolved_id = self._resolve_bootstrapped_location_id(requested_id, loc.lat, loc.lon)
        if not resolved_id and self.auto_bootstrap:
            self._trigger_location_bootstrap(
                location_id=requested_id,
                name=loc.name,
                lat=loc.lat,
                lon=loc.lon,
            )
            resolved_id = self._resolve_bootstrapped_location_id(requested_id, loc.lat, loc.lon)

        conn = self._connect_readonly_or_rw()
        if conn is None or not resolved_id:
            if conn is not None:
                conn.close()
            loc.teleconnection_effects = None
            loc.teleconnection_effects_provenance = SourceProvenance(
                source_name="Teleconnection Climatology DB",
                product=f"ERA5 Local Teleconnection & MJO Effects ({requested_id})",
                url=str(self.climate_db_path),
                retrieved_at=now_iso,
                available=False,
                error=f"Location '{requested_id}' not available in {self.climate_db_path}",
            )
            return loc

        loc_id = resolved_id

        try:
            loc_meta = conn.execute(
                "SELECT * FROM location WHERE id = ?;",
                (loc_id,),
            ).fetchone()

            index_effects: Dict[str, Any] = {}

            # 1. Daily numeric teleconnections: AO, NAO, PNA (current state + Day-7 forecast state)
            for code in ("AO", "NAO", "PNA"):
                tb = teleconnections.get(code)
                if not tb or not tb.observations:
                    continue
                cur_val = float(tb.observations[-1].value)
                cur_state = classify_teleconnection_state(code, cur_val)

                cur_rows = conn.execute(
                    """
                    SELECT *
                    FROM teleconnection_effect
                    WHERE location_id = ?
                      AND season = ?
                      AND code = ?
                      AND state = ?
                    ORDER BY lag_start_days ASC, variable ASC;
                    """,
                    (loc_id, season, code, cur_state),
                ).fetchall()

                code_entry: Dict[str, Any] = {
                    "current_value": round(cur_val, 2),
                    "current_state": cur_state,
                    "current_state_effects": _format_lag_effects(cur_rows),
                }

                if tb.forecasts:
                    day7_fc = next(
                        (f for f in tb.forecasts if f.lead_days == 7),
                        tb.forecasts[min(6, len(tb.forecasts) - 1)],
                    )
                    fc_val = float(day7_fc.ensemble_mean)
                    fc_state = classify_teleconnection_state(code, fc_val)
                    code_entry["day7_forecast_value"] = round(fc_val, 2)
                    code_entry["day7_forecast_state"] = fc_state
                    if fc_state != cur_state:
                        fc_rows = conn.execute(
                            """
                            SELECT *
                            FROM teleconnection_effect
                            WHERE location_id = ?
                              AND season = ?
                              AND code = ?
                              AND state = ?
                            ORDER BY lag_start_days ASC, variable ASC;
                            """,
                            (loc_id, season, code, fc_state),
                        ).fetchall()
                        code_entry["day7_forecast_state_effects"] = _format_lag_effects(fc_rows)

                index_effects[code] = code_entry

            # 2. Monthly background ENSO (NINO34)
            if enso and enso.latest_nino34 is not None:
                nino_val = float(enso.latest_nino34)
                nino_state = classify_teleconnection_state("NINO34", nino_val)
                nino_rows = conn.execute(
                    """
                    SELECT *
                    FROM teleconnection_effect
                    WHERE location_id = ?
                      AND season = ?
                      AND code = 'NINO34'
                      AND state = ?
                    ORDER BY lag_start_days ASC, variable ASC;
                    """,
                    (loc_id, season, nino_state),
                ).fetchall()
                index_effects["NINO34"] = {
                    "current_value_c": round(nino_val, 2),
                    "current_state": nino_state,
                    "current_state_effects": _format_lag_effects(nino_rows),
                }

            # 3. MJO phase effects (queried when MJO history is available)
            mjo_effect_block: Optional[Dict[str, Any]] = None
            if mjo and mjo.history:
                latest_mjo = mjo.history[-1]
                mjo_rows = conn.execute(
                    """
                    SELECT *
                    FROM mjo_effect
                    WHERE location_id = ?
                      AND season = ?
                      AND phase = ?
                    ORDER BY lag_start_days ASC, variable ASC;
                    """,
                    (loc_id, season, int(latest_mjo.phase)),
                ).fetchall()
                mjo_effect_block = {
                    "phase": int(latest_mjo.phase),
                    "amplitude": round(float(latest_mjo.amplitude), 2),
                    "active": bool(latest_mjo.active),
                    "note": (
                        "Historical MJO composites are derived from active MJO episodes (amplitude >= 1.0)."
                        if latest_mjo.active
                        else "MJO is currently weak/inactive (< 1.0); historical phase effects shown for reference only."
                    ),
                    "phase_effects": _format_lag_effects(mjo_rows),
                }

            loc.teleconnection_effects = {
                "location_id": loc_id,
                "location_name": loc.name,
                "season": season,
                "era5_grid_point": {
                    "latitude": float(loc_meta["era5_latitude"]) if loc_meta and loc_meta["era5_latitude"] is not None else None,
                    "longitude": float(loc_meta["era5_longitude"]) if loc_meta and loc_meta["era5_longitude"] is not None else None,
                },
                "history_period": {
                    "start": loc_meta["history_start"] if loc_meta else None,
                    "end": loc_meta["history_end"] if loc_meta else None,
                },
                "teleconnections": index_effects,
                "mjo": mjo_effect_block,
            }

            loc.teleconnection_effects_provenance = SourceProvenance(
                source_name="Teleconnection Climatology DB (ERA5)",
                product=f"Local Lagged Composites ({loc_id}, season {season})",
                url=str(self.climate_db_path),
                retrieved_at=now_iso,
                valid_through=loc_meta["history_end"] if loc_meta else None,
                from_cache=True,
                is_stale=False,
                age_hours=0.0,
                available=bool(index_effects or mjo_effect_block),
            )
        except Exception as exc:
            logger.warning(
                "Failed querying teleconnection climatology DB at %s for '%s': %s; falling back gracefully.",
                self.climate_db_path,
                loc.name,
                exc,
            )
            loc.teleconnection_effects = None
            loc.teleconnection_effects_provenance = SourceProvenance(
                source_name="Teleconnection Climatology DB",
                product=f"ERA5 Local Teleconnection & MJO Effects ({requested_id})",
                url=str(self.climate_db_path),
                retrieved_at=now_iso,
                available=False,
                error=str(exc),
            )
        finally:
            conn.close()

        return loc

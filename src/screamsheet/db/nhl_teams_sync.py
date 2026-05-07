"""Full sync of NHL team data into the local SQLite cache.

Fetches all 32 teams from the NHL API standings endpoint and upserts every
team record.  One API call covers all teams, so this is fast and can be run
frequently.

Usage:
    python -m screamsheet.db.nhl_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_teams_sync

Windows (run manually or add to Task Scheduler):
    python -m screamsheet.db.nhl_teams_sync
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import requests

from .nhl_teams_db import init_db, upsert_teams
from ._nhl_db_shared import get_db_path
from .team_lookup import upsert_team

logger = logging.getLogger(__name__)

_BASE_URL = "https://api-web.nhle.com/v1"


def fetch_teams_from_standings() -> List[dict]:
    """Fetch all 32 NHL teams from the standings endpoint.

    The ``/standings/now`` response always includes every franchise regardless
    of whether games are currently scheduled (handles off-season and playoffs
    correctly).  Each entry has the canonical numeric ``teamId``, abbreviation,
    common name, and place name — everything needed for the teams table.

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    url = f"{_BASE_URL}/standings/now"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    teams: list = []
    for t in data.get("standings", []):
        team_id = t.get("teamId")
        abbrev  = t.get("teamAbbrev", {}).get("default", "")
        if not team_id or not abbrev:
            continue
        teams.append({
            "team_id":        team_id,
            "team":           abbrev,
            "team_full_name": t.get("teamCommonName", {}).get("default", ""),
            "city":           t.get("placeName", {}).get("default", ""),
            "raw_json":       json.dumps(t),
        })

    return teams


def _sync_nhl_lookup_table(teams: List[dict], db_path: Optional[Path]) -> None:
    """Populate the unified nhl_teams lookup table from fetched team data."""
    now = datetime.now(timezone.utc).isoformat()
    for t in teams:
        team_id = t.get("team_id")
        city = t.get("city", "")
        nickname = t.get("team_full_name", "")
        abbrev = t.get("team", "")
        if not team_id:
            continue
        full_name = f"{city} {nickname}".strip()
        upsert_team("nhl", team_id, full_name, abbrev, now, db_path)


def full_sync_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all NHL teams and upsert them into the local cache.

    Also populates the unified ``nhl_teams`` lookup table used by subscriber
    config resolution.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db(db_path)
    teams = fetch_teams_from_standings()
    logger.info("full_sync_teams: fetched %d teams", len(teams))
    count = upsert_teams(teams, db_path)
    _sync_nhl_lookup_table(teams, db_path)
    logger.info("full_sync_teams: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync_teams()
    print(f"Sync complete: {rows} teams upserted to {get_db_path()}")

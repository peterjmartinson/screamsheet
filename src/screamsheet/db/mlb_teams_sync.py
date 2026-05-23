"""Full sync of MLB team data into the local SQLite cache.

Fetches all active MLB teams from the MLB Stats API and upserts every
team record into the mlb_teams table.

Usage:
    uv run python -m screamsheet.db.mlb_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && uv run python -m screamsheet.db.mlb_teams_sync
"""

import logging
from pathlib import Path
from typing import List, Optional

import requests

from ._nhl_db_shared import get_db_path
from .team_lookup_db import init_db, upsert_teams

logger = logging.getLogger(__name__)

_MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"


def fetch_teams() -> List[dict]:
    """Fetch all active MLB teams from the MLB Stats API.

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    response = requests.get(_MLB_TEAMS_URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    teams = []
    for team in data.get("teams", []):
        team_id = team.get("id")
        full_name = team.get("name", "")
        abbrev = team.get("abbreviation", "")
        if team_id and full_name:
            teams.append({
                "team_id":  team_id,
                "full_name": full_name,
                "abbrev":   abbrev,
            })

    return teams


def full_sync(db_path: Optional[Path] = None) -> int:
    """Fetch all MLB teams and upsert them into the local cache.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db("mlb", db_path)
    teams = fetch_teams()
    logger.info("mlb full_sync: fetched %d teams", len(teams))
    count = upsert_teams("mlb", teams, db_path)
    logger.info("mlb full_sync: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync()
    print(f"MLB sync complete: {rows} teams upserted to {get_db_path()}")

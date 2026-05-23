"""Full sync of NFL team data into the local SQLite cache.

Fetches all NFL teams from the ESPN API and upserts every team record
into the nfl_teams table.

Usage:
    uv run python -m screamsheet.db.nfl_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && uv run python -m screamsheet.db.nfl_teams_sync
"""

import logging
from pathlib import Path
from typing import List, Optional

import requests

from ._nhl_db_shared import get_db_path
from .team_lookup_db import init_db, upsert_teams

logger = logging.getLogger(__name__)

_ESPN_NFL_TEAMS_URL = (
    "http://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
)


def fetch_teams() -> List[dict]:
    """Fetch all NFL teams from the ESPN API.

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    response = requests.get(_ESPN_NFL_TEAMS_URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    try:
        teams_list = (
            data.get("sports", [])[0]
            .get("leagues", [])[0]
            .get("teams", [])
        )
    except IndexError:
        logger.warning("nfl fetch_teams: unexpected ESPN response structure")
        return []

    teams = []
    for entry in teams_list:
        team_info = entry.get("team", {})
        try:
            team_id = int(team_info.get("id", 0))
        except (TypeError, ValueError):
            continue
        full_name = team_info.get("displayName", "")
        abbrev = team_info.get("abbreviation", "")
        if team_id and full_name:
            teams.append({
                "team_id":  team_id,
                "full_name": full_name,
                "abbrev":   abbrev,
            })

    return teams


def full_sync(db_path: Optional[Path] = None) -> int:
    """Fetch all NFL teams and upsert them into the local cache.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db("nfl", db_path)
    teams = fetch_teams()
    logger.info("nfl full_sync: fetched %d teams", len(teams))
    count = upsert_teams("nfl", teams, db_path)
    logger.info("nfl full_sync: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync()
    print(f"NFL sync complete: {rows} teams upserted to {get_db_path()}")

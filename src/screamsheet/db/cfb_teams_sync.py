"""Full sync of College Football team data into the local SQLite cache.

Fetches all FBS/FCS college football teams from the ESPN API and upserts
every team record into the cfb_teams table.

Usage:
    uv run python -m screamsheet.db.cfb_teams_sync
"""

import logging
from pathlib import Path
from typing import List, Optional

import requests

from ._nhl_db_shared import get_db_path
from .team_lookup_db import init_db, upsert_teams

logger = logging.getLogger(__name__)

_ESPN_CFB_TEAMS_URL = (
    "http://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=500"
)


def fetch_teams() -> List[dict]:
    """Fetch all College Football teams from the ESPN API.

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    response = requests.get(_ESPN_CFB_TEAMS_URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    try:
        teams_list = (
            data.get("sports", [])[0]
            .get("leagues", [])[0]
            .get("teams", [])
        )
    except IndexError:
        logger.warning("cfb fetch_teams: unexpected ESPN response structure")
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
                "team_id": team_id,
                "full_name": full_name,
                "abbrev": abbrev or None,
            })

    return teams


def sync_cfb_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all College Football teams and upsert them into the database.

    Args:
        db_path: Optional path to the SQLite file. Defaults to platform path.

    Returns:
        Number of teams upserted.
    """
    path = db_path or get_db_path()
    init_db("cfb", db_path=path)
    teams = fetch_teams()
    logger.info("Fetched %d college football teams from ESPN API", len(teams))
    count = upsert_teams("cfb", teams, db_path=path)
    logger.info("Successfully synced %d college football teams into %s", count, path)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    synced = sync_cfb_teams()
    print(f"Synced {synced} College Football teams.")

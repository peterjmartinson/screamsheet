"""Full sync of MLB team data into the local SQLite cache.

Fetches all active MLB teams from the MLB Stats API and upserts every
team record into the mlb_teams table and team_aliases table.

Usage:
    uv run python -m screamsheet.db.mlb_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && uv run python -m screamsheet.db.mlb_teams_sync
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from ._nhl_db_shared import get_db_path
from .team_lookup_db import init_db, seed_aliases, upsert_team_aliases, upsert_teams

logger = logging.getLogger(__name__)

_MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"


def fetch_teams_and_aliases() -> Tuple[List[dict], List[dict]]:
    """Fetch all active MLB teams and derived aliases from the MLB Stats API.

    Returns:
        Tuple of (team_dicts, alias_dicts).

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    response = requests.get(_MLB_TEAMS_URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    teams = []
    aliases = []
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

            # Extract auto-aliases from API payload
            aliases.append({"team_id": team_id, "alias": full_name, "alias_type": "name"})
            if abbrev:
                aliases.append({"team_id": team_id, "alias": abbrev, "alias_type": "abbrev"})

            for field, atype in [
                ("teamName", "nickname"),
                ("locationName", "city"),
                ("shortName", "short_name"),
                ("clubName", "nickname"),
                ("franchiseName", "city"),
            ]:
                val = team.get(field)
                if val and str(val).strip():
                    aliases.append({"team_id": team_id, "alias": str(val).strip(), "alias_type": atype})

    return teams, aliases


def full_sync(db_path: Optional[Path] = None) -> int:
    """Fetch all MLB teams and upsert them and their aliases into the local cache.

    Args:
        db_path: Path to the SQLite file. Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db("mlb", db_path)
    # Seed curated aliases first (ensuring feed slugs etc. are present)
    seed_aliases("mlb", db_path)

    teams, aliases = fetch_teams_and_aliases()
    logger.info("mlb full_sync: fetched %d teams", len(teams))
    count = upsert_teams("mlb", teams, db_path)
    upsert_team_aliases("mlb", aliases, db_path)
    logger.info("mlb full_sync: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync()
    print(f"MLB sync complete: {rows} teams upserted to {get_db_path()}")

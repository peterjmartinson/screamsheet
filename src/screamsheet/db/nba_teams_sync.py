"""Full sync of NBA team data into the local SQLite cache.

Fetches all NBA teams from the nba_api static data (no network call needed)
and upserts every team record into the nba_teams table.

Usage:
    uv run python -m screamsheet.db.nba_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && uv run python -m screamsheet.db.nba_teams_sync
"""

import logging
from pathlib import Path
from typing import List, Optional

from ._nhl_db_shared import get_db_path
from .team_lookup_db import init_db, upsert_teams

logger = logging.getLogger(__name__)


def fetch_teams() -> List[dict]:
    """Return all NBA teams from the nba_api static dataset.

    Uses nba_api.stats.static.teams — no network request required.

    Returns:
        List of team dicts ready to pass to upsert_teams().
    """
    from nba_api.stats.static import teams as nba_static

    teams = []
    for t in nba_static.get_teams():
        team_id = t.get("id")
        full_name = t.get("full_name", "")
        abbrev = t.get("abbreviation", "")
        if team_id and full_name:
            teams.append({
                "team_id":  team_id,
                "full_name": full_name,
                "abbrev":   abbrev,
            })

    return teams


def full_sync(db_path: Optional[Path] = None) -> int:
    """Fetch all NBA teams and upsert them into the local cache.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db("nba", db_path)
    teams = fetch_teams()
    logger.info("nba full_sync: fetched %d teams", len(teams))
    count = upsert_teams("nba", teams, db_path)
    logger.info("nba full_sync: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync()
    print(f"NBA sync complete: {rows} teams upserted to {get_db_path()}")

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
from pathlib import Path
from typing import List, Optional

import requests

from .nhl_teams_db import init_db, upsert_teams
from ._nhl_db_shared import get_db_path

logger = logging.getLogger(__name__)

_BASE_URL = "https://api-web.nhle.com/v1"


def fetch_teams_from_standings() -> List[dict]:
    """Fetch all NHL teams from the weekly schedule endpoint.

    The ``/schedule/now`` response includes all 32 teams across its gameWeek
    entries, each with the canonical numeric team ``id``, abbreviation,
    common name, and place name — everything needed for the teams table.

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    url = f"{_BASE_URL}/schedule/now"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    seen: dict = {}
    for day in data.get("gameWeek", []):
        for game in day.get("games", []):
            for side in ("homeTeam", "awayTeam"):
                t = game.get(side, {})
                team_id = t.get("id")
                abbrev  = t.get("abbrev")
                if not team_id or not abbrev or abbrev in seen:
                    continue
                seen[abbrev] = {
                    "team_id":        team_id,
                    "team":           abbrev,
                    "team_full_name": t.get("commonName", {}).get("default", ""),
                    "city":           t.get("placeName", {}).get("default", ""),
                    "raw_json":       json.dumps(t),
                }

    return list(seen.values())


def full_sync_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all NHL teams and upsert them into the local cache.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows upserted.
    """
    init_db(db_path)
    teams = fetch_teams_from_standings()
    logger.info("full_sync_teams: fetched %d teams", len(teams))
    count = upsert_teams(teams, db_path)
    logger.info("full_sync_teams: complete — %d teams upserted", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync_teams()
    print(f"Sync complete: {rows} teams upserted to {get_db_path()}")

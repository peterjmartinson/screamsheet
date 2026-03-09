"""Full sync of NHL player roster data into the local SQLite cache.

Fetches all 32 team rosters from the NHL API and upserts every player record.
Intended to be run once per week via cron so the cache stays current.

Usage:
    python -m screamsheet.db.nhl_players_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_players_sync

Windows (run manually or add to Task Scheduler):
    python -m screamsheet.db.nhl_players_sync
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

import requests

from .nhl_players_db import get_db_path, init_db, upsert_players

logger = logging.getLogger(__name__)

_BASE_URL = "https://api-web.nhle.com/v1"


def fetch_all_team_abbreviations() -> List[str]:
    """Return every NHL team abbreviation from the standings endpoint.

    Returns:
        Sorted list of team abbreviation strings (e.g. ``["ANA", "BOS", ...]``).

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    url = f"{_BASE_URL}/standings/now"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    abbrevs: List[str] = []
    for record in data.get("standings", []):
        abbrev = record.get("teamAbbrev", {}).get("default")
        if abbrev:
            abbrevs.append(abbrev)

    return sorted(abbrevs)


def fetch_team_roster(team_abbrev: str) -> List[dict]:
    """Fetch and normalise all players for one team from the roster endpoint.

    Combines forwards, defensemen, and goalies into a flat list of dicts
    that is ready to pass directly to upsert_players().

    Args:
        team_abbrev: Three-letter NHL team abbreviation (e.g. ``"EDM"``).

    Returns:
        List of player dicts.  Empty list on any request error.
    """
    url = f"{_BASE_URL}/roster/{team_abbrev}/current"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        logger.warning("fetch_team_roster: failed for %s: %s", team_abbrev, exc)
        return []

    players: List[dict] = []
    for group in ("forwards", "defensemen", "goalies"):
        for p in data.get(group, []):
            players.append({
                "player_id":         p.get("id"),
                "player_first_name": p.get("firstName", {}).get("default", ""),
                "player_last_name":  p.get("lastName", {}).get("default", ""),
                "position":          p.get("positionCode", ""),
                "team":              team_abbrev,
                "raw_json":          json.dumps(p),
            })

    return players


def full_sync(db_path: Optional[Path] = None) -> int:
    """Fetch all NHL rosters and upsert every player into the local cache.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Total number of rows upserted across all teams.
    """
    init_db(db_path)
    abbreviations = fetch_all_team_abbreviations()
    logger.info("full_sync: syncing %d teams", len(abbreviations))

    total = 0
    for abbrev in abbreviations:
        players = fetch_team_roster(abbrev)
        if players:
            count = upsert_players(players, db_path)
            logger.info("full_sync: upserted %d players for %s", count, abbrev)
            total += count
        else:
            logger.warning("full_sync: no players returned for team %s", abbrev)

    logger.info("full_sync: complete — %d total players upserted", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rows = full_sync()
    print(f"Sync complete: {rows} players upserted to {get_db_path()}")

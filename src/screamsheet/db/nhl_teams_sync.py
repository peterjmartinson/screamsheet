"""Full sync of NHL team data into the local SQLite cache.

Fetches all 32 teams by combining two NHL API calls:
  1. /standings/now  — guarantees all 32 franchises are present year-round
  2. /schedule/{mid-season date} — provides numeric team IDs (not in standings)

This two-pass approach handles playoffs and off-season correctly.

Usage:
    python -m screamsheet.db.nhl_teams_sync

Cron example (Linux) — every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_teams_sync

Windows (run manually or add to Task Scheduler):
    python -m screamsheet.db.nhl_teams_sync
"""

import json
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Optional

import requests

from .nhl_teams_db import init_db, upsert_teams
from ._nhl_db_shared import get_db_path
from .team_lookup import upsert_team

logger = logging.getLogger(__name__)

_BASE_URL = "https://api-web.nhle.com/v1"


def _mid_season_date() -> str:
    """Return YYYY-MM-15 for November of the current NHL season's start year.

    The NHL regular season starts in October, so November 15 of the start year
    is always mid-season and guarantees every team appears in that week's schedule.
    """
    today = date.today()
    season_year = today.year if today.month >= 9 else today.year - 1
    return f"{season_year}-11-15"


def _fetch_team_ids_from_schedule(mid_season: str) -> dict:
    """Return {abbrev: team_id} by scanning one week of mid-season games.

    Uses /schedule/{YYYY-MM-DD} which includes all teams across its gameWeek.

    Args:
        mid_season: ISO date string (YYYY-MM-DD) guaranteed to be in-season.

    Returns:
        Dict mapping 3-letter abbreviation to numeric NHL team ID.
    """
    url = f"{_BASE_URL}/schedule/{mid_season}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    abbrev_to_id: dict = {}
    for day in data.get("gameWeek", []):
        for game in day.get("games", []):
            for side in ("homeTeam", "awayTeam"):
                t = game.get(side, {})
                team_id = t.get("id")
                abbrev = t.get("abbrev")
                if team_id and abbrev and abbrev not in abbrev_to_id:
                    abbrev_to_id[abbrev] = team_id
    return abbrev_to_id


def fetch_teams_from_standings() -> List[dict]:
    """Fetch all 32 NHL teams by combining standings and schedule data.

    - /standings/now provides all 32 franchises regardless of season phase.
    - /schedule/{mid-season date} provides numeric team IDs (not in standings).

    Returns:
        List of team dicts ready to pass to upsert_teams().

    Raises:
        requests.exceptions.HTTPError: on a non-2xx response.
    """
    # Pass 1: all 32 teams from standings (complete year-round)
    standings_url = f"{_BASE_URL}/standings/now"
    standings_resp = requests.get(standings_url, timeout=10)
    standings_resp.raise_for_status()
    standings_data = standings_resp.json()

    # Pass 2: numeric team IDs from a fixed mid-season schedule week
    abbrev_to_id = _fetch_team_ids_from_schedule(_mid_season_date())

    teams: list = []
    for t in standings_data.get("standings", []):
        abbrev = t.get("teamAbbrev", {}).get("default", "")
        if not abbrev:
            continue
        team_id = abbrev_to_id.get(abbrev)
        if not team_id:
            continue
        full_name = t.get("teamName", {}).get("default", "")
        city = t.get("placeName", {}).get("default", "")
        teams.append({
            "team_id":        team_id,
            "team":           abbrev,
            "team_full_name": full_name,
            "city":           city,
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
        full_name = nickname  # teamName.default already contains the full "City Nickname" string
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

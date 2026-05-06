"""Sync NFL team data into the local screamsheet.db via the ESPN unofficial API.

Fetches all 32 NFL teams from ESPN's site API and upserts them into the
``nfl_teams`` lookup table via :func:`team_lookup.upsert_team`.

Usage:
    uv run db_update
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from .team_lookup import upsert_team

logger = logging.getLogger(__name__)

_ESPN_NFL_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=100"
)


def sync_nfl_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all NFL teams from the ESPN API and upsert into the nfl_teams lookup table.

    Args:
        db_path: Override DB path (default: platform screamsheet.db).

    Returns:
        Number of rows upserted.

    Raises:
        requests.HTTPError: on a non-2xx API response.
    """
    response = requests.get(_ESPN_NFL_TEAMS_URL, timeout=15)
    response.raise_for_status()
    data = response.json()

    sports = data.get("sports", [])
    leagues = sports[0].get("leagues", []) if sports else []
    teams_list = leagues[0].get("teams", []) if leagues else []

    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for entry in teams_list:
        team = entry.get("team", {})
        team_id_str = (team.get("id") or "").strip()
        full_name = (team.get("displayName") or "").strip()
        abbrev = (team.get("abbreviation") or "").strip()
        if not team_id_str or not full_name:
            logger.warning("sync_nfl_teams: skipping incomplete entry: %s", team)
            continue
        try:
            team_id = int(team_id_str)
        except ValueError:
            logger.warning("sync_nfl_teams: non-integer team id %r, skipping", team_id_str)
            continue
        upsert_team("nfl", team_id, full_name, abbrev, now, db_path)
        count += 1

    logger.info("sync_nfl_teams: upserted %d teams", count)
    return count

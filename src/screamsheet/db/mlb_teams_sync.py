"""Sync MLB team data into the local screamsheet.db.

Fetches all MLB teams from the MLB Stats API and upserts them into the
``mlb_teams`` lookup table (via :func:`team_lookup.upsert_team`).

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

_MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"


def sync_mlb_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all MLB teams and upsert them into the mlb_teams lookup table.

    Args:
        db_path: Override DB path (default: platform screamsheet.db).

    Returns:
        Number of rows upserted.

    Raises:
        requests.HTTPError: on a non-2xx API response.
    """
    response = requests.get(_MLB_TEAMS_URL, timeout=15)
    response.raise_for_status()
    data = response.json()

    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for team in data.get("teams", []):
        team_id = team.get("id")
        full_name = (team.get("name") or "").strip()
        abbrev = (team.get("abbreviation") or "").strip()
        if not team_id or not full_name:
            logger.warning("sync_mlb_teams: skipping incomplete entry: %s", team)
            continue
        upsert_team("mlb", team_id, full_name, abbrev, now, db_path)
        count += 1

    logger.info("sync_mlb_teams: upserted %d teams", count)
    return count

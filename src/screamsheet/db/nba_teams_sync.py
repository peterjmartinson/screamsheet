"""Sync NBA team data into the local screamsheet.db.

Uses the ``nba_api`` package (static team list — no network call required)
and upserts into the ``nba_teams`` lookup table via
:func:`team_lookup.upsert_team`.

Usage:
    uv run db_update
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nba_api.stats.static import teams as nba_api_teams

from .team_lookup import upsert_team

logger = logging.getLogger(__name__)


def sync_nba_teams(db_path: Optional[Path] = None) -> int:
    """Fetch all NBA teams from nba_api and upsert into the nba_teams lookup table.

    Args:
        db_path: Override DB path (default: platform screamsheet.db).

    Returns:
        Number of rows upserted.
    """
    teams = nba_api_teams.get_teams()
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for team in teams:
        team_id = team.get("id")
        full_name = (team.get("full_name") or "").strip()
        abbrev = (team.get("abbreviation") or "").strip()
        if not team_id or not full_name:
            logger.warning("sync_nba_teams: skipping incomplete entry: %s", team)
            continue
        upsert_team("nba", team_id, full_name, abbrev, now, db_path)
        count += 1

    logger.info("sync_nba_teams: upserted %d teams", count)
    return count

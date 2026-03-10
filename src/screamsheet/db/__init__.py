"""NHL SQLite cache package (nhl.db).

Public API — players:
    get_db_path()                           Platform-appropriate DB file path
    init_db(db_path)                        Create the DB and tables
    upsert_players(players, db_path)        Bulk upsert player dicts
    lookup_player_by_id(player_id)          Cache lookup by NHL player ID
    lookup_player_by_name(last, first)      Cache lookup by name (case-insensitive)
    lookup_player(player_id, ...)           Orchestrator: cache → API fallback

Public API — teams:
    upsert_teams(teams, db_path)            Bulk upsert team dicts
    lookup_team_by_id(team_id)              Cache lookup by NHL numeric team ID
    lookup_team_by_abbrev(abbrev)           Cache lookup by 3-letter abbreviation
"""

from .nhl_players_db import (
    get_db_path,
    init_db,
    lookup_player,
    lookup_player_by_id,
    lookup_player_by_name,
    upsert_players,
)
from .nhl_teams_db import (
    lookup_team_by_abbrev,
    lookup_team_by_id,
    upsert_teams,
)

__all__ = [
    "get_db_path",
    "init_db",
    "lookup_player",
    "lookup_player_by_id",
    "lookup_player_by_name",
    "upsert_players",
    "lookup_team_by_abbrev",
    "lookup_team_by_id",
    "upsert_teams",
]

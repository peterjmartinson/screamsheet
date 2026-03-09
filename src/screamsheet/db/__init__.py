"""NHL players SQLite cache package.

Public API:
    get_db_path()                           Platform-appropriate DB file path
    init_db(db_path)                        Create the DB and players table
    upsert_players(players, db_path)        Bulk upsert player dicts
    lookup_player_by_id(player_id)          Cache lookup by NHL player ID
    lookup_player_by_name(last, first)      Cache lookup by name (case-insensitive)
    lookup_player(player_id, ...)           Orchestrator: cache → API fallback
"""

from .nhl_players_db import (
    get_db_path,
    init_db,
    lookup_player,
    lookup_player_by_id,
    lookup_player_by_name,
    upsert_players,
)

__all__ = [
    "get_db_path",
    "init_db",
    "lookup_player",
    "lookup_player_by_id",
    "lookup_player_by_name",
    "upsert_players",
]

"""Screamsheet SQLite cache package (screamsheet.db).

Public API — NHL players (legacy):
    get_db_path()                                    Resolved DB file path
    init_db(db_path)                                 Create the DB and tables
    upsert_players(players, db_path)                 Bulk upsert player dicts
    lookup_player_by_id(player_id)                   Cache lookup by NHL player ID
    lookup_player_by_name(last, first)               Cache lookup by name
    lookup_player(player_id, ...)                    Orchestrator: cache → API fallback

Public API — NHL teams (legacy, targets 'teams' table):
    upsert_nhl_teams(teams, db_path)                 Bulk upsert team dicts
    lookup_nhl_team_by_id(team_id)                   Cache lookup by NHL numeric ID
    lookup_nhl_team_by_abbrev(abbrev)                Cache lookup by 3-letter abbrev

Public API — multi-sport team lookup (targets '<sport>_teams' tables):
    sport_init_db(sport, db_path)                    Create sport table if missing
    sport_upsert_teams(sport, teams, db_path)        Bulk upsert team dicts
    sport_lookup_by_id(sport, team_id, db_path)      → dict | None
    sport_lookup_by_abbrev(sport, abbrev, db_path)   → dict | None
    sport_lookup_by_name(sport, fragment, db_path)   → list[dict]
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
    lookup_team_by_abbrev as lookup_nhl_team_by_abbrev,
    lookup_team_by_id as lookup_nhl_team_by_id,
    upsert_teams as upsert_nhl_teams,
)
from .team_lookup_db import (
    init_db as sport_init_db,
    lookup_team_by_abbrev as sport_lookup_by_abbrev,
    lookup_team_by_id as sport_lookup_by_id,
    lookup_team_by_name as sport_lookup_by_name,
    upsert_teams as sport_upsert_teams,
)

__all__ = [
    # DB path
    "get_db_path",
    # NHL players (legacy)
    "init_db",
    "lookup_player",
    "lookup_player_by_id",
    "lookup_player_by_name",
    "upsert_players",
    # NHL teams (legacy)
    "lookup_nhl_team_by_abbrev",
    "lookup_nhl_team_by_id",
    "upsert_nhl_teams",
    # Multi-sport team lookup
    "sport_init_db",
    "sport_lookup_by_abbrev",
    "sport_lookup_by_id",
    "sport_lookup_by_name",
    "sport_upsert_teams",
]

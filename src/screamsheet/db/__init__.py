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
    sport_lookup_by_alias(sport, alias, db_path)    → dict | None
    sport_get_team_aliases(sport, team_id, db_path)  → list[str]
    sport_get_team_feed_slug(sport, team_id, db_path)→ str | None
    sport_resolve_team(sport, query, db_path)        → dict | None
    sport_seed_aliases(sport, db_path, csv_path)     → int
    sport_load_aliases_from_csv(csv_path, sport, db_path) → int

Public API — LLM response cache:
    llm_cache_init(db_path)                          Create llm_cache table
    llm_cache_get(cache_key, db_path)                → str | None
    llm_cache_save(cache_key, ...)                   Save LLM response with TTL
    llm_cache_purge_expired(db_path)                 → int (purged count)
    llm_cache_clear(db_path, topic_filter)           → int (cleared count)
    llm_cache_stats(db_path)                         → dict
"""

from .llm_cache_db import (
    clear_cache as llm_cache_clear,
    get_cache_stats as llm_cache_stats,
    get_cached_response as llm_cache_get,
    init_cache_db as llm_cache_init,
    purge_expired_cache as llm_cache_purge_expired,
    save_cached_response as llm_cache_save,
)
from .weather_cache_db import (
    CachedFetchResult,
    fetch_with_cache,
    get_weather_cache,
    init_weather_cache_db,
    save_weather_cache,
    weather_cache_fetch,
)
from .weather_patterns_db import (
    WEATHER_PATTERNS_SCHEMA_VERSION,
    compute_teleconnection_verification_stats,
    find_historical_teleconnection_analogs,
    get_forecast_vintages_for_metric,
    get_local_pressure_history,
    get_stratosphere_obs_history,
    get_teleconnection_obs_history,
    get_weather_schema_version,
    init_weather_patterns_db,
    persist_weather_patterns_bundle,
    purge_expired_weather_raw_cache,
    save_enso_observations,
    save_local_location_observations,
    save_mjo_observations,
    save_nws_local_forecast_vintage,
    save_stratosphere_forecast_vintage,
    save_stratosphere_observations,
    save_teleconnection_forecast_vintage,
    save_teleconnection_observations,
    sync_weather_patterns_db,
)
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
    DEFAULT_CSV_PATH,
    get_team_aliases as sport_get_team_aliases,
    get_team_feed_slug as sport_get_team_feed_slug,
    init_db as sport_init_db,
    load_aliases_from_csv as sport_load_aliases_from_csv,
    lookup_team_by_alias as sport_lookup_by_alias,
    lookup_team_by_abbrev as sport_lookup_by_abbrev,
    lookup_team_by_id as sport_lookup_by_id,
    lookup_team_by_name as sport_lookup_by_name,
    resolve_team as sport_resolve_team,
    seed_aliases as sport_seed_aliases,
    upsert_team_aliases as sport_upsert_team_aliases,
    upsert_teams as sport_upsert_teams,
)
from .soccer_db import (
    init_soccer_db,
    resolve_soccer_league,
    resolve_soccer_player,
    resolve_soccer_team,
    seed_soccer_db,
    sync_soccer_leagues_from_api,
    upsert_soccer_aliases,
    upsert_soccer_leagues,
    upsert_soccer_players,
    upsert_soccer_teams,
)

__all__ = [
    # DB path
    "get_db_path",
    "DEFAULT_CSV_PATH",
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
    "sport_lookup_by_alias",
    "sport_get_team_aliases",
    "sport_get_team_feed_slug",
    "sport_resolve_team",
    "sport_seed_aliases",
    "sport_load_aliases_from_csv",
    "sport_upsert_team_aliases",
    "sport_upsert_teams",
    # LLM cache
    "llm_cache_init",
    "llm_cache_get",
    "llm_cache_save",
    "llm_cache_purge_expired",
    "llm_cache_clear",
    "llm_cache_stats",
    # Weather data cache
    "CachedFetchResult",
    "init_weather_cache_db",
    "get_weather_cache",
    "save_weather_cache",
    "weather_cache_fetch",
    # Weather Patterns V2 institutional memory DB
    "WEATHER_PATTERNS_SCHEMA_VERSION",
    "init_weather_patterns_db",
    "get_weather_schema_version",
    "save_teleconnection_observations",
    "save_stratosphere_observations",
    "save_mjo_observations",
    "save_enso_observations",
    "save_local_location_observations",
    "save_teleconnection_forecast_vintage",
    "save_stratosphere_forecast_vintage",
    "save_nws_local_forecast_vintage",
    "persist_weather_patterns_bundle",
    "get_teleconnection_obs_history",
    "get_stratosphere_obs_history",
    "get_local_pressure_history",
    "get_forecast_vintages_for_metric",
    "compute_teleconnection_verification_stats",
    "find_historical_teleconnection_analogs",
    "sync_weather_patterns_db",
    "purge_expired_weather_raw_cache",
    # International soccer catalog & alias DB
    "init_soccer_db",
    "seed_soccer_db",
    "sync_soccer_leagues_from_api",
    "resolve_soccer_league",
    "resolve_soccer_team",
    "resolve_soccer_player",
    "upsert_soccer_leagues",
    "upsert_soccer_teams",
    "upsert_soccer_players",
    "upsert_soccer_aliases",
]

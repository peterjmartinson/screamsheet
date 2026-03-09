"""SQLite cache for NHL player data.

Table schema:
    players (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id         INTEGER NOT NULL UNIQUE,   -- NHL API numeric player ID
        player_last_name  VARCHAR(100),
        player_first_name VARCHAR(100),
        position          VARCHAR(10),
        team              VARCHAR(100),
        update_date       VARCHAR(25),               -- ISO-8601 UTC timestamp
        raw_json          TEXT                        -- raw API payload for debugging
    )

Lookup priority (via lookup_player):
    1. player_id exact match
    2. last_name case-insensitive (+ optional first_name filter)
    3. NHL API /player/{id}/landing on cache-miss — result is auto-upserted

Name collisions:
    lookup_player_by_name() returns ALL matches as a List[Dict].  The caller
    is responsible for selecting the correct entry when multiple players share
    the same last name (e.g. two brothers or a common surname).  Cross-reference
    the ``team`` or ``position`` field to disambiguate.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from sqlalchemy import Column, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

logger = logging.getLogger(__name__)

_NHL_PLAYER_API = "https://api-web.nhle.com/v1/player/{player_id}/landing"


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class _Base(DeclarativeBase):
    pass


class _Player(_Base):
    __tablename__ = "players"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    player_id         = Column(Integer, nullable=False, unique=True, index=True)
    player_last_name  = Column(String(100), index=True)
    player_first_name = Column(String(100))
    position          = Column(String(10))
    team              = Column(String(100))
    update_date       = Column(String(25))
    raw_json          = Column(Text)


# ---------------------------------------------------------------------------
# DB path
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Return the platform-appropriate path for the NHL players database.

    Linux / macOS:  ~/database/nhl_players.db
    Windows:        C:\\database\\nhl_players.db
    """
    if sys.platform.startswith("win"):
        return Path("C:/database/nhl_players.db")
    return Path.home() / "database" / "nhl_players.db"


# ---------------------------------------------------------------------------
# Engine / init
# ---------------------------------------------------------------------------

def init_db(db_path: Optional[Path] = None):
    """Create the database file and players table if they do not exist.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        SQLAlchemy Engine bound to the database.
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    logger.info("NHL players DB initialised at %s", path)
    return engine


def _get_engine(db_path: Optional[Path] = None):
    """Return an engine for db_path, creating the DB/table if necessary."""
    return init_db(db_path)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_players(players: List[Dict], db_path: Optional[Path] = None) -> int:
    """Upsert a list of player dicts into the players table.

    Each dict must contain at minimum ``player_id``.  Accepted keys:
        player_id, player_first_name, player_last_name, position, team, raw_json

    ``update_date`` is always overwritten with the current UTC timestamp.

    Args:
        players:  List of player dicts.
        db_path:  Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows successfully upserted.
    """
    engine = _get_engine(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    with Session(engine) as session:
        for p in players:
            pid = p.get("player_id")
            if pid is None:
                logger.warning("upsert_players: skipping entry without player_id: %s", p)
                continue
            session.execute(
                text("DELETE FROM players WHERE player_id = :pid"), {"pid": pid}
            )
            session.add(_Player(
                player_id         = pid,
                player_last_name  = (p.get("player_last_name") or "")[:100],
                player_first_name = (p.get("player_first_name") or "")[:100],
                position          = (p.get("position") or "")[:10],
                team              = (p.get("team") or "")[:100],
                update_date       = now,
                raw_json          = p.get("raw_json") or "",
            ))
            count += 1
        session.commit()
    logger.debug("upsert_players: upserted %d rows", count)
    return count


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row: _Player) -> Dict:
    return {
        "id":                row.id,
        "player_id":         row.player_id,
        "player_last_name":  row.player_last_name,
        "player_first_name": row.player_first_name,
        "position":          row.position,
        "team":              row.team,
        "update_date":       row.update_date,
        "raw_json":          row.raw_json,
    }


def lookup_player_by_id(
    player_id: int,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a player by their NHL numeric player_id.

    Returns:
        Dict of player fields, or None if not in cache.
    """
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(_Player).filter(_Player.player_id == player_id).first()
        return _row_to_dict(row) if row else None


def lookup_player_by_name(
    last_name: str,
    first_name: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict]:
    """Case-insensitive lookup by last name, with optional first-name filter.

    Name collisions: multiple players may share a last name.  All matches are
    returned so the caller can disambiguate by ``team`` or ``position``.

    Returns:
        List of matching player dicts (may be empty).
    """
    engine = _get_engine(db_path)
    with Session(engine) as session:
        q = session.query(_Player).filter(
            _Player.player_last_name.ilike(f"%{last_name}%")
        )
        if first_name:
            q = q.filter(_Player.player_first_name.ilike(f"%{first_name}%"))
        return [_row_to_dict(r) for r in q.all()]


# ---------------------------------------------------------------------------
# API fallback
# ---------------------------------------------------------------------------

def _fetch_player_from_api(player_id: int) -> Optional[Dict]:
    """Fetch a single player from NHL API and return an upsert-ready dict."""
    try:
        url = _NHL_PLAYER_API.format(player_id=player_id)
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        info = res.json()
        return {
            "player_id":         player_id,
            "player_first_name": info.get("firstName", {}).get("default", "Unknown"),
            "player_last_name":  info.get("lastName", {}).get("default", "Player"),
            "position":          info.get("position", ""),
            "team":              info.get("currentTeamAbbrev", ""),
            "raw_json":          json.dumps(info),
        }
    except (requests.exceptions.RequestException, KeyError, ValueError) as exc:
        logger.warning(
            "_fetch_player_from_api: failed to fetch player %d: %s", player_id, exc
        )
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def lookup_player(
    player_id: Optional[int] = None,
    last_name: Optional[str] = None,
    first_name: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a player with automatic API fallback on cache miss.

    Priority:
        1. player_id exact match (when player_id is provided)
        2. Name-based search (when last_name is provided, no player_id)
        3. NHL API /player/{id}/landing — only when player_id is provided and
           not found locally; the fetched record is upserted into the cache.

    Args:
        player_id:  NHL numeric player ID.
        last_name:  Player last name (case-insensitive partial match).
        first_name: Player first name (case-insensitive partial match, optional filter).
        db_path:    Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Player dict or None.
    """
    if player_id is not None:
        cached = lookup_player_by_id(player_id, db_path)
        if cached:
            return cached
        # API fallback
        player_data = _fetch_player_from_api(player_id)
        if player_data:
            upsert_players([player_data], db_path)
            return lookup_player_by_id(player_id, db_path)
        return None

    if last_name:
        results = lookup_player_by_name(last_name, first_name, db_path)
        return results[0] if results else None

    return None

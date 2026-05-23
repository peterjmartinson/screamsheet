"""SQLite ORM models and lookup helpers for per-sport team tables.

All four sports share an identical table schema:

    <sport>_teams (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id     INTEGER NOT NULL,
        full_name   VARCHAR(150) NOT NULL,
        abbrev      VARCHAR(10),
        last_synced VARCHAR(25)
    )

Tables: nhl_teams, mlb_teams, nba_teams, nfl_teams

Public API:
    init_db(sport, db_path)                        Create table if missing → Engine
    upsert_teams(sport, teams, db_path)            Bulk idempotent upsert → count
    lookup_team_by_id(sport, team_id, db_path)     → dict | None
    lookup_team_by_abbrev(sport, abbrev, db_path)  → dict | None
    lookup_team_by_name(sport, fragment, db_path)  → list[dict]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger(__name__)

Sport = Literal["nhl", "mlb", "nba", "nfl"]


# ---------------------------------------------------------------------------
# ORM models — one per sport, identical schema, different __tablename__
# ---------------------------------------------------------------------------

class _NHLTeam(_Base):
    __tablename__ = "nhl_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _MLBTeam(_Base):
    __tablename__ = "mlb_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _NBATeam(_Base):
    __tablename__ = "nba_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _NFLTeam(_Base):
    __tablename__ = "nfl_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


_MODELS: dict[str, type] = {
    "nhl": _NHLTeam,
    "mlb": _MLBTeam,
    "nba": _NBATeam,
    "nfl": _NFLTeam,
}


# ---------------------------------------------------------------------------
# Engine / init
# ---------------------------------------------------------------------------

def _get_engine(db_path: Optional[Path] = None):
    """Return a SQLAlchemy engine, creating all sport-team tables if needed."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_db(sport: Sport, db_path: Optional[Path] = None):
    """Create the <sport>_teams table if it does not exist.

    Args:
        sport:   One of "nhl", "mlb", "nba", "nfl".
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        SQLAlchemy Engine bound to the database.
    """
    engine = _get_engine(db_path)
    logger.debug("init_db: %s_teams ready at %s", sport, db_path or get_db_path())
    return engine


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_teams(
    sport: Sport,
    teams: List[Dict],
    db_path: Optional[Path] = None,
) -> int:
    """Idempotent bulk upsert of team dicts into the <sport>_teams table.

    Each dict must contain ``team_id`` and ``full_name``.
    Optional: ``abbrev``.  ``last_synced`` is always set to the current UTC
    timestamp.

    Args:
        sport:   Target sport table.
        teams:   List of team dicts.
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows successfully upserted.
    """
    model_cls = _MODELS[sport]
    table = model_cls.__tablename__
    engine = _get_engine(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    with Session(engine) as session:
        for t in teams:
            tid = t.get("team_id")
            if tid is None:
                logger.warning(
                    "upsert_teams(%s): skipping entry without team_id: %s", sport, t
                )
                continue
            session.execute(
                text(f"DELETE FROM {table} WHERE team_id = :tid"), {"tid": tid}
            )
            session.add(model_cls(
                team_id     = tid,
                full_name   = (t.get("full_name") or "")[:150],
                abbrev      = (t.get("abbrev") or "")[:10],
                last_synced = now,
            ))
            count += 1
        session.commit()
    logger.debug("upsert_teams(%s): upserted %d rows", sport, count)
    return count


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> Dict:
    return {
        "id":          row.id,
        "team_id":     row.team_id,
        "full_name":   row.full_name,
        "abbrev":      row.abbrev,
        "last_synced": row.last_synced,
    }


def lookup_team_by_id(
    sport: Sport,
    team_id: int,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by its numeric team_id.

    Returns:
        Dict of team fields, or None if not in cache.
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(model_cls).filter(model_cls.team_id == team_id).first()
        return _row_to_dict(row) if row else None


def lookup_team_by_abbrev(
    sport: Sport,
    abbrev: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by abbreviation (case-insensitive).

    Returns:
        Dict of team fields, or None if not in cache.
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(model_cls).filter(
            model_cls.abbrev.ilike(abbrev)
        ).first()
        return _row_to_dict(row) if row else None


def lookup_team_by_name(
    sport: Sport,
    name_fragment: str,
    db_path: Optional[Path] = None,
) -> List[Dict]:
    """Case-insensitive partial match on full_name.

    Returns:
        List of matching team dicts (may be empty).
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        rows = session.query(model_cls).filter(
            model_cls.full_name.ilike(f"%{name_fragment}%")
        ).all()
        return [_row_to_dict(r) for r in rows]

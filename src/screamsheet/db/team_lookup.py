"""Team name → numeric API ID lookup via the local screamsheet.db.

Each sport has its own table (``nhl_teams``, ``mlb_teams``, ``nba_teams``,
``nfl_teams``).  The canonical team name is stored in the ``full_name``
column as ``"{city} {nickname}"``, e.g. ``"Philadelphia Flyers"``.

If the DB is not populated for a sport (e.g. before the first ``db_update``
run), ``lookup_team_id_by_name`` returns ``None`` — the caller is
responsible for handling a ``None`` id gracefully.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from ._nhl_db_shared import get_db_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM models — one per sport team table
# ---------------------------------------------------------------------------

class _TeamBase(DeclarativeBase):
    pass


class _NhlTeam(_TeamBase):
    __tablename__ = "nhl_teams"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    team_id   = Column(Integer, nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False, index=True)
    abbrev    = Column(String(10))
    last_synced = Column(String(25))


class _MlbTeam(_TeamBase):
    __tablename__ = "mlb_teams"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    team_id   = Column(Integer, nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False, index=True)
    abbrev    = Column(String(10))
    last_synced = Column(String(25))


class _NbaTeam(_TeamBase):
    __tablename__ = "nba_teams"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    team_id   = Column(Integer, nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False, index=True)
    abbrev    = Column(String(10))
    last_synced = Column(String(25))


class _NflTeam(_TeamBase):
    __tablename__ = "nfl_teams"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    team_id   = Column(Integer, nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False, index=True)
    abbrev    = Column(String(10))
    last_synced = Column(String(25))


_SPORT_MODEL = {
    "nhl": _NhlTeam,
    "mlb": _MlbTeam,
    "nba": _NbaTeam,
    "nfl": _NflTeam,
}


# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

def _get_engine(db_path: Optional[Path] = None):
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _TeamBase.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_team_id_by_name(
    sport: str,
    full_name: str,
    db_path: Optional[Path] = None,
) -> Optional[int]:
    """Return the numeric API team ID for a given canonical full name.

    Args:
        sport:     One of ``"nhl"``, ``"mlb"``, ``"nba"``, ``"nfl"``.
        full_name: Canonical full name, e.g. ``"Philadelphia Flyers"``.
        db_path:   Override DB path (used in tests).

    Returns:
        The integer team ID, or ``None`` if not found.
    """
    model = _SPORT_MODEL.get(sport)
    if model is None:
        logger.warning("lookup_team_id_by_name: unknown sport %r", sport)
        return None

    try:
        engine = _get_engine(db_path)
        with Session(engine) as session:
            row = (
                session.query(model)
                .filter(model.full_name == full_name)
                .first()
            )
            return row.team_id if row else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("lookup_team_id_by_name: DB error for %s/%s: %s", sport, full_name, exc)
        return None


def upsert_team(
    sport: str,
    team_id: int,
    full_name: str,
    abbrev: str,
    last_synced: str,
    db_path: Optional[Path] = None,
) -> None:
    """Insert or replace a team row.  Used by the sport-specific sync jobs."""
    model = _SPORT_MODEL.get(sport)
    if model is None:
        raise ValueError(f"Unknown sport: {sport!r}")

    engine = _get_engine(db_path)
    with Session(engine) as session:
        session.execute(
            text(f"DELETE FROM {model.__tablename__} WHERE team_id = :tid"),  # noqa: S608
            {"tid": team_id},
        )
        session.add(model(
            team_id=team_id,
            full_name=full_name[:150],
            abbrev=abbrev[:10],
            last_synced=last_synced,
        ))
        session.commit()

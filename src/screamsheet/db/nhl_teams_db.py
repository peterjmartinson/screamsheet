"""SQLite cache for NHL team data (stored in nhl.db).

Table schema:
    teams (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id        INTEGER NOT NULL UNIQUE,  -- NHL API numeric team ID
        team           VARCHAR(10),              -- 3-letter abbreviation, e.g. "PHI"
        team_full_name VARCHAR(100),             -- team nickname only, e.g. "Flyers"
        city           VARCHAR(100),             -- city/place name, e.g. "Philadelphia"
        update_date    VARCHAR(25),              -- ISO-8601 UTC timestamp
        raw_json       TEXT                      -- raw API payload for debugging
    )

Lookup order:
    lookup_team_by_id(team_id)        -- primary lookup key used by play-by-play data
    lookup_team_by_abbrev(abbrev)     -- secondary lookup by 3-letter code
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import Column, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class _Team(_Base):
    __tablename__ = "teams"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    team_id        = Column(Integer, nullable=False, unique=True, index=True)
    team           = Column(String(10), index=True)   # 3-letter abbreviation
    team_full_name = Column(String(100))               # nickname, e.g. "Flyers"
    city           = Column(String(100))               # city, e.g. "Philadelphia"
    update_date    = Column(String(25))
    raw_json       = Column(Text)


# ---------------------------------------------------------------------------
# Engine / init
# ---------------------------------------------------------------------------

def init_db(db_path: Optional[Path] = None):
    """Create the database file and teams table if they do not exist.

    Args:
        db_path: Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        SQLAlchemy Engine bound to the database.
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    logger.info("NHL DB initialised at %s", path)
    return engine


def _get_engine(db_path: Optional[Path] = None):
    return init_db(db_path)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_teams(teams: List[Dict], db_path: Optional[Path] = None) -> int:
    """Upsert a list of team dicts into the teams table.

    Each dict must contain at minimum ``team_id``.  Accepted keys:
        team_id, team, team_full_name, city, raw_json

    ``update_date`` is always overwritten with the current UTC timestamp.

    Args:
        teams:    List of team dicts.
        db_path:  Path to the SQLite file.  Defaults to get_db_path().

    Returns:
        Number of rows successfully upserted.
    """
    engine = _get_engine(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    with Session(engine) as session:
        for t in teams:
            tid = t.get("team_id")
            if tid is None:
                logger.warning("upsert_teams: skipping entry without team_id: %s", t)
                continue
            session.execute(
                text("DELETE FROM teams WHERE team_id = :tid"), {"tid": tid}
            )
            session.add(_Team(
                team_id        = tid,
                team           = (t.get("team") or "")[:10],
                team_full_name = (t.get("team_full_name") or "")[:100],
                city           = (t.get("city") or "")[:100],
                update_date    = now,
                raw_json       = t.get("raw_json") or "",
            ))
            count += 1
        session.commit()
    logger.debug("upsert_teams: upserted %d rows", count)
    return count


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row: _Team) -> Dict:
    return {
        "id":             row.id,
        "team_id":        row.team_id,
        "team":           row.team,
        "team_full_name": row.team_full_name,
        "city":           row.city,
        "update_date":    row.update_date,
        "raw_json":       row.raw_json,
    }


def lookup_team_by_id(
    team_id: int,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by its NHL numeric team_id.

    Returns:
        Dict of team fields, or None if not in cache.
    """
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(_Team).filter(_Team.team_id == team_id).first()
        return _row_to_dict(row) if row else None


def lookup_team_by_abbrev(
    abbrev: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by its 3-letter abbreviation (case-insensitive).

    Returns:
        Dict of team fields, or None if not in cache.
    """
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(_Team).filter(
            _Team.team.ilike(abbrev)
        ).first()
        return _row_to_dict(row) if row else None

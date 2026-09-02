"""SQLite storage and management for tracking seen and latest XKCD comics."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from sqlalchemy import Boolean, Column, Integer, String, create_engine
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger("screamsheet.xkcd.db")


class _XKCDComic(_Base):
    __tablename__ = "xkcd_comics"
    num         = Column(Integer, primary_key=True)
    title       = Column(String(300), nullable=False)
    safe_title  = Column(String(300), nullable=False)
    img         = Column(String(500), nullable=False)
    alt         = Column(String(2000), nullable=False)
    year        = Column(String(10), nullable=True)
    month       = Column(String(10), nullable=True)
    day         = Column(String(10), nullable=True)
    fetched_at  = Column(String(30), nullable=False)
    is_latest   = Column(Boolean, default=False, nullable=False)


def _get_engine(db_path: Optional[Path] = None):
    """Return a SQLAlchemy engine, ensuring xkcd_comics table exists."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_xkcd_db(db_path: Optional[Path] = None):
    """Create the xkcd_comics table if it does not exist."""
    return _get_engine(db_path)


def is_comic_seen(num: int, db_path: Optional[Path] = None) -> bool:
    """Check if comic *num* has already been recorded in the database."""
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(_XKCDComic.num).filter(_XKCDComic.num == num).first()
        return row is not None


def get_seen_comic_nums(db_path: Optional[Path] = None) -> Set[int]:
    """Retrieve the set of all comic issue numbers recorded in the database."""
    engine = _get_engine(db_path)
    with Session(engine) as session:
        rows = session.query(_XKCDComic.num).all()
        return {r[0] for r in rows}


def get_comic(num: int, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve recorded comic metadata for issue *num*."""
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(_XKCDComic).filter(_XKCDComic.num == num).first()
        if not row:
            return None
        return {
            "num": row.num,
            "title": row.title,
            "safe_title": row.safe_title,
            "img": row.img,
            "alt": row.alt,
            "year": row.year,
            "month": row.month,
            "day": row.day,
            "fetched_at": row.fetched_at,
            "is_latest": row.is_latest,
        }


def record_comic(
    comic_data: Dict[str, Any],
    is_latest: bool = False,
    db_path: Optional[Path] = None,
) -> None:
    """Record comic metadata in the database if not already present.

    Args:
        comic_data: Dictionary returned by the XKCD API.
        is_latest:  True if this was fetched as the latest new release.
        db_path:    Optional override for database path.
    """
    engine = _get_engine(db_path)
    num = int(comic_data["num"])
    now_iso = datetime.now(timezone.utc).isoformat()

    with Session(engine) as session:
        existing = session.query(_XKCDComic).filter(_XKCDComic.num == num).first()
        if existing:
            if is_latest and not existing.is_latest:
                existing.is_latest = True
                session.commit()
            return

        comic = _XKCDComic(
            num=num,
            title=str(comic_data.get("title", "")),
            safe_title=str(comic_data.get("safe_title", "")),
            img=str(comic_data.get("img", "")),
            alt=str(comic_data.get("alt", "")),
            year=str(comic_data.get("year", "")),
            month=str(comic_data.get("month", "")),
            day=str(comic_data.get("day", "")),
            fetched_at=now_iso,
            is_latest=is_latest,
        )
        session.add(comic)
        session.commit()
        logger.info("Recorded XKCD comic #%d (%s) [latest=%s]", num, comic.title, is_latest)

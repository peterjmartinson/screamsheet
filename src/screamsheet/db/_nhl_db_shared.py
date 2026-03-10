"""Shared SQLAlchemy base and DB-path helper for the NHL SQLite cache.

All ORM models that live in nhl.db import _Base from this module so that
SQLAlchemy's metadata is unified under one DeclarativeBase instance.
"""

import sys
from pathlib import Path

from sqlalchemy.orm import DeclarativeBase


class _Base(DeclarativeBase):
    pass


def get_db_path() -> Path:
    """Return the platform-appropriate path for the NHL database.

    Linux / macOS:  ~/database/nhl.db
    Windows:        C:\\database\\nhl.db
    """
    if sys.platform.startswith("win"):
        return Path("C:/database/nhl.db")
    return Path.home() / "database" / "nhl.db"

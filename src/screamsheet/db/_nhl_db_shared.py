"""Shared SQLAlchemy base and DB-path helper for the screamsheet SQLite cache.

All ORM models that live in screamsheet.db import _Base from this module so
that SQLAlchemy's metadata is unified under one DeclarativeBase instance.
"""

import sys
from pathlib import Path

from sqlalchemy.orm import DeclarativeBase


class _Base(DeclarativeBase):
    pass


def get_db_path() -> Path:
    """Return the platform-appropriate path for the screamsheet database.

    Linux / macOS:  ~/database/screamsheet.db
    Windows:        C:\\database\\screamsheet.db
    """
    if sys.platform.startswith("win"):
        return Path("C:/database/screamsheet.db")
    return Path.home() / "database" / "screamsheet.db"

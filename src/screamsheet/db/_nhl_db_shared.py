"""Shared SQLAlchemy base and DB-path helper for the screamsheet SQLite cache.

All ORM models import _Base from this module so that SQLAlchemy's metadata
is unified under one DeclarativeBase instance.  All tables live in a single
database file (screamsheet.db).

DB path resolution order:
    1. SCREAMSHEET_DB environment variable (if set)
    2. Platform default: ~/database/screamsheet.db  (Linux / macOS)
                         C:\\database\\screamsheet.db (Windows)
"""

import os
import sys
from pathlib import Path

from sqlalchemy.orm import DeclarativeBase


class _Base(DeclarativeBase):
    pass


def get_db_path() -> Path:
    """Return the resolved path to the screamsheet SQLite database.

    Checks the SCREAMSHEET_DB environment variable first, then falls back
    to the platform default (~/database/screamsheet.db).
    """
    env = os.environ.get("SCREAMSHEET_DB")
    if env:
        return Path(env)
    if sys.platform.startswith("win"):
        return Path("C:/database/screamsheet.db")
    return Path.home() / "database" / "screamsheet.db"

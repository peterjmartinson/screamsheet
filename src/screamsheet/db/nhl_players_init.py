"""One-time initialisation of the NHL players SQLite database.

Creates the ~/database/ directory (or C:\\database\\ on Windows) and the
players table.  Optionally runs a full player sync on first use.

Usage:
    python -m screamsheet.db.nhl_players_init          # schema only
    python -m screamsheet.db.nhl_players_init --sync   # schema + full sync

Cron example (Linux) — run a full sync every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_players_sync

Windows — run manually or add to Windows Task Scheduler:
    python -m screamsheet.db.nhl_players_init --sync
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from .nhl_players_db import get_db_path, init_db
from .nhl_players_sync import full_sync

logger = logging.getLogger(__name__)


def init(run_sync: bool = False, db_path: Optional[Path] = None) -> None:
    """Initialise the NHL players database.

    Args:
        run_sync: When True, immediately run a full player sync after init.
        db_path:  Override the default DB path (primarily for testing).
    """
    path = db_path or get_db_path()
    init_db(path)
    print(f"Database initialised at {path}")

    if run_sync:
        print("Running full player sync (this may take a minute)...")
        rows = full_sync(path)
        print(f"Sync complete: {rows} players upserted.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Initialise the NHL players SQLite database."
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run a full player sync after initialising the schema.",
    )
    args = parser.parse_args()
    init(run_sync=args.sync)

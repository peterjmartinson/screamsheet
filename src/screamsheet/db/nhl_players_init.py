"""One-time initialisation of the NHL SQLite database (nhl.db).

Creates ~/database/ (or C:\\database\ on Windows), the players table, and
the teams table.  Optionally runs a full sync of both players and teams.

Usage:
    python -m screamsheet.db.nhl_players_init          # schema only
    python -m screamsheet.db.nhl_players_init --sync   # schema + full sync (players + teams)

Cron example (Linux) — run a full sync every Sunday at 3 am:
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_players_sync
    0 3 * * 0 cd /path/to/screamsheet && .venv/bin/python -m screamsheet.db.nhl_teams_sync

Windows — run manually or add to Windows Task Scheduler:
    python -m screamsheet.db.nhl_players_init --sync
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from ._nhl_db_shared import get_db_path
from .nhl_players_db import init_db
from .nhl_players_sync import full_sync
from .nhl_teams_sync import full_sync_teams

logger = logging.getLogger(__name__)


def init(run_sync: bool = False, db_path: Optional[Path] = None) -> None:
    """Initialise the NHL database (players + teams tables).

    Args:
        run_sync: When True, run a full sync of players and teams after init.
        db_path:  Override the default DB path (primarily for testing).
    """
    path = db_path or get_db_path()
    init_db(path)
    print(f"Database initialised at {path}")

    if run_sync:
        print("Running full player sync (this may take a minute)...")
        player_rows = full_sync(path)
        print(f"Players sync complete: {player_rows} players upserted.")

        print("Running full team sync...")
        team_rows = full_sync_teams(path)
        print(f"Teams sync complete: {team_rows} teams upserted.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Initialise the NHL SQLite database (players + teams)."
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run a full player sync after initialising the schema.",
    )
    args = parser.parse_args()
    init(run_sync=args.sync)

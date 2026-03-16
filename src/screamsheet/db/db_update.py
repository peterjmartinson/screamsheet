"""CLI entry point for syncing the NHL database.

Runs the full teams-and-players sync and prints counts to stdout so that
callers (e.g. update_db.sh) can capture them in a log file.

Usage:
    uv run db_update
    uv run db_update --db /path/to/custom.db

Exit codes:
    0 — both syncs completed and returned non-zero row counts
    1 — a sync raised an exception or returned zero rows (silent network failure)
"""

import argparse
import sys
from pathlib import Path

from ._nhl_db_shared import get_db_path
from .nhl_teams_sync import full_sync_teams
from .nhl_players_sync import full_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync NHL teams and players into the local database.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database file (default: %(default)s → uses platform default)",
    )
    args = parser.parse_args()

    db = args.db or get_db_path()
    print(f"Using DB: {db}")

    try:
        teams = full_sync_teams(db)
        print(f"teams_upserted:{teams}")
        if teams == 0:
            print("WARNING: zero teams upserted — possible network failure.", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: teams sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        players = full_sync(db)
        print(f"players_upserted:{players}")
        if players == 0:
            print("WARNING: zero players upserted — possible network failure.", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: players sync failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

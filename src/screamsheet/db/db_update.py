"""CLI entry point for syncing all sport databases.

Runs team and player syncs for all supported sports and prints counts to
stdout so that callers (e.g. update_db.sh) can capture them in a log file.

Usage:
    uv run db_update
    uv run db_update --db /path/to/custom.db

Exit codes:
    0 — all syncs completed with non-zero row counts
    1 — any sync raised an exception or returned zero rows
"""

import argparse
import sys
from pathlib import Path

from ._nhl_db_shared import get_db_path
from .nhl_teams_sync import full_sync_canonical_teams, full_sync_teams
from .nhl_players_sync import full_sync as full_sync_players
from .mlb_teams_sync import full_sync as mlb_full_sync
from .nba_teams_sync import full_sync as nba_full_sync
from .nfl_teams_sync import full_sync as nfl_full_sync


def _run(label: str, fn, db: Path) -> bool:
    """Run one sync function, print its count, return False on failure."""
    try:
        count = fn(db)
        print(f"{label}:{count}")
        if count == 0:
            print(f"WARNING: zero rows for {label} — possible network failure.", file=sys.stderr)
            return False
        return True
    except Exception as exc:
        print(f"ERROR: {label} failed: {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync all sport teams and NHL players into the local database."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database file (default: platform default)",
    )
    args = parser.parse_args()

    db = args.db or get_db_path()
    print(f"Using DB: {db}")

    ok = True
    ok &= _run("nhl_teams_legacy_upserted",    full_sync_teams,           db)
    ok &= _run("nhl_teams_upserted",           full_sync_canonical_teams, db)
    ok &= _run("mlb_teams_upserted",           mlb_full_sync,             db)
    ok &= _run("nba_teams_upserted",           nba_full_sync,             db)
    ok &= _run("nfl_teams_upserted",           nfl_full_sync,             db)
    ok &= _run("nhl_players_upserted",         full_sync_players,         db)

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""CLI entry point for syncing the screamsheet database.

Syncs NHL teams + players, MLB teams, NBA teams, and NFL teams into the
local screamsheet.db.  Prints per-sport counts to stdout.

Usage:
    uv run db_update
    uv run db_update --db /path/to/custom.db

Exit codes:
    0 — all syncs completed with non-zero row counts
    1 — a sync raised an exception or returned zero rows
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

from ._nhl_db_shared import get_db_path
from .nhl_teams_sync import full_sync_teams
from .nhl_players_sync import full_sync
from .mlb_teams_sync import sync_mlb_teams
from .nba_teams_sync import sync_nba_teams
from .nfl_teams_sync import sync_nfl_teams


def run_all_syncs(db: Path) -> Dict[str, int]:
    """Run every sport sync job and return row counts keyed by sync name.

    Args:
        db: Path to the SQLite database file.

    Returns:
        Dict mapping sync name to number of rows upserted.
    """
    return {
        "nhl_teams":   full_sync_teams(db),
        "nhl_players": full_sync(db),
        "mlb_teams":   sync_mlb_teams(db),
        "nba_teams":   sync_nba_teams(db),
        "nfl_teams":   sync_nfl_teams(db),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync all sport data into the local screamsheet database."
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

    try:
        counts = run_all_syncs(db)
    except Exception as exc:
        print(f"ERROR: sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

    failed = False
    for key, count in counts.items():
        print(f"{key}:{count}")
        if count == 0:
            print(f"WARNING: {key} upserted zero rows — possible network failure.", file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

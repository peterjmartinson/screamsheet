"""Unit tests for db_update.run_all_syncs."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from screamsheet.db.db_update import run_all_syncs

_PATCHES = {
    "screamsheet.db.db_update.full_sync_teams": 32,
    "screamsheet.db.db_update.full_sync": 800,
    "screamsheet.db.db_update.sync_mlb_teams": 30,
    "screamsheet.db.db_update.sync_nba_teams": 30,
    "screamsheet.db.db_update.sync_nfl_teams": 32,
}


def _all_mocked():
    """Context manager stack that patches all five sync functions."""
    from contextlib import ExitStack
    stack = ExitStack()
    mocks = {name: stack.enter_context(patch(name, return_value=val)) for name, val in _PATCHES.items()}
    return stack, mocks


class TestRunAllSyncs:
    def test_calls_nhl_teams_sync(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with _all_mocked()[0] as _stack:
            with patch("screamsheet.db.db_update.full_sync_teams", return_value=32) as mock_nhl, \
                 patch("screamsheet.db.db_update.full_sync", return_value=800), \
                 patch("screamsheet.db.db_update.sync_mlb_teams", return_value=30), \
                 patch("screamsheet.db.db_update.sync_nba_teams", return_value=30), \
                 patch("screamsheet.db.db_update.sync_nfl_teams", return_value=32):
                run_all_syncs(db)
        mock_nhl.assert_called_once_with(db)

    def test_calls_mlb_teams_sync(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.db_update.full_sync_teams", return_value=32), \
             patch("screamsheet.db.db_update.full_sync", return_value=800), \
             patch("screamsheet.db.db_update.sync_mlb_teams", return_value=30) as mock_mlb, \
             patch("screamsheet.db.db_update.sync_nba_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nfl_teams", return_value=32):
            run_all_syncs(db)
        mock_mlb.assert_called_once_with(db)

    def test_calls_nba_teams_sync(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.db_update.full_sync_teams", return_value=32), \
             patch("screamsheet.db.db_update.full_sync", return_value=800), \
             patch("screamsheet.db.db_update.sync_mlb_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nba_teams", return_value=30) as mock_nba, \
             patch("screamsheet.db.db_update.sync_nfl_teams", return_value=32):
            run_all_syncs(db)
        mock_nba.assert_called_once_with(db)

    def test_calls_nfl_teams_sync(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.db_update.full_sync_teams", return_value=32), \
             patch("screamsheet.db.db_update.full_sync", return_value=800), \
             patch("screamsheet.db.db_update.sync_mlb_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nba_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nfl_teams", return_value=32) as mock_nfl:
            run_all_syncs(db)
        mock_nfl.assert_called_once_with(db)

    def test_returns_counts_for_all_sports(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.db_update.full_sync_teams", return_value=32), \
             patch("screamsheet.db.db_update.full_sync", return_value=800), \
             patch("screamsheet.db.db_update.sync_mlb_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nba_teams", return_value=30), \
             patch("screamsheet.db.db_update.sync_nfl_teams", return_value=32):
            result = run_all_syncs(db)
        assert result == {
            "nhl_teams": 32,
            "nhl_players": 800,
            "mlb_teams": 30,
            "nba_teams": 30,
            "nfl_teams": 32,
        }

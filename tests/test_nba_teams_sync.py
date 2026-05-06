"""Unit tests for screamsheet.db.nba_teams_sync."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from screamsheet.db.nba_teams_sync import sync_nba_teams

_NBA_TEAMS = [
    {
        "id": 1610612755,
        "full_name": "Philadelphia 76ers",
        "abbreviation": "PHI",
        "nickname": "76ers",
        "city": "Philadelphia",
    },
    {
        "id": 1610612748,
        "full_name": "Miami Heat",
        "abbreviation": "MIA",
        "nickname": "Heat",
        "city": "Miami",
    },
]


class TestSyncNbaTeams:
    def test_returns_count_of_upserted_teams(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nba_teams_sync.nba_api_teams.get_teams", return_value=_NBA_TEAMS):
            count = sync_nba_teams(db)
        assert count == 2

    def test_teams_persisted_in_lookup_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nba_teams_sync.nba_api_teams.get_teams", return_value=_NBA_TEAMS):
            sync_nba_teams(db)
        from screamsheet.db.team_lookup import lookup_team_id_by_name
        result = lookup_team_id_by_name("nba", "Philadelphia 76ers", db)
        assert result == 1610612755

    def test_zero_on_empty_list(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nba_teams_sync.nba_api_teams.get_teams", return_value=[]):
            count = sync_nba_teams(db)
        assert count == 0

"""Unit tests for screamsheet.db.nfl_teams_sync."""
from __future__ import annotations

import pytest
import requests
from pathlib import Path
from unittest.mock import patch

from screamsheet.db.nfl_teams_sync import sync_nfl_teams

_ESPN_RESPONSE = {
    "sports": [
        {
            "leagues": [
                {
                    "teams": [
                        {"team": {"id": "22", "displayName": "Philadelphia Eagles", "abbreviation": "PHI"}},
                        {"team": {"id": "19", "displayName": "New York Giants", "abbreviation": "NYG"}},
                    ]
                }
            ]
        }
    ]
}


class TestSyncNflTeams:
    def test_returns_count_of_upserted_teams(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nfl_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = _ESPN_RESPONSE
            count = sync_nfl_teams(db)
        assert count == 2

    def test_teams_persisted_in_lookup_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nfl_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = _ESPN_RESPONSE
            sync_nfl_teams(db)
        from screamsheet.db.team_lookup import lookup_team_id_by_name
        result = lookup_team_id_by_name("nfl", "Philadelphia Eagles", db)
        assert result == 22

    def test_zero_on_empty_teams_list(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nfl_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {
                "sports": [{"leagues": [{"teams": []}]}]
            }
            count = sync_nfl_teams(db)
        assert count == 0

    def test_raises_on_http_error(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nfl_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404")
            with pytest.raises(requests.HTTPError):
                sync_nfl_teams(db)

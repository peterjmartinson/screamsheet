"""Unit tests for screamsheet.db.mlb_teams_sync."""
from __future__ import annotations

import pytest
import requests
from pathlib import Path
from unittest.mock import patch

from screamsheet.db.mlb_teams_sync import sync_mlb_teams

_MLB_RESPONSE = {
    "teams": [
        {
            "id": 143,
            "name": "Philadelphia Phillies",
            "abbreviation": "PHI",
            "teamName": "Phillies",
            "locationName": "Philadelphia",
        },
        {
            "id": 121,
            "name": "New York Mets",
            "abbreviation": "NYM",
            "teamName": "Mets",
            "locationName": "New York",
        },
    ]
}


class TestSyncMlbTeams:
    def test_returns_count_of_upserted_teams(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.mlb_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = _MLB_RESPONSE
            count = sync_mlb_teams(db)
        assert count == 2

    def test_teams_persisted_in_lookup_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.mlb_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = _MLB_RESPONSE
            sync_mlb_teams(db)
        from screamsheet.db.team_lookup import lookup_team_id_by_name
        result = lookup_team_id_by_name("mlb", "Philadelphia Phillies", db)
        assert result == 143

    def test_zero_on_empty_response(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.mlb_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {"teams": []}
            count = sync_mlb_teams(db)
        assert count == 0

    def test_raises_on_http_error(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.mlb_teams_sync.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("503")
            with pytest.raises(requests.HTTPError):
                sync_mlb_teams(db)

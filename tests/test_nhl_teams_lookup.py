"""Tests for NHL team lookup table population and lookup_team_by_full_name."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

_NHL_STANDINGS_RESPONSE = {
    "standings": [
        {
            "teamAbbrev": {"default": "PHI"},
            "teamName": {"default": "Philadelphia Flyers"},
            "placeName": {"default": "Philadelphia"},
        },
        {
            "teamAbbrev": {"default": "EDM"},
            "teamName": {"default": "Edmonton Oilers"},
            "placeName": {"default": "Edmonton"},
        },
    ]
}

_NHL_SCHEDULE_RESPONSE = {
    "gameWeek": [
        {
            "games": [
                {
                    "homeTeam": {
                        "id": 4,
                        "abbrev": "PHI",
                        "commonName": {"default": "Flyers"},
                        "placeName": {"default": "Philadelphia"},
                    },
                    "awayTeam": {
                        "id": 22,
                        "abbrev": "EDM",
                        "commonName": {"default": "Oilers"},
                        "placeName": {"default": "Edmonton"},
                    },
                }
            ]
        }
    ]
}


def _make_mock_response(data: dict) -> MagicMock:
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = data
    return m


class TestNhlTeamsSyncPopulatesLookupTable:
    def test_full_sync_populates_nhl_teams_table(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nhl_teams_sync.requests.get") as mock_get:
            mock_get.side_effect = [
                _make_mock_response(_NHL_STANDINGS_RESPONSE),
                _make_mock_response(_NHL_SCHEDULE_RESPONSE),
            ]
            from screamsheet.db.nhl_teams_sync import full_sync_teams
            full_sync_teams(db)
        from screamsheet.db.team_lookup import lookup_team_id_by_name
        result = lookup_team_id_by_name("nhl", "Philadelphia Flyers", db)
        assert result == 4

    def test_lookup_team_by_full_name_in_teams_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with patch("screamsheet.db.nhl_teams_sync.requests.get") as mock_get:
            mock_get.side_effect = [
                _make_mock_response(_NHL_STANDINGS_RESPONSE),
                _make_mock_response(_NHL_SCHEDULE_RESPONSE),
            ]
            from screamsheet.db.nhl_teams_sync import full_sync_teams
            full_sync_teams(db)
        from screamsheet.db.nhl_teams_db import lookup_team_by_full_name
        result = lookup_team_by_full_name("Philadelphia Flyers", db)
        assert result is not None
        assert result["team_id"] == 4

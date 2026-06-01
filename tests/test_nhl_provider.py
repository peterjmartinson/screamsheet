"""Unit tests for screamsheet.providers.nhl_provider (NHLDataProvider)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from screamsheet.providers.nhl_provider import NHLDataProvider


@pytest.fixture
def provider():
    return NHLDataProvider()


# ---------------------------------------------------------------------------
# get_game_scores
# ---------------------------------------------------------------------------

class TestNHLGetGameScores:
    def test_returns_list_of_games(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_game_has_required_keys(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        game = result[0]
        for key in ("away_team", "home_team", "away_score", "home_score", "status",
                    "away_abbrev", "home_abbrev", "game_type"):
            assert key in game

    def test_full_team_name_constructed(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["away_team"] == "Philadelphia Flyers"
        assert result[0]["home_team"] == "New Jersey Devils"

    def test_scores_parsed(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["away_score"] == 4
        assert result[0]["home_score"] == 2

    def test_non_final_game_excluded(self, provider, sample_date):
        """Games with state 'PREVIEW' should not appear in results."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "gameWeek": [
                {
                    "games": [
                        {
                            "gameState": "PREVIEW",
                            "startTimeUTC": "2025-03-15T23:00:00Z",
                            "awayTeam": {
                                "id": 4,
                                "placeName": {"default": "Philadelphia"},
                                "commonName": {"default": "Flyers"},
                                "score": None,
                            },
                            "homeTeam": {
                                "id": 1,
                                "placeName": {"default": "New Jersey"},
                                "commonName": {"default": "Devils"},
                                "score": None,
                            },
                        }
                    ]
                }
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result == []

    def test_empty_game_week_returns_empty(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"gameWeek": [{"games": []}]}
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result == []


# ---------------------------------------------------------------------------
# get_standings
# ---------------------------------------------------------------------------

class TestNHLGetStandings:
    def test_returns_dataframe(self, provider, nhl_standings_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_standings_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_standings()
        assert isinstance(result, pd.DataFrame)

    def test_dataframe_has_team_column(self, provider, nhl_standings_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_standings_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_standings()
        assert "team" in result.columns

    def test_dataframe_has_expected_columns(self, provider, nhl_standings_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_standings_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_standings()
        for col in ("conference", "division", "GP", "W", "L"):
            assert col in result.columns


# ---------------------------------------------------------------------------
# _get_game_pk
# ---------------------------------------------------------------------------

class TestNHLGetGamePk:
    def test_returns_game_pk_for_matching_team(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "gameWeek": [
                {
                    "games": [
                        {
                            "id": 2025020001,
                            "gameState": "OFF",
                            "homeTeam": {"id": 4},
                            "awayTeam": {"id": 1},
                        }
                    ]
                }
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            pk = provider._get_game_pk(team_id=4, date=sample_date)
        assert pk == 2025020001

    def test_returns_none_when_no_matching_game(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"gameWeek": [{"games": []}]}
        with patch("requests.get", return_value=mock_resp):
            pk = provider._get_game_pk(team_id=4, date=sample_date)
        assert pk is None

    def test_returns_none_on_request_error(self, provider, sample_date):
        import requests as req_lib
        with patch("requests.get", side_effect=req_lib.exceptions.RequestException("fail")):
            pk = provider._get_game_pk(team_id=4, date=sample_date)
        assert pk is None


# ---------------------------------------------------------------------------
# dump_json (side-effect only — no file written in test)
# ---------------------------------------------------------------------------

class TestNHLDumpJson:
    def test_dump_disabled_by_default(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            with patch.object(provider, "_dump_json") as mock_dump:
                provider.get_game_scores(sample_date)
        mock_dump.assert_not_called()

    def test_dump_called_when_enabled(self, sample_date, nhl_schedule_response):
        provider = NHLDataProvider(dump=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            with patch.object(provider, "_dump_json") as mock_dump:
                provider.get_game_scores(sample_date)
        mock_dump.assert_called_once()


# ---------------------------------------------------------------------------
# get_game_scores — new fields (game_type, abbrev, series_status)
# ---------------------------------------------------------------------------

class TestNHLGetGameScoresNewFields:
    def test_game_type_included_in_regular_season_game(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["game_type"] == 2

    def test_away_abbrev_included_in_game_dict(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["away_abbrev"] == "PHI"

    def test_home_abbrev_included_in_game_dict(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["home_abbrev"] == "NJD"

    def test_regular_season_uses_full_team_name(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["away_team"] == "Philadelphia Flyers"
        assert result[0]["home_team"] == "New Jersey Devils"

    def test_series_status_absent_for_regular_season(self, provider, nhl_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["series_status"] is None

    def test_playoff_game_uses_place_name_only(self, provider, nhl_playoff_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_playoff_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["away_team"] == "Ottawa"
        assert result[0]["home_team"] == "Carolina"

    def test_series_status_present_for_playoff_game(self, provider, nhl_playoff_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_playoff_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["series_status"] is not None

    def test_series_status_has_expected_keys(self, provider, nhl_playoff_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_playoff_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        ss = result[0]["series_status"]
        for key in ("top_seed_abbrev", "top_seed_wins", "bottom_seed_abbrev",
                    "bottom_seed_wins", "needed_to_win"):
            assert key in ss

    def test_series_status_values_correctly_mapped(self, provider, nhl_playoff_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_playoff_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        ss = result[0]["series_status"]
        assert ss["top_seed_abbrev"] == "CAR"
        assert ss["top_seed_wins"] == 2
        assert ss["bottom_seed_abbrev"] == "OTT"
        assert ss["bottom_seed_wins"] == 0
        assert ss["needed_to_win"] == 4


# ---------------------------------------------------------------------------
# has_game
# ---------------------------------------------------------------------------

class TestNHLHasGame:
    def test_returns_true_when_game_exists(self, provider, sample_date):
        with patch.object(provider, "_get_game_pk", return_value=2025020001):
            assert provider.has_game(team_id=4, date=sample_date) is True

    def test_returns_false_when_no_game(self, provider, sample_date):
        with patch.object(provider, "_get_game_pk", return_value=None):
            assert provider.has_game(team_id=4, date=sample_date) is False


# ---------------------------------------------------------------------------
# get_all_teams_for_date
# ---------------------------------------------------------------------------

class TestNHLGetAllTeamsForDate:
    def test_returns_both_teams_from_final_game(
        self, provider, nhl_schedule_response, sample_date
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert (4, "Philadelphia Flyers") in result
        assert (1, "New Jersey Devils") in result

    def test_excludes_preseason_game_type(self, provider, sample_date):
        """game_type == 1 (preseason) must be excluded."""
        preseason_response = {
            "gameWeek": [{"games": [{
                "gameType": 1,
                "gameState": "OFF",
                "startTimeUTC": "2025-03-15T23:00:00Z",
                "awayTeam": {"id": 4, "placeName": {"default": "Philadelphia"},
                             "commonName": {"default": "Flyers"}, "score": 2},
                "homeTeam": {"id": 1, "placeName": {"default": "New Jersey"},
                             "commonName": {"default": "Devils"}, "score": 3},
            }]}]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = preseason_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert result == []

    def test_excludes_non_final_game_state(self, provider, sample_date):
        """Games with state LIVE or PREVIEW must be excluded."""
        live_response = {
            "gameWeek": [{"games": [{
                "gameType": 2,
                "gameState": "LIVE",
                "startTimeUTC": "2025-03-15T23:00:00Z",
                "awayTeam": {"id": 4, "placeName": {"default": "Philadelphia"},
                             "commonName": {"default": "Flyers"}, "score": 1},
                "homeTeam": {"id": 1, "placeName": {"default": "New Jersey"},
                             "commonName": {"default": "Devils"}, "score": 1},
            }]}]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = live_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert result == []

    def test_returns_empty_when_no_games(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"gameWeek": [{"games": []}]}
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert result == []

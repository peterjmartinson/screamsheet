"""Unit tests for screamsheet.providers.mlb_provider (MLBDataProvider)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from screamsheet.providers.mlb_provider import MLBDataProvider


@pytest.fixture
def provider():
    return MLBDataProvider()


# ---------------------------------------------------------------------------
# get_game_scores
# ---------------------------------------------------------------------------

class TestMLBGetGameScores:
    def test_returns_list_of_games(self, provider, mlb_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mlb_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_game_has_required_keys(self, provider, mlb_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mlb_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        game = result[0]
        for key in ("away_team", "home_team", "away_score", "home_score", "status"):
            assert key in game

    def test_correct_teams_parsed(self, provider, mlb_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mlb_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["home_team"] == "Philadelphia Phillies"
        assert result[0]["away_team"] == "New York Mets"

    def test_correct_scores_parsed(self, provider, mlb_schedule_response, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mlb_schedule_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result[0]["home_score"] == 5
        assert result[0]["away_score"] == 3

    def test_empty_dates_returns_empty_list(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"dates": []}
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_game_scores(sample_date)
        assert result == []


# ---------------------------------------------------------------------------
# get_standings
# ---------------------------------------------------------------------------

class TestMLBGetStandings:
    def _mock_get(self, url, **kwargs):
        """Return different mocks for schedule vs. division API calls."""
        mock = MagicMock()
        if "divisions" in url:
            mock.json.return_value = {
                "divisions": [{"name": "National League East"}]
            }
        else:
            mock.json.return_value = {
                "records": [
                    {
                        "division": {"link": "/api/v1/divisions/204"},
                        "teamRecords": [
                            {
                                "team": {"name": "Philadelphia Phillies"},
                                "leagueRecord": {
                                    "wins": 10,
                                    "losses": 5,
                                    "ties": 0,
                                    "pct": ".667",
                                },
                                "divisionRank": "1",
                            }
                        ],
                    }
                ]
            }
        return mock

    def test_returns_dataframe(self, provider):
        with patch("requests.get", side_effect=self._mock_get):
            result = provider.get_standings(season=2025)
        assert isinstance(result, pd.DataFrame)

    def test_dataframe_has_team_column(self, provider):
        with patch("requests.get", side_effect=self._mock_get):
            result = provider.get_standings(season=2025)
        assert "team" in result.columns

    def test_default_season_uses_current_year(self, provider):
        current_year = datetime.now().year
        with patch("requests.get", side_effect=self._mock_get) as mock_get:
            provider.get_standings()
        # The base_url call should include the current year
        first_call_url = mock_get.call_args_list[0][0][0]
        assert str(current_year) in first_call_url

    def test_empty_records_returns_empty_df(self, provider):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"records": []}
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_standings(season=2025)
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ---------------------------------------------------------------------------
# has_game
# ---------------------------------------------------------------------------

class TestMLBHasGame:
    def test_returns_true_when_game_exists(self, provider, sample_date):
        with patch.object(provider, "_get_game_pk", return_value=745528):
            assert provider.has_game(team_id=143, date=sample_date) is True

    def test_returns_false_when_no_game(self, provider, sample_date):
        with patch.object(provider, "_get_game_pk", return_value=None):
            assert provider.has_game(team_id=143, date=sample_date) is False

    def test_returns_false_on_exception(self, provider, sample_date):
        with patch.object(provider, "_get_game_pk", side_effect=Exception("network error")):
            assert provider.has_game(team_id=143, date=sample_date) is False

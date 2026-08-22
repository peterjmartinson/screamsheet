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


# ---------------------------------------------------------------------------
# get_all_teams_for_date
# ---------------------------------------------------------------------------

class TestMLBGetAllTeamsForDate:
    def test_returns_both_teams_from_final_game(
        self, provider, mlb_final_games_response, sample_date
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mlb_final_games_response
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert (143, "Philadelphia Phillies") in result
        assert (121, "New York Mets") in result

    def test_excludes_non_final_game(self, provider, sample_date):
        """In-progress or scheduled games must be excluded."""
        in_progress = {
            "dates": [{"games": [{
                "gameDate": "2025-03-15T18:05:00Z",
                "teams": {
                    "away": {"team": {"id": 121, "name": "New York Mets"}, "score": 1},
                    "home": {"team": {"id": 143, "name": "Philadelphia Phillies"}, "score": 2},
                },
                "status": {"detailedState": "In Progress"},
            }]}]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = in_progress
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert result == []

    def test_returns_empty_when_no_dates(self, provider, sample_date):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"dates": []}
        with patch("requests.get", return_value=mock_resp):
            result = provider.get_all_teams_for_date(sample_date)
        assert result == []


# ---------------------------------------------------------------------------
# get_game_summary & mad_fan
# ---------------------------------------------------------------------------

class TestMLBGetGameSummary:
    def test_loss_uses_regular_summarizer_when_mad_fan_false(self, provider, sample_date):
        fake_raw = {
            "gameData": {"teams": {"home": {"id": 143}, "away": {"id": 121}}},
        }
        fake_extracted = {
            "home_team": "Phillies", "away_team": "Mets",
            "home_score": 2, "away_score": 5, "narrative_snippets": "",
        }
        with patch("screamsheet.providers.extractors.MLBGameExtractor.fetch_raw_data", return_value=fake_raw), \
             patch("screamsheet.providers.extractors.MLBGameExtractor.extract_key_info", return_value=fake_extracted), \
             patch("screamsheet.llm.summary.MLBGameSummarizer.generate_summary", return_value="Regular summary") as mock_gen, \
             patch("screamsheet.llm.summary.MLBFanRantSummarizer.generate_summary") as mock_rant:
            summary = provider.get_game_summary(team_id=143, date=sample_date, is_primary_favorite=True, mad_fan=False)
            assert summary == "Regular summary"
            mock_gen.assert_called_once()
            mock_rant.assert_not_called()

    def test_loss_uses_fan_rant_when_mad_fan_true(self, provider, sample_date):
        fake_raw = {
            "gameData": {"teams": {"home": {"id": 143}, "away": {"id": 121}}},
        }
        fake_extracted = {
            "home_team": "Phillies", "away_team": "Mets",
            "home_score": 2, "away_score": 5, "narrative_snippets": "",
        }
        with patch("screamsheet.providers.extractors.MLBGameExtractor.fetch_raw_data", return_value=fake_raw), \
             patch("screamsheet.providers.extractors.MLBGameExtractor.extract_key_info", return_value=fake_extracted), \
             patch("screamsheet.llm.summary.MLBGameSummarizer.generate_summary") as mock_gen, \
             patch("screamsheet.llm.summary.MLBFanRantSummarizer.generate_summary", return_value="Rant summary") as mock_rant:
            summary = provider.get_game_summary(team_id=143, date=sample_date, is_primary_favorite=True, mad_fan=True)
            assert summary == "Rant summary"
            mock_rant.assert_called_once()
            mock_gen.assert_not_called()

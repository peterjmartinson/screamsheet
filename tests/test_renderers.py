"""Unit tests for renderer sections (GameScoresSection, StandingsSection, BoxScoreSection, WeatherSection)."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from reportlab.platypus import Table, Spacer, Paragraph

from screamsheet.renderers.game_scores import GameScoresSection
from screamsheet.renderers.standings import StandingsSection
from screamsheet.renderers.box_score import BoxScoreSection
from screamsheet.renderers.weather import WeatherSection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_provider_with_scores(scores):
    p = MagicMock()
    p.get_game_scores.return_value = scores
    return p


def _fake_provider_with_standings(df):
    p = MagicMock()
    p.get_standings.return_value = df
    return p


# ---------------------------------------------------------------------------
# GameScoresSection
# ---------------------------------------------------------------------------

class TestGameScoresSection:
    @pytest.fixture
    def games(self):
        return [
            {"away_team": "NY Mets", "home_team": "Philadelphia Phillies",
             "away_score": 3, "home_score": 5, "status": "Final", "gameDate": "2025-03-15"},
            {"away_team": "Boston Red Sox", "home_team": "NY Yankees",
             "away_score": 2, "home_score": 4, "status": "Final", "gameDate": "2025-03-15"},
        ]

    def test_fetch_data_stores_data(self, games):
        provider = _fake_provider_with_scores(games)
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.fetch_data()
        assert sec.data == games

    def test_render_returns_nonempty_list(self, games):
        provider = _fake_provider_with_scores(games)
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = games
        result = sec.render()
        assert len(result) > 0

    def test_render_returns_empty_when_no_data(self):
        provider = _fake_provider_with_scores([])
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = []
        result = sec.render()
        assert result == []

    def test_render_contains_table(self, games):
        provider = _fake_provider_with_scores(games)
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = games
        result = sec.render()
        assert any(isinstance(el, Table) for el in result)

    def test_has_content_false_when_empty(self):
        provider = _fake_provider_with_scores([])
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = []
        assert sec.has_content() is False

    def test_has_content_true_with_games(self, games):
        provider = _fake_provider_with_scores(games)
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = games
        assert sec.has_content() is True


# ---------------------------------------------------------------------------
# StandingsSection
# ---------------------------------------------------------------------------

class TestStandingsSection:
    def test_fetch_data_stores_dataframe(self, mlb_standings_df):
        provider = _fake_provider_with_standings(mlb_standings_df)
        sec = StandingsSection("Standings", provider)
        sec.fetch_data()
        assert sec.data is not None

    def test_render_returns_nonempty_list_for_mlb(self, mlb_standings_df):
        provider = _fake_provider_with_standings(mlb_standings_df)
        sec = StandingsSection("Standings", provider)
        sec.data = mlb_standings_df
        result = sec.render()
        assert len(result) > 0

    def test_render_returns_table_for_nhl(self, nhl_standings_df):
        provider = _fake_provider_with_standings(nhl_standings_df)
        sec = StandingsSection("Standings", provider)
        sec.data = nhl_standings_df
        result = sec.render()
        assert any(isinstance(el, Table) for el in result)

    def test_render_returns_empty_for_empty_df(self):
        empty_df = pd.DataFrame()
        provider = _fake_provider_with_standings(empty_df)
        sec = StandingsSection("Standings", provider)
        sec.data = empty_df
        result = sec.render()
        assert result == []

    def test_render_returns_empty_for_none_data(self):
        provider = _fake_provider_with_standings(None)
        sec = StandingsSection("Standings", provider)
        sec.data = None
        # Trigger fetch which returns None
        with patch.object(sec, "fetch_data"):
            result = sec.render()
        assert result == []


# ---------------------------------------------------------------------------
# BoxScoreSection
# ---------------------------------------------------------------------------

class TestBoxScoreSection:
    @pytest.fixture
    def mlb_box_data(self):
        return {
            "batting_stats": [
                {"name": "Bryce Harper", "AB": 4, "R": 1, "H": 2, "HR": 1, "RBI": 2, "BB": 0, "SO": 1}
            ],
            "pitching_stats": [
                {"name": "Zack Wheeler", "IP": "7.0", "H": 4, "R": 1, "ER": 1, "BB": 1, "SO": 8}
            ],
        }

    def test_fetch_data_calls_provider(self, mlb_box_data):
        provider = MagicMock()
        provider.get_box_score.return_value = mlb_box_data
        sec = BoxScoreSection("Box Score", provider, team_id=143, date=datetime(2025, 3, 15))
        sec.fetch_data()
        provider.get_box_score.assert_called_once_with(143, datetime(2025, 3, 15))

    def test_render_returns_empty_when_no_data(self):
        provider = MagicMock()
        provider.get_box_score.return_value = None
        provider.get_game_summary.return_value = None
        sec = BoxScoreSection("Box Score", provider, team_id=143, date=datetime(2025, 3, 15))
        sec.data = None
        with patch.object(sec, "fetch_data"):
            result = sec.render()
        assert result == []

    def test_render_returns_flowables_for_mlb_data(self, mlb_box_data):
        provider = MagicMock()
        provider.get_box_score.return_value = mlb_box_data
        provider.get_game_summary.return_value = "The Phillies dominated."
        sec = BoxScoreSection("Box Score", provider, team_id=143, date=datetime(2025, 3, 15))
        sec.data = mlb_box_data
        result = sec.render()
        assert len(result) > 0


# ---------------------------------------------------------------------------
# WeatherSection
# ---------------------------------------------------------------------------

class TestWeatherSection:
    @pytest.fixture
    def forecast_data(self):
        return [
            {
                "day": "Today",
                "location": "Bryn Mawr, PA",
                "description": "Sunny",
                "icon_url": "/path/to/icon.png",
                "max_temp": 72,
                "min_temp": 55,
            }
        ]

    def test_fetch_data_stores_data(self, forecast_data, sample_date):
        sec = WeatherSection("Weather", date=sample_date)
        with patch.object(sec.provider, "get_5_day_forecast", return_value=forecast_data):
            sec.fetch_data()
        assert sec.data == forecast_data

    def test_render_returns_empty_when_no_data(self, sample_date):
        sec = WeatherSection("Weather", date=sample_date)
        sec.data = []
        with patch.object(sec, "fetch_data"):  # prevent re-fetch hitting real network
            result = sec.render()
        assert result == []

    def test_render_returns_flowable_with_data(self, forecast_data, sample_date):
        sec = WeatherSection("Weather", date=sample_date)
        sec.data = forecast_data
        # icons don't exist on disk; patch Image to avoid file-not-found
        with patch("screamsheet.renderers.weather.Image", MagicMock()):
            result = sec.render()
        assert len(result) > 0

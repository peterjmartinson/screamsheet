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
# GameScoresSection — playoff series badge
# ---------------------------------------------------------------------------

def _make_series_status(top_abbrev, top_wins, bottom_abbrev, bottom_wins, needed=4):
    return {
        "top_seed_abbrev": top_abbrev,
        "top_seed_wins": top_wins,
        "bottom_seed_abbrev": bottom_abbrev,
        "bottom_seed_wins": bottom_wins,
        "needed_to_win": needed,
    }


def _playoff_game(away_abbrev, home_abbrev, away_score, home_score, series_status):
    return {
        "away_team": away_abbrev.lower().capitalize(),
        "home_team": home_abbrev.lower().capitalize(),
        "away_abbrev": away_abbrev,
        "home_abbrev": home_abbrev,
        "away_score": away_score,
        "home_score": home_score,
        "status": "OFF",
        "game_type": 3,
        "series_status": series_status,
        "gameDate": "2026-04-20T23:30:00Z",
    }


def _regular_game():
    return {
        "away_team": "Philadelphia Flyers",
        "home_team": "New Jersey Devils",
        "away_abbrev": "PHI",
        "home_abbrev": "NJD",
        "away_score": 4,
        "home_score": 2,
        "status": "OFF",
        "game_type": 2,
        "series_status": None,
        "gameDate": "2025-03-15T23:00:00Z",
    }


def _rendered_text(result) -> str:
    """Flatten all ReportLab flowable text from a render() result."""
    import re
    from reportlab.platypus import Paragraph

    texts = []
    for el in result:
        if isinstance(el, Paragraph):
            texts.append(el.text)
        elif isinstance(el, Table):
            for row in el._cellvalues:
                for cell in row:
                    if isinstance(cell, list):
                        for item in cell:
                            if isinstance(item, Paragraph):
                                texts.append(item.text)
                            elif isinstance(item, Table):
                                for r2 in item._cellvalues:
                                    for c2 in r2:
                                        if isinstance(c2, Paragraph):
                                            texts.append(c2.text)
                                        elif isinstance(c2, str):
                                            texts.append(c2)
                    elif isinstance(cell, Paragraph):
                        texts.append(cell.text)
                    elif isinstance(cell, str):
                        texts.append(cell)
    return " ".join(texts)


class TestGameScoresSectionPlayoff:
    def test_no_badge_rendered_for_regular_season_game(self):
        game = _regular_game()
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2025, 3, 15))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(leads" not in text and "(won" not in text and "(tied" not in text

    def test_badge_on_series_leader_row_when_away_leads(self):
        # OTT is top seed leading 2-0; OTT is away
        ss = _make_series_status("OTT", 2, "CAR", 0)
        game = _playoff_game("OTT", "CAR", 4, 2, ss)
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2026, 4, 20))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(leads 2-0)" in text

    def test_badge_on_series_leader_row_when_home_leads(self):
        # CAR is top seed leading 2-0; CAR is home
        ss = _make_series_status("CAR", 2, "OTT", 0)
        game = _playoff_game("OTT", "CAR", 2, 3, ss)
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2026, 4, 20))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(leads 2-0)" in text

    def test_badge_text_tied_when_series_tied(self):
        ss = _make_series_status("CAR", 1, "OTT", 1)
        game = _playoff_game("OTT", "CAR", 2, 3, ss)
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2026, 4, 20))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(tied 1-1)" in text

    def test_badge_text_won_when_top_seed_clinches(self):
        ss = _make_series_status("CAR", 4, "OTT", 1)
        game = _playoff_game("OTT", "CAR", 1, 4, ss)
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2026, 4, 20))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(won 4-1)" in text

    def test_badge_text_won_when_bottom_seed_clinches(self):
        ss = _make_series_status("CAR", 1, "OTT", 4)
        game = _playoff_game("OTT", "CAR", 3, 2, ss)
        provider = _fake_provider_with_scores([game])
        sec = GameScoresSection("Scores", provider, date=datetime(2026, 4, 20))
        sec.data = [game]
        result = sec.render()
        text = _rendered_text(result)
        assert "(won 4-1)" in text


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

    def test_render_first_element_is_location_paragraph(self, forecast_data, sample_date):
        from reportlab.platypus import Paragraph
        sec = WeatherSection("Weather", date=sample_date, location_name="Washington, DC")
        sec.data = forecast_data
        with patch("screamsheet.renderers.weather.Image", MagicMock()):
            result = sec.render()
        assert isinstance(result[0], Paragraph)
        assert "Washington, DC" in result[0].text

    def test_render_location_paragraph_precedes_table(self, forecast_data, sample_date):
        from reportlab.platypus import Paragraph, Table
        sec = WeatherSection("Weather", date=sample_date, location_name="Bryn Mawr, PA")
        sec.data = forecast_data
        with patch("screamsheet.renderers.weather.Image", MagicMock()):
            result = sec.render()
        assert isinstance(result[0], Paragraph)
        assert isinstance(result[1], Table)

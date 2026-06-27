"""Unit tests for FIFAWorldCupScreamsheet."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.sports.worldcup import FIFAWorldCupScreamsheet
from screamsheet.providers.worldcup26_provider import PRIORITY_TEAM_NAMES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_date():
    return datetime(2026, 6, 25)


def _completed_game(fixture_id: int, home: str, away: str, status: str = "FT") -> dict:
    return {
        "fixture_id": fixture_id,
        "home_team": home,
        "away_team": away,
        "home_score": 2,
        "away_score": 1,
        "home_penalty": None,
        "away_penalty": None,
        "status_short": status,
        "raw": {},
    }


# ---------------------------------------------------------------------------
# Featured fixture selection
# ---------------------------------------------------------------------------

class TestResolveFeatureFixture:
    def test_selects_usa_game_first(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        games = [
            _completed_game(1, "Mexico", "Brazil"),
            _completed_game(2, "USA", "England"),
            _completed_game(3, "France", "Germany"),
        ]
        with patch.object(sheet.provider, "get_game_scores", return_value=games):
            featured = sheet._resolve_featured_fixture()
        assert featured["fixture_id"] == 2

    def test_selects_argentina_if_no_usa(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        games = [
            _completed_game(1, "Mexico", "Brazil"),
            _completed_game(2, "Argentina", "France"),
        ]
        with patch.object(sheet.provider, "get_game_scores", return_value=games):
            featured = sheet._resolve_featured_fixture()
        assert featured["fixture_id"] == 2

    def test_selects_portugal_if_no_usa_argentina(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        games = [
            _completed_game(1, "Mexico", "Brazil"),
            _completed_game(2, "Portugal", "Germany"),
        ]
        with patch.object(sheet.provider, "get_game_scores", return_value=games):
            featured = sheet._resolve_featured_fixture()
        assert featured["fixture_id"] == 2

    def test_falls_back_to_random_when_no_priority_team(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        games = [
            _completed_game(1, "Mexico", "Brazil"),
            _completed_game(2, "France", "Germany"),
        ]
        with patch.object(sheet.provider, "get_game_scores", return_value=games):
            featured = sheet._resolve_featured_fixture()
        # Result is one of the two games (random)
        assert featured["fixture_id"] in (1, 2)

    def test_returns_none_when_no_completed_games(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        with patch.object(sheet.provider, "get_game_scores", return_value=[]):
            featured = sheet._resolve_featured_fixture()
        assert featured is None

    def test_united_states_name_also_matched(self, sample_date):
        """'United States' is a valid alias for the USA priority team."""
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        games = [_completed_game(5, "United States", "Canada")]
        with patch.object(sheet.provider, "get_game_scores", return_value=games):
            featured = sheet._resolve_featured_fixture()
        assert featured["fixture_id"] == 5


# ---------------------------------------------------------------------------
# build_sections
# ---------------------------------------------------------------------------

class TestBuildSections:
    def test_three_sections_when_games_exist(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        game = _completed_game(99, "USA", "England")
        with patch.object(sheet.provider, "get_game_scores", return_value=[game]):
            with patch.object(sheet.provider, "get_standings", return_value=[]):
                sections = sheet.build_sections()
        assert len(sections) == 3

    def test_two_sections_when_no_completed_games(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        with patch.object(sheet.provider, "get_game_scores", return_value=[]):
            with patch.object(sheet.provider, "get_standings", return_value=[]):
                sections = sheet.build_sections()
        # No completed game → no box score section
        assert len(sections) == 2

    def test_box_score_section_has_back_page_slot(self, sample_date):
        sheet = FIFAWorldCupScreamsheet("out.pdf", date=sample_date)
        game = _completed_game(99, "USA", "England")
        with patch.object(sheet.provider, "get_game_scores", return_value=[game]):
            with patch.object(sheet.provider, "get_standings", return_value=[]):
                sections = sheet.build_sections()
        back_sections = [s for s in sections if getattr(s, "page_slot", "front") == "back"]
        assert len(back_sections) == 1

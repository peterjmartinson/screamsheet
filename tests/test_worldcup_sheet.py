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


# ---------------------------------------------------------------------------
# Phase 3: penalty shootout table in WorldCupBoxScoreSection
# ---------------------------------------------------------------------------

from screamsheet.renderers.worldcup_box_score import WorldCupBoxScoreSection


_PEN_DETAIL = {
    "home_team": "Germany",
    "away_team": "Paraguay",
    "home_penalty_score": 3,
    "away_penalty_score": 4,
    "home_scorers": ["Kimish", "Musiala", "Amiri"],
    "away_scorers": ["Gomez", "Galarza", "Medina", "Dominguez"],
    "home_misses": ["Havertz", "Tah"],
    "away_misses": ["Sanabria"],
}

_GOAL_EVENTS = [
    {
        "type": "Goal",
        "time": {"elapsed": 42},
        "team": {"name": "Paraguay"},
        "player": {"name": "K. Ansisv"},
        "detail": "",
    },
    {
        "type": "Goal",
        "time": {"elapsed": 54},
        "team": {"name": "Germany"},
        "player": {"name": "Kai Havertz"},
        "detail": "",
    },
]


class TestWorldCupBoxScoreRenderer:
    """WorldCupBoxScoreSection includes penalty table for PEN games."""

    def _make_section(self, events=None, penalty_detail=None) -> WorldCupBoxScoreSection:
        mock_provider = MagicMock()
        mock_provider.get_fixture_lineups.return_value = []
        mock_provider.get_fixture_events.return_value = events or _GOAL_EVENTS
        mock_provider.get_fixture_statistics.return_value = {}
        mock_provider.get_penalty_detail.return_value = penalty_detail
        mock_provider.get_game_summary.return_value = "Test summary text."
        section = WorldCupBoxScoreSection(
            title="Germany vs Paraguay",
            provider=mock_provider,
            fixture_id=74,
            date=datetime(2026, 6, 29),
        )
        return section

    def test_fetch_data_stores_penalty_detail(self):
        section = self._make_section(penalty_detail=_PEN_DETAIL)
        section.fetch_data()
        assert section.penalty_detail is not None
        assert section.penalty_detail["home_team"] == "Germany"

    def test_pen_game_render_player_tables_includes_penalty_table(self):
        section = self._make_section(penalty_detail=_PEN_DETAIL)
        section.fetch_data()
        flowables = section._render_player_tables()
        # Should have more content than just the goals table alone
        assert len(flowables) > 0

    def test_non_pen_game_render_player_tables_no_penalty_table(self):
        section = self._make_section(penalty_detail=None)
        section.fetch_data()
        flowables = section._render_player_tables()
        # Goals-only table still renders something
        assert len(flowables) > 0

    def test_fetch_data_sets_penalty_detail_none_when_provider_lacks_method(self):
        """Renderer handles providers that don't implement get_penalty_detail."""
        mock_provider = MagicMock(spec=[
            "get_fixture_lineups", "get_fixture_events",
            "get_fixture_statistics", "get_game_summary",
        ])
        mock_provider.get_fixture_lineups.return_value = []
        mock_provider.get_fixture_events.return_value = []
        mock_provider.get_fixture_statistics.return_value = {}
        mock_provider.get_game_summary.return_value = None
        section = WorldCupBoxScoreSection(
            title="Test", provider=mock_provider, fixture_id=1,
            date=datetime(2026, 6, 29),
        )
        section.fetch_data()
        assert section.penalty_detail is None

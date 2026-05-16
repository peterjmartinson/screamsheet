"""Unit tests for screamsheet.sports.base_sports (SportsScreamsheet) and concrete subclasses."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.sports.base_sports import SportsScreamsheet
from screamsheet.sports.mlb import MLBScreamsheet
from screamsheet.sports.nhl import NHLScreamsheet
from screamsheet.renderers.game_scores import GameScoresSection
from screamsheet.renderers.standings import StandingsSection
from screamsheet.renderers.box_score import BoxScoreSection


# ---------------------------------------------------------------------------
# SportsScreamsheet — title and section structure
# ---------------------------------------------------------------------------

class TestSportsScreamseetTitle:
    def test_mlb_title(self):
        s = MLBScreamsheet("out.pdf")
        assert s.get_title() == "MLB Screamsheet"

    def test_nhl_title(self):
        s = NHLScreamsheet("out.pdf")
        assert s.get_title() == "NHL Screamsheet"


class TestSportsScreamseetBuildSections:
    def test_always_includes_game_scores_section(self):
        s = MLBScreamsheet("out.pdf")
        sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert GameScoresSection in types

    def test_always_includes_standings_section(self):
        s = MLBScreamsheet("out.pdf")
        sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert StandingsSection in types

    def test_no_box_score_when_no_team(self):
        s = MLBScreamsheet("out.pdf")
        sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection not in types

    def test_box_score_added_when_team_set(self):
        s = MLBScreamsheet("out.pdf", team_id=143, team_name="Philadelphia Phillies")
        with patch.object(s.provider, "has_game", return_value=True):
            sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection in types

    def test_section_count_without_team(self):
        s = MLBScreamsheet("out.pdf")
        sections = s.build_sections()
        assert len(sections) == 2

    def test_section_count_with_team(self):
        s = MLBScreamsheet("out.pdf", team_id=143, team_name="Philadelphia Phillies")
        with patch.object(s.provider, "has_game", return_value=True):
            sections = s.build_sections()
        assert len(sections) == 3


# ---------------------------------------------------------------------------
# MLBScreamsheet
# ---------------------------------------------------------------------------

class TestMLBScreamsheet:
    def test_sport_name(self):
        s = MLBScreamsheet("out.pdf")
        assert s.sport_name == "MLB"

    def test_provider_type(self):
        from screamsheet.providers.mlb_provider import MLBDataProvider
        s = MLBScreamsheet("out.pdf")
        assert isinstance(s.provider, MLBDataProvider)

    def test_team_id_stored(self):
        s = MLBScreamsheet("out.pdf", team_id=143)
        assert s.team_id == 143

    def test_team_name_stored(self):
        s = MLBScreamsheet("out.pdf", team_name="Philadelphia Phillies")
        assert s.team_name == "Philadelphia Phillies"


# ---------------------------------------------------------------------------
# NHLScreamsheet
# ---------------------------------------------------------------------------

class TestNHLScreamsheet:
    def test_sport_name(self):
        s = NHLScreamsheet("out.pdf")
        assert s.sport_name == "NHL"

    def test_provider_type(self):
        from screamsheet.providers.nhl_provider import NHLDataProvider
        s = NHLScreamsheet("out.pdf")
        assert isinstance(s.provider, NHLDataProvider)

    def test_team_id_stored(self):
        s = NHLScreamsheet("out.pdf", team_id=4)
        assert s.team_id == 4


# ---------------------------------------------------------------------------
# display_date — sections always use game date, not display date
# ---------------------------------------------------------------------------

class TestSportsScreamseetDisplayDate:
    def test_game_scores_section_uses_game_date_not_display_date(self):
        """GameScoresSection receives self.date (yesterday) even when display_date is set."""
        game_date = datetime(2026, 3, 21)
        run_date = datetime(2026, 3, 22)
        s = NHLScreamsheet("out.pdf", date=game_date, display_date=run_date)
        sections = s.build_sections()
        gs = next(sec for sec in sections if isinstance(sec, GameScoresSection))
        assert gs.date == game_date

    def test_box_score_section_uses_game_date_not_display_date(self):
        """BoxScoreSection receives self.date (yesterday) even when display_date is set."""
        game_date = datetime(2026, 3, 21)
        run_date = datetime(2026, 3, 22)
        s = MLBScreamsheet("out.pdf", team_id=143, team_name="Philadelphia Phillies",
                           date=game_date, display_date=run_date)
        sections = s.build_sections()
        bs = next(sec for sec in sections if isinstance(sec, BoxScoreSection))
        assert bs.date == game_date


# ---------------------------------------------------------------------------
# favorite_teams priority list — _resolve_featured_team
# ---------------------------------------------------------------------------

class TestResolveFeaturedTeam:
    def test_first_team_featured_when_it_has_game(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", return_value=True):
            result = s._resolve_featured_team()
        assert result == (4, "Philadelphia Flyers")

    def test_second_team_featured_when_first_has_no_game(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", side_effect=[False, True]):
            result = s._resolve_featured_team()
        assert result == (7, "Buffalo Sabres")

    def test_returns_none_when_no_team_has_game(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", return_value=False):
            result = s._resolve_featured_team()
        assert result is None

    def test_returns_none_when_list_is_empty(self):
        s = NHLScreamsheet("out.pdf", favorite_teams=[])
        result = s._resolve_featured_team()
        assert result is None

    def test_returns_none_when_no_teams_set(self):
        s = NHLScreamsheet("out.pdf")
        result = s._resolve_featured_team()
        assert result is None


class TestFavoriteTeamsBuildSections:
    def test_box_score_added_for_first_team_with_game(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", return_value=True):
            sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection in types

    def test_box_score_uses_resolved_team_id(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", side_effect=[False, True]):
            sections = s.build_sections()
        bs = next(sec for sec in sections if isinstance(sec, BoxScoreSection))
        assert bs.team_id == 7

    def test_no_box_score_when_no_team_has_game(self):
        s = NHLScreamsheet(
            "out.pdf",
            favorite_teams=[(4, "Philadelphia Flyers"), (7, "Buffalo Sabres")],
        )
        with patch.object(s.provider, "has_game", return_value=False):
            sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection not in types


class TestBackwardCompatSingleTeam:
    def test_team_id_and_name_still_work(self):
        """Old-style team_id + team_name args must still produce a BoxScoreSection."""
        s = MLBScreamsheet("out.pdf", team_id=143, team_name="Philadelphia Phillies")
        with patch.object(s.provider, "has_game", return_value=True):
            sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection in types

    def test_team_id_stored_on_sheet(self):
        s = NHLScreamsheet("out.pdf", team_id=4, team_name="Philadelphia Flyers")
        assert s.team_id == 4

    def test_team_name_stored_on_sheet(self):
        s = NHLScreamsheet("out.pdf", team_id=4, team_name="Philadelphia Flyers")
        assert s.team_name == "Philadelphia Flyers"

    def test_subtitle_shows_display_date_not_game_date(self):
        """get_date_string() returns display_date when set, not game date."""
        game_date = datetime(2026, 3, 21)
        run_date = datetime(2026, 3, 22)
        s = NHLScreamsheet("out.pdf", date=game_date, display_date=run_date)
        assert s.get_date_string() == "March 22, 2026"


# ---------------------------------------------------------------------------
# Two-page enforcement
# ---------------------------------------------------------------------------

import re
from typing import List as _List
from screamsheet.base.data_provider import DataProvider
from screamsheet.base.section import Section


class _StubProvider(DataProvider):
    def get_game_scores(self, date):
        return []

    def get_standings(self):
        return None


class _BulkyFrontSection(Section):
    """Generates far more content than fits on one page."""

    def fetch_data(self):
        self.data = list(range(200))

    def render(self):
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        out = []
        for i in range(200):
            out.append(Paragraph(f"Front content row {i}", styles["Normal"]))
            out.append(Spacer(1, 6))
        return out


class _MinimalBackSection(Section):
    """Represents a back-page section (e.g. box score)."""

    def __init__(self, title: str):
        super().__init__(title)
        self.page_slot = "back"

    def fetch_data(self):
        self.data = {"content": True}

    def render(self):
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        return [Paragraph("Back page content.", styles["Normal"])]


class _StubSportsSheet(SportsScreamsheet):
    def __init__(self, output_filename: str, sections: _List[Section]):
        self._test_sections = sections
        super().__init__("Test", output_filename)

    def create_provider(self) -> DataProvider:
        return _StubProvider()

    def build_sections(self) -> _List[Section]:
        return self._test_sections


def _count_pdf_pages(path: str) -> int:
    """Count pages in a ReportLab PDF by scanning for page dictionary objects."""
    with open(path, "rb") as f:
        content = f.read()
    return len(re.findall(rb"/Type\s*/Page[^s]", content))


class TestTwoPageEnforcement:
    def test_box_score_section_has_back_page_slot(self):
        """BoxScoreSection must declare page_slot='back'."""
        provider = MagicMock()
        section = BoxScoreSection(
            title="Test", provider=provider,
            team_id=143, date=datetime(2026, 5, 14),
        )
        assert section.page_slot == "back"

    def test_box_score_render_does_not_start_with_page_break(self):
        """BoxScoreSection.render() must not open with a PageBreak flowable."""
        from reportlab.platypus import PageBreak
        provider = MagicMock()
        provider.get_box_score.return_value = {"batting_stats": [], "pitching_stats": []}
        provider.get_game_summary.return_value = "Summary text."
        section = BoxScoreSection(
            title="Test", provider=provider,
            team_id=143, date=datetime(2026, 5, 14),
        )
        elements = section.render()
        assert not any(isinstance(e, PageBreak) for e in elements)

    def test_overflow_front_content_stays_on_page_one(self, tmp_path):
        """Front content that overflows is shrunk to fit; PDF has exactly 2 pages."""
        pdf_path = str(tmp_path / "overflow.pdf")
        sheet = _StubSportsSheet(pdf_path, [
            _BulkyFrontSection("bulk"),
            _MinimalBackSection("back"),
        ])
        sheet.generate()
        assert _count_pdf_pages(pdf_path) == 2

    def test_no_back_section_produces_single_page(self, tmp_path):
        """When there is no back-page content the PDF is exactly 1 page."""
        pdf_path = str(tmp_path / "front_only.pdf")
        sheet = _StubSportsSheet(pdf_path, [_BulkyFrontSection("bulk")])
        sheet.generate()
        assert _count_pdf_pages(pdf_path) == 1

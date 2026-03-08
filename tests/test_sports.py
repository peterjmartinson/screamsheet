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
        sections = s.build_sections()
        types = [type(sec) for sec in sections]
        assert BoxScoreSection in types

    def test_section_count_without_team(self):
        s = MLBScreamsheet("out.pdf")
        sections = s.build_sections()
        assert len(sections) == 2

    def test_section_count_with_team(self):
        s = MLBScreamsheet("out.pdf", team_id=143, team_name="Philadelphia Phillies")
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

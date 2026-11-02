"""Unit tests for SoccerScreamsheet, components, factory, and runner integration."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from screamsheet.components.box_score.soccer import SoccerBoxScoreComponent
from screamsheet.components.game_scores.soccer import SoccerGameScoresComponent
from screamsheet.components.standings.soccer import SoccerStandingsComponent
from screamsheet.factory import ScreamsheetFactory
from screamsheet.order import OutputOrderOptions, ScreamsheetOrder, SoccerOrderOptions, TeamEntry
from screamsheet.runner import run_order
from screamsheet.sports.soccer import SoccerScreamsheet


@pytest.fixture
def sample_date():
    return datetime(2026, 11, 1)


class TestSoccerScreamsheet:
    def test_init_defaults(self, tmp_path, sample_date):
        out_file = str(tmp_path / "soccer.pdf")
        sheet = SoccerScreamsheet(out_file, date=sample_date)
        assert sheet.get_title() == "Football Screamsheet"
        assert sheet.branding == "DISTRACTEDFORTUNE.COM/SCREAMSHEET"
        assert len(sheet.favorite_teams) == 2
        assert sheet.favorite_teams[0][1] == "Al-Nassr"
        assert sheet.favorite_teams[1][1] == "Portugal"

    def test_build_sections(self, tmp_path, sample_date):
        out_file = str(tmp_path / "soccer.pdf")
        sheet = SoccerScreamsheet(out_file, date=sample_date)
        sections = sheet.build_sections()
        assert len(sections) == 3
        types = [type(s) for s in sections]
        assert SoccerGameScoresComponent in types
        assert SoccerStandingsComponent in types
        assert SoccerBoxScoreComponent in types

    def test_generate_pdf_sample_mode(self, tmp_path, sample_date):
        out_file = str(tmp_path / "soccer_sample.pdf")
        sheet = SoccerScreamsheet(out_file, date=sample_date)
        generated_path = sheet.generate()
        assert os.path.exists(generated_path)
        assert os.path.getsize(generated_path) > 1000

    def test_generate_pdf_offday_fallback(self, tmp_path, sample_date):
        out_file = str(tmp_path / "soccer_offday.pdf")
        sheet = SoccerScreamsheet(out_file, date=sample_date)
        # Mock provider returning empty scores (no games yesterday)
        with patch.object(sheet.provider, "get_game_scores", return_value=[]):
            generated_path = sheet.generate()
            assert os.path.exists(generated_path)
            assert os.path.getsize(generated_path) > 1000


class TestSoccerComponents:
    def test_game_scores_component_render(self, sample_date):
        comp = SoccerGameScoresComponent(date=sample_date)
        flowables = comp.render()
        assert len(flowables) > 0

    def test_standings_component_render(self, sample_date):
        comp = SoccerStandingsComponent(date=sample_date)
        flowables = comp.render()
        assert len(flowables) > 0

    def test_box_score_component_render(self, sample_date):
        comp = SoccerBoxScoreComponent(date=sample_date)
        flowables = comp.render()
        assert len(flowables) > 0


class TestFactoryAndRunner:
    def test_factory_creation(self, tmp_path, sample_date):
        out_file = str(tmp_path / "factory_soccer.pdf")
        sheet = ScreamsheetFactory.create_soccer_screamsheet(
            output_filename=out_file,
            date=sample_date,
        )
        assert isinstance(sheet, SoccerScreamsheet)
        path = sheet.generate()
        assert os.path.exists(path)

    def test_run_order_with_soccer(self, tmp_path, sample_date):
        out_dir = str(tmp_path)
        order = ScreamsheetOrder(
            output=OutputOrderOptions(directory=out_dir),
            soccer=SoccerOrderOptions(
                favorite_teams=[TeamEntry(id=1005, name="Al-Nassr")],
            ),
        )
        res = run_order(order, today=sample_date)
        assert len(res.errors) == 0
        assert len(res.sheets_generated) == 1
        assert "SOCCER" in res.sheets_generated[0]
        assert (tmp_path / res.sheets_generated[0]).exists()

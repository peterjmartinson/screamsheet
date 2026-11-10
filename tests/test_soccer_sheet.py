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


@pytest.fixture(autouse=True)
def disable_live_api(monkeypatch):
    """Ensure unit tests run in offline sample mode without consuming API quota."""
    monkeypatch.delenv("APISPORTS_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("FIFA_API_KEY", raising=False)


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


class TestConfigurableSoccerAndDB:
    def test_soccer_db_resolution(self, tmp_path):
        from screamsheet.db import (
            resolve_soccer_league,
            resolve_soccer_player,
            resolve_soccer_team,
            seed_soccer_db,
        )

        db_file = tmp_path / "soccer_test.db"
        count = seed_soccer_db(db_path=db_file)
        assert count > 30

        # Leagues
        npfl = resolve_soccer_league("NPFL", db_path=db_file, allow_api_fallback=False)
        assert npfl is not None
        assert npfl["league_id"] == 399

        afcon = resolve_soccer_league("afcon", db_path=db_file, allow_api_fallback=False)
        assert afcon is not None
        assert afcon["league_id"] == 6

        # Teams
        enyimba = resolve_soccer_team("Peoples Elephant", db_path=db_file, allow_api_fallback=False)
        assert enyimba is not None
        assert enyimba["team_id"] == 5203
        assert enyimba["full_name"] == "Enyimba"

        nigeria = resolve_soccer_team("Super Eagles", db_path=db_file, allow_api_fallback=False)
        assert nigeria is not None
        assert nigeria["team_id"] == 19
        assert nigeria["full_name"] == "Nigeria"

        arsenal = resolve_soccer_team("Gunners", db_path=db_file, allow_api_fallback=False)
        assert arsenal is not None
        assert arsenal["team_id"] == 42

        # Players
        osimhen = resolve_soccer_player("Osimhen", db_path=db_file, allow_api_fallback=False)
        assert osimhen is not None
        assert osimhen["player_id"] == 2393
        assert osimhen["full_name"] == "Victor Osimhen"

        cr7 = resolve_soccer_player("CR7", db_path=db_file, allow_api_fallback=False)
        assert cr7 is not None
        assert cr7["player_id"] == 874

    def test_nigeria_subscriber_configuration(self, tmp_path, sample_date):
        from screamsheet.order import build_custom_sheet_options_from_dict

        raw_yaml = {
            "screamsheet_title": "Football Screamsheet",
            "teams": ["Arsenal", "Enyimba", "Super Eagles"],
            "players": ["Victor Osimhen"],
            "leagues": ["Premier League", "NPFL", "CAF Champions League", "AFCON"],
            "standings": ["Premier League", "NPFL"],
            "components": [
                {"type": "soccer_game_scores"},
                {"type": "soccer_standings"},
                {"type": "soccer_box_score"},
            ],
        }
        custom_opts = build_custom_sheet_options_from_dict("soccer", raw_yaml)
        order = ScreamsheetOrder(
            output=OutputOrderOptions(directory=str(tmp_path)),
            custom_sheets=[custom_opts],
        )
        res = run_order(order, today=sample_date)
        assert len(res.errors) == 0
        assert len(res.sheets_generated) == 1
        assert (tmp_path / res.sheets_generated[0]).exists()

        # Also verify off-day fallback for Osimhen + Arsenal
        box_comp = SoccerBoxScoreComponent(
            date=sample_date,
            favorite_teams=["Arsenal", "Enyimba"],
            favorite_players=["Victor Osimhen"],
            standings=["Premier League", "NPFL"],
        )
        with patch.object(box_comp.provider, "get_game_scores", return_value=[]):
            flowables = box_comp.render()
            assert len(flowables) > 0
            assert "VICTOR OSIMHEN" in flowables[0].text

    def test_man_of_the_match_spotlight_when_no_players_configured(self, sample_date):
        box_comp = SoccerBoxScoreComponent(
            date=sample_date,
            favorite_teams=["Arsenal"],
            favorite_players=[],
        )
        spot = box_comp.provider._build_spotlight_for_match(
            home_name="Arsenal",
            away_name="Chelsea",
            home_xi=[{"number": 7, "name": "B. Saka", "pos": "F", "rating": "8.9"}],
            away_xi=[{"number": 20, "name": "C. Palmer", "pos": "M", "rating": "7.8"}],
            key_events=[{"minute": "22'", "type": "GOAL", "team": "home", "player": "B. Saka", "detail": "Normal Goal"}],
        )
        assert spot["featured"] is True
        assert spot["label"] == "MAN OF THE MATCH"
        assert spot["player_name"] == "B. Saka"
        assert spot["goals"] == 1


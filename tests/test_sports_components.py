"""Unit tests for Stage 3: Sports Components (Game Scores, Box Score, TV Schedule, Injuries, HR Derby)."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from screamsheet.components import (
    BoxScoreComponent,
    ComponentRegistry,
    GameScoresComponent,
    GameSummaryComponent,
    HomeRunDerbyComponent,
    MLBAllStarBoxScoreComponent,
    MLBAllStarGameScoresComponent,
    MLBAllStarGameSummaryComponent,
    MLBBoxScoreComponent,
    MLBGameScoresComponent,
    NBABoxScoreComponent,
    NBAGameScoresComponent,
    NFLBoxScoreComponent,
    NFLGameScoresComponent,
    NFLInjuriesComponent,
    NFLTVScheduleComponent,
    NHLBoxScoreComponent,
    NHLGameScoresComponent,
    TVScheduleComponent,
    WorldCupBoxScoreComponent,
    WorldCupGameScoresComponent,
)


class TestStage3ComponentRegistry:
    """Verify all Stage 3 sports components are registered."""

    @pytest.mark.parametrize(
        "key,expected_cls",
        [
            ("mlb_game_scores", MLBGameScoresComponent),
            ("nhl_game_scores", NHLGameScoresComponent),
            ("nba_game_scores", NBAGameScoresComponent),
            ("nfl_game_scores", NFLGameScoresComponent),
            ("worldcup_game_scores", WorldCupGameScoresComponent),
            ("mlb_all_star_game_scores", MLBAllStarGameScoresComponent),
            ("mlb_box_score", MLBBoxScoreComponent),
            ("nhl_box_score", NHLBoxScoreComponent),
            ("nba_box_score", NBABoxScoreComponent),
            ("nfl_box_score", NFLBoxScoreComponent),
            ("worldcup_box_score", WorldCupBoxScoreComponent),
            ("mlb_all_star_box_score", MLBAllStarBoxScoreComponent),
            ("mlb_all_star_game_summary", MLBAllStarGameSummaryComponent),
            ("nfl_tv_schedule", NFLTVScheduleComponent),
            ("nfl_injuries", NFLInjuriesComponent),
            ("home_run_derby", HomeRunDerbyComponent),
        ],
    )
    def test_registered_in_component_registry(self, key, expected_cls):
        assert ComponentRegistry.get(key) is expected_cls


class TestGameScoresComponents:
    def test_game_scores_layout_spec(self):
        comp = MLBGameScoresComponent(provider=MagicMock())
        assert comp.layout_spec.weight == 0.25
        assert comp.layout_spec.component_family == "game_scores"
        assert comp.layout_spec.full_page_only is False

    def test_self_contained_game_scores_render_and_markdown(self):
        provider = MagicMock()
        provider.get_game_scores.return_value = [
            {"away_team": "Phillies", "away_score": 5, "home_team": "Mets", "home_score": 2, "status": "Final"}
        ]
        comp = MLBGameScoresComponent(provider=provider, date=datetime(2026, 7, 4))
        flowables = comp.render()
        assert len(flowables) == 1
        md = comp.render_markdown()
        assert "Phillies" in md
        assert "Mets" in md


class TestBoxScoreComponents:
    def test_box_score_layout_spec(self):
        comp = MLBBoxScoreComponent(provider=MagicMock(), team_id=143)
        assert comp.layout_spec.weight == 1.0
        assert comp.layout_spec.full_page_only is True
        assert comp.layout_spec.component_family == "box_score"

    def test_box_score_resolves_featured_team_from_favorites(self):
        provider = MagicMock()
        provider.has_game.side_effect = [False, True]
        provider.get_box_score.return_value = {
            "batting_stats": [{"name": "Harper", "AB": 4, "R": 1, "H": 2, "HR": 1, "RBI": 2, "BB": 0, "SO": 1}],
            "pitching_stats": [],
        }
        provider.get_game_summary.return_value = "Harper homered twice."

        comp = MLBBoxScoreComponent(
            provider=provider,
            favorite_teams=[(147, "New York Yankees"), (143, "Philadelphia Phillies")],
            date=datetime(2026, 7, 4),
        )
        comp.fetch_data()
        assert comp.team_id == 143
        assert comp.team_name == "Philadelphia Phillies"
        flowables = comp.render()
        assert len(flowables) == 1


class TestTVScheduleComponent:
    def test_tv_schedule_layout_spec_and_inheritance(self):
        provider = MagicMock()
        comp = NFLTVScheduleComponent(provider=provider)
        assert isinstance(comp, TVScheduleComponent)
        assert comp.layout_spec.weight == 0.25
        assert comp.layout_spec.component_family == "tv_schedule"

    def test_nfl_tv_schedule_formats_and_bolds_favorites(self):
        provider = MagicMock()
        provider.get_day_schedule.return_value = [
            {
                "away_team": "Dallas Cowboys",
                "home_team": "Philadelphia Eagles",
                "time_et": "8:15 PM ET",
                "broadcast": "NBC",
            },
            {
                "away_team": "New York Jets",
                "home_team": "Buffalo Bills",
                "time_et": "1:00 PM ET",
                "broadcast": "CBS",
            },
        ]
        comp = NFLTVScheduleComponent(
            provider=provider,
            date=datetime(2026, 9, 10),
            favorite_teams=[(21, "Philadelphia Eagles")],
        )
        comp.fetch_data()
        assert len(comp.data) == 2
        assert comp.data[0].startswith("<b>")
        assert not comp.data[1].startswith("<b>")

        flowables = comp.render()
        assert len(flowables) > 0
        md = comp.render_markdown()
        assert "**Dallas Cowboys @ Philadelphia Eagles: 8:15 PM ET (NBC)**" in md


class TestNFLInjuriesAndDerbyComponents:
    def test_nfl_injuries_resolves_team_from_favorites(self):
        provider = MagicMock()
        provider.get_injuries.return_value = [
            {"athlete": "A.J. Brown", "position": "WR", "status": "Questionable", "description": "Hamstring"}
        ]
        comp = NFLInjuriesComponent(
            provider=provider,
            favorite_teams=[(21, "Philadelphia Eagles")],
        )
        comp.fetch_data()
        assert comp.team_id == 21
        assert "Philadelphia Eagles" in comp.title
        assert len(comp.render()) > 0
        assert "A.J. Brown" in comp.render_markdown()

    def test_home_run_derby_component(self):
        provider = MagicMock()
        provider.get_home_run_derby_summary.return_value = {
            "bracket": {
                "champion": {"player": "Teoscar Hernandez", "hits": 14},
                "runner_up": {"player": "Bobby Witt Jr.", "hits": 13},
                "rounds": [],
            },
            "statcast": {},
        }
        comp = HomeRunDerbyComponent(provider=provider, date=datetime(2026, 7, 15))
        assert comp.layout_spec.full_page_only is True
        flowables = comp.render()
        assert len(flowables) > 0

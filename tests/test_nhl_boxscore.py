"""Unit tests for screamsheet.providers.nhl_boxscore."""
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.nhl_boxscore import (
    PlayerSkater,
    PlayerGoalie,
    get_game_boxscore,
    parse_nhl_boxscore,
    create_nhl_boxscore_tables,
)
from reportlab.platypus import Table


# ---------------------------------------------------------------------------
# get_game_boxscore
# ---------------------------------------------------------------------------

class TestGetGameBoxscore:
    def test_returns_dict_on_success(self, nhl_boxscore_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = nhl_boxscore_response
        with patch("requests.get", return_value=mock_resp):
            result = get_game_boxscore(2025020001)
        assert isinstance(result, dict)

    def test_returns_none_on_request_error(self):
        import requests as req_lib
        with patch("requests.get", side_effect=req_lib.exceptions.RequestException("fail")):
            result = get_game_boxscore(9999)
        assert result is None


# ---------------------------------------------------------------------------
# parse_nhl_boxscore
# ---------------------------------------------------------------------------

class TestParseNHLBoxscore:
    def test_returns_empty_stats_for_none_data(self):
        result = parse_nhl_boxscore(None, team_id=4)
        assert result["skater_stats"] == []
        assert result["goalie_stats"] == []

    def test_parses_skater_stats(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert len(result["skater_stats"]) == 1

    def test_skater_is_player_skater_instance(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert isinstance(result["skater_stats"][0], PlayerSkater)

    def test_skater_name_parsed(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert result["skater_stats"][0].name == "John Doe"

    def test_skater_goals_parsed(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert result["skater_stats"][0].goals == 1

    def test_parses_goalie_stats(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert len(result["goalie_stats"]) == 1

    def test_goalie_is_player_goalie_instance(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert isinstance(result["goalie_stats"][0], PlayerGoalie)

    def test_goalie_save_percentage_computed(self, nhl_boxscore_response):
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        goalie = result["goalie_stats"][0]
        assert goalie.save_percentage == pytest.approx(28 / 30)

    def test_goalie_zero_shots_gives_none_sv_pct(self, nhl_boxscore_response):
        # Patch shots_against to 0
        nhl_boxscore_response["playerByGameStats"]["awayTeam"]["goalies"][0][
            "shotsAgainst"
        ] = 0
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=4)
        assert result["goalie_stats"][0].save_percentage is None

    def test_selects_home_team_when_home(self, nhl_boxscore_response):
        """When team_id matches homeTeam.id, parse homeTeam stats."""
        result = parse_nhl_boxscore(nhl_boxscore_response, team_id=1)
        # homeTeam has empty lists
        assert result["skater_stats"] == []
        assert result["goalie_stats"] == []


# ---------------------------------------------------------------------------
# create_nhl_boxscore_tables
# ---------------------------------------------------------------------------

class TestCreateNHLBoxscoreTables:
    @pytest.fixture
    def sample_stats(self):
        return {
            "skater_stats": [
                PlayerSkater(
                    name="John Doe",
                    goals=1,
                    assists=1,
                    points=2,
                    shots_on_goal=3,
                    pim=0,
                )
            ],
            "goalie_stats": [
                PlayerGoalie(
                    name="Jane Smith",
                    shots_against=30,
                    saves=28,
                    save_percentage=0.933,
                )
            ],
        }

    def test_returns_dict_with_table_keys(self, sample_stats):
        result = create_nhl_boxscore_tables(sample_stats)
        assert "skater_table" in result
        assert "goalie_table" in result

    def test_skater_table_is_reportlab_table(self, sample_stats):
        result = create_nhl_boxscore_tables(sample_stats)
        assert isinstance(result["skater_table"], Table)

    def test_goalie_table_is_reportlab_table(self, sample_stats):
        result = create_nhl_boxscore_tables(sample_stats)
        assert isinstance(result["goalie_table"], Table)

    def test_empty_stats_still_returns_tables(self):
        result = create_nhl_boxscore_tables(
            {"skater_stats": [], "goalie_stats": []}
        )
        assert isinstance(result["skater_table"], Table)
        assert isinstance(result["goalie_table"], Table)

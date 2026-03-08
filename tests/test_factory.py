"""Unit tests for screamsheet.factory (ScreamsheetFactory)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.factory import ScreamsheetFactory
from screamsheet.sports.mlb import MLBScreamsheet
from screamsheet.sports.nhl import NHLScreamsheet
from screamsheet.sports.nfl import NFLScreamsheet
from screamsheet.sports.nba import NBAScreamsheet
from screamsheet.news.mlb_trade_rumors import MLBTradeRumorsScreamsheet
from screamsheet.news.players_tribune import PlayersTribuneScreamsheet
from screamsheet.news.fangraphs import FanGraphsScreamsheet


class TestTeamIdConstants:
    def test_mlb_phillies_constant(self):
        assert ScreamsheetFactory.MLB_PHILLIES == 143

    def test_nhl_flyers_constant(self):
        assert ScreamsheetFactory.NHL_FLYERS == 4

    def test_mlb_yankees_constant(self):
        assert ScreamsheetFactory.MLB_YANKEES == 147


class TestCreateMLBScreamsheet:
    def test_returns_mlb_instance(self):
        s = ScreamsheetFactory.create_mlb_screamsheet("out.pdf")
        assert isinstance(s, MLBScreamsheet)

    def test_output_filename_passed(self):
        s = ScreamsheetFactory.create_mlb_screamsheet("mlb.pdf")
        assert s.output_filename == "mlb.pdf"

    def test_team_id_passed(self):
        s = ScreamsheetFactory.create_mlb_screamsheet("out.pdf", team_id=143)
        assert s.team_id == 143

    def test_team_name_passed(self):
        s = ScreamsheetFactory.create_mlb_screamsheet(
            "out.pdf", team_name="Philadelphia Phillies"
        )
        assert s.team_name == "Philadelphia Phillies"

    def test_date_passed(self):
        d = datetime(2025, 3, 15)
        s = ScreamsheetFactory.create_mlb_screamsheet("out.pdf", date=d)
        assert s.date == d


class TestCreateNHLScreamsheet:
    def test_returns_nhl_instance(self):
        s = ScreamsheetFactory.create_nhl_screamsheet("out.pdf")
        assert isinstance(s, NHLScreamsheet)

    def test_team_id_passed(self):
        s = ScreamsheetFactory.create_nhl_screamsheet("out.pdf", team_id=4)
        assert s.team_id == 4


class TestCreateNFLScreamsheet:
    @patch(
        "screamsheet.providers.nfl_provider.NFLDataProvider._get_current_season",
        return_value=2025,
    )
    @patch(
        "screamsheet.providers.nfl_provider.NFLDataProvider._get_current_week",
        return_value=1,
    )
    def test_returns_nfl_instance(self, _w, _s):
        s = ScreamsheetFactory.create_nfl_screamsheet("out.pdf")
        assert isinstance(s, NFLScreamsheet)


class TestCreateNBAScreamsheet:
    def test_returns_nba_instance(self):
        s = ScreamsheetFactory.create_nba_screamsheet("out.pdf")
        assert isinstance(s, NBAScreamsheet)


class TestCreateMLBTradeRumorsScreamsheet:
    def test_returns_mlbtr_instance(self):
        s = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet("out.pdf")
        assert isinstance(s, MLBTradeRumorsScreamsheet)

    def test_favorite_teams_passed(self):
        s = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
            "out.pdf", favorite_teams=["Phillies"]
        )
        assert s.favorite_teams == ["Phillies"]

    def test_max_articles_default(self):
        s = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet("out.pdf")
        assert s.max_articles == 4


class TestCreatePlayersTribuneScreamsheet:
    def test_returns_pt_instance(self):
        s = ScreamsheetFactory.create_players_tribune_screamsheet("out.pdf")
        assert isinstance(s, PlayersTribuneScreamsheet)


class TestCreateFanGraphsScreamsheet:
    def test_returns_fg_instance(self):
        s = ScreamsheetFactory.create_fangraphs_screamsheet("out.pdf")
        assert isinstance(s, FanGraphsScreamsheet)

"""Stage 7 tests for CustomSheetOrderOptions, ComponentSpec, YAML dict parsing, and run_order()."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from screamsheet.components import (
    MLBGameScoresComponent,
    MLBStandingsComponent,
    MLBTradeRumorsComponent,
    NFLTVScheduleComponent,
    NHLBoxScoreComponent,
    WeatherComponent,
)
from screamsheet.order import (
    ComponentSpec,
    CustomSheetOrderOptions,
    OrderValidationError,
    OutputOrderOptions,
    ScreamsheetOrder,
    WeatherLocationOptions,
    build_custom_sheet_options_from_dict,
)
from screamsheet.runner import _build_component_from_spec, run_order


def test_component_spec_and_custom_sheet_validation():
    with pytest.raises(OrderValidationError):
        ComponentSpec(type="")

    with pytest.raises(OrderValidationError):
        ComponentSpec(type="mlb_standings", max_articles=0)

    opts_default = CustomSheetOrderOptions(sheet_key="my_sheet", screamsheet_title="")
    assert opts_default.screamsheet_title == "Screamsheet"

    opts_custom = CustomSheetOrderOptions(
        sheet_key="daily_standings",
        screamsheet_title="Daily Pro Sports Standings",
        components=[ComponentSpec(type="mlb_standings")],
    )
    assert opts_custom.screamsheet_title == "Daily Pro Sports Standings"


def test_build_custom_sheet_options_from_dict_parses_yaml_structure():
    default_weather = WeatherLocationOptions(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")
    raw_yaml = {
        "screamsheet_title": "Peter's Custom Digest",
        "subtitle": "Morning Edition",
        "components": [
            {"type": "weather"},
            {
                "type": "nfl_tv_schedule",
                "teams": ["Philadelphia Eagles", "Green Bay Packers"],
            },
            {
                "type": "mlb_trade_rumors_news",
                "teams": ["Milwaukee Brewers", "Philadelphia Phillies"],
                "max_articles": 4,
            },
            {
                "type": "nhl_box_score",
                "teams": ["Philadelphia Flyers"],
                "mad_fan": True,
            },
        ],
    }

    opts = build_custom_sheet_options_from_dict(
        sheet_key="my_custom_digest",
        raw=raw_yaml,
        default_weather=default_weather,
    )
    assert opts.sheet_key == "my_custom_digest"
    assert opts.screamsheet_title == "Peter's Custom Digest"
    assert opts.subtitle == "Morning Edition"
    assert len(opts.components) == 4
    assert opts.components[0].type == "weather"
    assert opts.components[0].weather == default_weather
    assert opts.components[1].type == "nfl_tv_schedule"
    assert opts.components[1].teams == ["Philadelphia Eagles", "Green Bay Packers"]
    assert opts.components[2].type == "mlb_trade_rumors_news"
    assert opts.components[2].max_articles == 4
    assert opts.components[3].type == "nhl_box_score"
    assert opts.components[3].mad_fan is True


def test_build_component_from_spec_instantiates_registered_components():
    today = datetime(2026, 10, 21)
    weather_loc = WeatherLocationOptions(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")

    w_comp = _build_component_from_spec(
        ComponentSpec(type="weather", weather=weather_loc),
        today=today,
    )
    assert isinstance(w_comp, WeatherComponent)
    assert w_comp.location_name == "Bryn Mawr, PA"

    tv_comp = _build_component_from_spec(
        ComponentSpec(type="nfl_tv_schedule", teams=["Philadelphia Eagles"]),
        today=today,
    )
    assert isinstance(tv_comp, NFLTVScheduleComponent)
    assert len(tv_comp.favorite_teams) == 1

    mtr_comp = _build_component_from_spec(
        ComponentSpec(
            type="mlb_trade_rumors_news",
            teams=["Milwaukee Brewers", "Philadelphia Phillies"],
        ),
        today=today,
    )
    assert isinstance(mtr_comp, MLBTradeRumorsComponent)
    assert mtr_comp.max_articles == 4
    assert mtr_comp.favorite_teams == ["Milwaukee Brewers", "Philadelphia Phillies"]

    box_comp = _build_component_from_spec(
        ComponentSpec(type="nhl_box_score", teams=["Philadelphia Flyers"], mad_fan=True),
        today=today,
    )
    assert isinstance(box_comp, NHLBoxScoreComponent)
    assert box_comp.mad_fan is True
    assert box_comp.date == datetime(2026, 10, 20)  # yesterday for box_score


def test_run_order_generates_custom_component_screamsheets(tmp_path, mlb_standings_df):
    today = datetime(2026, 10, 21)
    custom_opts = CustomSheetOrderOptions(
        sheet_key="daily_standings",
        screamsheet_title="Daily Pro Sports Standings",
        components=[
            ComponentSpec(type="mlb_game_scores", teams=["Philadelphia Phillies"]),
            ComponentSpec(type="mlb_standings"),
        ],
    )
    order = ScreamsheetOrder(
        output=OutputOrderOptions(directory=str(tmp_path)),
        custom_sheets=[custom_opts],
    )

    with patch.object(
        MLBGameScoresComponent,
        "fetch_data",
        autospec=True,
        side_effect=lambda self: setattr(
            self,
            "data",
            [
                {
                    "away_team": "Mets",
                    "away_score": 2,
                    "home_team": "Phillies",
                    "home_score": 5,
                    "status": "Final",
                }
            ],
        ),
    ), patch.object(
        MLBStandingsComponent,
        "fetch_data",
        autospec=True,
        side_effect=lambda self: setattr(self, "data", mlb_standings_df),
    ):
        res = run_order(order, today=today, subscriber_name="Peter Martinson")

    assert res.errors == []
    assert "daily_standings_20261021.pdf" in res.sheets_generated
    assert res.options_summary["daily_standings"] == ["mlb_game_scores", "mlb_standings"]
    assert (tmp_path / "daily_standings_20261021.pdf").exists()

"""Unit tests for MLS screamsheet, provider, and team alias resolution."""
from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from screamsheet.db import sport_init_db, sport_seed_aliases, sport_resolve_team
from screamsheet.factory import ScreamsheetFactory
from screamsheet.providers.mls_provider import MLSDataProvider
from screamsheet.sports.mls import MLSScreamsheet


def test_mls_db_alias_resolution(tmp_path):
    """Verify that 'Philadelphia', 'Miami', 'Union', and 'Messi' resolve correctly."""
    db_file = tmp_path / "test_screamsheet.db"
    sport_init_db("mls", db_path=db_file)
    sport_seed_aliases("mls", db_path=db_file)

    phi = sport_resolve_team("mls", "Philadelphia", db_path=db_file)
    assert phi is not None
    assert phi["team_id"] == 10739
    assert phi["full_name"] == "Philadelphia Union"

    mia = sport_resolve_team("mls", "Miami", db_path=db_file)
    assert mia is not None
    assert mia["team_id"] == 20232
    assert mia["full_name"] == "Inter Miami CF"

    union = sport_resolve_team("mls", "Union", db_path=db_file)
    assert union is not None
    assert union["team_id"] == 10739

    messi = sport_resolve_team("mls", "Messi", db_path=db_file)
    assert messi is not None
    assert messi["team_id"] == 20232


def test_mls_provider_mocked():
    """Verify MLSDataProvider with mocked ESPN endpoints."""
    provider = MLSDataProvider()

    mock_scoreboard = {
        "events": [
            {
                "id": "761941",
                "competitions": [
                    {
                        "status": {"type": {"description": "Full Time", "shortDetail": "FT"}},
                        "competitors": [
                            {"homeAway": "home", "team": {"id": "10739", "displayName": "Philadelphia Union"}, "score": "4"},
                            {"homeAway": "away", "team": {"id": "7318", "displayName": "Toronto FC"}, "score": "1"},
                        ],
                    }
                ],
            }
        ]
    }

    with patch("screamsheet.providers.mls_provider._call_espn_endpoint", return_value=mock_scoreboard):
        scores = provider.get_game_scores(datetime(2026, 11, 7))
        assert len(scores) == 1
        assert scores[0]["home_team"] == "Philadelphia Union"
        assert scores[0]["home_score"] == 4
        assert scores[0]["away_score"] == 1
        assert provider.has_game(10739, datetime(2026, 11, 7)) is True
        assert provider.has_game(99999, datetime(2026, 11, 7)) is False


def test_mls_factory_and_screamsheet(tmp_path):
    """Verify ScreamsheetFactory creates MLSScreamsheet with expected components."""
    out_pdf = str(tmp_path / "MLS_test.pdf")
    sheet = ScreamsheetFactory.create_mls_screamsheet(
        output_filename=out_pdf,
        favorite_teams=[(10739, "Philadelphia Union"), (20232, "Inter Miami CF")],
        date=datetime(2026, 11, 7),
        display_date=datetime(2026, 11, 8),
    )
    assert isinstance(sheet, MLSScreamsheet)
    assert sheet.sport_name == "MLS"

    scores_comp = sheet.create_game_scores_component()
    assert scores_comp.title == "MLS Game Scores"

    standings_comp = sheet.create_standings_component()
    assert standings_comp.title == "MLS Standings"

    box_comp = sheet.create_box_score_component(10739, "Philadelphia Union")
    assert box_comp.team_id == 10739


def test_mls_playoff_series_extraction():
    """Verify playoff series status extraction for MLS."""
    from screamsheet.providers.mls_provider import _extract_mls_series_status

    # Case 1: Away team leads series 1-0
    comp1 = {
        "series": {"totalCompetitions": 3},
        "notes": [{"text": "CIN leads series 1-0"}],
    }
    status1 = _extract_mls_series_status(comp1, "CIN", "NYC", "FC Cincinnati", "New York City FC")
    assert status1 is not None
    assert status1["top_seed_abbrev"] == "CIN"
    assert status1["top_seed_wins"] == 1
    assert status1["bottom_seed_abbrev"] == "NYC"
    assert status1["bottom_seed_wins"] == 0
    assert status1["needed_to_win"] == 2

    # Case 2: Series tied 1-1
    comp2 = {
        "series": {"totalCompetitions": 3},
        "notes": [{"text": "Series tied 1-1"}],
    }
    status2 = _extract_mls_series_status(comp2, "MIA", "ATL", "Inter Miami CF", "Atlanta United FC")
    assert status2 is not None
    assert status2["top_seed_wins"] == 1
    assert status2["bottom_seed_wins"] == 1
    assert status2["needed_to_win"] == 2

    # Case 3: Home team won series 2-0
    comp3 = {
        "series": {"totalCompetitions": 3},
        "notes": [{"text": "MIN win series 2-0"}],
    }
    status3 = _extract_mls_series_status(comp3, "RSL", "MIN", "Real Salt Lake", "Minnesota United FC")
    assert status3 is not None
    assert status3["top_seed_abbrev"] == "MIN"
    assert status3["top_seed_wins"] == 2
    assert status3["bottom_seed_abbrev"] == "RSL"
    assert status3["bottom_seed_wins"] == 0
    assert status3["needed_to_win"] == 2

    # Case 4: Regular season (no series or notes)
    comp4 = {"series": None, "notes": []}
    status4 = _extract_mls_series_status(comp4, "PHI", "TOR", "Philadelphia Union", "Toronto FC")
    assert status4 is None


def test_mls_game_scores_series_badge_rendering():
    """Verify that MLSGameScoresComponent renders series badges in table cells for playoff games."""
    from screamsheet.components.game_scores.mls import MLSGameScoresComponent

    provider = MagicMock()
    provider.get_game_scores.return_value = [
        {
            "game_id": "1",
            "date": "20241102",
            "away_id": 18267,
            "away_team": "Cincinnati",
            "away_abbrev": "CIN",
            "away_score": 1,
            "home_id": 17606,
            "home_team": "NYCFC",
            "home_abbrev": "NYC",
            "home_score": 3,
            "series_status": {
                "top_seed_abbrev": "CIN",
                "top_seed_wins": 1,
                "bottom_seed_abbrev": "NYC",
                "bottom_seed_wins": 1,
                "needed_to_win": 2,
            },
        },
        {
            "game_id": "2",
            "date": "20241102",
            "away_id": 17362,
            "away_team": "Salt Lake",
            "away_abbrev": "RSL",
            "away_score": 1,
            "home_id": 4771,
            "home_team": "Minnesota",
            "home_abbrev": "MIN",
            "home_score": 1,
            "series_status": {
                "top_seed_abbrev": "MIN",
                "top_seed_wins": 2,
                "bottom_seed_abbrev": "RSL",
                "bottom_seed_wins": 0,
                "needed_to_win": 2,
            },
        },
    ]

    comp = MLSGameScoresComponent(provider=provider, date=datetime(2024, 11, 2))
    elements = comp.render()
    assert len(elements) > 0

    # Inspect the outer 3-column table
    outer_table = elements[0]
    cell_content = outer_table._cellvalues[0]

    # Column 0 has game 0, column 1 has game 1
    game0_table = cell_content[0][0]  # First element in col 0
    table_data_0 = game0_table._cellvalues
    # Game 0: NYC won 3-1, series tied 1-1 -> badge goes on home (NYC) row
    assert table_data_0[0] == ["Cincinnati", "1", ""]
    assert table_data_0[1] == ["@NYCFC", "3", "(tied 1-1)"]

    game1_table = cell_content[1][0]  # First element in col 1
    table_data_1 = game1_table._cellvalues
    # Game 1: MIN won 2-0 -> badge goes on MIN row
    assert table_data_1[0] == ["Salt Lake", "1", ""]
    assert table_data_1[1] == ["@Minnesota", "1", "(won 2-0)"]


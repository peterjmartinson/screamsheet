"""Unit tests for College Football (CFB) screamsheet and data provider."""
import os
from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from screamsheet.factory import ScreamsheetFactory
from screamsheet.order import CFBOrderOptions, OutputOrderOptions, ScreamsheetOrder, TeamEntry
from screamsheet.providers.cfb_provider import CFBDataProvider
from screamsheet.runner import run_order
from screamsheet.sports.cfb import CFBScreamsheet


@pytest.fixture
def mock_cfb_provider():
    provider = MagicMock(spec=CFBDataProvider)
    provider.get_game_scores.return_value = [
        {
            "gameId": "401856717",
            "game_id": "401856717",
            "away_team": "(1) Texas",
            "away_team_full": "Texas Longhorns",
            "away_team_id": 251,
            "away_score": 24,
            "away_rank": 1,
            "home_team": "Oklahoma",
            "home_team_full": "Oklahoma Sooners",
            "home_team_id": 201,
            "home_score": 27,
            "home_rank": 99,
            "status": "STATUS_FINAL",
            "is_final": True,
            "priority": 1,
        },
        {
            "gameId": "401856712",
            "game_id": "401856712",
            "away_team": "(2) Georgia",
            "away_team_full": "Georgia Bulldogs",
            "away_team_id": 61,
            "away_score": 20,
            "away_rank": 2,
            "home_team": "(6) Alabama",
            "home_team_full": "Alabama Crimson Tide",
            "home_team_id": 333,
            "home_score": 17,
            "home_rank": 6,
            "status": "STATUS_FINAL",
            "is_final": True,
            "priority": 1,
        },
    ]

    rankings_data = []
    for r in range(1, 26):
        rankings_data.append({
            "rank": r,
            "team": f"College {r}",
            "record": f"{r % 5 + 3}-0",
            "previous": str(r if r > 1 else "-"),
            "points": 1500.0 - (r * 30),
        })
    provider.get_standings.return_value = pd.DataFrame(rankings_data)

    provider.get_all_teams_for_date.return_value = [
        (251, "Texas Longhorns"),
        (201, "Oklahoma Sooners"),
        (61, "Georgia Bulldogs"),
        (333, "Alabama Crimson Tide"),
    ]
    provider.has_game.side_effect = lambda tid, dt: tid in (251, 201, 61, 333)

    provider.get_box_score.return_value = {
        "away_team": "Texas Longhorns",
        "away_abbrev": "TEX",
        "away_score": "24",
        "away_linescores": ["7", "10", "0", "7"],
        "home_team": "Oklahoma Sooners",
        "home_abbrev": "OU",
        "home_score": "27",
        "home_linescores": ["0", "7", "3", "17"],
        "quarter_labels": ["1", "2", "3", "4"],
        "team_stats": [
            {"stat": "Total Yards", "away": "382", "home": "238"},
            {"stat": "Net Passing Yards", "away": "260", "home": "155"},
            {"stat": "Rushing Yards", "away": "122", "home": "83"},
            {"stat": "Turnovers", "away": "2", "home": "0"},
        ],
        "top_performers": [
            {"category": "PASS (OU)", "player": "John Mateer", "stat": "18/26, 155 YDS"},
            {"category": "RUSH (OU)", "player": "Lloyd Avant", "stat": "10 CAR, 72 YDS, 1 TD"},
            {"category": "PASS (TEX)", "player": "Arch Manning", "stat": "19/31, 260 YDS, 3 TD, 2 INT"},
        ],
    }

    provider.get_game_summary.return_value = (
        "Oklahoma secured a dramatic 27-24 upset over No. 1 Texas in the Red River Rivalry.\n\n"
        "3 Key Takeaways:\n\n"
        "<b>Turnovers:</b> Defense forced two interceptions.\n\n"
        "<b>Clutch Kicking:</b> 47-yard game-winning field goal.\n\n"
        "<b>Rushing:</b> Ground game controlled the fourth quarter."
    )
    return provider


def test_cfb_screamsheet_initialization():
    sheet = CFBScreamsheet(
        output_filename="test_cfb.pdf",
        date=datetime(2026, 10, 10),
        display_date=datetime(2026, 10, 11),
        favorite_teams=[(251, "Texas Longhorns")],
    )
    assert sheet.sport_name == "College Football"
    assert sheet.get_title() == "COLLEGE FOOTBALL"
    assert sheet.get_subtitle() == "Saturday Gameday Recap"
    assert sheet.get_date_string() == "Sunday, October 11, 2026"


def test_cfb_sections_build(mock_cfb_provider):
    sheet = CFBScreamsheet(
        output_filename="test_cfb.pdf",
        date=datetime(2026, 10, 10),
        display_date=datetime(2026, 10, 11),
        favorite_teams=[(251, "Texas Longhorns")],
    )
    sheet.provider = mock_cfb_provider
    sections = sheet.build_sections()

    assert len(sections) == 3
    # Front page
    assert sections[0].title == "College Football Game Scores"
    assert getattr(sections[0], "page_slot", "") == "front"
    assert sections[1].title == "AP Top 25 Rankings"
    assert getattr(sections[1], "page_slot", "") == "front"
    # Back page
    assert sections[2].title == "Texas Longhorns Box Score"
    assert getattr(sections[2], "page_slot", "") == "back"


def test_cfb_generate_pdf(tmp_path, mock_cfb_provider):
    pdf_path = str(tmp_path / "CFB_scores_test.pdf")
    sheet = CFBScreamsheet(
        output_filename=pdf_path,
        date=datetime(2026, 10, 10),
        display_date=datetime(2026, 10, 11),
        favorite_teams=[(251, "Texas Longhorns")],
    )
    sheet.provider = mock_cfb_provider
    result = sheet.generate()

    assert os.path.exists(result)
    assert os.path.getsize(result) > 1000


def test_cfb_markdown_generation(tmp_path, mock_cfb_provider):
    pdf_path = str(tmp_path / "CFB_scores_test.pdf")
    md_path = str(tmp_path / "CFB_scores_test.md")
    sheet = CFBScreamsheet(
        output_filename=pdf_path,
        date=datetime(2026, 10, 10),
        display_date=datetime(2026, 10, 11),
        favorite_teams=[(251, "Texas Longhorns")],
    )
    sheet.provider = mock_cfb_provider
    md_result = sheet.generate_markdown(output_path=md_path, use_cache=False)

    assert os.path.exists(md_result)
    content = open(md_result, "r", encoding="utf-8").read()
    assert "# COLLEGE FOOTBALL" in content
    assert "College Football Game Scores" in content
    assert "AP Top 25 Rankings" in content
    assert "Box Score" in content


def test_cfb_factory_and_runner(tmp_path, mock_cfb_provider):
    with patch("screamsheet.sports.cfb.CFBDataProvider", return_value=mock_cfb_provider):
        order = ScreamsheetOrder(
            output=OutputOrderOptions(directory=str(tmp_path)),
            cfb=CFBOrderOptions(
                favorite_teams=[TeamEntry(id=251, name="Texas Longhorns")],
                mad_fan=False,
            ),
        )
        res = run_order(order, today=datetime(2026, 10, 11))
        assert len(res.sheets_generated) == 1
        assert res.sheets_generated[0] == "CFB_gamescores_20261011.pdf"
        assert os.path.exists(tmp_path / res.sheets_generated[0])


def test_cfb_provider_scores_priority():
    provider = CFBDataProvider()
    mock_events = [
        {
            "id": "1",
            "competitions": [{
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitors": [
                    {"homeAway": "home", "team": {"id": 10, "shortDisplayName": "TeamA", "displayName": "TeamA"}, "score": "21", "curatedRank": {"current": 99}},
                    {"homeAway": "away", "team": {"id": 20, "shortDisplayName": "TeamB", "displayName": "TeamB"}, "score": "14", "curatedRank": {"current": 99}},
                ],
            }],
        },
        {
            "id": "2",
            "competitions": [{
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitors": [
                    {"homeAway": "home", "team": {"id": 30, "shortDisplayName": "TopA", "displayName": "TopA"}, "score": "28", "curatedRank": {"current": 4}},
                    {"homeAway": "away", "team": {"id": 40, "shortDisplayName": "TopB", "displayName": "TopB"}, "score": "24", "curatedRank": {"current": 8}},
                ],
            }],
        },
        {
            "id": "3",
            "competitions": [{
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitors": [
                    {"homeAway": "home", "team": {"id": 50, "shortDisplayName": "FavHome", "displayName": "FavHome"}, "score": "35", "curatedRank": {"current": 99}},
                    {"homeAway": "away", "team": {"id": 60, "shortDisplayName": "Other", "displayName": "Other"}, "score": "7", "curatedRank": {"current": 99}},
                ],
            }],
        },
    ]

    mock_response = MagicMock()
    mock_response.json.return_value = {"events": mock_events}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        scores = provider.get_game_scores(
            date=datetime(2026, 10, 10),
            favorite_teams=[(50, "FavHome")],
        )
        assert len(scores) == 3
        # Favorite game must be first (priority 0)
        assert scores[0]["home_team_id"] == 50
        # Ranked vs ranked matchup must be second (priority 1)
        assert scores[1]["away_team"] == "(8) TopB"
        assert scores[1]["home_team"] == "(4) TopA"

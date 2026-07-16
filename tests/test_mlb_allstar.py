"""Tests for MLB All-Star Game screamsheet and provider methods."""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from screamsheet.providers.mlb_provider import MLBDataProvider
from screamsheet.factory import ScreamsheetFactory
from screamsheet.sports.mlb_allstar import MLBAllStarScreamsheet
from screamsheet.renderers.allstar_renderers import (
    AllStarGameScoresSection,
    AllStarGameSummarySection,
    AllStarSideBySideBoxScoreSection,
)


def test_mlb_allstar_screamsheet_factory():
    """Verify ScreamsheetFactory creates MLBAllStarScreamsheet correctly."""
    sheet = ScreamsheetFactory.create_mlb_allstar_screamsheet(
        output_filename="test_allstar.pdf",
        date=datetime(2025, 7, 15),
    )
    assert isinstance(sheet, MLBAllStarScreamsheet)
    assert sheet.sport_name == "MLB All-Star"
    assert sheet.get_title() == "MLB All-Star Game"
    assert sheet.get_subtitle() == "Screamsheet Special Edition"


def test_mlb_allstar_build_sections():
    """Verify build_sections returns the 3 expected All-Star sections."""
    sheet = MLBAllStarScreamsheet(output_filename="test.pdf", date=datetime(2025, 7, 15))
    sections = sheet.build_sections()
    assert len(sections) == 3
    assert isinstance(sections[0], AllStarGameScoresSection)
    assert isinstance(sections[1], AllStarGameSummarySection)
    assert isinstance(sections[2], AllStarSideBySideBoxScoreSection)
    assert sections[0].page_slot == "front"
    assert sections[1].page_slot == "front"
    assert sections[2].page_slot == "back"


@patch("requests.get")
def test_get_allstar_game_scores(mock_get):
    """Test get_allstar_game_scores parsing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "dates": [
            {
                "games": [
                    {
                        "gameType": "A",
                        "gameDate": "2025-07-16T00:00:00Z",
                        "teams": {
                            "away": {"team": {"name": "American League All-Stars", "id": 159}, "score": 6},
                            "home": {"team": {"name": "National League All-Stars", "id": 160}, "score": 7},
                        },
                        "status": {"detailedState": "Final"},
                    }
                ]
            }
        ]
    }
    mock_get.return_value = mock_response

    provider = MLBDataProvider()
    scores = provider.get_allstar_game_scores(datetime(2025, 7, 15))
    assert len(scores) == 1
    assert scores[0]["away_team"] == "American League All-Stars"
    assert scores[0]["home_team"] == "National League All-Stars"
    assert scores[0]["away_score"] == 6
    assert scores[0]["home_score"] == 7


@patch("requests.get")
def test_get_allstar_box_scores(mock_get):
    """Test get_allstar_box_scores parses AL and NL columns."""
    def mock_requests_get(url, params=None):
        m = MagicMock()
        if "schedule" in url:
            m.json.return_value = {
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 12345,
                                "gameType": "A",
                                "status": {"abstractGameCode": "F", "detailedState": "Final"},
                            }
                        ]
                    }
                ]
            }
        elif "boxscore" in url:
            m.json.return_value = {
                "teams": {
                    "away": {
                        "team": {"id": 159, "name": "American League All-Stars"},
                        "players": {
                            "ID1": {
                                "person": {"fullName": "Aaron Judge"},
                                "stats": {"batting": {"atBats": 3, "runs": 1, "hits": 2, "homeRuns": 1, "rbi": 2}, "pitching": {}}
                            }
                        }
                    },
                    "home": {
                        "team": {"id": 160, "name": "National League All-Stars"},
                        "players": {
                            "ID2": {
                                "person": {"fullName": "Paul Skenes"},
                                "stats": {"batting": {}, "pitching": {"inningsPitched": "1.0", "strikeOuts": 2}}
                            }
                        }
                    }
                }
            }
        return m

    mock_get.side_effect = mock_requests_get
    provider = MLBDataProvider()
    box = provider.get_allstar_box_scores(datetime(2025, 7, 15))
    assert box is not None
    assert "AL" in box
    assert "NL" in box
    assert box["AL"]["team_name"] == "American League All-Stars"
    assert len(box["AL"]["batting_stats"]) == 1
    assert box["AL"]["batting_stats"][0]["name"] == "Aaron Judge"
    assert len(box["NL"]["pitching_stats"]) == 1
    assert box["NL"]["pitching_stats"][0]["name"] == "Paul Skenes"

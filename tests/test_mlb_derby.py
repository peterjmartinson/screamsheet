"""Unit tests for MLB Home Run Derby data provider and Markdown renderer."""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from screamsheet.providers.mlb_provider import MLBDataProvider
from screamsheet.renderers.derby_markdown import format_derby_markdown


@pytest.fixture
def provider():
    """Create MLBDataProvider instance."""
    return MLBDataProvider()


@pytest.fixture
def mock_schedule_response():
    """Mock schedule API response containing Home Run Derby event."""
    return {
        "dates": [
            {
                "date": "2024-07-15",
                "events": [
                    {"id": 775747, "name": "Home Run Derby Testing"},
                    {"id": 773161, "name": "2024 MLB All-Star Workout Day: Home Run Derby"}
                ]
            }
        ]
    }


@pytest.fixture
def mock_bracket_response():
    """Mock bracket API response."""
    return {
        "rounds": [
            {
                "round": {"name": "Round 1"},
                "matchups": [
                    {
                        "topSeed": {"player": {"fullName": "Teoscar Hernández"}, "hits": 19},
                        "bottomSeed": {"player": {"fullName": "Alec Bohm"}, "hits": 21},
                        "winner": {"fullName": "Alec Bohm"}
                    }
                ]
            },
            {
                "round": {"name": "Finals"},
                "matchups": [
                    {
                        "topSeed": {"player": {"fullName": "Teoscar Hernández"}, "hits": 14},
                        "bottomSeed": {"player": {"fullName": "Bobby Witt Jr."}, "hits": 13},
                        "winner": {"fullName": "Teoscar Hernández"}
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_statcast_response():
    """Mock pool Statcast API response."""
    return {
        "rounds": [
            {
                "batters": [
                    {
                        "player": {"fullName": "Teoscar Hernández"},
                        "hits": [
                            {
                                "isHomeRun": True,
                                "hitData": {"totalDistance": 466.0, "launchSpeed": 110.5}
                            },
                            {
                                "isHomeRun": False,
                                "hitData": {"totalDistance": 380.0, "launchSpeed": 99.0}
                            }
                        ]
                    },
                    {
                        "player": {"fullName": "Bobby Witt Jr."},
                        "hits": [
                            {
                                "isHomeRun": True,
                                "hitData": {"totalDistance": 440.0, "launchSpeed": 114.2}
                            }
                        ]
                    }
                ]
            }
        ]
    }


def test_get_derby_game_pk(provider, mock_schedule_response):
    """Test get_derby_game_pk finds the correct event ID while ignoring testing sessions."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_schedule_response
        mock_get.return_value = mock_resp
        
        game_pk = provider.get_derby_game_pk(datetime(2024, 7, 15))
        assert game_pk == 773161


def test_fetch_derby_bracket(provider, mock_bracket_response):
    """Test fetch_derby_bracket parses rounds, champion, and runner up."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_bracket_response
        mock_get.return_value = mock_resp
        
        bracket = provider.fetch_derby_bracket(773161)
        assert bracket is not None
        assert len(bracket["rounds"]) == 2
        assert bracket["champion"]["player"] == "Teoscar Hernández"
        assert bracket["runner_up"]["player"] == "Bobby Witt Jr."


def test_fetch_derby_statcast(provider, mock_statcast_response):
    """Test fetch_derby_statcast extracts longest home run and hardest hit ball."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_statcast_response
        mock_get.return_value = mock_resp
        
        statcast = provider.fetch_derby_statcast(773161)
        assert statcast is not None
        assert statcast["longest_hr"]["distance"] == 466.0
        assert statcast["longest_hr"]["player"] == "Teoscar Hernández"
        assert statcast["hardest_hit"]["exit_velocity"] == 114.2
        assert statcast["hardest_hit"]["player"] == "Bobby Witt Jr."


def test_format_derby_markdown():
    """Test format_derby_markdown produces expected table and Statcast highlights."""
    sample_data = {
        "game_pk": 773161,
        "date": "2024-07-15",
        "bracket": {
            "champion": {"player": "Teoscar Hernández", "hits": 14},
            "runner_up": {"player": "Bobby Witt Jr.", "hits": 13},
            "rounds": [
                {
                    "round_name": "Finals",
                    "matchups": [
                        {
                            "top_seed": {"player": "Teoscar Hernández", "hits": 14},
                            "bottom_seed": {"player": "Bobby Witt Jr.", "hits": 13},
                            "winner": "Teoscar Hernández"
                        }
                    ]
                }
            ]
        },
        "statcast": {
            "longest_hr": {"player": "Teoscar Hernández", "distance": 466.0},
            "hardest_hit": {"player": "Bobby Witt Jr.", "exit_velocity": 114.2}
        }
    }
    
    markdown = format_derby_markdown(sample_data)
    assert "# 🏆 MLB Home Run Derby Summary" in markdown
    assert "**Champion:** Teoscar Hernández (14 HR in Finals)" in markdown
    assert "**Runner-Up:** Bobby Witt Jr. (13 HR in Finals)" in markdown
    assert "| **Finals** | Teoscar Hernández | 14 | Champion |" in markdown
    assert "| | Bobby Witt Jr. | 13 | Runner-Up |" in markdown
    assert "* **Longest Home Run:** 466.0 ft — *Teoscar Hernández*" in markdown
    assert "* **Hardest Hit Ball:** 114.2 mph — *Bobby Witt Jr.*" in markdown


def test_format_derby_markdown_empty():
    """Test format_derby_markdown handles empty or None data."""
    assert format_derby_markdown({}) == "No Home Run Derby data available."

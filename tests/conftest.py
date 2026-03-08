"""Shared pytest fixtures for the screamsheet test suite."""
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_date():
    return datetime(2025, 3, 15)


# ---------------------------------------------------------------------------
# MLB API payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def mlb_schedule_response():
    """Minimal MLB /schedule API response with one completed game."""
    return {
        "dates": [
            {
                "games": [
                    {
                        "gameDate": "2025-03-15T18:05:00Z",
                        "teams": {
                            "away": {
                                "team": {"name": "New York Mets"},
                                "score": 3,
                            },
                            "home": {
                                "team": {"name": "Philadelphia Phillies"},
                                "score": 5,
                            },
                        },
                        "status": {"detailedState": "Final"},
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mlb_standings_response():
    """Minimal MLB /standings API response (two divisions, two teams each)."""
    return {
        "records": [
            {
                "division": {"link": "/api/v1/divisions/201"},
                "teamRecords": [
                    {
                        "team": {"name": "Philadelphia Phillies"},
                        "leagueRecord": {"wins": 10, "losses": 5, "ties": 0, "pct": ".667"},
                        "divisionRank": "1",
                    },
                    {
                        "team": {"name": "New York Mets"},
                        "leagueRecord": {"wins": 8, "losses": 7, "ties": 0, "pct": ".533"},
                        "divisionRank": "2",
                    },
                ],
            }
        ]
    }


@pytest.fixture
def mlb_division_response():
    """Minimal MLB /divisions/<id> response."""
    return {
        "divisions": [
            {"nameShort": "NL East", "name": "National League East"}
        ]
    }


@pytest.fixture
def mlb_live_feed_response():
    """Minimal MLB live feed response used by MLBGameExtractor."""
    return {
        "gameData": {
            "teams": {
                "home": {"name": "Philadelphia Phillies"},
                "away": {"name": "New York Mets"},
            }
        },
        "liveData": {
            "linescore": {
                "teams": {
                    "home": {"runs": 5},
                    "away": {"runs": 3},
                }
            },
            "plays": {
                "allPlays": [
                    {"result": {"description": "Strikeout swinging."}},
                    {"result": {"description": "Home run to left field."}},
                ]
            },
        },
    }


# ---------------------------------------------------------------------------
# NHL API payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def nhl_schedule_response():
    """Minimal NHL /schedule/<date> API response."""
    return {
        "gameWeek": [
            {
                "games": [
                    {
                        "gameState": "OFF",
                        "startTimeUTC": "2025-03-15T23:00:00Z",
                        "awayTeam": {
                            "id": 4,
                            "placeName": {"default": "Philadelphia"},
                            "commonName": {"default": "Flyers"},
                            "score": 4,
                        },
                        "homeTeam": {
                            "id": 1,
                            "placeName": {"default": "New Jersey"},
                            "commonName": {"default": "Devils"},
                            "score": 2,
                        },
                    }
                ]
            }
        ]
    }


@pytest.fixture
def nhl_standings_response():
    """Minimal NHL /standings/now response."""
    return {
        "standings": [
            {
                "teamName": {"default": "Flyers"},
                "divisionName": "Metropolitan",
                "conferenceName": "Eastern",
                "divisionSequence": 1,
                "gamesPlayed": 60,
                "wins": 35,
                "losses": 20,
                "otLosses": 5,
                "points": 75,
                "winPctg": 0.583,
                "streakCode": "W",
                "streakCount": 3,
                "pointPctg": 0.625,
                "goalFor": 200,
                "goalAgainst": 165,
                "goalDifferential": 35,
            }
        ]
    }


@pytest.fixture
def nhl_boxscore_response():
    """Minimal NHL /gamecenter/<pk>/boxscore response."""
    return {
        "homeTeam": {"id": 1},
        "awayTeam": {"id": 4},
        "playerByGameStats": {
            "awayTeam": {
                "forwards": [
                    {
                        "name": {"default": "John Doe"},
                        "goals": 1,
                        "assists": 1,
                        "points": 2,
                        "shots": 3,
                        "pim": 0,
                    }
                ],
                "defense": [],
                "goalies": [
                    {
                        "name": {"default": "Jane Smith"},
                        "shotsAgainst": 30,
                        "saves": 28,
                    }
                ],
            },
            "homeTeam": {
                "forwards": [],
                "defense": [],
                "goalies": [],
            },
        },
    }


# ---------------------------------------------------------------------------
# Weather / NWS payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def nws_points_response():
    """Minimal NWS /points response."""
    return {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast"
        }
    }


@pytest.fixture
def nws_forecast_response():
    """Minimal NWS forecast response with two periods (day + night)."""
    return {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "isDaytime": True,
                    "shortForecast": "Sunny",
                    "icon": "https://example.com/sunny.png",
                    "temperature": 72,
                    "temperatureUnit": "F",
                },
                {
                    "name": "Tonight",
                    "isDaytime": False,
                    "shortForecast": "Clear",
                    "icon": "https://example.com/clear.png",
                    "temperature": 55,
                    "temperatureUnit": "F",
                },
                # Repeat pattern for remaining days
                *[
                    {
                        "name": f"Day{i}",
                        "isDaytime": i % 2 == 0,
                        "shortForecast": "Partly Cloudy",
                        "icon": "https://example.com/cloudy.png",
                        "temperature": 68,
                        "temperatureUnit": "F",
                    }
                    for i in range(2, 10)
                ],
            ]
        }
    }


# ---------------------------------------------------------------------------
# RSS / feedparser payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def rss_entry():
    """Minimal feedparser entry dict."""
    return {
        "title": "Phillies Sign New Pitcher",
        "link": "https://www.mlbtraderumors.com/phillies-sign-pitcher",
        "summary": "The Phillies have signed a new pitcher.",
        "published": "Sat, 15 Mar 2025 12:00:00 +0000",
    }


@pytest.fixture
def rss_feed(rss_entry):
    """Minimal feedparser feed-like object."""
    mock_feed = MagicMock()
    mock_feed.entries = [rss_entry]
    return mock_feed


# ---------------------------------------------------------------------------
# LLM / LangChain mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_chain():
    """A MagicMock that behaves like a LangChain Runnable chain."""
    chain = MagicMock()
    chain.invoke.return_value = "The Phillies won 5-3 in a dominant performance."
    return chain


# ---------------------------------------------------------------------------
# Pre-built DataFrames
# ---------------------------------------------------------------------------

@pytest.fixture
def mlb_standings_df():
    """Simple MLB standings DataFrame."""
    return pd.DataFrame(
        [
            {
                "division": "National League East",
                "team": "Philadelphia Phillies",
                "wins": 10,
                "losses": 5,
                "ties": 0,
                "pct": ".667",
                "divisionRank": "1",
            },
            {
                "division": "National League East",
                "team": "New York Mets",
                "wins": 8,
                "losses": 7,
                "ties": 0,
                "pct": ".533",
                "divisionRank": "2",
            },
        ]
    )


@pytest.fixture
def nhl_standings_df():
    """Simple NHL standings DataFrame matching NHLDataProvider column names."""
    return pd.DataFrame(
        [
            {
                "conference": "Eastern",
                "division": "Metropolitan",
                "team": "Flyers",
                "divisionRank": 1,
                "GP": 60,
                "W": 35,
                "L": 20,
                "OTL": 5,
                "P": 75,
                "PCT": 0.625,
                "GF": 200,
                "GA": 165,
                "DIFF": 35,
                "STRK": "W3",
            }
        ]
    )

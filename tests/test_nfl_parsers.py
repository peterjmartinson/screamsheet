"""Tests for NFL data parsers."""
import pytest
from screamsheet.providers.parsers.nfl_parsers import (
    extract_scoreboard,
    extract_game_summary,
    extract_standings,
    extract_injuries,
    extract_box_score,
)


def test_extract_scoreboard_valid():
    raw_payload = {
        "events": [
            {
                "id": "401547412",
                "date": "2024-09-08T17:00Z",
                "competitions": [
                    {
                        "status": {"type": {"name": "STATUS_FINAL"}},
                        "competitors": [
                            {
                                "homeAway": "home",
                                "team": {"displayName": "Pittsburgh Steelers", "name": "Steelers"},
                                "score": "18",
                                "linescores": [{"value": 6}, {"value": 3}, {"value": 3}, {"value": 6}]
                            },
                            {
                                "homeAway": "away",
                                "team": {"displayName": "Atlanta Falcons", "name": "Falcons"},
                                "score": "10",
                                "linescores": [{"value": 0}, {"value": 10}, {"value": 0}, {"value": 0}]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    games = extract_scoreboard(raw_payload)
    assert len(games) == 1
    assert games[0]["game_id"] == "401547412"
    assert games[0]["home_team"] == "Pittsburgh Steelers"
    assert games[0]["home_score"] == 18
    assert games[0]["away_team"] == "Atlanta Falcons"
    assert games[0]["away_score"] == 10
    assert games[0]["status"] == "STATUS_FINAL"
    assert games[0]["quarter_scores"]["home"] == [6, 3, 3, 6]
    assert games[0]["quarter_scores"]["away"] == [0, 10, 0, 0]


def test_extract_scoreboard_empty():
    assert extract_scoreboard({}) == []
    assert extract_scoreboard(None) == []
    assert extract_scoreboard({"events": []}) == []


def test_extract_game_summary_valid():
    raw_payload = {
        "drives": {
            "previous": [
                {
                    "plays": [
                        {
                            "scoringPlay": True,
                            "period": {"number": 1},
                            "clock": {"displayValue": "10:15"},
                            "team": {"displayName": "Pittsburgh Steelers"},
                            "text": "C.Boswell 57 yd FG",
                            "scoreValue": 3,
                            "awayScore": 3,
                            "homeScore": 0
                        }
                    ]
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"displayName": "Pittsburgh Steelers"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "270"},
                        {"name": "netPassingYards", "displayValue": "133"},
                        {"name": "rushingYards", "displayValue": "137"},
                        {"name": "turnovers", "displayValue": "0"},
                        {"name": "thirdDownEff", "displayValue": "8-17"},
                        {"name": "possessionTime", "displayValue": "35:36"}
                    ]
                }
            ]
        },
        "leaders": [
            {
                "name": "passingLeader",
                "leaders": [
                    {
                        "displayValue": "156 YDS, 1 TD",
                        "athlete": {"displayName": "Justin Fields"},
                        "team": {"displayName": "Steelers"}
                    }
                ]
            },
            {
                "name": "rushingLeader",
                "leaders": [
                    {
                        "displayValue": "70 YDS",
                        "athlete": {"displayName": "Najee Harris"},
                        "team": {"displayName": "Steelers"}
                    }
                ]
            }
        ]
    }
    summary = extract_game_summary(raw_payload)
    assert len(summary["scoring_drives"]) == 1
    assert summary["scoring_drives"][0]["description"] == "C.Boswell 57 yd FG"
    assert "Pittsburgh Steelers" in summary["team_totals"]
    assert summary["team_totals"]["Pittsburgh Steelers"]["total_yards"] == "270"
    assert len(summary["leaders"]["passing"]) == 1
    assert summary["leaders"]["passing"][0]["name"] == "Justin Fields"
    assert len(summary["leaders"]["rushing"]) == 1


def test_extract_game_summary_empty():
    summary = extract_game_summary({})
    assert summary["scoring_drives"] == []
    assert summary["team_totals"] == {}
    assert summary["leaders"]["passing"] == []


def test_extract_standings():
    raw_payload = {
        "children": [
            {
                "name": "AFC North",
                "standings": {
                    "entries": [
                        {
                            "team": {"displayName": "Pittsburgh Steelers"},
                            "stats": [
                                {"name": "rank", "value": 1},
                                {"name": "wins", "value": 10},
                                {"name": "losses", "value": 7},
                                {"name": "ties", "value": 0},
                                {"name": "winPercent", "value": 0.588},
                                {"name": "pointDifferential", "value": 45},
                                {"name": "streak", "displayValue": "W2"}
                            ]
                        }
                    ]
                }
            }
        ]
    }
    standings = extract_standings(raw_payload)
    assert len(standings) == 1
    assert standings[0]["team"] == "Pittsburgh Steelers"
    assert standings[0]["division"] == "AFC North"
    assert standings[0]["wins"] == 10
    assert standings[0]["losses"] == 7
    assert standings[0]["differential"] == 45
    assert standings[0]["streak"] == "W2"

    # Filter division
    filtered = extract_standings(raw_payload, division_name="AFC North")
    assert len(filtered) == 1
    filtered_none = extract_standings(raw_payload, division_name="NFC South")
    assert len(filtered_none) == 0


def test_extract_injuries():
    raw_payload = {
        "injuries": [
            {
                "athlete": {
                    "displayName": "Russell Wilson",
                    "position": {"abbreviation": "QB"}
                },
                "status": "Questionable",
                "date": "2024-09-06",
                "details": {"detail": "Calf tightness"}
            }
        ]
    }
    injuries = extract_injuries(raw_payload)
    assert len(injuries) == 1
    assert injuries[0]["athlete"] == "Russell Wilson"
    assert injuries[0]["position"] == "QB"
    assert injuries[0]["status"] == "Questionable"
    assert injuries[0]["description"] == "Calf tightness"


def test_extract_box_score_valid():
    raw_payload = {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Pittsburgh Steelers", "abbreviation": "PIT"},
                            "score": 18,
                            "linescores": [{"value": 6}, {"value": 3}, {"value": 3}, {"value": 6}]
                        },
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Atlanta Falcons", "abbreviation": "ATL"},
                            "score": 10,
                            "linescores": [{"value": 0}, {"value": 10}, {"value": 0}, {"value": 0}]
                        }
                    ]
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"displayName": "Pittsburgh Steelers", "abbreviation": "PIT"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "270"},
                        {"name": "netPassingYards", "displayValue": "133"},
                        {"name": "rushingYards", "displayValue": "137"},
                        {"name": "turnovers", "displayValue": "0"},
                        {"name": "thirdDownEff", "displayValue": "8-17"},
                        {"name": "possessionTime", "displayValue": "35:36"}
                    ]
                },
                {
                    "team": {"displayName": "Atlanta Falcons", "abbreviation": "ATL"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "226"},
                        {"name": "netPassingYards", "displayValue": "137"},
                        {"name": "rushingYards", "displayValue": "89"},
                        {"name": "turnovers", "displayValue": "3"},
                        {"name": "thirdDownEff", "displayValue": "2-9"},
                        {"name": "possessionTime", "displayValue": "24:24"}
                    ]
                }
            ]
        },
        "leaders": [
            {
                "team": {"abbreviation": "PIT"},
                "leaders": [
                    {
                        "name": "passingYards",
                        "leaders": [
                            {
                                "athlete": {"displayName": "Justin Fields"},
                                "displayValue": "17/23, 156 YDS"
                            }
                        ]
                    },
                    {
                        "name": "rushingYards",
                        "leaders": [
                            {
                                "athlete": {"displayName": "Najee Harris"},
                                "displayValue": "20 CAR, 70 YDS"
                            }
                        ]
                    }
                ]
            },
            {
                "team": {"abbreviation": "ATL"},
                "leaders": [
                    {
                        "name": "passingYards",
                        "leaders": [
                            {
                                "athlete": {"displayName": "Kirk Cousins"},
                                "displayValue": "16/26, 155 YDS, 1 TD, 2 INT"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    box = extract_box_score(raw_payload)
    assert box["away_team"] == "Pittsburgh Steelers"
    assert box["away_abbrev"] == "PIT"
    assert box["away_score"] == 18
    assert box["away_linescores"] == ["6", "3", "3", "6"]
    assert box["home_team"] == "Atlanta Falcons"
    assert box["home_abbrev"] == "ATL"
    assert box["home_score"] == 10
    assert box["home_linescores"] == ["0", "10", "0", "0"]
    assert box["quarter_labels"] == ["1", "2", "3", "4"]

    # Team stats
    assert len(box["team_stats"]) == 6
    stat_names = [s["stat"] for s in box["team_stats"]]
    assert "Total Yards" in stat_names
    assert "Net Passing Yards" in stat_names
    assert "Rushing Yards" in stat_names
    assert "Turnovers" in stat_names
    assert "Third Down Efficiency" in stat_names
    assert "Time Of Possession" in stat_names
    tot_yards = next(s for s in box["team_stats"] if s["stat"] == "Total Yards")
    assert tot_yards["away"] == "270"
    assert tot_yards["home"] == "226"

    # Top performers
    assert len(box["top_performers"]) == 3
    passer = box["top_performers"][0]
    assert "PASS (PIT)" in passer["category"]
    assert passer["player"] == "Justin Fields"
    assert passer["stat"] == "17/23, 156 YDS"


def test_extract_box_score_empty():
    assert extract_box_score({}) == {}
    assert extract_box_score(None) == {}
    assert extract_box_score({"header": {}}) == {}


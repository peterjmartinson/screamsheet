"""Unit tests for NBADataProvider."""
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.nba_provider import NBADataProvider


# ---------------------------------------------------------------------------
# Helpers: fake DataFrames that mimic nba_api outputs
# ---------------------------------------------------------------------------

def _make_gamefinder_df(game_id: str, home_team: str, away_team: str,
                        home_score: int, away_score: int,
                        home_matchup: str, away_matchup: str) -> pd.DataFrame:
    """Two-row DataFrame as returned by LeagueGameFinder (one row per team)."""
    return pd.DataFrame([
        {
            "GAME_ID": game_id,
            "TEAM_ID": 1610612755,
            "TEAM_NAME": home_team,
            "MATCHUP": home_matchup,   # e.g. "PHI vs. BOS" — home team
            "PTS": home_score,
            "GAME_DATE": "2026-05-03",
        },
        {
            "GAME_ID": game_id,
            "TEAM_ID": 1610612738,
            "TEAM_NAME": away_team,
            "MATCHUP": away_matchup,   # e.g. "BOS @ PHI" — away team
            "PTS": away_score,
            "GAME_DATE": "2026-05-03",
        },
    ])


# ---------------------------------------------------------------------------
# get_game_scores — home/away detection
# ---------------------------------------------------------------------------

class TestGetGameScoresHomeAway:
    """Ensure MATCHUP column drives home/away assignment."""

    def test_home_team_uses_vs_matchup(self):
        """Team whose MATCHUP contains 'vs.' is the home team."""
        df = _make_gamefinder_df(
            game_id="0022500001",
            home_team="Philadelphia 76ers",
            away_team="Boston Celtics",
            home_score=110,
            away_score=105,
            home_matchup="PHI vs. BOS",
            away_matchup="BOS @ PHI",
        )

        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [df]
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert len(scores) == 1
        game = scores[0]
        assert game["home_team"] == "Philadelphia 76ers"
        assert game["away_team"] == "Boston Celtics"
        assert game["home_score"] == 110
        assert game["away_score"] == 105

    def test_away_team_uses_at_matchup(self):
        """Team whose MATCHUP contains '@' is the away team."""
        df = _make_gamefinder_df(
            game_id="0022500002",
            home_team="New York Knicks",
            away_team="Milwaukee Bucks",
            home_score=98,
            away_score=101,
            home_matchup="NYK vs. MIL",
            away_matchup="MIL @ NYK",
        )

        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [df]
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert len(scores) == 1
        assert scores[0]["home_team"] == "New York Knicks"
        assert scores[0]["away_team"] == "Milwaukee Bucks"

    def test_empty_result_returns_empty_list(self):
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [pd.DataFrame()]
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))
        assert scores == []


# ---------------------------------------------------------------------------
# has_game
# ---------------------------------------------------------------------------

class TestHasGame:
    def test_returns_true_when_team_played(self):
        df = pd.DataFrame([{
            "GAME_ID": "0022500001",
            "TEAM_ID": 1610612755,
            "TEAM_NAME": "Philadelphia 76ers",
            "MATCHUP": "PHI vs. BOS",
            "PTS": 110,
            "GAME_DATE": "2026-05-03",
        }])
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [df]
            provider = NBADataProvider()
            assert provider.has_game(1610612755, datetime(2026, 5, 3)) is True

    def test_returns_false_when_team_did_not_play(self):
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [pd.DataFrame()]
            provider = NBADataProvider()
            assert provider.has_game(1610612755, datetime(2026, 5, 3)) is False


# ---------------------------------------------------------------------------
# _get_game_id
# ---------------------------------------------------------------------------

class TestGetGameId:
    def test_returns_game_id_when_found(self):
        df = pd.DataFrame([{
            "GAME_ID": "0022500001",
            "TEAM_ID": 1610612755,
            "TEAM_NAME": "Philadelphia 76ers",
            "MATCHUP": "PHI vs. BOS",
            "PTS": 110,
            "GAME_DATE": "2026-05-03",
        }])
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [df]
            provider = NBADataProvider()
            game_id = provider._get_game_id(1610612755, datetime(2026, 5, 3))
        assert game_id == "0022500001"

    def test_returns_none_when_no_game(self):
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [pd.DataFrame()]
            provider = NBADataProvider()
            game_id = provider._get_game_id(1610612755, datetime(2026, 5, 3))
        assert game_id is None


# ---------------------------------------------------------------------------
# get_box_score
# ---------------------------------------------------------------------------

def _make_boxscore_df(team_id: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "TEAM_ID": team_id,
            "PLAYER_NAME": "Joel Embiid",
            "MIN": "32:41",
            "FGM": 9, "FGA": 18,
            "FG3M": 1, "FG3A": 3,
            "FTM": 8, "FTA": 9,
            "REB": 10, "AST": 3, "STL": 1, "BLK": 2, "PTS": 27,
        },
        {
            "TEAM_ID": team_id,
            "PLAYER_NAME": "Tyrese Maxey",
            "MIN": "35:12",
            "FGM": 7, "FGA": 14,
            "FG3M": 3, "FG3A": 6,
            "FTM": 4, "FTA": 4,
            "REB": 4, "AST": 6, "STL": 2, "BLK": 0, "PTS": 21,
        },
    ])


class TestGetBoxScore:
    def test_returns_player_stats_dict(self):
        team_id = 1610612755
        finder_df = pd.DataFrame([{
            "GAME_ID": "0022500001",
            "TEAM_ID": team_id,
            "TEAM_NAME": "Philadelphia 76ers",
            "MATCHUP": "PHI vs. BOS",
            "PTS": 110,
            "GAME_DATE": "2026-05-03",
        }])
        box_df = _make_boxscore_df(team_id)

        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder, patch(
            "screamsheet.providers.nba_provider.boxscoretraditionalv2.BoxScoreTraditionalV2"
        ) as mock_box:
            mock_finder.return_value.get_data_frames.return_value = [finder_df]
            mock_box.return_value.get_data_frames.return_value = [box_df]

            provider = NBADataProvider()
            result = provider.get_box_score(team_id, datetime(2026, 5, 3))

        assert result is not None
        assert "player_stats" in result
        assert len(result["player_stats"]) == 2
        first = result["player_stats"][0]
        assert first["name"] == "Joel Embiid"
        assert first["PTS"] == 27
        assert first["REB"] == 10
        assert "FG" in first   # e.g. "9-18"

    def test_returns_none_when_no_game(self):
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [pd.DataFrame()]
            provider = NBADataProvider()
            result = provider.get_box_score(1610612755, datetime(2026, 5, 3))
        assert result is None

    def test_dnp_players_with_nan_stats_are_excluded(self):
        """Players marked DNP have NaN stat values and must not crash get_box_score."""
        import math
        team_id = 1610612755
        finder_df = pd.DataFrame([{
            "GAME_ID": "0022500001",
            "TEAM_ID": team_id,
            "TEAM_NAME": "Philadelphia 76ers",
            "MATCHUP": "PHI vs. BOS",
            "PTS": 110,
            "GAME_DATE": "2026-05-03",
        }])
        box_df = pd.DataFrame([
            {
                "TEAM_ID": team_id,
                "PLAYER_NAME": "Joel Embiid",
                "MIN": "32:41",
                "FGM": 9, "FGA": 18,
                "FG3M": 1, "FG3A": 3,
                "FTM": 8, "FTA": 9,
                "REB": 10, "AST": 3, "STL": 1, "BLK": 2, "PTS": 27,
            },
            {
                "TEAM_ID": team_id,
                "PLAYER_NAME": "Paul George",  # DNP
                "MIN": float("nan"),
                "FGM": float("nan"), "FGA": float("nan"),
                "FG3M": float("nan"), "FG3A": float("nan"),
                "FTM": float("nan"), "FTA": float("nan"),
                "REB": float("nan"), "AST": float("nan"),
                "STL": float("nan"), "BLK": float("nan"),
                "PTS": float("nan"),
            },
        ])

        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder, patch(
            "screamsheet.providers.nba_provider.boxscoretraditionalv2.BoxScoreTraditionalV2"
        ) as mock_box:
            mock_finder.return_value.get_data_frames.return_value = [finder_df]
            mock_box.return_value.get_data_frames.return_value = [box_df]

            provider = NBADataProvider()
            result = provider.get_box_score(team_id, datetime(2026, 5, 3))

        assert result is not None
        names = [p["name"] for p in result["player_stats"]]
        assert "Joel Embiid" in names
        assert "Paul George" not in names, "DNP player with NaN MIN must be excluded"


# ---------------------------------------------------------------------------
# get_all_teams_for_date
# ---------------------------------------------------------------------------

class TestNBAGetAllTeamsForDate:
    def test_returns_both_teams_from_completed_game(self):
        df = _make_gamefinder_df(
            game_id="0022500001",
            home_team="Philadelphia 76ers",
            away_team="Boston Celtics",
            home_score=110,
            away_score=105,
            home_matchup="PHI vs. BOS",
            away_matchup="BOS @ PHI",
        )
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [df]
            provider = NBADataProvider()
            result = provider.get_all_teams_for_date(datetime(2026, 5, 3))

        assert (1610612755, "Philadelphia 76ers") in result
        assert (1610612738, "Boston Celtics") in result

    def test_returns_empty_when_no_games(self):
        with patch(
            "screamsheet.providers.nba_provider.leaguegamefinder.LeagueGameFinder"
        ) as mock_finder:
            mock_finder.return_value.get_data_frames.return_value = [pd.DataFrame()]
            provider = NBADataProvider()
            result = provider.get_all_teams_for_date(datetime(2026, 5, 3))
        assert result == []

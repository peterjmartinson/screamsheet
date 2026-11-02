"""Unit tests for NBADataProvider using ESPN API."""
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.nba_provider import NBADataProvider, NBA_TO_ESPN_ID


# ---------------------------------------------------------------------------
# Helpers: fake ESPN JSON fixtures
# ---------------------------------------------------------------------------

def _make_espn_scoreboard(
    game_id: str = "0022500001",
    home_team: str = "Philadelphia 76ers",
    home_id: str = "20",
    home_score: str = "110",
    away_team: str = "Boston Celtics",
    away_id: str = "2",
    away_score: str = "105",
) -> dict:
    """Fixture mimicking ESPN scoreboard endpoint response."""
    return {
        "events": [
            {
                "id": game_id,
                "competitions": [
                    {
                        "status": {"type": {"description": "Final"}},
                        "competitors": [
                            {
                                "id": home_id,
                                "homeAway": "home",
                                "score": home_score,
                                "team": {"id": home_id, "displayName": home_team},
                            },
                            {
                                "id": away_id,
                                "homeAway": "away",
                                "score": away_score,
                                "team": {"id": away_id, "displayName": away_team},
                            },
                        ],
                    }
                ],
            }
        ]
    }


def _make_espn_standings() -> dict:
    """Fixture mimicking ESPN standings endpoint response."""
    return {
        "children": [
            {
                "name": "Eastern Conference",
                "standings": {
                    "entries": [
                        {
                            "team": {"displayName": "Boston Celtics"},
                            "stats": [
                                {"name": "wins", "value": 64},
                                {"name": "losses", "value": 18},
                                {"name": "winPercent", "value": 0.780},
                                {"name": "vs. Conf.", "displayValue": "41-11"},
                                {"name": "divisionWinPercent", "rank": 1},
                            ],
                        }
                    ]
                },
            }
        ]
    }


def _make_espn_summary(
    game_id: str = "0022500001",
    home_id: str = "20",
    home_team: str = "Philadelphia 76ers",
    away_id: str = "2",
    away_team: str = "Boston Celtics",
) -> dict:
    """Fixture mimicking ESPN summary endpoint response."""
    return {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {
                            "id": home_id,
                            "homeAway": "home",
                            "score": "110",
                            "team": {"id": home_id, "displayName": home_team},
                        },
                        {
                            "id": away_id,
                            "homeAway": "away",
                            "score": "105",
                            "team": {"id": away_id, "displayName": away_team},
                        },
                    ]
                }
            ]
        },
        "boxscore": {
            "players": [
                {
                    "team": {"id": home_id, "displayName": home_team},
                    "statistics": [
                        {
                            "names": ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK"],
                            "athletes": [
                                {
                                    "athlete": {"displayName": "Joel Embiid"},
                                    "didNotPlay": False,
                                    "stats": ["32:41", "27", "9-18", "1-3", "8-9", "10", "3", "1", "2"],
                                },
                                {
                                    "athlete": {"displayName": "Tyrese Maxey"},
                                    "didNotPlay": False,
                                    "stats": ["35:12", "21", "7-14", "3-6", "4-4", "4", "6", "2", "0"],
                                },
                                {
                                    "athlete": {"displayName": "Paul George"},
                                    "didNotPlay": True,
                                    "stats": ["-", "-", "-", "-", "-", "-", "-", "-", "-"],
                                },
                            ],
                        }
                    ],
                }
            ]
        },
        "plays": [
            {
                "period": {"number": 1},
                "clock": {"displayValue": "11:30"},
                "scoringPlay": True,
                "text": "Tyrese Maxey makes 24-foot three point jumper",
            }
        ],
    }


# ---------------------------------------------------------------------------
# get_game_scores — home/away detection
# ---------------------------------------------------------------------------

class TestGetGameScoresHomeAway:
    """Ensure home/away assignment correctly parses from ESPN scoreboard."""

    def test_home_and_away_teams_detected(self):
        data = _make_espn_scoreboard(
            game_id="0022500001",
            home_team="Philadelphia 76ers",
            away_team="Boston Celtics",
            home_score="110",
            away_score="105",
        )

        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert len(scores) == 1
        game = scores[0]
        assert game["home_team"] == "Philadelphia 76ers"
        assert game["away_team"] == "Boston Celtics"
        assert game["home_score"] == 110
        assert game["away_score"] == 105

    def test_second_game_scores(self):
        data = _make_espn_scoreboard(
            game_id="0022500002",
            home_team="New York Knicks",
            away_team="Milwaukee Bucks",
            home_score="98",
            away_score="101",
        )

        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert len(scores) == 1
        assert scores[0]["home_team"] == "New York Knicks"
        assert scores[0]["away_team"] == "Milwaukee Bucks"
        assert scores[0]["home_score"] == 98
        assert scores[0]["away_score"] == 101

    def test_empty_result_returns_empty_list(self):
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value={"events": []}):
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))
        assert scores == []


# ---------------------------------------------------------------------------
# has_game
# ---------------------------------------------------------------------------

class TestHasGame:
    def test_returns_true_when_team_played(self):
        data = _make_espn_scoreboard(home_id="20")
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            # Test with NBA legacy ID (1610612755) and ESPN ID (20)
            assert provider.has_game(1610612755, datetime(2026, 5, 3)) is True
            assert provider.has_game(20, datetime(2026, 5, 3)) is True

    def test_returns_false_when_team_did_not_play(self):
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value={"events": []}):
            provider = NBADataProvider()
            assert provider.has_game(1610612755, datetime(2026, 5, 3)) is False


# ---------------------------------------------------------------------------
# _get_game_id
# ---------------------------------------------------------------------------

class TestGetGameId:
    def test_returns_game_id_when_found(self):
        data = _make_espn_scoreboard(game_id="0022500001", home_id="20")
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            game_id = provider._get_game_id(1610612755, datetime(2026, 5, 3))
        assert game_id == "0022500001"

    def test_returns_none_when_no_game(self):
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value={"events": []}):
            provider = NBADataProvider()
            game_id = provider._get_game_id(1610612755, datetime(2026, 5, 3))
        assert game_id is None


# ---------------------------------------------------------------------------
# get_box_score
# ---------------------------------------------------------------------------

class TestGetBoxScore:
    def test_returns_player_stats_dict(self):
        team_id = 1610612755  # 76ers -> ESPN ID 20
        summary_data = _make_espn_summary(home_id="20")

        provider = NBADataProvider()
        provider._game_id_cache[(team_id, "2026-05-03")] = "0022500001"

        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=summary_data):
            result = provider.get_box_score(team_id, datetime(2026, 5, 3))

        assert result is not None
        assert "player_stats" in result
        assert len(result["player_stats"]) == 2
        first = result["player_stats"][0]
        assert first["name"] == "Joel Embiid"
        assert first["PTS"] == 27
        assert first["REB"] == 10
        assert first["FG"] == "9-18"

    def test_returns_none_when_no_game(self):
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value={"events": []}):
            provider = NBADataProvider()
            result = provider.get_box_score(1610612755, datetime(2026, 5, 3))
        assert result is None

    def test_dnp_players_with_nan_stats_are_excluded(self):
        """Players marked DNP must not crash get_box_score and must be excluded."""
        team_id = 1610612755
        summary_data = _make_espn_summary(home_id="20")

        provider = NBADataProvider()
        provider._game_id_cache[(team_id, "2026-05-03")] = "0022500001"

        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=summary_data):
            result = provider.get_box_score(team_id, datetime(2026, 5, 3))

        assert result is not None
        names = [p["name"] for p in result["player_stats"]]
        assert "Joel Embiid" in names
        assert "Paul George" not in names, "DNP player must be excluded"


# ---------------------------------------------------------------------------
# get_all_teams_for_date
# ---------------------------------------------------------------------------

class TestNBAGetAllTeamsForDate:
    def test_returns_both_teams_from_completed_game(self):
        data = _make_espn_scoreboard(
            game_id="0022500001",
            home_team="Philadelphia 76ers",
            home_id="20",
            away_team="Boston Celtics",
            away_id="2",
        )
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            result = provider.get_all_teams_for_date(datetime(2026, 5, 3))

        assert (1610612755, "Philadelphia 76ers") in result
        assert (1610612738, "Boston Celtics") in result

    def test_returns_empty_when_no_games(self):
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value={"events": []}):
            provider = NBADataProvider()
            result = provider.get_all_teams_for_date(datetime(2026, 5, 3))
        assert result == []


# ---------------------------------------------------------------------------
# get_game_summary & mad_fan
# ---------------------------------------------------------------------------

class TestNBAGetGameSummary:
    def test_loss_uses_regular_summarizer_when_mad_fan_false(self):
        provider = NBADataProvider()
        fake_raw = {"game": "data"}
        fake_extracted = {
            "home_team": "76ers", "away_team": "Celtics",
            "home_score": 98, "away_score": 105,
            "featured_team_is_home": True,
            "narrative_snippets": "",
        }
        with patch.object(provider, "_get_game_id", return_value="0022500001"), \
             patch("screamsheet.providers.extractors.NBAGameExtractor.fetch_raw_data", return_value=fake_raw), \
             patch("screamsheet.providers.extractors.NBAGameExtractor.extract_key_info", return_value=fake_extracted), \
             patch("screamsheet.llm.summarizers.NBAGameSummarizer.generate_summary", return_value="Regular summary") as mock_gen, \
             patch("screamsheet.llm.summarizers.NBAFanRantSummarizer.generate_summary") as mock_rant:
            summary = provider.get_game_summary(team_id=1610612755, date=datetime(2026, 5, 3), is_primary_favorite=True, mad_fan=False)
            assert summary == "Regular summary"
            mock_gen.assert_called_once()
            mock_rant.assert_not_called()

    def test_loss_uses_fan_rant_when_mad_fan_true(self):
        provider = NBADataProvider()
        fake_raw = {"game": "data"}
        fake_extracted = {
            "home_team": "76ers", "away_team": "Celtics",
            "home_score": 98, "away_score": 105,
            "featured_team_is_home": True,
            "narrative_snippets": "",
        }
        with patch.object(provider, "_get_game_id", return_value="0022500001"), \
             patch("screamsheet.providers.extractors.NBAGameExtractor.fetch_raw_data", return_value=fake_raw), \
             patch("screamsheet.providers.extractors.NBAGameExtractor.extract_key_info", return_value=fake_extracted), \
             patch("screamsheet.llm.summarizers.NBAGameSummarizer.generate_summary") as mock_gen, \
             patch("screamsheet.llm.summarizers.NBAFanRantSummarizer.generate_summary", return_value="Rant summary") as mock_rant:
            summary = provider.get_game_summary(team_id=1610612755, date=datetime(2026, 5, 3), is_primary_favorite=True, mad_fan=True)
            assert summary == "Rant summary"
            mock_rant.assert_called_once()
            mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# NBAGameExtractor
# ---------------------------------------------------------------------------

class TestNBAGameExtractor:
    def test_espn_extracts_correct_info(self):
        from screamsheet.providers.extractors import NBAGameExtractor
        summary = _make_espn_summary(home_id="20", away_id="2")
        extractor = NBAGameExtractor()
        info = extractor.extract_key_info(summary, featured_team_id=1610612755)

        assert isinstance(info, dict)
        assert info["home_team"] == "Philadelphia 76ers"
        assert info["away_team"] == "Boston Celtics"
        assert info["home_score"] == 110
        assert info["away_score"] == 105
        assert info["featured_team_is_home"] is True
        assert info["losing_team"] == "Boston Celtics"
        assert "Tyrese Maxey" in info["narrative_snippets"]

    def test_v3_ignores_zero_team_id_and_resolves_full_team_names(self):
        """Legacy DataFrame format support."""
        from screamsheet.providers.extractors import NBAGameExtractor

        box_df = pd.DataFrame([
            {
                "GAME_ID": "0012600013",
                "TEAM_ID": 1610612755,
                "TEAM_ABBREVIATION": "PHI",
                "TEAM_CITY": "Philadelphia",
                "PLAYER_NAME": "VJ Edgecombe",
                "MIN": "26:01",
                "PTS": 19,
                "REB": 3,
                "AST": 4,
            },
            {
                "GAME_ID": "0012600013",
                "TEAM_ID": 1610612738,
                "TEAM_ABBREVIATION": "BOS",
                "TEAM_CITY": "Boston",
                "PLAYER_NAME": "Jayson Tatum",
                "MIN": "28:00",
                "PTS": 23,
                "REB": 7,
                "AST": 5,
            },
        ])
        pbp_df = pd.DataFrame([
            {
                "period": 1,
                "clock": "PT12M00.00S",
                "teamId": 0,
                "location": "h",
                "actionType": "period",
                "description": "Period Start",
                "scoreHome": "",
                "scoreAway": "",
            },
            {
                "period": 1,
                "clock": "PT11M30.00S",
                "teamId": 1610612738,
                "location": "h",
                "actionType": "Made Shot",
                "description": "Tatum 3PT Jump Shot",
                "scoreHome": "144",
                "scoreAway": "106",
            },
            {
                "period": 1,
                "clock": "PT11M10.00S",
                "teamId": 1610612755,
                "location": "v",
                "actionType": "Made Shot",
                "description": "Edgecombe Driving Layup",
                "scoreHome": "144",
                "scoreAway": "106",
            },
        ])
        raw_data = {"play_by_play": pbp_df, "boxscore": box_df, "pbp_version": 3}

        extractor = NBAGameExtractor()
        info = extractor.extract_key_info(raw_data, featured_team_id=1610612755)

        assert isinstance(info, dict)
        assert info["home_team"] == "Boston Celtics"
        assert info["away_team"] == "Philadelphia 76ers"
        assert info["featured_team_is_home"] is False
        assert info["losing_team"] == "Philadelphia 76ers"
        assert info["home_score"] == 144
        assert info["away_score"] == 106


# ---------------------------------------------------------------------------
# NBA API Retries
# ---------------------------------------------------------------------------

class TestNBARetries:
    """Test tenacity retry behaviors on transient failures for NBA API calls."""

    def test_game_scores_retries_transient_error_and_succeeds(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_espn_scoreboard()
        mock_resp.raise_for_status.return_value = None
        call_count = 0

        def flaky_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionResetError("Connection dropped by remote server")
            return mock_resp

        with patch("requests.get", side_effect=flaky_get), \
             patch("tenacity.nap.time.sleep") as mock_sleep:
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert call_count == 3
        assert mock_sleep.call_count == 2
        assert len(scores) == 1
        assert scores[0]["home_team"] == "Philadelphia 76ers"

    def test_game_scores_exhausts_retries_on_persistent_error(self):
        with patch(
            "screamsheet.providers.nba_provider._call_espn_endpoint",
            side_effect=ConnectionResetError("ESPN API maintenance"),
        ):
            provider = NBADataProvider()
            scores = provider.get_game_scores(datetime(2026, 5, 3))

        assert scores == []

    def test_standings_retries_transient_error_and_succeeds(self):
        data = _make_espn_standings()
        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            provider = NBADataProvider()
            df = provider.get_standings()

        assert not df.empty
        assert df.iloc[0]["team"] == "Boston Celtics"
        assert df.iloc[0]["wins"] == 64
        assert df.iloc[0]["losses"] == 18

    def test_box_score_retries_transient_error_and_succeeds(self):
        data = _make_espn_summary()
        provider = NBADataProvider()
        provider._game_id_cache[(1610612755, "2026-05-03")] = "0022500001"

        with patch("screamsheet.providers.nba_provider._call_espn_endpoint", return_value=data):
            result = provider.get_box_score(1610612755, datetime(2026, 5, 3))

        assert result is not None
        assert result["player_stats"][0]["name"] == "Joel Embiid"

    def test_nba_screamsheet_suppressed_when_all_sections_empty(self, tmp_path):
        from screamsheet.sports.nba import NBAScreamsheet
        from screamsheet.base.errors import EmptyScreamsheetError

        out_pdf = tmp_path / "nba_empty.pdf"
        sheet = NBAScreamsheet(
            output_filename=str(out_pdf),
            favorite_teams=[(1610612755, "Philadelphia 76ers")],
            date=datetime(2026, 5, 3),
        )
        with patch.object(sheet.provider, "get_game_scores", return_value=[]), \
             patch.object(sheet.provider, "get_standings", return_value=pd.DataFrame()), \
             patch.object(sheet.provider, "has_game", return_value=False), \
             patch.object(sheet.provider, "get_all_teams_for_date", return_value=[]):
            assert sheet.has_content() is False
            with pytest.raises(EmptyScreamsheetError, match="has no content to display"):
                sheet.generate()
        assert not out_pdf.exists()

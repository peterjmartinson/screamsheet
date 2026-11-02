"""Unit tests for SoccerDataProvider and Match of the Day ranking."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from screamsheet.providers.soccer_provider import (
    AL_NASSR_TEAM_ID,
    PORTUGAL_TEAM_ID,
    SoccerDataProvider,
    score_fixture_for_motd,
)


@pytest.fixture
def provider():
    # Construct without API key to test offline / sample fallback mode
    return SoccerDataProvider(api_key="")


@pytest.fixture
def sample_date():
    return datetime(2026, 11, 1)


class TestScoreFixtureForMOTD:
    def test_al_nassr_hard_affinity_lock(self):
        fixture_nassr = {
            "fixture_id": 100,
            "home_id": AL_NASSR_TEAM_ID,
            "home_team": "Al-Nassr",
            "away_id": 999,
            "away_team": "Al-Okhdood",
            "home_score": 2,
            "away_score": 0,
            "league_id": 307,
            "status_short": "FT",
        }
        score = score_fixture_for_motd(fixture_nassr)
        assert score >= 10000.0

    def test_portugal_hard_affinity_lock(self):
        fixture_portugal = {
            "fixture_id": 101,
            "home_id": 500,
            "home_team": "Spain",
            "away_id": PORTUGAL_TEAM_ID,
            "away_team": "Portugal",
            "home_score": 1,
            "away_score": 2,
            "league_id": 5,
            "status_short": "FT",
        }
        score = score_fixture_for_motd(fixture_portugal)
        assert score >= 8000.0

    def test_champions_league_higher_than_regular_league(self):
        ucl_game = {
            "fixture_id": 102,
            "home_id": 11,
            "home_team": "Club A",
            "away_id": 12,
            "away_team": "Club B",
            "home_score": 1,
            "away_score": 0,
            "league_id": 2,  # UEFA Champions League
            "status_short": "FT",
        }
        spl_game = {
            "fixture_id": 103,
            "home_id": 13,
            "home_team": "Club C",
            "away_id": 14,
            "away_team": "Club D",
            "home_score": 1,
            "away_score": 0,
            "league_id": 307,  # Saudi Pro League
            "status_short": "FT",
        }
        assert score_fixture_for_motd(ucl_game) > score_fixture_for_motd(spl_game)

    def test_marquee_club_multiplier(self):
        # Real Madrid (541) vs Barcelona (529) (El Clasico)
        el_clasico = {
            "fixture_id": 104,
            "home_id": 541,
            "home_team": "Real Madrid",
            "away_id": 529,
            "away_team": "Barcelona",
            "home_score": 3,
            "away_score": 2,
            "league_id": 140,
            "status_short": "FT",
        }
        other_laliga = {
            "fixture_id": 105,
            "home_id": 530,
            "home_team": "Getafe",
            "away_id": 531,
            "away_team": "Osasuna",
            "home_score": 3,
            "away_score": 2,
            "league_id": 140,
            "status_short": "FT",
        }
        assert score_fixture_for_motd(el_clasico) > score_fixture_for_motd(other_laliga) + 50.0

    def test_extra_time_or_penalties_adds_drama_points(self):
        ft_game = {
            "fixture_id": 106,
            "home_id": 50,
            "away_id": 40,
            "home_score": 2,
            "away_score": 2,
            "league_id": 39,
            "status_short": "FT",
        }
        pen_game = {
            "fixture_id": 107,
            "home_id": 50,
            "away_id": 40,
            "home_score": 2,
            "away_score": 2,
            "league_id": 39,
            "status_short": "PEN",
        }
        assert score_fixture_for_motd(pen_game) > score_fixture_for_motd(ft_game)


class TestSoccerDataProvider:
    def test_get_game_scores_sample_mode(self, provider, sample_date):
        scores = provider.get_game_scores(sample_date)
        assert len(scores) >= 3
        # Ensure Al-Nassr match is present in sample mode
        nassr_matches = [
            s for s in scores
            if s.get("home_id") == AL_NASSR_TEAM_ID or s.get("away_id") == AL_NASSR_TEAM_ID
        ]
        assert len(nassr_matches) >= 1
        al_nassr = nassr_matches[0]
        assert al_nassr["home_team"] == "Al-Nassr"
        assert al_nassr["home_score"] == 3

    def test_get_standings_sample_mode(self, provider):
        standings = provider.get_standings()
        assert "Saudi Pro League" in standings
        assert "Premier League" in standings
        spl_df = standings["Saudi Pro League"]
        assert isinstance(spl_df, pd.DataFrame)
        assert not spl_df.empty
        assert "Al-Nassr" in spl_df["team"].values

    def test_get_match_of_the_day_selects_al_nassr(self, provider, sample_date):
        motd = provider.get_match_of_the_day(sample_date)
        assert motd is not None
        assert motd["home_id"] == AL_NASSR_TEAM_ID
        assert motd["home_team"] == "Al-Nassr"

    def test_get_box_score_structure(self, provider, sample_date):
        box = provider.get_box_score(1204851, sample_date)
        assert box is not None
        assert "home_team" in box
        assert "away_team" in box
        assert "starting_xi" in box
        assert "team_metrics" in box
        assert "key_events" in box
        assert "ronaldo_spotlight" in box
        assert box["ronaldo_spotlight"]["featured"] is True
        assert box["ronaldo_spotlight"]["goals"] >= 1

    def test_has_game_and_all_teams(self, provider, sample_date):
        assert provider.has_game(AL_NASSR_TEAM_ID, sample_date) is True
        assert provider.has_game(999999, sample_date) is False
        teams = provider.get_all_teams_for_date(sample_date)
        assert any(t[0] == AL_NASSR_TEAM_ID for t in teams)

    def test_api_calls_with_mocked_requests(self):
        active_provider = SoccerDataProvider(api_key="test_api_key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {"id": 9991, "status": {"long": "Match Finished", "short": "FT"}},
                    "league": {"id": 39, "name": "Premier League", "country": "England"},
                    "teams": {
                        "home": {"id": 50, "name": "Manchester City"},
                        "away": {"id": 40, "name": "Liverpool"},
                    },
                    "goals": {"home": 2, "away": 2},
                    "score": {"penalty": {}, "aggregate": {}},
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_response):
            scores = active_provider.get_game_scores(datetime(2026, 11, 1))
            assert len(scores) == 1
            assert scores[0]["fixture_id"] == 9991
            assert scores[0]["home_team"] == "Manchester City"
            assert scores[0]["away_score"] == 2

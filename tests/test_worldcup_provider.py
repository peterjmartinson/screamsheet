"""Unit tests for WorldCup26Provider (worldcup26.ir)."""
from __future__ import annotations
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from screamsheet.providers.worldcup26_provider import (
    WorldCup26Provider,
    PRIORITY_TEAM_NAMES,
    _parse_scorers,
)


@pytest.fixture
def provider():
    return WorldCup26Provider()


@pytest.fixture
def sample_date():
    return datetime(2026, 6, 25)


def _mock(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


GAMES = {
    "games": [
        {
            "id": "7", "home_score": "3", "away_score": "1",
            "home_scorers": "null", "away_scorers": "null",
            "local_date": "06/25/2026 19:00", "finished": "TRUE", "type": "group",
            "home_team_name_en": "USA", "away_team_name_en": "England",
        },
        {
            "id": "8", "home_score": "2", "away_score": "0",
            "home_scorers": "null", "away_scorers": "null",
            "local_date": "06/25/2026 21:00", "finished": "TRUE", "type": "group",
            "home_team_name_en": "Australia", "away_team_name_en": "Turkey",
        },
        {  # wrong date
            "id": "5", "home_score": "1", "away_score": "1",
            "home_scorers": "null", "away_scorers": "null",
            "local_date": "06/24/2026 19:00", "finished": "TRUE",
            "home_team_name_en": "France", "away_team_name_en": "Germany",
        },
        {  # unfinished
            "id": "9", "home_score": "0", "away_score": "0",
            "home_scorers": "null", "away_scorers": "null",
            "local_date": "06/25/2026 23:00", "finished": "FALSE",
            "home_team_name_en": "Brazil", "away_team_name_en": "Mexico",
        },
    ]
}

TEAMS = {"teams": [{"id": "10", "name_en": "USA"}, {"id": "11", "name_en": "England"}]}
GROUPS = {
    "groups": [{
        "name": "A",
        "teams": [{"team_id": "10", "pts": "6", "gd": "3"}, {"team_id": "11", "pts": "3", "gd": "0"}],
    }]
}


class TestParseScorers:
    def test_null_returns_empty(self):
        assert _parse_scorers("null", "X") == []

    def test_empty_returns_empty(self):
        assert _parse_scorers("", "X") == []

    def test_single_scorer(self):
        raw = '{"H. Kane 12\'"}'
        ev = _parse_scorers(raw, "England")
        assert len(ev) == 1
        assert ev[0]["player"]["name"] == "H. Kane"
        assert ev[0]["time"]["elapsed"] == 12

    def test_penalty_detected(self):
        raw = '{"H. Kane 12\'(p)"}'
        ev = _parse_scorers(raw, "England")
        assert "(p)" in ev[0]["detail"]

    def test_extra_time_minute(self):
        raw = '{"Player 90+3\'"}'
        ev = _parse_scorers(raw, "Team")
        assert ev[0]["time"]["elapsed"] == 90

    def test_type_is_goal(self):
        raw = '{"Player 33\'"}'
        ev = _parse_scorers(raw, "T")
        assert ev[0]["type"] == "Goal"


class TestGetGameScores:
    def test_only_completed_on_date(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        assert len(r) == 2

    def test_required_keys(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        for k in ("fixture_id", "home_team", "away_team", "home_score", "away_score", "status_short"):
            assert k in r[0]

    def test_scores_are_ints(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        usa = next(g for g in r if g["home_team"] == "USA")
        assert usa["home_score"] == 3

    def test_status_ft(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        assert all(g["status_short"] == "FT" for g in r)

    def test_excludes_wrong_date(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        names = [g["home_team"] for g in r] + [g["away_team"] for g in r]
        assert "France" not in names

    def test_excludes_unfinished(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            r = provider.get_game_scores(sample_date)
        names = [g["home_team"] for g in r] + [g["away_team"] for g in r]
        assert "Brazil" not in names

    def test_empty_returns_empty(self, provider, sample_date):
        with patch("requests.get", return_value=_mock({"games": []})):
            assert provider.get_game_scores(sample_date) == []

    def test_games_cached(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)) as mr:
            provider.get_game_scores(sample_date)
            provider.get_game_scores(sample_date)
        assert mr.call_count == 1


class TestGetFixtureEvents:
    def test_unknown_fixture_returns_empty(self, provider):
        with patch("requests.get", return_value=_mock(GAMES)):
            assert provider.get_fixture_events(9999) == []

    def test_null_scorers_no_events(self, provider):
        with patch("requests.get", return_value=_mock(GAMES)):
            assert provider.get_fixture_events(7) == []


class TestGetStandings:
    def test_returns_groups(self, provider):
        with patch("requests.get", side_effect=[_mock(TEAMS), _mock(GROUPS)]):
            r = provider.get_standings()
        assert len(r) == 1

    def test_team_names_resolved(self, provider):
        with patch("requests.get", side_effect=[_mock(TEAMS), _mock(GROUPS)]):
            r = provider.get_standings()
        assert r[0][0]["team"]["name"] == "USA"

    def test_sorted_by_pts(self, provider):
        with patch("requests.get", side_effect=[_mock(TEAMS), _mock(GROUPS)]):
            r = provider.get_standings()
        pts = [e["points"] for e in r[0]]
        assert pts == sorted(pts, reverse=True)

    def test_empty_returns_empty(self, provider):
        with patch("requests.get", side_effect=[_mock(TEAMS), _mock({"groups": []})]):
            assert provider.get_standings() == []


class TestHasGame:
    def test_usa_played(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            assert provider.has_game(0, sample_date) is True

    def test_out_of_range_false(self, provider, sample_date):
        assert provider.has_game(999, sample_date) is False

    def test_no_games_false(self, provider, sample_date):
        with patch("requests.get", return_value=_mock({"games": []})):
            assert provider.has_game(0, sample_date) is False


class TestGetAllTeamsForDate:
    def test_four_pairs_for_two_games(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            pairs = provider.get_all_teams_for_date(sample_date)
        assert len(pairs) == 4

    def test_ids_are_ints(self, provider, sample_date):
        with patch("requests.get", return_value=_mock(GAMES)):
            pairs = provider.get_all_teams_for_date(sample_date)
        assert all(isinstance(fid, int) for fid, _ in pairs)

"""Unit tests for the NHL players SQLite cache (screamsheet.db)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.db.nhl_players_db import (
    get_db_path,
    init_db,
    lookup_player,
    lookup_player_by_id,
    lookup_player_by_name,
    upsert_players,
)
from screamsheet.db.nhl_players_sync import (
    fetch_all_team_abbreviations,
    fetch_team_roster,
    full_sync,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_db(tmp_path):
    """Initialised SQLite DB in a temp directory (not in-memory, so multiple
    engines can share the same file across helper calls)."""
    db = tmp_path / "test_players.db"
    init_db(db)
    return db


@pytest.fixture
def mcdavid():
    return {
        "player_id":         8478402,
        "player_first_name": "Connor",
        "player_last_name":  "McDavid",
        "position":          "C",
        "team":              "EDM",
        "raw_json":          json.dumps({"id": 8478402}),
    }


@pytest.fixture
def draisaitl():
    return {
        "player_id":         8477934,
        "player_first_name": "Leon",
        "player_last_name":  "Draisaitl",
        "position":          "C",
        "team":              "EDM",
        "raw_json":          json.dumps({"id": 8477934}),
    }


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "players.db"
        init_db(db)
        assert db.exists()

    def test_creates_players_table(self, tmp_path):
        import sqlalchemy as sa
        db = tmp_path / "players.db"
        engine = init_db(db)
        assert "players" in sa.inspect(engine).get_table_names()

    def test_idempotent(self, tmp_path):
        """Calling init_db twice must not raise."""
        db = tmp_path / "players.db"
        init_db(db)
        init_db(db)

    def test_get_db_path_returns_path(self):
        result = get_db_path()
        assert isinstance(result, Path)
        assert result.name == "nhl_players.db"


# ---------------------------------------------------------------------------
# upsert_players
# ---------------------------------------------------------------------------

class TestUpsertPlayers:
    def test_inserts_new_player(self, mem_db, mcdavid):
        count = upsert_players([mcdavid], mem_db)
        assert count == 1
        result = lookup_player_by_id(8478402, mem_db)
        assert result is not None
        assert result["player_last_name"] == "McDavid"

    def test_updates_existing_player(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        traded = {**mcdavid, "team": "TOR"}
        upsert_players([traded], mem_db)
        result = lookup_player_by_id(8478402, mem_db)
        assert result["team"] == "TOR"

    def test_sets_update_date(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        result = lookup_player_by_id(8478402, mem_db)
        assert result["update_date"] is not None

    def test_skips_entry_without_player_id(self, mem_db):
        bad = {"player_last_name": "Ghost", "player_first_name": "No ID"}
        count = upsert_players([bad], mem_db)
        assert count == 0

    def test_returns_count_for_multiple_players(self, mem_db, mcdavid, draisaitl):
        count = upsert_players([mcdavid, draisaitl], mem_db)
        assert count == 2

    def test_subsequent_upsert_does_not_duplicate(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        upsert_players([mcdavid], mem_db)
        results = lookup_player_by_name("McDavid", db_path=mem_db)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# lookup_player_by_id
# ---------------------------------------------------------------------------

class TestLookupPlayerById:
    def test_hit_returns_player_dict(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        result = lookup_player_by_id(8478402, mem_db)
        assert isinstance(result, dict)
        assert result["player_id"] == 8478402

    def test_miss_returns_none(self, mem_db):
        result = lookup_player_by_id(9999999, mem_db)
        assert result is None

    def test_result_has_all_expected_keys(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        result = lookup_player_by_id(8478402, mem_db)
        for key in ("id", "player_id", "player_last_name", "player_first_name",
                    "position", "team", "update_date", "raw_json"):
            assert key in result


# ---------------------------------------------------------------------------
# lookup_player_by_name
# ---------------------------------------------------------------------------

class TestLookupPlayerByName:
    def test_exact_last_name_match(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        results = lookup_player_by_name("McDavid", db_path=mem_db)
        assert len(results) == 1
        assert results[0]["player_first_name"] == "Connor"

    def test_case_insensitive(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        results = lookup_player_by_name("mcdavid", db_path=mem_db)
        assert len(results) == 1

    def test_first_name_filter_narrows_results(self, mem_db, draisaitl):
        fake = {**draisaitl, "player_id": 9000001, "player_first_name": "Fake"}
        upsert_players([draisaitl, fake], mem_db)
        results = lookup_player_by_name("Draisaitl", first_name="Leon", db_path=mem_db)
        assert len(results) == 1
        assert results[0]["player_first_name"] == "Leon"

    def test_miss_returns_empty_list(self, mem_db):
        results = lookup_player_by_name("Gretzky", db_path=mem_db)
        assert results == []

    def test_name_collision_returns_all_matches(self, mem_db):
        smith1 = {"player_id": 1001, "player_last_name": "Smith",
                  "player_first_name": "Adam", "position": "RW", "team": "BOS", "raw_json": "{}"}
        smith2 = {"player_id": 1002, "player_last_name": "Smith",
                  "player_first_name": "Zach", "position": "D",  "team": "NYR", "raw_json": "{}"}
        upsert_players([smith1, smith2], mem_db)
        results = lookup_player_by_name("Smith", db_path=mem_db)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# lookup_player (orchestrator)
# ---------------------------------------------------------------------------

class TestLookupPlayer:
    def test_cache_hit_requires_no_api_call(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        with patch("requests.get") as mock_get:
            result = lookup_player(player_id=8478402, db_path=mem_db)
        mock_get.assert_not_called()
        assert result["player_id"] == 8478402

    def test_api_fallback_on_cache_miss(self, mem_db):
        api_payload = {
            "firstName": {"default": "Connor"},
            "lastName":  {"default": "McDavid"},
            "position":  "C",
            "currentTeamAbbrev": "EDM",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = api_payload
        with patch("screamsheet.db.nhl_players_db.requests.get", return_value=mock_resp):
            result = lookup_player(player_id=8478402, db_path=mem_db)
        assert result is not None
        assert result["player_last_name"] == "McDavid"

    def test_api_fallback_upserts_into_cache(self, mem_db):
        api_payload = {
            "firstName": {"default": "Connor"},
            "lastName":  {"default": "McDavid"},
            "position":  "C",
            "currentTeamAbbrev": "EDM",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = api_payload
        with patch("screamsheet.db.nhl_players_db.requests.get", return_value=mock_resp):
            lookup_player(player_id=8478402, db_path=mem_db)
        # Second call must hit the cache — no further API call
        with patch("requests.get") as mock_get:
            result = lookup_player(player_id=8478402, db_path=mem_db)
        mock_get.assert_not_called()
        assert result is not None

    def test_returns_none_when_api_also_fails(self, mem_db):
        import requests as req_lib
        with patch(
            "screamsheet.db.nhl_players_db.requests.get",
            side_effect=req_lib.exceptions.RequestException("timeout"),
        ):
            result = lookup_player(player_id=9999999, db_path=mem_db)
        assert result is None

    def test_name_lookup_when_no_player_id(self, mem_db, mcdavid):
        upsert_players([mcdavid], mem_db)
        result = lookup_player(last_name="McDavid", db_path=mem_db)
        assert result is not None
        assert result["player_id"] == 8478402

    def test_returns_none_for_unknown_name(self, mem_db):
        result = lookup_player(last_name="Gretzky", db_path=mem_db)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_all_team_abbreviations
# ---------------------------------------------------------------------------

class TestFetchAllTeamAbbreviations:
    def _standings_payload(self, abbrevs):
        return {
            "standings": [
                {"teamAbbrev": {"default": a}, "teamName": {"default": a}}
                for a in abbrevs
            ]
        }

    def test_returns_sorted_abbreviations(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._standings_payload(["EDM", "BOS", "TOR"])
        with patch("screamsheet.db.nhl_players_sync.requests.get", return_value=mock_resp):
            result = fetch_all_team_abbreviations()
        assert result == ["BOS", "EDM", "TOR"]

    def test_skips_entries_without_abbrev(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "standings": [
                {"teamAbbrev": {"default": "EDM"}},
                {"teamName": {"default": "NoAbbrev"}},  # missing teamAbbrev key
            ]
        }
        with patch("screamsheet.db.nhl_players_sync.requests.get", return_value=mock_resp):
            result = fetch_all_team_abbreviations()
        assert result == ["EDM"]


# ---------------------------------------------------------------------------
# fetch_team_roster
# ---------------------------------------------------------------------------

class TestFetchTeamRoster:
    def _roster_payload(self):
        return {
            "forwards": [{
                "id": 8478402,
                "firstName": {"default": "Connor"},
                "lastName":  {"default": "McDavid"},
                "positionCode": "C",
            }],
            "defensemen": [{
                "id": 8480801,
                "firstName": {"default": "Evan"},
                "lastName":  {"default": "Bouchard"},
                "positionCode": "D",
            }],
            "goalies": [{
                "id": 8480045,
                "firstName": {"default": "Stuart"},
                "lastName":  {"default": "Skinner"},
                "positionCode": "G",
            }],
        }

    def test_returns_players_from_all_groups(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._roster_payload()
        with patch("screamsheet.db.nhl_players_sync.requests.get", return_value=mock_resp):
            result = fetch_team_roster("EDM")
        assert len(result) == 3

    def test_player_dict_has_required_keys(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._roster_payload()
        with patch("screamsheet.db.nhl_players_sync.requests.get", return_value=mock_resp):
            result = fetch_team_roster("EDM")
        for key in ("player_id", "player_first_name", "player_last_name", "position", "team"):
            assert key in result[0]

    def test_team_set_on_each_player(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._roster_payload()
        with patch("screamsheet.db.nhl_players_sync.requests.get", return_value=mock_resp):
            result = fetch_team_roster("EDM")
        assert all(p["team"] == "EDM" for p in result)

    def test_returns_empty_list_on_request_error(self):
        import requests as req_lib
        with patch(
            "screamsheet.db.nhl_players_sync.requests.get",
            side_effect=req_lib.exceptions.RequestException("timeout"),
        ):
            result = fetch_team_roster("EDM")
        assert result == []


# ---------------------------------------------------------------------------
# full_sync
# ---------------------------------------------------------------------------

class TestFullSync:
    def test_upserts_players_for_all_teams(self, mem_db):
        standings_payload = {
            "standings": [
                {"teamAbbrev": {"default": "EDM"}},
                {"teamAbbrev": {"default": "BOS"}},
            ]
        }
        roster_payload = {
            "forwards":   [{"id": 1, "firstName": {"default": "A"}, "lastName": {"default": "B"}, "positionCode": "C"}],
            "defensemen": [],
            "goalies":    [],
        }
        roster_payload_2 = {
            "forwards":   [{"id": 2, "firstName": {"default": "X"}, "lastName": {"default": "Y"}, "positionCode": "LW"}],
            "defensemen": [],
            "goalies":    [],
        }

        def _side_effect(url, **kwargs):
            m = MagicMock()
            if "standings" in url:
                m.json.return_value = standings_payload
            elif "EDM" in url:
                m.json.return_value = roster_payload
            else:
                m.json.return_value = roster_payload_2
            return m

        with patch("screamsheet.db.nhl_players_sync.requests.get", side_effect=_side_effect):
            count = full_sync(mem_db)

        assert count == 2
        assert lookup_player_by_id(1, mem_db) is not None
        assert lookup_player_by_id(2, mem_db) is not None

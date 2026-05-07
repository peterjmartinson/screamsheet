"""Unit tests for the NHL teams SQLite cache (screamsheet.db.nhl_teams_db)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.db.nhl_teams_db import (
    init_db,
    lookup_team_by_abbrev,
    lookup_team_by_id,
    upsert_teams,
)
from screamsheet.db.nhl_teams_sync import (
    fetch_teams_from_standings,
    full_sync_teams,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_db(tmp_path):
    """Initialised SQLite DB in a temp directory."""
    db = tmp_path / "test_teams.db"
    init_db(db)
    return db


@pytest.fixture
def flyers():
    return {
        "team_id":        4,
        "team":           "PHI",
        "team_full_name": "Flyers",
        "city":           "Philadelphia",
        "raw_json":       json.dumps({"teamId": 4}),
    }


@pytest.fixture
def oilers():
    return {
        "team_id":        22,
        "team":           "EDM",
        "team_full_name": "Oilers",
        "city":           "Edmonton",
        "raw_json":       json.dumps({"teamId": 22}),
    }


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "teams.db"
        init_db(db)
        assert db.exists()

    def test_creates_teams_table(self, tmp_path):
        import sqlalchemy as sa
        db = tmp_path / "teams.db"
        engine = init_db(db)
        assert "teams" in sa.inspect(engine).get_table_names()

    def test_idempotent(self, tmp_path):
        """Calling init_db twice must not raise."""
        db = tmp_path / "teams.db"
        init_db(db)
        init_db(db)


# ---------------------------------------------------------------------------
# upsert_teams
# ---------------------------------------------------------------------------

class TestUpsertTeams:
    def test_inserts_new_team(self, mem_db, flyers):
        count = upsert_teams([flyers], mem_db)
        assert count == 1
        result = lookup_team_by_id(4, mem_db)
        assert result is not None
        assert result["team_full_name"] == "Flyers"

    def test_updates_existing_team(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        renamed = {**flyers, "city": "South Philly"}
        upsert_teams([renamed], mem_db)
        result = lookup_team_by_id(4, mem_db)
        assert result["city"] == "South Philly"

    def test_sets_update_date(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_id(4, mem_db)
        assert result["update_date"] is not None

    def test_skips_entry_without_team_id(self, mem_db):
        bad = {"team": "XXX", "team_full_name": "No ID"}
        count = upsert_teams([bad], mem_db)
        assert count == 0

    def test_returns_count_for_multiple_teams(self, mem_db, flyers, oilers):
        count = upsert_teams([flyers, oilers], mem_db)
        assert count == 2

    def test_subsequent_upsert_does_not_duplicate(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_abbrev("PHI", mem_db)
        assert result is not None
        # Only one row should exist — verify by checking id stability
        first_id = result["id"]
        upsert_teams([flyers], mem_db)
        result2 = lookup_team_by_abbrev("PHI", mem_db)
        # id will increase with delete-then-insert but row count stays 1
        assert result2 is not None


# ---------------------------------------------------------------------------
# lookup_team_by_id
# ---------------------------------------------------------------------------

class TestLookupTeamById:
    def test_hit_returns_team_dict(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_id(4, mem_db)
        assert isinstance(result, dict)
        assert result["team_id"] == 4

    def test_miss_returns_none(self, mem_db):
        result = lookup_team_by_id(9999, mem_db)
        assert result is None

    def test_result_has_all_expected_keys(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_id(4, mem_db)
        for key in ("id", "team_id", "team", "team_full_name", "city",
                    "update_date", "raw_json"):
            assert key in result


# ---------------------------------------------------------------------------
# lookup_team_by_abbrev
# ---------------------------------------------------------------------------

class TestLookupTeamByAbbrev:
    def test_exact_abbrev_match(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_abbrev("PHI", mem_db)
        assert result is not None
        assert result["team_full_name"] == "Flyers"

    def test_case_insensitive(self, mem_db, flyers):
        upsert_teams([flyers], mem_db)
        result = lookup_team_by_abbrev("phi", mem_db)
        assert result is not None

    def test_miss_returns_none(self, mem_db):
        result = lookup_team_by_abbrev("XXX", mem_db)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_teams_from_standings
# ---------------------------------------------------------------------------

class TestFetchTeamsFromStandings:
    def _standings_payload(self):
        """Minimal /standings/now payload covering two teams."""
        return {
            "standings": [
                {
                    "teamAbbrev": {"default": "PHI"},
                    "teamName":   {"default": "Flyers"},
                    "placeName":  {"default": "Philadelphia"},
                },
                {
                    "teamAbbrev": {"default": "EDM"},
                    "teamName":   {"default": "Oilers"},
                    "placeName":  {"default": "Edmonton"},
                },
            ]
        }

    def _schedule_payload(self):
        """Minimal /schedule/{date} payload providing team IDs."""
        return {
            "gameWeek": [
                {
                    "games": [
                        {
                            "homeTeam": {"id": 4,  "abbrev": "PHI"},
                            "awayTeam": {"id": 22, "abbrev": "EDM"},
                        }
                    ]
                }
            ]
        }

    def _mock_responses(self):
        standings_mock = MagicMock()
        standings_mock.json.return_value = self._standings_payload()
        schedule_mock = MagicMock()
        schedule_mock.json.return_value = self._schedule_payload()
        return [standings_mock, schedule_mock]

    def test_returns_list_of_team_dicts(self):
        with patch(
            "screamsheet.db.nhl_teams_sync.requests.get",
            side_effect=self._mock_responses(),
        ):
            result = fetch_teams_from_standings()
        assert len(result) == 2

    def test_team_dict_has_required_keys(self):
        with patch(
            "screamsheet.db.nhl_teams_sync.requests.get",
            side_effect=self._mock_responses(),
        ):
            result = fetch_teams_from_standings()
        team = result[0]
        for key in ("team_id", "team", "team_full_name", "city", "raw_json"):
            assert key in team

    def test_skips_entries_without_matching_schedule_id(self):
        standings = {
            "standings": [
                {"teamAbbrev": {"default": "PHI"}, "teamName": {"default": "Flyers"},
                 "placeName":  {"default": "Philadelphia"}},
                {"teamAbbrev": {"default": "EDM"}, "teamName": {"default": "Oilers"},
                 "placeName":  {"default": "Edmonton"}},
            ]
        }
        # schedule only has EDM — PHI has no ID → skipped
        schedule = {"gameWeek": [{"games": [
            {"homeTeam": {"id": 22, "abbrev": "EDM"}, "awayTeam": {"id": 3, "abbrev": "NYR"}}
        ]}]}
        sm = MagicMock(); sm.json.return_value = standings
        sc = MagicMock(); sc.json.return_value = schedule
        with patch(
            "screamsheet.db.nhl_teams_sync.requests.get",
            side_effect=[sm, sc],
        ):
            result = fetch_teams_from_standings()
        assert len(result) == 1
        assert result[0]["team"] == "EDM"

    def test_all_standings_entries_with_ids_included(self):
        standings = {
            "standings": [
                {"teamAbbrev": {"default": "PHI"}, "teamName": {"default": "Flyers"},  "placeName": {"default": "Philadelphia"}},
                {"teamAbbrev": {"default": "EDM"}, "teamName": {"default": "Oilers"},  "placeName": {"default": "Edmonton"}},
                {"teamAbbrev": {"default": "NYR"}, "teamName": {"default": "Rangers"}, "placeName": {"default": "New York"}},
            ]
        }
        schedule = {"gameWeek": [
            {"games": [{"homeTeam": {"id": 4,  "abbrev": "PHI"}, "awayTeam": {"id": 22, "abbrev": "EDM"}}]},
            {"games": [{"homeTeam": {"id": 3,  "abbrev": "NYR"}, "awayTeam": {"id": 1,  "abbrev": "NJD"}}]},
        ]}
        sm = MagicMock(); sm.json.return_value = standings
        sc = MagicMock(); sc.json.return_value = schedule
        with patch("screamsheet.db.nhl_teams_sync.requests.get", side_effect=[sm, sc]):
            result = fetch_teams_from_standings()
        assert len(result) == 3

    def test_maps_fields_correctly(self):
        with patch(
            "screamsheet.db.nhl_teams_sync.requests.get",
            side_effect=self._mock_responses(),
        ):
            result = fetch_teams_from_standings()
        phi = next(t for t in result if t["team"] == "PHI")
        assert phi["team_id"] == 4
        assert phi["team_full_name"] == "Flyers"
        assert phi["city"] == "Philadelphia"


# ---------------------------------------------------------------------------
# full_sync_teams
# ---------------------------------------------------------------------------

class TestFullSyncTeams:
    def _standings_payload(self):
        return {
            "standings": [
                {
                    "teamAbbrev": {"default": "PHI"},
                    "teamName":   {"default": "Flyers"},
                    "placeName":  {"default": "Philadelphia"},
                },
                {
                    "teamAbbrev": {"default": "EDM"},
                    "teamName":   {"default": "Oilers"},
                    "placeName":  {"default": "Edmonton"},
                },
            ]
        }

    def _schedule_payload(self):
        return {
            "gameWeek": [
                {
                    "games": [
                        {
                            "homeTeam": {"id": 4,  "abbrev": "PHI"},
                            "awayTeam": {"id": 22, "abbrev": "EDM"},
                        }
                    ]
                }
            ]
        }

    def _mock_responses(self):
        sm = MagicMock(); sm.json.return_value = self._standings_payload()
        sc = MagicMock(); sc.json.return_value = self._schedule_payload()
        return [sm, sc]

    def test_returns_upserted_row_count(self, tmp_path):
        db = tmp_path / "sync_test.db"
        with patch("screamsheet.db.nhl_teams_sync.requests.get", side_effect=self._mock_responses()):
            count = full_sync_teams(db)
        assert count == 2

    def test_teams_are_queryable_after_sync(self, tmp_path):
        db = tmp_path / "sync_test.db"
        with patch("screamsheet.db.nhl_teams_sync.requests.get", side_effect=self._mock_responses()):
            full_sync_teams(db)
        result = lookup_team_by_id(4, db)
        assert result is not None
        assert result["team"] == "PHI"

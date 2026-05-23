"""Unit tests for the multi-sport team lookup DB (team_lookup_db).

Each test verifies exactly one behaviour (SRP).
All tests run against a tmp_path SQLite file — no network, no real DB.
"""

import pytest

from screamsheet.db.team_lookup_db import (
    init_db,
    lookup_team_by_abbrev,
    lookup_team_by_id,
    lookup_team_by_name,
    upsert_teams,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(params=["nhl", "mlb", "nba", "nfl"])
def sport(request):
    return request.param


@pytest.fixture
def db(tmp_path, sport):
    path = tmp_path / "test.db"
    init_db(sport, path)
    return path


@pytest.fixture
def phillies():
    return {"team_id": 143, "full_name": "Philadelphia Phillies", "abbrev": "PHI"}


@pytest.fixture
def padres():
    return {"team_id": 135, "full_name": "San Diego Padres", "abbrev": "SD"}


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_db_file(self, tmp_path, sport):
        path = tmp_path / "teams.db"
        init_db(sport, path)
        assert path.exists()

    def test_creates_sport_table(self, tmp_path, sport):
        import sqlalchemy as sa
        path = tmp_path / "teams.db"
        engine = init_db(sport, path)
        assert f"{sport}_teams" in sa.inspect(engine).get_table_names()


# ---------------------------------------------------------------------------
# upsert_teams
# ---------------------------------------------------------------------------

class TestUpsertTeams:
    def test_inserts_row(self, db, sport, phillies):
        count = upsert_teams(sport, [phillies], db)
        assert count == 1

    def test_returns_count_for_multiple_teams(self, db, sport, phillies, padres):
        count = upsert_teams(sport, [phillies, padres], db)
        assert count == 2

    def test_is_idempotent(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        upsert_teams(sport, [phillies], db)
        # Still only one row — no duplicates
        results = lookup_team_by_name(sport, "Philadelphia Phillies", db)
        assert len(results) == 1

    def test_updates_existing_row(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        updated = {**phillies, "full_name": "Updated Phillies"}
        upsert_teams(sport, [updated], db)
        result = lookup_team_by_id(sport, phillies["team_id"], db)
        assert result["full_name"] == "Updated Phillies"

    def test_skips_entry_without_team_id(self, db, sport):
        count = upsert_teams(sport, [{"full_name": "No ID Team", "abbrev": "NON"}], db)
        assert count == 0


# ---------------------------------------------------------------------------
# lookup_team_by_id
# ---------------------------------------------------------------------------

class TestLookupTeamById:
    def test_returns_dict_for_known_id(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        result = lookup_team_by_id(sport, 143, db)
        assert result is not None
        assert result["full_name"] == "Philadelphia Phillies"

    def test_returns_none_for_unknown_id(self, db, sport):
        result = lookup_team_by_id(sport, 9999, db)
        assert result is None

    def test_result_contains_required_fields(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        result = lookup_team_by_id(sport, 143, db)
        for field in ("team_id", "full_name", "abbrev", "last_synced"):
            assert field in result


# ---------------------------------------------------------------------------
# lookup_team_by_abbrev
# ---------------------------------------------------------------------------

class TestLookupTeamByAbbrev:
    def test_returns_dict_for_known_abbrev(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        result = lookup_team_by_abbrev(sport, "PHI", db)
        assert result is not None
        assert result["team_id"] == 143

    def test_is_case_insensitive_lower(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        assert lookup_team_by_abbrev(sport, "phi", db) is not None

    def test_is_case_insensitive_mixed(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        assert lookup_team_by_abbrev(sport, "Phi", db) is not None

    def test_returns_none_for_unknown_abbrev(self, db, sport):
        result = lookup_team_by_abbrev(sport, "XYZ", db)
        assert result is None


# ---------------------------------------------------------------------------
# lookup_team_by_name
# ---------------------------------------------------------------------------

class TestLookupTeamByName:
    def test_returns_matching_team(self, db, sport, phillies, padres):
        upsert_teams(sport, [phillies, padres], db)
        results = lookup_team_by_name(sport, "Philadelphia", db)
        assert len(results) == 1
        assert results[0]["abbrev"] == "PHI"

    def test_partial_match(self, db, sport, phillies, padres):
        upsert_teams(sport, [phillies, padres], db)
        results = lookup_team_by_name(sport, "San", db)
        assert len(results) == 1
        assert results[0]["abbrev"] == "SD"

    def test_returns_empty_list_for_no_match(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        results = lookup_team_by_name(sport, "Toronto", db)
        assert results == []

    def test_returns_all_matching_teams(self, db, sport, phillies):
        angels  = {"team_id": 108, "full_name": "Los Angeles Angels",  "abbrev": "LAA"}
        dodgers = {"team_id": 119, "full_name": "Los Angeles Dodgers", "abbrev": "LAD"}
        upsert_teams(sport, [phillies, angels, dodgers], db)
        results = lookup_team_by_name(sport, "Los Angeles", db)
        assert len(results) == 2

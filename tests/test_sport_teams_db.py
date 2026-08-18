"""Unit tests for the multi-sport team lookup DB (team_lookup_db).

Each test verifies exactly one behaviour (SRP).
All tests run against a tmp_path SQLite file — no network, no real DB.
"""

import pytest

from screamsheet.db.team_lookup_db import (
    get_team_aliases,
    get_team_feed_slug,
    init_db,
    lookup_team_by_abbrev,
    lookup_team_by_alias,
    lookup_team_by_id,
    lookup_team_by_name,
    resolve_team,
    seed_aliases,
    upsert_team_aliases,
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

    def test_creates_team_aliases_table(self, tmp_path, sport):
        import sqlalchemy as sa
        path = tmp_path / "teams.db"
        engine = init_db(sport, path)
        assert "team_aliases" in sa.inspect(engine).get_table_names()


# ---------------------------------------------------------------------------
# upsert_teams
# ---------------------------------------------------------------------------

class TestUpsertTeams:
    def test_returns_upserted_count(self, db, sport, phillies, padres):
        count = upsert_teams(sport, [phillies, padres], db)
        assert count == 2

    def test_is_idempotent(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        count = upsert_teams(sport, [phillies], db)
        assert count == 1
        import sqlalchemy as sa
        engine = init_db(sport, db)
        with engine.connect() as conn:
            rows = conn.execute(sa.text(f"SELECT COUNT(*) FROM {sport}_teams")).scalar()
            assert rows == 1

    def test_skips_entries_without_team_id(self, db, sport):
        count = upsert_teams(sport, [{"full_name": "No ID Team"}], db)
        assert count == 0

    def test_updates_fields_on_conflict(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        updated = {"team_id": 143, "full_name": "Philly Phils", "abbrev": "PHP"}
        upsert_teams(sport, [updated], db)
        result = lookup_team_by_id(sport, 143, db)
        assert result["full_name"] == "Philly Phils"
        assert result["abbrev"] == "PHP"


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


# ---------------------------------------------------------------------------
# team_aliases and resolve_team
# ---------------------------------------------------------------------------

class TestTeamAliases:
    def test_upsert_and_lookup_by_alias(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        aliases = [
            {"team_id": 143, "alias": "Phils", "alias_type": "nickname"},
            {"team_id": 143, "alias": "phillies", "alias_type": "slug"},
        ]
        count = upsert_team_aliases(sport, aliases, db)
        assert count == 2

        res = lookup_team_by_alias(sport, "Phils", db)
        assert res is not None
        assert res["team_id"] == 143
        assert res["full_name"] == "Philadelphia Phillies"

    def test_lookup_by_alias_case_insensitive(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        upsert_team_aliases(sport, [{"team_id": 143, "alias": "Fightin Phils"}], db)
        assert lookup_team_by_alias(sport, "fightin phils", db) is not None

    def test_get_team_aliases(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        upsert_team_aliases(
            sport,
            [
                {"team_id": 143, "alias": "Phils", "alias_type": "nickname"},
                {"team_id": 143, "alias": "phillies", "alias_type": "slug"},
            ],
            db,
        )
        aliases = get_team_aliases(sport, 143, db)
        assert "Philadelphia Phillies" in aliases
        assert "PHI" in aliases
        assert "Phils" in aliases
        assert "phillies" in aliases

    def test_get_team_feed_slug(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        upsert_team_aliases(
            sport,
            [{"team_id": 143, "alias": "phillies", "alias_type": "slug"}],
            db,
        )
        assert get_team_feed_slug(sport, 143, db) == "phillies"

    def test_seed_aliases_seeds_mlb(self, tmp_path):
        db_path = tmp_path / "seed_test.db"
        count = seed_aliases("mlb", db_path)
        assert count > 0

        # Resolving various MLB team names
        brewers = resolve_team("mlb", "Milwaukee Brewers", db_path)
        assert brewers is not None
        assert brewers["full_name"] == "Milwaukee Brewers"

        dbacks = resolve_team("mlb", "D-backs", db_path)
        assert dbacks is not None
        assert dbacks["full_name"] == "Arizona Diamondbacks"

        redsox = resolve_team("mlb", "Red Sox", db_path)
        assert redsox is not None
        assert redsox["full_name"] == "Boston Red Sox"

    def test_resolve_team_handles_ids_abbrevs_and_names(self, db, sport, phillies):
        upsert_teams(sport, [phillies], db)
        upsert_team_aliases(
            sport,
            [{"team_id": 143, "alias": "Phils", "alias_type": "nickname"}],
            db,
        )
        assert resolve_team(sport, 143, db)["team_id"] == 143
        assert resolve_team(sport, "143", db)["team_id"] == 143
        assert resolve_team(sport, "PHI", db)["team_id"] == 143
        assert resolve_team(sport, "Phils", db)["team_id"] == 143
        assert resolve_team(sport, "Philadelphia", db)["team_id"] == 143

    def test_load_aliases_from_csv(self, tmp_path):
        db_path = tmp_path / "csv_test.db"
        csv_file = tmp_path / "custom_aliases.csv"
        csv_file.write_text(
            "sport,team_id,full_name,abbrev,alias,alias_type\n"
            "mlb,143,Philadelphia Phillies,PHI,Fightins,nickname\n"
            "mlb,143,Philadelphia Phillies,PHI,The Broad Street Bullies of Baseball,nickname\n"
            "mlb,158,Milwaukee Brewers,MIL,Brew Crew,nickname\n"
        )
        from screamsheet.db.team_lookup_db import load_aliases_from_csv
        count = load_aliases_from_csv(csv_file, "mlb", db_path)
        assert count == 3

        resolved = resolve_team("mlb", "The Broad Street Bullies of Baseball", db_path)
        assert resolved is not None
        assert resolved["team_id"] == 143
        assert resolved["full_name"] == "Philadelphia Phillies"

        brew = resolve_team("mlb", "Brew Crew", db_path)
        assert brew is not None
        assert brew["team_id"] == 158

    def test_seed_aliases_uses_default_csv(self, tmp_path):
        db_path = tmp_path / "default_csv_test.db"
        count = seed_aliases("mlb", db_path)
        assert count > 0
        phils = resolve_team("mlb", "Fightin' Phils", db_path)
        assert phils is not None
        assert phils["team_id"] == 143

"""SQLite ORM models and lookup helpers for per-sport team and alias tables.

All four sports share an identical table schema:

    <sport>_teams (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id     INTEGER NOT NULL,
        full_name   VARCHAR(150) NOT NULL,
        abbrev      VARCHAR(10),
        last_synced VARCHAR(25)
    )

    team_aliases (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sport       VARCHAR(10) NOT NULL,
        team_id     INTEGER NOT NULL,
        alias       VARCHAR(100) NOT NULL,
        alias_type  VARCHAR(20)
    )

Tables: nhl_teams, mlb_teams, nba_teams, nfl_teams, team_aliases

Public API:
    init_db(sport, db_path)                        Create table if missing → Engine
    upsert_teams(sport, teams, db_path)            Bulk idempotent upsert → count
    upsert_team_aliases(sport, aliases, db_path)   Bulk idempotent alias upsert → count
    load_aliases_from_csv(csv_path, sport, db_path) Load aliases from user-editable CSV → count
    seed_aliases(sport, db_path, csv_path)         Seed team aliases (checks CSV first) → count
    lookup_team_by_id(sport, team_id, db_path)     → dict | None
    lookup_team_by_abbrev(sport, abbrev, db_path)  → dict | None
    lookup_team_by_name(sport, fragment, db_path)  → list[dict]
    lookup_team_by_alias(sport, alias, db_path)    → dict | None
    get_team_aliases(sport, team_id, db_path)      → list[str]
    get_team_feed_slug(sport, team_id, db_path)    → str | None
    resolve_team(sport, query, db_path)            → dict | None
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path
from .team_aliases_data import ALL_SEEDS

logger = logging.getLogger(__name__)

Sport = Literal["nhl", "mlb", "nba", "nfl"]

DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "team_aliases.csv"


# ---------------------------------------------------------------------------
# ORM models — one per sport, identical schema, different __tablename__
# ---------------------------------------------------------------------------

class _NHLTeam(_Base):
    __tablename__ = "nhl_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _MLBTeam(_Base):
    __tablename__ = "mlb_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _NBATeam(_Base):
    __tablename__ = "nba_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _NFLTeam(_Base):
    __tablename__ = "nfl_teams"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    team_id     = Column(Integer, nullable=False, index=True)
    full_name   = Column(String(150), nullable=False)
    abbrev      = Column(String(10), index=True)
    last_synced = Column(String(25))


class _TeamAlias(_Base):
    __tablename__ = "team_aliases"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    sport       = Column(String(10), nullable=False, index=True)
    team_id     = Column(Integer, nullable=False, index=True)
    alias       = Column(String(100), nullable=False, index=True)
    alias_type  = Column(String(20))


_MODELS: dict[str, type] = {
    "nhl": _NHLTeam,
    "mlb": _MLBTeam,
    "nba": _NBATeam,
    "nfl": _NFLTeam,
}


# ---------------------------------------------------------------------------
# Engine / init
# ---------------------------------------------------------------------------

def _get_engine(db_path: Optional[Path] = None):
    """Return a SQLAlchemy engine, creating all sport-team tables if needed."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_db(sport: Optional[Sport] = None, db_path: Optional[Path] = None):
    """Create sport team tables and team_aliases table if they do not exist.

    Args:
        sport:   Optional sport name ("nhl", "mlb", "nba", "nfl").
        db_path: Path to the SQLite file. Defaults to get_db_path().

    Returns:
        SQLAlchemy Engine bound to the database.
    """
    engine = _get_engine(db_path)
    logger.debug("init_db ready at %s", db_path or get_db_path())
    return engine


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_teams(
    sport: Sport,
    teams: List[Dict],
    db_path: Optional[Path] = None,
) -> int:
    """Idempotent bulk upsert of team dicts into the <sport>_teams table.

    Each dict must contain ``team_id`` and ``full_name``.
    Optional: ``abbrev``. ``last_synced`` is always set to the current UTC
    timestamp.

    Args:
        sport:   Target sport table.
        teams:   List of team dicts.
        db_path: Path to the SQLite file. Defaults to get_db_path().

    Returns:
        Number of rows successfully upserted.
    """
    model_cls = _MODELS[sport]
    table = model_cls.__tablename__
    engine = _get_engine(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    with Session(engine) as session:
        for t in teams:
            tid = t.get("team_id")
            if tid is None:
                logger.warning(
                    "upsert_teams(%s): skipping entry without team_id: %s", sport, t
                )
                continue
            session.execute(
                text(f"DELETE FROM {table} WHERE team_id = :tid"), {"tid": tid}
            )
            session.add(model_cls(
                team_id     = tid,
                full_name   = (t.get("full_name") or "")[:150],
                abbrev      = (t.get("abbrev") or "")[:10],
                last_synced = now,
            ))
            count += 1
        session.commit()
    logger.debug("upsert_teams(%s): upserted %d rows", sport, count)
    return count


def upsert_team_aliases(
    sport: Sport,
    aliases: List[Dict[str, Any]],
    db_path: Optional[Path] = None,
) -> int:
    """Bulk upsert of alias records into team_aliases table.

    Each dict must contain ``team_id`` and ``alias``.
    Optional: ``alias_type``.

    Args:
        sport:   Sport identifier ("mlb", "nhl", "nba", "nfl").
        aliases: List of alias dictionaries.
        db_path: Path to the SQLite file.

    Returns:
        Number of alias rows processed/upserted.
    """
    engine = _get_engine(db_path)
    count = 0
    with Session(engine) as session:
        for a in aliases:
            tid = a.get("team_id")
            alias = a.get("alias", "").strip()
            if tid is None or not alias:
                continue
            alias_type = a.get("alias_type")

            # Check if alias already exists for this sport & team
            existing = (
                session.query(_TeamAlias)
                .filter(
                    _TeamAlias.sport == sport,
                    _TeamAlias.team_id == tid,
                    _TeamAlias.alias.ilike(alias),
                )
                .first()
            )
            if not existing:
                session.add(
                    _TeamAlias(
                        sport=sport,
                        team_id=tid,
                        alias=alias[:100],
                        alias_type=alias_type,
                    )
                )
            else:
                if alias_type and existing.alias_type != alias_type:
                    existing.alias_type = alias_type
            count += 1
        session.commit()
    logger.debug("upsert_team_aliases(%s): processed %d rows", sport, count)
    return count


def load_aliases_from_csv(
    csv_path: Optional[Path] = None,
    sport: Optional[Sport] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Load team aliases and base team records from a user-editable CSV file.

    Columns: sport, team_id, full_name, abbrev, alias, alias_type.

    Args:
        csv_path: Path to the CSV file (defaults to src/screamsheet/db/data/team_aliases.csv).
        sport:    Optional sport filter ("mlb", "nhl", "nba", "nfl").
        db_path:  Path to SQLite DB file.

    Returns:
        Number of alias rows loaded/upserted.
    """
    path = csv_path or DEFAULT_CSV_PATH
    if not path.exists():
        logger.warning("Aliases CSV not found at %s", path)
        return 0

    init_db(sport, db_path)

    teams_by_sport: dict[str, dict[int, dict]] = {}
    aliases_by_sport: dict[str, list[dict]] = {}

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s = row.get("sport", "").strip().lower()
            if not s or (sport and s != sport):
                continue
            if s not in _MODELS:
                continue

            try:
                tid = int(row.get("team_id", 0))
            except (ValueError, TypeError):
                continue

            full_name = row.get("full_name", "").strip()
            abbrev = row.get("abbrev", "").strip()
            alias = row.get("alias", "").strip()
            alias_type = row.get("alias_type", "").strip()

            if s not in teams_by_sport:
                teams_by_sport[s] = {}
                aliases_by_sport[s] = []

            if full_name and tid not in teams_by_sport[s]:
                teams_by_sport[s][tid] = {
                    "team_id": tid,
                    "full_name": full_name,
                    "abbrev": abbrev,
                }

            if alias:
                aliases_by_sport[s].append({
                    "team_id": tid,
                    "alias": alias,
                    "alias_type": alias_type or "nickname",
                })

    total_aliases = 0
    for s, teams_dict in teams_by_sport.items():
        if teams_dict:
            upsert_teams(s, list(teams_dict.values()), db_path)
        if s in aliases_by_sport:
            count = upsert_team_aliases(s, aliases_by_sport[s], db_path)
            total_aliases += count

    logger.info("Loaded %d team aliases from %s", total_aliases, path)
    return total_aliases


def seed_aliases(
    sport: Optional[Sport] = None,
    db_path: Optional[Path] = None,
    csv_path: Optional[Path] = None,
) -> int:
    """Seed team aliases and base team records into the local database.

    Always checks the user-editable CSV file first. If present, populates from CSV.
    Falls back to built-in code seeds if CSV is missing.

    Args:
        sport:    Optional sport identifier. If None, seeds all supported sports.
        db_path:  Path to the SQLite file.
        csv_path: Optional custom path to CSV file.

    Returns:
        Total number of alias rows inserted.
    """
    path = csv_path or DEFAULT_CSV_PATH
    if path.exists():
        return load_aliases_from_csv(path, sport, db_path)

    init_db(sport, db_path)
    sports_to_seed = [sport] if sport else list(ALL_SEEDS.keys())
    total_aliases = 0

    for s in sports_to_seed:
        seeds = ALL_SEEDS.get(s, [])
        if not seeds:
            continue

        teams_to_upsert = []
        alias_entries = []

        for item in seeds:
            tid = item["team_id"]
            full_name = item["full_name"]
            abbrev = item["abbrev"]
            slug = item.get("slug", "")
            aliases = item.get("aliases", [])

            teams_to_upsert.append({
                "team_id": tid,
                "full_name": full_name,
                "abbrev": abbrev,
            })

            alias_entries.append({"team_id": tid, "alias": full_name, "alias_type": "name"})
            if abbrev:
                alias_entries.append({"team_id": tid, "alias": abbrev, "alias_type": "abbrev"})
            if slug:
                alias_entries.append({"team_id": tid, "alias": slug, "alias_type": "slug"})
            for alt in aliases:
                alias_entries.append({"team_id": tid, "alias": alt, "alias_type": "nickname"})

        model_cls = _MODELS[s]
        engine = _get_engine(db_path)
        with Session(engine) as session:
            existing_count = session.query(model_cls).count()
            if existing_count == 0:
                upsert_teams(s, teams_to_upsert, db_path)

        inserted = upsert_team_aliases(s, alias_entries, db_path)
        total_aliases += inserted

    return total_aliases


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> Dict:
    return {
        "id":          row.id,
        "team_id":     row.team_id,
        "full_name":   row.full_name,
        "abbrev":      row.abbrev,
        "last_synced": row.last_synced,
    }


def lookup_team_by_id(
    sport: Sport,
    team_id: int,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by its numeric team_id.

    Returns:
        Dict of team fields, or None if not in cache.
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(model_cls).filter(model_cls.team_id == team_id).first()
        return _row_to_dict(row) if row else None


def lookup_team_by_abbrev(
    sport: Sport,
    abbrev: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by abbreviation (case-insensitive).

    Returns:
        Dict of team fields, or None if not in cache.
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        row = session.query(model_cls).filter(
            model_cls.abbrev.ilike(abbrev)
        ).first()
        return _row_to_dict(row) if row else None


def lookup_team_by_name(
    sport: Sport,
    name_fragment: str,
    db_path: Optional[Path] = None,
) -> List[Dict]:
    """Case-insensitive partial match on full_name.

    Returns:
        List of matching team dicts (may be empty).
    """
    model_cls = _MODELS[sport]
    engine = _get_engine(db_path)
    with Session(engine) as session:
        rows = session.query(model_cls).filter(
            model_cls.full_name.ilike(f"%{name_fragment}%")
        ).all()
        return [_row_to_dict(r) for r in rows]


def lookup_team_by_alias(
    sport: Sport,
    alias: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Look up a team by an alias (case-insensitive exact alias match).

    Returns:
        Dict of canonical team fields, or None if not found.
    """
    cleaned = alias.strip()
    if not cleaned:
        return None

    engine = _get_engine(db_path)
    with Session(engine) as session:
        alias_count = session.query(_TeamAlias).filter(_TeamAlias.sport == sport).count()
        if alias_count == 0:
            seed_aliases(sport, db_path)

        alias_row = (
            session.query(_TeamAlias)
            .filter(_TeamAlias.sport == sport, _TeamAlias.alias.ilike(cleaned))
            .first()
        )
        if alias_row:
            return lookup_team_by_id(sport, alias_row.team_id, db_path)
    return None


def get_team_aliases(
    sport: Sport,
    team_id: int,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Retrieve all known alias strings for a team (including name and abbreviation).

    Args:
        sport:   Sport identifier.
        team_id: Numeric team ID.
        db_path: Path to the SQLite file.

    Returns:
        List of unique alias strings.
    """
    engine = _get_engine(db_path)
    aliases: Set[str] = set()

    with Session(engine) as session:
        alias_count = session.query(_TeamAlias).filter(_TeamAlias.sport == sport).count()
        if alias_count == 0:
            seed_aliases(sport, db_path)

        rows = (
            session.query(_TeamAlias)
            .filter(_TeamAlias.sport == sport, _TeamAlias.team_id == team_id)
            .all()
        )
        for r in rows:
            if r.alias:
                aliases.add(r.alias)

    team = lookup_team_by_id(sport, team_id, db_path)
    if team:
        if team.get("full_name"):
            aliases.add(team["full_name"])
        if team.get("abbrev"):
            aliases.add(team["abbrev"])

    return sorted(aliases)


def get_team_feed_slug(
    sport: Sport,
    team_id: int,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Return the feed slug for a team (e.g. 'phillies', 'dbacks', 'redsox')."""
    engine = _get_engine(db_path)
    with Session(engine) as session:
        alias_count = session.query(_TeamAlias).filter(_TeamAlias.sport == sport).count()
        if alias_count == 0:
            seed_aliases(sport, db_path)

        row = (
            session.query(_TeamAlias)
            .filter(
                _TeamAlias.sport == sport,
                _TeamAlias.team_id == team_id,
                _TeamAlias.alias_type == "slug",
            )
            .first()
        )
        if row:
            return row.alias
    return None


def resolve_team(
    sport: Sport,
    query: Any,
    db_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Resolve a team identifier or query string to canonical team data.

    Accepts:
      - Integer or numeric string team ID (e.g. 143, "143")
      - Exact abbreviation (e.g. "PHI")
      - Exact alias or nickname (e.g. "Phillies", "D-backs", "Red Sox", "redsox")
      - Name fragment (e.g. "Philadelphia", "Brewers")

    Returns:
        Dict with canonical team data (id, team_id, full_name, abbrev) or None.
    """
    if query is None:
        return None

    # 1. Numeric ID
    if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
        tid = int(query)
        match = lookup_team_by_id(sport, tid, db_path)
        if match:
            return match

    query_str = str(query).strip()
    if not query_str:
        return None

    # 2. Exact abbreviation match
    match = lookup_team_by_abbrev(sport, query_str, db_path)
    if match:
        return match

    # 3. Team alias match
    match = lookup_team_by_alias(sport, query_str, db_path)
    if match:
        return match

    # 4. Name substring match
    matches = lookup_team_by_name(sport, query_str, db_path)
    if matches:
        return matches[0]

    return None

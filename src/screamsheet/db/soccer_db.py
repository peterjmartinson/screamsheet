"""SQLite ORM models, seed data, and resolution helpers for International Football (Soccer).

Manages four tables in the shared screamsheet SQLite database:
  - soccer_leagues: Competition catalog (ID, name, country, type, current_season, tier_points)
  - soccer_teams:   Club & national team catalog (ID, full_name, abbrev, country, is_national, primary_league_id)
  - soccer_players: Player catalog & cached stats (ID, full_name, first/last, nationality, current_team_id, stats_json)
  - soccer_aliases: Unified alias lookup across ('league', 'team', 'player')

Supports:
  1. Fast deterministic seeding from curated seeds (0 API calls).
  2. Bulk league catalog sync via API-Football `GET /leagues` (1 API call during db_update / deploy).
  3. Ad-hoc read/write cache-on-miss via API-Football search endpoints when a subscriber requests
     an uncached team, player, or league.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from sqlalchemy import Column, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger(__name__)

EntityType = Literal["league", "team", "player"]

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class _SoccerLeague(_Base):
    __tablename__ = "soccer_leagues"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    league_id      = Column(Integer, nullable=False, unique=True, index=True)
    name           = Column(String(150), nullable=False)
    country        = Column(String(100))
    league_type    = Column(String(30))  # "League" or "Cup"
    current_season = Column(Integer)
    tier_points    = Column(Integer, default=50)
    last_synced    = Column(String(25))


class _SoccerTeam(_Base):
    __tablename__ = "soccer_teams"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    team_id           = Column(Integer, nullable=False, unique=True, index=True)
    full_name         = Column(String(150), nullable=False)
    abbrev            = Column(String(15), index=True)
    country           = Column(String(100))
    is_national       = Column(Integer, default=0)  # 1 for national teams, 0 for clubs
    primary_league_id = Column(Integer, nullable=True)
    last_synced       = Column(String(25))


class _SoccerPlayer(_Base):
    __tablename__ = "soccer_players"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    player_id         = Column(Integer, nullable=False, unique=True, index=True)
    full_name         = Column(String(150), nullable=False)
    first_name        = Column(String(100))
    last_name         = Column(String(100), index=True)
    nationality       = Column(String(100))
    current_team_id   = Column(Integer, nullable=True)
    current_team_name = Column(String(150))
    position          = Column(String(30))
    stats_json        = Column(Text)
    last_synced       = Column(String(25))


class _SoccerAlias(_Base):
    __tablename__ = "soccer_aliases"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False, index=True)  # 'league' | 'team' | 'player'
    entity_id   = Column(Integer, nullable=False, index=True)
    alias       = Column(String(150), nullable=False, index=True)
    alias_type  = Column(String(30))


# ---------------------------------------------------------------------------
# Curated Seeds (Leagues, Teams, Players, Aliases)
# ---------------------------------------------------------------------------

SOCCER_LEAGUE_SEEDS: List[Dict[str, Any]] = [
    {
        "league_id": 2,
        "name": "UEFA Champions League",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 100,
        "aliases": ["ucl", "champions league", "uefa champions league", "champions_league", "european cup"],
    },
    {
        "league_id": 39,
        "name": "Premier League",
        "country": "England",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 85,
        "aliases": ["epl", "premier league", "premier_league", "english premier league", "prem", "england premier league"],
    },
    {
        "league_id": 140,
        "name": "La Liga",
        "country": "Spain",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 80,
        "aliases": ["la liga", "la_liga", "laliga", "spanish league", "primera division", "spain la liga"],
    },
    {
        "league_id": 135,
        "name": "Serie A",
        "country": "Italy",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 75,
        "aliases": ["serie a", "serie_a", "italian league", "italy serie a", "calcio"],
    },
    {
        "league_id": 78,
        "name": "Bundesliga",
        "country": "Germany",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 75,
        "aliases": ["bundesliga", "german league", "germany bundesliga"],
    },
    {
        "league_id": 61,
        "name": "Ligue 1",
        "country": "France",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 70,
        "aliases": ["ligue 1", "ligue_1", "french league", "france ligue 1"],
    },
    {
        "league_id": 307,
        "name": "Saudi Pro League",
        "country": "Saudi-Arabia",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 65,
        "aliases": ["spl", "saudi pro league", "saudi_pro_league", "saudi", "saudi league", "roshn saudi league"],
    },
    {
        "league_id": 17,
        "name": "AFC Champions League Elite",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 85,
        "aliases": ["afc champions league", "afc_champions_league", "afc champions league elite", "acl", "asian champions league"],
    },
    {
        "league_id": 308,
        "name": "King's Cup",
        "country": "Saudi-Arabia",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 55,
        "aliases": ["kings cup", "king's cup", "kings_cup", "saudi kings cup"],
    },
    {
        "league_id": 5,
        "name": "UEFA Nations League",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 70,
        "aliases": ["nations league", "uefa nations league", "nations_league"],
    },
    {
        "league_id": 32,
        "name": "World Cup Qualifiers",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 75,
        "aliases": ["wcq", "world cup qualifiers", "world_cup_qualifiers"],
    },
    {
        "league_id": 1,
        "name": "FIFA World Cup",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 100,
        "aliases": ["world cup", "fifa world cup", "world_cup"],
    },
    {
        "league_id": 6,
        "name": "Africa Cup of Nations",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2025,
        "tier_points": 85,
        "aliases": ["afcon", "africa cup of nations", "african cup of nations"],
    },
    {
        "league_id": 12,
        "name": "CAF Champions League",
        "country": "World",
        "league_type": "Cup",
        "current_season": 2026,
        "tier_points": 75,
        "aliases": ["caf champions league", "caf_champions_league", "caf cl", "african champions league"],
    },
    {
        "league_id": 399,
        "name": "NPFL",
        "country": "Nigeria",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 60,
        "aliases": ["npfl", "nigeria premier football league", "nigerian premier league", "nigeria league"],
    },
    {
        "league_id": 203,
        "name": "Süper Lig",
        "country": "Turkey",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 65,
        "aliases": ["super lig", "süper lig", "turkish super lig", "turkey league"],
    },
    {
        "league_id": 253,
        "name": "Major League Soccer",
        "country": "USA",
        "league_type": "League",
        "current_season": 2026,
        "tier_points": 60,
        "aliases": ["mls", "major league soccer"],
    },
]

SOCCER_TEAM_SEEDS: List[Dict[str, Any]] = [
    # Saudi Pro League
    {"team_id": 1005, "full_name": "Al-Nassr", "abbrev": "ALN", "country": "Saudi-Arabia", "is_national": 0, "primary_league_id": 307,
     "aliases": ["al-nassr", "al nassr", "alnassr", "nassr", "al-nassr fc", "al nassr fc"]},
    {"team_id": 1007, "full_name": "Al-Hilal", "abbrev": "HIL", "country": "Saudi-Arabia", "is_national": 0, "primary_league_id": 307,
     "aliases": ["al-hilal", "al hilal", "hilal"]},
    {"team_id": 1003, "full_name": "Al-Ittihad", "abbrev": "ITT", "country": "Saudi-Arabia", "is_national": 0, "primary_league_id": 307,
     "aliases": ["al-ittihad", "al ittihad", "ittihad"]},
    # Premier League
    {"team_id": 42, "full_name": "Arsenal", "abbrev": "ARS", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["arsenal", "arsenal fc", "the gunners", "gunners"]},
    {"team_id": 40, "full_name": "Liverpool", "abbrev": "LIV", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["liverpool", "liverpool fc", "the reds"]},
    {"team_id": 50, "full_name": "Manchester City", "abbrev": "MCI", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["manchester city", "man city", "mancity", "city"]},
    {"team_id": 33, "full_name": "Manchester United", "abbrev": "MUN", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["manchester united", "man united", "man utd", "united", "red devils"]},
    {"team_id": 49, "full_name": "Chelsea", "abbrev": "CHE", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["chelsea", "chelsea fc", "the blues"]},
    {"team_id": 47, "full_name": "Tottenham", "abbrev": "TOT", "country": "England", "is_national": 0, "primary_league_id": 39,
     "aliases": ["tottenham", "tottenham hotspur", "spurs"]},
    # La Liga
    {"team_id": 541, "full_name": "Real Madrid", "abbrev": "RMA", "country": "Spain", "is_national": 0, "primary_league_id": 140,
     "aliases": ["real madrid", "madrid", "los blancos"]},
    {"team_id": 529, "full_name": "Barcelona", "abbrev": "BAR", "country": "Spain", "is_national": 0, "primary_league_id": 140,
     "aliases": ["barcelona", "fc barcelona", "barca", "barça"]},
    {"team_id": 530, "full_name": "Atletico Madrid", "abbrev": "ATM", "country": "Spain", "is_national": 0, "primary_league_id": 140,
     "aliases": ["atletico madrid", "atletico", "atleti"]},
    # Serie A / Bundesliga / Ligue 1 / Turkey
    {"team_id": 157, "full_name": "Bayern Munich", "abbrev": "BAY", "country": "Germany", "is_national": 0, "primary_league_id": 78,
     "aliases": ["bayern munich", "bayern", "fc bayern"]},
    {"team_id": 165, "full_name": "Borussia Dortmund", "abbrev": "BVB", "country": "Germany", "is_national": 0, "primary_league_id": 78,
     "aliases": ["borussia dortmund", "dortmund", "bvb"]},
    {"team_id": 85, "full_name": "Paris Saint-Germain", "abbrev": "PSG", "country": "France", "is_national": 0, "primary_league_id": 61,
     "aliases": ["paris saint-germain", "psg", "paris sg"]},
    {"team_id": 505, "full_name": "Inter Milan", "abbrev": "INT", "country": "Italy", "is_national": 0, "primary_league_id": 135,
     "aliases": ["inter milan", "inter", "internazionale"]},
    {"team_id": 489, "full_name": "AC Milan", "abbrev": "MIL", "country": "Italy", "is_national": 0, "primary_league_id": 135,
     "aliases": ["ac milan", "milan"]},
    {"team_id": 496, "full_name": "Juventus", "abbrev": "JUV", "country": "Italy", "is_national": 0, "primary_league_id": 135,
     "aliases": ["juventus", "juve"]},
    {"team_id": 492, "full_name": "Napoli", "abbrev": "NAP", "country": "Italy", "is_national": 0, "primary_league_id": 135,
     "aliases": ["napoli", "ssc napoli"]},
    {"team_id": 499, "full_name": "Atalanta", "abbrev": "ATA", "country": "Italy", "is_national": 0, "primary_league_id": 135,
     "aliases": ["atalanta", "atalanta bc"]},
    {"team_id": 645, "full_name": "Galatasaray", "abbrev": "GAL", "country": "Turkey", "is_national": 0, "primary_league_id": 203,
     "aliases": ["galatasaray", "gala"]},
    # Nigerian Premier Football League (NPFL)
    {"team_id": 5203, "full_name": "Enyimba", "abbrev": "ENY", "country": "Nigeria", "is_national": 0, "primary_league_id": 399,
     "aliases": ["enyimba", "enyimba fc", "enyimba international", "peoples elephant"]},
    {"team_id": 5205, "full_name": "Kano Pillars", "abbrev": "KAN", "country": "Nigeria", "is_national": 0, "primary_league_id": 399,
     "aliases": ["kano pillars", "pillars", "sai masu gida"]},
    {"team_id": 5209, "full_name": "Rangers International", "abbrev": "RAN", "country": "Nigeria", "is_national": 0, "primary_league_id": 399,
     "aliases": ["enugu rangers", "rangers international", "flying antelopes"]},
    {"team_id": 5212, "full_name": "Shooting Stars", "abbrev": "3SC", "country": "Nigeria", "is_national": 0, "primary_league_id": 399,
     "aliases": ["shooting stars", "3sc", "ibadan"]},
    # National Teams
    {"team_id": 27, "full_name": "Portugal", "abbrev": "POR", "country": "Portugal", "is_national": 1, "primary_league_id": 5,
     "aliases": ["portugal", "portugal national team", "selecao das quinas"]},
    {"team_id": 19, "full_name": "Nigeria", "abbrev": "NGA", "country": "Nigeria", "is_national": 1, "primary_league_id": 6,
     "aliases": ["nigeria", "super eagles", "nigeria national team"]},
    {"team_id": 26, "full_name": "Argentina", "abbrev": "ARG", "country": "Argentina", "is_national": 1, "primary_league_id": 1,
     "aliases": ["argentina", "albiceleste", "argentina national team"]},
    {"team_id": 6, "full_name": "Brazil", "abbrev": "BRA", "country": "Brazil", "is_national": 1, "primary_league_id": 1,
     "aliases": ["brazil", "selecao", "brazil national team"]},
    {"team_id": 2, "full_name": "France", "abbrev": "FRA", "country": "France", "is_national": 1, "primary_league_id": 5,
     "aliases": ["france", "les bleus", "france national team"]},
    {"team_id": 10, "full_name": "England", "abbrev": "ENG", "country": "England", "is_national": 1, "primary_league_id": 5,
     "aliases": ["england", "three lions", "england national team"]},
    {"team_id": 9, "full_name": "Spain", "abbrev": "ESP", "country": "Spain", "is_national": 1, "primary_league_id": 5,
     "aliases": ["spain", "la roja", "spain national team"]},
    {"team_id": 25, "full_name": "Germany", "abbrev": "GER", "country": "Germany", "is_national": 1, "primary_league_id": 5,
     "aliases": ["germany", "die mannschaft", "germany national team"]},
    {"team_id": 2384, "full_name": "USA", "abbrev": "USA", "country": "USA", "is_national": 1, "primary_league_id": 32,
     "aliases": ["usa", "usmnt", "united states"]},
]

SOCCER_PLAYER_SEEDS: List[Dict[str, Any]] = [
    {
        "player_id": 874,
        "full_name": "Cristiano Ronaldo",
        "first_name": "Cristiano",
        "last_name": "Ronaldo",
        "nationality": "Portugal",
        "current_team_id": 1005,
        "current_team_name": "Al-Nassr",
        "position": "Attacker",
        "aliases": ["cristiano ronaldo", "ronaldo", "cr7", "cristiano"],
        "stats_json": json.dumps({
            "headline_title": "CRISTIANO RONALDO: THE ROAD TO 1,000 GOALS",
            "career_total": 916,
            "milestone_target": 1000,
            "rows": [
                ["Real Madrid", "438", "450", "4x Champions League, 2x La Liga"],
                ["Manchester United", "346", "145", "1x Champions League, 3x Premier League"],
                ["Portugal National Team", "214", "133", "Euro 2016, Nations League 2019"],
                ["Juventus", "134", "101", "2x Serie A"],
                ["Al-Nassr FC (Current)", "85", "74", "Arab Club Champions Cup"],
                ["Sporting CP", "31", "5", "Supertaça"],
                ["CAREER TOTAL", "1,248", "916", "84 Goals Remaining to 1,000!"],
            ],
        }),
    },
    {
        "player_id": 2393,
        "full_name": "Victor Osimhen",
        "first_name": "Victor",
        "last_name": "Osimhen",
        "nationality": "Nigeria",
        "current_team_id": 645,
        "current_team_name": "Galatasaray",
        "position": "Attacker",
        "aliases": ["victor osimhen", "osimhen"],
        "stats_json": json.dumps({
            "headline_title": "VICTOR OSIMHEN: CAREER & SEASON TRACKER",
            "career_total": 149,
            "rows": [
                ["Napoli", "133", "76", "Serie A Champion (2022–23), Capocannoniere"],
                ["Nigeria Super Eagles", "37", "23", "AFCON Silver Medalist, CAF Player of the Year"],
                ["Lille OSC", "38", "18", "Prix Marc-Vivien Foé"],
                ["Sporting Charleroi", "36", "20", "Belgian Pro League Breakout"],
                ["Galatasaray (Current)", "28", "20", "Süper Lig Leading Striker"],
                ["CAREER TOTAL", "272", "157", "African Footballer of the Year"],
            ],
        }),
    },
    {
        "player_id": 18766,
        "full_name": "Ademola Lookman",
        "first_name": "Ademola",
        "last_name": "Lookman",
        "nationality": "Nigeria",
        "current_team_id": 499,
        "current_team_name": "Atalanta",
        "position": "Attacker",
        "aliases": ["ademola lookman", "lookman"],
        "stats_json": json.dumps({
            "headline_title": "ADEMOLA LOOKMAN: CAREER & SEASON TRACKER",
            "career_total": 88,
            "rows": [
                ["Atalanta (Current)", "95", "45", "UEFA Europa League Winner (Final Hat-Trick)"],
                ["Nigeria Super Eagles", "27", "8", "AFCON Finalist, CAF Player of the Year"],
                ["RB Leipzig / Leicester / Fulham", "98", "23", "Bundesliga & Premier League"],
                ["Everton / Charlton", "96", "15", "U-20 World Cup Winner"],
                ["CAREER TOTAL", "316", "91", "2024 African Footballer of the Year"],
            ],
        }),
    },
    {
        "player_id": 1460,
        "full_name": "Bukayo Saka",
        "first_name": "Bukayo",
        "last_name": "Saka",
        "nationality": "England",
        "current_team_id": 42,
        "current_team_name": "Arsenal",
        "position": "Attacker",
        "aliases": ["bukayo saka", "saka", "starboy"],
        "stats_json": json.dumps({
            "headline_title": "BUKAYO SAKA: CAREER & SEASON TRACKER",
            "career_total": 78,
            "rows": [
                ["Arsenal FC (Current)", "240", "66", "FA Cup Winner, 2x Arsenal Player of the Season"],
                ["England National Team", "43", "12", "2x England Men's Player of the Year"],
                ["CAREER TOTAL", "283", "78", "Premier League Young Superstar"],
            ],
        }),
    },
    {
        "player_id": 154,
        "full_name": "Lionel Messi",
        "first_name": "Lionel",
        "last_name": "Messi",
        "nationality": "Argentina",
        "current_team_id": 9568,
        "current_team_name": "Inter Miami",
        "position": "Attacker",
        "aliases": ["lionel messi", "messi", "leo messi"],
        "stats_json": json.dumps({
            "headline_title": "LIONEL MESSI: CAREER TRACKER",
            "career_total": 850,
            "rows": [
                ["FC Barcelona", "778", "672", "4x Champions League, 10x La Liga, 8x Ballon d'Or"],
                ["Argentina National Team", "191", "112", "2022 World Cup Champion, 2x Copa América"],
                ["Paris Saint-Germain", "75", "32", "2x Ligue 1 Champion"],
                ["Inter Miami CF (Current)", "39", "34", "Supporters' Shield, Leagues Cup"],
                ["CAREER TOTAL", "1,083", "850", "All-Time Most Decorated Footballer"],
            ],
        }),
    },
    {
        "player_id": 306,
        "full_name": "Mohamed Salah",
        "first_name": "Mohamed",
        "last_name": "Salah",
        "nationality": "Egypt",
        "current_team_id": 40,
        "current_team_name": "Liverpool",
        "position": "Attacker",
        "aliases": ["mohamed salah", "mo salah", "salah"],
        "stats_json": None,
    },
    {
        "player_id": 278,
        "full_name": "Kylian Mbappé",
        "first_name": "Kylian",
        "last_name": "Mbappé",
        "nationality": "France",
        "current_team_id": 541,
        "current_team_name": "Real Madrid",
        "position": "Attacker",
        "aliases": ["kylian mbappe", "kylian mbappé", "mbappe", "mbappé"],
        "stats_json": None,
    },
    {
        "player_id": 1100,
        "full_name": "Erling Haaland",
        "first_name": "Erling",
        "last_name": "Haaland",
        "nationality": "Norway",
        "current_team_id": 50,
        "current_team_name": "Manchester City",
        "position": "Attacker",
        "aliases": ["erling haaland", "haaland"],
        "stats_json": None,
    },
]


# ---------------------------------------------------------------------------
# Engine / Initialization
# ---------------------------------------------------------------------------


def init_soccer_db(db_path: Optional[Path] = None):
    """Create the soccer tables if they do not exist."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_api_key() -> str:
    return (
        os.environ.get("APISPORTS_KEY")
        or os.environ.get("FOOTBALL_API_KEY")
        or os.environ.get("FIFA_API_KEY")
        or ""
    )


# ---------------------------------------------------------------------------
# Upsert & Seeding Functions
# ---------------------------------------------------------------------------


def upsert_soccer_leagues(leagues: List[Dict[str, Any]], db_path: Optional[Path] = None) -> int:
    engine = init_soccer_db(db_path)
    now = _now_iso()
    count = 0
    with Session(engine) as session:
        for item in leagues:
            lid = int(item["league_id"])
            existing = session.query(_SoccerLeague).filter_by(league_id=lid).first()
            if existing:
                existing.name = str(item["name"])
                existing.country = str(item.get("country") or existing.country or "")
                existing.league_type = str(item.get("league_type") or existing.league_type or "League")
                existing.current_season = int(item.get("current_season") or existing.current_season or 2026)
                if "tier_points" in item and item["tier_points"] is not None:
                    existing.tier_points = int(item["tier_points"])
                existing.last_synced = now
            else:
                session.add(
                    _SoccerLeague(
                        league_id=lid,
                        name=str(item["name"]),
                        country=str(item.get("country") or ""),
                        league_type=str(item.get("league_type") or "League"),
                        current_season=int(item.get("current_season") or 2026),
                        tier_points=int(item.get("tier_points") or 50),
                        last_synced=now,
                    )
                )
            count += 1
        session.commit()
    return count


def upsert_soccer_teams(teams: List[Dict[str, Any]], db_path: Optional[Path] = None) -> int:
    engine = init_soccer_db(db_path)
    now = _now_iso()
    count = 0
    with Session(engine) as session:
        for item in teams:
            tid = int(item["team_id"])
            existing = session.query(_SoccerTeam).filter_by(team_id=tid).first()
            if existing:
                existing.full_name = str(item["full_name"])
                existing.abbrev = str(item.get("abbrev") or existing.abbrev or "")
                existing.country = str(item.get("country") or existing.country or "")
                existing.is_national = int(bool(item.get("is_national", existing.is_national)))
                if item.get("primary_league_id") is not None:
                    existing.primary_league_id = int(item["primary_league_id"])
                existing.last_synced = now
            else:
                session.add(
                    _SoccerTeam(
                        team_id=tid,
                        full_name=str(item["full_name"]),
                        abbrev=str(item.get("abbrev") or ""),
                        country=str(item.get("country") or ""),
                        is_national=int(bool(item.get("is_national", False))),
                        primary_league_id=int(item["primary_league_id"]) if item.get("primary_league_id") is not None else None,
                        last_synced=now,
                    )
                )
            count += 1
        session.commit()
    return count


def upsert_soccer_players(players: List[Dict[str, Any]], db_path: Optional[Path] = None) -> int:
    engine = init_soccer_db(db_path)
    now = _now_iso()
    count = 0
    with Session(engine) as session:
        for item in players:
            pid = int(item["player_id"])
            existing = session.query(_SoccerPlayer).filter_by(player_id=pid).first()
            if existing:
                existing.full_name = str(item["full_name"])
                existing.first_name = str(item.get("first_name") or existing.first_name or "")
                existing.last_name = str(item.get("last_name") or existing.last_name or "")
                existing.nationality = str(item.get("nationality") or existing.nationality or "")
                if item.get("current_team_id") is not None:
                    existing.current_team_id = int(item["current_team_id"])
                if item.get("current_team_name"):
                    existing.current_team_name = str(item["current_team_name"])
                if item.get("position"):
                    existing.position = str(item["position"])
                if item.get("stats_json"):
                    existing.stats_json = str(item["stats_json"])
                existing.last_synced = now
            else:
                session.add(
                    _SoccerPlayer(
                        player_id=pid,
                        full_name=str(item["full_name"]),
                        first_name=str(item.get("first_name") or ""),
                        last_name=str(item.get("last_name") or ""),
                        nationality=str(item.get("nationality") or ""),
                        current_team_id=int(item["current_team_id"]) if item.get("current_team_id") is not None else None,
                        current_team_name=str(item.get("current_team_name") or ""),
                        position=str(item.get("position") or "Attacker"),
                        stats_json=str(item["stats_json"]) if item.get("stats_json") else None,
                        last_synced=now,
                    )
                )
            count += 1
        session.commit()
    return count


def upsert_soccer_aliases(aliases: List[Dict[str, Any]], db_path: Optional[Path] = None) -> int:
    engine = init_soccer_db(db_path)
    count = 0
    with Session(engine) as session:
        for item in aliases:
            etype = str(item["entity_type"]).lower().strip()
            eid = int(item["entity_id"])
            alias_str = str(item["alias"]).strip().lower()
            if not alias_str:
                continue
            existing = (
                session.query(_SoccerAlias)
                .filter(
                    _SoccerAlias.entity_type == etype,
                    text("LOWER(alias) = :alias"),
                )
                .params(alias=alias_str)
                .first()
            )
            if existing:
                existing.entity_id = eid
                existing.alias_type = str(item.get("alias_type") or existing.alias_type or "alias")
            else:
                session.add(
                    _SoccerAlias(
                        entity_type=etype,
                        entity_id=eid,
                        alias=alias_str,
                        alias_type=str(item.get("alias_type") or "alias"),
                    )
                )
            count += 1
        session.commit()
    return count


def seed_soccer_db(db_path: Optional[Path] = None) -> int:
    """Seed soccer leagues, teams, players, and aliases into SQLite."""
    total = 0
    total += upsert_soccer_leagues(SOCCER_LEAGUE_SEEDS, db_path=db_path)
    total += upsert_soccer_teams(SOCCER_TEAM_SEEDS, db_path=db_path)
    total += upsert_soccer_players(SOCCER_PLAYER_SEEDS, db_path=db_path)

    alias_rows: List[Dict[str, Any]] = []
    for l_seed in SOCCER_LEAGUE_SEEDS:
        lid = l_seed["league_id"]
        alias_rows.append({"entity_type": "league", "entity_id": lid, "alias": l_seed["name"].lower(), "alias_type": "canonical"})
        for a in l_seed.get("aliases", []):
            alias_rows.append({"entity_type": "league", "entity_id": lid, "alias": a, "alias_type": "nickname"})

    for t_seed in SOCCER_TEAM_SEEDS:
        tid = t_seed["team_id"]
        alias_rows.append({"entity_type": "team", "entity_id": tid, "alias": t_seed["full_name"].lower(), "alias_type": "canonical"})
        if t_seed.get("abbrev"):
            alias_rows.append({"entity_type": "team", "entity_id": tid, "alias": t_seed["abbrev"].lower(), "alias_type": "abbrev"})
        for a in t_seed.get("aliases", []):
            alias_rows.append({"entity_type": "team", "entity_id": tid, "alias": a, "alias_type": "nickname"})

    for p_seed in SOCCER_PLAYER_SEEDS:
        pid = p_seed["player_id"]
        alias_rows.append({"entity_type": "player", "entity_id": pid, "alias": p_seed["full_name"].lower(), "alias_type": "canonical"})
        if p_seed.get("last_name"):
            alias_rows.append({"entity_type": "player", "entity_id": pid, "alias": p_seed["last_name"].lower(), "alias_type": "lastname"})
        for a in p_seed.get("aliases", []):
            alias_rows.append({"entity_type": "player", "entity_id": pid, "alias": a, "alias_type": "nickname"})

    total += upsert_soccer_aliases(alias_rows, db_path=db_path)
    return total


def sync_soccer_leagues_from_api(db_path: Optional[Path] = None, api_key: Optional[str] = None) -> int:
    """Sync all active international leagues from API-Football (1 HTTP request) if key is available."""
    # Always ensure curated seeds are present first
    seeded = seed_soccer_db(db_path=db_path)
    key = api_key or _get_api_key()
    if not key:
        return seeded

    try:
        resp = requests.get(
            f"{API_FOOTBALL_BASE_URL}/leagues",
            params={"current": "true"},
            headers={"x-apisports-key": key},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json().get("response", [])
        if not payload:
            return seeded

        leagues_to_upsert: List[Dict[str, Any]] = []
        for entry in payload:
            lg = entry.get("league", {})
            country = entry.get("country", {})
            seasons = entry.get("seasons", [])
            curr_season = next((s.get("year") for s in seasons if s.get("current")), 2026)
            lid = lg.get("id")
            name = lg.get("name")
            if not lid or not name:
                continue
            leagues_to_upsert.append({
                "league_id": int(lid),
                "name": str(name),
                "country": str(country.get("name") or ""),
                "league_type": str(lg.get("type") or "League"),
                "current_season": int(curr_season or 2026),
            })

        return upsert_soccer_leagues(leagues_to_upsert, db_path=db_path)
    except Exception as exc:
        logger.warning("API-Football league sync skipped/failed (using seeded catalog): %s", exc)
        return seeded


# ---------------------------------------------------------------------------
# Resolution Helpers (Local DB + Ad-Hoc Cache-on-Miss API Fallback)
# ---------------------------------------------------------------------------


def _ensure_seeded(session: Session, db_path: Optional[Path]) -> None:
    count = session.query(_SoccerTeam).count()
    if count == 0:
        seed_soccer_db(db_path=db_path)


def _league_to_dict(row: _SoccerLeague) -> Dict[str, Any]:
    return {
        "league_id": row.league_id,
        "name": row.name,
        "country": row.country,
        "league_type": row.league_type,
        "current_season": row.current_season,
        "tier_points": row.tier_points,
    }


def _team_to_dict(row: _SoccerTeam) -> Dict[str, Any]:
    return {
        "team_id": row.team_id,
        "full_name": row.full_name,
        "abbrev": row.abbrev,
        "country": row.country,
        "is_national": bool(row.is_national),
        "primary_league_id": row.primary_league_id,
    }


def _player_to_dict(row: _SoccerPlayer) -> Dict[str, Any]:
    return {
        "player_id": row.player_id,
        "full_name": row.full_name,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "nationality": row.nationality,
        "current_team_id": row.current_team_id,
        "current_team_name": row.current_team_name,
        "position": row.position,
        "stats_json": row.stats_json,
    }


def resolve_soccer_league(
    query: str | int,
    db_path: Optional[Path] = None,
    allow_api_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """Resolve a league ID, name, or alias (e.g. 'Premier League', 'NPFL', 'AFCON', 39)."""
    engine = init_soccer_db(db_path)
    with Session(engine) as session:
        _ensure_seeded(session, db_path)

        # 1. Numeric ID
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            lid = int(str(query).strip())
            row = session.query(_SoccerLeague).filter_by(league_id=lid).first()
            if row:
                return _league_to_dict(row)

        q = str(query).strip().lower()
        if not q:
            return None

        # 2. Alias table exact match
        alias_hit = (
            session.query(_SoccerAlias)
            .filter(_SoccerAlias.entity_type == "league", text("LOWER(alias) = :q"))
            .params(q=q)
            .first()
        )
        if alias_hit:
            row = session.query(_SoccerLeague).filter_by(league_id=alias_hit.entity_id).first()
            if row:
                return _league_to_dict(row)

        # 3. Direct name match
        row = (
            session.query(_SoccerLeague)
            .filter(text("LOWER(name) = :q"))
            .params(q=q)
            .first()
        )
        if row:
            return _league_to_dict(row)

        # 4. Substring match
        row = (
            session.query(_SoccerLeague)
            .filter(_SoccerLeague.name.ilike(f"%{q}%"))
            .order_by(_SoccerLeague.tier_points.desc())
            .first()
        )
        if row:
            return _league_to_dict(row)

    # 5. Ad-hoc API search fallback on cache miss
    if allow_api_fallback and len(str(query).strip()) >= 3:
        key = _get_api_key()
        if key:
            try:
                resp = requests.get(
                    f"{API_FOOTBALL_BASE_URL}/leagues",
                    params={"search": str(query).strip()},
                    headers={"x-apisports-key": key},
                    timeout=10,
                )
                resp.raise_for_status()
                items = resp.json().get("response", [])
                if items:
                    first = items[0]
                    lg = first.get("league", {})
                    country = first.get("country", {})
                    seasons = first.get("seasons", [])
                    curr_season = next((s.get("year") for s in seasons if s.get("current")), 2026)
                    new_league = {
                        "league_id": int(lg["id"]),
                        "name": str(lg["name"]),
                        "country": str(country.get("name") or ""),
                        "league_type": str(lg.get("type") or "League"),
                        "current_season": int(curr_season or 2026),
                        "tier_points": 55,
                    }
                    upsert_soccer_leagues([new_league], db_path=db_path)
                    upsert_soccer_aliases(
                        [{"entity_type": "league", "entity_id": new_league["league_id"], "alias": q, "alias_type": "search"}],
                        db_path=db_path,
                    )
                    return new_league
            except Exception as exc:
                logger.warning("Ad-hoc league search failed for %r: %s", query, exc)

    return None


def resolve_soccer_team(
    query: str | int,
    db_path: Optional[Path] = None,
    allow_api_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """Resolve a club or national team by ID, name, abbreviation, or alias (e.g. 'Arsenal', 'Enyimba', 'Super Eagles')."""
    engine = init_soccer_db(db_path)
    with Session(engine) as session:
        _ensure_seeded(session, db_path)

        # 1. Numeric ID
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            tid = int(str(query).strip())
            row = session.query(_SoccerTeam).filter_by(team_id=tid).first()
            if row:
                return _team_to_dict(row)

        q = str(query).strip().lower()
        if not q:
            return None

        # 2. Alias table exact match
        alias_hit = (
            session.query(_SoccerAlias)
            .filter(_SoccerAlias.entity_type == "team", text("LOWER(alias) = :q"))
            .params(q=q)
            .first()
        )
        if alias_hit:
            row = session.query(_SoccerTeam).filter_by(team_id=alias_hit.entity_id).first()
            if row:
                return _team_to_dict(row)

        # 3. Direct name or abbrev match
        row = (
            session.query(_SoccerTeam)
            .filter(text("LOWER(full_name) = :q OR LOWER(abbrev) = :q"))
            .params(q=q)
            .first()
        )
        if row:
            return _team_to_dict(row)

        # 4. Substring match
        row = (
            session.query(_SoccerTeam)
            .filter(_SoccerTeam.full_name.ilike(f"%{q}%"))
            .first()
        )
        if row:
            return _team_to_dict(row)

    # 5. Ad-hoc API search fallback on cache miss
    if allow_api_fallback and len(str(query).strip()) >= 3:
        key = _get_api_key()
        if key:
            try:
                resp = requests.get(
                    f"{API_FOOTBALL_BASE_URL}/teams",
                    params={"search": str(query).strip()},
                    headers={"x-apisports-key": key},
                    timeout=10,
                )
                resp.raise_for_status()
                items = resp.json().get("response", [])
                if items:
                    tm = items[0].get("team", {})
                    new_team = {
                        "team_id": int(tm["id"]),
                        "full_name": str(tm["name"]),
                        "abbrev": str(tm.get("code") or tm["name"][:3].upper()),
                        "country": str(tm.get("country") or ""),
                        "is_national": bool(tm.get("national", False)),
                        "primary_league_id": None,
                    }
                    upsert_soccer_teams([new_team], db_path=db_path)
                    upsert_soccer_aliases(
                        [{"entity_type": "team", "entity_id": new_team["team_id"], "alias": q, "alias_type": "search"}],
                        db_path=db_path,
                    )
                    return new_team
            except Exception as exc:
                logger.warning("Ad-hoc team search failed for %r: %s", query, exc)

    return None


def resolve_soccer_player(
    query: str | int,
    db_path: Optional[Path] = None,
    allow_api_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """Resolve a football player by ID, name, or nickname (e.g. 'Victor Osimhen', 'CR7', 'Saka')."""
    engine = init_soccer_db(db_path)
    with Session(engine) as session:
        _ensure_seeded(session, db_path)

        # 1. Numeric ID
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            pid = int(str(query).strip())
            row = session.query(_SoccerPlayer).filter_by(player_id=pid).first()
            if row:
                return _player_to_dict(row)

        q = str(query).strip().lower()
        if not q:
            return None

        # 2. Alias table exact match
        alias_hit = (
            session.query(_SoccerAlias)
            .filter(_SoccerAlias.entity_type == "player", text("LOWER(alias) = :q"))
            .params(q=q)
            .first()
        )
        if alias_hit:
            row = session.query(_SoccerPlayer).filter_by(player_id=alias_hit.entity_id).first()
            if row:
                return _player_to_dict(row)

        # 3. Direct full_name or last_name match
        row = (
            session.query(_SoccerPlayer)
            .filter(text("LOWER(full_name) = :q OR LOWER(last_name) = :q"))
            .params(q=q)
            .first()
        )
        if row:
            return _player_to_dict(row)

        # 4. Substring match
        row = (
            session.query(_SoccerPlayer)
            .filter(_SoccerPlayer.full_name.ilike(f"%{q}%"))
            .first()
        )
        if row:
            return _player_to_dict(row)

    # 5. Ad-hoc API search fallback on cache miss
    if allow_api_fallback and len(str(query).strip()) >= 3:
        key = _get_api_key()
        if key:
            try:
                resp = requests.get(
                    f"{API_FOOTBALL_BASE_URL}/players/profiles",
                    params={"search": str(query).strip()},
                    headers={"x-apisports-key": key},
                    timeout=10,
                )
                resp.raise_for_status()
                items = resp.json().get("response", [])
                if items:
                    pl = items[0].get("player", {})
                    new_player = {
                        "player_id": int(pl["id"]),
                        "full_name": f"{pl.get('firstname', '')} {pl.get('lastname', '')}".strip() or str(pl.get("name", query)),
                        "first_name": str(pl.get("firstname") or ""),
                        "last_name": str(pl.get("lastname") or ""),
                        "nationality": str(pl.get("nationality") or ""),
                        "current_team_id": None,
                        "current_team_name": "",
                        "position": str(pl.get("position") or "Attacker"),
                        "stats_json": None,
                    }
                    upsert_soccer_players([new_player], db_path=db_path)
                    upsert_soccer_aliases(
                        [{"entity_type": "player", "entity_id": new_player["player_id"], "alias": q, "alias_type": "search"}],
                        db_path=db_path,
                    )
                    return new_player
            except Exception as exc:
                logger.warning("Ad-hoc player search failed for %r: %s", query, exc)

    return None

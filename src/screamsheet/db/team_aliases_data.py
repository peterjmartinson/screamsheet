"""Built-in seed data for team aliases, abbreviations, nicknames, and feed slugs."""
from __future__ import annotations

from typing import Dict, List, TypedDict


class TeamAliasSeed(TypedDict):
    team_id: int
    full_name: str
    abbrev: str
    slug: str
    aliases: List[str]


MLB_TEAM_SEEDS: List[TeamAliasSeed] = [
    {
        "team_id": 108,
        "full_name": "Los Angeles Angels",
        "abbrev": "LAA",
        "slug": "angels",
        "aliases": ["Angels", "Los Angeles Angels", "LA Angels", "LAA", "Halos", "angels"],
    },
    {
        "team_id": 109,
        "full_name": "Arizona Diamondbacks",
        "abbrev": "ARI",
        "slug": "dbacks",
        "aliases": ["Diamondbacks", "D-backs", "Dbacks", "Arizona", "ARI", "Arizona Diamondbacks", "dbacks"],
    },
    {
        "team_id": 110,
        "full_name": "Baltimore Orioles",
        "abbrev": "BAL",
        "slug": "orioles",
        "aliases": ["Orioles", "O's", "Baltimore", "BAL", "Baltimore Orioles", "orioles"],
    },
    {
        "team_id": 111,
        "full_name": "Boston Red Sox",
        "abbrev": "BOS",
        "slug": "redsox",
        "aliases": ["Red Sox", "RedSox", "red-sox", "Boston", "BOS", "Boston Red Sox", "redsox"],
    },
    {
        "team_id": 112,
        "full_name": "Chicago Cubs",
        "abbrev": "CHC",
        "slug": "cubs",
        "aliases": ["Cubs", "Chicago Cubs", "CHC", "cubs"],
    },
    {
        "team_id": 113,
        "full_name": "Cincinnati Reds",
        "abbrev": "CIN",
        "slug": "reds",
        "aliases": ["Reds", "Cincinnati", "CIN", "Cincinnati Reds", "reds"],
    },
    {
        "team_id": 114,
        "full_name": "Cleveland Guardians",
        "abbrev": "CLE",
        "slug": "guardians",
        "aliases": ["Guardians", "Cleveland", "CLE", "Cleveland Guardians", "Indians", "guardians"],
    },
    {
        "team_id": 115,
        "full_name": "Colorado Rockies",
        "abbrev": "COL",
        "slug": "rockies",
        "aliases": ["Rockies", "Colorado", "COL", "Colorado Rockies", "rockies"],
    },
    {
        "team_id": 116,
        "full_name": "Detroit Tigers",
        "abbrev": "DET",
        "slug": "tigers",
        "aliases": ["Tigers", "Detroit", "DET", "Detroit Tigers", "tigers"],
    },
    {
        "team_id": 117,
        "full_name": "Houston Astros",
        "abbrev": "HOU",
        "slug": "astros",
        "aliases": ["Astros", "Houston", "HOU", "Houston Astros", "astros"],
    },
    {
        "team_id": 118,
        "full_name": "Kansas City Royals",
        "abbrev": "KC",
        "slug": "royals",
        "aliases": ["Royals", "Kansas City", "KC", "KCR", "Kansas City Royals", "royals"],
    },
    {
        "team_id": 119,
        "full_name": "Los Angeles Dodgers",
        "abbrev": "LAD",
        "slug": "dodgers",
        "aliases": ["Dodgers", "LAD", "Los Angeles Dodgers", "LA Dodgers", "dodgers"],
    },
    {
        "team_id": 120,
        "full_name": "Washington Nationals",
        "abbrev": "WSH",
        "slug": "nationals",
        "aliases": ["Nationals", "Nats", "Washington", "WSH", "WAS", "Washington Nationals", "nationals"],
    },
    {
        "team_id": 121,
        "full_name": "New York Mets",
        "abbrev": "NYM",
        "slug": "mets",
        "aliases": ["Mets", "NYM", "New York Mets", "NY Mets", "mets"],
    },
    {
        "team_id": 133,
        "full_name": "Athletics",
        "abbrev": "ATH",
        "slug": "athletics",
        "aliases": ["Athletics", "A's", "Oakland Athletics", "Oakland", "ATH", "OAK", "Sacramento Athletics", "athletics"],
    },
    {
        "team_id": 134,
        "full_name": "Pittsburgh Pirates",
        "abbrev": "PIT",
        "slug": "pirates",
        "aliases": ["Pirates", "Bucs", "Pittsburgh", "PIT", "Pittsburgh Pirates", "pirates"],
    },
    {
        "team_id": 135,
        "full_name": "San Diego Padres",
        "abbrev": "SD",
        "slug": "padres",
        "aliases": ["Padres", "San Diego", "SD", "SDP", "San Diego Padres", "padres"],
    },
    {
        "team_id": 136,
        "full_name": "Seattle Mariners",
        "abbrev": "SEA",
        "slug": "mariners",
        "aliases": ["Mariners", "M's", "Seattle", "SEA", "Seattle Mariners", "mariners"],
    },
    {
        "team_id": 137,
        "full_name": "San Francisco Giants",
        "abbrev": "SF",
        "slug": "giants",
        "aliases": ["Giants", "San Francisco", "SF", "SFG", "San Francisco Giants", "giants"],
    },
    {
        "team_id": 138,
        "full_name": "St. Louis Cardinals",
        "abbrev": "STL",
        "slug": "cardinals",
        "aliases": ["Cardinals", "Cards", "St. Louis", "STL", "St. Louis Cardinals", "Saint Louis Cardinals", "cardinals"],
    },
    {
        "team_id": 139,
        "full_name": "Tampa Bay Rays",
        "abbrev": "TB",
        "slug": "rays",
        "aliases": ["Rays", "Tampa Bay", "TB", "TBR", "Tampa Bay Rays", "rays"],
    },
    {
        "team_id": 140,
        "full_name": "Texas Rangers",
        "abbrev": "TEX",
        "slug": "rangers",
        "aliases": ["Rangers", "Texas", "TEX", "Texas Rangers", "rangers"],
    },
    {
        "team_id": 141,
        "full_name": "Toronto Blue Jays",
        "abbrev": "TOR",
        "slug": "bluejays",
        "aliases": ["Blue Jays", "BlueJays", "blue-jays", "Jays", "Toronto", "TOR", "Toronto Blue Jays", "bluejays"],
    },
    {
        "team_id": 142,
        "full_name": "Minnesota Twins",
        "abbrev": "MIN",
        "slug": "twins",
        "aliases": ["Twins", "Minnesota", "MIN", "Minnesota Twins", "twins"],
    },
    {
        "team_id": 143,
        "full_name": "Philadelphia Phillies",
        "abbrev": "PHI",
        "slug": "phillies",
        "aliases": ["Phillies", "Philadelphia", "PHI", "Philadelphia Phillies", "phillies", "Phils"],
    },
    {
        "team_id": 144,
        "full_name": "Atlanta Braves",
        "abbrev": "ATL",
        "slug": "braves",
        "aliases": ["Braves", "Atlanta", "ATL", "Atlanta Braves", "braves"],
    },
    {
        "team_id": 145,
        "full_name": "Chicago White Sox",
        "abbrev": "CWS",
        "slug": "whitesox",
        "aliases": ["White Sox", "WhiteSox", "white-sox", "Chicago White Sox", "CWS", "CHW", "whitesox"],
    },
    {
        "team_id": 146,
        "full_name": "Miami Marlins",
        "abbrev": "MIA",
        "slug": "marlins",
        "aliases": ["Marlins", "Miami", "MIA", "Miami Marlins", "marlins", "Fish"],
    },
    {
        "team_id": 147,
        "full_name": "New York Yankees",
        "abbrev": "NYY",
        "slug": "yankees",
        "aliases": ["Yankees", "NYY", "New York Yankees", "NY Yankees", "yankees", "Bronx Bombers", "Yanks"],
    },
    {
        "team_id": 158,
        "full_name": "Milwaukee Brewers",
        "abbrev": "MIL",
        "slug": "brewers",
        "aliases": ["Brewers", "Milwaukee", "MIL", "Milwaukee Brewers", "brewers", "Crew"],
    },
]

# Sport to seed list mapping
ALL_SEEDS: Dict[str, List[TeamAliasSeed]] = {
    "mlb": MLB_TEAM_SEEDS,
}

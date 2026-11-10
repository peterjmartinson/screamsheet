"""International Soccer data provider using API-Football (v3)."""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from ..base import SportsDataProvider
from ..db.soccer_db import (
    resolve_soccer_league,
    resolve_soccer_player,
    resolve_soccer_team,
)

logger = logging.getLogger(__name__)

AL_NASSR_TEAM_ID = 1005
PORTUGAL_TEAM_ID = 27
CR7_PLAYER_ID = 874

# Default target competitions for international soccer screamsheet
TARGET_LEAGUES: Dict[int, str] = {
    307: "Saudi Pro League",
    2: "UEFA Champions League",
    39: "Premier League",
    140: "La Liga",
    17: "AFC Champions League Elite",
    308: "King's Cup",
    5: "UEFA Nations League",
    32: "World Cup Qualifiers",
}

MARQUEE_CLUBS: Dict[int, str] = {
    541: "Real Madrid",
    529: "Barcelona",
    50: "Manchester City",
    40: "Liverpool",
    42: "Arsenal",
    49: "Chelsea",
    33: "Manchester United",
    157: "Bayern Munich",
    85: "Paris Saint-Germain",
    505: "Inter Milan",
    496: "Juventus",
}

LEAGUE_TIER_POINTS: Dict[int, int] = {
    2: 100,
    17: 85,
    39: 75,
    140: 65,
    307: 60,
    5: 70,
    32: 70,
    308: 50,
    6: 85,
    12: 75,
    399: 60,
}


def resolve_team_list(raw_teams: Optional[List[Any]]) -> List[Tuple[int, str]]:
    """Resolve a list of team entries/names/tuples into [(team_id, full_name), ...]."""
    if not raw_teams:
        return []
    resolved: List[Tuple[int, str]] = []
    for idx, item in enumerate(raw_teams, start=1):
        if isinstance(item, tuple) and len(item) == 2:
            resolved.append((int(item[0]), str(item[1])))
        elif hasattr(item, "id") and hasattr(item, "name"):
            resolved.append((int(item.id), str(item.name)))
        elif isinstance(item, dict) and "id" in item and "name" in item:
            resolved.append((int(item["id"]), str(item["name"])))
        else:
            q = item.get("name") if isinstance(item, dict) else item
            hit = resolve_soccer_team(q)
            if hit:
                resolved.append((int(hit["team_id"]), str(hit["full_name"])))
            elif isinstance(q, int):
                resolved.append((q, f"Team {q}"))
            elif str(q).strip():
                resolved.append((900000 + idx, str(q).strip()))
    return resolved


def resolve_player_list(raw_players: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """Resolve a list of player names/IDs/dicts into soccer_db player dicts."""
    if not raw_players:
        return []
    resolved: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_players, start=1):
        if isinstance(item, dict) and "player_id" in item and "full_name" in item:
            resolved.append(item)
            continue
        q = item.get("name") if isinstance(item, dict) else item
        hit = resolve_soccer_player(q)
        if hit:
            resolved.append(hit)
        elif str(q).strip():
            resolved.append({
                "player_id": 900000 + idx,
                "full_name": str(q).strip(),
                "first_name": "",
                "last_name": str(q).strip().split()[-1],
                "nationality": "",
                "current_team_id": None,
                "current_team_name": "",
                "position": "Attacker",
                "stats_json": None,
            })
    return resolved


def resolve_league_dict(raw_leagues: Optional[List[Any]]) -> Dict[int, str]:
    """Resolve a list of league names/IDs into {league_id: league_name}."""
    if not raw_leagues:
        return {}
    resolved: Dict[int, str] = {}
    for idx, item in enumerate(raw_leagues, start=1):
        if isinstance(item, tuple) and len(item) == 2:
            resolved[int(item[0])] = str(item[1])
            continue
        hit = resolve_soccer_league(item)
        if hit:
            resolved[int(hit["league_id"])] = str(hit["name"])
        elif isinstance(item, int):
            resolved[item] = TARGET_LEAGUES.get(item, f"League {item}")
        elif str(item).strip().isdigit():
            lid = int(str(item).strip())
            resolved[lid] = TARGET_LEAGUES.get(lid, f"League {lid}")
    return resolved


def score_fixture_for_motd(
    fixture: Dict[str, Any],
    favorite_team_ids: Optional[List[int]] = None,
) -> float:
    """Calculate an excitement score for selecting Match of the Day."""
    home_id = fixture.get("home_id") or fixture.get("teams", {}).get("home", {}).get("id")
    away_id = fixture.get("away_id") or fixture.get("teams", {}).get("away", {}).get("id")

    # 1. Subscriber Affinity Locks (or default Al-Nassr / Portugal)
    if favorite_team_ids:
        for rank, fav_id in enumerate(favorite_team_ids):
            if fav_id in (home_id, away_id):
                return max(5000.0, 10000.0 - rank * 1500.0)
    else:
        if AL_NASSR_TEAM_ID in (home_id, away_id):
            return 10000.0
        if PORTUGAL_TEAM_ID in (home_id, away_id):
            return 8000.0

    league_id = fixture.get("league_id") or fixture.get("league", {}).get("id")
    score = float(LEAGUE_TIER_POINTS.get(league_id, 30))

    # 2. Marquee Club Multiplier
    marquee_count = sum(1 for tid in (home_id, away_id) if tid in MARQUEE_CLUBS)
    score += marquee_count * 25.0
    if marquee_count == 2:
        score += 20.0

    # 3. Goal Volume
    goals_home = fixture.get("home_score", 0) or 0
    goals_away = fixture.get("away_score", 0) or 0
    total_goals = goals_home + goals_away
    score += total_goals * 8.0

    # 4. Competitive Margin & Drama
    goal_diff = abs(goals_home - goals_away)
    if goal_diff == 0 and total_goals > 0:
        score += 25.0
    elif goal_diff == 1:
        score += 20.0

    status_short = fixture.get("status_short") or fixture.get("status", "")
    if status_short in ("AET", "PEN"):
        score += 35.0

    return score


class SoccerDataProvider(SportsDataProvider):
    """
    Data provider for international football using API-Football v3.
    Supports per-subscriber customization of favorite teams, players, leagues, and standings.
    """

    COMPLETED_STATUSES = {"FT", "AET", "PEN"}

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        if "api_key" in config:
            self.api_key: str = config.get("api_key") or ""
        else:
            self.api_key = (
                os.environ.get("APISPORTS_KEY")
                or os.environ.get("FOOTBALL_API_KEY")
                or os.environ.get("FIFA_API_KEY")
                or ""
            )
        self.base_url: str = config.get("base_url", "https://v3.football.api-sports.io")
        self.timeout: int = int(config.get("request_timeout", 15))

        # Configurable subscriber preferences
        raw_teams = config.get("favorite_teams") or config.get("teams")
        self.favorite_teams: List[Tuple[int, str]] = (
            resolve_team_list(raw_teams)
            if raw_teams is not None
            else [(AL_NASSR_TEAM_ID, "Al-Nassr"), (PORTUGAL_TEAM_ID, "Portugal")]
        )

        raw_players = config.get("favorite_players") or config.get("players")
        if raw_players is not None:
            self.favorite_players: List[Dict[str, Any]] = resolve_player_list(raw_players)
        elif raw_teams is None:
            # Default to Cristiano Ronaldo only when using default teams
            self.favorite_players = resolve_player_list(["Cristiano Ronaldo"])
        else:
            self.favorite_players = []

        raw_leagues = config.get("leagues") or config.get("target_leagues")
        resolved_leagues = resolve_league_dict(raw_leagues) if raw_leagues else {}
        if resolved_leagues:
            self.target_leagues: Dict[int, str] = resolved_leagues
        else:
            self.target_leagues = dict(TARGET_LEAGUES)
            # Also auto-include the primary domestic leagues of any configured favorite teams
            for tid, _ in self.favorite_teams:
                t_info = resolve_soccer_team(tid, allow_api_fallback=False)
                if t_info and t_info.get("primary_league_id"):
                    plid = int(t_info["primary_league_id"])
                    if plid not in self.target_leagues:
                        l_info = resolve_soccer_league(plid, allow_api_fallback=False)
                        if l_info:
                            self.target_leagues[plid] = str(l_info["name"])

        raw_standings = config.get("standings") or config.get("standings_leagues")
        resolved_standings = resolve_league_dict(raw_standings) if raw_standings else {}
        if resolved_standings:
            self.standings_leagues: List[Tuple[int, str]] = list(resolved_standings.items())[:2]
        else:
            # Smart default: if custom teams were given, use their domestic leagues; else Saudi + EPL
            custom_standings: List[Tuple[int, str]] = []
            if raw_teams is not None:
                for tid, _ in self.favorite_teams:
                    t_info = resolve_soccer_team(tid, allow_api_fallback=False)
                    if t_info and t_info.get("primary_league_id") and not t_info.get("is_national"):
                        plid = int(t_info["primary_league_id"])
                        l_info = resolve_soccer_league(plid, allow_api_fallback=False)
                        if l_info and all(x[0] != plid for x in custom_standings):
                            custom_standings.append((plid, str(l_info["name"])))
                if len(custom_standings) == 1:
                    fallback_second = (39, "Premier League") if custom_standings[0][0] != 39 else (2, "UEFA Champions League")
                    custom_standings.append(fallback_second)
            self.standings_leagues = custom_standings[:2] if custom_standings else [
                (307, "Saudi Pro League"),
                (39, "Premier League"),
            ]

        self._fixtures_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._standings_cache: Dict[int, List[Dict[str, Any]]] = {}
        self._details_cache: Dict[int, Dict[str, Any]] = {}

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-apisports-key"] = self.api_key
        return headers

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GET request against API-Football."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Error querying API-Football endpoint: %s", endpoint)
            return {"response": []}

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """Fetch completed international matches for target leagues and favorite teams on date."""
        date_str = date.strftime("%Y-%m-%d")
        if date_str in self._fixtures_cache:
            return self._fixtures_cache[date_str]

        if not self.api_key:
            logger.info(
                "No API key found (APISPORTS_KEY / FOOTBALL_API_KEY / FIFA_API_KEY); returning sample soccer scores for %s",
                date_str,
            )
            return self._sample_scores(date_str)

        data = self._get("fixtures", {"date": date_str, "timezone": "America/New_York"})
        fixtures_raw = data.get("response", [])
        if not fixtures_raw:
            return []

        fav_team_ids = {tid for tid, _ in self.favorite_teams}
        for p in self.favorite_players:
            if p.get("current_team_id"):
                fav_team_ids.add(int(p["current_team_id"]))

        games: List[Dict[str, Any]] = []
        for item in fixtures_raw:
            league = item.get("league", {})
            lid = league.get("id")
            home = item.get("teams", {}).get("home", {})
            away = item.get("teams", {}).get("away", {})
            hid = home.get("id")
            aid = away.get("id")

            # Match target league or any favorite team/player's club
            if (
                lid not in self.target_leagues
                and hid not in fav_team_ids
                and aid not in fav_team_ids
            ):
                continue

            goals = item.get("goals", {})
            status = item.get("fixture", {}).get("status", {})
            status_short = status.get("short", "FT")

            score_pen = item.get("score", {}).get("penalty", {})
            score_agg = item.get("score", {}).get("aggregate", {})

            games.append({
                "fixture_id": item.get("fixture", {}).get("id"),
                "date": date_str,
                "league_id": lid,
                "league_name": self.target_leagues.get(lid) or league.get("name", "International"),
                "league_country": league.get("country", ""),
                "home_id": hid,
                "home_team": home.get("name", "Home"),
                "away_id": aid,
                "away_team": away.get("name", "Away"),
                "home_score": goals.get("home", 0) if goals.get("home") is not None else 0,
                "away_score": goals.get("away", 0) if goals.get("away") is not None else 0,
                "status": status.get("long", "Final"),
                "status_short": status_short,
                "home_penalties": score_pen.get("home"),
                "away_penalties": score_pen.get("away"),
                "aggregate": score_agg if (score_agg.get("home") is not None) else None,
            })

        self._fixtures_cache[date_str] = games
        return games

    def get_standings(self, standings_leagues: Optional[List[Tuple[int, str]]] = None) -> Dict[str, pd.DataFrame]:
        """Fetch standings for the configured dual standings leagues."""
        leagues_to_fetch = standings_leagues or self.standings_leagues
        tables: Dict[str, pd.DataFrame] = {}
        for lid, league_name in leagues_to_fetch:
            if not self.api_key:
                tables[league_name] = self._sample_standings(lid, league_name)
                continue

            l_info = resolve_soccer_league(lid, allow_api_fallback=False)
            current_year = datetime.now().year
            default_season = current_year if datetime.now().month >= 7 else (current_year - 1)
            season = int(l_info["current_season"]) if (l_info and l_info.get("current_season")) else default_season

            data = self._get("standings", {"league": lid, "season": season})
            resp = data.get("response", [])
            if not resp:
                tables[league_name] = self._sample_standings(lid, league_name)
                continue

            league_data = resp[0].get("league", {})
            standings_list = league_data.get("standings", [[]])[0]

            rows = []
            for entry in standings_list:
                rows.append({
                    "rank": entry.get("rank"),
                    "team": entry.get("team", {}).get("name"),
                    "team_id": entry.get("team", {}).get("id"),
                    "mp": entry.get("all", {}).get("played", 0),
                    "w": entry.get("all", {}).get("win", 0),
                    "d": entry.get("all", {}).get("draw", 0),
                    "l": entry.get("all", {}).get("lose", 0),
                    "gd": entry.get("goalsDiff", 0),
                    "pts": entry.get("points", 0),
                    "form": entry.get("form", ""),
                })
            df = pd.DataFrame(rows)
            tables[league_name] = df

        return tables

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Check if a team played a completed fixture on date."""
        scores = self.get_game_scores(date)
        for g in scores:
            if g.get("status_short") in self.COMPLETED_STATUSES:
                if g.get("home_id") == team_id or g.get("away_id") == team_id:
                    return True
        return False

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (team_id, team_name) for all completed fixtures on date."""
        scores = self.get_game_scores(date)
        teams: List[Tuple[int, str]] = []
        for g in scores:
            if g.get("status_short") in self.COMPLETED_STATUSES:
                if g.get("home_id") and g.get("home_team"):
                    teams.append((int(g["home_id"]), str(g["home_team"])))
                if g.get("away_id") and g.get("away_team"):
                    teams.append((int(g["away_id"]), str(g["away_team"])))
        return teams

    def get_match_of_the_day(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Select the highest-excitement match from date, prioritizing subscriber favorites."""
        scores = self.get_game_scores(date)
        completed = [s for s in scores if s.get("status_short") in self.COMPLETED_STATUSES]
        if not completed:
            return None
        fav_ids = [tid for tid, _ in self.favorite_teams]
        for p in self.favorite_players:
            if p.get("current_team_id") and int(p["current_team_id"]) not in fav_ids:
                fav_ids.append(int(p["current_team_id"]))
        return max(completed, key=lambda f: score_fixture_for_motd(f, favorite_team_ids=fav_ids))

    def get_upcoming_fixtures(self, team_id: int, team_name: str = "", limit: int = 2) -> List[Dict[str, Any]]:
        """Fetch the next upcoming scheduled fixtures for a favorite team."""
        if self.api_key:
            data = self._get("fixtures", {"team": team_id, "next": limit, "timezone": "America/New_York"})
            resp = data.get("response", [])
            upcoming: List[Dict[str, Any]] = []
            for item in resp:
                fx = item.get("fixture", {})
                lg = item.get("league", {})
                home = item.get("teams", {}).get("home", {})
                away = item.get("teams", {}).get("away", {})
                venue = fx.get("venue", {}).get("name", "TBD")
                city = fx.get("venue", {}).get("city", "")
                venue_str = f"{venue}, {city}".strip(", ")
                date_iso = fx.get("date", "")
                date_label = date_iso[:10] if date_iso else "Upcoming"
                upcoming.append({
                    "matchup": f"{home.get('name', 'Home')} vs. {away.get('name', 'Away')}",
                    "competition": lg.get("name", "Fixture"),
                    "venue": venue_str or "TBD",
                    "date": date_label,
                })
            if upcoming:
                return upcoming

        # Offline / fallback preview tailored to the requested team
        display_team = team_name or "Al-Nassr"
        if team_id == AL_NASSR_TEAM_ID or "nassr" in display_team.lower():
            return [{
                "matchup": "Al-Nassr vs. Al-Ain",
                "competition": "AFC Champions League Elite",
                "venue": "Al-Awwal Park, Riyadh",
                "date": "Upcoming Matchday",
            }]
        return [{
            "matchup": f"{display_team} vs. League Opponent",
            "competition": self.standings_leagues[0][1] if self.standings_leagues else "League Fixture",
            "venue": f"{display_team} Stadium",
            "date": "Upcoming Matchday",
        }]

    def _build_spotlight_for_match(
        self,
        home_name: str,
        away_name: str,
        home_xi: List[Dict[str, Any]],
        away_xi: List[Dict[str, Any]],
        key_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a spotlight banner dict for either a configured favorite player or the Match MVP."""
        all_players = [(p, home_name) for p in home_xi] + [(p, away_name) for p in away_xi]
        goal_counts: Dict[str, int] = {}
        for ev in key_events:
            if ev.get("type") in ("GOAL", "PEN"):
                p_name = str(ev.get("player", "")).replace("(P)", "").strip()
                if p_name:
                    goal_counts[p_name.lower()] = goal_counts.get(p_name.lower(), 0) + 1

        # 1. Check if any configured favorite player is in this match
        for fav_p in self.favorite_players:
            fav_last = str(fav_p.get("last_name") or fav_p["full_name"].split()[-1]).lower()
            fav_full = str(fav_p["full_name"]).lower()
            for xi_p, club_name in all_players:
                xi_name = str(xi_p.get("name", "")).lower()
                if fav_last in xi_name or fav_full in xi_name:
                    goals = sum(cnt for k, cnt in goal_counts.items() if fav_last in k)
                    career_total = None
                    if fav_p.get("stats_json"):
                        try:
                            career_total = json.loads(fav_p["stats_json"]).get("career_total")
                        except Exception:
                            career_total = None
                    is_cr7 = fav_p.get("player_id") == CR7_PLAYER_ID or "ronaldo" in fav_full
                    return {
                        "featured": True,
                        "is_cr7": is_cr7,
                        "label": "CR7 SPOTLIGHT" if is_cr7 else f"{fav_p['full_name'].upper()} SPOTLIGHT",
                        "player_name": fav_p["full_name"],
                        "team_name": club_name,
                        "rating": str(xi_p.get("rating", "8.2")),
                        "goals": goals,
                        "career_total": career_total or (916 if is_cr7 else None),
                        "milestone_note": "(Road to 1,000)" if is_cr7 else f"({club_name})",
                    }

        # 2. Fallback: Spotlight the Man of the Match (highest rated player or top scorer)
        if all_players:
            def _player_score(item: Tuple[Dict[str, Any], str]) -> float:
                p_dict, _ = item
                try:
                    r = float(p_dict.get("rating", 7.0))
                except (ValueError, TypeError):
                    r = 7.0
                p_name = str(p_dict.get("name", "")).lower()
                g = sum(cnt for k, cnt in goal_counts.items() if k in p_name or p_name in k)
                return r + g * 0.5

            best_p, best_club = max(all_players, key=_player_score)
            best_name = str(best_p.get("name", "Star Player"))
            best_goals = sum(cnt for k, cnt in goal_counts.items() if k in best_name.lower() or best_name.lower() in k)
            return {
                "featured": True,
                "is_cr7": False,
                "label": "MAN OF THE MATCH",
                "player_name": best_name,
                "team_name": best_club,
                "rating": str(best_p.get("rating", "8.4")),
                "goals": best_goals,
                "career_total": None,
                "milestone_note": f"({best_club})",
            }

        return {
            "featured": False,
            "rating": "8.0",
            "goals": 0,
            "career_total": None,
        }

    def get_box_score(self, fixture_id: int, date: datetime) -> Optional[Dict[str, Any]]:
        """Fetch deep-dive box score details for fixture_id."""
        if fixture_id in self._details_cache:
            return self._details_cache[fixture_id]

        if not self.api_key:
            return self._sample_box_score(fixture_id)

        # Look up basic match info from scores cache if available
        scores = self.get_game_scores(date)
        match_meta = next((g for g in scores if g.get("fixture_id") == fixture_id), {})

        # 3 API calls for lineups, stats, and events
        lineups_data = self._get("fixtures/lineups", {"fixture": fixture_id}).get("response", [])
        stats_data = self._get("fixtures/statistics", {"fixture": fixture_id}).get("response", [])
        events_data = self._get("fixtures/events", {"fixture": fixture_id}).get("response", [])

        # Process lineups
        home_lineup = lineups_data[0] if len(lineups_data) > 0 else {}
        away_lineup = lineups_data[1] if len(lineups_data) > 1 else {}

        home_xi = [
            {
                "number": p.get("player", {}).get("number", 0),
                "name": p.get("player", {}).get("name", ""),
                "pos": p.get("player", {}).get("pos", ""),
                "rating": "7.0",
                "is_captain": False,
            }
            for p in home_lineup.get("startXI", [])
        ]
        away_xi = [
            {
                "number": p.get("player", {}).get("number", 0),
                "name": p.get("player", {}).get("name", ""),
                "pos": p.get("player", {}).get("pos", ""),
                "rating": "7.0",
                "is_captain": False,
            }
            for p in away_lineup.get("startXI", [])
        ]

        # Process stats
        home_stats = {s.get("type"): s.get("value") for s in (stats_data[0].get("statistics", []) if len(stats_data) > 0 else [])}
        away_stats = {s.get("type"): s.get("value") for s in (stats_data[1].get("statistics", []) if len(stats_data) > 1 else [])}

        team_metrics = [
            {"label": "Possession", "home": str(home_stats.get("Ball Possession", "50%")), "away": str(away_stats.get("Ball Possession", "50%"))},
            {"label": "Expected Goals (xG)", "home": str(home_stats.get("expected_goals", "—")), "away": str(away_stats.get("expected_goals", "—"))},
            {"label": "Total Shots", "home": str(home_stats.get("Total Shots", 0)), "away": str(away_stats.get("Total Shots", 0))},
            {"label": "Shots on Goal", "home": str(home_stats.get("Shots on Goal", 0)), "away": str(away_stats.get("Shots on Goal", 0))},
            {"label": "Corner Kicks", "home": str(home_stats.get("Corner Kicks", 0)), "away": str(away_stats.get("Corner Kicks", 0))},
            {"label": "Fouls", "home": str(home_stats.get("Fouls", 0)), "away": str(away_stats.get("Fouls", 0))},
            {"label": "Yellow Cards", "home": str(home_stats.get("Yellow Cards", 0)), "away": str(away_stats.get("Yellow Cards", 0))},
            {"label": "Goalkeeper Saves", "home": str(home_stats.get("Goalkeeper Saves", 0)), "away": str(away_stats.get("Goalkeeper Saves", 0))},
        ]

        # Key events
        key_events = []
        for ev in events_data:
            ev_type = ev.get("type", "")
            time_el = f"{ev.get('time', {}).get('elapsed', 0)}'"
            player_name = ev.get("player", {}).get("name", "")
            detail = ev.get("detail", "")
            key_events.append({
                "minute": time_el,
                "type": ev_type.upper(),
                "team": "home" if ev.get("team", {}).get("id") == home_lineup.get("team", {}).get("id") else "away",
                "player": player_name,
                "detail": detail,
            })

        home_name = home_lineup.get("team", {}).get("name") or match_meta.get("home_team", "Home")
        away_name = away_lineup.get("team", {}).get("name") or match_meta.get("away_team", "Away")
        spotlight = self._build_spotlight_for_match(home_name, away_name, home_xi, away_xi, key_events)

        box_score = {
            "fixture_id": fixture_id,
            "competition": match_meta.get("league_name", "International Match"),
            "venue": "",
            "home_team": {
                "name": home_name,
                "formation": home_lineup.get("formation", "4-3-3"),
                "score": match_meta.get("home_score", 0),
            },
            "away_team": {
                "name": away_name,
                "formation": away_lineup.get("formation", "4-3-3"),
                "score": match_meta.get("away_score", 0),
            },
            "starting_xi": {"home": home_xi, "away": away_xi},
            "team_metrics": team_metrics,
            "key_events": key_events,
            "ronaldo_spotlight": spotlight,
            "player_spotlight": spotlight,
        }
        self._details_cache[fixture_id] = box_score
        return box_score

    def get_game_summary(
        self,
        fixture_id: int,
        date: datetime,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
        **kwargs: Any,
    ) -> Optional[str]:
        """Generate a 200-300 word engaging newspaper-style game narrative."""
        box = self.get_box_score(fixture_id, date)
        if not box:
            return "No match details available."

        fallback_text = self._build_rich_summary(box)

        gemini_key = os.getenv("GEMINI_API_KEY")
        grok_key = os.getenv("GROK_API_KEY")
        if not (gemini_key or grok_key):
            return fallback_text

        try:
            from ..llm.summarizers import SoccerGameSummarizer

            home_team = box.get("home_team", {}).get("name", "Home")
            away_team = box.get("away_team", {}).get("name", "Away")
            h_score = str(box.get("home_team", {}).get("score", 0))
            a_score = str(box.get("away_team", {}).get("score", 0))
            comp = box.get("competition", "International Football Match")

            events_timeline = "\n".join(
                f"- {e.get('minute')}: {e.get('type')} by {e.get('player')} ({e.get('detail')})"
                for e in box.get("key_events", [])
            ) or "- No major events recorded"

            stats_summary = "\n".join(
                f"- {m.get('label')}: {home_team} {m.get('home')} vs {m.get('away')} {away_team}"
                for m in box.get("team_metrics", [])
            ) or "- Possession: 50% vs 50%"

            extracted_info = {
                "competition": comp,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": h_score,
                "away_score": a_score,
                "status_label": "",
                "events_timeline": events_timeline,
                "stats_summary": stats_summary,
            }

            summarizer = SoccerGameSummarizer(gemini_api_key=gemini_key, grok_api_key=grok_key)
            return summarizer.generate_summary(llm_choice="gemini", data=extracted_info)
        except Exception as exc:
            logger.warning("Soccer LLM summary failed, using rich text: %s", exc)
            return fallback_text

    def _build_rich_summary(self, box: Dict[str, Any]) -> str:
        """Construct a high-quality 200-250 word game recap from box score data."""
        home_team = box.get("home_team", {}).get("name", "Home")
        away_team = box.get("away_team", {}).get("name", "Away")
        comp = box.get("competition", "International Match")
        h_score = box.get("home_team", {}).get("score", 0)
        a_score = box.get("away_team", {}).get("score", 0)

        events = box.get("key_events", [])
        goal_events = [e for e in events if e.get("type") in ("GOAL", "PEN")]

        if h_score > a_score:
            result_phrase = f"{home_team} claimed a thrilling {h_score}–{a_score} victory over {away_team}"
            victor = home_team
        elif a_score > h_score:
            result_phrase = f"{away_team} secured an emphatic {a_score}–{h_score} triumph over {home_team}"
            victor = away_team
        else:
            result_phrase = f"{home_team} and {away_team} shared the spoils in an intense {h_score}–{a_score} draw"
            victor = None

        spotlight = box.get("player_spotlight") or box.get("ronaldo_spotlight", {})
        spotlight_clause = ""
        if spotlight.get("featured"):
            if spotlight.get("is_cr7", True) and spotlight.get("career_total") == 916:
                cr7_total = spotlight.get("career_total", 916)
                spotlight_clause = (
                    f" Cristiano Ronaldo served as the attacking spearhead, showcasing his signature movement and instincts inside "
                    f"the box. His clinical execution pushed his historic career tally to {cr7_total} goals, fueling his quest "
                    f"toward the elusive 1,000-goal milestone."
                )
            elif spotlight.get("player_name"):
                p_name = spotlight["player_name"]
                p_rating = spotlight.get("rating", "8.5")
                spotlight_clause = (
                    f" {p_name} stood out as a decisive figure on the pitch, earning a {p_rating} match rating with "
                    f"relentless attacking movement and composure in the final third."
                )

        goals_narrative = ""
        if goal_events:
            goal_strs = [f"{g.get('player', 'A striker')} ({g.get('minute', '')})" for g in goal_events]
            goals_narrative = (
                f" The breakthrough moments arrived through strikes from {', followed by '.join(goal_strs)}. "
                f"Each goal altered the tactical landscape, prompting urgent adjustments and high-tempo pressing."
            )

        para1 = (
            f"In a captivating {comp} encounter, {result_phrase} before an electric atmosphere. "
            f"Both squads embraced an attacking mentality from the opening whistle, testing the backlines with "
            f"quick vertical transitions and stretching play out wide.{spotlight_clause}"
        )

        para2 = (
            f"The contest intensified across the second half with fierce battles in central midfield.{goals_narrative} "
            f"Goalkeepers on both ends produced crucial stops in high-leverage sequences, maintaining suspense as the "
            f"game stretched into its closing moments."
        )

        para3 = (
            f"When the final whistle sounded, the outcome reverberated across the league standings. "
            f"{f'The hard-earned three points provide {victor} with major momentum in the championship race.' if victor else 'The shared point leaves both clubs eager to build on their collective grit in upcoming fixtures.'} "
            f"Supporters enjoyed an exceptional display of skill, tactical discipline, and unrelenting competitive drive."
        )

        return f"{para1}\n\n{para2}\n\n{para3}"

    # ------------------------------------------------------------------
    # Sample Mock Fallbacks (for testing and offline operation)
    # ------------------------------------------------------------------

    def _sample_scores(self, date_str: str) -> List[Dict[str, Any]]:
        return [
            {
                "fixture_id": 1204851,
                "date": date_str,
                "league_id": 307,
                "league_name": "Saudi Pro League",
                "home_id": 1005,
                "home_team": "Al-Nassr",
                "away_id": 1007,
                "away_team": "Al-Hilal",
                "home_score": 3,
                "away_score": 1,
                "status": "Match Finished",
                "status_short": "FT",
            },
            {
                "fixture_id": 1204852,
                "date": date_str,
                "league_id": 39,
                "league_name": "Premier League",
                "home_id": 40,
                "home_team": "Liverpool",
                "away_id": 42,
                "away_team": "Arsenal",
                "home_score": 2,
                "away_score": 2,
                "status": "Match Finished",
                "status_short": "FT",
            },
            {
                "fixture_id": 1204853,
                "date": date_str,
                "league_id": 2,
                "league_name": "UEFA Champions League",
                "home_id": 541,
                "home_team": "Real Madrid",
                "away_id": 157,
                "away_team": "Bayern Munich",
                "home_score": 3,
                "away_score": 2,
                "status": "Match Finished",
                "status_short": "FT",
            },
        ]

    def _sample_standings(self, league_id: int, league_name: str = "") -> pd.DataFrame:
        if league_id == 307:
            return pd.DataFrame([
                {"rank": 1, "team": "Al-Hilal", "team_id": 1007, "mp": 10, "w": 9, "d": 1, "l": 0, "gd": "+21", "pts": 28, "form": "WWWDW"},
                {"rank": 2, "team": "Al-Nassr", "team_id": 1005, "mp": 10, "w": 8, "d": 2, "l": 0, "gd": "+19", "pts": 26, "form": "WWWWW"},
                {"rank": 3, "team": "Al-Ittihad", "team_id": 1003, "mp": 10, "w": 8, "d": 0, "l": 2, "gd": "+14", "pts": 24, "form": "LWWWW"},
                {"rank": 4, "team": "Al-Shabab", "team_id": 1008, "mp": 10, "w": 7, "d": 0, "l": 3, "gd": "+8", "pts": 21, "form": "WLWLW"},
                {"rank": 5, "team": "Al-Qadsiah", "team_id": 1009, "mp": 10, "w": 6, "d": 1, "l": 3, "gd": "+5", "pts": 19, "form": "DWLWW"},
            ])
        if league_id == 399 or "npfl" in league_name.lower() or "nigeria" in league_name.lower():
            return pd.DataFrame([
                {"rank": 1, "team": "Remo Stars", "team_id": 5210, "mp": 12, "w": 8, "d": 2, "l": 2, "gd": "+11", "pts": 26, "form": "WWLDW"},
                {"rank": 2, "team": "Enyimba", "team_id": 5203, "mp": 12, "w": 7, "d": 3, "l": 2, "gd": "+9", "pts": 24, "form": "WDWWW"},
                {"rank": 3, "team": "Rangers International", "team_id": 5209, "mp": 12, "w": 6, "d": 4, "l": 2, "gd": "+7", "pts": 22, "form": "DWWLD"},
                {"rank": 4, "team": "Kano Pillars", "team_id": 5205, "mp": 12, "w": 6, "d": 2, "l": 4, "gd": "+4", "pts": 20, "form": "WLWWL"},
                {"rank": 5, "team": "Shooting Stars", "team_id": 5212, "mp": 12, "w": 5, "d": 3, "l": 4, "gd": "+2", "pts": 18, "form": "LWDWL"},
            ])
        return pd.DataFrame([
            {"rank": 1, "team": "Liverpool", "team_id": 40, "mp": 10, "w": 8, "d": 1, "l": 1, "gd": "+11", "pts": 25, "form": "WDWWW"},
            {"rank": 2, "team": "Manchester City", "team_id": 50, "mp": 10, "w": 7, "d": 2, "l": 1, "gd": "+10", "pts": 23, "form": "LWWWD"},
            {"rank": 3, "team": "Arsenal", "team_id": 42, "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+6", "pts": 18, "form": "LDWDL"},
            {"rank": 4, "team": "Chelsea", "team_id": 49, "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+8", "pts": 18, "form": "DWLDW"},
            {"rank": 5, "team": "Nottingham Forest", "team_id": 65, "mp": 10, "w": 5, "d": 4, "l": 1, "gd": "+7", "pts": 19, "form": "WWDWW"},
        ])

    def _sample_box_score(self, fixture_id: int) -> Dict[str, Any]:
        return {
            "fixture_id": fixture_id,
            "competition": "Saudi Pro League • Matchday 10",
            "venue": "Al-Awwal Park, Riyadh (Att: 24,800)",
            "home_team": {"name": "Al-Nassr", "formation": "4-2-3-1", "score": 3},
            "away_team": {"name": "Al-Hilal", "formation": "4-3-3", "score": 1},
            "ronaldo_spotlight": {
                "featured": True,
                "is_cr7": True,
                "label": "CR7 SPOTLIGHT",
                "player_name": "Cristiano Ronaldo",
                "rating": "8.8",
                "goals": 2,
                "career_total": 916,
                "milestone_note": "(Road to 1,000)",
            },
            "starting_xi": {
                "home": [
                    {"number": 24, "name": "Bento", "pos": "G", "rating": "7.2"},
                    {"number": 2, "name": "S. Al-Ghannam", "pos": "D", "rating": "6.8"},
                    {"number": 27, "name": "A. Laporte", "pos": "D", "rating": "7.5"},
                    {"number": 20, "name": "A. Brozović", "pos": "M", "rating": "7.7"},
                    {"number": 94, "name": "Talísca", "pos": "M", "rating": "8.1"},
                    {"number": 10, "name": "S. Mané", "pos": "F", "rating": "7.3"},
                    {"number": 7, "name": "C. Ronaldo", "pos": "F", "rating": "8.8"},
                ],
                "away": [
                    {"number": 37, "name": "Y. Bono", "pos": "G", "rating": "6.5"},
                    {"number": 3, "name": "K. Koulibaly", "pos": "D", "rating": "6.2"},
                    {"number": 8, "name": "R. Neves", "pos": "M", "rating": "7.1"},
                    {"number": 9, "name": "A. Mitrović", "pos": "F", "rating": "7.3"},
                ],
            },
            "team_metrics": [
                {"label": "Possession", "home": "48%", "away": "52%"},
                {"label": "Expected Goals (xG)", "home": "2.41", "away": "1.18"},
                {"label": "Total Shots", "home": "16", "away": "11"},
                {"label": "Shots on Goal", "home": "8", "away": "4"},
                {"label": "Corner Kicks", "home": "6", "away": "5"},
                {"label": "Fouls", "home": "12", "away": "15"},
                {"label": "Yellow Cards", "home": "1", "away": "3"},
            ],
            "key_events": [
                {"minute": "14'", "type": "GOAL", "team": "home", "player": "C. Ronaldo", "detail": "Volley"},
                {"minute": "31'", "type": "CARD", "team": "away", "player": "Ali Al-Bulaihi", "detail": "Yellow"},
                {"minute": "42'", "type": "GOAL", "team": "away", "player": "A. Mitrović", "detail": "Header"},
                {"minute": "78'", "type": "GOAL", "team": "home", "player": "C. Ronaldo (P)", "detail": "Penalty"},
                {"minute": "90+3'", "type": "GOAL", "team": "home", "player": "Talísca", "detail": "Counterattack"},
            ],
        }

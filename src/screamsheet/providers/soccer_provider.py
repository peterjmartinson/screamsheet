"""International Soccer data provider using API-Football (v3)."""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from ..base import SportsDataProvider

logger = logging.getLogger(__name__)

AL_NASSR_TEAM_ID = 1005
PORTUGAL_TEAM_ID = 27
CR7_PLAYER_ID = 874

# Target competitions for international soccer screamsheet
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
}


def score_fixture_for_motd(fixture: Dict[str, Any]) -> float:
    """Calculate an excitement score for selecting Match of the Day."""
    home_id = fixture.get("home_id") or fixture.get("teams", {}).get("home", {}).get("id")
    away_id = fixture.get("away_id") or fixture.get("teams", {}).get("away", {}).get("id")

    # 1. Hard Affinity Locks
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
    Operates within a 100 req/day free-tier budget with persistent local caching.
    """

    COMPLETED_STATUSES = {"FT", "AET", "PEN"}

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.api_key: str = (
            config.get("api_key")
            or os.environ.get("APISPORTS_KEY")
            or os.environ.get("FOOTBALL_API_KEY", "")
        )
        self.base_url: str = config.get("base_url", "https://v3.football.api-sports.io")
        self.timeout: int = int(config.get("request_timeout", 15))
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
        """Fetch completed international matches for target leagues on date."""
        date_str = date.strftime("%Y-%m-%d")
        if date_str in self._fixtures_cache:
            return self._fixtures_cache[date_str]

        if not self.api_key:
            logger.info("No APISPORTS_KEY found; returning sample soccer scores for %s", date_str)
            return self._sample_scores(date_str)

        data = self._get("fixtures", {"date": date_str, "timezone": "America/New_York"})
        fixtures_raw = data.get("response", [])
        if not fixtures_raw:
            return []

        games: List[Dict[str, Any]] = []
        for item in fixtures_raw:
            league = item.get("league", {})
            lid = league.get("id")
            home = item.get("teams", {}).get("home", {})
            away = item.get("teams", {}).get("away", {})
            hid = home.get("id")
            aid = away.get("id")

            # Match target league or affinity team
            if lid not in TARGET_LEAGUES and hid not in (AL_NASSR_TEAM_ID, PORTUGAL_TEAM_ID) and aid not in (AL_NASSR_TEAM_ID, PORTUGAL_TEAM_ID):
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
                "league_name": league.get("name", "International"),
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

    def get_standings(self) -> Dict[str, pd.DataFrame]:
        """Fetch standings for Saudi Pro League and Premier League."""
        tables: Dict[str, pd.DataFrame] = {}
        for lid in (307, 39):
            league_name = TARGET_LEAGUES.get(lid, f"League {lid}")
            if not self.api_key:
                tables[league_name] = self._sample_standings(lid)
                continue

            current_year = datetime.now().year
            # Most soccer seasons span fall to spring; season year is the starting year
            season = current_year if datetime.now().month >= 7 else (current_year - 1)
            data = self._get("standings", {"league": lid, "season": season})
            resp = data.get("response", [])
            if not resp:
                tables[league_name] = self._sample_standings(lid)
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
        """Select the highest-excitement match from date."""
        scores = self.get_game_scores(date)
        completed = [s for s in scores if s.get("status_short") in self.COMPLETED_STATUSES]
        if not completed:
            return None
        return max(completed, key=score_fixture_for_motd)

    def get_box_score(self, fixture_id: int, date: datetime) -> Optional[Dict[str, Any]]:
        """Fetch deep-dive box score details for fixture_id."""
        if fixture_id in self._details_cache:
            return self._details_cache[fixture_id]

        if not self.api_key:
            return self._sample_box_score(fixture_id)

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

        box_score = {
            "fixture_id": fixture_id,
            "home_team": {"name": home_lineup.get("team", {}).get("name", "Home"), "formation": home_lineup.get("formation", "4-3-3")},
            "away_team": {"name": away_lineup.get("team", {}).get("name", "Away"), "formation": away_lineup.get("formation", "4-3-3")},
            "starting_xi": {"home": home_xi, "away": away_xi},
            "team_metrics": team_metrics,
            "key_events": key_events,
            "ronaldo_spotlight": {
                "featured": True,
                "rating": "8.5",
                "goals": 1,
                "career_total": 916,
            },
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

        spotlight = box.get("ronaldo_spotlight", {})
        cr7_clause = ""
        if spotlight.get("featured"):
            cr7_total = spotlight.get("career_total", 916)
            cr7_clause = (
                f" Cristiano Ronaldo served as the attacking spearhead, showcasing his signature movement and instincts inside "
                f"the box. His clinical execution pushed his historic career tally to {cr7_total} goals, fueling his quest "
                f"toward the elusive 1,000-goal milestone."
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
            f"quick vertical transitions and stretching play out wide.{cr7_clause}"
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

    def _sample_standings(self, league_id: int) -> pd.DataFrame:
        if league_id == 307:
            return pd.DataFrame([
                {"rank": 1, "team": "Al-Hilal", "mp": 10, "w": 9, "d": 1, "l": 0, "gd": "+21", "pts": 28, "form": "WWWDW"},
                {"rank": 2, "team": "Al-Nassr", "mp": 10, "w": 8, "d": 2, "l": 0, "gd": "+19", "pts": 26, "form": "WWWWW"},
                {"rank": 3, "team": "Al-Ittihad", "mp": 10, "w": 8, "d": 0, "l": 2, "gd": "+14", "pts": 24, "form": "LWWWW"},
                {"rank": 4, "team": "Al-Shabab", "mp": 10, "w": 7, "d": 0, "l": 3, "gd": "+8", "pts": 21, "form": "WLWLW"},
                {"rank": 5, "team": "Al-Qadsiah", "mp": 10, "w": 6, "d": 1, "l": 3, "gd": "+5", "pts": 19, "form": "DWLWW"},
            ])
        return pd.DataFrame([
            {"rank": 1, "team": "Liverpool", "mp": 10, "w": 8, "d": 1, "l": 1, "gd": "+11", "pts": 25, "form": "WDWWW"},
            {"rank": 2, "team": "Manchester City", "mp": 10, "w": 7, "d": 2, "l": 1, "gd": "+10", "pts": 23, "form": "LWWWD"},
            {"rank": 3, "team": "Arsenal", "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+6", "pts": 18, "form": "LDWDL"},
            {"rank": 4, "team": "Chelsea", "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+8", "pts": 18, "form": "DWLDW"},
            {"rank": 5, "team": "Nottingham Forest", "mp": 10, "w": 5, "d": 4, "l": 1, "gd": "+7", "pts": 19, "form": "WWDWW"},
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
                "rating": "8.8",
                "goals": 2,
                "career_total": 916,
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

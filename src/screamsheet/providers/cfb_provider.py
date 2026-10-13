"""College Football Data Provider using ESPN API."""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

from ..base import DataProvider
from .parsers.nfl_parsers import extract_box_score, extract_game_summary

logger = logging.getLogger(__name__)


class CFBDataProvider(DataProvider):
    """Data provider for College Football using the ESPN API.

    Provides access to:
    - Game scores (Top 25 rankings, conference matchups, and favorite teams)
    - AP Top 25 rankings / conference standings
    - Box scores (linescore, team comparison, and top performers)
    - Game recaps and LLM summaries
    """

    def __init__(self, **config):
        super().__init__(**config)
        self.base_url = "http://site.api.espn.com/apis/site/v2/sports/football/college-football"
        self.standings_url = "http://site.api.espn.com/apis/v2/sports/football/college-football/standings"
        self.rankings_url = "http://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"
        self._teams_cache: Optional[Dict[int, str]] = None

    def _get_team_name_lookup(self) -> Dict[int, str]:
        """Get a lookup dictionary of team ID to team name."""
        if self._teams_cache is not None:
            return self._teams_cache

        team_name_lookup: Dict[int, str] = {}
        try:
            # First check local database if populated
            from ..db import sport_lookup_by_id
            # If not in DB, query ESPN
            url = f"{self.base_url}/teams?limit=500"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            teams_list = data.get("sports", [])[0].get("leagues", [])[0].get("teams", [])
            for entry in teams_list:
                t = entry.get("team", {})
                tid = int(t.get("id", 0))
                disp = t.get("displayName")
                if tid and disp:
                    team_name_lookup[tid] = disp
        except Exception as e:
            logger.warning("Error getting CFB team names lookup: %s", e)

        self._teams_cache = team_name_lookup
        return team_name_lookup

    def _find_recent_game_date(self, start_date: datetime) -> Optional[datetime]:
        """Look back up to 7 days from start_date to find a day with completed games."""
        for days_back in range(1, 8):
            candidate = start_date - timedelta(days=days_back)
            date_str = candidate.strftime("%Y%m%d")
            url = f"{self.base_url}/scoreboard?dates={date_str}&groups=80&limit=10"
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    events = res.json().get("events", [])
                    has_completed = any(
                        e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("name") == "STATUS_FINAL"
                        for e in events
                    )
                    if has_completed:
                        return candidate
            except Exception:
                continue
        return None

    def get_game_scores(
        self,
        date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        max_games: int = 18,
    ) -> list:
        """Get College Football game scores for a date.

        Prioritizes:
        1. Games involving subscriber's favorite teams
        2. Top 25 vs Top 25 ranked matchups
        3. Top 25 games
        4. Other completed FBS games

        Args:
            date: Target date for scores (defaults to yesterday)
            favorite_teams: Optional list of (team_id, team_name) tuples to prioritize
            max_games: Maximum number of games to display on the 3-column scoreboard

        Returns:
            List of game score dicts formatted for GameScoresSection
        """
        target_date = date or (datetime.now() - timedelta(days=1))
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.base_url}/scoreboard?dates={date_str}&groups=80&limit=100"

        raw_events = []
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            raw_events = data.get("events", [])
        except Exception as e:
            logger.warning("Error fetching CFB scoreboard for %s: %s", date_str, e)

        # If 0 events found on this date, check if looking back finds recent games
        if not raw_events and date is None:
            recent_date = self._find_recent_game_date(target_date)
            if recent_date:
                recent_str = recent_date.strftime("%Y%m%d")
                try:
                    res = requests.get(f"{self.base_url}/scoreboard?dates={recent_str}&groups=80&limit=100", timeout=10)
                    if res.status_code == 200:
                        raw_events = res.json().get("events", [])
                except Exception:
                    pass

        fav_ids = set()
        fav_names = set()
        if favorite_teams:
            for tid, tname in favorite_teams:
                if tid:
                    fav_ids.add(int(tid))
                if tname:
                    fav_names.add(tname.lower())

        games = []
        for event in raw_events:
            comps = event.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            status_name = comp.get("status", {}).get("type", {}).get("name", "")
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

            try:
                home_id = int(home_comp.get("team", {}).get("id", 0))
            except (ValueError, TypeError):
                home_id = 0
            try:
                away_id = int(away_comp.get("team", {}).get("id", 0))
            except (ValueError, TypeError):
                away_id = 0

            home_team_full = home_comp.get("team", {}).get("displayName", "Home")
            away_team_full = away_comp.get("team", {}).get("displayName", "Away")
            home_short = home_comp.get("team", {}).get("shortDisplayName", home_team_full)
            away_short = away_comp.get("team", {}).get("shortDisplayName", away_team_full)

            # Curated ranks (AP / CFP)
            h_rank = home_comp.get("curatedRank", {}).get("current", 99)
            a_rank = away_comp.get("curatedRank", {}).get("current", 99)

            def format_name_with_rank(name: str, rank: int) -> str:
                if 1 <= rank <= 25:
                    return f"({rank}) {name}"
                return name

            away_display = format_name_with_rank(away_short, a_rank)
            home_display = format_name_with_rank(home_short, h_rank)

            def parse_score(val):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None

            away_score = parse_score(away_comp.get("score"))
            home_score = parse_score(home_comp.get("score"))

            # Calculate priority
            is_fav = (
                home_id in fav_ids
                or away_id in fav_ids
                or any(f in home_team_full.lower() for f in fav_names)
                or any(f in away_team_full.lower() for f in fav_names)
            )

            is_final = status_name == "STATUS_FINAL"
            ranked_both = (1 <= h_rank <= 25) and (1 <= a_rank <= 25)
            ranked_either = (1 <= h_rank <= 25) or (1 <= a_rank <= 25)

            # Sort priority key: 0 = favorite, 1 = ranked vs ranked, 2 = ranked, 3 = other
            if is_fav:
                prio = 0
            elif ranked_both:
                prio = 1
            elif ranked_either:
                prio = 2
            else:
                prio = 3

            games.append({
                "gameId": str(event.get("id", "")),
                "game_id": str(event.get("id", "")),
                "away_team": away_display,
                "away_team_full": away_team_full,
                "away_team_id": away_id,
                "away_score": away_score,
                "away_rank": a_rank,
                "home_team": home_display,
                "home_team_full": home_team_full,
                "home_team_id": home_id,
                "home_score": home_score,
                "home_rank": h_rank,
                "status": status_name,
                "is_final": is_final,
                "priority": prio,
            })

        # Filter to completed games if available
        completed_games = [g for g in games if g["is_final"] and g["away_score"] is not None and g["home_score"] is not None]
        active_pool = completed_games if completed_games else games

        # Sort by priority, then by top rank
        active_pool.sort(key=lambda g: (g["priority"], min(g["away_rank"], g["home_rank"])))

        return active_pool[:max_games]

    def get_standings(self, date: Optional[datetime] = None) -> pd.DataFrame:
        """Get College Football rankings (AP Top 25) as a pandas DataFrame.

        Returns DataFrame with columns:
            ['rank', 'team', 'record', 'previous', 'points']
        """
        try:
            res = requests.get(self.rankings_url, timeout=10)
            res.raise_for_status()
            data = res.json()
            rankings = data.get("rankings", [])
            # Find AP Top 25 or first available poll
            target_poll = None
            for p in rankings:
                if p.get("name") == "AP Top 25":
                    target_poll = p
                    break
            if not target_poll and rankings:
                target_poll = rankings[0]

            if target_poll and "ranks" in target_poll:
                rows = []
                for r in target_poll["ranks"][:25]:
                    t = r.get("team", {})
                    team_name = t.get("nickname") or t.get("name") or t.get("location", "")
                    rows.append({
                        "rank": int(r.get("current", 0)),
                        "team": team_name,
                        "record": str(r.get("recordSummary", "")),
                        "previous": str(r.get("previous", "-")),
                        "points": float(r.get("points", 0)),
                    })
                df = pd.DataFrame(rows)
                if not df.empty:
                    return df.sort_values(by="rank").reset_index(drop=True)
        except Exception as e:
            logger.warning("Error fetching CFB AP rankings: %s", e)

        # Fallback to conference standings
        return self._get_fallback_standings()

    def _get_fallback_standings(self) -> pd.DataFrame:
        """Fallback to basic conference standings if AP poll fails."""
        try:
            res = requests.get(self.standings_url, timeout=10)
            res.raise_for_status()
            data = res.json()
            rows = []
            for conf in data.get("children", []):
                conf_name = conf.get("name", "")
                entries = conf.get("standings", {}).get("entries", [])
                for entry in entries[:5]:
                    tm = entry.get("team", {})
                    name = tm.get("displayName", "")
                    stats = {s.get("name"): s.get("displayValue") for s in entry.get("stats", [])}
                    overall = stats.get("overall", "")
                    rows.append({
                        "conference": conf_name,
                        "team": name,
                        "record": overall,
                        "winPercent": float(stats.get("leagueWinPercent", 0.0) or 0.0),
                    })
            if rows:
                return pd.DataFrame(rows)
        except Exception as e:
            logger.warning("Error fetching fallback CFB standings: %s", e)

        return pd.DataFrame()

    def _find_event_id(self, team_id: int, date: Optional[datetime] = None) -> Optional[str]:
        """Find the ESPN event ID for a given team on a date."""
        target_date = date or (datetime.now() - timedelta(days=1))
        date_str = target_date.strftime("%Y%m%d")

        lookup = self._get_team_name_lookup()
        team_name = lookup.get(team_id, "").lower()

        urls_to_try = [
            f"{self.base_url}/scoreboard?dates={date_str}&groups=80&limit=100",
            f"{self.base_url}/scoreboard?dates={date_str}&limit=100",
        ]

        for url in urls_to_try:
            try:
                res = requests.get(url, timeout=10)
                res.raise_for_status()
                for event in res.json().get("events", []):
                    comp = event.get("competitions", [{}])[0]
                    for c in comp.get("competitors", []):
                        t = c.get("team", {})
                        cid = int(t.get("id", 0))
                        cname = t.get("displayName", "").lower()
                        if cid == team_id or (team_name and (team_name in cname or cname in team_name)):
                            return str(event.get("id"))
            except Exception as e:
                logger.debug("Error checking scoreboard for event ID: %s", e)

        return None

    def has_game(self, team_id: int, date: Optional[datetime] = None) -> bool:
        """Check if team played a completed game on date."""
        event_id = self._find_event_id(team_id, date)
        if not event_id:
            return False

        try:
            url = f"{self.base_url}/summary?event={event_id}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                header = res.json().get("header", {})
                status_name = header.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("name", "")
                return status_name in ("STATUS_FINAL", "FINAL", "OFF")
        except Exception:
            pass

        return True

    def get_all_teams_for_date(self, date: Optional[datetime] = None) -> List[Tuple[int, str]]:
        """Get all teams that played completed games on date."""
        target_date = date or (datetime.now() - timedelta(days=1))
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.base_url}/scoreboard?dates={date_str}&groups=80&limit=100"

        teams: List[Tuple[int, str]] = []
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            for event in res.json().get("events", []):
                comp = event.get("competitions", [{}])[0]
                status_name = comp.get("status", {}).get("type", {}).get("name", "")
                if status_name != "STATUS_FINAL":
                    continue
                for c in comp.get("competitors", []):
                    t = c.get("team", {})
                    tid = int(t.get("id", 0))
                    name = t.get("displayName", "")
                    if tid and name:
                        teams.append((tid, name))
        except Exception as e:
            logger.warning("Error getting teams for date %s: %s", date_str, e)

        return list(set(teams))

    def get_box_score(self, team_id: int, date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Get structured box score for a College Football game involving team_id."""
        event_id = self._find_event_id(team_id, date)
        if not event_id:
            # Fall back to first available game on that date
            all_teams = self.get_all_teams_for_date(date)
            if all_teams:
                event_id = self._find_event_id(all_teams[0][0], date)

        if not event_id:
            return None

        url = f"{self.base_url}/summary?event={event_id}"
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            return extract_box_score(data, team_id=team_id)
        except Exception as e:
            logger.warning("Error fetching CFB box score for event %s: %s", event_id, e)
            return None

    def get_game_summary(
        self,
        team_id: int,
        date: Optional[datetime] = None,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
    ) -> Optional[str]:
        """Get LLM-generated game summary for a specific team on date."""
        from ..llm.summary import CFBGameSummarizer

        event_id = self._find_event_id(team_id, date)
        if not event_id:
            all_teams = self.get_all_teams_for_date(date)
            if all_teams:
                event_id = self._find_event_id(all_teams[0][0], date)

        if not event_id:
            return None

        url = f"{self.base_url}/summary?event={event_id}"
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            extracted = extract_game_summary(data, favorite_team_id=team_id)

            away_team = extracted.get("away_team", "")
            home_team = extracted.get("home_team", "")
            away_score = extracted.get("away_score", 0)
            home_score = extracted.get("home_score", 0)

            drives_list = extracted.get("scoring_drives", [])
            drives_formatted = "\n".join(
                [f"- Q{d.get('quarter', '')} ({d.get('clock', '')}): {d.get('team', '')} - {d.get('description', '')}" for d in drives_list]
            ) if drives_list else "None recorded."

            totals_lines = []
            for tm, stats in extracted.get("team_totals", {}).items():
                totals_lines.append(
                    f"{tm}: Total Yards {stats.get('total_yards', '')}, Pass {stats.get('passing_yards', '')}, Rush {stats.get('rushing_yards', '')}, Turnovers {stats.get('turnovers', '')}"
                )
            totals_formatted = "\n".join(totals_lines) if totals_lines else "None recorded."

            leaders_lines = []
            for cat in ["passing", "rushing", "receiving"]:
                for l in extracted.get("leaders", {}).get(cat, []):
                    leaders_lines.append(f"{cat.capitalize()}: {l.get('name', '')} ({l.get('team', '')}) - {l.get('display_stat', '')}")
            top_performers_formatted = "\n".join(leaders_lines) if leaders_lines else "None recorded."

            llm_payload = {
                "away_team": away_team,
                "away_score": away_score,
                "home_team": home_team,
                "home_score": home_score,
                "scoring_drives": drives_formatted,
                "team_totals": totals_formatted,
                "top_performers": top_performers_formatted,
            }

            # Try generating summary with Gemini
            gemini_key = os.getenv("GEMINI_API_KEY")
            grok_key = os.getenv("GROK_API_KEY")
            if gemini_key or grok_key:
                try:
                    summarizer = CFBGameSummarizer(gemini_api_key=gemini_key, grok_api_key=grok_key)
                    summary = summarizer.generate_summary(llm_choice="gemini" if gemini_key else "grok", data=llm_payload)
                    if summary and summary.strip():
                        return summary
                except Exception as e:
                    logger.warning("LLM generation error: %s, falling back to article", e)

            # Fallback to ESPN written article story
            article = data.get("article", {})
            story = article.get("story", "")
            headline = article.get("headline", "")
            if story:
                # Strip basic HTML tags
                import re
                clean_story = re.sub(r"<[^>]+>", "", story)
                paragraphs = [p.strip() for p in clean_story.split("\n") if p.strip()]
                lead = "\n\n".join(paragraphs[:3])
                if headline:
                    return f"<b>{headline}</b>\n\n{lead}"
                return lead

            return None
        except Exception as e:
            logger.warning("Error generating CFB summary for event %s: %s", event_id, e)
            return None

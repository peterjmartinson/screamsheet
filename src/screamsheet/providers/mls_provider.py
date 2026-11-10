"""MLS data provider for fetching Major League Soccer game data via ESPN API."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..base import SportsDataProvider

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT: int = 15
DEFAULT_RETRY_ATTEMPTS: int = 3
DEFAULT_RETRY_MIN_WAIT: float = 1.0
DEFAULT_RETRY_MAX_WAIT: float = 10.0


def _espn_api_retry():
    """Build a standard tenacity retry decorator for ESPN API calls."""
    return retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1.0, min=DEFAULT_RETRY_MIN_WAIT, max=DEFAULT_RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def _extract_mls_series_status(
    comp: Dict[str, Any],
    away_abbrev: str,
    home_abbrev: str,
    away_name: str = "",
    home_name: str = "",
) -> Optional[Dict[str, Any]]:
    """Extract series status dict for an MLS playoff series match (e.g. Round One best-of-3)."""
    series = comp.get("series")
    notes = [n.get("text", "") for n in comp.get("notes", [])]
    if not series and not notes:
        return None

    total_competitions = series.get("totalCompetitions", 3) if series else 3
    needed_to_win = (int(total_competitions) // 2) + 1

    pattern_lead = re.compile(r"(\b[A-Za-z0-9]+)\s+(?:leads|wins?)\s+series\s+(\d+)-(\d+)", re.IGNORECASE)
    pattern_tied = re.compile(r"Series\s+tied\s+(\d+)-(\d+)", re.IGNORECASE)

    for note in notes:
        m_tied = pattern_tied.search(note)
        if m_tied:
            w1 = int(m_tied.group(1))
            w2 = int(m_tied.group(2))
            return {
                "top_seed_abbrev": away_abbrev,
                "top_seed_wins": w1,
                "bottom_seed_abbrev": home_abbrev,
                "bottom_seed_wins": w2,
                "needed_to_win": needed_to_win,
            }
        m_lead = pattern_lead.search(note)
        if m_lead:
            team_str = m_lead.group(1).upper()
            w = int(m_lead.group(2))
            l = int(m_lead.group(3))
            if team_str == away_abbrev.upper() or (away_name and team_str in away_name.upper()):
                return {
                    "top_seed_abbrev": away_abbrev,
                    "top_seed_wins": w,
                    "bottom_seed_abbrev": home_abbrev,
                    "bottom_seed_wins": l,
                    "needed_to_win": needed_to_win,
                }
            else:
                return {
                    "top_seed_abbrev": home_abbrev,
                    "top_seed_wins": w,
                    "bottom_seed_abbrev": away_abbrev,
                    "bottom_seed_wins": l,
                    "needed_to_win": needed_to_win,
                }
    return None


@_espn_api_retry()
def _call_espn_endpoint(
    url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fetch JSON from an ESPN endpoint with retries and timeout."""
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


class MLSDataProvider(SportsDataProvider):
    """Data provider for Major League Soccer using ESPN's public soccer API."""

    SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
    STANDINGS_URL: str = "https://site.api.espn.com/apis/v2/sports/soccer/usa.1/standings"
    SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/summary"

    COMPLETED_STATUSES = {"Final", "FT", "AET", "PEN", "Full Time"}

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self._request_timeout: int = int(config.get("request_timeout", DEFAULT_REQUEST_TIMEOUT))
        self._scores_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._summary_cache: Dict[str, Dict[str, Any]] = {}
        self._standings_cache: Optional[pd.DataFrame] = None

    def _safe_int(self, val: Any, default: int = 0) -> int:
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    # ------------------------------------------------------------------
    # DataProvider Interface
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """Fetch all MLS matches for the target date."""
        date_str = date.strftime("%Y%m%d")
        if date_str in self._scores_cache:
            return self._scores_cache[date_str]

        url = f"{self.SCOREBOARD_URL}?dates={date_str}"
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout)
        except Exception:
            logger.exception("Failed to fetch MLS scoreboard for %s", date_str)
            return []

        events = data.get("events", [])
        games: List[Dict[str, Any]] = []

        for e in events:
            comps = e.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            status_desc = comp.get("status", {}).get("type", {}).get("description", "Scheduled")
            status_short = comp.get("status", {}).get("type", {}).get("shortDetail", status_desc)

            competitors = comp.get("competitors", [])
            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_comp or not away_comp:
                continue

            h_team = home_comp.get("team", {})
            a_team = away_comp.get("team", {})

            h_score = self._safe_int(home_comp.get("score", 0))
            a_score = self._safe_int(away_comp.get("score", 0))

            h_rec = (home_comp.get("records") or [{}])[0].get("summary", "")
            a_rec = (away_comp.get("records") or [{}])[0].get("summary", "")

            home_abbrev = h_team.get("abbreviation") or ""
            away_abbrev = a_team.get("abbreviation") or ""

            series_status = _extract_mls_series_status(
                comp,
                away_abbrev=away_abbrev,
                home_abbrev=home_abbrev,
                away_name=a_team.get("displayName", ""),
                home_name=h_team.get("displayName", ""),
            )

            # In playoff series, use shortDisplayName to fit compact table columns
            if series_status:
                home_display = h_team.get("shortDisplayName") or h_team.get("displayName", "Home")
                away_display = a_team.get("shortDisplayName") or a_team.get("displayName", "Away")
            else:
                home_display = h_team.get("displayName", "Home")
                away_display = a_team.get("displayName", "Away")

            games.append({
                "game_id": str(e.get("id")),
                "date": date_str,
                "home_id": self._safe_int(h_team.get("id")),
                "home_team": home_display,
                "home_abbrev": home_abbrev,
                "home_score": h_score,
                "home_record": h_rec,
                "away_id": self._safe_int(a_team.get("id")),
                "away_team": away_display,
                "away_abbrev": away_abbrev,
                "away_score": a_score,
                "away_record": a_rec,
                "status": status_desc,
                "status_short": status_short,
                "series_status": series_status,
                "headline": comp.get("headlines", [{}])[0].get("shortLinkText", "") if comp.get("headlines") else "",
            })

        self._scores_cache[date_str] = games
        return games

    def get_standings(self) -> pd.DataFrame:
        """Fetch MLS standings broken down by Eastern and Western conferences."""
        if self._standings_cache is not None:
            return self._standings_cache

        try:
            data = _call_espn_endpoint(self.STANDINGS_URL, timeout=self._request_timeout)
        except Exception:
            logger.exception("Failed to fetch MLS standings from ESPN")
            return pd.DataFrame()

        children = data.get("children", [])
        rows: List[Dict[str, Any]] = []

        for child in children:
            conf_raw = child.get("name", "")
            conf = "East" if "East" in conf_raw else "West" if "West" in conf_raw else conf_raw
            for entry in child.get("standings", {}).get("entries", []):
                t = entry.get("team", {})
                stats = {s.get("name"): s for s in entry.get("stats", [])}

                rank = self._safe_int(stats.get("rank", {}).get("value", 0))
                pts = self._safe_int(stats.get("points", {}).get("value", 0))
                mp = self._safe_int(stats.get("gamesPlayed", {}).get("value", 0))
                w = self._safe_int(stats.get("wins", {}).get("value", 0))
                d = self._safe_int(stats.get("ties", {}).get("value", 0))
                l = self._safe_int(stats.get("losses", {}).get("value", 0))
                gd_val = self._safe_int(stats.get("pointDifferential", {}).get("value", 0))
                gd_str = f"+{gd_val}" if gd_val > 0 else str(gd_val)

                rows.append({
                    "conference": conf,
                    "rank": rank,
                    "team": t.get("displayName", ""),
                    "team_id": self._safe_int(t.get("id")),
                    "mp": mp,
                    "w": w,
                    "d": d,
                    "l": l,
                    "gd": gd_str,
                    "pts": pts,
                    "overall": f"{w}-{d}-{l}",
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by=["conference", "rank", "pts"], ascending=[True, True, False])
        self._standings_cache = df
        return df

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Check if team_id played on date."""
        scores = self.get_game_scores(date)
        return any(
            g.get("home_id") == team_id or g.get("away_id") == team_id
            for g in scores
        )

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (team_id, team_name) for all teams playing on date."""
        scores = self.get_game_scores(date)
        teams: List[Tuple[int, str]] = []
        for g in scores:
            if g.get("home_id") and g.get("home_team"):
                teams.append((int(g["home_id"]), str(g["home_team"])))
            if g.get("away_id") and g.get("away_team"):
                teams.append((int(g["away_id"]), str(g["away_team"])))
        return teams

    def get_game_id(self, team_id: int, date: datetime) -> Optional[str]:
        """Find the event ID for team_id on date."""
        scores = self.get_game_scores(date)
        for g in scores:
            if g.get("home_id") == team_id or g.get("away_id") == team_id:
                return str(g.get("game_id"))
        return None

    def get_match_of_the_day(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Select the highest excitement MLS game on date."""
        scores = self.get_game_scores(date)
        if not scores:
            return None

        def _excitement(g: Dict[str, Any]) -> float:
            tot = g.get("home_score", 0) + g.get("away_score", 0)
            diff = abs(g.get("home_score", 0) - g.get("away_score", 0))
            score = tot * 10.0 - diff * 3.0
            # Affinity team boost: Inter Miami (20232) or Philadelphia Union (10739)
            if 20232 in (g.get("home_id"), g.get("away_id")):
                score += 30.0
            if 10739 in (g.get("home_id"), g.get("away_id")):
                score += 25.0
            return score

        return max(scores, key=_excitement)

    def get_box_score(self, event_id: Any, date: datetime) -> Optional[Dict[str, Any]]:
        """Fetch deep match details including stats, events, and rosters."""
        if not event_id or str(event_id).strip() in ("0", "", "None"):
            return None

        eid_str = str(event_id)
        # If event_id looks like a team_id, resolve to actual event_id on date
        if len(eid_str) < 6:
            real_eid = self.get_game_id(self._safe_int(eid_str), date)
            if real_eid:
                eid_str = str(real_eid)

        if eid_str in self._summary_cache:
            return self._summary_cache[eid_str]

        url = f"{self.SUMMARY_URL}?event={eid_str}"
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout)
        except Exception:
            logger.exception("Failed to fetch MLS summary for event %s", eid_str)
            return None

        header = data.get("header", {})
        comp = (header.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])

        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

        h_team = home_comp.get("team", {})
        a_team = away_comp.get("team", {})

        h_score = self._safe_int(home_comp.get("score", 0))
        a_score = self._safe_int(away_comp.get("score", 0))

        # Venue & game info
        game_info = data.get("gameInfo", {})
        venue = game_info.get("venue", {}).get("fullName", "MLS Stadium")
        city = game_info.get("venue", {}).get("address", {}).get("city", "")
        att = game_info.get("attendance")
        venue_str = f"{venue}, {city}" if city else venue
        if att:
            venue_str += f" (Att: {att:,})"

        # Key events (Goals, Red cards, Penalties)
        key_events: List[Dict[str, Any]] = []
        for ev in data.get("keyEvents", []):
            ev_type = ev.get("type", {}).get("text", "")
            clock = ev.get("clock", {}).get("displayValue", "")
            text_desc = ev.get("text", "")
            if not text_desc:
                continue

            # Check if event is a goal, penalty, red/yellow card
            ev_upper = ev_type.upper()
            if any(k in ev_upper for k in ("GOAL", "PENALTY", "CARD", "RED", "YELLOW")):
                key_events.append({
                    "minute": clock or "—",
                    "type": ev_type,
                    "text": text_desc,
                })

        # Team stats comparison
        boxscore_teams = data.get("boxscore", {}).get("teams", [])
        h_stats_raw = next((t for t in boxscore_teams if str(t.get("team", {}).get("id")) == str(h_team.get("id"))), {})
        a_stats_raw = next((t for t in boxscore_teams if str(t.get("team", {}).get("id")) == str(a_team.get("id"))), {})

        h_stat_dict = {s.get("name"): s.get("displayValue") for s in h_stats_raw.get("statistics", [])}
        a_stat_dict = {s.get("name"): s.get("displayValue") for s in a_stats_raw.get("statistics", [])}

        team_metrics = [
            {"label": "Possession", "home": f"{h_stat_dict.get('possessionPct', '50')}%", "away": f"{a_stat_dict.get('possessionPct', '50')}%"},
            {"label": "Total Shots", "home": str(h_stat_dict.get("totalShots", "0")), "away": str(a_stat_dict.get("totalShots", "0"))},
            {"label": "Shots on Target", "home": str(h_stat_dict.get("shotsOnTarget", "0")), "away": str(a_stat_dict.get("shotsOnTarget", "0"))},
            {"label": "Corner Kicks", "home": str(h_stat_dict.get("wonCorners", "0")), "away": str(a_stat_dict.get("wonCorners", "0"))},
            {"label": "Fouls", "home": str(h_stat_dict.get("foulsCommitted", "0")), "away": str(a_stat_dict.get("foulsCommitted", "0"))},
            {"label": "Yellow Cards", "home": str(h_stat_dict.get("yellowCards", "0")), "away": str(a_stat_dict.get("yellowCards", "0"))},
            {"label": "Saves", "home": str(h_stat_dict.get("saves", "0")), "away": str(a_stat_dict.get("saves", "0"))},
        ]

        # Starters from rosters
        h_starters: List[Dict[str, str]] = []
        a_starters: List[Dict[str, str]] = []
        for r in data.get("rosters", []):
            is_home = str(r.get("team", {}).get("id")) == str(h_team.get("id"))
            target_list = h_starters if is_home else a_starters
            for p in r.get("roster", []):
                if p.get("starter", False):
                    target_list.append({
                        "number": str(p.get("jersey", "")),
                        "name": str(p.get("athlete", {}).get("displayName", "")),
                        "pos": str(p.get("position", {}).get("abbreviation", "")),
                    })

        result = {
            "event_id": eid_str,
            "venue": venue_str,
            "status": comp.get("status", {}).get("type", {}).get("description", "Final"),
            "home_team": {
                "id": self._safe_int(h_team.get("id")),
                "name": h_team.get("displayName", "Home"),
                "score": h_score,
            },
            "away_team": {
                "id": self._safe_int(a_team.get("id")),
                "name": a_team.get("displayName", "Away"),
                "score": a_score,
            },
            "key_events": key_events,
            "team_metrics": team_metrics,
            "starters": {"home": h_starters, "away": a_starters},
        }

        self._summary_cache[eid_str] = result
        return result

    def get_game_summary(
        self,
        event_id: Any,
        date: datetime,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
        **kwargs: Any,
    ) -> Optional[str]:
        """Generate a newspaper-style game narrative using LLM or fallback."""
        box = self.get_box_score(event_id, date)
        if not box:
            return "No match details available."

        h_name = box["home_team"]["name"]
        a_name = box["away_team"]["name"]
        h_score = box["home_team"]["score"]
        a_score = box["away_team"]["score"]

        # Check if LLM is available
        import os
        gemini_key = os.getenv("GEMINI_API_KEY")
        grok_key = os.getenv("GROK_API_KEY")

        if gemini_key or grok_key:
            try:
                from ..llm.summarizers import MLSGameSummarizer

                events_str = "\n".join(
                    f"- {e.get('minute')}: {e.get('type')} — {e.get('text')}"
                    for e in box.get("key_events", [])
                ) or "- No major goals or cards recorded."

                stats_str = "\n".join(
                    f"- {m.get('label')}: {h_name} {m.get('home')} vs {m.get('away')} {a_name}"
                    for m in box.get("team_metrics", [])
                ) or "- Possession: 50% vs 50%"

                extracted_info = {
                    "home_team": h_name,
                    "away_team": a_name,
                    "home_score": str(h_score),
                    "away_score": str(a_score),
                    "venue": box.get("venue", "MLS Stadium"),
                    "key_events": events_str,
                    "team_metrics": stats_str,
                }

                summarizer = MLSGameSummarizer()
                summary = summarizer.generate_summary(extracted_info)
                if summary and str(summary).strip():
                    return str(summary)
            except Exception:
                logger.exception("MLSGameSummarizer failed; falling back to template")

        # Fallback template
        return self._build_fallback_narrative(box)

    def _build_fallback_narrative(self, box: Dict[str, Any]) -> str:
        h_name = box["home_team"]["name"]
        a_name = box["away_team"]["name"]
        h_score = box["home_team"]["score"]
        a_score = box["away_team"]["score"]
        venue = box.get("venue", "MLS Stadium")

        if h_score > a_score:
            outcome = f"{h_name} picked up a decisive {h_score}–{a_score} victory over {a_name}"
            winner = h_name
        elif a_score > h_score:
            outcome = f"{a_name} earned an impressive {a_score}–{h_score} road win against {h_name}"
            winner = a_name
        else:
            outcome = f"{h_name} and {a_name} battled to a hard-fought {h_score}–{a_score} draw"
            winner = None

        events = box.get("key_events", [])
        goal_events = [e for e in events if "GOAL" in e.get("type", "").upper() or "PENALTY" in e.get("type", "").upper()]
        event_lines = ""
        if goal_events:
            event_lines = " Key scoring plays included " + "; ".join(e.get("text", "") for e in goal_events[:3]) + "."

        para1 = (
            f"In an electric Major League Soccer clash at {venue}, {outcome}. "
            f"Both sides displayed sharp attacking intent from kickoff, looking to control tempo through the midfield.{event_lines}"
        )
        para2 = (
            f"The second half brought intense action on both ends of the pitch as defensive adjustments were put to the test. "
            f"Goalkeepers and backlines were forced into crucial stops under sustained pressure during high-leverage minutes."
        )
        para3 = (
            f"With the final whistle, {f'{winner} banked three crucial points in the conference standings.' if winner else 'both teams walked away sharing the points in the regular season race.'} "
            f"Supporters were treated to an entertaining showcase of MLS competition."
        )
        return f"{para1}\n\n{para2}\n\n{para3}"

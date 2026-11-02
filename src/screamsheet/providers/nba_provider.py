"""NBA data provider for fetching NBA game data via ESPN API."""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from ..base import SportsDataProvider

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT: int = 15
DEFAULT_RETRY_ATTEMPTS: int = 3
DEFAULT_RETRY_MIN_WAIT: float = 1.0
DEFAULT_RETRY_MAX_WAIT: float = 10.0

# ---------------------------------------------------------------------------
# Bidirectional NBA API ID <-> ESPN Team ID mapping
# ---------------------------------------------------------------------------
NBA_TO_ESPN_ID: Dict[int, int] = {
    1610612737: 1,   # Atlanta Hawks
    1610612738: 2,   # Boston Celtics
    1610612739: 5,   # Cleveland Cavaliers
    1610612740: 3,   # New Orleans Pelicans
    1610612741: 4,   # Chicago Bulls
    1610612742: 6,   # Dallas Mavericks
    1610612743: 7,   # Denver Nuggets
    1610612744: 9,   # Golden State Warriors
    1610612745: 10,  # Houston Rockets
    1610612746: 12,  # LA Clippers / Los Angeles Clippers
    1610612747: 13,  # Los Angeles Lakers
    1610612748: 14,  # Miami Heat
    1610612749: 15,  # Milwaukee Bucks
    1610612750: 16,  # Minnesota Timberwolves
    1610612751: 17,  # Brooklyn Nets
    1610612752: 18,  # New York Knicks
    1610612753: 19,  # Orlando Magic
    1610612754: 11,  # Indiana Pacers
    1610612755: 20,  # Philadelphia 76ers
    1610612756: 21,  # Phoenix Suns
    1610612757: 22,  # Portland Trail Blazers
    1610612758: 23,  # Sacramento Kings
    1610612759: 24,  # San Antonio Spurs
    1610612760: 25,  # Oklahoma City Thunder
    1610612761: 28,  # Toronto Raptors
    1610612762: 26,  # Utah Jazz
    1610612763: 29,  # Memphis Grizzlies
    1610612764: 27,  # Washington Wizards
    1610612765: 8,   # Detroit Pistons
    1610612766: 30,  # Charlotte Hornets
}

ESPN_TO_NBA_ID: Dict[int, int] = {v: k for k, v in NBA_TO_ESPN_ID.items()}


def _nba_api_retry():
    """Build a standard tenacity retry decorator for NBA API calls."""
    return retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1.0, min=DEFAULT_RETRY_MIN_WAIT, max=DEFAULT_RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@_nba_api_retry()
def _call_espn_endpoint(url: str, timeout: int = DEFAULT_REQUEST_TIMEOUT, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch JSON from an ESPN endpoint with retries and timeout."""
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# Legacy helper stubs for backward-compatibility if referenced elsewhere
def _call_league_game_finder(timeout: int = DEFAULT_REQUEST_TIMEOUT, **kwargs: Any) -> List[pd.DataFrame]:
    return [pd.DataFrame()]


def _call_league_standings(timeout: int = DEFAULT_REQUEST_TIMEOUT, **kwargs: Any) -> List[pd.DataFrame]:
    return [pd.DataFrame()]


def _call_box_score_traditional_v2(timeout: int = DEFAULT_REQUEST_TIMEOUT, **kwargs: Any) -> List[pd.DataFrame]:
    return [pd.DataFrame()]


def _call_play_by_play_v3(timeout: int = DEFAULT_REQUEST_TIMEOUT, **kwargs: Any) -> List[pd.DataFrame]:
    return [pd.DataFrame()]


def _call_play_by_play_v2(timeout: int = DEFAULT_REQUEST_TIMEOUT, **kwargs: Any) -> List[pd.DataFrame]:
    return [pd.DataFrame()]


class NBADataProvider(SportsDataProvider):
    """
    Data provider for NBA using the ESPN API.

    Provides access to:
    - Game scores
    - League standings
    - Box scores
    - Game summaries (via LLM)
    """

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self._request_timeout = int(config.get("request_timeout", DEFAULT_REQUEST_TIMEOUT))
        self._base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        self._standings_url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
        # Cache game_id lookups to avoid redundant API calls within one run.
        # Key: (team_id, date_str)  Value: game_id or None
        self._game_id_cache: Dict[tuple, Optional[str]] = {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Convert *value* to int, returning *default* for NaN/None/non-numeric."""
        try:
            if value is None:
                return default
            f = float(value)
            return default if math.isnan(f) else int(f)
        except (TypeError, ValueError):
            return default

    def _get_game_id(self, team_id: int, date: datetime) -> Optional[str]:
        """Return the GAME_ID for *team_id* on *date*, or None if not found.

        Results are cached per (team_id, date) pair so repeated calls within
        the same run do not trigger extra API requests.
        """
        date_str = date.strftime("%Y-%m-%d")
        cache_key = (team_id, date_str)
        if cache_key in self._game_id_cache:
            logger.debug("game_id cache hit for team %s on %s", team_id, date_str)
            return self._game_id_cache[cache_key]

        target_espn_id = NBA_TO_ESPN_ID.get(team_id, team_id)
        espn_cache_key = (target_espn_id, date_str)
        if espn_cache_key in self._game_id_cache:
            val = self._game_id_cache[espn_cache_key]
            self._game_id_cache[cache_key] = val
            return val

        date_param = date.strftime("%Y%m%d")
        logger.info("Looking up game_id for team_id=%s on %s via ESPN", team_id, date_str)
        try:
            url = f"{self._base_url}/scoreboard"
            data = _call_espn_endpoint(url, timeout=self._request_timeout, params={"dates": date_param})
            events = data.get("events", [])
            for ev in events:
                ev_id = str(ev.get("id", ""))
                for comp in ev.get("competitions", []):
                    for c in comp.get("competitors", []):
                        cid = self._safe_int(c.get("id"))
                        nba_cid = ESPN_TO_NBA_ID.get(cid, cid)
                        self._game_id_cache[(cid, date_str)] = ev_id
                        self._game_id_cache[(nba_cid, date_str)] = ev_id

            found = self._game_id_cache.get(cache_key) or self._game_id_cache.get(espn_cache_key)
            if found:
                logger.info("Found game_id=%s for team_id=%s on %s", found, team_id, date_str)
                self._game_id_cache[cache_key] = found
                return found

            logger.warning("No game found for team_id=%s on %s", team_id, date_str)
            self._game_id_cache[cache_key] = None
            return None
        except Exception:
            logger.exception("Error looking up game_id for team_id=%s on %s", team_id, date_str)
            self._game_id_cache[cache_key] = None
            return None

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """
        Get NBA game scores for a specific date from ESPN.
        """
        date_param = date.strftime("%Y%m%d")
        date_str = date.strftime("%Y-%m-%d")
        url = f"{self._base_url}/scoreboard"
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout, params={"dates": date_param})
            events = data.get("events", [])
            if not events:
                return []

            games: List[Dict[str, Any]] = []
            for ev in events:
                competitions = ev.get("competitions", [])
                if not competitions:
                    continue
                comp = competitions[0]
                status_desc = comp.get("status", {}).get("type", {}).get("description", "Final")
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue

                home_c = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away_c = next((c for c in competitors if c.get("homeAway") == "away"), None)

                if not home_c or not away_c:
                    home_c = competitors[0]
                    away_c = competitors[1]

                home_team = str(home_c.get("team", {}).get("displayName", ""))
                away_team = str(away_c.get("team", {}).get("displayName", ""))
                home_score = self._safe_int(home_c.get("score"))
                away_score = self._safe_int(away_c.get("score"))

                # Populate game_id cache
                ev_id = str(ev.get("id", ""))
                if ev_id:
                    for c in (home_c, away_c):
                        cid = self._safe_int(c.get("id"))
                        nba_cid = ESPN_TO_NBA_ID.get(cid, cid)
                        self._game_id_cache[(cid, date_str)] = ev_id
                        self._game_id_cache[(nba_cid, date_str)] = ev_id

                games.append({
                    "gameDate": date_str,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": status_desc,
                })

            logger.info("Fetched %d NBA game(s) for %s", len(games), date_str)
            return games
        except Exception:
            logger.exception("Error fetching NBA game scores for %s", date_str)
            return []

    def get_standings(self) -> pd.DataFrame:
        """
        Get current NBA league standings from ESPN.

        Returns:
            DataFrame with columns: conference, team, wins, losses, pct,
            conf_record, division_rank — sorted by conference then win pct desc.
        """
        url = self._standings_url
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout)
            children = data.get("children", [])
            if not children:
                return pd.DataFrame()

            rows: List[Dict[str, Any]] = []
            for child in children:
                child_name = str(child.get("name", ""))
                conf = "East" if "East" in child_name else "West" if "West" in child_name else child_name
                for entry in child.get("standings", {}).get("entries", []):
                    team_name = str(entry.get("team", {}).get("displayName", ""))
                    stats_dict = {s.get("name"): s for s in entry.get("stats", [])}
                    wins = self._safe_int(stats_dict.get("wins", {}).get("value", 0))
                    losses = self._safe_int(stats_dict.get("losses", {}).get("value", 0))

                    raw_pct = stats_dict.get("winPercent", {}).get("value")
                    try:
                        pct = round(float(raw_pct), 3) if raw_pct is not None else 0.0
                    except (ValueError, TypeError):
                        pct = 0.0

                    conf_stat = stats_dict.get("vs. Conf.", stats_dict.get("vsConf", {}))
                    conf_record = str(conf_stat.get("displayValue", ""))

                    div_rank = self._safe_int(stats_dict.get("divisionWinPercent", {}).get("rank", 0))

                    rows.append({
                        "conference": conf,
                        "team": team_name,
                        "wins": wins,
                        "losses": losses,
                        "pct": pct,
                        "conf_record": conf_record,
                        "division_rank": div_rank,
                    })

            df = pd.DataFrame(rows)
            if df.empty:
                return df

            return df.sort_values(
                by=["conference", "pct"],
                ascending=[True, False],
            ).reset_index(drop=True)
        except Exception:
            logger.exception("Error fetching NBA standings")
            return pd.DataFrame()

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Return True if *team_id* played on *date*."""
        result = self._get_game_id(team_id, date) is not None
        logger.info("has_game(team_id=%s, date=%s) -> %s", team_id, date.strftime("%Y-%m-%d"), result)
        return result

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (team_id, team_name) for all completed games on date."""
        date_param = date.strftime("%Y%m%d")
        date_str = date.strftime("%Y-%m-%d")
        url = f"{self._base_url}/scoreboard"
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout, params={"dates": date_param})
            events = data.get("events", [])
            teams: List[Tuple[int, str]] = []
            for ev in events:
                for comp in ev.get("competitions", []):
                    for c in comp.get("competitors", []):
                        espn_id = self._safe_int(c.get("id"))
                        nba_id = ESPN_TO_NBA_ID.get(espn_id, espn_id)
                        team_name = str(c.get("team", {}).get("displayName", ""))
                        teams.append((nba_id, team_name))
            return teams
        except Exception:
            logger.exception("Error fetching NBA teams for date %s", date_str)
            return []

    def get_box_score(self, team_id: int, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Get box score for *team_id* on *date*.

        Returns a dict with key ``player_stats``: a list of per-player dicts with
        keys: name, MIN, FG, 3P, FT, REB, AST, STL, BLK, PTS.
        Returns None if the team did not play or data is unavailable.
        """
        game_id = self._get_game_id(team_id, date)
        if not game_id:
            return None

        target_espn_id = NBA_TO_ESPN_ID.get(team_id, team_id)
        url = f"{self._base_url}/summary"
        try:
            data = _call_espn_endpoint(url, timeout=self._request_timeout, params={"event": game_id})
            players_group = data.get("boxscore", {}).get("players", [])

            target_group = None
            for pg in players_group:
                pg_team_id = self._safe_int(pg.get("team", {}).get("id"))
                if pg_team_id == target_espn_id:
                    target_group = pg
                    break

            if not target_group:
                logger.warning(
                    "BoxScore returned no rows for team_id=%s (espn_id=%s) game_id=%s",
                    team_id, target_espn_id, game_id
                )
                return None

            player_stats: List[Dict[str, Any]] = []
            for stat_cat in target_group.get("statistics", []):
                names = stat_cat.get("names", [])
                for ath in stat_cat.get("athletes", []):
                    if ath.get("didNotPlay"):
                        continue
                    stats = ath.get("stats", [])
                    if not stats or stats[0] in ("-", "--", "", "DNP"):
                        continue
                    stats_map = dict(zip(names, stats))
                    player_name = str(ath.get("athlete", {}).get("displayName", ""))
                    if not player_name:
                        continue

                    min_str = str(stats_map.get("MIN", "0"))
                    min_str = min_str.split(".")[0] if "." in min_str else min_str

                    player_stats.append({
                        "name": player_name,
                        "MIN": min_str,
                        "FG": str(stats_map.get("FG", "0-0")),
                        "3P": str(stats_map.get("3PT", stats_map.get("3P", "0-0"))),
                        "FT": str(stats_map.get("FT", "0-0")),
                        "REB": self._safe_int(stats_map.get("REB")),
                        "AST": self._safe_int(stats_map.get("AST")),
                        "STL": self._safe_int(stats_map.get("STL")),
                        "BLK": self._safe_int(stats_map.get("BLK")),
                        "PTS": self._safe_int(stats_map.get("PTS")),
                    })

            player_stats.sort(key=lambda p: p["PTS"], reverse=True)
            logger.info("Box score for game_id=%s: %d players", game_id, len(player_stats))
            return {"player_stats": player_stats}

        except Exception:
            logger.exception("Error fetching NBA box score for team_id=%s game_id=%s", team_id, game_id)
            return None

    def get_game_summary(
        self,
        team_id: int,
        date: datetime,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
    ) -> Optional[str]:
        """
        Generate an LLM game summary for *team_id* on *date*.

        Uses the angry fan-rant persona when ``mad_fan`` is True, ``is_primary_favorite``
        is True, and the featured team lost; otherwise uses the neutral recap.
        """
        import os
        from .extractors import NBAGameExtractor
        from ..llm.summarizers import NBAGameSummarizer, NBAFanRantSummarizer

        game_id = self._get_game_id(team_id, date)
        if not game_id:
            return None

        try:
            extractor = NBAGameExtractor()
            raw = extractor.fetch_raw_data(game_id)
            extracted = extractor.extract_key_info(raw, team_id)
            if isinstance(extracted, str):
                return extracted

            use_rant = False
            if mad_fan and is_primary_favorite:
                home_score = int(extracted["home_score"])
                away_score = int(extracted["away_score"])
                is_home = bool(extracted.get("featured_team_is_home", False))
                team_won = home_score > away_score if is_home else away_score > home_score
                use_rant = not team_won
                result_str = "won" if team_won else "lost"
                logger.info(
                    "Game summary: team_id=%s %s (%s-%s) — using %s",
                    team_id, result_str, extracted["home_score"], extracted["away_score"],
                    "FanRantSummarizer" if use_rant else "GameSummarizer",
                )
            else:
                logger.info(
                    "Game summary: team_id=%s (not primary favorite or mad_fan disabled) — using GameSummarizer",
                    team_id
                )

            gemini_key = os.environ.get("GEMINI_API_KEY")
            grok_key = os.environ.get("GROK_API_KEY")

            summarizer: "NBAGameSummarizer | NBAFanRantSummarizer"
            if use_rant:
                summarizer = NBAFanRantSummarizer(
                    gemini_api_key=gemini_key,
                    grok_api_key=grok_key,
                )
            else:
                summarizer = NBAGameSummarizer(
                    gemini_api_key=gemini_key,
                    grok_api_key=grok_key,
                )

            return summarizer.generate_summary(data=extracted)

        except Exception:
            logger.exception("Error generating NBA game summary for team_id=%s game_id=%s", team_id, game_id)
            return None

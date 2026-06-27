"""worldcup26.ir data provider for FIFA World Cup 2026.

No API key required. Endpoints:
    GET /get/games   → {"games": [...]}
    GET /get/teams   → {"teams": [...]}
    GET /get/groups  → {"groups": [...]}
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Priority teams checked in order for featured-match selection.
# Includes common name variants used by the API.
PRIORITY_TEAM_NAMES: List[str] = ["USA", "United States", "Argentina", "Portugal"]


def _parse_scorers(scorers_str: str, team_name: str) -> List[Dict[str, Any]]:
    """Parse the API's set-literal scorer string into goal-event dicts.

    Input:  '{"H. Kane 12\\'(p)","H. Kane 42\\'"}'
    Output: list of {"type": "Goal", "time": {...}, "team": {...}, ...}
    """
    if not scorers_str or scorers_str.strip() == "null":
        return []
    inner = scorers_str.strip().lstrip("{").rstrip("}")
    # Split on the separator between items: ","
    raw_items = re.split(r'","', inner)
    events: List[Dict[str, Any]] = []
    for item in raw_items:
        item = item.strip().strip('"')
        if not item:
            continue
        m = re.search(r"(\d+(?:\+\d+)?)'", item)
        if not m:
            continue
        minute_str = m.group(1)
        try:
            minute = int(minute_str.split("+")[0])
        except ValueError:
            minute = 0
        player_name = item[: m.start()].strip().rstrip("(").strip()
        detail = "(p)" if "(p)" in item else ""
        events.append(
            {
                "type": "Goal",
                "time": {"elapsed": minute},
                "team": {"name": team_name},
                "player": {"name": player_name},
                "assist": None,
                "detail": detail,
            }
        )
    return events


class WorldCup26Provider(DataProvider):
    BASE_URL = "https://worldcup26.ir"
    COMPLETED_STATUSES = {"FT", "AET", "PEN"}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._games_cache: Optional[List[Dict[str, Any]]] = None
        self._teams_cache: Optional[Dict[str, str]] = None  # id → name_en

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        logger.info("GET %s", url)
        start = time.time()
        try:
            resp = requests.get(url, timeout=10)
            elapsed = time.time() - start
            logger.info("  → HTTP %s (%.2fs)", resp.status_code, elapsed)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.error("Request failed for %s: %s", url, exc)
            return {}

    # ------------------------------------------------------------------
    # Caching loaders (called at most once per provider instance)
    # ------------------------------------------------------------------

    def _load_games(self) -> List[Dict[str, Any]]:
        if self._games_cache is None:
            data = self._get("/get/games")
            self._games_cache = data.get("games") or []
            logger.info("  games cache: %d total fixtures loaded", len(self._games_cache))
        return self._games_cache

    def _load_teams(self) -> Dict[str, str]:
        """Return mapping of team_id → name_en."""
        if self._teams_cache is None:
            data = self._get("/get/teams")
            teams = data.get("teams") or []
            self._teams_cache = {
                str(t.get("id", "")): t.get("name_en") or t.get("name_fa") or "Unknown"
                for t in teams
            }
            logger.info("  teams cache: %d teams loaded", len(self._teams_cache))
        return self._teams_cache

    # ------------------------------------------------------------------
    # Internal date utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_local_date(local_date_str: str) -> datetime:
        """Parse 'MM/DD/YYYY HH:MM' → datetime."""
        return datetime.strptime(local_date_str.strip(), "%m/%d/%Y %H:%M")

    def _games_for_date(self, date: datetime) -> List[Dict[str, Any]]:
        target = date.date()
        result = []
        for g in self._load_games():
            try:
                if self._parse_local_date(g.get("local_date", "")).date() == target:
                    result.append(g)
            except Exception:
                continue
        return result

    # ------------------------------------------------------------------
    # DataProvider contract
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """Return completed World Cup fixtures for *date*.

        Output dict keys (matching renderer expectations):
            fixture_id, home_team, away_team, home_score, away_score,
            home_penalty, away_penalty, status_short, raw
        """
        games = self._games_for_date(date)
        out: List[Dict[str, Any]] = []
        for g in games:
            if str(g.get("finished", "")).upper() != "TRUE":
                continue
            try:
                home_score = int(g.get("home_score", 0))
                away_score = int(g.get("away_score", 0))
            except (ValueError, TypeError):
                home_score = away_score = 0
            out.append(
                {
                    "fixture_id": int(g.get("id", 0)),
                    "home_team": g.get("home_team_name_en") or "",
                    "away_team": g.get("away_team_name_en") or "",
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_penalty": None,  # not in API schema
                    "away_penalty": None,
                    "status_short": "FT",
                    "raw": g,
                }
            )
        logger.info(
            "  %d completed fixtures on %s (of %d total today)",
            len(out), date.strftime("%Y-%m-%d"), len(games),
        )
        for g in out:
            logger.info(
                "    [%s] %s %s – %s %s  (id=%s)",
                g["status_short"], g["away_team"], g["away_score"],
                g["home_score"], g["home_team"], g["fixture_id"],
            )
        return out

    def get_standings(self) -> List[List[Dict[str, Any]]]:
        """Return group standings, each group sorted by pts then gd."""
        teams = self._load_teams()
        data = self._get("/get/groups")
        groups_raw = data.get("groups") or []
        groups: List[List[Dict[str, Any]]] = []
        for grp in groups_raw:
            name: str = grp.get("name") or ""
            raw_teams = grp.get("teams") or []
            sorted_teams = sorted(
                raw_teams,
                key=lambda t: (int(t.get("pts") or 0), int(t.get("gd") or 0)),
                reverse=True,
            )
            entries: List[Dict[str, Any]] = []
            for rank, t in enumerate(sorted_teams, 1):
                team_name = teams.get(str(t.get("team_id", "")), "Unknown")
                entries.append(
                    {
                        "group": f"Group {name}",
                        "rank": rank,
                        "team": {"name": team_name},
                        "points": int(t.get("pts") or 0),
                        "goalsDiff": int(t.get("gd") or 0),
                    }
                )
            groups.append(entries)
        logger.info("  standings: %d groups returned", len(groups))
        return groups

    def get_fixture_events(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Return goal events for the given fixture, parsed from scorer strings."""
        all_games = self._load_games()
        game = next(
            (g for g in all_games if str(g.get("id")) == str(fixture_id)), None
        )
        if not game:
            logger.warning("  fixture %s not found in games cache", fixture_id)
            return []
        events: List[Dict[str, Any]] = []
        events.extend(_parse_scorers(game.get("home_scorers") or "", game.get("home_team_name_en") or ""))
        events.extend(_parse_scorers(game.get("away_scorers") or "", game.get("away_team_name_en") or ""))
        events.sort(key=lambda e: e["time"]["elapsed"])
        logger.info("  fixture %s: %d goal events parsed", fixture_id, len(events))
        return events

    def get_fixture_statistics(self, fixture_id: int) -> Dict[str, Any]:
        """worldcup26.ir has no statistics endpoint — returns empty."""
        return {}

    def get_fixture_lineups(self, fixture_id: int) -> List[Dict[str, Any]]:
        """worldcup26.ir has no lineup endpoint — returns empty."""
        return []

    def get_game_summary(
        self, team_id: int, date: datetime, is_primary_favorite: bool = False
    ) -> Optional[str]:
        """Return a plain-text goal timeline for the featured fixture."""
        games = self.get_game_scores(date)
        featured = next((g for g in games if g.get("fixture_id") == team_id), None)
        if featured is None:
            return None
        away = featured.get("away_team") or ""
        home = featured.get("home_team") or ""
        events = self.get_fixture_events(int(team_id))
        lines: List[str] = [
            f"{away}  {featured.get('away_score', '-')}  –  {featured.get('home_score', '-')}  {home}",
            "",
        ]
        for ev in events:
            elapsed = ev["time"]["elapsed"]
            team_name = ev["team"]["name"]
            player = ev["player"]["name"]
            suffix = " (pen)" if ev.get("detail") else ""
            lines.append(f"  {elapsed}'  {player}{suffix}  ({team_name})")
        if len(lines) == 2:
            lines.append("  No goal events recorded.")
        return "\n".join(lines)

    def has_game(self, team_id: int, date: datetime) -> bool:
        if team_id < 0 or team_id >= len(PRIORITY_TEAM_NAMES):
            return False
        target = PRIORITY_TEAM_NAMES[team_id]
        return any(
            g.get("home_team") == target or g.get("away_team") == target
            for g in self.get_game_scores(date)
        )

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        games = self.get_game_scores(date)
        pairs: List[Tuple[int, str]] = []
        for g in games:
            fid = g.get("fixture_id")
            if fid is None:
                continue
            if g.get("home_team"):
                pairs.append((int(fid), str(g["home_team"])))
            if g.get("away_team"):
                pairs.append((int(fid), str(g["away_team"])))
        return pairs

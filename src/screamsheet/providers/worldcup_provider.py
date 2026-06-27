"""API-Football (FIFA World Cup 2026) data provider."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..base.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Canonical priority team names (checked against home_team / away_team strings)
PRIORITY_TEAM_NAMES: List[str] = ["USA", "United States", "Argentina", "Portugal"]


class FIFAWorldCupProvider(DataProvider):
    DEFAULT_BASE = "https://v3.football.api-sports.io"
    LEAGUE = 1
    SEASON = 2026

    COMPLETED_STATUSES = {"FT", "AET", "PEN"}

    def __init__(
        self,
        api_key: Optional[str] = None,
        timezone: str = "America/New_York",
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            timezone=timezone,
            base_url=base_url or self.DEFAULT_BASE,
            **kwargs,
        )
        # Resolution order: explicit arg → config dict → FIFA_API_KEY env var
        self.api_key: Optional[str] = (
            api_key
            or self.config.get("api_key")
            or self.config.get("FIFA_API_KEY")
            or os.environ.get("FIFA_API_KEY")
        )
        self.base_url: str = base_url or self.config.get("base_url") or self.DEFAULT_BASE
        self.timezone: str = timezone or self.config.get("timezone") or "America/New_York"
        if not self.api_key:
            logger.warning("No FIFA_API_KEY found — all API calls will fail (set FIFA_API_KEY env var or config.yaml worldcup.api_key)")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["x-apisports-key"] = self.api_key
        return headers

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        param_str = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        logger.info("GET %s?%s", url, param_str)
        try:
            resp = requests.get(url, params=params or {}, headers=self._headers(), timeout=10)
            logger.info("  → HTTP %s", resp.status_code)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            errors = data.get("errors")
            if errors:
                # API-Football returns errors as a dict or list inside a 200 response
                for key, msg in (errors.items() if isinstance(errors, dict) else enumerate(errors)):
                    logger.warning("  API error [%s]: %s", key, msg)
            return data
        except Exception as exc:
            logger.error("HTTP request failed for %s: %s", url, exc)
            return {}

    # ------------------------------------------------------------------
    # DataProvider contract
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """Return completed and in-progress World Cup fixtures for *date*.

        Each item is a dict with keys:
            fixture_id, home_team, away_team, home_score, away_score,
            status_short, home_penalty, away_penalty, raw
        """
        d = date.strftime("%Y-%m-%d")
        data = self._get(
            "/fixtures",
            params={"league": self.LEAGUE, "season": self.SEASON, "date": d, "timezone": self.timezone},
        )
        out: List[Dict[str, Any]] = []
        for item in data.get("response") or []:
            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            score = item.get("score", {})
            # Penalty shootout scores live under score.penalty
            penalty = score.get("penalty", {}) or {}
            out.append(
                {
                    "fixture_id": fixture.get("id"),
                    "home_team": teams.get("home", {}).get("name"),
                    "away_team": teams.get("away", {}).get("name"),
                    "home_score": goals.get("home"),
                    "away_score": goals.get("away"),
                    "home_penalty": penalty.get("home"),
                    "away_penalty": penalty.get("away"),
                    "status_short": fixture.get("status", {}).get("short"),
                    "raw": item,
                }
            )
        logger.info("  fixtures returned: %d (date=%s)", len(out), d)
        for g in out:
            logger.info("    [%s] %s %s – %s %s (id=%s)",
                g.get("status_short"), g.get("away_team"), g.get("away_score"),
                g.get("home_score"), g.get("home_team"), g.get("fixture_id"))
        return out

    def get_standings(self) -> List[List[Dict[str, Any]]]:
        """Return standings as a list of groups; each group is a list of team dicts.

        Each team dict contains at minimum: group, rank, team (name), points, goalsDiff.
        """
        data = self._get("/standings", params={"league": self.LEAGUE, "season": self.SEASON})
        resp = data.get("response") or []
        if not resp:
            logger.warning("  standings: empty response")
            return []
        try:
            league = resp[0].get("league", {})
            groups: List[List[Dict[str, Any]]] = league.get("standings", [])
            logger.info("  standings: %d groups returned", len(groups))
            return groups
        except Exception:
            logger.warning("  standings: unexpected response shape")
            return []

    def get_fixture_events(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Return Goal and Card events for the given fixture."""
        data = self._get("/fixtures/events", params={"fixture": fixture_id})
        filtered = [
            e for e in (data.get("response") or [])
            if isinstance(e, dict) and e.get("type") in ("Goal", "Card")
        ]
        logger.info("  fixture %s events: %d goal/card events (of %d total)",
            fixture_id, len(filtered), len(data.get("response") or []))
        return filtered

    def get_fixture_statistics(self, fixture_id: int) -> Dict[str, Dict[str, Any]]:
        """Return per-team summary statistics mapped by team name.

        Keys in each team sub-dict: possession, total_shots, shots_on_target,
        plus any other stat types returned by the API (original key preserved).
        """
        data = self._get("/fixtures/statistics", params={"fixture": fixture_id})
        out: Dict[str, Dict[str, Any]] = {}
        for team_block in data.get("response") or []:
            team_name: str = (team_block.get("team") or {}).get("name") or ""
            stats: Dict[str, Any] = {}
            for s in team_block.get("statistics") or []:
                key: str = s.get("type") or ""
                value = s.get("value")
                if not key or value is None:
                    continue
                kl = key.lower()
                if kl == "ball possession":
                    stats["possession"] = value
                elif "on target" in kl:
                    stats["shots_on_target"] = value
                elif "total shots" in kl or kl == "shots":
                    stats["total_shots"] = value
                else:
                    stats[key] = value
            if team_name:
                out[team_name] = stats
        return out

    def get_fixture_lineups(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Return per-player statistics for both teams in the fixture.

        Each item: {team_name, player_name, position, minutes, goals, assists,
                    shots_total, shots_on_target, yellow_cards, red_cards, saves}
        """
        data = self._get("/fixtures/players", params={"fixture": fixture_id})
        players: List[Dict[str, Any]] = []
        logger.info("  fixture %s lineups: %d teams in response", fixture_id, len(data.get("response") or []))
        for team_block in data.get("response") or []:
            team_name: str = (team_block.get("team") or {}).get("name") or ""
            for p in team_block.get("players") or []:
                info = p.get("player") or {}
                stats_list = p.get("statistics") or [{}]
                s = stats_list[0] if stats_list else {}
                games = s.get("games") or {}
                goals_d = s.get("goals") or {}
                shots_d = s.get("shots") or {}
                cards_d = s.get("cards") or {}
                gk_d = s.get("goalkeeper") or {}
                pos: str = games.get("position") or ""
                players.append(
                    {
                        "team_name": team_name,
                        "player_name": info.get("name") or "",
                        "position": pos,
                        "minutes": games.get("minutes"),
                        "goals": goals_d.get("total") or 0,
                        "assists": goals_d.get("assists") or 0,
                        "shots_total": shots_d.get("total") or 0,
                        "shots_on_target": shots_d.get("on") or 0,
                        "yellow_cards": cards_d.get("yellow") or 0,
                        "red_cards": cards_d.get("red") or 0,
                        "saves": gk_d.get("saves") or 0,
                    }
                )
        return players

    def get_game_summary(self, team_id: int, date: datetime, is_primary_favorite: bool = False) -> Optional[str]:
        """Return a plain-text events narrative for the featured fixture.

        Finds the first fixture on *date* that matches the team name stored
        against *team_id* in the provider, then formats goals and cards into a
        readable timeline.
        """
        games = self.get_game_scores(date)
        featured = next(
            (g for g in games if g.get("fixture_id") == team_id),
            None,
        )
        if featured is None:
            return None

        fid: int = featured["fixture_id"]
        home: str = featured.get("home_team") or ""
        away: str = featured.get("away_team") or ""
        events = self.get_fixture_events(fid)

        lines: List[str] = [f"{away} {featured.get('away_score', '-')} – {home} {featured.get('home_score', '-')}", ""]
        for ev in sorted(events, key=lambda e: (e.get("time") or {}).get("elapsed") or 0):
            elapsed = (ev.get("time") or {}).get("elapsed")
            team_name = (ev.get("team") or {}).get("name") or ""
            player = (ev.get("player") or {}).get("name") or "Unknown"
            typ = ev.get("type")
            detail = (ev.get("detail") or "").lower()
            if typ == "Goal":
                assist_name = (ev.get("assist") or {}).get("name")
                assist_str = f" (asst: {assist_name})" if assist_name else ""
                lines.append(f"  {elapsed}' ⚽ {player} ({team_name}){assist_str}")
            elif typ == "Card":
                card_sym = "🟥" if detail == "red card" else "🟨"
                lines.append(f"  {elapsed}' {card_sym} {player} ({team_name})")

        return "\n".join(lines)

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Return True if the team represented by *team_id* played a completed game.

        For World Cup, *team_id* is used as an index into PRIORITY_TEAM_NAMES so
        that the base SportsScreamsheet selection logic works. ID -1 (random) is
        handled by the sheet layer before calling this method.
        """
        if team_id < 0 or team_id >= len(PRIORITY_TEAM_NAMES):
            return False
        target = PRIORITY_TEAM_NAMES[team_id]
        games = self.get_game_scores(date)
        for g in games:
            if g.get("status_short") in self.COMPLETED_STATUSES:
                if g.get("home_team") == target or g.get("away_team") == target:
                    return True
        return False

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (fixture_id, team_name) for all completed fixtures on *date*.

        The first element of each tuple is the *fixture_id* (not a DB team ID).
        This is used by the World Cup sheet's fallback random selection logic
        which passes fixture_id to WorldCupBoxScoreSection directly.
        """
        games = self.get_game_scores(date)
        pairs: List[Tuple[int, str]] = []
        for g in games:
            if g.get("status_short") not in self.COMPLETED_STATUSES:
                continue
            fid = g.get("fixture_id")
            if fid is None:
                continue
            if g.get("home_team"):
                pairs.append((int(fid), str(g["home_team"])))
            if g.get("away_team"):
                pairs.append((int(fid), str(g["away_team"])))
        return pairs

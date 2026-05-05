"""Game data extraction: fetch raw API data and extract structured dicts for LLM summarizers.

These classes own the data-fetching and transformation steps only — no LLM logic lives here.
Pass the returned ExtractedInfo dict to the appropriate summarizer in llm/summary.py.
"""
import logging
import re
import time
import requests
from typing import Optional, Dict, Any, Union, List

from ..db import lookup_player as _db_lookup_player
from ..db.nhl_teams_db import lookup_team_by_id as _db_lookup_team

logger = logging.getLogger(__name__)

ExtractedInfo = Dict[str, Union[str, int]]


class MLBGameExtractor:
    """Fetches and extracts MLB game data from the MLB Stats API."""

    @staticmethod
    def fetch_raw_data(team_id: int, date_str: str) -> Optional[Dict[str, Any]]:
        """Fetch raw live feed data for a team on a given date (YYYY-MM-DD)."""
        schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
        params = {'sportId': 1, 'teamId': team_id, 'date': date_str}

        try:
            schedule_response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data = schedule_response.json()

            game_pk = None
            if schedule_data.get('totalItems', 0) > 0:
                for game in schedule_data.get('dates', [{}])[0].get('games', []):
                    away_id = game.get('teams', {}).get('away', {}).get('team', {}).get('id')
                    home_id = game.get('teams', {}).get('home', {}).get('team', {}).get('id')
                    if away_id == team_id or home_id == team_id:
                        game_pk = game.get('gamePk')
                        break

            if not game_pk:
                print("No game found for the specified team and date.")
                return None

            game_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            summary_response = requests.get(game_url)
            summary_response.raise_for_status()
            return summary_response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error fetching MLB game data: {e}")
            return None

    @staticmethod
    def extract_key_info(raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Extract home/away teams, scores, and play-by-play narrative from raw feed data."""
        if not raw_data:
            return "No game data available."

        try:
            home_team = raw_data['gameData']['teams']['home']['name']
            away_team = raw_data['gameData']['teams']['away']['name']

            home_score = raw_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('home', {}).get('runs', 0)
            away_score = raw_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('away', {}).get('runs', 0)

            play_by_play: List[str] = []
            plays = raw_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            for play in plays:
                description = play.get('result', {}).get('description', '')
                if description:
                    play_by_play.append(description)

            return {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'narrative_snippets': " ".join(play_by_play),
            }
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing MLB game data: {e}")
            return "Could not parse MLB game details for summary generation."


class NHLGameExtractor:
    """Fetches and extracts NHL game data from the NHL Web API.

    Loads player and team name maps from documentation/ on init to avoid
    repeated API lookups for every play in a game.
    """

    # ------------------------------------------------------------------
    # Name lookups (DB-backed)
    # ------------------------------------------------------------------

    def _lookup_player(self, player_id: Optional[int]) -> str:
        if player_id is None:
            return "N/A"
        result = _db_lookup_player(player_id=player_id)
        if result:
            first = result.get("player_first_name", "")
            last = result.get("player_last_name", "")
            return f"{first} {last}".strip() or "Unknown Player"
        return "Unknown Player"

    def _lookup_team(self, team_id: Optional[int]) -> str:
        if team_id is None:
            return "N/A Team"
        result = _db_lookup_team(team_id=team_id)
        if result:
            city = result.get("city", "")
            name = result.get("team_full_name", "")
            return f"{city} {name}".strip() or "Unknown Team"
        return "Unknown Team"

    # ------------------------------------------------------------------
    # Data fetch
    # ------------------------------------------------------------------

    def fetch_raw_data(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Fetch raw play-by-play data for a game_pk."""
        try:
            url = f"https://api-web.nhle.com/v1/gamecenter/{game_pk}/play-by-play"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NHL game data: {e}")
            return None

    # ------------------------------------------------------------------
    # Play parsers
    # ------------------------------------------------------------------

    def _parse_goal(self, details: Dict[str, Any]) -> str:
        scoring_player = self._lookup_player(details.get("scoringPlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        goalie = self._lookup_player(details.get("goalieInNetId"))
        goalie_text = f"on {goalie}" if goalie != "Unknown Player" else "into an empty net"
        narrative = f"{scoring_player} ({team}) scored {goalie_text}"

        assists = []
        if details.get("assist1PlayerId"):
            assists.append(self._lookup_player(details["assist1PlayerId"]))
        if details.get("assist2PlayerId"):
            assists.append(self._lookup_player(details["assist2PlayerId"]))

        if len(assists) == 1:
            narrative += f" assisted by {assists[0]}"
        elif len(assists) == 2:
            narrative += f" assisted by {assists[0]} and {assists[1]}"

        return narrative

    def _parse_hit(self, details: Dict[str, Any]) -> str:
        hitter = self._lookup_player(details.get("hittingPlayerId"))
        hittee = self._lookup_player(details.get("hitteePlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        return f"{hitter} ({team}) hit {hittee}"

    def _parse_penalty(self, details: Dict[str, Any]) -> str:
        reason = details.get("descKey", "Unknown Reason")
        duration = f'{details.get("duration", 0)} {details.get("typeCode", "min")}'
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        committed_by = self._lookup_player(details.get("committedByPlayerId"))
        narrative = f"{duration} penalty for {committed_by} ({team}) for {reason}"

        if drawn_by_id := details.get("drawnByPlayerId"):
            narrative += f" (drawn by {self._lookup_player(drawn_by_id)})"

        return narrative

    def _parse_shot_on_goal(self, details: Dict[str, Any]) -> str:
        shooter = self._lookup_player(details.get("shootingPlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        goalie = self._lookup_player(details.get("goalieInNetId"))
        return f"Shot on goal by {shooter} ({team}) saved by {goalie}"

    def _parse_takeaway(self, details: Dict[str, Any]) -> str:
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        player = self._lookup_player(details.get("playerId"))
        return f"Takeaway by {player} ({team})"

    def _build_narrative(self, play: Dict[str, Any]) -> str:
        period = play.get("periodDescriptor", {}).get("number", "N/A")
        time_remaining = play.get("timeRemaining", "0:00")
        details = play.get("details", {})
        play_type = play.get("typeDescKey")

        parser_map = {
            "goal": self._parse_goal,
            "hit": self._parse_hit,
            "penalty": self._parse_penalty,
            "shot-on-goal": self._parse_shot_on_goal,
            "takeaway": self._parse_takeaway,
        }

        parser = parser_map.get(play_type or '') or (lambda d: f"Unknown play type: {play_type}")
        description = parser(details)
        zone = details.get("zoneCode", "N/A")
        return f"[Period {period}, {time_remaining}] {description} in zone {zone}."

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Extract home/away teams, scores, and play-by-play narrative from raw data."""
        if not raw_data:
            return "No game data available."

        try:
            home = raw_data.get("homeTeam", {})
            away = raw_data.get("awayTeam", {})

            home_name = home.get("placeName", {}).get("default", "Home") + " " + home.get("commonName", {}).get("default", "Team")
            away_name = away.get("placeName", {}).get("default", "Away") + " " + away.get("commonName", {}).get("default", "Team")

            play_narratives: List[str] = [
                self._build_narrative(play)
                for play in raw_data.get("plays", [])
                if play.get("typeDescKey") in {'goal', 'hit', 'penalty', 'shot-on-goal', 'takeaway'}
            ]

            return {
                'home_team': home_name,
                'away_team': away_name,
                'home_score': home.get("score", 0),
                'away_score': away.get("score", 0),
                'narrative_snippets': " ".join(play_narratives),
            }
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing NHL game data: {e}")
            return "Could not parse NHL game details for summary generation."


class NBAGameExtractor:
    """Fetches and extracts NBA game data from nba_api for LLM summarizers.

    Play-by-play is sourced from ``PlayByPlayV3`` (preferred — works for
    playoff games) with ``PlayByPlayV2`` as a fallback.  Final score and team
    names are authoritative from ``BoxScoreTraditionalV2``.
    """

    # V3 actionType strings we include in the narrative
    _V3_NARRATIVE_TYPES = {"Made Shot", "Free Throw", "Turnover", "Foul"}

    # V2 EVENTMSGTYPE codes we include in the narrative
    _V2_MADE_SHOT = 1
    _V2_FREE_THROW = 3
    _V2_TURNOVER = 5
    _V2_FOUL = 6
    _V2_NARRATIVE_CODES = {_V2_MADE_SHOT, _V2_FREE_THROW, _V2_TURNOVER, _V2_FOUL}

    @staticmethod
    def _parse_v3_clock(clock: str) -> str:
        """Convert ISO 8601 duration ``PT11M30.00S`` → ``11:30``."""
        m = re.match(r"PT(\d+)M([\d.]+)S", clock)
        if m:
            mins = m.group(1)
            secs = str(int(float(m.group(2)))).zfill(2)
            return f"{mins}:{secs}"
        return clock

    def fetch_raw_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Return a dict with ``play_by_play`` DataFrame, ``boxscore`` DataFrame,
        and ``pbp_version`` (3, 2, or 0).

        Strategy:
        1. Fetch BoxScoreTraditionalV2 (always reliable).
        2. Try PlayByPlayV3 first — handles regular-season *and* playoff games.
        3. Fall back to PlayByPlayV2 if V3 fails.
        4. If both fail, return an empty DataFrame (box-score-only summary).
        """
        import pandas as pd

        try:
            from nba_api.stats.endpoints import boxscoretraditionalv2
        except ImportError:
            logger.error("nba_api not installed — cannot fetch NBA game data")
            return None

        # ---- boxscore (required) ----
        try:
            box_df = boxscoretraditionalv2.BoxScoreTraditionalV2(
                game_id=game_id
            ).get_data_frames()[0]
        except Exception:
            logger.exception("BoxScoreTraditionalV2 failed for game_id=%s", game_id)
            return None

        # nba_api enforces a ~600 ms rate limit between consecutive requests.
        time.sleep(0.8)

        # ---- play-by-play V3 (preferred — works for playoffs) ----
        try:
            from nba_api.stats.endpoints import playbyplayv3
            pbp_df = playbyplayv3.PlayByPlayV3(
                game_id=game_id, start_period=0, end_period=14
            ).get_data_frames()[0]
            logger.info("PlayByPlayV3: %d events for game_id=%s", len(pbp_df), game_id)
            return {"play_by_play": pbp_df, "boxscore": box_df, "pbp_version": 3}
        except Exception:
            logger.warning(
                "PlayByPlayV3 failed for game_id=%s — trying V2", game_id, exc_info=True
            )

        time.sleep(0.8)

        # ---- play-by-play V2 (fallback — regular season only) ----
        try:
            from nba_api.stats.endpoints import playbyplayv2
            pbp_df = playbyplayv2.PlayByPlayV2(game_id=game_id).get_data_frames()[0]
            logger.info("PlayByPlayV2: %d events for game_id=%s", len(pbp_df), game_id)
            return {"play_by_play": pbp_df, "boxscore": box_df, "pbp_version": 2}
        except Exception:
            logger.warning(
                "PlayByPlayV2 also failed for game_id=%s — summary will be box-score only",
                game_id,
                exc_info=True,
            )

        return {"play_by_play": pd.DataFrame(), "boxscore": box_df, "pbp_version": 0}

    def extract_key_info(
        self,
        raw_data: Optional[Dict[str, Any]],
        featured_team_id: int,
    ) -> Union[ExtractedInfo, str]:
        """Extract team names, final score, and play-by-play narrative.

        Handles V3 columns (``scoreHome``/``scoreAway``, ``actionType``,
        ``description``), V2 columns (``SCORE``, ``EVENTMSGTYPE``,
        ``HOMEDESCRIPTION``/``VISITORDESCRIPTION``), and an empty play-by-play
        DataFrame (box-score-only fallback for both score and narrative).
        """
        if not raw_data:
            return "No game data available."

        try:
            import pandas as pd

            pbp: pd.DataFrame = raw_data["play_by_play"]
            box: pd.DataFrame = raw_data["boxscore"]
            pbp_version: int = raw_data.get("pbp_version", 0)

            # ---- team IDs and names from boxscore ----
            team_ids = box["TEAM_ID"].unique()
            if len(team_ids) < 2:
                return "Could not identify teams in NBA boxscore."

            # Default order from boxscore (may be visitor-first; corrected below)
            home_team_id: int = int(team_ids[0])
            away_team_id: int = int(team_ids[1])

            # V3 play-by-play has a `location` column: 'h' = home, 'v' = visitor.
            # Use it to reliably map team_id → home/away.
            if pbp_version == 3 and not pbp.empty and "location" in pbp.columns and "teamId" in pbp.columns:
                home_rows_pbp = pbp[(pbp["location"] == "h") & pbp["teamId"].notna()]
                away_rows_pbp = pbp[(pbp["location"] == "v") & pbp["teamId"].notna()]
                if not home_rows_pbp.empty and not away_rows_pbp.empty:
                    home_team_id = int(home_rows_pbp.iloc[0]["teamId"])
                    away_team_id = int(away_rows_pbp.iloc[0]["teamId"])
                    logger.debug(
                        "V3 location: home_team_id=%s away_team_id=%s", home_team_id, away_team_id
                    )

            def _team_name(tid: int) -> str:
                rows = box[box["TEAM_ID"] == tid]
                if rows.empty:
                    return "Unknown Team"
                r = rows.iloc[0]
                city = str(r.get("TEAM_CITY", ""))
                name = str(r.get("TEAM_NICKNAME", r.get("TEAM_NAME", "")))
                return f"{city} {name}".strip()

            home_team_name = _team_name(home_team_id)
            away_team_name = _team_name(away_team_id)
            featured_team_is_home = (featured_team_id == home_team_id)

            # ---- final score ----
            home_score: int
            away_score: int

            if pbp_version == 3 and not pbp.empty and "scoreHome" in pbp.columns:
                # V3: scoreHome/scoreAway columns, empty string on non-scoring rows
                valid = pbp[pbp["scoreHome"].notna() & (pbp["scoreHome"] != "")]
                if not valid.empty:
                    last = valid.iloc[-1]
                    home_score = int(float(str(last["scoreHome"])))
                    away_score = int(float(str(last["scoreAway"])))
                else:
                    home_score = int(box[box["TEAM_ID"] == home_team_id]["PTS"].sum())
                    away_score = int(box[box["TEAM_ID"] == away_team_id]["PTS"].sum())
            elif pbp_version == 2 and not pbp.empty and "SCORE" in pbp.columns:
                # V2: "VISITOR - HOME" string in SCORE column
                score_rows = pbp[pbp["SCORE"].notna() & (pbp["SCORE"] != "")]
                if not score_rows.empty:
                    parts = str(score_rows.iloc[-1]["SCORE"]).split(" - ")
                    away_score = int(parts[0].strip()) if len(parts) == 2 else 0
                    home_score = int(parts[1].strip()) if len(parts) == 2 else 0
                else:
                    home_score = int(box[box["TEAM_ID"] == home_team_id]["PTS"].sum())
                    away_score = int(box[box["TEAM_ID"] == away_team_id]["PTS"].sum())
            else:
                # No play-by-play — use boxscore totals
                home_score = int(box[box["TEAM_ID"] == home_team_id]["PTS"].sum())
                away_score = int(box[box["TEAM_ID"] == away_team_id]["PTS"].sum())

            # ---- narrative ----
            narrative_parts: List[str] = []

            if pbp_version == 3 and not pbp.empty and "actionType" in pbp.columns:
                for _, row in pbp.iterrows():
                    if str(row.get("actionType", "")) not in self._V3_NARRATIVE_TYPES:
                        continue
                    desc = str(row.get("description", "")).strip()
                    if not desc or desc.lower() == "nan":
                        continue
                    period = row.get("period", "")
                    clock = self._parse_v3_clock(str(row.get("clock", "")).strip())
                    prefix = f"[Q{period} {clock}]" if period and clock else ""
                    narrative_parts.append(f"{prefix} {desc}".strip())

            elif pbp_version == 2 and not pbp.empty and "EVENTMSGTYPE" in pbp.columns:
                for _, row in pbp.iterrows():
                    if row.get("EVENTMSGTYPE") not in self._V2_NARRATIVE_CODES:
                        continue
                    home_desc = str(row.get("HOMEDESCRIPTION") or "").strip()
                    visit_desc = str(row.get("VISITORDESCRIPTION") or "").strip()
                    desc = home_desc or visit_desc
                    if not desc or desc.lower() == "nan":
                        continue
                    period = row.get("PERIOD", "")
                    clock = str(row.get("PCTIMESTRING") or "").strip()
                    prefix = f"[Q{period} {clock}]" if period and clock else ""
                    narrative_parts.append(f"{prefix} {desc}".strip())

            # If no play-by-play at all, build a minimal narrative from the top
            # scorers in the boxscore so the LLM has *something* to work with.
            if not narrative_parts:
                logger.info(
                    "No play-by-play for game_id; building narrative from boxscore top scorers"
                )
                for tid, label in [(home_team_id, "Home"), (away_team_id, "Away")]:
                    team_rows = box[box["TEAM_ID"] == tid].copy()
                    team_rows = team_rows[team_rows["MIN"].notna() & (team_rows["MIN"] != "")]
                    top = team_rows.nlargest(3, "PTS") if "PTS" in team_rows.columns else team_rows.head(3)
                    for _, r in top.iterrows():
                        name = str(r.get("PLAYER_NAME", "Unknown"))
                        pts = int(float(str(r.get("PTS", 0)))) if str(r.get("PTS", "nan")) != "nan" else 0
                        reb = int(float(str(r.get("REB", 0)))) if str(r.get("REB", "nan")) != "nan" else 0
                        ast = int(float(str(r.get("AST", 0)))) if str(r.get("AST", "nan")) != "nan" else 0
                        narrative_parts.append(
                            f"{name} ({label}): {pts} pts, {reb} reb, {ast} ast"
                        )

            losing_team = home_team_name if home_score < away_score else away_team_name

            return {
                "home_team": home_team_name,
                "away_team": away_team_name,
                "home_score": home_score,
                "away_score": away_score,
                "featured_team_is_home": featured_team_is_home,
                "losing_team": losing_team,
                "narrative_snippets": " ".join(narrative_parts),
            }

        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.exception("Error parsing NBA game data")
            return "Could not parse NBA game details for summary generation."

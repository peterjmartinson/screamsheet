"""NBA data provider for fetching NBA game data."""
import logging
import math
import pandas as pd
from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple

from ..base import DataProvider

logger = logging.getLogger(__name__)

try:
    from nba_api.stats.endpoints import leaguegamefinder, leaguestandings, boxscoretraditionalv2
except ImportError:
    logger.warning("nba_api package not installed — NBA provider will have limited functionality.")


class NBADataProvider(DataProvider):
    """
    Data provider for NBA using the nba_api package.

    Provides access to:
    - Game scores
    - League standings
    - Box scores
    - Game summaries (via LLM)
    """

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
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

        logger.info("Looking up game_id for team_id=%s on %s", team_id, date_str)
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                team_id_nullable=team_id,
                date_from_nullable=date_str,
                date_to_nullable=date_str,
            )
            df = finder.get_data_frames()[0]
            if df.empty:
                logger.warning("No game found for team_id=%s on %s", team_id, date_str)
                self._game_id_cache[cache_key] = None
                return None
            game_id = str(df.iloc[0]["GAME_ID"])
            logger.info("Found game_id=%s for team_id=%s on %s", game_id, team_id, date_str)
            self._game_id_cache[cache_key] = game_id
            return game_id
        except Exception:
            logger.exception("Error looking up game_id for team_id=%s on %s", team_id, date_str)
            self._game_id_cache[cache_key] = None
            return None
    
    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> List[Dict[str, Any]]:
        """
        Get NBA game scores for a specific date.

        Uses the MATCHUP column to determine home vs. away:
        - ``"PHI vs. BOS"`` → Philadelphia is home
        - ``"BOS @ PHI"``   → Boston is away
        """
        date_str = date.strftime("%Y-%m-%d")
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                date_from_nullable=date_str,
                date_to_nullable=date_str,
            )
            games_df = finder.get_data_frames()[0]

            if games_df.empty:
                return []

            games: List[Dict[str, Any]] = []
            seen_game_ids: set = set()

            for _, row in games_df.iterrows():
                game_id = row["GAME_ID"]
                if game_id in seen_game_ids:
                    continue
                seen_game_ids.add(game_id)

                game_rows = games_df[games_df["GAME_ID"] == game_id]
                if len(game_rows) < 2:
                    continue

                # Identify home / away by MATCHUP content
                home_rows = game_rows[game_rows["MATCHUP"].str.contains(r"\bvs\.", regex=True)]
                away_rows = game_rows[game_rows["MATCHUP"].str.contains(r"\s@\s", regex=True)]

                if home_rows.empty or away_rows.empty:
                    # Fallback: row 0 home, row 1 away
                    home_row = game_rows.iloc[0]
                    away_row = game_rows.iloc[1]
                else:
                    home_row = home_rows.iloc[0]
                    away_row = away_rows.iloc[0]

                games.append({
                    "gameDate": str(home_row["GAME_DATE"]),
                    "home_team": str(home_row["TEAM_NAME"]),
                    "away_team": str(away_row["TEAM_NAME"]),
                    "home_score": int(home_row["PTS"]),
                    "away_score": int(away_row["PTS"]),
                    "status": "Final",
                })

            logger.info("Fetched %d NBA game(s) for %s", len(games), date_str)
            return games
        except Exception:
            logger.exception("Error fetching NBA game scores for %s", date_str)
            return []
    
    def get_standings(self) -> pd.DataFrame:
        """
        Get current NBA league standings.

        Returns:
            DataFrame with columns: conference, team, wins, losses, pct,
            conf_record, division_rank — sorted by conference then win pct desc.
        """
        try:
            standings = leaguestandings.LeagueStandings()
            df = standings.get_data_frames()[0]

            if df.empty:
                return pd.DataFrame()

            df = df[[
                "Conference",
                "TeamCity",
                "TeamName",
                "WINS",
                "LOSSES",
                "WinPCT",
                "ConferenceRecord",
                "DivisionRank",
            ]].copy()

            df["FullTeamName"] = df["TeamCity"] + " " + df["TeamName"]
            df = df[[
                "Conference",
                "FullTeamName",
                "WINS",
                "LOSSES",
                "WinPCT",
                "ConferenceRecord",
                "DivisionRank",
            ]].copy()
            df.columns = [
                "conference", "team", "wins", "losses",
                "pct", "conf_record", "division_rank",
            ]

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
        date_str = date.strftime("%Y-%m-%d")
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                date_from_nullable=date_str,
                date_to_nullable=date_str,
            )
            df = finder.get_data_frames()[0]
            if df.empty:
                return []
            return [
                (int(row["TEAM_ID"]), str(row["TEAM_NAME"]))
                for _, row in df.iterrows()
            ]
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

        try:
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            df = box.get_data_frames()[0]  # PlayerStats DataFrame

            team_df = df[df["TEAM_ID"] == team_id].copy()
            if team_df.empty:
                logger.warning("BoxScore returned no rows for team_id=%s game_id=%s", team_id, game_id)
                return None

            # Drop rows where the player did not play (MIN is NaN)
            team_df = team_df[team_df["MIN"].notna() & (team_df["MIN"] != "")]
            logger.debug("Box score rows after DNP filter: %d", len(team_df))

            si = self._safe_int  # shorthand
            player_stats: List[Dict[str, Any]] = []
            for _, row in team_df.iterrows():
                fg = f"{si(row.get('FGM'))}-{si(row.get('FGA'))}"
                three_p = f"{si(row.get('FG3M'))}-{si(row.get('FG3A'))}"
                ft = f"{si(row.get('FTM'))}-{si(row.get('FTA'))}"

                raw_min = str(row.get("MIN", "0:00"))
                min_str = raw_min.split(".")[0] if "." in raw_min else raw_min

                player_stats.append({
                    "name": str(row["PLAYER_NAME"]),
                    "MIN": min_str,
                    "FG": fg,
                    "3P": three_p,
                    "FT": ft,
                    "REB": si(row.get("REB")),
                    "AST": si(row.get("AST")),
                    "STL": si(row.get("STL")),
                    "BLK": si(row.get("BLK")),
                    "PTS": si(row.get("PTS")),
                })

            # Sort by points descending so leading scorers appear first
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
    ) -> Optional[str]:
        """
        Generate an LLM game summary for *team_id* on *date*.

        Uses the angry fan-rant persona when ``is_primary_favorite`` is True
        and the featured team lost; otherwise uses the neutral recap.
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
            if is_primary_favorite:
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
                logger.info("Game summary: team_id=%s (not primary favorite) — using GameSummarizer", team_id)

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

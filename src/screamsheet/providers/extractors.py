"""Game data extraction: fetch raw API data and extract structured dicts for LLM summarizers.

These classes own the data-fetching and transformation steps only — no LLM logic lives here.
Pass the returned ExtractedInfo dict to the appropriate summarizer in llm/summary.py.
"""
import requests
from typing import Optional, Dict, Any, Union, List

from ..db import lookup_player as _db_lookup_player
from ..db.nhl_teams_db import lookup_team_by_id as _db_lookup_team

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

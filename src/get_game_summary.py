import os
import requests
from lorem_text import lorem
from google import genai
from typing import Optional, Dict, Union, Any, List
from pathlib import Path
import json


class GameSummaryGenerator:
    """
    A class to fetch MLB game data and generate a human-readable summary
    using a Large Language Model.
    """

    # Class attributes
    _use_default_text: bool = True
    _default_text: str = lorem.paragraphs(1)

    def __init__(self, gemini_api_key: Optional[str] = None) -> None:
        """
        Initializes the generator with a Gemini API key.
        """
        self._cwd = Path.cwd()
        if gemini_api_key is not None:
            self._use_default_text = False
            self.client: genai.Client = genai.Client(api_key=gemini_api_key)
            self.model_name: str = 'gemini-2.5-flash'
        else:
            self._use_default_text = True
            self.client = None
            self.model_name = None

    def _fetch_raw_game_data(self, team_id: int, date_str: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to get the raw JSON data for a specific game.
        """
        schedule_url: str = "https://statsapi.mlb.com/api/v1/schedule"
        params: Dict[str, Union[int, str]] = {'sportId': 1, 'teamId': team_id, 'date': date_str}
        
        try:
            schedule_response: requests.Response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data: Dict[str, Any] = schedule_response.json()

            game_pk: Optional[int] = None
            if 'dates' in schedule_data and schedule_data['dates']:
                for game in schedule_data['dates'][0]['games']:
                    # Assuming team IDs are integers
                    if game['teams']['away']['team']['id'] == team_id or game['teams']['home']['team']['id'] == team_id:
                        game_pk = game['gamePk']
                        break
            
            if not game_pk:
                return None
            
            game_summary_url: str = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            summary_response: requests.Response = requests.get(game_summary_url)
            summary_response.raise_for_status()
            
            output: Dict[str, Any] = summary_response.json()
            print(output)
            return output

        except requests.exceptions.RequestException as e:
            print(f"Error fetching game data: {e}")
            return None

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[Dict[str, Union[str, int]], str]:
        """
        Internal method to parse and extract key game events.
        """
        if not raw_data:
            return "No game data available."
        
        try:
            home_team: str = raw_data['gameData']['teams']['home']['name']
            away_team: str = raw_data['gameData']['teams']['away']['name']
            
            # Use 'linescore' to get the final score
            home_score: int = raw_data['liveData']['linescore']['teams']['home']['runs']
            away_score: int = raw_data['liveData']['linescore']['teams']['away']['runs']
            
            # A simple way to get some play-by-play narrative
            play_by_play_narrative: List[str] = []
            plays: List[Dict[str, Any]] = raw_data['liveData']['plays']['allPlays']
            for play in plays: #[:10]: # Limiting to the first 10 for conciseness
                play_by_play_narrative.append(play['result']['description'])

            # Type annotation for the return dictionary
            return {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'narrative_snippets': " ".join(play_by_play_narrative)
            }
        except (KeyError, IndexError) as e:
            print(f"Error parsing game data: {e}")
            return "Could not parse game details for summary generation."

    def _generate_llm_summary(self, extracted_info: Union[Dict[str, Union[str, int]], str]) -> str:
        """
        Internal method to send extracted data to the LLM and get a summary.
        """
        if isinstance(extracted_info, str):
            return extracted_info

        # Extracted info is guaranteed to be a Dict here
        extracted_info_dict: Dict[str, Union[str, int]] = extracted_info # Type alias for clarity

        prompt: str = f"""
        You are a professional sports journalist. Write a concise, engaging summary of the following baseball game. 
        Focus on the final score and a few key highlights from each inning, in order.

        Game details:
        Home Team: {extracted_info_dict['home_team']}
        Away Team: {extracted_info_dict['away_team']}
        Final Score: {extracted_info_dict['home_team']} {extracted_info_dict['home_score']}, {extracted_info_dict['away_team']} {extracted_info_dict['away_score']}
        
        Narrative snippets (for context): {extracted_info_dict['narrative_snippets']}

        Provide the summary in a single paragraph.
        """
        
        try:
            # Assuming self.client is properly initialized as a genai.Client
            response: Any = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."

    def generate_summary(self, team_id: int = 143, date_str: str = "2025-09-05") -> str:
        """
        Public method to generate the full game summary.
        
        Args:
            team_id (int): The MLB team ID (e.g., 143 for Phillies).
            date_str (str): The date in 'YYYY-MM-DD' format.
        
        Returns:
            str: A formatted game summary from the LLM.
        """
        llm_summary: str = self._default_text
        if not self._use_default_text:
            raw_data: Optional[Dict[str, Any]] = self._fetch_raw_game_data(team_id, date_str)
            extracted_info: Union[Dict[str, Union[str, int]], str] = self._extract_key_info(raw_data)
            llm_summary = self._generate_llm_summary(extracted_info)
        return llm_summary

class GameSummaryGeneratorNHL(GameSummaryGenerator):
    """
    A subclass of GameSummaryGenerator for NHL games.
    """

    def __init__(self, gemini_api_key: Optional[str] = None) -> None:
        super().__init__(gemini_api_key)
        self._doc_dir = self._cwd / "documentation"
        player_file = self._doc_dir / "nhl_players.json"
        with open(player_file, "r") as f:
            self._player_map = json.load(f)
        team_file = self._doc_dir / "nhl_teams.json"
        with open(team_file, "r") as f:
            self._team_map = json.load(f)


    def _fetch_raw_game_data(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """
        Internal method to get the raw JSON data for a specific NHL game.
        """
        schedule_url: str = "https://statsapi.web.nhl.com/api/v1/schedule"
        
        try:
            game_summary_url: str = f"https://api-web.nhle.com/v1/gamecenter/{game_pk}/play-by-play"
            summary_response: requests.Response = requests.get(game_summary_url)
            summary_response.raise_for_status()
            
            output: Dict[str, Any] = summary_response.json()
            return output

        except requests.exceptions.RequestException as e:
            print(f"Error fetching game data: {e}")
            return None

    def _get_team_roster(self, team_id):
        pass

    def _lookup_player(self, player_id):
        for player in self._player_map:
            if player["player_id"] == player_id:
                return player["first_name"] + " " + player["last_name"]
        try:
            url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
            res = requests.get(url)
            player_info = res.json()
            first_name = player_info["firstName"]["default"]
            last_name = player_info["lastName"]["default"]
            return first_name + " " + last_name
        except Exception as ex:
            print(f"Player {player_id} not found:  {ex}")
        return "Unknown Player"


    def _lookup_team(self, team_id):
        for team in self._team_map["data"]:
            if team["id"] == team_id:
                return team["fullName"]
        return "Unknown Team"


    def _build_narrative(self, play):
        period = play["periodDescriptor"]["number"]
        time_remaining = play["timeRemaining"]
        narrative = f"[Period {period}, {time_remaining} remaining] "
        details = play["details"]
        zone = details["zoneCode"]
        play_type = play["typeDescKey"]
        if play_type == "goal":
            description = self._parse_goal(details)
        elif play_type == "hit":
            description = self._parse_hit(details)
        elif play_type == "penalty":
            description = self._parse_penalty(details)
        elif play_type == "shot-on-goal":
            description = self._parse_shot_on_goal(details)
        elif play_type == "takeaway":
            description = self._parse_takeaway(details)
        narrative += description + f"in zone {zone}."
        return narrative
        
    def _parse_takeaway(self, details):
        team = self._lookup_team(details["eventOwnerTeamId"])
        player = self._lookup_player(details["playerId"])
        narrative = f"Takeaway by {player} ({team})"
        return narrative

    def _parse_penalty(self, details):
        reason = details["descKey"]
        duration = f'{details["duration"]} {details["typeCode"]}'
        team = self._lookup_team(details["eventOwnerTeamId"])
        committed_by_player = self._lookup_player(details["committedByPlayerId"])
        narrative = f"{duration} penalty for {committed_by_player} ({team}) for {reason}"
        if "drawnByPlayerId" in details:
            drawn_by_player = self._lookup_player(details["drawnByPlayerId"])
            narrative += f" against {drawn_by_player}"
        return narrative

    def _parse_hit(self, details):
        hitting_player = self._lookup_player(details["hittingPlayerId"])
        hittee_player = self._lookup_player(details["hitteePlayerId"])
        team = self._lookup_team(details["eventOwnerTeamId"])
        narrative = f"{hitting_player} ({team}) hit {hittee_player}"
        return narrative

    def _parse_goal(self, details):
        scoring_player = self._lookup_player(details["scoringPlayerId"])
        team = self._lookup_team(details["eventOwnerTeamId"])
        goalie = "Empty Net (goalie pulled)"
        if "goalieInNetId" in details:
            goalie = self._lookup_player(details["goalieInNetId"])
        narrative = f"{scoring_player} ({team}) scored on {goalie}"
        if "assist1PlayerId" in details:
            assist_player_1 = self._lookup_player(details["assist1PlayerId"])
            narrative += f" assisted by {assist_player_1}"
        if "assist2PlayerId" in details:
            assist_player_2 = self._lookup_player(details["assist2PlayerId"])
            narrative += f" and {assist_player_2}"
        return narrative

    def _parse_shot_on_goal(self, details):
        shooting_player = self._lookup_player(details["shootingPlayerId"])
        team = self._lookup_team(details["eventOwnerTeamId"])
        goalie = self._lookup_player(details["goalieInNetId"])
        narrative = f"{shooting_player} ({team}) shot on {goalie}"
        return narrative

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[Dict[str, Union[str, int]], str]:
        """
        Internal method to parse and extract key game events.
        """
        if not raw_data:
            return "No game data available."
        
        try:
            home_team = {
              "id": raw_data["homeTeam"]["id"],
              "name": raw_data["homeTeam"]["commonName"]["default"],
              "place": raw_data["homeTeam"]["placeName"]["default"],
              "score": raw_data["homeTeam"]["score"]
            }
            away_team = {
              "id": raw_data["awayTeam"]["id"],
              "name": raw_data["awayTeam"]["commonName"]["default"],
              "place": raw_data["awayTeam"]["placeName"]["default"],
              "score": raw_data["awayTeam"]["score"]
            }

            
            # A simple way to get some play-by-play narrative
            play_by_play_narrative: List[str] = []
            for play in raw_data["plays"]:
                if play["typeDescKey"] in ['goal', 'hit', 'penalty', 'shot-on-goal', 'takeaway']:
                    play_by_play_narrative.append(self._build_narrative(play))

            # Type annotation for the return dictionary
            return {
                'home_team': home_team["place"] + " " + home_team["name"],
                'away_team': away_team["place"] + " " + away_team["name"],
                'home_score': home_team["score"],
                'away_score': away_team["score"],
                'narrative_snippets': " ".join(play_by_play_narrative)
            }
        except (KeyError, IndexError) as e:
            print(f"Error parsing game data: {e}")
            return "Could not parse game details for summary generation."

    def _generate_llm_summary(self, extracted_info: Union[Dict[str, Union[str, int]], str]) -> str:
        """
        Internal method to send extracted data to the LLM and get a summary.
        """
        if isinstance(extracted_info, str):
            return extracted_info

        # Extracted info is guaranteed to be a Dict here
        extracted_info_dict: Dict[str, Union[str, int]] = extracted_info # Type alias for clarity

        prompt: str = f"""
        You are a friendly, enthusiastic sports broadcaster writing a recap for
        a young boy who is just starting to learn about hockey. Explain any
        complex terms (like 'power play' or 'penalty kill') simply, and focus on
        the action and excitement. The final summary must be a single paragraph.

        Game details to include:
        Home Team: {extracted_info_dict['home_team']}
        Away Team: {extracted_info_dict['away_team']}
        Final Score: {extracted_info_dict['home_team']} {extracted_info_dict['home_score']} to {extracted_info_dict['away_team']} {extracted_info_dict['away_score']}

        Narrative snippets (for context, include highlights from each period in order): {extracted_info_dict['narrative_snippets']}

        Write the exciting, one-paragraph recap now.
        """
        
        try:
            # Assuming self.client is properly initialized as a genai.Client
            response: Any = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."






# Example Usage in your main script
if __name__ == "__main__":
    # Instantiate the class
    summary_generator: GameSummaryGenerator = GameSummaryGeneratorNHL("AIzaSyARxhq7R287MSTqMxKJu2Xd7vsxcMGNDO0")
    game_pk = 2025020178
    raw_data = summary_generator._fetch_raw_game_data(game_pk)

    info = summary_generator._extract_key_info(raw_data)
    summary = summary_generator._generate_llm_summary(info)

    # Generate the summary for the Phillies on 2025-09-05
    # summary: str = summary_generator.generate_summary()
    
    print("\n--- NHL Game Summary ---")
    print(summary)

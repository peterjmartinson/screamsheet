import os
import requests
from lorem_text import lorem
from google import genai
from typing import Optional, Dict, Union, Any, List
from pathlib import Path
import json

# Define the common type for extracted game info
ExtractedInfo = Dict[str, Union[str, int]]


class BaseGameSummaryGenerator:
    """
    Base class for fetching sports game data, extracting key info, 
    and generating a human-readable summary using a Large Language Model.
    """

    _DEFAULT_TEXT: str = lorem.paragraphs(1)
    _MODEL_NAME: str = 'gemini-2.5-flash'

    def __init__(self, gemini_api_key: Optional[str] = None) -> None:
        """Initializes the generator with a Gemini API key."""
        self._use_llm: bool = gemini_api_key is not None
        self._cwd = Path.cwd()

        if self._use_llm:
            self.client: genai.Client = genai.Client(api_key=gemini_api_key)
        else:
            self.client = None

    # --- ABSTRACT METHODS (Must be implemented by subclasses) ---
    def _fetch_raw_game_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetches raw game data from the league API. Args depend on the league."""
        raise NotImplementedError("Subclass must implement abstract method '_fetch_raw_game_data'")

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Parses raw data and extracts essential game details for the LLM."""
        raise NotImplementedError("Subclass must implement abstract method '_extract_key_info'")

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """Constructs the LLM prompt using the extracted game details."""
        raise NotImplementedError("Subclass must implement abstract method '_build_llm_prompt'")
    # -----------------------------------------------------------

    def _generate_llm_summary(self, extracted_info: Union[ExtractedInfo, str]) -> str:
        """Sends extracted data to the LLM and gets a summary (shared logic)."""
        if isinstance(extracted_info, str):
            # If extraction failed, return the error message string
            return extracted_info
        
        # Extracted info is guaranteed to be a Dict here
        prompt: str = self._build_llm_prompt(extracted_info)
        
        if not self._use_llm:
            return self._DEFAULT_TEXT
            
        try:
            response: Any = self.client.models.generate_content(
                model=self._MODEL_NAME,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."

    def generate_summary(self, **kwargs) -> str:
        """Public method to generate the full game summary."""
        raw_data: Optional[Dict[str, Any]] = self._fetch_raw_game_data(**kwargs)
        extracted_info: Union[ExtractedInfo, str] = self._extract_key_info(raw_data)
        llm_summary = self._generate_llm_summary(extracted_info)
        return llm_summary


class GameSummaryGeneratorMLB(BaseGameSummaryGenerator):
    """A class to fetch MLB game data and generate a summary."""

    def _fetch_raw_game_data(self, team_id: int, date_str: str) -> Optional[Dict[str, Any]]:
        """Fetches raw MLB game data using team_id and date_str."""
        schedule_url: str = "https://statsapi.mlb.com/api/v1/schedule"
        params: Dict[str, Union[int, str]] = {'sportId': 1, 'teamId': team_id, 'date': date_str}
        
        try:
            # 1. Get schedule to find gamePk
            schedule_response: requests.Response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data: Dict[str, Any] = schedule_response.json()

            # Safely check for gamePk existence
            game_pk: Optional[int] = None
            if schedule_data.get('totalItems', 0) > 0:
                # Use .get() and safe indexing
                for game in schedule_data.get('dates', [{}])[0].get('games', []):
                    # Check both home and away team IDs
                    away_id = game.get('teams', {}).get('away', {}).get('team', {}).get('id')
                    home_id = game.get('teams', {}).get('home', {}).get('team', {}).get('id')
                    
                    if away_id == team_id or home_id == team_id:
                        game_pk = game.get('gamePk')
                        break
            
            if not game_pk:
                print("No game found for the specified team and date.")
                return None
            
            # 2. Get live game data using gamePk
            game_summary_url: str = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            summary_response: requests.Response = requests.get(game_summary_url)
            summary_response.raise_for_status()
            
            output: Dict[str, Any] = summary_response.json()
            return output

        except requests.exceptions.RequestException as e:
            print(f"Error fetching MLB game data: {e}")
            return None

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Extracts key MLB game details."""
        if not raw_data:
            return "No game data available."
        
        try:
            home_team: str = raw_data['gameData']['teams']['home']['name']
            away_team: str = raw_data['gameData']['teams']['away']['name']
            
            # Use .get() and safe structure navigation for score and plays
            home_score: int = raw_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('home', {}).get('runs', 0)
            away_score: int = raw_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('away', {}).get('runs', 0)
            
            play_by_play_narrative: List[str] = []
            plays: List[Dict[str, Any]] = raw_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            
            for play in plays:
                # Safely get description, defaulting to an empty string if missing
                description = play.get('result', {}).get('description', '')
                if description:
                    play_by_play_narrative.append(description)

            return {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'narrative_snippets': " ".join(play_by_play_narrative)
            }
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing MLB game data: {e}")
            return "Could not parse MLB game details for summary generation."

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """Constructs the LLM prompt for the MLB game."""
        return f"""
        You are a professional sports journalist. Write a concise, engaging
        summary of the following baseball game.  Focus on the final score and a
        few key highlights from each inning, in order.

        Game details:
        Home Team: {extracted_info['home_team']}
        Away Team: {extracted_info['away_team']}
        Final Score: {extracted_info['home_team']} {extracted_info['home_score']}, {extracted_info['away_team']} {extracted_info['away_score']}
        
        Narrative snippets (for context): {extracted_info['narrative_snippets']}

        Provide the summary in a single paragraph.
        """

    def generate_summary(self, team_id: int = 143, date_str: str = "2025-09-05") -> str:
        """
        Public method to generate the full game summary.
        Uses named arguments expected by _fetch_raw_game_data.
        """
        return super()._generate_llm_summary(
            self._extract_key_info(self._fetch_raw_game_data(team_id=team_id, date_str=date_str))
        )

class GameSummaryGeneratorNHL(BaseGameSummaryGenerator):
    """
    A subclass for NHL games, handling player/team lookups and specific play parsing.
    """

    def __init__(self, gemini_api_key: Optional[str] = None) -> None:
        super().__init__(gemini_api_key)
        self._player_map = self._load_map("nhl_players.json")
        self._team_map = self._load_map("nhl_teams.json")

    def _load_map(self, filename: str) -> Dict[str, Any]:
        """Safely loads a JSON file map from the 'documentation' directory."""
        file_path = self._cwd / "documentation" / filename
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Map file not found at {file_path}")
            return {}
        except json.JSONDecodeError:
            print(f"Warning: Error decoding JSON from {file_path}")
            return {}

    def _lookup_player(self, player_id: Optional[int]) -> str:
        """Consolidated and safer player lookup."""
        if player_id is None:
            return "N/A"
            
        # 1. Check in-memory map
        for player in self._player_map:
            if player.get("player_id") == player_id:
                return f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        
        # 2. Fallback to API lookup
        try:
            url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
            res = requests.get(url, timeout=3)
            res.raise_for_status()
            player_info = res.json()
            
            # Use .get() and safe chaining to handle missing keys
            first_name = player_info.get("firstName", {}).get("default", "Unknown")
            last_name = player_info.get("lastName", {}).get("default", "Player")
            return f"{first_name} {last_name}"
        except (requests.exceptions.RequestException, KeyError, json.JSONDecodeError) as ex:
            # print(f"Player {player_id} not found via API: {ex}") # Removed for cleaner output
            return "Unknown Player"

    def _lookup_team(self, team_id: Optional[int]) -> str:
        """Consolidated and safer team lookup."""
        if team_id is None:
            return "N/A Team"
            
        for team in self._team_map.get("data", []):
            if team.get("id") == team_id:
                return team.get("fullName", "Unknown Team")
        return "Unknown Team"

    def _fetch_raw_game_data(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Fetches raw NHL play-by-play data using game_pk."""
        try:
            game_summary_url: str = f"https://api-web.nhle.com/v1/gamecenter/{game_pk}/play-by-play"
            summary_response: requests.Response = requests.get(game_summary_url)
            summary_response.raise_for_status()
            return summary_response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NHL game data: {e}")
            return None

    def _parse_goal(self, details: Dict[str, Any]) -> str:
        """Parses a goal play, handling missing assists and goalie gracefully."""
        scoring_player = self._lookup_player(details.get("scoringPlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        
        # Safely handle missing goalie/empty net
        goalie = self._lookup_player(details.get("goalieInNetId"))
        goalie_text = f"on {goalie}" if goalie != "Unknown Player" else "into an empty net"

        narrative = f"{scoring_player} ({team}) scored {goalie_text}"
        
        assists = []
        if details.get("assist1PlayerId"):
            assists.append(self._lookup_player(details["assist1PlayerId"]))
        if details.get("assist2PlayerId"):
            assists.append(self._lookup_player(details["assist2PlayerId"]))
            
        if assists:
            if len(assists) == 1:
                narrative += f" assisted by {assists[0]}"
            else:
                narrative += f" assisted by {assists[0]} and {assists[1]}"
                
        return narrative

    def _parse_hit(self, details: Dict[str, Any]) -> str:
        """Parses a hit play."""
        hitting_player = self._lookup_player(details.get("hittingPlayerId"))
        hittee_player = self._lookup_player(details.get("hitteePlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        return f"{hitting_player} ({team}) hit {hittee_player}"

    def _parse_penalty(self, details: Dict[str, Any]) -> str:
        """Parses a penalty play, safely handling missing 'drawn by' player."""
        reason = details.get("descKey", "Unknown Reason")
        duration = f'{details.get("duration", 0)} {details.get("typeCode", "min")}'
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        committed_by_player = self._lookup_player(details.get("committedByPlayerId"))
        
        narrative = f"{duration} penalty for {committed_by_player} ({team}) for {reason}"
        
        if drawn_by_id := details.get("drawnByPlayerId"):
            drawn_by_player = self._lookup_player(drawn_by_id)
            narrative += f" (drawn by {drawn_by_player})"
            
        return narrative

    def _parse_shot_on_goal(self, details: Dict[str, Any]) -> str:
        """Parses a shot on goal play."""
        shooting_player = self._lookup_player(details.get("shootingPlayerId"))
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        goalie = self._lookup_player(details.get("goalieInNetId"))
        return f"Shot on goal by {shooting_player} ({team}) saved by {goalie}"

    def _parse_takeaway(self, details: Dict[str, Any]) -> str:
        """Parses a takeaway play."""
        team = self._lookup_team(details.get("eventOwnerTeamId"))
        player = self._lookup_player(details.get("playerId"))
        return f"Takeaway by {player} ({team})"

    def _build_narrative(self, play: Dict[str, Any]) -> str:
        """Combines details into a single narrative string."""
        # Use .get() and default values for robustness
        period = play.get("periodDescriptor", {}).get("number", "N/A")
        time_remaining = play.get("timeRemaining", "0:00")
        
        narrative = f"[Period {period}, {time_remaining}] "
        details = play.get("details", {})
        play_type = play.get("typeDescKey")
        
        parser_map = {
            "goal": self._parse_goal,
            "hit": self._parse_hit,
            "penalty": self._parse_penalty,
            "shot-on-goal": self._parse_shot_on_goal,
            "takeaway": self._parse_takeaway,
        }
        
        description = parser_map.get(play_type, lambda d: f"Unknown play type: {play_type}")(details)
        zone = details.get("zoneCode", "N/A")
        
        narrative += f"{description} in zone {zone}."
        return narrative

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Extracts key NHL game details."""
        if not raw_data:
            return "No game data available."
        
        try:
            # Safely extract team info using .get()
            home_team_data = raw_data.get("homeTeam", {})
            away_team_data = raw_data.get("awayTeam", {})
            
            home_team_name = home_team_data.get("placeName", {}).get("default", "Home") + " " + home_team_data.get("commonName", {}).get("default", "Team")
            away_team_name = away_team_data.get("placeName", {}).get("default", "Away") + " " + away_team_data.get("commonName", {}).get("default", "Team")
            
            # Safely extract scores
            home_score = home_team_data.get("score", 0)
            away_score = away_team_data.get("score", 0)
            
            # Generate narrative
            play_by_play_narrative: List[str] = []
            for play in raw_data.get("plays", []):
                # Only process defined play types
                if play.get("typeDescKey") in ['goal', 'hit', 'penalty', 'shot-on-goal', 'takeaway']:
                    play_by_play_narrative.append(self._build_narrative(play))

            return {
                'home_team': home_team_name,
                'away_team': away_team_name,
                'home_score': home_score,
                'away_score': away_score,
                'narrative_snippets': " ".join(play_by_play_narrative)
            }
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing NHL game data: {e}")
            return "Could not parse NHL game details for summary generation."

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """Constructs the LLM prompt for the NHL game."""
        prompt = f"""
        You are a hilarious sports journalist writing a game recap for a clever
        young hockey fan who loves the sport and wants to laugh while
        learning about what happened. Your reader knows what goals, penalties,
        and power plays are - don't waste words on basics.

        TONE: Funny, witty, and slightly snarky. Use vivid descriptions and
        playful language. Roast bad plays gently (e.g., "that pass had all
        the accuracy of a water balloon thrown backwards"). Celebrate awesome
        moments with enthusiasm (e.g., "that snipe was absolutely FILTHY").
        Include clever wordplay or jokes where appropriate. Make your young
        reader chuckle - be edgy and cheeky but keep it clean (no swear words).

        The entire summary must be 200 words or less in a single continuous
        paragraph of plain text (no markdown, bolding, italics, or special
        formatting). Make it entertaining above all else - this should feel
        like reading a funny story, not a boring news report.

        You must define exactly one obscure or technical hockey term by following
        it with an asterisk (e.g., term*). Choose something interesting like
        'zone exit', 'board battle', 'forechecking pressure', 'odd-man rush',
        'high slot', 'cycle', 'cross-ice pass', or similar tactical/positional
        concepts. Avoid defining basic terms like 'goal', 'penalty', 'hit',
        'shot', 'save', or 'takeaway'. The definition should appear on a
        separate line at the end, prefixed by an asterisk with a brief but
        insightful explanation that a young boy would understand and find
        interesting (e.g., *A zone exit is when...).

        Game details to include:
        Home Team: {extracted_info['home_team']}
        Away Team: {extracted_info['away_team']}
        Final Score: {extracted_info['home_team']} {extracted_info['home_score']} to {extracted_info['away_team']} {extracted_info['away_score']}

        Narrative snippets (for context, include highlights from each period in order): {extracted_info['narrative_snippets']}

        Write the funny, entertaining recap now. Make that us laugh!
        """
        return prompt

    def generate_summary(self, game_pk: int) -> str:
        """
        Public method to generate the full NHL game summary.
        Uses the 'game_pk' argument expected by _fetch_raw_game_data.
        """
        raw_data = self._fetch_raw_game_data(game_pk=game_pk)
        key_info = self._extract_key_info(raw_data)
        result = super()._generate_llm_summary(key_info)
        return result


class GameSummaryGeneratorNBA(BaseGameSummaryGenerator):
    """
    A subclass for NBA games, handling player/team lookups and specific play parsing.
    """

    def __init__(self, gemini_api_key: Optional[str] = None) -> None:
        super().__init__(gemini_api_key)

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """Constructs the LLM prompt for the NHL game."""
        prompt = f"""
        You are a professional news correspondent writing a concise game
        summary of an NBA basketball match. The summary must be professional
        yet extremely accessible, ensuring the language is easy enough for
        someone with a reading comprehension level below the 5th grade or with
        no prior knowledge of basketball.  The entire summary must be 200 words
        or less and consist of a single, continuous paragraph of plain text (no
        markdown, bolding, italics, or special formatting).

        The summary must define only one important basketball term used in the
        text. To ensure the reader learns new vocabulary, prioritize choosing a
        term that is not 'score', 'foul', 'rebound', 'shot', or 'basket/point',
        unless those terms are the only important ones available in the text.
        Indicate the defined term within the main text by following it
        immediately with an asterisk (e.g., term*). The definition must appear
        on a separate line at the very end of the summary, prefixed by an
        asterisk and explaining the term clearly for a novice (e.g., *In
        basketball, [term] is...).

        Game details to include:
        Home Team: {extracted_info['home_team']}
        Away Team: {extracted_info['away_team']}
        Final Score: {extracted_info['home_team']} {extracted_info['home_score']} to {extracted_info['away_team']} {extracted_info['away_score']}

        Narrative snippets (for context, include highlights from each period in order): {extracted_info['narrative_snippets']}

        Write the professional and accessible recap now.
        """
        return prompt


class NewsStorySummarizer(BaseGameSummaryGenerator):
    """
    A subclass to use the LLM to generate news summaries
    """

    # def __init__(self, gemini_api_key: Optional[str] = None) -> None:
    #     super().__init__(gemini_api_key)

    def get_accessible_summary(self, title, content):
        """
        Generates a professional, accessible summary of a news article using the Gemini API.
        
        This function uses the finalized prompt template tailored for accessibility and
        selective term definition (avoiding common words like 'goal', 'foul', 'shot', etc.).
        """
        
        # --- The Finalized NBA/General Sports Prompt ---
        # We use a general prompt and pass in placeholders for generic content slots
        # since this isn't a score recap, but a news summary.
        prompt = f"""
            You are a professional news correspondent writing a concise,
            engaging summary of a sports news article.  Focus on getting as
            much detail as possible into the summary, while retaining clarity
            and readability.

            The entire summary must be 300 words or less and consist of a
            single, continuous paragraph of plain text (no markdown, bolding,
            italics, or special formatting).

            **Article Title:** {title}
            **Article Content:** {content}
            
            Write the professional and accessible recap now.
        """
        
        try:
            response: Any = self.client.models.generate_content(
                model=self._MODEL_NAME,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return f"ERROR: Could not summarize article titled '{title}'."


# Example Usage in your main script
if __name__ == "__main__":
    # Instantiate the class
    summary_generator: GameSummaryGeneratorNHL = GameSummaryGeneratorNHL()
    game_pk = 2025020178
    raw_data = summary_generator._fetch_raw_game_data(game_pk)

    info = summary_generator._extract_key_info(raw_data)
    summary = summary_generator._generate_llm_summary(info)

    # Generate the summary for the Phillies on 2025-09-05
    # summary: str = summary_generator.generate_summary()
    
    print("\n--- NHL Game Summary ---")
    print(summary)

import os
import requests
from lorem_text import lorem
from google import genai

class GameSummaryGenerator:
    """
    A class to fetch MLB game data and generate a human-readable summary
    using a Large Language Model.
    """

    _use_default_text = True
    _default_text = lorem.paragraphs(1)

    def __init__(self, gemini_api_key=None):
        """
        Initializes the generator with a Gemini API key.
        """
        if gemini_api_key is not None:
            self._use_default_text = False
            self.client = genai.Client(api_key=gemini_api_key)
            self.model_name = 'gemini-2.5-flash' 
        else:
            self._use_default_text = True
            self.client = None
            self.model_name = None

    def _fetch_raw_game_data(self, team_id, date_str):
        """
        Internal method to get the raw JSON data for a specific game.
        """
        schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
        params = {'sportId': 1, 'teamId': team_id, 'date': date_str}
        
        try:
            schedule_response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data = schedule_response.json()

            game_pk = None
            if 'dates' in schedule_data and schedule_data['dates']:
                for game in schedule_data['dates'][0]['games']:
                    if game['teams']['away']['team']['id'] == team_id or game['teams']['home']['team']['id'] == team_id:
                        game_pk = game['gamePk']
                        break
            
            if not game_pk:
                return None
            
            game_summary_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            summary_response = requests.get(game_summary_url)
            summary_response.raise_for_status()
            
            output = summary_response.json()
            print(output)
            return output

        except requests.exceptions.RequestException as e:
            print(f"Error fetching game data: {e}")
            return None

    def _extract_key_info(self, raw_data):
        """
        Internal method to parse and extract key game events.
        """
        if not raw_data:
            return "No game data available."
        
        try:
            home_team = raw_data['gameData']['teams']['home']['name']
            away_team = raw_data['gameData']['teams']['away']['name']
            
            # Use 'linescore' to get the final score
            home_score = raw_data['liveData']['linescore']['teams']['home']['runs']
            away_score = raw_data['liveData']['linescore']['teams']['away']['runs']
            
            # A simple way to get some play-by-play narrative
            play_by_play_narrative = []
            plays = raw_data['liveData']['plays']['allPlays']
            for play in plays:#[:10]: # Limiting to the first 10 for conciseness
                play_by_play_narrative.append(play['result']['description'])

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

    def _generate_llm_summary(self, extracted_info):
        """
        Internal method to send extracted data to the LLM and get a summary.
        """
        if isinstance(extracted_info, str):
            return extracted_info

        prompt = f"""
        You are a professional sports journalist. Write a concise, engaging summary of the following baseball game. 
        Focus on the final score and a few key highlights from each inning, in order.

        Game details:
        Home Team: {extracted_info['home_team']}
        Away Team: {extracted_info['away_team']}
        Final Score: {extracted_info['home_team']} {extracted_info['home_score']}, {extracted_info['away_team']} {extracted_info['away_score']}
        
        Narrative snippets (for context): {extracted_info['narrative_snippets']}

        Provide the summary in a single paragraph.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."

    def generate_summary(self, team_id=143, date_str="2025-09-05"):
        """
        Public method to generate the full game summary.
        
        Args:
            team_id (int): The MLB team ID (e.g., 143 for Phillies).
            date_str (str): The date in 'YYYY-MM-DD' format.
        
        Returns:
            str: A formatted game summary from the LLM.
        """
        llm_summary = self._default_text
        if not self._use_default_text:
            raw_data = self._fetch_raw_game_data(team_id, date_str)
            extracted_info = self._extract_key_info(raw_data)
            llm_summary = self._generate_llm_summary(extracted_info)
        return llm_summary

# Example Usage in your main script
if __name__ == "__main__":
    # You would need to have your GEMINI_API_KEY set as an environment variable
    # or pass it directly to the constructor.
    # For example: export GEMINI_API_KEY='your-key-here' in your terminal
    
    # Instantiate the class
    summary_generator = GameSummaryGenerator()

    # Generate the summary for the Phillies on 2025-09-05
    # The default arguments match your request
    summary = summary_generator.generate_summary()
    
    print("\n--- MLB Game Summary ---")
    print(summary)

"""MLB data provider for fetching MLB game data."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

from ..base import DataProvider


class MLBDataProvider(DataProvider):
    """
    Data provider for MLB using the MLB Stats API.
    
    Provides access to:
    - Game scores
    - League standings
    - Box scores
    - Game summaries (via LLM)
    """
    
    def __init__(self, **config):
        super().__init__(**config)
        self.base_url = "https://statsapi.mlb.com"
    
    def get_game_scores(self, date: datetime) -> list:
        """
        Get MLB game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        game_date = date.strftime("%Y-%m-%d")
        
        url = (
            f"{self.base_url}/api/v1/schedule"
            f"?sportId=1"
            f"&startDate={game_date}"
            f"&endDate={game_date}"
        )
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for date_data in data.get("dates", []):
            for game in date_data.get("games", []):
                game_info = {
                    "gameDate": game.get("gameDate"),
                    "away_team": game["teams"]["away"]["team"]["name"],
                    "home_team": game["teams"]["home"]["team"]["name"],
                    "away_score": game["teams"]["away"].get("score"),
                    "home_score": game["teams"]["home"].get("score"),
                    "status": game["status"]["detailedState"]
                }
                games.append(game_info)
        return games
    
    def get_standings(self, season: int = None) -> pd.DataFrame:
        """
        Get current MLB league standings.

        Args:
            season: The season year (defaults to current year). During spring
                    training the API returns all teams with 0-0 records, which
                    is the correct thing to display.

        Returns:
            DataFrame with standings data
        """
        if season is None:
            season = datetime.now().year

        url = f"{self.base_url}/api/v1/standings?season={season}&leagueId=103,104"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        team_list = []
        for record in data.get("records", []):
            division = self._get_division(record)
            for team in record.get("teamRecords", []):
                team_obj = {
                    "division": division,
                    "team": team.get("team", {}).get("name"),
                    "wins": team["leagueRecord"].get("wins"),
                    "losses": team["leagueRecord"].get("losses"),
                    "ties": team["leagueRecord"].get("ties"),
                    "pct": team["leagueRecord"].get("pct"),
                    "divisionRank": team.get("divisionRank")
                }
                team_list.append(team_obj)
        
        if not team_list:
            print(f"Warning: No MLB standings data found for season {season}")
            return pd.DataFrame()
        
        standings = pd.DataFrame(team_list)
        
        # Check if required columns exist before sorting
        if 'division' in standings.columns and 'divisionRank' in standings.columns:
            return standings.sort_values(
                by=['division', 'divisionRank'],
                ascending=[True, True]
            )
        else:
            print(f"Warning: MLB standings missing expected columns. Available: {standings.columns.tolist()}")
            return standings
    
    def _get_division(self, record: Dict) -> str:
        """Get division name from a standings record."""
        try:
            url = self.base_url + record.get("division", {}).get("link", "")
            if not url or url == self.base_url:
                return "Unknown Division"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("divisions", [{}])[0].get("name", "Unknown Division")
        except Exception as e:
            print(f"Warning: Error getting division name: {e}")
            return "Unknown Division"
    
    def get_box_score(self, team_id: int, date: datetime) -> Optional[Any]:
        """
        Get box score for a specific team and date.
        
        Args:
            team_id: The MLB team ID
            date: The date to fetch box score for
            
        Returns:
            Box score data or None if not available
        """
        try:
            game_date = date.strftime("%Y-%m-%d")

            # Find the game PK for this team and date
            schedule_url = f"{self.base_url}/api/v1/schedule"
            params = {'sportId': 1, 'teamId': team_id, 'date': game_date}
            schedule_response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data = schedule_response.json()

            game_pk = None
            if 'dates' in schedule_data and schedule_data['dates']:
                for game in schedule_data['dates'][0]['games']:
                    if game['status']['statusCode'] == 'F':
                        if (game['teams']['away']['team']['id'] == team_id or
                                game['teams']['home']['team']['id'] == team_id):
                            game_pk = game['gamePk']
                            break

            if not game_pk:
                print(f"No completed game found for team ID {team_id} on {game_date}.")
                return None

            # Fetch the detailed box score
            boxscore_url = f"{self.base_url}/api/v1/game/{game_pk}/boxscore"
            boxscore_response = requests.get(boxscore_url)
            boxscore_response.raise_for_status()
            boxscore_data = boxscore_response.json()

            if not boxscore_data:
                return {'batting_stats': [], 'pitching_stats': []}

            # Parse batting and pitching stats for the target team
            home_team_id = boxscore_data['teams']['home']['team']['id']
            target_team = 'home' if home_team_id == team_id else 'away'
            players = boxscore_data['teams'][target_team]['players']

            batting_stats = []
            pitching_stats = []

            for player_data in players.values():
                if player_data['stats'].get('batting'):
                    stats = player_data['stats']['batting']
                    batting_stats.append({
                        'name': player_data['person']['fullName'],
                        'AB': stats.get('atBats', 0),
                        'R': stats.get('runs', 0),
                        'H': stats.get('hits', 0),
                        'HR': stats.get('homeRuns', 0),
                        'RBI': stats.get('rbi', 0),
                        'BB': stats.get('baseOnBalls', 0),
                        'SO': stats.get('strikeOuts', 0),
                    })
                if player_data['stats'].get('pitching'):
                    stats = player_data['stats']['pitching']
                    pitching_stats.append({
                        'name': player_data['person']['fullName'],
                        'IP': stats.get('inningsPitched', '0.0'),
                        'H': stats.get('hits', 0),
                        'R': stats.get('runs', 0),
                        'ER': stats.get('earnedRuns', 0),
                        'BB': stats.get('baseOnBalls', 0),
                        'SO': stats.get('strikeOuts', 0),
                    })

            return {'batting_stats': batting_stats, 'pitching_stats': pitching_stats}
        except Exception as e:
            print(f"Error getting MLB box score: {e}")
            return None
    
    def get_game_summary(self, team_id: int, date: datetime) -> Optional[str]:
        """
        Get game summary for a specific team and date.
        
        Args:
            team_id: The MLB team ID
            date: The date to fetch summary for
            
        Returns:
            Game summary text or None if not available
        """
        # Import here to avoid circular dependency
        try:
            import os
            from .extractors import MLBGameExtractor
            from ..llm.summary import MLBGameSummarizer
            date_str = date.strftime("%Y-%m-%d")
            extractor = MLBGameExtractor()
            extracted = extractor.extract_key_info(extractor.fetch_raw_data(team_id, date_str))
            if isinstance(extracted, str):
                return extracted
            summarizer = MLBGameSummarizer(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                grok_api_key=os.getenv("GROK_API_KEY")
            )
            return summarizer.generate_summary(llm_choice='gemini', data=extracted)
        except Exception as e:
            print(f"Error getting MLB game summary: {e}")
            return None

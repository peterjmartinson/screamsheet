"""NHL data provider for fetching NHL game data."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

from ..base import DataProvider

try:
    from src.screamsheet_structures import GameScore
    from src.utilities import dump_json
except:
    from ...screamsheet_structures import GameScore
    from ...utilities import dump_json


class NHLDataProvider(DataProvider):
    """
    Data provider for NHL using the NHL API.
    
    Provides access to:
    - Game scores
    - League standings
    - Box scores
    - Game summaries (via LLM)
    """
    
    FINAL_STATUS_CODE = 'OFF'
    
    def __init__(self, **config):
        super().__init__(**config)
        self.base_url = "https://api-web.nhle.com/v1"
        self.dump = config.get('dump', False)
    
    def get_game_scores(self, date: datetime) -> List[Dict]:
        """
        Get NHL game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        game_date = date.strftime("%Y-%m-%d")
        url = f"{self.base_url}/schedule/{game_date}"
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if self.dump:
            dump_json(response, "nhl_game_scores")
        
        games = []
        games_for_the_day = data.get('gameWeek', [{}])[0].get('games', [])
        
        for game in games_for_the_day:
            game_state = game['gameState']
            
            if game_state in ['FINAL', 'OFF', 'LIVE']:
                away_place_name = game['awayTeam']['placeName']['default']
                home_place_name = game['homeTeam']['placeName']['default']
                away_team_name = game['awayTeam']['commonName']['default']
                home_team_name = game['homeTeam']['commonName']['default']
                
                away_full_name = f"{away_place_name} {away_team_name}"
                home_full_name = f"{home_place_name} {home_team_name}"
                
                away_score_raw = game['awayTeam'].get('score')
                home_score_raw = game['homeTeam'].get('score')
                away_score = int(away_score_raw) if away_score_raw is not None else 0
                home_score = int(home_score_raw) if home_score_raw is not None else 0
                
                game_info = {
                    "gameDate": game.get('startTimeUTC'),
                    "away_team": away_full_name,
                    "home_team": home_full_name,
                    "away_score": away_score,
                    "home_score": home_score,
                    "status": game_state
                }
                games.append(game_info)
        
        return games
    
    def get_standings(self) -> pd.DataFrame:
        """
        Get current NHL league standings.
        
        Returns:
            DataFrame with standings data
        """
        url = f"{self.base_url}/standings/now"
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if self.dump:
            dump_json(response, "nhl_standings")
        
        team_list: List[Dict[str, Any]] = []
        
        for team_record in data.get("standings", []):
            name = team_record.get("teamName", {}).get("default")
            division = team_record.get("divisionName")
            conference = team_record.get("conferenceName")
            
            team_obj = {
                "conference": conference,
                "division": division,
                "team": name,
                "divisionRank": team_record.get("divisionSequence"),
                "GP": team_record.get("gamesPlayed"),
                "W": team_record.get("wins"),
                "L": team_record.get("losses"),
                "OTL": team_record.get("otLosses"),
                "P": team_record.get("points"),
                "PCT": team_record.get("pointPctg"),
                "GF": team_record.get("goalFor"),
                "GA": team_record.get("goalAgainst"),
                "DIFF": team_record.get("goalDifferential"),
                "STRK": team_record.get("streakCode") + str(team_record.get("streakCount"))
            }
            team_list.append(team_obj)
        
        standings = pd.DataFrame(team_list)
        return standings.sort_values(
            by=['conference', 'division', 'divisionRank'],
            ascending=[True, True, True]
        ).reset_index(drop=True)
    
    def get_box_score(self, team_id: int, date: datetime) -> Optional[Any]:
        """
        Get box score for a specific team and date.
        
        Args:
            team_id: The NHL team ID
            date: The date to fetch box score for
            
        Returns:
            Box score data or None if not available
        """
        try:
            from src.get_box_score_nhl import get_nhl_boxscore
            game_pk = self._get_game_pk(team_id, date)
            if game_pk:
                return get_nhl_boxscore(team_id, game_pk)
            return None
        except Exception as e:
            print(f"Error getting NHL box score: {e}")
            return None
    
    def get_game_summary(self, team_id: int, date: datetime) -> Optional[str]:
        """
        Get game summary for a specific team and date.
        
        Args:
            team_id: The NHL team ID
            date: The date to fetch summary for
            
        Returns:
            Game summary text or None if not available
        """
        try:
            import os
            from src.get_game_summary import GameSummaryGeneratorNHL
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            generator = GameSummaryGeneratorNHL(gemini_api_key)
            game_pk = self._get_game_pk(team_id, date)
            if game_pk:
                return generator.generate_summary(game_pk)
            return None
        except Exception as e:
            print(f"Error getting NHL game summary: {e}")
            return None
    
    def _get_game_pk(self, team_id: int, date: datetime) -> Optional[int]:
        """
        Get the game PK for a specific team and date.
        
        Args:
            team_id: The NHL team ID
            date: The date to fetch game PK for
            
        Returns:
            Game PK or None if not found
        """
        game_date_str = date.strftime('%Y-%m-%d')
        schedule_url = f"{self.base_url}/schedule/{game_date_str}"
        
        try:
            schedule_response = requests.get(schedule_url)
            schedule_response.raise_for_status()
            schedule_data = schedule_response.json()
            
            if self.dump:
                dump_json(schedule_response, "nhl_get_game_pk")
            
            game_pk = None
            
            if 'gameWeek' in schedule_data and schedule_data['gameWeek']:
                for day in schedule_data['gameWeek']:
                    for game in day.get('games', []):
                        if str(game['gameState']) == self.FINAL_STATUS_CODE:
                            home_id = game['homeTeam']['id']
                            away_id = game['awayTeam']['id']
                            
                            if home_id == team_id or away_id == team_id:
                                game_pk = game['id']
                                break
                    if game_pk:
                        return game_pk
            
            if not game_pk:
                print(f"No completed game found for team ID {team_id} on {game_date_str}.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NHL data: {e}")
            return None

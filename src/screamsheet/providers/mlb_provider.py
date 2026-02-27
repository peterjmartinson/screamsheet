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
            season: The season year (defaults to current year)
            
        Returns:
            DataFrame with standings data
        """
        if season is None:
            season = datetime.now().year
            # If we're in early year (Jan-Mar) and current season has no data,
            # try previous year
            if datetime.now().month <= 3:
                # Try current year first
                url = f"{self.base_url}/api/v1/standings?season={season}&leagueId=103,104"
                response = requests.get(url)
                if response.ok:
                    data = response.json()
                    if not data.get("records", []):
                        # No data for current year, use previous year
                        season = season - 1
                        print(f"No MLB data for {season + 1}, using {season} season")
        
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
        # Import here to avoid circular dependency
        try:
            from get_box_score import get_box_score
            game_date = date.strftime("%Y-%m-%d")
            return get_box_score(team_id, game_date)
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
            from get_game_summary import GameSummaryGeneratorMLB
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            generator = GameSummaryGeneratorMLB(gemini_api_key)
            date_str = date.strftime("%Y-%m-%d")
            return generator.generate_summary(team_id, date_str)
        except Exception as e:
            print(f"Error getting MLB game summary: {e}")
            return None

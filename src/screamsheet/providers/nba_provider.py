"""NBA data provider for fetching NBA game data."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

from ..base import DataProvider

try:
    from nba_api.stats.endpoints import leaguegamefinder, leaguestandings
    from nba_api.stats.static import teams
except ImportError:
    print("Warning: nba_api package not installed. NBA provider will have limited functionality.")


class NBADataProvider(DataProvider):
    """
    Data provider for NBA using the nba_api package.
    
    Provides access to:
    - Game scores
    - League standings
    
    Note: Box scores and game summaries not yet fully implemented for NBA.
    """
    
    def __init__(self, **config):
        super().__init__(**config)
    
    def get_game_scores(self, date: datetime) -> list:
        """
        Get NBA game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        try:
            # Use nba_api to get games for the date
            date_str = date.strftime("%Y-%m-%d")
            
            # Get all games from league game finder
            gamefinder = leaguegamefinder.LeagueGameFinder(
                date_from_nullable=date_str,
                date_to_nullable=date_str
            )
            games_df = gamefinder.get_data_frames()[0]
            
            if games_df.empty:
                return []
            
            # Process games - note that each game appears twice (once for each team)
            games = []
            seen_game_ids = set()
            
            for _, row in games_df.iterrows():
                game_id = row['GAME_ID']
                if game_id in seen_game_ids:
                    continue
                seen_game_ids.add(game_id)
                
                # Get both teams' data for this game
                game_data = games_df[games_df['GAME_ID'] == game_id]
                
                if len(game_data) >= 2:
                    teams_data = game_data.iloc[:2]
                    
                    game_info = {
                        "gameDate": row['GAME_DATE'],
                        "away_team": teams_data.iloc[1]['TEAM_NAME'],
                        "home_team": teams_data.iloc[0]['TEAM_NAME'],
                        "away_score": int(teams_data.iloc[1]['PTS']),
                        "home_score": int(teams_data.iloc[0]['PTS']),
                        "status": "Final"
                    }
                    games.append(game_info)
            
            return games
        except Exception as e:
            print(f"Error getting NBA game scores: {e}")
            return []
    
    def get_standings(self) -> pd.DataFrame:
        """
        Get current NBA league standings.
        
        Returns:
            DataFrame with standings data
        """
        try:
            standings = leaguestandings.LeagueStandings()
            standings_df = standings.get_data_frames()[0]
            
            # Simplify to key columns
            if not standings_df.empty:
                standings_df = standings_df[[
                    'Conference',
                    'TeamName',
                    'WINS',
                    'LOSSES',
                    'WinPCT',
                    'ConferenceRecord',
                    'DivisionRank'
                ]].copy()
                
                standings_df.columns = [
                    'conference',
                    'team',
                    'wins',
                    'losses',
                    'pct',
                    'conf_record',
                    'division_rank'
                ]
                
                return standings_df.sort_values(
                    by=['conference', 'pct'],
                    ascending=[True, False]
                ).reset_index(drop=True)
            
            return pd.DataFrame()
        except Exception as e:
            print(f"Error getting NBA standings: {e}")
            return pd.DataFrame()

"""NFL data provider for fetching NFL game data."""
import requests
import pandas as pd
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, List, Dict

from ..base import DataProvider


class NFLDataProvider(DataProvider):
    """
    Data provider for NFL using the ESPN API.
    
    Provides access to:
    - Game scores (by week)
    - League standings
    
    Note: Box scores and game summaries not yet implemented for NFL.
    """
    
    def __init__(self, **config):
        super().__init__(**config)
        self.base_url = "http://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self.current_season = self._get_current_season()
        self.current_week = self._get_current_week()
    
    def get_game_scores(self, date: datetime = None) -> list:
        """
        Get NFL game scores for the current week.
        
        Note: NFL games are organized by week, not by specific date.
        The date parameter is used only to determine the season/week.
        
        Args:
            date: The date (used to determine week)
            
        Returns:
            List of game score dictionaries
        """
        if self.current_week is None:
            return []
        
        return self._get_weekly_scores(
            self.current_season,
            self.current_week,
            previous_week=False
        )
    
    def get_standings(self) -> pd.DataFrame:
        """
        Get current NFL league standings.
        
        Returns:
            DataFrame with standings data
        """
        season = self.current_season
        base_standings_url = (
            f"https://sports.core.api.espn.com/v2/sports/football/"
            f"leagues/nfl/seasons/{season}/types/2/groups/"
        )
        conferences = {7: "NFC", 8: "AFC"}
        all_standings = []
        
        # Get team name lookup
        team_name_lookup = self._get_team_name_lookup()
        id_pattern = re.compile(r"/teams/(\d+)")
        
        for group_id, conference_name in conferences.items():
            url = f"{base_standings_url}{group_id}/standings/0"
            
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching standings for {conference_name}: {e}")
                continue
            
            for team_entry in data.get("standings", []):
                # Extract team ID from URL reference
                team_ref = team_entry.get("team", {}).get("$ref", "")
                match = id_pattern.search(team_ref)
                if not match:
                    continue
                
                team_id = int(match.group(1))
                team_name = team_name_lookup.get(team_id, f"Team {team_id}")
                
                # Get stats
                stats = team_entry.get("stats", [])
                stat_dict = {stat["name"]: stat["value"] for stat in stats}
                
                team_obj = {
                    "conference": conference_name,
                    "team": team_name,
                    "wins": stat_dict.get("wins", 0),
                    "losses": stat_dict.get("losses", 0),
                    "ties": stat_dict.get("ties", 0),
                    "winPercent": stat_dict.get("winPercent", 0.0),
                    "pointDifferential": stat_dict.get("pointDifferential", 0),
                    "divisionWinPercent": stat_dict.get("divisionWinPercent", 0.0),
                }
                all_standings.append(team_obj)
        
        standings = pd.DataFrame(all_standings)
        return standings.sort_values(
            by=['conference', 'winPercent'],
            ascending=[True, False]
        ).reset_index(drop=True)
    
    def _get_team_name_lookup(self) -> Dict[int, str]:
        """Get a lookup dictionary of team ID to team name."""
        teams_url = f"{self.base_url}/teams"
        team_name_lookup = {}
        
        try:
            response = requests.get(teams_url)
            response.raise_for_status()
            data = response.json()
            
            teams_list = data.get("sports", [])[0].get("leagues", [])[0].get("teams", [])
            for team_entry in teams_list:
                team_info = team_entry.get("team", {})
                team_id = int(team_info.get("id"))
                display_name = team_info.get("displayName")
                if team_id and display_name:
                    team_name_lookup[team_id] = display_name
        except (IndexError, ValueError, requests.exceptions.RequestException) as e:
            print(f"Error getting team names: {e}")
        
        return team_name_lookup
    
    def _get_current_season(self) -> int:
        """Determine the current NFL season year."""
        now = datetime.now(timezone.utc)
        this_year = now.year
        prev_year = this_year - 1
        
        url = f"{self.base_url}/scoreboard?dates={prev_year}&seasontype=2"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            calendar = data.get("leagues", [])[0].get("calendar", [])
            
            latest_end = None
            for period in calendar:
                end_date_str = period.get("endDate")
                if not end_date_str:
                    continue
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                if latest_end is None or end_date > latest_end:
                    latest_end = end_date
            
            if latest_end is not None:
                return prev_year if now <= latest_end else this_year
        except requests.exceptions.RequestException:
            pass
        
        # Fallback: Jan/Feb => previous season
        return prev_year if now.month in (1, 2) else this_year
    
    def _get_current_week(self) -> Optional[Dict]:
        """Get information about the current NFL week."""
        season = self.current_season
        url = f"{self.base_url}/scoreboard?dates={season}&seasontype=2"
        now = datetime.now(timezone.utc)
        
        week_info = {
            "SeasonName": "",
            "SeasonValue": 0,
            "WeekName": "",
            "WeekDetail": "",
            "WeekValue": 0
        }
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching scoreboard data: {e}")
            return None
        
        calendar = data["leagues"][0]["calendar"]
        
        for period in calendar:
            start_date = datetime.fromisoformat(period["startDate"].replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(period["endDate"].replace('Z', '+00:00'))
            if start_date <= now <= end_date:
                week_info["SeasonName"] = period["label"]
                week_info["SeasonValue"] = period["value"]
                for week in period["entries"]:
                    week_start = datetime.fromisoformat(week["startDate"].replace('Z', '+00:00'))
                    week_end = datetime.fromisoformat(week["endDate"].replace('Z', '+00:00'))
                    if week_start <= now <= week_end:
                        week_info["WeekName"] = week["label"]
                        week_info["WeekDetail"] = week["detail"]
                        week_info["WeekValue"] = week["value"]
        
        return week_info if week_info["WeekValue"] != 0 else None
    
    def _get_weekly_scores(
        self,
        season_year: int,
        week_info: Dict,
        previous_week: bool = False
    ) -> list:
        """Get NFL game scores for a specific week."""
        season = week_info["SeasonValue"]
        week = int(week_info["WeekValue"])
        
        if previous_week:
            if week - 1 == 0:
                print(f"First week of {week_info['SeasonName']}")
                return []
            week = week - 1
            print("Getting previous week's games")
        
        url = (
            f"{self.base_url}/scoreboard"
            f"?dates={season_year}"
            f"&seasontype={season}"
            f"&week={week}"
        )
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from ESPN API: {e}")
            return []
        
        games = []
        for event in data.get("events", []):
            competitions = event.get("competitions", [])
            if competitions:
                game = competitions[0]
                
                if game.get("status", {}).get("type", {}).get("name") == "STATUS_FINAL":
                    home_team = game["competitors"][0]
                    away_team = game["competitors"][1]
                    
                    game_info = {
                        "gameId": event.get("id"),
                        "gameDate": event.get("date"),
                        "away_team": away_team["team"]["displayName"],
                        "away_score": away_team.get("score"),
                        "home_team": home_team["team"]["displayName"],
                        "home_score": home_team.get("score"),
                        "status": game["status"]["type"]["name"]
                    }
                    games.append(game_info)
        
        return games

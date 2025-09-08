import pandas as pd
import requests
from datetime import datetime, timedelta
import json

class MLBDataFetcher:
    """
    Handles all data retrieval from the MLB stats API.
    """
    BASE_URL = "https://statsapi.mlb.com"

    def get_division_name(self, record: dict) -> str:
        """Fetches the division name from a given record link."""
        url = self.BASE_URL + record.get("division", {}).get("link", {})
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data["divisions"][0].get("name")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching division data: {e}")
            return "Unknown Division"

    def get_scores_last_24_hours(self, filename: str = None) -> list:
        """Fetches game scores from the last 24 hours."""
        if filename:
            return self.get_scores_from_file(filename)
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        start_date = yesterday.strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
        url = (
            f"{self.BASE_URL}/api/v1/schedule"
            f"?sportId=1"
            f"&startDate={start_date}"
            f"&endDate={end_date}"
        )
        try:
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
                    if game_info["away_score"] is not None and game_info["home_score"] is not None:
                         games.append(game_info)
            return games
        except requests.exceptions.RequestException as e:
            print(f"Error fetching game scores: {e}")
            return []

    def get_scores_from_file(self, filename: str) -> list:
        scores_list = []
        with open(filename, "r") as file:
            scores_list = json.load(file)
        return scores_list

    def get_standings(self, season: int = 2025, filename: str = None) -> pd.DataFrame:
        """Fetches current league standings."""
        if filename:
            return self.get_standings_from_file(filename)
        url = f"{self.BASE_URL}/api/v1/standings?season={season}&leagueId=103,104"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            team_list = []
            for record in data.get("records", []):
                division = self.get_division_name(record)
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
            standings = pd.DataFrame(team_list)
            return standings.sort_values(by=['division', 'divisionRank'])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching standings: {e}")
            return pd.DataFrame()

    def get_standings_from_file(self, filename) -> pd.DataFrame:
        standings_df = pd.read_csv(filename)
        return standings_df

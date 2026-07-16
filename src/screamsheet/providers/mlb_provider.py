"""MLB data provider for fetching MLB game data."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple

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
    
    def _get_game_pk(self, team_id: int, date: datetime) -> Optional[int]:
        """Return the gamePk for a completed game on date, or None."""
        game_date = date.strftime("%Y-%m-%d")
        schedule_url = f"{self.base_url}/api/v1/schedule"
        params = {'sportId': 1, 'teamId': team_id, 'date': game_date}
        schedule_response = requests.get(schedule_url, params=params)
        schedule_response.raise_for_status()
        schedule_data = schedule_response.json()

        if 'dates' in schedule_data and schedule_data['dates']:
            for game in schedule_data['dates'][0]['games']:
                status = game.get('status', {})
                if status.get('abstractGameCode') == 'F' or 'Final' in status.get('detailedState', ''):
                    if (game['teams']['away']['team']['id'] == team_id or
                            game['teams']['home']['team']['id'] == team_id):
                        return game['gamePk']
        return None

    def _get_game_pk_by_type(self, game_type: str, date: datetime) -> Optional[int]:
        """Return the gamePk for a completed game of a specific gameType on date, or None."""
        game_date = date.strftime("%Y-%m-%d")
        schedule_url = f"{self.base_url}/api/v1/schedule"
        params = {'sportId': 1, 'gameType': game_type, 'date': game_date}
        try:
            schedule_response = requests.get(schedule_url, params=params)
            schedule_response.raise_for_status()
            schedule_data = schedule_response.json()
            if 'dates' in schedule_data and schedule_data['dates']:
                for game in schedule_data['dates'][0]['games']:
                    status = game.get('status', {})
                    if status.get('abstractGameCode') == 'F' or 'Final' in status.get('detailedState', ''):
                        return game['gamePk']
        except Exception as e:
            print(f"Error getting gamePk for type {game_type}: {e}")
        return None

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Return True if the team played a completed game on the given date."""
        try:
            return self._get_game_pk(team_id, date) is not None
        except Exception:
            return False

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (team_id, team_name) for all completed games on date."""
        game_date = date.strftime("%Y-%m-%d")
        url = (
            f"{self.base_url}/api/v1/schedule"
            f"?sportId=1"
            f"&startDate={game_date}"
            f"&endDate={game_date}"
        )
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching MLB schedule for fallback: {e}")
            return []

        teams: List[Tuple[int, str]] = []
        for date_data in data.get("dates", []):
            for game in date_data.get("games", []):
                if "Final" not in game["status"]["detailedState"]:
                    continue
                away = game["teams"]["away"]["team"]
                home = game["teams"]["home"]["team"]
                teams.append((int(away["id"]), str(away["name"])))
                teams.append((int(home["id"]), str(home["name"])))
        return teams

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

            game_pk = self._get_game_pk(team_id, date)

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
    
    def get_game_summary(self, team_id: int, date: datetime, is_primary_favorite: bool = False) -> Optional[str]:
        """
        Get game summary for a specific team and date.

        When ``is_primary_favorite`` is True and the featured team lost, the
        summary uses the angry-fan rant persona instead of the neutral recap.

        Args:
            team_id: The MLB team ID
            date: The date to fetch summary for
            is_primary_favorite: True when this is the #1 priority team
            
        Returns:
            Game summary text or None if not available
        """
        # Import here to avoid circular dependency
        try:
            import os
            from .extractors import MLBGameExtractor
            from ..llm.summary import MLBGameSummarizer, MLBFanRantSummarizer
            date_str = date.strftime("%Y-%m-%d")
            extractor = MLBGameExtractor()
            raw = extractor.fetch_raw_data(team_id, date_str)
            extracted = extractor.extract_key_info(raw)
            if isinstance(extracted, str):
                return extracted

            use_rant = False
            losing_team: Optional[str] = None
            if is_primary_favorite and raw:
                home_id = (
                    raw.get("gameData", {}).get("teams", {}).get("home", {}).get("id")
                )
                home_score = int(extracted["home_score"])
                away_score = int(extracted["away_score"])
                if home_id == team_id:
                    team_won = home_score > away_score
                    losing_team = str(extracted["home_team"])
                else:
                    team_won = away_score > home_score
                    losing_team = str(extracted["away_team"])
                use_rant = not team_won

            if use_rant and losing_team is not None:
                summarizer: MLBGameSummarizer = MLBFanRantSummarizer(
                    gemini_api_key=os.getenv("GEMINI_API_KEY"),
                    grok_api_key=os.getenv("GROK_API_KEY"),
                )
                data = {**extracted, "losing_team": losing_team}
            else:
                summarizer = MLBGameSummarizer(
                    gemini_api_key=os.getenv("GEMINI_API_KEY"),
                    grok_api_key=os.getenv("GROK_API_KEY"),
                )
                data = extracted  # type: ignore[assignment]

            llm_choice = "gemini" if os.getenv("GEMINI_API_KEY") else "grok"
            return summarizer.generate_summary(llm_choice=llm_choice, data=data)
        except Exception as e:
            print(f"Error getting MLB game summary: {e}")
            return None

    def get_allstar_game_scores(self, date: datetime) -> list:
        """Get MLB All-Star game scores (`gameType='A'`) for a specific date."""
        game_date = date.strftime("%Y-%m-%d")
        url = (
            f"{self.base_url}/api/v1/schedule"
            f"?sportId=1"
            f"&gameType=A"
            f"&startDate={game_date}"
            f"&endDate={game_date}"
        )
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching All-Star schedule: {e}")
            return []

        games = []
        for date_data in data.get("dates", []):
            for game in date_data.get("games", []):
                if game.get("gameType") != "A":
                    continue
                game_info = {
                    "gameDate": game.get("gameDate"),
                    "away_team": game["teams"]["away"]["team"]["name"],
                    "home_team": game["teams"]["home"]["team"]["name"],
                    "away_score": game["teams"]["away"].get("score"),
                    "home_score": game["teams"]["home"].get("score"),
                    "status": game["status"]["detailedState"],
                    "away_id": game["teams"]["away"]["team"]["id"],
                    "home_id": game["teams"]["home"]["team"]["id"],
                }
                games.append(game_info)
        return games

    def get_allstar_box_scores(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Get side-by-side box scores for AL (id 159) and NL (id 160) for a given date."""
        game_pk = self._get_game_pk_by_type("A", date)
        if not game_pk:
            game_pk = self._get_game_pk(160, date) or self._get_game_pk(159, date)
        if not game_pk:
            print(f"No completed All-Star game found on {date.strftime('%Y-%m-%d')}.")
            return None

        try:
            boxscore_url = f"{self.base_url}/api/v1/game/{game_pk}/boxscore"
            boxscore_response = requests.get(boxscore_url)
            boxscore_response.raise_for_status()
            boxscore_data = boxscore_response.json()
            if not boxscore_data:
                return None

            result = {}
            for t_key in ['away', 'home']:
                t_info = boxscore_data['teams'][t_key]
                t_id = t_info['team']['id']
                t_name = t_info['team']['name']
                players = t_info['players']

                batting_stats = []
                pitching_stats = []

                for player_data in players.values():
                    p_name = player_data['person']['fullName']
                    bs = player_data['stats'].get('batting', {})
                    ps = player_data['stats'].get('pitching', {})

                    if bs.get('atBats', 0) > 0 or bs.get('plateAppearances', 0) > 0 or bs.get('runs', 0) > 0 or bs.get('rbi', 0) > 0:
                        batting_stats.append({
                            'name': p_name,
                            'AB': bs.get('atBats', 0),
                            'R': bs.get('runs', 0),
                            'H': bs.get('hits', 0),
                            'HR': bs.get('homeRuns', 0),
                            'RBI': bs.get('rbi', 0),
                            'BB': bs.get('baseOnBalls', 0),
                            'SO': bs.get('strikeOuts', 0),
                        })

                    if ps.get('inningsPitched', '0.0') != '0.0' or ps.get('battersFaced', 0) > 0:
                        pitching_stats.append({
                            'name': p_name,
                            'IP': ps.get('inningsPitched', '0.0'),
                            'H': ps.get('hits', 0),
                            'R': ps.get('runs', 0),
                            'ER': ps.get('earnedRuns', 0),
                            'BB': ps.get('baseOnBalls', 0),
                            'SO': ps.get('strikeOuts', 0),
                        })

                league_key = "AL" if t_id == 159 or "American" in t_name else "NL"
                result[league_key] = {
                    'team_name': t_name,
                    'batting_stats': batting_stats,
                    'pitching_stats': pitching_stats,
                }

            return result
        except Exception as e:
            print(f"Error getting All-Star box score: {e}")
            return None

    def get_allstar_game_summary(self, date: datetime) -> Optional[str]:
        """Get ~500-word regular game summary for the All-Star game from NL perspective."""
        try:
            import os
            from .extractors import MLBGameExtractor
            from ..llm.summary import MLBAllStarGameSummarizer
            date_str = date.strftime("%Y-%m-%d")
            extractor = MLBGameExtractor()
            raw = extractor.fetch_raw_data(160, date_str)
            if not raw:
                raw = extractor.fetch_raw_data(159, date_str)
            extracted = extractor.extract_key_info(raw)
            if isinstance(extracted, str):
                return extracted

            summarizer = MLBAllStarGameSummarizer(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                grok_api_key=os.getenv("GROK_API_KEY"),
            )
            llm_choice = "gemini" if os.getenv("GEMINI_API_KEY") else "grok"
            return summarizer.generate_summary(llm_choice=llm_choice, data=extracted)
        except Exception as e:
            print(f"Error getting All-Star game summary: {e}")
            return None

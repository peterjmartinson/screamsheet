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
                if game['status']['statusCode'] == 'F':
                    if (game['teams']['away']['team']['id'] == team_id or
                            game['teams']['home']['team']['id'] == team_id):
                        return game['gamePk']
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

    def get_derby_game_pk(self, date: datetime) -> Optional[int]:
        """
        Get the gamePk for the MLB Home Run Derby on or around a specific date.
        If no Derby is found on the exact date, searches recent days or the month of July.
        
        Args:
            date: The date to search for the Home Run Derby event
            
        Returns:
            The event id / gamePk if found, or None
        """
        headers = {"User-Agent": "Mozilla/5.0"}

        def _check_url(url: str) -> Optional[int]:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:
                    return None
                data = response.json()
                for date_data in data.get("dates", []):
                    for event in date_data.get("events", []):
                        name = event.get("name", "")
                        if "Home Run Derby" in name and "Testing" not in name and "Batting Practice" not in name:
                            return int(event["id"])
                    for game in date_data.get("games", []):
                        description = game.get("description", "")
                        if "Home Run Derby" in description:
                            return int(game["gamePk"])
            except Exception as e:
                print(f"Error checking schedule URL {url}: {e}")
            return None

        # 1. Check exact date
        game_date = date.strftime("%Y-%m-%d")
        found = _check_url(f"{self.base_url}/api/v1/schedule?sportId=1&date={game_date}&scheduleTypes=events")
        if found:
            return found

        # 2. Check yesterday and two days ago (common when running morning reports after the Derby)
        for d in (1, 2):
            prev_date = (date - timedelta(days=d)).strftime("%Y-%m-%d")
            found = _check_url(f"{self.base_url}/api/v1/schedule?sportId=1&date={prev_date}&scheduleTypes=events")
            if found:
                return found

        # 3. Search the month of July for the target year (Derby is always mid-July)
        year = date.year
        found = _check_url(f"{self.base_url}/api/v1/schedule?sportId=1&startDate={year}-07-01&endDate={year}-07-31&scheduleTypes=events")
        if found:
            return found

        # 4. If no event found in target year (or running before July), check previous year or fallback to 2024 Derby (773161)
        if year > 2024:
            found = _check_url(f"{self.base_url}/api/v1/schedule?sportId=1&startDate={year-1}-07-01&endDate={year-1}-07-31&scheduleTypes=events")
            if found:
                return found

        # Default fallback to 2024 Home Run Derby if no future Derby is scheduled yet
        return 773161

    def fetch_derby_bracket(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse bracket data for the Home Run Derby.
        
        Args:
            game_pk: The Home Run Derby event gamePk
            
        Returns:
            Parsed bracket structure including rounds, matchups, champion, and runner-up
        """
        url = f"{self.base_url}/api/v1/homeRunDerby/{game_pk}/bracket"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            
            rounds_summary = []
            champion = None
            runner_up = None
            
            def _parse_seed_hits(seed: Any) -> int:
                if not isinstance(seed, dict):
                    return 0
                for key in ("numHomeRuns", "numPoints", "homeRuns"):
                    if key in seed and seed[key] is not None:
                        try:
                            return int(seed[key])
                        except (ValueError, TypeError):
                            pass
                val = seed.get("hits")
                if isinstance(val, dict):
                    for k in ("total", "hits", "homeRuns"):
                        if k in val and val[k] is not None:
                            try:
                                return int(val[k])
                            except (ValueError, TypeError):
                                pass
                elif isinstance(val, list):
                    hr_count = sum(1 for h in val if isinstance(h, dict) and (h.get("homeRun") is True or h.get("isHomeRun") is True))
                    if hr_count > 0:
                        return hr_count
                    return len(val)
                elif val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
                return 0

            rounds = data.get("rounds", [])
            for rnd in rounds:
                round_obj = rnd.get("round", "")
                if isinstance(round_obj, dict):
                    round_name = round_obj.get("name", str(round_obj))
                else:
                    round_name = f"Round {round_obj}" if str(round_obj).isdigit() else str(round_obj)
                    if round_obj == 1:
                        round_name = "Round 1"
                    elif round_obj == 2:
                        round_name = "Semifinals"
                    elif round_obj == 3:
                        round_name = "Finals"
                
                matchups_list = []
                for m in rnd.get("matchups", []):
                    top = m.get("topSeed", {})
                    bot = m.get("bottomSeed", {})
                    
                    top_player = top.get("player", {}).get("fullName", "TBD") if isinstance(top.get("player"), dict) else str(top.get("player", "TBD"))
                    top_hits = _parse_seed_hits(top)
                    
                    bot_player = bot.get("player", {}).get("fullName", "TBD") if isinstance(bot.get("player"), dict) else str(bot.get("player", "TBD"))
                    bot_hits = _parse_seed_hits(bot)
                    
                    top_is_winner = top.get("isWinner", top.get("winner")) is True
                    bot_is_winner = bot.get("isWinner", bot.get("winner")) is True
                    winner_obj = m.get("winner")

                    if top_is_winner and not bot_is_winner:
                        winner_name = top_player
                    elif bot_is_winner and not top_is_winner:
                        winner_name = bot_player
                    elif isinstance(winner_obj, dict):
                        winner_name = winner_obj.get("fullName", "TBD")
                    elif isinstance(winner_obj, str) and winner_obj and winner_obj != "TBD":
                        winner_name = winner_obj
                    elif top_hits > bot_hits:
                        winner_name = top_player
                    elif bot_hits > top_hits:
                        winner_name = bot_player
                    else:
                        winner_name = "TBD"
                    
                    matchups_list.append({
                        "top_seed": {"player": top_player, "hits": top_hits},
                        "bottom_seed": {"player": bot_player, "hits": bot_hits},
                        "winner": winner_name
                    })
                
                rounds_summary.append({
                    "round_name": round_name,
                    "matchups": matchups_list
                })
            
            if rounds_summary and rounds_summary[-1]["matchups"]:
                final_matchup = rounds_summary[-1]["matchups"][-1]
                top_s = final_matchup["top_seed"]
                bot_s = final_matchup["bottom_seed"]
                winner_name = final_matchup["winner"]
                
                if winner_name == top_s["player"]:
                    champion = top_s
                    runner_up = bot_s
                elif winner_name == bot_s["player"]:
                    champion = bot_s
                    runner_up = top_s
                else:
                    if top_s["hits"] >= bot_s["hits"]:
                        champion = top_s
                        runner_up = bot_s
                    else:
                        champion = bot_s
                        runner_up = top_s
                        
            return {
                "rounds": rounds_summary,
                "champion": champion,
                "runner_up": runner_up
            }
        except Exception as e:
            print(f"Error fetching MLB Home Run Derby bracket: {e}")
            return None

    def fetch_derby_statcast(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse Statcast pool data for the Home Run Derby.
        
        Args:
            game_pk: The Home Run Derby event gamePk
            
        Returns:
            Parsed Statcast highlights including longest home run and hardest hit ball
        """
        url = f"{self.base_url}/api/v1/homeRunDerby/{game_pk}/pool"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            
            longest_dist = 0
            longest_player = "N/A"
            hardest_vel = 0.0
            hardest_player = "N/A"
            
            for rnd in data.get("rounds", []):
                for b in rnd.get("batters", []):
                    pname = b.get("player", {}).get("fullName", "Unknown")
                    for hit in b.get("hits", []):
                        if not hit.get("isHomeRun", False):
                            continue
                        hd = hit.get("hitData", {})
                        dist = hd.get("totalDistance", 0)
                        vel = hd.get("launchSpeed", 0.0)
                        if dist > longest_dist:
                            longest_dist = dist
                            longest_player = pname
                        if vel > hardest_vel:
                            hardest_vel = vel
                            hardest_player = pname
                            
            return {
                "longest_hr": {"player": longest_player, "distance": longest_dist},
                "hardest_hit": {"player": hardest_player, "exit_velocity": hardest_vel}
            }
        except Exception as e:
            print(f"Error fetching MLB Home Run Derby Statcast pool: {e}")
            return None

    def get_home_run_derby_summary(self, date: datetime, game_pk: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive Home Run Derby summary including bracket and Statcast highlights.
        
        Args:
            date: The target date
            game_pk: Optional explicit gamePk (useful for historical testing)
            
        Returns:
            Combined dictionary of Derby data or None if unavailable
        """
        if game_pk is None:
            game_pk = self.get_derby_game_pk(date)
            if game_pk is None:
                return None
                
        bracket_data = self.fetch_derby_bracket(game_pk)
        statcast_data = self.fetch_derby_statcast(game_pk)
        
        if not bracket_data and not statcast_data:
            return None
            
        return {
            "game_pk": game_pk,
            "date": date.strftime("%Y-%m-%d"),
            "bracket": bracket_data or {},
            "statcast": statcast_data or {}
        }


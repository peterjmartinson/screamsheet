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
    
    def get_game_scores(self, date: datetime = None, fallback_to_week: bool = False) -> list:
        """
        Get NFL game scores for a specific date (or current/weekly slate).
        
        Args:
            date: The date to fetch scores for (queries ESPN by date YYYYMMDD).
            fallback_to_week: If True and date has no games, falls back to weekly slate.
            
        Returns:
            List of game score dictionaries
        """
        from .parsers.nfl_parsers import extract_scoreboard
        if date:
            date_str = date.strftime("%Y%m%d")
            url = f"{self.base_url}/scoreboard?dates={date_str}"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                games = extract_scoreboard(data)
                if games:
                    return games
                elif not fallback_to_week:
                    return []
            except requests.exceptions.RequestException as e:
                print(f"Error fetching game scores for date {date_str}: {e}")
                if not fallback_to_week:
                    return []

        # Fallback to weekly scores if no date specified or if fallback_to_week is True
        week_info = self._get_current_week(date) if date else self.current_week
        season_year = self._get_current_season(date) if date else self.current_season
        if week_info is None:
            return []
        
        return self._get_weekly_scores(
            season_year,
            week_info,
            previous_week=False
        )

    
    def get_standings(self, date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get current NFL league standings for the active season type (preseason, regular season, postseason).
        
        Returns:
            DataFrame with standings data
        """
        season = self._get_current_season(date) if date else self.current_season
        week_info = self._get_current_week(date) if date else self.current_week
        season_type = week_info.get("SeasonValue", 2) if week_info else 2
        # Default to regular season (2) if not specified or 0
        if not season_type:
            season_type = 2

        base_standings_url = (
            f"https://sports.core.api.espn.com/v2/sports/football/"
            f"leagues/nfl/seasons/{season}/types/{season_type}/groups/"
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
                print(f"Error fetching standings for {conference_name} (type {season_type}): {e}")
                continue
            
            for team_entry in data.get("standings", []):
                # Extract team ID from URL reference
                team_ref = team_entry.get("team", {}).get("$ref", "")
                match = id_pattern.search(team_ref)
                if not match:
                    continue
                
                team_id = int(match.group(1))
                team_name = team_name_lookup.get(team_id, f"Team {team_id}")
                
                # Get stats from records array (ESPN API structure)
                records = team_entry.get("records", [])
                if not records:
                    continue
                    
                # Get overall record (first record entry)
                overall_record = records[0]
                stats = overall_record.get("stats", [])
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

        # Offseason/preseason fallback: if the computed season type has no standings yet,
        # retry regular season (types/2) or previous season's final standings.
        if standings.empty and season_type != 2:
            print(f"NFL standings: no data for season type {season_type}, retrying regular season (type 2)...")
            base_standings_url = (
                f"https://sports.core.api.espn.com/v2/sports/football/"
                f"leagues/nfl/seasons/{season}/types/2/groups/"
            )
            for group_id, conference_name in conferences.items():
                url = f"{base_standings_url}{group_id}/standings/0"
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching standings for {conference_name} (type 2): {e}")
                    continue

                for team_entry in data.get("standings", []):
                    team_ref = team_entry.get("team", {}).get("$ref", "")
                    match = id_pattern.search(team_ref)
                    if not match:
                        continue
                    team_id = int(match.group(1))
                    team_name = team_name_lookup.get(team_id, f"Team {team_id}")
                    records = team_entry.get("records", [])
                    if not records:
                        continue
                    overall_record = records[0]
                    stats = overall_record.get("stats", [])
                    stat_dict = {stat["name"]: stat["value"] for stat in stats}
                    all_standings.append({
                        "conference": conference_name,
                        "team": team_name,
                        "wins": stat_dict.get("wins", 0),
                        "losses": stat_dict.get("losses", 0),
                        "ties": stat_dict.get("ties", 0),
                        "winPercent": stat_dict.get("winPercent", 0.0),
                        "pointDifferential": stat_dict.get("pointDifferential", 0),
                        "divisionWinPercent": stat_dict.get("divisionWinPercent", 0.0),
                    })
            standings = pd.DataFrame(all_standings)

        if standings.empty:
            prev_season = season - 1
            print(f"NFL standings: no data for season {season}, retrying season {prev_season}...")
            all_standings = []
            prev_base_url = (
                f"https://sports.core.api.espn.com/v2/sports/football/"
                f"leagues/nfl/seasons/{prev_season}/types/2/groups/"
            )
            for group_id, conference_name in conferences.items():
                url = f"{prev_base_url}{group_id}/standings/0"
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching standings for {conference_name} (season {prev_season}): {e}")
                    continue

                for team_entry in data.get("standings", []):
                    team_ref = team_entry.get("team", {}).get("$ref", "")
                    match = id_pattern.search(team_ref)
                    if not match:
                        continue
                    team_id = int(match.group(1))
                    team_name = team_name_lookup.get(team_id, f"Team {team_id}")
                    records = team_entry.get("records", [])
                    if not records:
                        continue
                    overall_record = records[0]
                    stats = overall_record.get("stats", [])
                    stat_dict = {stat["name"]: stat["value"] for stat in stats}
                    all_standings.append({
                        "conference": conference_name,
                        "team": team_name,
                        "wins": stat_dict.get("wins", 0),
                        "losses": stat_dict.get("losses", 0),
                        "ties": stat_dict.get("ties", 0),
                        "winPercent": stat_dict.get("winPercent", 0.0),
                        "pointDifferential": stat_dict.get("pointDifferential", 0),
                        "divisionWinPercent": stat_dict.get("divisionWinPercent", 0.0),
                    })

            standings = pd.DataFrame(all_standings)

        # Defensive guard: if columns are still missing, return unsorted rather than KeyError.
        if standings.empty or 'conference' not in standings.columns or 'winPercent' not in standings.columns:
            print("NFL standings: no standings data available; returning empty DataFrame.")
            return standings.reset_index(drop=True)

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
    
    def _get_current_season(self, date: Optional[datetime] = None) -> int:
        """Determine the NFL season year for a given date (or now)."""
        dt = date if date is not None else datetime.now(timezone.utc)
        this_year = dt.year
        prev_year = this_year - 1
        
        # During January and February, games belong to previous year's season (includes playoffs/Super Bowl)
        # After mid-February, switch to new season
        if dt.month == 1:
            return prev_year
        elif dt.month == 2 and dt.day <= 15:
            return prev_year
        elif dt.month >= 3 and dt.month <= 8:
            # Offseason - use upcoming season
            return this_year
        else:
            # September onwards - current year's season
            return this_year
    
    def _get_current_week(self, date: Optional[datetime] = None) -> Optional[Dict]:
        """Get information about the NFL week for a given date (or now)."""
        season = self._get_current_season(date) if date else self.current_season
        url = f"{self.base_url}/scoreboard?dates={season}"
        if date:
            if date.tzinfo is None:
                target_dt = date.replace(tzinfo=timezone.utc)
            else:
                target_dt = date
        else:
            target_dt = datetime.now(timezone.utc)
        
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
        
        calendar = data.get("leagues", [{}])[0].get("calendar", [])
        
        for period in calendar:
            start_date = datetime.fromisoformat(period["startDate"].replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(period["endDate"].replace('Z', '+00:00'))
            if start_date <= target_dt <= end_date:
                week_info["SeasonName"] = period.get("label", "")
                week_info["SeasonValue"] = int(period.get("value", 0))
                for week in period.get("entries", []):
                    week_start = datetime.fromisoformat(week["startDate"].replace('Z', '+00:00'))
                    week_end = datetime.fromisoformat(week["endDate"].replace('Z', '+00:00'))
                    if week_start <= target_dt <= week_end:
                        week_info["WeekName"] = week.get("label", "")
                        week_info["WeekDetail"] = week.get("detail", "")
                        week_info["WeekValue"] = int(week.get("value", 0))
        
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

    def _find_event_id(self, team_id: int, date: Optional[datetime] = None) -> Optional[str]:
        """Find the ESPN game/event ID for a given team on a date or week."""
        scores = self.get_game_scores(date)
        team_lookup = self._get_team_name_lookup()
        team_name = team_lookup.get(team_id, "")
        for g in scores:
            h_id = g.get("home_team_id")
            a_id = g.get("away_team_id")
            h_name = g.get("home_team")
            a_name = g.get("away_team")
            if (h_id == team_id or a_id == team_id) or (team_name and (team_name == h_name or team_name == a_name)):
                return g.get("gameId") or g.get("game_id")

        # Fall back to weekly scores search
        week_info = self._get_current_week(date) if date else self.current_week
        if week_info:
            weekly_scores = self._get_weekly_scores(self.current_season, week_info)
            for g in weekly_scores:
                if team_name and (team_name == g.get("home_team") or team_name == g.get("away_team")):
                    return g.get("gameId") or g.get("game_id")

        return None

    def get_box_score(self, team_id: int, date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Get structured box score for an NFL game involving team_id on date.
        """
        from .parsers.nfl_parsers import extract_box_score
        event_id = self._find_event_id(team_id, date)
        if not event_id:
            return None

        url = f"{self.base_url}/summary?event={event_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return extract_box_score(data, team_id=team_id)
        except Exception as e:
            print(f"Error fetching NFL box score for event {event_id}: {e}")
            return None

    def get_game_summary(self, team_id: int, date: Optional[datetime] = None, is_primary_favorite: bool = False, mad_fan: bool = False) -> Optional[str]:
        """
        Get LLM-generated game summary for a specific team on a given date/week.
        """
        import os
        from .parsers.nfl_parsers import extract_game_summary
        from ..llm.summary import NFLGameSummarizer
        
        event_id = self._find_event_id(team_id, date)
        if not event_id:
            return None

        url = f"{self.base_url}/summary?event={event_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            extracted = extract_game_summary(data, favorite_team_id=team_id)

            # Format extracted data for NFLGameSummarizer
            away_team = extracted.get("away_team", "")
            home_team = extracted.get("home_team", "")
            away_score = extracted.get("away_score", 0)
            home_score = extracted.get("home_score", 0)

            drives_list = extracted.get("scoring_drives", [])
            drives_formatted = "\n".join(
                [f"- Q{d.get('quarter', '')} ({d.get('clock', '')}): {d.get('team', '')} - {d.get('description', '')}" for d in drives_list]
            ) if drives_list else "None recorded."

            totals_lines = []
            for tm, stats in extracted.get("team_totals", {}).items():
                totals_lines.append(
                    f"{tm}: Total Yards {stats.get('total_yards', '')}, Pass {stats.get('passing_yards', '')}, Rush {stats.get('rushing_yards', '')}, Turnovers {stats.get('turnovers', '')}"
                )
            totals_formatted = "\n".join(totals_lines) if totals_lines else "None recorded."

            leaders_lines = []
            for cat in ["passing", "rushing", "receiving"]:
                for l in extracted.get("leaders", {}).get(cat, []):
                    leaders_lines.append(f"{cat.capitalize()}: {l.get('name', '')} ({l.get('team', '')}) - {l.get('display_stat', '')}")
            top_performers_formatted = "\n".join(leaders_lines) if leaders_lines else "None recorded."

            llm_payload = {
                "away_team": away_team,
                "away_score": away_score,
                "home_team": home_team,
                "home_score": home_score,
                "scoring_drives": drives_formatted,
                "team_totals": totals_formatted,
                "top_performers": top_performers_formatted,
            }

            summarizer = NFLGameSummarizer(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                grok_api_key=os.getenv("GROK_API_KEY"),
            )
            return summarizer.generate_summary(llm_choice="gemini", data=llm_payload)
        except Exception as e:
            print(f"Error generating NFL game summary for event {event_id}: {e}")
            return None

    def get_injuries(self, team_id: int) -> list:
        """
        Get injury report for a specific team.
        """
        from .parsers.nfl_parsers import extract_injuries
        url = f"{self.base_url}/teams/{team_id}/injuries"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return extract_injuries(data)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching injuries for team {team_id}: {e}")
            return []

    def has_game(self, team_id: int, date: Optional[datetime] = None) -> bool:
        """Check if team played on the date (or in the current week)."""
        team_lookup = self._get_team_name_lookup()
        team_name = team_lookup.get(team_id, "")
        scores = self.get_game_scores(date)
        for g in scores:
            h_id = g.get("home_team_id")
            a_id = g.get("away_team_id")
            h_name = g.get("home_team")
            a_name = g.get("away_team")
            if (h_id == team_id or a_id == team_id) or (team_name and (team_name == h_name or team_name == a_name)):
                return True
        return False

    def get_all_teams_for_date(self, date: Optional[datetime] = None) -> List[tuple]:
        """Get all teams that played completed games for the date/week."""
        scores = self.get_game_scores(date)
        team_lookup = self._get_team_name_lookup()
        # reverse map
        name_to_id = {v: k for k, v in team_lookup.items()}
        teams = []
        for g in scores:
            h_id = g.get("home_team_id")
            a_id = g.get("away_team_id")
            h_name = g.get("home_team")
            a_name = g.get("away_team")
            if h_id and h_name:
                teams.append((h_id, h_name))
            elif h_name:
                teams.append((name_to_id.get(h_name, 0), h_name))
            if a_id and a_name:
                teams.append((a_id, a_name))
            elif a_name:
                teams.append((name_to_id.get(a_name, 0), a_name))
        return list(set(teams))

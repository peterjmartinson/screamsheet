"""Pure parser functions for NFL ESPN API payloads."""
from typing import Any, Dict, List, Optional


def extract_scoreboard(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract scoreboard games from ESPN scoreboard API payload.
    
    Returns:
        List of dicts: [
            {
                "game_id": str,
                "game_date": str,
                "status": str,
                "away_team": str,
                "away_score": int | None,
                "home_team": str,
                "home_score": int | None,
                "quarter_scores": {
                    "away": List[int],
                    "home": List[int]
                }
            }
        ]
    """
    if not isinstance(raw_json, dict):
        return []
    
    events = raw_json.get("events", [])
    if not isinstance(events, list):
        return []

    games: List[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        game_id = str(event.get("id", ""))
        game_date = str(event.get("date", ""))
        
        competitions = event.get("competitions", [])
        if not competitions or not isinstance(competitions, list):
            continue
        comp = competitions[0]
        if not isinstance(comp, dict):
            continue

        status_name = comp.get("status", {}).get("type", {}).get("name", "")

        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        def parse_score(val: Any) -> Optional[int]:
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def parse_linescores(comp_data: Dict[str, Any]) -> List[int]:
            linescores = comp_data.get("linescores", [])
            out = []
            for ls in linescores:
                if isinstance(ls, dict) and "value" in ls:
                    try:
                        out.append(int(ls["value"]))
                    except (ValueError, TypeError):
                        pass
            return out

        home_team_name = home_comp.get("team", {}).get("displayName", home_comp.get("team", {}).get("name", "Home Team"))
        away_team_name = away_comp.get("team", {}).get("displayName", away_comp.get("team", {}).get("name", "Away Team"))

        games.append({
            "game_id": game_id,
            "game_date": game_date,
            "status": status_name,
            "away_team": away_team_name,
            "away_score": parse_score(away_comp.get("score")),
            "home_team": home_team_name,
            "home_score": parse_score(home_comp.get("score")),
            "quarter_scores": {
                "away": parse_linescores(away_comp),
                "home": parse_linescores(home_comp),
            }
        })

    return games


def extract_game_summary(raw_json: Dict[str, Any], favorite_team_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Extract game summary including team totals, scoring drive logs, and top performers.
    
    Returns dict with keys:
      - 'team_totals': { 'home': {...}, 'away': {...} }
      - 'scoring_drives': list of dicts { 'quarter': ..., 'clock': ..., 'team': ..., 'description': ... }
      - 'leaders': { 'passing': [...], 'rushing': [...], 'receiving': [...] }
    """
    if not isinstance(raw_json, dict):
        return {"team_totals": {}, "scoring_drives": [], "leaders": {"passing": [], "rushing": [], "receiving": []}}

    # 1. Scoring drives
    scoring_drives = []
    drives_data = raw_json.get("drives", {})
    if isinstance(drives_data, dict):
        for drive in drives_data.get("previous", []):
            if not isinstance(drive, dict):
                continue
            for play in drive.get("plays", []):
                if not isinstance(play, dict):
                    continue
                if play.get("scoringPlay"):
                    scoring_drives.append({
                        "quarter": play.get("period", {}).get("number", 0),
                        "clock": play.get("clock", {}).get("displayValue", ""),
                        "team": play.get("team", {}).get("displayName", play.get("team", {}).get("abbreviation", "")),
                        "description": play.get("text", play.get("type", {}).get("text", "")),
                        "score_value": play.get("scoreValue", 0),
                        "away_score": play.get("awayScore", 0),
                        "home_score": play.get("homeScore", 0),
                    })

    # If drives.previous didn't have plays, check scoringPlays top-level if present
    if not scoring_drives and "scoringPlays" in raw_json:
        for play in raw_json.get("scoringPlays", []):
            if isinstance(play, dict):
                scoring_drives.append({
                    "quarter": play.get("period", {}).get("number", 0),
                    "clock": play.get("clock", {}).get("displayValue", ""),
                    "team": play.get("team", {}).get("displayName", play.get("team", {}).get("abbreviation", "")),
                    "description": play.get("text", play.get("type", {}).get("text", "")),
                    "away_score": play.get("awayScore", 0),
                    "home_score": play.get("homeScore", 0),
                })

    # 2. Team totals (boxscore -> teams)
    team_totals = {}
    boxscore = raw_json.get("boxscore", {})
    teams_stats = boxscore.get("teams", []) if isinstance(boxscore, dict) else []
    for team_entry in teams_stats:
        if not isinstance(team_entry, dict):
            continue
        team_info = team_entry.get("team", {})
        team_name = team_info.get("displayName", team_info.get("name", "Unknown"))
        stats_list = team_entry.get("statistics", [])
        stat_map = {}
        for s in stats_list:
            if isinstance(s, dict) and "name" in s and "displayValue" in s:
                stat_map[s["name"]] = s["displayValue"]
        
        team_totals[team_name] = {
            "total_yards": stat_map.get("totalYards", ""),
            "passing_yards": stat_map.get("netPassingYards", stat_map.get("passingYards", "")),
            "rushing_yards": stat_map.get("rushingYards", ""),
            "turnovers": stat_map.get("turnovers", ""),
            "third_down_eff": stat_map.get("thirdDownEff", ""),
            "possession_time": stat_map.get("possessionTime", ""),
        }

    # 3. Top performers (leaders)
    leaders = {"passing": [], "rushing": [], "receiving": []}
    leaders_data = raw_json.get("leaders", [])
    if isinstance(leaders_data, list):
        for leader_category in leaders_data:
            if not isinstance(leader_category, dict):
                continue
            cat_name = leader_category.get("name", "").lower()
            target_key = None
            if "pass" in cat_name:
                target_key = "passing"
            elif "rush" in cat_name:
                target_key = "rushing"
            elif "receiv" in cat_name:
                target_key = "receiving"

            if target_key:
                for leader_entry in leader_category.get("leaders", []):
                    if not isinstance(leader_entry, dict):
                        continue
                    athlete = leader_entry.get("athlete", {})
                    name = athlete.get("displayName", athlete.get("name", "Unknown"))
                    stat_display = leader_entry.get("displayValue", "")
                    team_name = leader_entry.get("team", {}).get("displayName", "")
                    leaders[target_key].append({
                        "name": name,
                        "team": team_name,
                        "display_stat": stat_display,
                    })

    return {
        "team_totals": team_totals,
        "scoring_drives": scoring_drives,
        "leaders": leaders,
    }


def extract_standings(raw_json: Dict[str, Any], division_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Extract standings records from ESPN standings API.
    
    Returns:
        List of dicts: [
            {
                "team": str,
                "division": str,
                "rank": int,
                "wins": int,
                "losses": int,
                "ties": int,
                "win_percent": float,
                "differential": int,
                "streak": str
            }
        ]
    """
    if not isinstance(raw_json, dict):
        return []

    standings: List[Dict[str, Any]] = []
    
    children = raw_json.get("children", [])
    
    def process_entries(entries: List[Dict[str, Any]], current_div: str):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            team_info = entry.get("team", {})
            team_name = team_info.get("displayName", team_info.get("name", ""))
            
            stats = entry.get("stats", [])
            stat_dict = {}
            for s in stats:
                if isinstance(s, dict) and "name" in s:
                    stat_dict[s["name"]] = s.get("value", s.get("displayValue"))
            
            def safe_int(v: Any, default: int = 0) -> int:
                try:
                    return int(float(v))
                except (ValueError, TypeError):
                    return default
            
            def safe_float(v: Any, default: float = 0.0) -> float:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return default

            standings.append({
                "team": team_name,
                "division": current_div,
                "rank": safe_int(stat_dict.get("divisionWinPercentRank", stat_dict.get("rank", 0))),
                "wins": safe_int(stat_dict.get("wins")),
                "losses": safe_int(stat_dict.get("losses")),
                "ties": safe_int(stat_dict.get("ties")),
                "win_percent": safe_float(stat_dict.get("winPercent")),
                "differential": safe_int(stat_dict.get("pointDifferential")),
                "streak": str(stat_dict.get("streak", "")),
            })

    if children:
        for child in children:
            if not isinstance(child, dict):
                continue
            div_title = child.get("name", "")
            sub_children = child.get("children", [])
            if sub_children:
                for sub in sub_children:
                    sub_div_title = sub.get("name", div_title)
                    process_entries(sub.get("standings", {}).get("entries", []), sub_div_title)
            else:
                process_entries(child.get("standings", {}).get("entries", []), div_title)
    elif "standings" in raw_json and "entries" in raw_json["standings"]:
        process_entries(raw_json["standings"]["entries"], "")

    if division_name:
        standings = [s for s in standings if division_name.lower() in s["division"].lower()]

    return standings


def extract_injuries(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract injury reports for a team from ESPN team injuries endpoint.
    
    Returns:
        List of dicts: [
            {
                "athlete": str,
                "position": str,
                "status": str,
                "injury_date": str,
                "description": str
            }
        ]
    """
    if not isinstance(raw_json, dict):
        return []

    injuries: List[Dict[str, Any]] = []
    items = raw_json.get("injuries", [])
    if not isinstance(items, list):
        items = raw_json.get("items", [])

    for item in items:
        if not isinstance(item, dict):
            continue
        athlete = item.get("athlete", {})
        athlete_name = athlete.get("displayName", athlete.get("name", "Unknown Player"))
        position = athlete.get("position", {}).get("abbreviation", athlete.get("position", {}).get("name", ""))
        status = item.get("status", item.get("type", {}).get("description", ""))
        injury_date = item.get("date", "")
        description = item.get("details", {}).get("detail", item.get("shortComment", item.get("description", "")))

        injuries.append({
            "athlete": athlete_name,
            "position": position,
            "status": status,
            "injury_date": injury_date,
            "description": description,
        })

    return injuries

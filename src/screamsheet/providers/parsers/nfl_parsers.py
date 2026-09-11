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

        home_team_id = home_comp.get("team", {}).get("id")
        away_team_id = away_comp.get("team", {}).get("id")
        try:
            home_team_id = int(home_team_id) if home_team_id is not None else None
        except (ValueError, TypeError):
            home_team_id = None
        try:
            away_team_id = int(away_team_id) if away_team_id is not None else None
        except (ValueError, TypeError):
            away_team_id = None

        games.append({
            "gameId": game_id,
            "game_id": game_id,
            "gameDate": game_date,
            "game_date": game_date,
            "status": status_name,
            "away_team": away_team_name,
            "away_score": parse_score(away_comp.get("score")),
            "away_team_id": away_team_id,
            "home_team": home_team_name,
            "home_score": parse_score(home_comp.get("score")),
            "home_team_id": home_team_id,
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

    # Extract header / matchup info if available
    away_team = ""
    home_team = ""
    away_score = 0
    home_score = 0
    header_comps = raw_json.get("header", {}).get("competitions", []) if isinstance(raw_json.get("header"), dict) else []
    if header_comps and isinstance(header_comps, list):
        comp = header_comps[0]
        for c in comp.get("competitors", []):
            if c.get("homeAway") == "home":
                home_team = c.get("team", {}).get("displayName", "")
                try:
                    home_score = int(c.get("score", 0))
                except (ValueError, TypeError):
                    home_score = 0
            elif c.get("homeAway") == "away":
                away_team = c.get("team", {}).get("displayName", "")
                try:
                    away_score = int(c.get("score", 0))
                except (ValueError, TypeError):
                    away_score = 0

    # 3. Top performers (leaders)
    leaders = {"passing": [], "rushing": [], "receiving": []}
    leaders_data = raw_json.get("leaders", [])
    if isinstance(leaders_data, list):
        for entry in leaders_data:
            if not isinstance(entry, dict):
                continue
            cat_name = entry.get("name", "").lower()
            if "pass" in cat_name or "rush" in cat_name or "receiv" in cat_name:
                category_list = [entry]
                entry_team_name = ""
            elif "leaders" in entry and isinstance(entry.get("leaders"), list):
                category_list = entry.get("leaders", [])
                entry_team_name = entry.get("team", {}).get("displayName", "")
            else:
                category_list = [entry]
                entry_team_name = entry.get("team", {}).get("displayName", "")

            for leader_category in category_list:
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
                        team_name = leader_entry.get("team", {}).get("displayName", entry_team_name)
                        leaders[target_key].append({
                            "name": name,
                            "team": team_name,
                            "display_stat": stat_display,
                        })

    return {
        "away_team": away_team,
        "home_team": home_team,
        "away_score": away_score,
        "home_score": home_score,
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


def extract_box_score(raw_json: Dict[str, Any], team_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Extract structured NFL box score data from ESPN summary API payload.
    
    Returns a dict with:
        - "away_team": str
        - "away_abbrev": str
        - "away_score": int | str
        - "away_linescores": List[str]
        - "home_team": str
        - "home_abbrev": str
        - "home_score": int | str
        - "home_linescores": List[str]
        - "quarter_labels": List[str]
        - "team_stats": List[Dict[str, str]]
        - "top_performers": List[Dict[str, str]]
    """
    if not isinstance(raw_json, dict):
        return {}

    # 1. Header / competitors
    header_comps = raw_json.get("header", {}).get("competitions", []) if isinstance(raw_json.get("header"), dict) else []
    comp = header_comps[0] if header_comps and isinstance(header_comps, list) else {}
    competitors = comp.get("competitors", []) if isinstance(comp, dict) else []

    if not competitors:
        events = raw_json.get("events", [])
        if events and isinstance(events, list) and isinstance(events[0], dict):
            comp = events[0].get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])

    if not competitors or not isinstance(competitors, list):
        return {}

    home_comp = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away_comp = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    home_team = home_comp.get("team", {}).get("displayName", home_comp.get("team", {}).get("name", "Home Team"))
    away_team = away_comp.get("team", {}).get("displayName", away_comp.get("team", {}).get("name", "Away Team"))
    home_abbrev = home_comp.get("team", {}).get("abbreviation", home_team[:3].upper())
    away_abbrev = away_comp.get("team", {}).get("abbreviation", away_team[:3].upper())

    home_score = home_comp.get("score", 0)
    away_score = away_comp.get("score", 0)

    def parse_ls(c: Dict[str, Any]) -> List[str]:
        linescores = c.get("linescores", [])
        out = []
        if isinstance(linescores, list):
            for ls in linescores:
                if isinstance(ls, dict):
                    val = ls.get("displayValue", ls.get("value", "0"))
                    out.append(str(val))
                elif isinstance(ls, (int, str)):
                    out.append(str(ls))
        return out

    home_ls = parse_ls(home_comp)
    away_ls = parse_ls(away_comp)

    max_quarters = max(len(home_ls), len(away_ls), 4)
    if max_quarters == 4:
        quarter_labels = ["1", "2", "3", "4"]
    elif max_quarters == 5:
        quarter_labels = ["1", "2", "3", "4", "OT"]
    else:
        quarter_labels = ["1", "2", "3", "4"] + [f"{i-3}OT" for i in range(5, max_quarters + 1)]

    while len(home_ls) < max_quarters:
        home_ls.append("0")
    while len(away_ls) < max_quarters:
        away_ls.append("0")

    # 2. Team statistics
    stat_maps = {}
    boxscore = raw_json.get("boxscore", {})
    if isinstance(boxscore, dict):
        for t in boxscore.get("teams", []):
            if not isinstance(t, dict):
                continue
            tm_name = t.get("team", {}).get("displayName", "")
            tm_abbrev = t.get("team", {}).get("abbreviation", "")
            s_map = {}
            for s in t.get("statistics", []):
                if isinstance(s, dict) and "name" in s and "displayValue" in s:
                    s_map[s["name"]] = s["displayValue"]
            if tm_name:
                stat_maps[tm_name.lower()] = s_map
            if tm_abbrev:
                stat_maps[tm_abbrev.lower()] = s_map

    home_stats = stat_maps.get(home_team.lower(), stat_maps.get(home_abbrev.lower(), {}))
    away_stats = stat_maps.get(away_team.lower(), stat_maps.get(away_abbrev.lower(), {}))

    display_stats = [
        ("Total Yards", ("totalYards",)),
        ("Net Passing Yards", ("netPassingYards", "passingYards")),
        ("Rushing Yards", ("rushingYards",)),
        ("Turnovers", ("turnovers",)),
        ("Third Down Efficiency", ("thirdDownEff",)),
        ("Time Of Possession", ("possessionTime",)),
    ]

    team_stats = []
    for label, keys in display_stats:
        a_val = next((away_stats.get(k) for k in keys if away_stats.get(k) is not None), "-")
        h_val = next((home_stats.get(k) for k in keys if home_stats.get(k) is not None), "-")
        team_stats.append({
            "stat": label,
            "away": str(a_val),
            "home": str(h_val),
        })

    # 3. Top performers (leaders)
    top_performers = []
    leaders_data = raw_json.get("leaders", [])
    if isinstance(leaders_data, list):
        for entry in leaders_data:
            if not isinstance(entry, dict):
                continue
            team_info = entry.get("team", {})
            t_abbrev = team_info.get("abbreviation", team_info.get("displayName", ""))
            
            # Case A: team-level groupings
            if "leaders" in entry and isinstance(entry["leaders"], list):
                for cat in entry["leaders"]:
                    if not isinstance(cat, dict):
                        continue
                    cat_name = cat.get("name", "").lower()
                    cat_code = None
                    if "pass" in cat_name:
                        cat_code = "PASS"
                    elif "rush" in cat_name:
                        cat_code = "RUSH"
                    elif "receiv" in cat_name:
                        cat_code = "REC"
                    
                    if cat_code:
                        for l in cat.get("leaders", []):
                            if not isinstance(l, dict):
                                continue
                            ath = l.get("athlete", {}).get("displayName", l.get("athlete", {}).get("name", "Unknown"))
                            stat_val = l.get("displayValue", "")
                            label = f"{cat_code} ({t_abbrev})" if t_abbrev else cat_code
                            top_performers.append({
                                "category": label,
                                "player": ath,
                                "stat": stat_val,
                            })
            else:
                # Case B: top-level category entries
                cat_name = entry.get("name", "").lower()
                cat_code = None
                if "pass" in cat_name:
                    cat_code = "PASS"
                elif "rush" in cat_name:
                    cat_code = "RUSH"
                elif "receiv" in cat_name:
                    cat_code = "REC"
                
                if cat_code:
                    for l in entry.get("leaders", []):
                        if not isinstance(l, dict):
                            continue
                        ath = l.get("athlete", {}).get("displayName", l.get("athlete", {}).get("name", "Unknown"))
                        stat_val = l.get("displayValue", "")
                        entry_team = l.get("team", {}).get("abbreviation", l.get("team", {}).get("displayName", t_abbrev))
                        label = f"{cat_code} ({entry_team})" if entry_team else cat_code
                        top_performers.append({
                            "category": label,
                            "player": ath,
                            "stat": stat_val,
                        })

    return {
        "away_team": away_team,
        "away_abbrev": away_abbrev,
        "away_score": away_score,
        "away_linescores": away_ls,
        "home_team": home_team,
        "home_abbrev": home_abbrev,
        "home_score": home_score,
        "home_linescores": home_ls,
        "quarter_labels": quarter_labels,
        "team_stats": team_stats,
        "top_performers": top_performers,
    }


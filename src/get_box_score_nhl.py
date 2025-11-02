from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# NOTE: You will need to import ReportLab components (like Table, TableStyle, colors)
# and a paragraph generator (like lorem) to use the functions below the dashed line.
# Assuming 'requests' is installed.

# --- NHL Data Fetching and Parsing ---

# The Philadelphia Flyers' Team ID in the NHL API
FLYERS_TEAM_ID: int = 4
# The status code for a completed game in the NHL API
FINAL_STATUS_CODE: str = 'OFF' # '3' typically means 'Final'

@dataclass
class PlayerSkater:
    name: str
    goals: int
    assists: int
    points: int
    shots_on_goal: int
    pim: int

@dataclass
class PlayerGoalie:
    name: str
    shots_against: int
    saves: int
    save_percentage: Optional[float]






def get_game_pk(team_id: int, game_date: str) -> Optional[int]:
    """
    Fetches the gamePk for the last completed game of the specified NHL team on a given date.

    Args:
        team_id: The NHL team ID (e.g., Flyers is 4).
        game_date_str: The specific date to check in 'YYYY-MM-DD' format.
    Returns:
        The gamePk if found, otherwise None.
    """
    # NHL Schedule API uses a URL format based on the date
    game_date_str = game_date.strftime('%Y-%m-%d')
    schedule_url = f"https://api-web.nhle.com/v1/schedule/{game_date_str}"
    
    try:
        # Step 1: Find the Game ID (gamePk)
        schedule_response = requests.get(schedule_url)
        schedule_response.raise_for_status()
        schedule_data = schedule_response.json()
        
        game_pk = None
        
        # NHL data structure is simpler: 'gameWeek' contains 'games'
        if 'gameWeek' in schedule_data and schedule_data['gameWeek']:
            for day in schedule_data['gameWeek']:
                for game in day.get('games', []):
                    # Check for completed game status (e.g., 'Final' or '3')
                    if str(game['gameState']) == FINAL_STATUS_CODE:
                        
                        # Check if the target team is in the game
                        home_id = game['homeTeam']['id']
                        away_id = game['awayTeam']['id']
                        
                        if home_id == team_id or away_id == team_id:
                            # The game's ID is the 'id' field in the game object
                            game_pk = game['id']
                            break
                if game_pk:
                    return game_pk

        if not game_pk:
            print(f"No completed game found for Flyers (ID {team_id}) on {game_date_str}.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching NHL data: {e}")
        return None
    

def get_game_boxscore(game_pk: int) -> Optional[Dict[str, Any]]:
    """
    Fetches the box score data for an NHL completed game.

    Args:
        game_pk: The unique identifier for the NHL game.

    Returns:
        A dictionary with raw box score data, or None if not found.
    """
    try:
        boxscore_url = f"https://api-web.nhle.com/v1/gamecenter/{game_pk}/boxscore"
        boxscore_response = requests.get(boxscore_url)
        boxscore_response.raise_for_status()
        boxscore_data = boxscore_response.json()
        print(boxscore_url)

        return boxscore_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NHL data: {e}")
        return None

def parse_nhl_boxscore(boxscore_data: Optional[Dict[str, Any]], team_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parses an NHL box score dictionary to extract skater and goalie stats for a specific team.

    Args:
        boxscore_data: The JSON response from the NHL boxscore API.
        team_id: The ID of the team to parse stats for.

    Returns:
        A dictionary with skater_stats and goalie_stats.
    """
    if not boxscore_data:
        return {'skater_stats': [], 'goalie_stats': []}

    # target_team_code = boxscore_data['homeTeam']['abbrev'] if boxscore_data['homeTeam']['id'] == team_id else boxscore_data['awayTeam']['abbrev']
    target_team_code = "homeTeam" if boxscore_data['homeTeam']['id'] == team_id else "awayTeam"
    
    skater_stats: List[Dict[str, Any]] = []
    skater_stats_obj: List[PlayerSkater] = []
    
    # Skaters are grouped by their team's abbreviation
    raw_skaters = boxscore_data['playerByGameStats'][target_team_code]['forwards'] + \
                  boxscore_data['playerByGameStats'][target_team_code]['defense']

    # Parse Skater stats (G, A, P, SOG)
    for player in raw_skaters:
        skater_stats_obj.append(PlayerSkater(
            player['name']['default'],
            player.get('goals', 0),
            player.get('assists', 0),
            player.get('points', 0),
            player.get('shots', 0),
            player.get('pim', 0)
        ))

        skater_stats.append({
            'name': f"{player['name']['default']}",
            'G': player.get('goals', 0),
            'A': player.get('assists', 0),
            'P': player.get('points', 0),
            'SOG': player.get('shots', 0),
            'PIM': player.get('pim', 0)
        })

    goalie_stats: List[Dict[str, Any]] = []
    goalie_stats_obj: List[PlayerGoalie] = []
    raw_goalies = boxscore_data['playerByGameStats'][target_team_code]['goalies']

    # Parse Goalie stats (SA, SV)
    for player in raw_goalies:
        # compute save percentage as float when possible, otherwise None
        shots_against = player.get('shotsAgainst', 0)
        saves = player.get('saves', 0)
        sv_pct: Optional[float]
        if shots_against and shots_against > 0:
            sv_pct = saves / shots_against
        else:
            sv_pct = None

        goalie_stats_obj.append(
            PlayerGoalie(
                player['name']['default'],
                shots_against,
                saves,
                sv_pct
            )
        )
        goalie_stats.append({
            'name': f"{player['name']['default']}",
            'SA': player.get('shotsAgainst', 0),
            'SV': player.get('saves', 0),
            'SV%': f"{(player.get('saves', 0) / player.get('shotsAgainst', 1)):.3f}" if player.get('shotsAgainst', 0) > 0 else 'N/A'
        })

    print({'skater_stats': skater_stats_obj, 'goalie_stats': goalie_stats_obj})
    return {'skater_stats': skater_stats, 'goalie_stats': goalie_stats}

# --- ReportLab Table Generation (adapted for NHL stats) ---

# This function uses the ReportLab components you provided in your original code.
def create_nhl_boxscore_tables(boxscore_stats: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Table]:
    """
    Creates ReportLab Table objects for skater and goalie stats.
    """
    skater_stats: List[Dict[str, Any]] = boxscore_stats['skater_stats']
    goalie_stats: List[Dict[str, Any]] = boxscore_stats['goalie_stats']

    # --- Skater Table ---
    # G, A, P, SOG, PIM are common NHL stats
    skater_header = ["Skater", "G", "A", "P", "SOG", "PIM"]
    skater_data = [skater_header]

    for player in skater_stats:
        row = [
            player['name'],
            str(player.get('G', 0)),
            str(player.get('A', 0)),
            str(player.get('P', 0)),
            str(player.get('SOG', 0)),
            str(player.get('PIM', 0))
        ]
        skater_data.append(row)

    skater_table = Table(skater_data)
    skater_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    # --- Goalie Table ---
    # SA (Shots Against), SV (Saves), SV% (Save Percentage)
    goalie_header = ["Goaltender", "SA", "SV", "SV%"]
    goalie_data = [goalie_header]

    for player in goalie_stats:
        row = [
            player['name'],
            str(player.get('SA', 0)),
            str(player.get('SV', 0)),
            player.get('SV%', 'N/A')
        ]
        goalie_data.append(row)

    goalie_table = Table(goalie_data)
    goalie_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    final_table = {'skater_table': skater_table, 'goalie_table': goalie_table}
    return final_table


# --- Orchestration Function ---

def get_nhl_boxscore(team_id: int, game_date: Optional[datetime] = None) -> Dict[str, Table]:
    """
    Orchestrates the data retrieval and parsing for the Flyers' NHL box score.
    This function is designed to be called by your main report generation script.
    """
    # Use the Flyers' Team ID (4)
    game_pk = get_game_pk(team_id, game_date)
    print(game_pk)
    box_score_data = get_game_boxscore(game_pk)
    
    if not box_score_data:
        # Return empty tables if no game was found
        return {'skater_table': Table([['No Skater Data Found']]), 
                'goalie_table': Table([['No Goalie Data Found']])}
        
    parsed_stats = parse_nhl_boxscore(box_score_data, team_id)
    
    # Generate the ReportLab flowable tables
    return create_nhl_boxscore_tables(parsed_stats)

if __name__ == '__main__':
    yesterday = (datetime.now() - timedelta(days=3))
    yesterday = datetime(2025, 10, 28)
    box_score_data = get_nhl_boxscore(FLYERS_TEAM_ID, yesterday)
    print(box_score_data)
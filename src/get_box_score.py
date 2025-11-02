import requests
from datetime import datetime, timedelta
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from lorem_text import lorem
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Frame,
    PageBreak,  # <-- Import the PageBreak flowable
)

# Re-using your defined style for centered headings
CENTERED_STYLE = ParagraphStyle(name='Centered', alignment=1)


def get_last_game_boxscore(team_id: int, game_date: datetime = None):
    """
    Fetches the box score data for a team's last completed game.

    Args:
        team_id: The MLB team ID (e.g., Phillies is 143).
        game_date: The date of the game.  If None, defaults to yesterday.

    Returns:
        A dictionary with parsed box score data, or None if not found.
    """
    if not game_date:
        yesterday = (datetime.now() - timedelta(days=1))
        game_date = yesterday.strftime('%Y-%m-%d')
    schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
    
    try:
        # Step 1: Find the game ID for yesterday's game
        params = {'sportId': 1, 'teamId': team_id, 'date': game_date}
        schedule_response = requests.get(schedule_url, params=params)
        schedule_response.raise_for_status()
        schedule_data = schedule_response.json()
        
        game_pk = None
        if 'dates' in schedule_data and schedule_data['dates']:
            for game in schedule_data['dates'][0]['games']:
                # Ensure the game is completed
                if game['status']['statusCode'] == 'F':
                    if game['teams']['away']['team']['id'] == team_id or game['teams']['home']['team']['id'] == team_id:
                        game_pk = game['gamePk']
                        break
        
        if not game_pk:
            print(f"No completed game found for team ID {team_id} on {game_date}.")
            return None
        
        # Step 2: Fetch the detailed box score using the game ID
        boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        boxscore_response = requests.get(boxscore_url)
        boxscore_response.raise_for_status()
        boxscore_data = boxscore_response.json()

        return boxscore_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_boxscore(boxscore_data, team_id: int):
    """
    Parses a box score dictionary to extract player stats for a specific team.

    Args:
        boxscore_data: The JSON response from the boxscore API.
        team_id: The ID of the team to parse stats for.

    Returns:
        A dictionary with hitting and pitching stats.
    """
    if not boxscore_data:
        return {'batting_stats': [], 'pitching_stats': []}

    home_team_id = boxscore_data['teams']['home']['team']['id']
    away_team_id = boxscore_data['teams']['away']['team']['id']
    
    target_team = 'home' if home_team_id == team_id else 'away'
    
    batting_stats = []
    pitching_stats = []

    players = boxscore_data['teams'][target_team]['players']
    
    # Parse hitting stats
    for player_id, player_data in players.items():
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
                'SO': stats.get('strikeOuts', 0)
            })

    # Parse pitching stats
    for player_id, player_data in players.items():
        if player_data['stats'].get('pitching'):
            stats = player_data['stats']['pitching']
            pitching_stats.append({
                'name': player_data['person']['fullName'],
                'IP': stats.get('inningsPitched', '0.0'),
                'H': stats.get('hits', 0),
                'R': stats.get('runs', 0),
                'ER': stats.get('earnedRuns', 0),
                'BB': stats.get('baseOnBalls', 0),
                'SO': stats.get('strikeOuts', 0)
            })

    return {'batting_stats': batting_stats, 'pitching_stats': pitching_stats}

def get_box_score(team_id=143, game_date=None) -> dict:
    box_score = get_last_game_boxscore(team_id)
    parsed_score = parse_boxscore(box_score, team_id)
    return parsed_score

def create_boxscore_tables(boxscore_stats):
    """
    Creates ReportLab Table objects for hitting and pitching stats.

    Args:
        boxscore_stats: A dictionary containing 'batting_stats' and 
                        'pitching_stats' lists.

    Returns:
        A dictionary with ReportLab Table objects for batting and pitching.
    """
    batting_stats = boxscore_stats['batting_stats']
    pitching_stats = boxscore_stats['pitching_stats']

    # --- Hitting Table ---
    hitting_header = ["Batter", "AB", "R", "H", "HR", "RBI", "BB", "SO"]
    hitting_data = [hitting_header]

    for player in batting_stats:
        row = [
            player['name'],
            str(player.get('AB', 0)),
            str(player.get('R', 0)),
            str(player.get('H', 0)),
            str(player.get('HR', 0)),
            str(player.get('RBI', 0)),
            str(player.get('BB', 0)),
            str(player.get('SO', 0))
        ]
        hitting_data.append(row)

    hitting_table = Table(hitting_data)
    hitting_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    # --- Pitching Table ---
    pitching_header = ["Pitcher", "IP", "H", "R", "ER", "BB", "SO"]
    pitching_data = [pitching_header]

    for player in pitching_stats:
        row = [
            player['name'],
            player.get('IP', '0.0'),
            str(player.get('H', 0)),
            str(player.get('R', 0)),
            str(player.get('ER', 0)),
            str(player.get('BB', 0)),
            str(player.get('SO', 0))
        ]
        pitching_data.append(row)

    pitching_table = Table(pitching_data)
    pitching_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    return {'batting_table': hitting_table, 'pitching_table': pitching_table}

def get_dummy_paragraph():
    paragraph = lorem.paragraphs(1)
    return paragraph

if __name__ == '__main__':
    # This is a sample `boxscore_stats` dictionary, mirroring the JSON you provided
    filename="mlb_report.pdf"
    margin = 40
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )

    story = []

    sample_boxscore = {
        'batting_stats': [{'name': 'Brandon Marsh', 'AB': 4, 'R': 3, 'H': 2, 'HR': 0, 'RBI': 0, 'BB': 1, 'SO': 1}, {'name': 'Bryce Harper', 'AB': 3, 'R': 1, 'H': 2, 'HR': 0, 'RBI': 0, 'BB': 2, 'SO': 0}, {'name': 'J.T. Realmuto', 'AB': 4, 'R': 1, 'H': 1, 'HR': 0, 'RBI': 0, 'BB': 1, 'SO': 0}, {'name': 'Weston Wilson', 'AB': 5, 'R': 0, 'H': 1, 'HR': 0, 'RBI': 1, 'BB': 0, 'SO': 1}, {'name': 'Nick Castellanos', 'AB': 3, 'R': 1, 'H': 2, 'HR': 1, 'RBI': 3, 'BB': 0, 'SO': 1}, {'name': 'Alec Bohm', 'AB': 5, 'R': 1, 'H': 2, 'HR': 0, 'RBI': 3, 'BB': 0, 'SO': 0}, {'name': 'Bryson Stott', 'AB': 5, 'R': 0, 'H': 0, 'HR': 0, 'RBI': 0, 'BB': 0, 'SO': 2}, {'name': 'Kyle Schwarber', 'AB': 4, 'R': 0, 'H': 0, 'HR': 0, 'RBI': 0, 'BB': 1, 'SO': 2}, {'name': 'Harrison Bader', 'AB': 5, 'R': 1, 'H': 3, 'HR': 1, 'RBI': 1, 'BB': 0, 'SO': 1}, {'name': 'Max Kepler', 'AB': 2, 'R': 0, 'H': 0, 'HR': 0, 'RBI': 0, 'BB': 0, 'SO': 0}],
        'pitching_stats': [{'name': 'Walker Buehler', 'IP': '3.2', 'H': 2, 'R': 0, 'ER': 0, 'BB': 2, 'SO': 3}, {'name': 'Taijuan Walker', 'IP': '4.0', 'H': 5, 'R': 2, 'ER': 2, 'BB': 1, 'SO': 2}, {'name': 'Tanner Banks', 'IP': '0.1', 'H': 0, 'R': 0, 'ER': 0, 'BB': 0, 'SO': 0}, {'name': 'Max Lazar', 'IP': '1.0', 'H': 0, 'R': 0, 'ER': 0, 'BB': 0, 'SO': 0}]
    }


    boxscore_tables = create_boxscore_tables(sample_boxscore)
    
    summary = Paragraph(get_dummy_paragraph())
    box = [boxscore_tables['batting_table'], boxscore_tables['pitching_table']]
    section_table = Table(
        [
            [summary, box]
        ],
        colWidths=[doc.width/2, doc.width/2], hAlign='LEFT'
    )

    story.append(section_table)
    doc.build(story)

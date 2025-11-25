from nba_api.stats.endpoints import leaguegamefinder, leaguestandings
from nba_api.stats.static import teams
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Frame,
    PageBreak,  # <-- Import the PageBreak flowable
)
import pandas as pd
import requests
import os
import json
try:
    # from get_game_summary import GameSummaryGeneratorNBA
    from screamsheet_structures import GameScore
    from utilities import dump_json, dump_dataframe
except Exception:
    # from src.get_game_summary import GameSummaryGeneratorNBA
    from src.screamsheet_structures import GameScore
    from src.utilities import dump_json, dump_dataframe
from typing import Optional, Dict, Any, List
from get_box_score_nhl import get_nhl_boxscore
from dotenv import load_dotenv
load_dotenv()

page_height = 11 * inch
page_width = 8.5 * inch
left_margin = 36
right_margin = 36
top_margin = 36
bottom_margin = 36
available_width = page_width - left_margin - right_margin
available_height = page_height - top_margin - bottom_margin

DUMP = False

styles = getSampleStyleSheet()

CENTERED_STYLE = ParagraphStyle(
    name="CenteredText",
    alignment=TA_CENTER
)

TITLE_STYLE = ParagraphStyle(
    name="Title",
    parent=styles['h1'],
    fontName='Helvetica-Bold',
    fontSize=28,
    spaceAfter=12,
    alignment=TA_CENTER
)

SUBTITLE_STYLE = ParagraphStyle(
    name="Subtitle",
    parent=styles['h2'],
    fontName='Helvetica',
    fontSize=18,
    spaceAfter=12,
    alignment=TA_CENTER
)



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
        if DUMP:
            dump_json(schedule_response, "nba_get_game_pk")
        
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

def get_game_scores_for_day(game_date: str = None) -> List[GameScore]:
    """
    Fetches NBA game scores for a given day using the nhl_api wrapper 
    and returns them as a list of standardized GameScore objects.
    """
    if not game_date:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        game_date = yesterday.strftime("%m/%d/%Y")

    nba_teams = teams.get_teams()
    tricode_to_name = {
        team['abbreviation']: team['full_name'] 
        for team in nba_teams
    }

    # --- 2. Retrieve Yesterday's NBA Data ---
    gamefinder = leaguegamefinder.LeagueGameFinder(
        date_from_nullable=game_date,
        date_to_nullable=game_date
    )
    # The data frame has two rows per game (one for each team)
    df_list = gamefinder.get_data_frames()
    raw_games_df = df_list[0]
    if DUMP:
        dump_dataframe(raw_games_df, "nba_get_game_scores_for_day")

    # --- 3. Process and Format the Data ---
    games = []

    if not raw_games_df.empty:
        # Key columns needed for processing
        df = raw_games_df[['GAME_ID', 'GAME_DATE', 'MATCHUP', 'TEAM_ABBREVIATION', 'WL', 'PTS']]
        
        # Identify unique games based on GAME_ID
        unique_game_ids = df['GAME_ID'].unique()
        
        for game_id in unique_game_ids:
            # Get the two rows corresponding to this single game
            game_data = df[df['GAME_ID'] == game_id].reset_index(drop=True)
            
            # Ensure we have exactly two teams (safety check)
            # Really, ensure there are two rows, the "@" row and the "vs." row
            if len(game_data) != 2:
                print(f"Skipping incomplete game data for GAME_ID: {game_id}")
                continue
                
            # Determine the home and away teams using the MATCHUP format
            # NBA Matchups are always 'AWAY_TEAM @ HOME_TEAM' or 'HOME_TEAM vs. AWAY_TEAM'
            matchup_str = game_data.iloc[0]['MATCHUP']
            
            if '@' in matchup_str:
                # "LAC @ PHX"
                # The 'home' team is the one whose abbreviation appears AFTER the '@'
                away_tri, home_tri = matchup_str.split(' @ ')
            else:
                # "PHX vs. LAC"
                # Now the home team is the one BEFORE the 'vs.'
                # Handle cases where the home team is first (e.g., if MATCHUP only shows one team's perspective)
                # This is less common, but ensures robust parsing. We'll use the WL column logic below.
                home_tri, away_tri = matchup_str.split(' vs. ')

            # Extract data for both teams in the game
            team_1 = game_data.iloc[0]
            team_2 = game_data.iloc[1]
            
            # Identify which row is Home and which is Away
            if team_1['TEAM_ABBREVIATION'] == home_tri:
                home_team_data = team_1
                away_team_data = team_2
            elif team_2['TEAM_ABBREVIATION'] == home_tri:
                home_team_data = team_2
                away_team_data = team_1
            else:
                # This handles unexpected Matchup formats or data inconsistencies
                print(f"Could not reliably determine home/away for GAME_ID: {game_id}")
                continue

            # Handle development leagues
            if home_team_data['TEAM_ABBREVIATION'] not in tricode_to_name.keys():
                continue

            # Build the dictionary in the exact format you requested
            game_info = {
                # Format the date nicely
                "gameDate": home_team_data['GAME_DATE'],
                
                # Use the tricode_to_name mapping to get the full team names
                "away_team": tricode_to_name.get(away_team_data['TEAM_ABBREVIATION'], away_team_data['TEAM_ABBREVIATION']),
                "home_team": tricode_to_name.get(home_team_data['TEAM_ABBREVIATION'], home_team_data['TEAM_ABBREVIATION']),
                
                "away_score": int(away_team_data['PTS']),
                "home_score": int(home_team_data['PTS']),
                
                # Use 'Final' for the status, as this data is only for completed games
                "status": "Final"
            }
            games.append(game_info)
    return games

def get_division(record) -> str:
    base_url = f"https://statsapi.mlb.com"
    url = base_url + record.get("division", {}).get("link", {})
    response = requests.get(url)
    data = response.json()
    if DUMP:
        dump_json(response, "nba_get_division")
    division = data["divisions"][0].get("name")
    return division

def get_nba_standings() -> pd.DataFrame:
    """
    Fetches current NBA standings via nba_api and returns a DataFrame.
    """
    # 1. Fetch Data
    # '00' is the default LeagueID for the NBA
    standings_api = leaguestandings.LeagueStandings(league_id='00', season_type='Regular Season')
    standings_df = standings_api.get_data_frames()[0]

    # Optional: Dump raw data if you have your DUMP flag enabled
    # if DUMP:
    #     dump_dataframe(standings_df, "nba_raw_standings")

    team_list = []

    # 2. Process Data
    for index, row in standings_df.iterrows():
        
        # Calculate a clean team name (e.g., "Boston Celtics")
        city = row['TeamCity']
        name = row['TeamName']
        full_name = f"{city} {name}"

        # NBA Conference/Division Mapping
        conference = row['Conference'] # 'East' or 'West'
        division = row['Division']     # e.g., 'Atlantic', 'Pacific'

        # Format Win Percentage (e.g., 0.750)
        # The API usually returns this as a float, but sometimes needs rounding
        win_pct = row['WinPCT']
        win_pct_str = f"{win_pct:.3f}".lstrip('0') # .750 format

        team_obj = {
            "conference": "Eastern" if conference == 'East' else "Western",
            "division": division,
            "team": full_name,
            # Rank within the division is usually implicitly sorted by the API, 
            # but we can rely on WinPCT for sorting if needed.
            "W": row['WINS'],
            "L": row['LOSSES'],
            "PCT": win_pct_str,
            "GB": row['ConferenceGamesBack'], # or 'DivisionGamesBack'
            "STRK": row['CurrentStreak']
        }
        team_list.append(team_obj)

    standings = pd.DataFrame(team_list)

    # 3. Sort: Conference -> Division -> Win % (Descending)
    return standings.sort_values(
        by=['conference', 'division', 'PCT'], 
        ascending=[True, True, False]
    ).reset_index(drop=True)

def create_standings_table(standings_df: pd.DataFrame):
    """
    Creates a master reportlab Table for NBA standings.
    Layout: 3 rows of side-by-side tables (East vs West).
    """
    # 1. Separate Data by Conference
    eastern_conf = standings_df[standings_df['conference'] == 'Eastern']
    western_conf = standings_df[standings_df['conference'] == 'Western']

    # 2. Define the Layout (3 Rows)
    # East Divisions: Atlantic, Central, Southeast
    # West Divisions: Northwest, Pacific, Southwest
    division_layout = [
        {'east': 'Atlantic',  'west': 'Northwest'},
        {'east': 'Central',   'west': 'Pacific'},
        {'east': 'Southeast', 'west': 'Southwest'},
    ]

    # 3. Initialize Master Grid
    CENTERED_STYLE = ParagraphStyle(name="Centered", alignment=1, fontName="Helvetica-Bold")
    
    grid_data = [
        [
            Paragraph("<b>EASTERN CONFERENCE</b>", CENTERED_STYLE), 
            Paragraph("<b>WESTERN CONFERENCE</b>", CENTERED_STYLE)
        ],
    ]
    
    # Adjusted Widths: More room for names, remove OTL column
    # Total Width approx: 140 + 25 + 25 + 30 = 220 per side
    INNER_COL_WIDTHS = [135, 25, 25, 35] 
    
    # 4. Loop to Build Rows
    for row_info in division_layout:
        row_list = []
        
        # --- Helper to build one side ---
        def build_division_table(conf_df, div_name):
            group = conf_df[conf_df['division'] == div_name]
            if group.empty:
                return ''
            
            # Header: Team | W | L | Pct
            INNER_HEADER = [f"{div_name}", "W", "L", "Pct"]
            
            # Values: Name, W, L, PCT
            table_vals = [INNER_HEADER] + group[['team', 'W', 'L', 'PCT']].values.tolist()
            
            t = Table(table_vals, colWidths=INNER_COL_WIDTHS)
            
            t_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')), # Header Grey
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),             # Header Font
                # ('FONTSIZE', (0, 0), (-1, -1), 8),                           # Smaller font for stats
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),                          # Align Teams Left
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),                       # Align Stats Center
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ])
            t.setStyle(t_style)
            return t

        # Build Left (East)
        row_list.append(build_division_table(eastern_conf, row_info['east']))
        
        # Build Right (West)
        row_list.append(build_division_table(western_conf, row_info['west']))

        grid_data.append(row_list)
        
    # 5. Create Master Table
    # Two main columns, each roughly 230pts wide
    MASTER_COL_WIDTHS = [230, 230] 
    
    master_table_style = TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ])
    
    final_table = Table(grid_data, colWidths=MASTER_COL_WIDTHS)
    final_table.setStyle(master_table_style)
    
    return final_table

def make_pdf(games, standings, filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    margin = 40
    column_left_x = margin
    column_right_x = width / 2
    y = height - margin

    # Title
    title = "MLB Scream Sheet"
    subtitle = datetime.today().strftime("%A, %B %#d, %Y")

    # Positioning
    y_title = height - 60      # Top margin for title
    y_subtitle = y_title - 28  # Space below title

    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(width / 2, y_title, title)

    c.setFont("Helvetica", 24)
    c.drawCentredString(width / 2, y_subtitle, subtitle)

    starting_y = height - margin - 100
    y = starting_y

    c.setFont("Helvetica", 12)
    # i = 0
    for game in games:
        # Only print scores for games that have scores
        if game["away_score"] is not None and game["home_score"] is not None:
            away_text = f"{game['away_team']}"
            home_text = f"@ {game['home_team']}"
            score_width = 350  # Space reserved for scores

            # Calculate where to right-align scores
            text_width = width - margin * 2 - score_width

            box_x = column_left_x
            inc_y = 22
            # if i%2 != 0:
            #     box_x = column_right_x
            #     inc_y = 22
            # i += 1
            # Draw away team line
            c.drawString(box_x, y, away_text)
            c.drawRightString(box_x + text_width, y, str(game['away_score']))
            y -= 16

            # Draw home team line
            c.drawString(box_x, y, home_text)
            c.drawRightString(box_x + text_width, y, str(game['home_score']))
            y -= inc_y  # Space between games

            # Optionally, print status and date (commented for compactness)
            # c.setFont("Helvetica-Oblique", 9)
            # c.drawString(margin, y, f"{game['status']} - {game['gameDate'][:16].replace('T',' ')}")
            # c.setFont("Helvetica", 12)
            # y -= 14

            if y < margin + 32:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 12)

    y = starting_y
    x = column_right_x
    for division_name, group in standings.groupby('division'):
        stuff = group[['team', 'wins', 'losses', 'ties', 'pct']].to_string(index=False) 
        c.drawString(x, y, division_name)
        y-=16
        c.drawString(x, y, stuff)
        y-=30
        # print(f"\n### {division_name}\n")
        # print(group[['team', 'wins', 'losses', 'ties', 'pct']].to_string(index=False))



    c.save()


def get_scores_table(games_list: List[GameScore], doc=None):
    if not doc:
        margin = 36  # 0.5 inches in points
        filename = "dummy_filename"
        doc = SimpleDocTemplate(
            filename,
            pagesize=letter,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin
        )

    scores_left = []
    scores_center = []
    scores_right = []
    for i, game in enumerate(games_list):
        if game["away_score"] is not None and game["home_score"] is not None:
            table_data = [
                [game['away_team'], str(game['away_score'])],
                [f"@{game['home_team']}", str(game['home_score'])]
            ]
            table_style = TableStyle([
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ])
            game_table = Table(table_data, colWidths=[80, 50])
            game_table.setStyle(table_style)
            
            if i % 3 == 0:
                scores_left.append(game_table)
                scores_left.append(Spacer(1, 10))
            elif i % 3 == 1:
                scores_center.append(game_table)
                scores_center.append(Spacer(1, 10))
            else:
                scores_right.append(game_table)
                scores_right.append(Spacer(1, 10))

    scores_table = Table(
        [
            [scores_left, scores_center, scores_right]
        ],
        colWidths=[doc.width/3, doc.width/3, doc.width/3], hAlign='LEFT'
    )
    get_chart_dimensions(scores_table)

    return scores_table


# def generate_nba_report(games, standings, game_summary_text="", box_score=None, filename="nhl_report.pdf"):
def generate_nba_report(games, standings, filename="nhl_report.pdf"):
    """
    Generates a PDF report with game scores in two top columns and a standings grid at the bottom.

    Args:
        games (list): A list of dictionaries, where each dictionary represents a game.
        standings_df (pd.DataFrame): A DataFrame of team standings, assumed to be pre-sorted.
        filename (str): The name of the output PDF file.
    """
    # --- Adjust margins here ---
    title = "NBA Scream Sheet"
    margin = 36 # 0.5 inches in points
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )
    story = []

    print("make scores table")
    scores_table = get_scores_table(games, doc)
    print("make standings table")
    standings_table = create_standings_table(standings)
    # print("make box scores table")
    # box_score_skaters = box_score["skater_table"]
    # box_score_goalies = box_score["goalie_table"]

    # Create a heading for the summary
    # summary_heading_style = ParagraphStyle(
    #     name="SummaryHeading",
    #     parent=styles['h3'],
    #     fontName='Helvetica-Bold',
    #     fontSize=14,
    #     spaceAfter=12,
    # )

    # summary_text_style = ParagraphStyle(
    #     name="SummaryText",
    #     parent=styles['Normal'],
    #     fontName='Courier',
    #     fontSize=12,
    # )

    # summary = [
    #     Paragraph("Game Summary", summary_heading_style),
    #     Paragraph(game_summary_text, summary_text_style)
    # ]
    # box_content = [
    #     box_score_skaters,
    #     Spacer(1, 0.15 * inch),
    #     box_score_goalies,
    #     Spacer(1, 0.15 * inch),
    #     Paragraph("G = Goals", summary_text_style),
    #     Paragraph("A = Assists", summary_text_style),
    #     Paragraph("P = Points", summary_text_style),
    #     Paragraph("SOG = Shots on Goal", summary_text_style),
    #     Paragraph("PIM = Minutes in the Penalty Box", summary_text_style),
    #     Paragraph("SA = Shots Against", summary_text_style),
    #     Paragraph("SV = Saves", summary_text_style),
    #     Paragraph("SV% = Save Percentage", summary_text_style)
    # ]

    # box_column_table = Table(
    #     [[flowable] for flowable in box_content],
    #     colWidths=['*'],
    #     hAlign='CENTER'
    # )

    # yesterday_game_table = Table(
    #     [
    #         [summary, box_column_table]
    #     ],
    #     colWidths=[doc.width/2, doc.width/2], hAlign='LEFT'
    # )

    # --- Build the PDF ---
    story.append(Paragraph(title, TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 12))
    story.append(scores_table)
    story.append(Spacer(1, 24))
    story.append(standings_table)
    # story.append(PageBreak())
    # story.append(yesterday_game_table)
    doc.build(story)
    print(f"PDF file '{filename}' has been created.")

def get_scores_from_file(filename) -> list:
    scores_list = []
    with open(filename, "r") as file:
        scores_list = json.load(file)
    return scores_list


def get_standings_from_file(filename) -> pd.DataFrame:
    standings_df = pd.read_csv(filename)
    return standings_df

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

def get_paragraph_dimensions(p: Paragraph) -> dict:
    required_width, required_height = p.wrapOn(None, available_width, 100 * inch)
    dimensions = {
        "width_pt": required_width,
        "height_pt": required_height,
        "width_inch": required_width / inch,
        "height_inch": required_height / inch
    }
    # print(f"paragraph dimensions: {dimensions}")
    return dimensions

def get_chart_dimensions(c: Table) -> dict:
    required_width, required_height = c.wrap(available_width, 0)
    dimensions = {
      "width_pt": required_width,
      "height_pt": required_height,
      "width_inch": required_width / inch,
      "height_inch": required_height / inch
    }
    # print(f"chart dimensions: {dimensions}")
    return dimensions

def main(team_id = 4):
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%m/%d/%Y")

    # print(f"height, width = ({available_height, available_width})")

    # scores = get_scores_from_file("scores_20250818.json")
    # standings = get_standings_from_file("standings_20250818.csv")

    scores = get_game_scores_for_day(yesterday_str)
    standings = get_nba_standings()
    # game_pk = get_game_pk(team_id, yesterday)
    # box_score = get_nhl_boxscore(team_id, game_pk)

    # try:
    #     gemini_api_key = os.getenv("GEMINI_API_KEY")
    # except Exception:
    #     gemini_api_key = None
    # game_summarizer = GameSummaryGeneratorNBA(gemini_api_key)
    # game_summary_text = game_summarizer.generate_summary(game_pk)

    filename = f"NBA_Scores_{today.strftime('%Y%m%d')}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    generate_nba_report(scores, standings, output_file_path)
    # generate_nba_report(scores, standings, game_summary_text, box_score, output_file_path)


if __name__ == "__main__":

    # DUMP = True
    main()


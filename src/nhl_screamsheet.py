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
from typing import Optional, Dict, Any, List

try:
    from get_box_score_nhl import get_nhl_boxscore
    from get_game_summary import GameSummaryGeneratorNHL
    from screamsheet_structures import GameScore
    from utilities import dump_json
except Exception:
    from src.get_box_score_nhl import get_nhl_boxscore
    from src.get_game_summary import GameSummaryGeneratorNHL
    from src.screamsheet_structures import GameScore
    from src.utilities import dump_json

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
FLYERS = 4
FINAL_STATUS_CODE: str = 'OFF' # '3' typically means 'Final'

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
            dump_json(schedule_response, "nhl_get_game_pk")
        
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

def get_game_scores_for_day(game_date: str = None, dump: bool = False) -> List[GameScore]:
    """
    Fetches NHL game scores for a given day using the nhl_api wrapper 
    and returns them as a list of standardized GameScore objects.
    """
    if not game_date:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        game_date = yesterday.strftime("%Y-%m-%d")

    url = (
        f"https://api-web.nhle.com/v1/schedule/{game_date}"
    )

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if DUMP:
        dump_json(response, "nhl_game_scores")

    games: List[GameScore] = []
    games_for_the_day = data.get('gameWeek', [{}])[0].get('games', [])

    for game in games_for_the_day:
        game_state = game['gameState']
        
        if game_state in ['FINAL', 'OFF', 'LIVE']:
            # Use the same logic as before to extract data from the raw JSON
            away_place_name = game['awayTeam']['placeName']['default']
            home_place_name = game['homeTeam']['placeName']['default']
            away_team_name = game['awayTeam']['commonName']['default']
            home_team_name = game['homeTeam']['commonName']['default']
            away_full_name = away_place_name + " " + away_team_name
            home_full_name = home_place_name + " " + home_team_name
            
            away_score_raw = game['awayTeam'].get('score')
            home_score_raw = game['homeTeam'].get('score')
            away_score = int(away_score_raw) if away_score_raw is not None else 0
            home_score = int(home_score_raw) if home_score_raw is not None else 0
            
            game_info = GameScore(
                gameDate=game.get('startTimeUTC'),
                away_team=away_full_name,
                home_team=home_full_name,
                away_score=away_score,
                home_score=home_score,
                status=game_state
            )
            games.append(game_info)
        # Future games (PRE, FUT) are skipped to focus on scores

    return games

def get_division(record) -> str:
    base_url = f"https://statsapi.mlb.com"
    url = base_url + record.get("division", {}).get("link", {})
    response = requests.get(url)
    data = response.json()
    if DUMP:
        dump_json(response, "nhl_get_division")
    division = data["divisions"][0].get("name")
    return division

def get_nhl_standings() -> pd.DataFrame:
    """
    Fetches the current NHL standings using the dedicated 'now' endpoint.
    Returns the standings as a pandas DataFrame.
    """
    # The dedicated 'now' endpoint for current standings
    url = "https://api-web.nhle.com/v1/standings/now"
    
    # Using requests.get(url) as requested
    response = requests.get(url)
    response.raise_for_status() # Raises an error if the request failed

    data = response.json()

    if DUMP:
        dump_json(response, "nhl_get_nhl_standings")

    team_list: List[Dict[str, Any]] = []
    
    # Data is directly under the 'standings' key
    for team_record in data.get("standings", []):
        
        # Extract the team name and abbreviation
        name = team_record.get("teamName", {}).get("default")
        abbrev = team_record.get("teamAbbrev", {}).get("default")
        
        # Use division and conference names for grouping/sorting
        division = team_record.get("divisionName")
        conference = team_record.get("conferenceName")
        
        # Core NHL Standings Metrics
        wins = team_record.get("wins")
        losses = team_record.get("losses")
        otLosses = team_record.get("otLosses") # Critical for NHL points calculation
        points = team_record.get("points")
        pointPct = team_record.get("pointPctg") # Equivalent to MLB 'pct'
        
        # Rank is crucial for table display
        divisionRank = team_record.get("divisionSequence") # 'divisionSequence' is the division rank
        
        team_obj = {
            "conference": conference,
            "division": division,
            "team": f"{name}", # Combine name and abbrev for cleaner display
            "divisionRank": divisionRank,
            "GP": team_record.get("gamesPlayed"),
            "W": wins,
            "L": losses,
            "OTL": otLosses,
            "P": points,
            "PCT": pointPct,
            "GF": team_record.get("goalFor"),
            "GA": team_record.get("goalAgainst"),
            "DIFF": team_record.get("goalDifferential"),
            "STRK": team_record.get("streakCode") + str(team_record.get("streakCount"))
        }
        team_list.append(team_obj)

    standings = pd.DataFrame(team_list)
    
    # Sort the final output by Conference, Division, and then Rank
    return standings.sort_values(
        by=['conference', 'division', 'divisionRank'], 
        ascending=[True, True, True]
    ).reset_index(drop=True)

def create_standings_table(standings_df: pd.DataFrame):
    """
    Creates a master reportlab Table object for NHL standings with a 
    purely two-column layout: Eastern Conference vs Western Conference.
    """
    # 1. Separate Data by Conference
    eastern_conf = standings_df[standings_df['conference'] == 'Eastern']
    western_conf = standings_df[standings_df['conference'] == 'Western']

    # 2. Define the side-by-side layout (2 rows)
    # Row 1: Atlantic (E) vs Central (W)
    # Row 2: Metropolitan (E) vs Pacific (W)
    division_layout = [
        {'east': 'Atlantic', 'west': 'Central'},
        {'east': 'Metropolitan', 'west': 'Pacific'},
    ]

    # 3. Initialize Master Table Data Header
    # *** CHANGE: Removed the first empty string column ***
    grid_data = [
        [
            Paragraph("<b>EASTERN CONFERENCE</b>", CENTERED_STYLE), 
            Paragraph("<b>WESTERN CONFERENCE</b>", CENTERED_STYLE)
        ],
    ]
    
    # Define column widths for the inner tables (kept compact)
    INNER_COL_WIDTHS = [130, 20, 20, 25, 25]  
    
    # 4. Loop Twice to Build Two Side-by-Side Rows
    for row_info in division_layout:
        east_div_name = row_info['east']
        west_div_name = row_info['west']
        
        # *** CHANGE: row_list now only contains 2 elements (the two tables) ***
        row_list = []
        
        # --- Build Eastern Table ---
        east_group = eastern_conf[eastern_conf['division'] == east_div_name]
        
        if not east_group.empty:
            # Header includes the Division name
            INNER_HEADER = [f"{east_div_name} Division", "W", "L", "OTL", "P"]
            table_data = [INNER_HEADER] + east_group[['team', 'W', 'L', 'OTL', 'P']].values.tolist()
            
            # Apply table style
            table_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER')
                # ('FONTSIZE', (0, 0), (-1, -1), 8)
            ])
            
            standings_table = Table(table_data, colWidths=INNER_COL_WIDTHS)
            standings_table.setStyle(table_style)
            row_list.append(standings_table)
        else:
            row_list.append('')
            
        # --- Build Western Table ---
        west_group = western_conf[western_conf['division'] == west_div_name]
        
        if not west_group.empty:
            # Header includes the Division name
            INNER_HEADER = [f"{west_div_name} Division", "W", "L", "OTL", "P"]
            table_data = [INNER_HEADER] + west_group[['team', 'W', 'L', 'OTL', 'P']].values.tolist()
            
            # Re-apply the same table style
            standings_table = Table(table_data, colWidths=INNER_COL_WIDTHS)
            standings_table.setStyle(table_style)
            row_list.append(standings_table)
        else:
            row_list.append('')

        # Add the completed row to the master grid
        grid_data.append(row_list)
        
    # 5. Create the Master Table
    # *** CHANGE: Removed the first column width. Total width is 460 pts. ***
    MASTER_COL_WIDTHS = [230, 230] 
    
    master_table_style = TableStyle([
        # ('GRID', (0, 0), (-1, -1), 1, colors.black), # Optional: shows master table grid
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Alignment rule for the old left column is removed
    ])
    
    final_standings_table = Table(grid_data, colWidths=MASTER_COL_WIDTHS)
    final_standings_table.setStyle(master_table_style)
    get_chart_dimensions(final_standings_table)
    
    return final_standings_table

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
        if game.away_score is not None and game.home_score is not None:
            table_data = [
                [game.away_team, str(game.away_score)],
                [f"@{game.home_team}", str(game.home_score)]
            ]
            table_style = TableStyle([
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('LEFTPADDING', (0, 0), (0, -1), 0),
                ('RIGHTPADDING', (0, 0), (0, -1), 0),
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


# def generate_mlb_report(games, standings_df, game_summary_text="", box_score=None, filename="mlb_report.pdf"):
def generate_nhl_report(games, standings, game_summary_text="", box_score=None, filename="nhl_report.pdf"):
    """
    Generates a PDF report with game scores in two top columns and a standings grid at the bottom.

    Args:
        games (list): A list of dictionaries, where each dictionary represents a game.
        standings_df (pd.DataFrame): A DataFrame of team standings, assumed to be pre-sorted.
        filename (str): The name of the output PDF file.
    """
    # --- Adjust margins here ---
    title = "NHL Scream Sheet"
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
    print("make box scores table")
    box_score_skaters = box_score["skater_table"]
    box_score_goalies = box_score["goalie_table"]

    # Create a heading for the summary
    summary_heading_style = ParagraphStyle(
        name="SummaryHeading",
        parent=styles['h3'],
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceAfter=12,
    )

    summary_text_style = ParagraphStyle(
        name="SummaryText",
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=12,
    )

    print(f"[DEBUG] game_summary_text type: {type(game_summary_text)}")
    print(f"[DEBUG] game_summary_text length: {len(game_summary_text) if game_summary_text else 0}")
    print(f"[DEBUG] game_summary_text preview: {game_summary_text[:150] if game_summary_text else 'EMPTY'}")
    
    summary = [
        Paragraph("Game Summary", summary_heading_style),
    ]
    if game_summary_text and game_summary_text.strip():
        summary.append(Paragraph(game_summary_text, summary_text_style))
    else:
        summary.append(Paragraph(f"[ERROR] No game summary generated. Text was: {repr(game_summary_text)}", summary_text_style))
    box_content = [
        box_score_skaters,
        Spacer(1, 0.15 * inch),
        box_score_goalies,
        Spacer(1, 0.15 * inch),
        Paragraph("G = Goals", summary_text_style),
        Paragraph("A = Assists", summary_text_style),
        Paragraph("P = Points", summary_text_style),
        Paragraph("SOG = Shots on Goal", summary_text_style),
        Paragraph("PIM = Minutes in the Penalty Box", summary_text_style),
        Paragraph("SA = Shots Against", summary_text_style),
        Paragraph("SV = Saves", summary_text_style),
        Paragraph("SV% = Save Percentage", summary_text_style)
    ]

    box_column_table = Table(
        [[flowable] for flowable in box_content],
        colWidths=['*'],
        hAlign='CENTER'
    )

    yesterday_game_table = Table(
        [
            [summary, box_column_table]
        ],
        colWidths=[doc.width/2, doc.width/2], hAlign='LEFT'
    )

    # --- Build the PDF ---
    story.append(Paragraph(title, TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 12))
    story.append(scores_table)
    story.append(Spacer(1, 24))
    story.append(standings_table)
    story.append(PageBreak())
    story.append(yesterday_game_table)
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

def main(team_id = 4, day_offset=1):
    print("="*60)
    print("[NHL SCREAMSHEET] Starting main function")
    print("="*60)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    yesterday = today - timedelta(days=day_offset)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # print(f"height, width = ({available_height, available_width})")

    # scores = get_scores_from_file("scores_20250818.json")
    # standings = get_standings_from_file("standings_20250818.csv")

    scores = get_game_scores_for_day(yesterday_str)
    standings = get_nhl_standings()
    game_pk = get_game_pk(team_id, yesterday)
    print(f"[DEBUG] game_pk retrieved: {game_pk}")
    
    if game_pk is None:
        print(f"[ERROR] Could not find a game for team {team_id} on {yesterday_str}")
        game_summary_text = "No game found for this date."
        box_score = {'skater_table': Table([['No data']]), 'goalie_table': Table([['No data']])}
    else:
        box_score = get_nhl_boxscore(team_id, game_pk)
        print(f"[DEBUG] box_score retrieved")

        try:
            gemini_api_key = os.getenv("GEMINI_API_KEY")
        except Exception:
            gemini_api_key = None
        
        print(f"[DEBUG] gemini_api_key is set: {gemini_api_key is not None}")
        game_summarizer = GameSummaryGeneratorNHL(gemini_api_key)
        print(f"[DEBUG] game_summarizer created, _use_llm={game_summarizer._use_llm}")
        
        try:
            game_summary_text = game_summarizer.generate_summary(game_pk)
            print(f"[DEBUG] game_summary_text generated successfully")
            print(f"[DEBUG] game_summary_text length: {len(game_summary_text)}")
            print(f"[DEBUG] game_summary_text preview: {game_summary_text[:100]}")
        except Exception as e:
            print(f"[ERROR] Failed to generate summary: {e}")
            import traceback
            traceback.print_exc()
            game_summary_text = f"ERROR generating summary: {e}"

    filename = f"NHL_Scores_{today.strftime('%Y%m%d')}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    generate_nhl_report(scores, standings, game_summary_text, box_score, output_file_path)


if __name__ == "__main__":

    DUMP = True
    main(FLYERS, 2)

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

from get_game_summary import GameSummaryGenerator
from get_box_score import get_box_score

from dotenv import load_dotenv

ANGELS = 108
ASTROS = 117
ATHLETICS = 133
BLUEJAYS = 141
BRAVES = 144
BREWERS = 158
CARDINALS = 138
CUBS = 112
DIAMONDBACKS = 109
DODGERS = 119
GIANTS = 137
GUARDIANS = 114
MARINERS = 136
MARLINS = 146
METS = 121
NATIONALS = 120
ORIOLES = 110
PADRES = 135
PHILLIES = 143
PIRATES = 134
RANGERS = 140
RAYS = 139
REDSOX = 111
REDS = 113
ROCKIES = 115
ROYALS = 118
TIGERS = 116
TWINS = 142
WHITESOX = 145
YANKEES = 147


# Optional: Load environment variables from a .env file for API keys
load_dotenv()

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

def get_game_scores_for_day(game_date=None) -> list:
    if not game_date:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        game_date = yesterday.strftime("%Y-%m-%d")

    url = (
        f"https://statsapi.mlb.com/api/v1/schedule"
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

def get_division(record) -> str:
    base_url = f"https://statsapi.mlb.com"
    url = base_url + record.get("division", {}).get("link", {})
    response = requests.get(url)
    data = response.json()
    division = data["divisions"][0].get("name")
    return division

def get_standings(season: int =2025) -> pd.DataFrame:
    base_url = f"https://statsapi.mlb.com"
    url = f"{base_url}/api/v1/standings?season={season}&leagueId=103,104"
    response = requests.get(url)
    response.raise_for_status()  # Raises an error if the request failed

    data = response.json()

    team_list = []
    for record in data.get("records", []):
        division = get_division(record)
        for team in record.get("teamRecords", []):
            name = team.get("team", {}).get("name")
            wins = team["leagueRecord"].get("wins")
            losses = team["leagueRecord"].get("losses")
            ties = team["leagueRecord"].get("ties")
            pct = team["leagueRecord"].get("pct")
            rank = team.get("divisionRank")
            team_obj = {
                "division": division,
                "team": name,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "pct": pct,
                "divisionRank": rank
            }
            team_list.append(team_obj)

    standings = pd.DataFrame(team_list)
    return standings.sort_values(by=['division', 'divisionRank'], ascending=[True, True])

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


def generate_mlb_report(games, standings_df, game_summary_text="", box_score=None, filename="mlb_report.pdf"):
    """
    Generates a PDF report with game scores in two top columns and a standings grid at the bottom.

    Args:
        games (list): A list of dictionaries, where each dictionary represents a game.
        standings_df (pd.DataFrame): A DataFrame of team standings, assumed to be pre-sorted.
        filename (str): The name of the output PDF file.
    """
    # --- Adjust margins here ---
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

    # --- Header (Title and Subtitle) ---
    # story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    # story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    # story.append(Spacer(1, 12))

    # --- Prepare Game Scores for Two Columns ---
    scores_left = []
    scores_center = []
    scores_right = []
    for i, game in enumerate(games):
        if game.get("away_score") is not None and game.get("home_score") is not None:
            table_data = [
                [game['away_team'], str(game['away_score'])],
                [f"@{game['home_team']}", str(game['home_score'])]
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

    # -- add scores_table
    # story.append(scores_table)
    # story.append(Spacer(1, 24))

    # --- Standings as a 2x3 Grid ---
    al_divisions = standings_df[standings_df['division'].str.contains('American League')]
    nl_divisions = standings_df[standings_df['division'].str.contains('National League')]
    divisions_order = ['East', 'Central', 'West']

    grid_data = [
        ['', Paragraph("<b>American League</b>", CENTERED_STYLE), Paragraph("<b>National League</b>", CENTERED_STYLE)],
    ]
    for geography in divisions_order:
        row_list = [Paragraph(f"<b>{geography}</b>", CENTERED_STYLE)]
        al_group = al_divisions[al_divisions['division'].str.contains(geography)]
        nl_group = nl_divisions[nl_divisions['division'].str.contains(geography)]
        
        for group in [al_group, nl_group]:
            if not group.empty:
                header = ["Team", "W", "L", "%"]
                table_data = [header] + group[['team', 'wins', 'losses', 'pct']].values.tolist()
                table_style = TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ])
                standings_table = Table(table_data, colWidths=[150, 30, 30, 30])
                standings_table.setStyle(table_style)
                row_list.append(standings_table)
            else:
                row_list.append('')
        grid_data.append(row_list)
        
    master_table_style = TableStyle([
        # ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
        # ('BACKGROUND', (1, 0), (-1, 0), colors.lightgrey),
        # ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
    ])
    final_standings_table = Table(grid_data, colWidths=[60, 250, 250])
    final_standings_table.setStyle(master_table_style)

    # -- Add standings tables
    # story.append(final_standings_table)

    # --- NEW: Add a page break and the game summary ---
    # story.append(PageBreak())

    # Create a heading for the summary
    summary_heading_style = ParagraphStyle(
        name="SummaryHeading",
        parent=styles['h3'],
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceAfter=12,
    )
    # story.append(Paragraph("Game Summary", summary_heading_style))
    
    # Add the game summary text as a Paragraph
    summary_text_style = styles['Normal']
    summary_text_style.fontName = 'Helvetica'
    summary_text_style = ParagraphStyle(
        name="SummaryText",
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=12,
    )
    # story.append(Paragraph(game_summary_text, summary_text_style))

    boxscore_table = create_boxscore_tables(box_score)

    summary = [
        Paragraph("Game Summary", summary_heading_style),
        Paragraph(game_summary_text, summary_text_style)
    ]
    box_content = [
        boxscore_table['batting_table'],
        Spacer(1, 0.15 * inch),
        boxscore_table['pitching_table']
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
    story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 12))
    story.append(scores_table)
    story.append(Spacer(1, 24))
    story.append(yesterday_game_table)
    story.append(PageBreak())
    story.append(final_standings_table)
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

def main(team_id = PHILLIES):
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # scores = get_scores_from_file("scores_20250818.json")
    # standings = get_standings_from_file("standings_20250818.csv")
    scores = get_game_scores_for_day()
    standings = get_standings(2025)

    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
    except Exception:
        gemini_api_key = None
    game_summarizer = GameSummaryGenerator(gemini_api_key)
    game_summary_text = game_summarizer.generate_summary(team_id=team_id, date_str=yesterday_str)

    box_score = get_box_score(team_id, yesterday)

    filename = f"MLB_Scores_{today_str}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    generate_mlb_report(scores, standings, game_summary_text, box_score, output_file_path)


if __name__ == "__main__":

    main()




from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
import re

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

def get_current_nfl_week(season: int) -> int | None:
    """
    Determines the current NFL regular season week for a given season.

    Args:
        season (int): The NFL season year (e.g., 2025).

    Returns:
        int: The number of the current regular season week, or None if not found.
    """
    url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching scoreboard data: {e}")
        return None

    # The week information is nested under 'week'
    week_info = data.get("week")
    
    # Check if the week object exists and has a valid number
    if week_info and "number" in week_info:
        return week_info["number"]
    else:
        print("Could not determine the current week from the API response.")
        return None

def get_nfl_weekly_scores(season, week) -> list:
    """
    Fetches NFL game scores for a specific season and week from ESPN's unofficial API.
    """
    url = (
        f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?dates={season}"
        f"&seasontype=2"  # 2 is for regular season
        f"&week={week}"
    )

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from ESPN API: {e}")
        return []

    games = []
    # ESPN's data is nested, so you need to navigate through events
    for event in data.get("events", []):
        competitions = event.get("competitions", [])
        if competitions:
            game = competitions[0]  # Get the first (and only) competition for the event
            
            # Check if the game is over
            if game.get("status", {}).get("type", {}).get("name") == "STATUS_FINAL":
                home_team = game["competitors"][0]
                away_team = game["competitors"][1]
                
                game_info = {
                    "gameId": event.get("id"),
                    "date": event.get("date"),
                    "away_team": away_team["team"]["displayName"],
                    "away_score": away_team.get("score"),
                    "home_team": home_team["team"]["displayName"],
                    "home_score": home_team.get("score"),
                    "status": game["status"]["type"]["name"]
                }
                games.append(game_info)
                
    return games

def get_nfl_data(season: int = 2025) -> pd.DataFrame:
    """
    Fetches NFL team data and conference standings from ESPN APIs, 
    and combines them into a single, clean DataFrame.
    """
    # 1. Fetch team names and IDs from the dedicated teams API endpoint
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
    try:
        teams_response = requests.get(teams_url)
        teams_response.raise_for_status()
        teams_data = teams_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching team data from {teams_url}: {e}")
        return pd.DataFrame()

    # Build the team ID to name lookup dictionary
    team_name_lookup = {}
    try:
        # Navigate the JSON to get to the list of teams
        teams_list = teams_data.get("sports", [])[0].get("leagues", [])[0].get("teams", [])
        for team_entry in teams_list:
            team_info = team_entry.get("team", {})
            team_id = int(team_info.get("id"))
            display_name = team_info.get("displayName")
            if team_id and display_name:
                team_name_lookup[team_id] = display_name
    except (IndexError, ValueError) as e:
        print(f"Error parsing teams JSON: {e}")
        return pd.DataFrame()

    print(f"Successfully created a lookup for {len(team_name_lookup)} NFL teams.")

    # 2. Fetch conference standings using the previous logic
    base_standings_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/types/2/groups/"
    conferences = {7: "NFC", 8: "AFC"}
    all_standings = []
    
    # Regular expression to extract the ID from the URL reference
    id_pattern = re.compile(r"/teams/(\d+)")
    
    for group_id, conference_name in conferences.items():
        url = f"{base_standings_url}{group_id}/standings/0"
        
        try:
            standings_response = requests.get(url)
            standings_response.raise_for_status()
            standings_data = standings_response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching standings for {conference_name}: {e}")
            continue

        for team_entry in standings_data.get("standings", []):
            team_ref = team_entry.get("team", {}).get("$ref", "")
            
            # Extract the team ID from the URL reference using the regex
            match = id_pattern.search(team_ref)
            if not match:
                continue
            
            team_id = int(match.group(1))

            overall_record = team_entry.get("records", [])[0]
            stats = overall_record.get("stats", [])
            stat_map = {s['abbreviation']: s['value'] for s in stats}

            team_obj = {
                "Conference": conference_name,
                "Team": team_name_lookup.get(team_id, "Unknown Team"),
                "Wins": int(stat_map.get('W', 0)),
                "Losses": int(stat_map.get('L', 0)),
                "Ties": int(stat_map.get('T', 0)),
                "Win Pct": stat_map.get('PCT', 0.0)
            }
            all_standings.append(team_obj)
            
    final_standings = pd.DataFrame(all_standings)
    
    # Sort the final DataFrame by conference and win percentage
    return final_standings.sort_values(by=['Conference', 'Win Pct', 'Wins'], ascending=[True, False, False])


def generate_nfl_report(games, standings_df=None, game_summary_text="", filename="nfl_report.pdf"):
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
    story.append(Paragraph("NFL Scream Sheet", TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 12))

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
            game_table = Table(table_data, colWidths=[85, 50])
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

    scores_table = Table([[scores_left, scores_center, scores_right]], colWidths=[doc.width/3, doc.width/3, doc.width/3], hAlign='LEFT')
    story.append(scores_table)
    story.append(Spacer(1, 12))

    # Get the data for each conference
    afc_standings = standings_df[standings_df['Conference'] == 'AFC']
    nfc_standings = standings_df[standings_df['Conference'] == 'NFC']

    # Prepare the data for the two tables
    header = ["Team", "W", "L", "T", "%"]
    
    afc_table_data = [header] + afc_standings[['Team', 'Wins', 'Losses', 'Ties', 'Win Pct']].values.tolist()
    nfc_table_data = [header] + nfc_standings[['Team', 'Wins', 'Losses', 'Ties', 'Win Pct']].values.tolist()

    # Define the table style
    table_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    # Create the two individual tables
    afc_table = Table(afc_table_data, colWidths=[130, 30, 30, 30, 30])
    afc_table.setStyle(table_style)
    
    nfc_table = Table(nfc_table_data, colWidths=[130, 30, 30, 30, 30])
    nfc_table.setStyle(table_style)

    # Combine the two tables into a single master table
    master_table_data = [
        [Paragraph("<b>AFC Standings</b>", CENTERED_STYLE), Paragraph("<b>NFC Standings</b>", CENTERED_STYLE)],
        [afc_table, nfc_table]
    ]

    master_table_style = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])

    final_table = Table(master_table_data, colWidths=[250, 250])
    final_table.setStyle(master_table_style)
    story.append(final_table)

    # # --- NEW: Add a page break and the game summary ---
    # story.append(PageBreak())

    # # Create a heading for the summary
    # summary_heading_style = ParagraphStyle(
    #     name="SummaryHeading",
    #     parent=styles['h3'],
    #     fontName='Helvetica-Bold',
    #     fontSize=14,
    #     spaceAfter=12,
    # )
    # story.append(Paragraph("Game Summary", summary_heading_style))
    
    # # Add the game summary text as a Paragraph
    # summary_text_style = styles['Normal']
    # summary_text_style.fontName = 'Helvetica'
    # summary_text_style = ParagraphStyle(
    #     name="SummaryText",
    #     parent=styles['Normal'],
    #     fontName='Courier',
    #     fontSize=12,
    # )
    # story.append(Paragraph(game_summary_text, summary_text_style))


    # --- Build the PDF ---
    doc.build(story)
    print(f"PDF file '{filename}' has been created.")


if __name__ == "__main__":

    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Example usage:
    # To get the scores for Week 2 of the 2025 season
    # Note: You may need to dynamically determine the current week and season
    # based on the current date and the NFL schedule.
    current_season = 2025
    current_week = get_current_nfl_week(current_season)

    weekly_scores = get_nfl_weekly_scores(current_season, current_week)
    # if weekly_scores:
    #     for game in weekly_scores:
    #         print(f"{game['away_team']} {game['away_score']} at {game['home_team']} {game['home_score']} - Final")
    # else:
    #     print("No completed games found for this week.")

    # scores = get_scores_from_file("scores_20250818.json")
    # standings = get_standings_from_file("standings_20250818.csv")
    # scores = get_game_scores_for_day()
    # standings = get_standings(2025)

    # game_summarizer = GameSummaryGenerator()
    # game_summary_text = game_summarizer.generate_summary(date_str=yesterday_str)

    filename = f"NFL_Scores_{today_str}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    generate_nfl_report(weekly_scores, standings_df, filename=output_file_path)

    print(f"PDF saved as: {filename}")


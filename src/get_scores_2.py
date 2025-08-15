from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate, FrameBreak
import pandas as pd
import requests


def get_mlb_scores_last_24_hours():
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    start_date = yesterday.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    url = (
        f"https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1"
        f"&startDate={start_date}"
        f"&endDate={end_date}"
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

def get_division(record):
    base_url = f"https://statsapi.mlb.com"
    url = base_url + record.get("division", {}).get("link", {})
    response = requests.get(url)
    data = response.json()
    division = data["divisions"][0].get("name")
    return division

def get_standings(season=2025):
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


def generate_mlb_report(games, standings_df, filename="mlb_report.pdf"):
    """
    Generates a two-column PDF report with MLB game scores and team standings.

    Args:
        games (list): A list of dictionaries, where each dictionary represents a game.
        standings_df (pd.DataFrame): A DataFrame of team standings, assumed to be pre-sorted.
        filename (str): The name of the output PDF file.
    """
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # --- Header (Title and Subtitle) ---
    story.append(Paragraph("MLB Scream Sheet", styles['h1']))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), styles['h2']))
    story.append(Spacer(1, 24))

    # --- Prepare the main content for the two columns ---
    # Left Column: Game Scores
    for game in games:
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
            game_table = Table(table_data, colWidths=[200, 50])
            game_table.setStyle(table_style)
            story.append(game_table)
            story.append(Spacer(1, 10))

    # Use FrameBreak to switch to the right column
    story.append(FrameBreak())

    # Right Column: Standings
    division_header_style = styles['h3']
    division_header_style.alignment = 1

    for division_name, group in standings_df.groupby('division'):
        standings_story = [Paragraph(division_name, division_header_style), Spacer(1, 6)]
        header = ["Team", "W", "L"]
        table_data = [header]
        for index, row in group.iterrows():
            table_data.append([row['team'], row['wins'], row['losses']])
        
        table_style = TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ])
        standings_table = Table(table_data, colWidths=[150, 30, 30])
        standings_table.setStyle(table_style)
        standings_story.append(standings_table)
        standings_story.append(Spacer(1, 12))
        
        # Add the standings story for this division to the main story
        story.extend(standings_story)

    # --- Define and assign frames for a two-column layout ---
    # Create two frames for your two columns
    frame_left = Frame(doc.leftMargin, doc.bottomMargin, doc.width/2 - 6, doc.height, id='col_left')
    frame_right = Frame(doc.leftMargin + doc.width/2 + 6, doc.bottomMargin, doc.width/2 - 6, doc.height, id='col_right')

    # Create a PageTemplate and assign the frames
    two_column_template = PageTemplate(id='TwoColumns', frames=[frame_left, frame_right])
    doc.addPageTemplates([two_column_template])

    # --- Build the PDF ---
    doc.build(story)
    print(f"PDF file '{filename}' has been created.")




if __name__ == "__main__":
    scores = get_mlb_scores_last_24_hours()
    standings = get_standings(2025)
    today_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"MLB_Scores_{today_str}.pdf"
    # make_pdf(scores, standings, filename)
    generate_mlb_report(scores, standings, filename)
    print(f"PDF saved as: {filename}")


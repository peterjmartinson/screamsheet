import requests
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

def make_pdf(games, filename):
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

    y -= 100

    c.setFont("Helvetica", 12)
    i = 0
    for game in games:
        # Only print scores for games that have scores
        if game["away_score"] is not None and game["home_score"] is not None:
            away_text = f"{game['away_team']}"
            home_text = f"@ {game['home_team']}"
            score_width = 350  # Space reserved for scores

            # Calculate where to right-align scores
            text_width = width - margin * 2 - score_width

            box_x = column_left_x
            inc_y = -16
            if i%2 != 0:
                box_x = column_right_x
                inc_y = 22
            i += 1
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

    c.save()

if __name__ == "__main__":
    scores = get_mlb_scores_last_24_hours()
    today_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"MLB_Scores_{today_str}.pdf"
    make_pdf(scores, filename)
    print(f"PDF saved as: {filename}")

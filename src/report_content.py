import pandas as pd
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

styles = getSampleStyleSheet()

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

def create_scores_flowables(games: list) -> list:
    """
    Creates a list of reportlab flowables for the scores section.
    """
    story = [
        Paragraph("<b>Recent Game Scores</b>", styles['Heading3']),
        Spacer(1, 12)
    ]
    for game in games:
        table_data = [
            [Paragraph(game['away_team']), Paragraph(str(game['away_score']))],
            [Paragraph(f"@{game['home_team']}"), Paragraph(str(game['home_score']))]
        ]
        table_style = TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('RIGHTPADDING', (0, 0), (0, -1), 0),
        ])
        game_table = Table(table_data, colWidths=[150, 50])
        game_table.setStyle(table_style)
        story.append(game_table)
        story.append(Spacer(1, 12))
    return story

def create_standings_flowables(standings: pd.DataFrame) -> list:
    """
    Creates a list of reportlab flowables for the standings section.
    """
    story = [
        Paragraph("<b>Current Standings</b>", styles['Heading3']),
        Spacer(1, 12)
    ]
    for division_name, group in standings.groupby('division'):
        story.append(Paragraph(f"<b>{division_name}</b>", styles['h3']))
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
        story.append(standings_table)
        story.append(Spacer(1, 24))
    return story

"""All-Star Game screamsheet renderers (`AllStarGameScoresSection`, `AllStarGameSummarySection`, `AllStarSideBySideBoxScoreSection`)."""
import logging
from datetime import datetime
from typing import List, Any, Optional, Dict
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from ..base import Section, DataProvider

logger = logging.getLogger(__name__)


class AllStarGameScoresSection(Section):
    """
    Section for displaying the MLB All-Star Game score on the front page.
    """

    def __init__(self, title: str, provider: DataProvider, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.page_slot = "front"
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="AllStarScoreSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )

    def fetch_data(self):
        """Fetch All-Star game scores from the provider."""
        self.data = self.provider.get_allstar_game_scores(self.date)

    def render(self) -> List[Any]:
        """Render the All-Star game score section."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return [Paragraph("<b>No completed All-Star Game found for this date.</b>", self.subtitle_style)]

        elements = []
        for game in self.data:
            if game.get("away_score") is not None and game.get("home_score") is not None:
                table_data = [
                    [game['away_team'], str(game['away_score'])],
                    [game['home_team'], str(game['home_score'])],
                ]
                col_widths = [220, 50]
                table_style = TableStyle([
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ])
                game_table = Table(table_data, colWidths=col_widths, hAlign='CENTER')
                game_table.setStyle(table_style)
                elements.append(game_table)
                elements.append(Spacer(1, 14))

        return elements


class AllStarGameSummarySection(Section):
    """
    Section for displaying the ~500-word regular All-Star game summary on the front page.
    """

    def __init__(self, title: str, provider: DataProvider, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.page_slot = "front"
        self.styles = getSampleStyleSheet()

        self.summary_text_style = ParagraphStyle(
            name="AllStarSummaryText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=14.5,
            spaceAfter=10,
            alignment=TA_LEFT
        )

    def fetch_data(self):
        """Fetch game summary from the provider."""
        self.data = self.provider.get_allstar_game_summary(self.date)

    def render(self) -> List[Any]:
        """Render the All-Star game summary section."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return []

        elements = []
        # Split text by double newlines if multiple paragraphs returned by LLM
        paragraphs = [p.strip() for p in self.data.split("\n\n") if p.strip()]
        for p in paragraphs:
            elements.append(Paragraph(p, self.summary_text_style))

        return elements


class AllStarSideBySideBoxScoreSection(Section):
    """
    Section displaying side-by-side box scores on the back page:
    American League on the Left column, National League on the Right column.
    """

    def __init__(self, title: str, provider: DataProvider, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.page_slot = "back"
        self.styles = getSampleStyleSheet()

        self.team_header_style = ParagraphStyle(
            name="AllStarTeamHeader",
            parent=self.styles['h4'],
            fontName='Helvetica-Bold',
            fontSize=11,
            spaceAfter=6,
            alignment=TA_CENTER
        )

    def fetch_data(self):
        """Fetch side-by-side AL and NL box scores from the provider."""
        self.data = self.provider.get_allstar_box_scores(self.date)

    def render(self) -> List[Any]:
        """Render side-by-side two-column box scores."""
        if not self.data:
            self.fetch_data()

        if not self.data or not isinstance(self.data, dict):
            return []

        al_column = self._render_team_column(self.data.get('AL', {}))
        nl_column = self._render_team_column(self.data.get('NL', {}))

        two_column_table = Table(
            [[al_column, nl_column]],
            colWidths=['50%', '50%'],
            rowHeights=[None]
        )
        two_column_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 8),
            ('LEFTPADDING', (1, 0), (1, 0), 8),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        return [two_column_table]

    def _render_team_column(self, team_data: dict) -> List[Any]:
        """Render batting and pitching tables for a single league column."""
        if not team_data:
            return [Paragraph("No box score data", self.styles['Normal'])]

        elements = []
        team_name = team_data.get('team_name', 'Unknown Team')
        elements.append(Paragraph(f"<b>{team_name}</b>", self.team_header_style))

        # Batting table
        batting_stats = team_data.get('batting_stats', [])
        if batting_stats:
            hitting_header = ["Batter", "AB", "R", "H", "HR", "RBI", "BB", "SO"]
            hitting_data = [hitting_header]
            for p in batting_stats:
                hitting_data.append([
                    p['name'],
                    str(p.get('AB', 0)),
                    str(p.get('R', 0)),
                    str(p.get('H', 0)),
                    str(p.get('HR', 0)),
                    str(p.get('RBI', 0)),
                    str(p.get('BB', 0)),
                    str(p.get('SO', 0))
                ])

            hitting_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ])
            hitting_table = Table(hitting_data, colWidths=[100, 22, 22, 22, 22, 22, 22, 22])
            hitting_table.setStyle(hitting_style)
            elements.append(hitting_table)
            elements.append(Spacer(1, 8))

        # Pitching table
        pitching_stats = team_data.get('pitching_stats', [])
        if pitching_stats:
            pitching_header = ["Pitcher", "IP", "H", "R", "ER", "BB", "SO"]
            pitching_data = [pitching_header]
            for p in pitching_stats:
                pitching_data.append([
                    p['name'],
                    str(p.get('IP', '0.0')),
                    str(p.get('H', 0)),
                    str(p.get('R', 0)),
                    str(p.get('ER', 0)),
                    str(p.get('BB', 0)),
                    str(p.get('SO', 0))
                ])

            pitching_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ])
            pitching_table = Table(pitching_data, colWidths=[110, 24, 24, 24, 24, 24, 24])
            pitching_table.setStyle(pitching_style)
            elements.append(pitching_table)

        return elements

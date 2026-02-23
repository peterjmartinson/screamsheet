"""Game scores section renderer."""
from datetime import datetime
from typing import List, Any
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section, DataProvider


class GameScoresSection(Section):
    """
    Section for displaying game scores.
    
    Shows all game scores from a specific date in a multi-column layout.
    """
    
    def __init__(self, title: str, provider: DataProvider, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.styles = getSampleStyleSheet()
        
        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )
    
    def fetch_data(self):
        """Fetch game scores from the provider."""
        self.data = self.provider.get_game_scores(self.date)
    
    def render(self) -> List[Any]:
        """Render the game scores section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Section title suppressed (document top-level title used instead)
        
        # Organize games into three columns
        scores_left = []
        scores_center = []
        scores_right = []
        
        for i, game in enumerate(self.data):
            if game.get("away_score") is not None and game.get("home_score") is not None:
                table_data = [
                    [game['away_team'], str(game['away_score'])],
                    [f"@{game['home_team']}", str(game['home_score'])]
                ]
                table_style = TableStyle([
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
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
        
        # Create three-column layout
        # Use available width (letter size minus margins)
        available_width = 540  # 8.5" * 72 - 72 (margins)
        col_width = available_width / 3
        
        scores_table = Table(
            [[scores_left, scores_center, scores_right]],
            colWidths=[col_width, col_width, col_width],
            hAlign='LEFT'
        )
        
        elements.append(scores_table)
        
        return elements

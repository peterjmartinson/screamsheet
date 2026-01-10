"""Game summary section renderer."""
from datetime import datetime
from typing import List, Any
from reportlab.platypus import Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section, DataProvider


class GameSummarySection(Section):
    """
    Section for displaying game summaries.
    
    Shows LLM-generated narrative summaries of games.
    Currently only fully implemented for MLB and NHL.
    """
    
    def __init__(self, title: str, provider: DataProvider, team_id: int, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.team_id = team_id
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
        
        self.summary_text_style = ParagraphStyle(
            name="SummaryText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
        )
    
    def fetch_data(self):
        """Fetch game summary from the provider."""
        self.data = self.provider.get_game_summary(self.team_id, self.date)
    
    def render(self) -> List[Any]:
        """Render the game summary section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Add section title
        elements.append(Paragraph(self.title, self.subtitle_style))
        elements.append(Spacer(1, 12))
        
        # Add summary text
        elements.append(Paragraph(self.data, self.summary_text_style))
        
        return elements

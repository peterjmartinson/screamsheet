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
        self.page_slot = "back"
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
        if self.data is None:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Section title suppressed (document top-level title used instead)
        
        # Add summary paragraphs
        paragraphs = [p for p in str(self.data).split("\n\n") if p.strip()]
        for p in paragraphs:
            elements.append(Paragraph(p, self.summary_text_style))
            elements.append(Spacer(1, 6))
        
        return elements

    def render_markdown(self) -> str:
        """Render the game summary in Markdown format."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return ""

        return f"### {self.title}\n\n{self.data}"

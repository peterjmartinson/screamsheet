"""Weather section renderer."""
from datetime import datetime
from typing import List, Any
from reportlab.platypus import Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section


class WeatherSection(Section):
    """
    Section for displaying weather reports.
    
    Shows weather information for the current day.
    """
    
    def __init__(self, title: str, date: datetime):
        super().__init__(title)
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
        
        self.weather_text_style = ParagraphStyle(
            name="WeatherText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
        )
    
    def fetch_data(self):
        """Fetch weather data."""
        try:
            from src.print_weather import generate_weather_report
            self.data = generate_weather_report()
        except Exception as e:
            print(f"Error getting weather report: {e}")
            self.data = None
    
    def render(self) -> List[Any]:
        """Render the weather section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Section title suppressed (document top-level title used instead)
        
        # The weather data is already a Table flowable from generate_weather_report()
        # Just add it directly instead of wrapping in Paragraph
        elements.append(self.data)
        
        return elements

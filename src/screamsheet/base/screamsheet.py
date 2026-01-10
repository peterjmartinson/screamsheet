"""Base screamsheet class that all screamsheets inherit from."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from .section import Section


class BaseScreamsheet(ABC):
    """
    Base class for all screamsheets (sports or news).
    
    A screamsheet is composed of multiple sections that are rendered in order.
    Each screamsheet type (MLB, NHL, News, etc.) implements the abstract methods
    to define its specific sections and generate the PDF.
    """
    
    def __init__(self, output_filename: str, date: Optional[datetime] = None):
        """
        Initialize the screamsheet.
        
        Args:
            output_filename: Path to save the generated PDF
            date: Target date for the screamsheet (defaults to yesterday)
        """
        self.output_filename = output_filename
        self.date = date or (datetime.now() - timedelta(days=1))
        self.sections: List[Section] = []
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
    def _setup_styles(self):
        """Setup common paragraph styles used across screamsheets."""
        self.title_style = ParagraphStyle(
            name="Title",
            parent=self.styles['h1'],
            fontName='Helvetica-Bold',
            fontSize=28,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        self.subtitle_style = ParagraphStyle(
            name="Subtitle",
            parent=self.styles['h2'],
            fontName='Helvetica',
            fontSize=18,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        self.centered_style = ParagraphStyle(
            name="CenteredText",
            alignment=TA_CENTER
        )
    
    @abstractmethod
    def build_sections(self) -> List[Section]:
        """
        Build and return all sections for this screamsheet.
        
        This method should create instances of Section objects, each representing
        a different part of the screamsheet (e.g., game scores, standings, etc.).
        
        Returns:
            List of Section objects to be rendered
        """
        pass
    
    @abstractmethod
    def get_title(self) -> str:
        """Return the title for this screamsheet."""
        pass
    
    def generate(self) -> str:
        """
        Generate the complete screamsheet PDF.
        
        Returns:
            Path to the generated PDF file
        """
        # Build all sections
        self.sections = self.build_sections()
        
        # Create PDF
        doc = SimpleDocTemplate(
            self.output_filename,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        # Build story (content)
        story = []
        
        # Add title
        title = Paragraph(self.get_title(), self.title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Add each section
        for section in self.sections:
            if section.has_content():
                story.extend(section.render())
                story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story)
        
        return self.output_filename
    
    def add_section(self, section: Section):
        """Add a section to the screamsheet."""
        self.sections.append(section)

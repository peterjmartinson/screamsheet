"""Base screamsheet class that all screamsheets inherit from."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, List, Optional
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

from .section import Section


class BaseScreamsheet(ABC):
    """
    Base class for all screamsheets (sports or news).
    
    A screamsheet is composed of multiple sections that are rendered in order.
    Each screamsheet type (MLB, NHL, News, etc.) implements the abstract methods
    to define its specific sections and generate the PDF.
    """
    
    def __init__(self, output_filename: str, date: Optional[datetime] = None, display_date: Optional[datetime] = None):
        """
        Initialize the screamsheet.
        
        Args:
            output_filename: Path to save the generated PDF
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
        """
        self.output_filename = output_filename
        self.date = date or (datetime.now() - timedelta(days=1))
        self.display_date: datetime = display_date if display_date is not None else self.date
        self.sections: List[Section] = []
        self.styles = getSampleStyleSheet()
        self.branding: str = self._load_branding()
        self._setup_styles()
        
    def _load_branding(self) -> str:
        """Load branding text from config, returning empty string on any failure."""
        try:
            from ..config import load_config
            return load_config().branding
        except Exception:
            return ""

    def _draw_branding_footer(self, canvas: Any, doc: Any) -> None:
        """Draw the branding footer at the bottom of a page via canvas callback."""
        if not self.branding:
            return
        text = self.branding.upper()
        page_width, _ = letter
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.black)
        canvas.drawCentredString(page_width / 2, 13, text)
        canvas.restoreState()

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
        """Return the main title for this screamsheet."""
        pass
    
    def get_subtitle(self) -> Optional[str]:
        """
        Return an optional subtitle for this screamsheet.
        
        Override this method to add a subtitle line (e.g., news source).
        Returns None by default.
        """
        return None
    
    def get_date_string(self) -> str:
        """Return the formatted date string (uses display_date for the subtitle)."""
        return self.display_date.strftime("%B %d, %Y")
    
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
        
        # Add subtitle if present (e.g., news source)
        subtitle = self.get_subtitle()
        if subtitle:
            # Use italic style for subtitle
            subtitle_para = Paragraph(f"<i>{subtitle}</i>", self.subtitle_style)
            story.append(subtitle_para)
        
        # Add date
        date_para = Paragraph(self.get_date_string(), self.subtitle_style)
        story.append(date_para)
        story.append(Spacer(1, 12))
        
        # Add each section
        for section in self.sections:
            if section.has_content():
                story.extend(section.render())
                story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(
            story,
            onFirstPage=self._draw_branding_footer,
            onLaterPages=self._draw_branding_footer,
        )
        
        return self.output_filename
    
    def add_section(self, section: Section):
        """Add a section to the screamsheet."""
        self.sections.append(section)

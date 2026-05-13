"""Base screamsheet class that all screamsheets inherit from."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from .section import Section


def _sanitize_masthead(text: str) -> str:
    """Strip protocol prefix and convert to ALL CAPS for display."""
    for prefix in ("https://", "http://"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    return text.lower()


class BaseScreamsheet(ABC):
    """
    Base class for all screamsheets (sports or news).
    
    A screamsheet is composed of multiple sections that are rendered in order.
    Each screamsheet type (MLB, NHL, News, etc.) implements the abstract methods
    to define its specific sections and generate the PDF.
    """
    
    def __init__(
        self,
        output_filename: str,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        masthead: str = "",
    ):
        """
        Initialize the screamsheet.

        Args:
            output_filename:   Path to save the generated PDF
            date:              Target date for game data lookups (defaults to yesterday)
            display_date:      Date shown in the subtitle header (defaults to date)
            masthead:          Branding text shown in the top-right "ear" box on every
                               page header.  Pass an empty string (default) to suppress
                               the ear entirely.
        """
        self.output_filename = output_filename
        self.date = date or (datetime.now() - timedelta(days=1))
        self.display_date: datetime = display_date if display_date is not None else self.date
        self.masthead: str = masthead
        self.sections: List[Section] = []
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
    def _setup_styles(self):
        """Setup common paragraph styles used across screamsheets."""
        self.title_style = ParagraphStyle(
            name="Title",
            parent=self.styles['h1'],
            fontName='Helvetica-BoldOblique',
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
    
    def _build_story(self) -> List[Any]:
        """Assemble and return the full ReportLab story from the current sections.

        Requires ``self.sections`` to already be populated (call ``build_sections()``
        and assign before calling this).  Safe to call multiple times — each call
        invokes ``section.render()`` afresh, so callers can mutate section params
        between calls (e.g. the overflow-compression loop in SportsScreamsheet).
        """
        story: List[Any] = []

        # ---- Centred header ---------------------------------------------------
        story.append(Paragraph(self.get_title().upper(), self.title_style))
        subtitle = self.get_subtitle()
        if subtitle:
            story.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        date_line = self.get_date_string()
        if self.masthead:
            ear = _sanitize_masthead(self.masthead)
            date_line = f"{date_line} | <font size='12'>{ear}</font>"
        story.append(Paragraph(date_line, self.subtitle_style))
        # -----------------------------------------------------------------------

        story.append(Spacer(1, 12))
        # -------------------------------------------------------------------------

        # Sections
        for section in self.sections:
            if section.has_content():
                story.extend(section.render())
                story.append(Spacer(1, 20))

        return story

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
        
        story = self._build_story()
        
        # Build PDF
        doc.build(story)

        return self.output_filename
    
    def add_section(self, section: Section):
        """Add a section to the screamsheet."""
        self.sections.append(section)

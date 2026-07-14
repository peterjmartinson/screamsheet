"""Base screamsheet class that all screamsheets inherit from."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, List, Optional
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    BaseDocTemplate, PageTemplate, Frame,
    NextPageTemplate, PageBreak,
)
from reportlab.platypus.flowables import KeepInFrame
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

from .section import Section

logger = logging.getLogger(__name__)


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
        canvas.drawCentredString(page_width / 2, 20, text)
        canvas.restoreState()

    def _build_two_page_pdf(
        self,
        front_content: List,
        back_content: List,
    ) -> str:
        """Build a two-page-max PDF using BaseDocTemplate + KeepInFrame shrink.

        Front content is constrained to page 1 via KeepInFrame(mode='shrink').
        Back content (if any) flows onto page 2 with the branding footer.

        Args:
            front_content: ReportLab flowables for page 1.
            back_content:  ReportLab flowables for page 2 (may be empty).

        Returns:
            Path to the written PDF file.
        """
        margin = 36
        page_width, page_height = letter
        frame_w = page_width - 2 * margin
        frame_h = page_height - 2 * margin

        front_frame = Frame(margin, margin, frame_w, frame_h, id="front_frame")
        back_frame = Frame(margin, margin, frame_w, frame_h, id="back_frame")

        doc = BaseDocTemplate(
            self.output_filename,
            pagesize=letter,
            leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=margin,
        )
        doc.addPageTemplates([
            PageTemplate(id="Front", frames=[front_frame], onPage=self._draw_branding_footer),
            PageTemplate(id="Back", frames=[back_frame], onPage=self._draw_branding_footer),
        ])

        story: List = [
            KeepInFrame(maxWidth=0, maxHeight=frame_h, content=front_content, mode="shrink")
        ]

        if back_content:
            story.append(NextPageTemplate("Back"))
            story.append(PageBreak())
            story.append(
                KeepInFrame(maxWidth=0, maxHeight=frame_h, content=back_content, mode="shrink")
            )

        doc.build(story)
        logger.info("PDF written to %s", self.output_filename)
        return self.output_filename

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
        Generate the complete screamsheet PDF, distributing sections between
        front and back pages.
        
        Returns:
            Path to the generated PDF file
        """
        # Build all sections
        logger.info("Building sections for %s", self.get_title())
        self.sections = self.build_sections()
        logger.info("Sections built: %d total", len(self.sections))
        
        front_content: List = []
        back_content: List = []

        # Add title, subtitle, date to front page header
        front_content.append(Paragraph(self.get_title(), self.title_style))
        subtitle = self.get_subtitle()
        if subtitle:
            front_content.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        front_content.append(Paragraph(self.get_date_string(), self.subtitle_style))
        front_content.append(Spacer(1, 12))

        # Render and distribute sections
        for section in self.sections:
            if section.has_content():
                elements = section.render()
                if getattr(section, "page_slot", "front") == "back":
                    back_content.extend(elements)
                    back_content.append(Spacer(1, 20))
                    logger.info("Section '%s' → back page (%d flowables)", section.title, len(elements))
                else:
                    front_content.extend(elements)
                    front_content.append(Spacer(1, 20))
                    logger.info("Section '%s' → front page (%d flowables)", section.title, len(elements))

        return self._build_two_page_pdf(front_content, back_content)

    
    def add_section(self, section: Section):
        """Add a section to the screamsheet."""
        self.sections.append(section)

"""Base class for all news screamsheets."""
import logging
from abc import abstractmethod
from typing import List, Optional
from datetime import datetime

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.pagesizes import letter

from ..base import BaseScreamsheet, Section

logger = logging.getLogger(__name__)


class NewsScreamsheet(BaseScreamsheet):
    """
    Base class for all news screamsheets.
    
    News screamsheets have a common structure:
    1. Weather report (optional)
    2. News articles (number varies)
    
    Subclasses provide news-source-specific sections and configuration.
    """
    
    def __init__(
        self,
        news_source: str,
        output_filename: str,
        include_weather: bool = True,
        date: Optional[datetime] = None
    ):
        """
        Initialize the news screamsheet.
        
        Args:
            news_source: Name of the news source (e.g., "MLB Trade Rumors")
            output_filename: Path to save the PDF
            include_weather: Whether to include a weather report
            date: Target date (defaults to today)
        """
        super().__init__(output_filename, date)
        self.news_source = news_source
        self.include_weather = include_weather
    
    def get_title(self) -> str:
        """Get the main title for this screamsheet."""
        # Extract league name from news source (e.g., "MLB Trade Rumors" -> "MLB")
        # For generic sources, use the first word or full source name
        words = self.news_source.split()
        league = words[0] if words else self.news_source
        return f"{league} Screamsheet"
    
    def get_subtitle(self) -> Optional[str]:
        """Get the news source as subtitle."""
        return self.news_source
    
    @abstractmethod
    def build_sections(self) -> List[Section]:
        """
        Build all sections for the news screamsheet.
        
        Subclasses should implement this to add weather and article sections.
        """
        pass

    def generate(self) -> str:
        """Generate a two-page-max PDF for this news screamsheet.

        Front page: header + weather (if any) + first ``NewsArticlesSection``.
        Back page:  sections with ``page_slot='back'`` + branding footer.
        """
        logger.info("Building sections for %s", self.get_title())
        self.sections = self.build_sections()
        logger.info("Sections built: %d total", len(self.sections))

        front_content: List = []
        back_content: List = []

        # Header
        front_content.append(Paragraph(self.get_title(), self.title_style))
        subtitle = self.get_subtitle()
        if subtitle:
            front_content.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        front_content.append(Paragraph(self.get_date_string(), self.subtitle_style))
        front_content.append(Spacer(1, 12))

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

"""Base class for all news screamsheets."""
from abc import abstractmethod
from typing import List, Optional
from datetime import datetime

from ..base import BaseScreamsheet, Section


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
        """Get the title for this screamsheet."""
        date_str = self.date.strftime("%B %d, %Y")
        return f"{self.news_source} - {date_str}"
    
    @abstractmethod
    def build_sections(self) -> List[Section]:
        """
        Build all sections for the news screamsheet.
        
        Subclasses should implement this to add weather and article sections.
        """
        pass

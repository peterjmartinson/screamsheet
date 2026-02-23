"""Section class representing a single section of a screamsheet."""
from abc import ABC, abstractmethod
from typing import List, Any


class Section(ABC):
    """
    Base class for a screamsheet section.
    
    Each section represents a distinct part of the screamsheet
    (e.g., game scores, standings, box score, etc.).
    """
    
    def __init__(self, title: str):
        """
        Initialize the section.
        
        Args:
            title: The title/heading for this section
        """
        self.title = title
        self.data = None
    
    @abstractmethod
    def fetch_data(self):
        """
        Fetch the data needed for this section.
        
        This method should retrieve data from APIs, databases, files, etc.
        and store it in self.data for rendering.
        """
        pass
    
    @abstractmethod
    def render(self) -> List[Any]:
        """
        Render the section into ReportLab flowables.
        
        Returns:
            List of ReportLab flowable objects (Paragraph, Table, Spacer, etc.)
        """
        pass
    
    def has_content(self) -> bool:
        """
        Check if this section has content to render.
        
        Returns:
            True if the section has data to display, False otherwise
        """
        if self.data is None:
            self.fetch_data()
        return self.data is not None and len(self.data) > 0 if isinstance(self.data, (list, dict)) else self.data is not None

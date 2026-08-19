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
        self.page_slot: str = "front"  # 'front' or 'back'
    
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
    
    def render_markdown(self) -> str:
        """Render the section into a clean, sequential Markdown string.

        Subclasses override this to format specific domain models (tables, summaries, articles).
        The base implementation provides a robust fallback serializer for self.data.

        Returns:
            Formatted Markdown string.
        """
        if self.data is None:
            self.fetch_data()

        if self.data is None:
            return ""

        # String data (e.g. LLM summaries)
        if isinstance(self.data, str):
            return self.data.strip()

        # List data
        if isinstance(self.data, list):
            lines = []
            for item in self.data:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("name") or item.get("headline")
                    summary = item.get("summary") or item.get("body") or item.get("description") or item.get("text")
                    link = item.get("link") or item.get("url")
                    if title and summary:
                        entry = f"### {title}\n\n{summary}"
                        if link:
                            entry += f"\n\n[Source]({link})"
                        lines.append(entry)
                    else:
                        lines.append(str(item))
                else:
                    lines.append(f"* {item}")
            return "\n\n".join(lines)

        # Dictionary data
        if isinstance(self.data, dict):
            lines = []
            for k, v in self.data.items():
                lines.append(f"* **{k}**: {v}")
            return "\n".join(lines)

        return str(self.data)

    def has_content(self) -> bool:
        """
        Check if this section has content to render.
        
        Returns:
            True if the section has data to display, False otherwise
        """
        if self.data is None:
            self.fetch_data()
        return self.data is not None and len(self.data) > 0 if isinstance(self.data, (list, dict)) else self.data is not None

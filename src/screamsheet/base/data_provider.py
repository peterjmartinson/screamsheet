"""Data provider interface for fetching data from various sources."""
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from datetime import datetime
import re
import html


class DataProvider(ABC):
    """
    Base class for data providers.
    
    Data providers are responsible for fetching data from various sources:
    - APIs (REST, GraphQL, etc.)
    - Python packages (nba_api, etc.)
    - Web scraping
    - Local files
    - Databases
    
    Each sport/news source implements its own provider.
    """
    
    def __init__(self, **config):
        """
        Initialize the data provider.
        
        Args:
            **config: Configuration parameters for the provider
        """
        self.config = config
    
    @abstractmethod
    def get_game_scores(self, date: datetime) -> list:
        """
        Get game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        pass
    
    @abstractmethod
    def get_standings(self) -> Any:
        """
        Get current league standings.
        
        Returns:
            Standings data (format varies by provider)
        """
        pass
    
    def get_box_score(self, team_id: int, date: datetime) -> Optional[Any]:
        """
        Get box score for a specific team and date.
        
        Args:
            team_id: The team ID
            date: The date to fetch box score for
            
        Returns:
            Box score data or None if not available
        """
        return None
    
    def get_game_summary(self, team_id: int, date: datetime) -> Optional[str]:
        """
        Get game summary for a specific team and date.
        
        Args:
            team_id: The team ID
            date: The date to fetch summary for
            
        Returns:
            Game summary text or None if not available
        """
        return None

    # --- News provider helpers -------------------------------------------
    def _sanitize_text(self, text: str) -> str:
        """Clean up article text: strip HTML, decode entities, remove control chars.

        This reduces the chance of feeding invalid input (like a single brace)
        to LLMs.
        """
        if not text:
            return ''

        # If it's not a string, coerce
        try:
            text = str(text)
        except Exception:
            return ''

        # Decode HTML entities
        text = html.unescape(text)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove C0 control characters except newlines/tabs
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]+', '', text)

        # Normalize whitespace
        text = re.sub(r"\s+", ' ', text).strip()

        return text

    def _looks_like_garbage(self, text: str) -> bool:
        """Heuristic to detect garbage text that should not be sent to an LLM."""
        if not text:
            return True

        t = text.strip()

        # Too short
        if len(t) < 20:
            return True

        # Single punctuation or braces or only non-word chars
        if re.fullmatch(r"^[\W_]{1,30}$", t):
            return True

        # Looks like JSON or stray brace only
        if t in ('{', '}', '[]', '{}'):
            return True

        return False

    def sanitize_entry(self, entry: Dict) -> Optional[Dict]:
        """Sanitize a single feedparser entry dict.

        Returns a cleaned entry dict or None if the entry is considered garbage.
        """
        if not isinstance(entry, dict) and not hasattr(entry, 'get'):
            return None

        # feedparser entries may be objects with attribute access; make dict-like
        try:
            get = entry.get
        except Exception:
            # Convert object to dict of its attributes
            entry = {k: getattr(entry, k) for k in dir(entry) if not k.startswith('_')}
            get = entry.get

        title = get('title', '') or get('title_detail', '')
        summary = get('summary', '') or get('description', '') or get('content', '')

        title = self._sanitize_text(title)
        summary = self._sanitize_text(summary)

        if self._looks_like_garbage(summary) and self._looks_like_garbage(title):
            return None

        # Ensure title exists: fallback to first sentence of summary
        if not title or len(title) < 3:
            first_sentence = summary.split('. ')[0][:120].strip()
            if first_sentence:
                title = first_sentence

        # Truncate overly long summaries to protect LLM token usage
        MAX_SUMMARY = 4000
        if len(summary) > MAX_SUMMARY:
            summary = summary[:MAX_SUMMARY].rsplit(' ', 1)[0] + '...'

        # Build a cleaned minimal dict to avoid carrying unexpected/mutable
        # fields from the feedparser entry object. This ensures title+summary
        # remain paired and stable.
        cleaned = {
            'title': title,
            'summary': summary,
            'link': get('link', '') if callable(get) else entry.get('link', ''),
            'published_parsed': get('published_parsed', None) if callable(get) else entry.get('published_parsed', None),
            'id': get('id', get('guid', get('link', ''))) if callable(get) else entry.get('id', entry.get('guid', entry.get('link', ''))),
        }

        return cleaned

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """Sanitize a list of article dicts returned by providers.

        Expects items shaped like {'slot': ..., 'entry': <feed entry>} and
        returns the same structure but with cleaned 'entry' dicts. Garbage
        entries are filtered out.
        """
        cleaned_list: List[Dict] = []
        for item in articles or []:
            try:
                entry = item.get('entry') if isinstance(item, dict) else None
                if entry is None:
                    continue
                cleaned_entry = self.sanitize_entry(entry)
                if cleaned_entry is None:
                    continue
                cleaned_list.append({'slot': item.get('slot', 'Section'), 'entry': cleaned_entry})
            except Exception:
                continue

        return cleaned_list


"""Data provider interface for fetching data from various sources."""
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict, Tuple
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
    
    def get_game_scores(self, date: datetime) -> list:
        """
        Get game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        return []
    
    def get_standings(self) -> Any:
        """
        Get current league standings.
        
        Returns:
            Standings data (format varies by provider)
        """
        return None
    
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
    
    def get_game_summary(self, team_id: int, date: datetime, is_primary_favorite: bool = False, mad_fan: bool = False) -> Optional[str]:
        """
        Get game summary for a specific team and date.
        
        Args:
            team_id: The team ID
            date: The date to fetch summary for
            is_primary_favorite: True when this is the #1 priority team
            mad_fan: True when fan-rant mode is enabled for losses by primary favorite
            
        Returns:
            Game summary text or None if not available
        """
        return None

    def has_game(self, team_id: int, date: datetime) -> bool:
        """Return True if the team played a completed game on the given date.

        The default implementation always returns True, which preserves
        existing behaviour for providers that have not yet implemented
        box-score / game-PK lookups (e.g. NBA, NFL).  Concrete providers
        that support box scores should override this method.

        Args:
            team_id: The team ID to check.
            date: The date to check.

        Returns:
            True if a completed game exists for this team on this date.
        """
        return True

    def get_all_teams_for_date(self, date: datetime) -> List[Tuple[int, str]]:
        """Return (team_id, team_name) for all completed non-preseason games on date.

        Used as a fallback when no favourite team played: the caller picks a
        random entry from the returned list.  The base implementation returns
        an empty list, preserving behaviour for providers that have not yet
        implemented this method.

        Args:
            date: The date to query.

        Returns:
            List of (team_id, team_name) tuples, two entries per game
            (home and away team), filtered to FINAL/completed non-preseason games.
        """
        return []

    def get_day_schedule(self, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Return scheduled games and broadcast info for a calendar date.

        Args:
            date: Target date to query (defaults to today in provider's timezone).

        Returns:
            List of scheduled game dicts (empty list by default).
        """
        return []

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
        # remain paired and stable, while preserving multi-source cluster metadata.
        cleaned: Dict[str, Any] = {
            'title': title,
            'summary': summary,
            'link': get('link', '') if callable(get) else entry.get('link', ''),
            'published_parsed': get('published_parsed', None) if callable(get) else entry.get('published_parsed', None),
            'id': get('id', get('guid', get('link', ''))) if callable(get) else entry.get('id', entry.get('guid', entry.get('link', ''))),
        }

        raw_source = get('source', '') if callable(get) else entry.get('source', '')
        raw_sources = get('sources', None) if callable(get) else entry.get('sources', None)
        raw_reports = get('reports', None) if callable(get) else entry.get('reports', None)
        is_cluster = get('is_cluster', False) if callable(get) else entry.get('is_cluster', False)
        cluster_score = get('cluster_score', None) if callable(get) else entry.get('cluster_score', None)

        if isinstance(raw_sources, list):
            cleaned_sources = [self._sanitize_text(s) for s in raw_sources if self._sanitize_text(s)]
            if cleaned_sources:
                cleaned['sources'] = cleaned_sources

        source_clean = self._sanitize_text(raw_source)
        if not source_clean and cleaned.get('sources'):
            source_clean = ", ".join(cleaned['sources'])
        if source_clean:
            cleaned['source'] = source_clean

        if isinstance(raw_reports, list):
            max_report_summary = 2000
            cleaned_reports = []
            for rep in raw_reports:
                if not isinstance(rep, dict):
                    continue
                rep_title = self._sanitize_text(rep.get('title', ''))
                rep_summary = self._sanitize_text(rep.get('summary', ''))
                if len(rep_summary) > max_report_summary:
                    rep_summary = rep_summary[:max_report_summary].rsplit(' ', 1)[0] + '...'
                rep_source = self._sanitize_text(rep.get('source', ''))
                rep_link = rep.get('link', '') or ''
                if rep_title or rep_summary:
                    cleaned_reports.append({
                        'source': rep_source,
                        'title': rep_title,
                        'summary': rep_summary,
                        'link': rep_link,
                    })
            if cleaned_reports:
                cleaned['reports'] = cleaned_reports

        if is_cluster:
            cleaned['is_cluster'] = True
        if cluster_score is not None:
            cleaned['cluster_score'] = cluster_score

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


class SportsDataProvider(DataProvider):
    """Abstract base class for sports data providers (MLB, NHL, NBA, NFL, World Cup)."""

    @abstractmethod
    def get_game_scores(self, date: datetime) -> list:
        """Get game scores for a specific date."""
        pass

    @abstractmethod
    def get_standings(self) -> Any:
        """Get current league standings."""
        pass


class NewsDataProvider(DataProvider):
    """Abstract base class for news and article data providers."""

    @abstractmethod
    def get_articles(self) -> List[Dict]:
        """Fetch and return news articles for this provider."""
        pass

    def _score_and_cluster_entries(
        self,
        entries: List[Dict[str, Any]],
        sport: str,
        favorite_teams: List[str],
        junk_keywords: List[str],
        primary_source: str,
        primary_source_bonus: int = 25,
        max_articles: int = 4,
        similarity_threshold: float = 0.68,
        default_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Deduplicate by URL, score with authority & favorite-team boosts, and cluster into topics."""
        from ..news.clustering import TopicClusterer
        from ..news.scoring import SportsNewsScorer

        fallback_source = default_source or primary_source

        deduped: List[Dict[str, Any]] = []
        seen_links: set = set()
        for entry in entries:
            link = str(entry.get("link") or entry.get("id") or "").strip()
            if link:
                if link in seen_links:
                    continue
                seen_links.add(link)
            deduped.append(entry)

        if not deduped:
            return []

        scorer = SportsNewsScorer(
            sport=sport,
            favorite_teams=favorite_teams,
            junk_keywords=junk_keywords,
            primary_source=primary_source,
            primary_source_bonus=primary_source_bonus,
        )
        clusterer = TopicClusterer(
            similarity_threshold=similarity_threshold,
            scorer=scorer,
        )
        selected_clusters = clusterer.cluster(deduped, top_n=max_articles)

        output: List[Dict[str, Any]] = []
        for i, cluster in enumerate(selected_clusters):
            first_article = cluster.articles[0] if cluster.articles else {}
            pub_parsed = (
                first_article.get("published_parsed")
                if hasattr(first_article, "get")
                else getattr(first_article, "published_parsed", None)
            )
            slot_entry = {
                "title": cluster.topic,
                "summary": cluster.combined_summary,
                "link": cluster.primary_link,
                "id": cluster.primary_link,
                "source": ", ".join(cluster.sources) if cluster.sources else fallback_source,
                "sources": cluster.sources if cluster.sources else ([fallback_source] if fallback_source else []),
                "reports": [
                    {
                        "source": (a.get("source") if hasattr(a, "get") else getattr(a, "source", "")) or fallback_source,
                        "title": (a.get("title") if hasattr(a, "get") else getattr(a, "title", "")) or "",
                        "summary": (a.get("summary") if hasattr(a, "get") else getattr(a, "summary", "")) or "",
                        "link": (a.get("link") if hasattr(a, "get") else getattr(a, "link", "")) or "",
                    }
                    for a in cluster.articles
                ],
                "is_cluster": True,
                "cluster_score": cluster.score,
                "published_parsed": pub_parsed,
            }
            output.append({"slot": f"Section {i + 1}", "entry": slot_entry})

        return output




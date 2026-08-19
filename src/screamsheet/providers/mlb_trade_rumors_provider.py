"""MLB Trade Rumors data provider for fetching news articles."""
import re
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import feedparser

from ..base import DataProvider


class MLBTradeRumorsProvider(DataProvider):
    """
    Data provider for MLB Trade Rumors news via RSS feed.
    
    Provides access to:
    - News articles from MLB Trade Rumors
    - Filtered and prioritized by favorite teams (using team names and aliases)
    """
    
    RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'
    EXCLUSION_KEYWORDS = [
        'Top 50', 'Contest', 'Prediction', 'Subscribers', 'Email List',
        'Presents Our', 'Podcast', 'Live Chat', 'Q&A', 'Ask Us Anything',
        'Best of', 'MLBTR Chat', 'Front Office'
    ]
    
    def __init__(self, favorite_teams: Optional[List[str]] = None, max_articles: int = 4, **config):
        super().__init__(**config)
        self.favorite_teams = favorite_teams if favorite_teams is not None else []
        self.max_articles = max_articles
    
    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []
    
    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None
    
    def _get_team_match_patterns(self, team_name: str) -> List[str]:
        """Return a list of matching keywords/aliases for a team name."""
        keywords: Set[str] = {team_name.strip()}

        # Try screamsheet.db resolution
        try:
            from ..db import sport_get_team_aliases, sport_resolve_team

            resolved = sport_resolve_team("mlb", team_name)
            if resolved:
                aliases = sport_get_team_aliases("mlb", resolved["team_id"])
                for a in aliases:
                    keywords.add(a)
                if resolved.get("full_name"):
                    keywords.add(resolved["full_name"])
                if resolved.get("abbrev"):
                    keywords.add(resolved["abbrev"])
        except Exception:
            pass

        # Fallback heuristic: split words (e.g. "Milwaukee Brewers" -> "Brewers", "Milwaukee")
        parts = team_name.strip().split()
        if len(parts) > 1:
            keywords.add(parts[-1])  # Nickname
            keywords.add(" ".join(parts[:-1]))  # City / Region

        return [k.lower() for k in keywords if len(k) > 1]

    def _entry_matches_team(self, entry: Dict[str, Any], team_name: str) -> bool:
        """Check if an RSS entry matches a favorite team name or any of its aliases."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        patterns = self._get_team_match_patterns(team_name)

        for pat in patterns:
            # Word-boundary matching for short or hyphenated terms
            regex = r'(?:\b|\A)' + re.escape(pat) + r'(?:\b|\Z)'
            if re.search(regex, title) or re.search(regex, summary):
                return True
        return False

    def get_articles(self) -> List[Dict]:
        """
        Fetch and filter articles from MLB Trade Rumors.
        
        Returns:
            List of article dictionaries with 'slot' and 'entry' keys
        """
        feed = feedparser.parse(self.RSS_URL)
        
        # Filter out garbage articles
        clean_entries = [
            entry for entry in feed.entries
            if not self._is_garbage(entry)
        ]
        
        # Prioritize and select articles
        final_selection = [None] * self.max_articles
        selected_guids = set()
        
        # 1. Fill team slots in priority order (0-indexed)
        slot_index = 0
        for team_name in self.favorite_teams:
            if slot_index >= self.max_articles:
                break
                
            for entry in clean_entries:
                guid = entry.get('link', '') or entry.get('id', '')
                if guid not in selected_guids and self._entry_matches_team(entry, team_name):
                    final_selection[slot_index] = entry
                    selected_guids.add(guid)
                    slot_index += 1
                    break
        
        # 2. Fill remaining slots with general clean articles
        remaining_entries = [
            entry for entry in clean_entries
            if (entry.get('link', '') or entry.get('id', '')) not in selected_guids
        ]
        
        entry_index = 0
        for i in range(self.max_articles):
            if final_selection[i] is None and entry_index < len(remaining_entries):
                entry = remaining_entries[entry_index]
                final_selection[i] = entry
                guid = entry.get('link', '') or entry.get('id', '')
                selected_guids.add(guid)
                entry_index += 1
        
        # Format output
        output_list = []
        for i, entry in enumerate(final_selection):
            if entry is not None:
                output_list.append({
                    'slot': f'Section {i + 1}',
                    'entry': entry
                })
        
        return output_list
    
    def _is_garbage(self, entry: Dict) -> bool:
        """Check if an article contains blacklisted promotional keywords."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        
        for keyword in self.EXCLUSION_KEYWORDS:
            if keyword.lower() in title or keyword.lower() in summary:
                return True
        return False

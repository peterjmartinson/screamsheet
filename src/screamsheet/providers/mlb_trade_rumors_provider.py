"""MLB Trade Rumors data provider for fetching news articles."""
import feedparser
from typing import List, Dict, Optional
from datetime import datetime

from ..base import DataProvider


class MLBTradeRumorsProvider(DataProvider):
    """
    Data provider for MLB Trade Rumors news via RSS feed.
    
    Provides access to:
    - News articles from MLB Trade Rumors
    - Filtered and prioritized by favorite teams
    """
    
    RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'
    EXCLUSION_KEYWORDS = [
        'Top 50', 'Contest', 'Prediction', 'Subscribers', 'Email List',
        'Presents Our', 'Podcast', 'Live Chat', 'Q&A', 'Ask Us Anything',
        'Best of', 'MLBTR Chat', 'Front Office'
    ]
    
    def __init__(self, favorite_teams: List[str] = None, max_articles: int = 4, **config):
        super().__init__(**config)
        self.favorite_teams = favorite_teams or ['Phillies', 'Padres', 'Yankees']
        self.max_articles = max_articles
        self.team_priority = {team: i for i, team in enumerate(self.favorite_teams)}
    
    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []
    
    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None
    
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
        
        # Fill team slots (priority-based)
        for priority in sorted(self.team_priority.values()):
            if priority + 1 >= self.max_articles:
                break
                
            team_name = self.favorite_teams[priority]
            slot_index = priority + 1
            
            for entry in clean_entries:
                title = entry.get('title', '')
                guid = entry.get('link', '')
                
                if guid not in selected_guids and team_name in title:
                    final_selection[slot_index] = entry
                    selected_guids.add(guid)
                    break
        
        # Fill remaining slots with general articles
        remaining_entries = [
            entry for entry in clean_entries
            if entry.get('link', '') not in selected_guids
        ]
        
        fill_index = 0
        entry_index = 0
        
        while fill_index < self.max_articles and entry_index < len(remaining_entries):
            if final_selection[fill_index] is None:
                entry = remaining_entries[entry_index]
                final_selection[fill_index] = entry
                selected_guids.add(entry.get('link', ''))
                entry_index += 1
                fill_index += 1
            else:
                fill_index += 1
        
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

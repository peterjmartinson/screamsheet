"""FanGraphs Blogs data provider via RSS feed."""
import feedparser
from typing import List, Dict
from datetime import datetime

from ..base import DataProvider


class FanGraphsProvider(DataProvider):
    """
    Data provider for FanGraphs blogs via RSS.
    """

    RSS_URL = 'https://blogs.fangraphs.com/feed/'

    def __init__(self, max_articles: int = 4, **config):
        super().__init__(**config)
        self.max_articles = max_articles

    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []

    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None

    def get_articles(self) -> List[Dict]:
        """Fetch recent articles from FanGraphs RSS feed."""
        feed = feedparser.parse(self.RSS_URL)

        entries = feed.entries[: self.max_articles]

        output_list = []
        for i, entry in enumerate(entries):
            output_list.append({
                'slot': f'Section {i + 1}',
                'entry': entry,
            })

        return output_list

    def _is_garbage(self, entry: Dict) -> bool:
        """Placeholder for future filtering logic."""
        return False

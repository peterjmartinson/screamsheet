from typing import List, Dict
from dataclasses import dataclass
import feedparser

FAVORITE_TEAMS = ['Phillies', 'Padres', 'Yankees']
MAX_ARTICLES = 4
SLOTS = [
    'Section 1',
    'Section 2',
    'Section 3',
    'Section 4'
]

@dataclass
class Article:
    title: str
    text: str
    summary: str
    guid: str


class NewsSource:

    _EXCLUSION_KEYWORDS = [
        'Top 50', 'Contest', 'Prediction', 'Subscribers', 'Email List',
        'Presents Our', 'Podcast', 'Live Chat', 'Q&A', 'Ask Us Anything',
        'Best of', 'MLBTR Chat', 'Front Office'
    ]

    def __init__(self, favorite_teams: List[str] = FAVORITE_TEAMS):
        self._FAVORITE_TEAMS = favorite_teams
        self._TEAM_PRIORITY = {team: i for i, team in enumerate(favorite_teams)}

    def is_garbage(self, entry: Dict) -> bool:
        """Checks if an article entry contains blacklisted promotional keywords."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        
        # Combine check on both title and summary for any exclusion keywords
        for keyword in self._EXCLUSION_KEYWORDS:
            if keyword.lower() in title or keyword.lower() in summary:
                return True
        return False

    def build_one_article(self, entry) -> Article:
        raise NotImplementedError("Subclass must implement abstract method '_build_llm_prompt'")

    def fetch_articles(self) -> List[Article]:
        raise NotImplementedError("Subclass must implement abstract method 'fetch_articles'")

class SourceRSS(NewsSource):

    def __init__(self, rss_url: str) -> None:
        self.rss_url = rss_url

    def build_one_article(self, entry) -> Article:
        title = entry.get('title', '')
        guid = entry.get('link', '')
        text = entry.get('summary', entry.get('description', title))
        summary = ""
        article = Article(title, text, summary, guid)
        return article

    def fetch_articles(self) -> List[Article]:
        feed = feedparser.parse(self.rss_url)
        self._entries = [entry for entry in feed.entries if not self.is_garbage(entry)]
        articles: List[Article] = []
        for entry in self._entries:
            article = self.build_one_article(entry)
            articles.append(article)
        return articles




class SourceHTML:
    pass

class MLBTradeRumors(NewsSource):

    RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'

    def fetch_and_filter_articles(self) -> List[Dict]:
        """
        Fetches, filters (removes garbage), and prioritizes up to 4 articles.
        """
        feed = feedparser.parse(self.RSS_URL)
        
        # 1. Filter out garbage before starting the selection process
        clean_entries = [entry for entry in feed.entries if not self.is_garbage(entry)]
        
        # --- The rest of the logic remains the same, but operates on clean_entries ---
        final_selection = [None] * MAX_ARTICLES
        selected_guids = set()
        
        # 2. Fill Team Slots (Priority 1, 2, 3)
        for priority in sorted(TEAM_PRIORITY.values()):
            team_name = FAVORITE_TEAMS[priority]
            slot_index = priority + 1
            
            for entry in clean_entries:
                title = entry.get('title', '')
                guid = entry.get('link', '')

                if guid not in selected_guids and team_name in title:
                    final_selection[slot_index] = entry
                    selected_guids.add(guid)
                    break

        # 3. Fill League/General Slot (Index 0) and any Remaining Empty Slots
        remaining_entries = [entry for entry in clean_entries if entry.get('link', '') not in selected_guids]
        
        fill_index = 0
        entry_index = 0
        
        while fill_index < MAX_ARTICLES and entry_index < len(remaining_entries):
            if final_selection[fill_index] is None:
                entry = remaining_entries[entry_index]
                final_selection[fill_index] = entry
                selected_guids.add(entry.get('link', ''))
                entry_index += 1
                fill_index += 1
            else:
                fill_index += 1

        # 4. Format Output for Summarization
        output_list: list = []
        for i, entry in enumerate(final_selection):
            if entry is not None:
                output_list.append({'slot': SLOTS[i], 'entry': entry})
                
        return output_list



if __name__ == "__main__":

    x = generate_news_sections()

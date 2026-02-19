"""The Players' Tribune data provider for fetching news articles."""
import feedparser
from typing import List, Dict, Optional
from datetime import datetime

from ..base import DataProvider


class PlayersTribuneProvider(DataProvider):
    """
    Data provider for The Players' Tribune via RSS feed.
    
    Provides access to first-person stories and features from professional athletes.
    """
    
    RSS_URL = 'https://www.theplayerstribune.com/posts.rss'
    
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
        """
        Fetch articles from The Players' Tribune.
        
        Returns:
            List of article dictionaries with 'slot' and 'entry' keys
        """
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        feed = feedparser.parse(self.RSS_URL)
        
        # Get the most recent articles (no filtering needed for this feed)
        entries = feed.entries[:self.max_articles]
        
        # Format output and generate better titles using LLM
        output_list = []
        for i, entry in enumerate(entries):
            # Many Players' Tribune titles are bad ("0.00", "Hi Daddy    ", etc.)
            # Generate a better title from the description using LLM
            original_title = entry.get('title', '').strip()
            description = entry.get('description', entry.get('summary', ''))
            
            # Check if title looks bad (numeric, very short, or mostly whitespace)
            title_looks_bad = (
                len(original_title) < 3 or
                original_title.replace('.', '').replace(' ', '').isdigit() or
                len(original_title.strip()) < len(original_title) / 2  # Mostly whitespace
            )
            
            if title_looks_bad and description:
                # Generate title using LLM
                try:
                    import sys
                    from pathlib import Path
                    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
                    from src.get_llm_summary import NewsSummarizer
                    
                    # Initialize summarizer
                    summarizer = NewsSummarizer(
                        gemini_api_key=os.getenv('GEMINI_API_KEY'),
                        grok_api_key=os.getenv('GROK_API_KEY')
                    )
                    
                    # Generate a title from the description
                    if summarizer.llm_gemini or summarizer.llm_grok:
                        prompt = f"Generate a short, compelling title (max 8 words) for this article: {description[:200]}"
                        title = summarizer._run_llm_query(prompt, 'gemini' if summarizer.llm_gemini else 'grok')
                        # Clean up the title (remove quotes if present)
                        title = title.strip('"\' ').strip()
                        entry['title'] = title
                        print(f"[INFO] Generated title for article {i+1}: {title}")
                    else:
                        # No LLM available, use first sentence of description
                        title = description.split('.')[0][:60] + '...'
                        entry['title'] = title
                except Exception as e:
                    print(f"[WARNING] Could not generate title for article {i+1}: {e}")
                    # Fall back to first sentence of description
                    title = description.split('.')[0][:60] + '...'
                    entry['title'] = title
            
            output_list.append({
                'slot': f'Section {i + 1}',
                'entry': entry
            })
        
        return output_list
    
    def _is_garbage(self, entry: Dict) -> bool:
        """
        Check if an article should be filtered out.
        
        The Players' Tribune has high-quality content, so minimal filtering needed.
        """
        # Could add filtering here if needed in the future
        return False

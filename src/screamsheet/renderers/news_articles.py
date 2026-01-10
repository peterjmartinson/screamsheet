"""News articles section renderer."""
from typing import List, Any
import os
from dotenv import load_dotenv
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section
from ..providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider

# Load environment variables
load_dotenv()


class NewsArticlesSection(Section):
    """
    Section for displaying news articles.
    
    Shows summarized news articles from a news provider.
    """
    
    def __init__(self, title: str, provider: MLBTradeRumorsProvider, max_articles: int = 4, start_index: int = 0):
        super().__init__(title)
        self.provider = provider
        self.max_articles = max_articles
        self.start_index = start_index
        self.styles = getSampleStyleSheet()
        
        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        self.article_heading_style = ParagraphStyle(
            name="ArticleHeading",
            parent=self.styles['h4'],
            fontName='Helvetica-Bold',
            fontSize=12,
            spaceAfter=6,
        )
        
        self.article_text_style = ParagraphStyle(
            name="ArticleText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
        )
    
    def fetch_data(self):
        """Fetch articles from the provider."""
        articles = self.provider.get_articles()
        
        # Generate summaries using LLM
        try:
            # Import from the correct path (relative to workspace root)
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from src.get_llm_summary import NewsSummarizer
            
            # Initialize with API keys from environment
            summarizer = NewsSummarizer(
                gemini_api_key=os.getenv('GEMINI_API_KEY'),
                grok_api_key=os.getenv('GROK_API_KEY')
            )
            self.data = self._generate_summaries(articles, summarizer)
        except Exception as e:
            print(f"Error generating article summaries: {e}")
            import traceback
            traceback.print_exc()
            self.data = articles  # Use original articles without summaries
    
    def _generate_summaries(self, articles: List[dict], summarizer) -> List[dict]:
        """Generate LLM summaries for articles."""
        summarized_articles = []
        
        # Check if summarizer has any available LLMs
        has_llm = (summarizer.llm_gemini is not None or summarizer.llm_grok is not None)
        
        for article in articles:
            entry = article['entry']
            title = entry.get('title', 'Untitled')
            link = entry.get('link', '')
            summary_text = entry.get('summary', '')
            
            if has_llm:
                try:
                    # Generate summary using LLM
                    # Format data as dict with title and summary (as expected by NewsSummarizer)
                    story_data = {
                        'title': title,
                        'summary': summary_text
                    }
                    llm_summary = summarizer.generate_summary(
                        llm_choice='grok',  # Use grok as in the original implementation
                        data=story_data
                    )
                    
                    summarized_articles.append({
                        'slot': article['slot'],
                        'title': title,
                        'summary': llm_summary,
                        'link': link
                    })
                except Exception as e:
                    print(f"Error summarizing article '{title}': {e}")
                    import traceback
                    traceback.print_exc()
                    summarized_articles.append({
                        'slot': article['slot'],
                        'title': title,
                        'summary': summary_text[:500] + '...',  # Truncated original
                        'link': link
                    })
            else:
                # No LLM available, use original summary
                print(f"No LLM available for article '{title}', using original summary")
                summarized_articles.append({
                    'slot': article['slot'],
                    'title': title,
                    'summary': summary_text[:500] + '...',  # Truncated original
                    'link': link
                })
        
        return summarized_articles
    
    def render(self) -> List[Any]:
        """Render the news articles section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Add section title
        elements.append(Paragraph(self.title, self.subtitle_style))
        elements.append(Spacer(1, 12))
        
        # Slice articles for this section
        articles_to_render = self.data[self.start_index:self.start_index + self.max_articles]
        
        # Create two-column layout for articles
        left_column = []
        right_column = []
        
        for i, article in enumerate(articles_to_render):
            # Split summary into paragraphs on double newlines
            summary_paragraphs = [p for p in article['summary'].split('\n\n') if p.strip()]
            
            article_elements = [
                Paragraph(f"<b>{article['title']}</b>", self.article_heading_style),
            ]
            
            # Add each paragraph as a separate Paragraph element
            for paragraph in summary_paragraphs:
                article_elements.append(Paragraph(paragraph, self.article_text_style))
                article_elements.append(Spacer(1, 6))  # Smaller spacer between paragraphs
            
            article_elements.append(Spacer(1, 12))  # Larger spacer between articles
            
            if i % 2 == 0:
                left_column.extend(article_elements)
            else:
                right_column.extend(article_elements)
        
        # Create table for two-column layout
        news_table = Table(
            [[left_column, right_column]],
            colWidths=[270, 270]
        )
        
        news_style = TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 10),
        ])
        news_table.setStyle(news_style)
        
        elements.append(news_table)
        
        return elements

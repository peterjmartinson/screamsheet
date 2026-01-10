"""News articles section renderer."""
from typing import List, Any
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section
from ..providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider


class NewsArticlesSection(Section):
    """
    Section for displaying news articles.
    
    Shows summarized news articles from a news provider.
    """
    
    def __init__(self, title: str, provider: MLBTradeRumorsProvider, max_articles: int = 4):
        super().__init__(title)
        self.provider = provider
        self.max_articles = max_articles
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
            from src.get_llm_summary import NewsSummarizer
            summarizer = NewsSummarizer()
            self.data = self._generate_summaries(articles, summarizer)
        except Exception as e:
            print(f"Error generating article summaries: {e}")
            self.data = articles  # Use original articles without summaries
    
    def _generate_summaries(self, articles: List[dict], summarizer) -> List[dict]:
        """Generate LLM summaries for articles."""
        summarized_articles = []
        
        for article in articles:
            entry = article['entry']
            title = entry.get('title', 'Untitled')
            link = entry.get('link', '')
            summary_text = entry.get('summary', '')
            
            try:
                # Generate summary using LLM
                # Format data as string combining title and summary
                article_data = f"Title: {title}\n\nSummary: {summary_text}\n\nLink: {link}"
                llm_summary = summarizer.generate_summary(
                    llm_choice='gemini',
                    data=article_data
                )
                
                summarized_articles.append({
                    'slot': article['slot'],
                    'title': title,
                    'summary': llm_summary,
                    'link': link
                })
            except Exception as e:
                print(f"Error summarizing article '{title}': {e}")
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
        
        # Create two-column layout for articles
        left_column = []
        right_column = []
        
        for i, article in enumerate(self.data):
            article_elements = [
                Paragraph(f"<b>{article['title']}</b>", self.article_heading_style),
                Paragraph(article['summary'], self.article_text_style),
                Spacer(1, 12)
            ]
            
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

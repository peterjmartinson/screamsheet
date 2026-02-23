"""Renderer for Grok-generated articles.

Articles arrive pre-written from GrokMLBNewsProvider, so this renderer
skips the LLM summarization pass entirely and goes straight to layout.
The two-column Table layout mirrors NewsArticlesSection exactly.
"""
from typing import List, Any

from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

from ..base import Section


class GrokGeneratedArticlesSection(Section):
    """
    Renders pre-written Grok articles in the standard two-column news layout.

    No LLM summarization is performed — the provider has already composed the
    final copy.

    Args:
        title:        Section heading label.
        provider:     A GrokMLBNewsProvider instance.
        max_articles: Number of articles to display (default 2).
        start_index:  Offset into the provider's article list (default 0).
    """

    def __init__(
        self,
        title: str,
        provider,
        max_articles: int = 2,
        start_index: int = 0,
    ):
        super().__init__(title)
        self.provider = provider
        self.max_articles = max_articles
        self.start_index = start_index

        base = getSampleStyleSheet()
        self.article_heading_style = ParagraphStyle(
            'GrokHeading', parent=base['h4'],
            fontName='Helvetica-Bold', fontSize=12, spaceAfter=6,
        )
        self.article_date_style = ParagraphStyle(
            'GrokDate', parent=base['Normal'],
            fontName='Helvetica-Oblique', fontSize=9,
            textColor='#666666', spaceAfter=6,
        )
        self.article_text_style = ParagraphStyle(
            'GrokText', parent=base['Normal'],
            fontName='Helvetica', fontSize=10,
        )

    # ------------------------------------------------------------------
    # Section protocol
    # ------------------------------------------------------------------

    def fetch_data(self):
        """Retrieve articles from the provider (no summarization)."""
        try:
            all_articles = self.provider.get_articles()
            self.data = all_articles[self.start_index: self.start_index + self.max_articles]
        except Exception as e:
            print(f'GrokGeneratedArticlesSection: Error fetching articles: {e}')
            self.data = []

    def render(self) -> List[Any]:
        """Render articles into the standard two-column Table layout."""
        if not self.data:
            self.fetch_data()
        if not self.data:
            return []

        left_column: List[Any] = []
        right_column: List[Any] = []

        for i, article in enumerate(self.data):
            entry = article.get('entry', {})
            title = entry.get('title', 'Untitled')
            body = entry.get('summary', '')
            pub_date = entry.get('pub_date')

            article_elements: List[Any] = [
                Paragraph(f'<b>{title}</b>', self.article_heading_style),
            ]

            if pub_date:
                article_elements.append(
                    Paragraph(pub_date, self.article_date_style)
                )

            # Split body into paragraphs on blank lines
            paragraphs = [p for p in body.split('\n\n') if p.strip()]
            for para in paragraphs:
                article_elements.append(
                    Paragraph(para.replace('\n', ' '), self.article_text_style)
                )
                article_elements.append(Spacer(1, 6))

            article_elements.append(Spacer(1, 12))

            if i % 2 == 0:
                left_column.extend(article_elements)
            else:
                right_column.extend(article_elements)

        news_table = Table(
            [[left_column, right_column]],
            colWidths=[270, 270],
        )
        news_table.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (0,  0),  0),
            ('RIGHTPADDING',  (1, 0), (1,  0),  0),
            ('RIGHTPADDING',  (0, 0), (0,  0),  10),
        ]))

        return [news_table]

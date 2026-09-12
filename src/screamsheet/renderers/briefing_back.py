"""Two-column back page section renderer for Morning Briefing screamsheet."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

from ..base import Section
from .email_news import EmailNewsSection
from .important_emails import ImportantEmailsSection

logger = logging.getLogger(__name__)


class TwoColumnBriefingBackSection(Section):
    """
    Renders a two-column back page for Morning Briefing:
    - Left column: News summaries (EmailNewsSection)
    - Right column: Important emails (ImportantEmailsSection)
    - Overflow behavior: If news summaries run long (> max_left_news),
      remaining news summaries continue at the top of the right column
      over the important emails.
    - If there are no important emails and news runs long, news is balanced
      across both columns.
    - If there are no news summaries, important emails are placed on the left.
    """

    def __init__(
        self,
        news_section: Optional[EmailNewsSection] = None,
        important_section: Optional[ImportantEmailsSection] = None,
        title: str = "Morning News & Important Notices",
        max_left_news: int = 5,
    ) -> None:
        super().__init__(title)
        self.page_slot = "back"
        self.news_section = news_section
        self.important_section = important_section
        self.max_left_news = max_left_news

    def fetch_data(self) -> None:
        if self.news_section:
            self.news_section.fetch_data()
        if self.important_section:
            self.important_section.fetch_data()

    def has_content(self) -> bool:
        has_news = bool(self.news_section and self.news_section.has_content())
        has_important = bool(self.important_section and self.important_section.has_content())
        return has_news or has_important

    def render(self) -> List[Any]:
        if self.news_section:
            self.news_section.fetch_data()
        if self.important_section:
            self.important_section.fetch_data()

        news_items = self.news_section.items if self.news_section else []
        important_items = self.important_section.items if self.important_section else []

        if not news_items and not important_items:
            return []

        left_flowables: List[Any] = []
        right_flowables: List[Any] = []

        if news_items and important_items:
            # Left column: news banner + up to max_left_news items
            left_flowables.extend(self.news_section.build_banner_flowables())
            left_news = news_items[: self.max_left_news]
            overflow_news = news_items[self.max_left_news :]

            for i, item in enumerate(left_news):
                left_flowables.extend(
                    self.news_section.build_item_flowables(
                        item, is_last=(i == len(left_news) - 1 and not overflow_news)
                    )
                )

            # Right column: overflow news items (if any) continue OVER the emails
            if overflow_news:
                right_flowables.extend(
                    self.news_section.build_banner_flowables(
                        title_override="MORNING NEWS BRIEFING (CONT.)",
                        subtitle_override=f"{len(overflow_news)} additional source{'s' if len(overflow_news) != 1 else ''}",
                    )
                )
                for i, item in enumerate(overflow_news):
                    right_flowables.extend(
                        self.news_section.build_item_flowables(
                            item, is_last=(i == len(overflow_news) - 1)
                        )
                    )
                right_flowables.append(Spacer(1, 14))

            # Important emails in right column
            right_flowables.extend(self.important_section.build_banner_flowables())
            for i, item in enumerate(important_items):
                right_flowables.extend(
                    self.important_section.build_item_flowables(
                        item, is_last=(i == len(important_items) - 1)
                    )
                )

        elif news_items and not important_items:
            # News only: if more than max_left_news, balance across both columns
            if len(news_items) > self.max_left_news:
                split_idx = (len(news_items) + 1) // 2
                left_news = news_items[:split_idx]
                right_news = news_items[split_idx:]

                left_flowables.extend(self.news_section.build_banner_flowables())
                for i, item in enumerate(left_news):
                    left_flowables.extend(
                        self.news_section.build_item_flowables(item, is_last=(i == len(left_news) - 1))
                    )

                right_flowables.extend(
                    self.news_section.build_banner_flowables(
                        title_override="MORNING NEWS BRIEFING (CONT.)",
                        subtitle_override=f"{len(right_news)} additional source{'s' if len(right_news) != 1 else ''}",
                    )
                )
                for i, item in enumerate(right_news):
                    right_flowables.extend(
                        self.news_section.build_item_flowables(item, is_last=(i == len(right_news) - 1))
                    )
            else:
                left_flowables.extend(self.news_section.build_banner_flowables())
                for i, item in enumerate(news_items):
                    left_flowables.extend(
                        self.news_section.build_item_flowables(item, is_last=(i == len(news_items) - 1))
                    )

        elif important_items and not news_items:
            # Important emails only: place in left column
            left_flowables.extend(self.important_section.build_banner_flowables())
            for i, item in enumerate(important_items):
                left_flowables.extend(
                    self.important_section.build_item_flowables(item, is_last=(i == len(important_items) - 1))
                )

        # 2-column table layout: page width 612 pt, margins 36 pt on each side -> 540 pt usable width
        # Left col: 260 pt, Gap: 20 pt, Right col: 260 pt
        col_table = Table([[left_flowables, "", right_flowables]], colWidths=[260, 20, 260])
        col_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [col_table]

    def render_markdown(self) -> str:
        parts: List[str] = []
        if self.news_section and self.news_section.has_content():
            parts.append(self.news_section.render_markdown().strip())
        if self.important_section and self.important_section.has_content():
            parts.append(self.important_section.render_markdown().strip())
        return "\n\n---\n\n".join(p for p in parts if p)

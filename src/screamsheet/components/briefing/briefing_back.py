"""Two-column back page composite component for Morning Briefing screamsheet."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from reportlab.platypus import Spacer, Table, TableStyle

from ...providers.gmail_provider import GmailNewsProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry
from .email_news import EmailNewsComponent
from .important_emails import ImportantEmailsComponent

logger = logging.getLogger(__name__)


@ComponentRegistry.register("briefing_back")
class BriefingBackComponent(ScreamsheetComponent):
    """Renders a two-column back page for Morning Briefing (EmailNews + ImportantEmails)."""

    component_type = "briefing_back"
    layout_spec = ComponentLayoutSpec(
        weight=1.0,
        full_page_only=True,
        component_family="briefing_back",
        max_on_front_page=1,
        max_per_page=1,
        renders_own_header=True,
    )

    def __init__(
        self,
        news_section: Optional[EmailNewsComponent] = None,
        important_section: Optional[ImportantEmailsComponent] = None,
        title: str = "Morning News & Important Notices",
        max_left_news: int = 5,
        include_email_news: Optional[bool] = None,
        gmail_label: str = "Morning Briefing",
        important_senders: Optional[List[str]] = None,
        latest_per_sender: bool = True,
        date: Optional[datetime] = None,
        email_provider: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, date=date, page_slot="back", **kwargs)
        self.max_left_news = max_left_news

        if news_section is None and (
            include_email_news is True
            or (include_email_news is None and important_senders is not None)
        ):
            ep = email_provider or GmailNewsProvider(label=gmail_label)
            news_section = EmailNewsComponent(
                provider=ep,
                date=self.date,
                gmail_label=gmail_label,
                latest_per_sender=latest_per_sender,
            )

        if important_section is None and important_senders:
            ep = email_provider or GmailNewsProvider(label=gmail_label)
            important_section = ImportantEmailsComponent(
                important_senders=important_senders,
                provider=ep,
                date=self.date,
                gmail_label=gmail_label,
                latest_per_sender=latest_per_sender,
            )

        self.news_section = news_section
        self.important_section = important_section

    def fetch_data(self) -> None:
        if self.news_section:
            self.news_section.fetch_data()
        if self.important_section:
            self.important_section.fetch_data()

    def has_content(self) -> bool:
        has_news = bool(self.news_section and self.news_section.has_content())
        has_important = bool(self.important_section and self.important_section.has_content())
        return has_news or has_important

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
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
            left_flowables.extend(self.news_section.build_banner_flowables())
            left_news = news_items[: self.max_left_news]
            overflow_news = news_items[self.max_left_news :]

            for i, item in enumerate(left_news):
                left_flowables.extend(
                    self.news_section.build_item_flowables(
                        item, is_last=(i == len(left_news) - 1 and not overflow_news)
                    )
                )

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

            right_flowables.extend(self.important_section.build_banner_flowables())
            for i, item in enumerate(important_items):
                right_flowables.extend(
                    self.important_section.build_item_flowables(
                        item, is_last=(i == len(important_items) - 1)
                    )
                )

        elif news_items and not important_items:
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
            left_flowables.extend(self.important_section.build_banner_flowables())
            for i, item in enumerate(important_items):
                left_flowables.extend(
                    self.important_section.build_item_flowables(item, is_last=(i == len(important_items) - 1))
                )

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

"""Important emails section renderer for the Morning Briefing screamsheet (Page 2)."""
from __future__ import annotations

import html
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph

from ..base import Section
from ..llm.summary import EmailImportantSummarizer
from ..providers.gmail_provider import GmailNewsProvider

logger = logging.getLogger(__name__)


class ImportantEmailsSection(Section):
    """
    Renders action-oriented summaries of priority personal/school emails on page 2.
    """

    def __init__(
        self,
        important_senders: Optional[List[str]] = None,
        provider: Optional[GmailNewsProvider] = None,
        date: Optional[datetime] = None,
        title: str = "Important Notices & Updates",
        max_emails: int = 5,
        lookback_hours: int = 24,
        summarizer_class=None,
        senders: Optional[List[str]] = None,
    ) -> None:
        super().__init__(title)
        self.page_slot = "back"
        self.important_senders = important_senders or senders or []
        self.provider = provider or GmailNewsProvider()
        self.date = date or datetime.now()
        self.max_emails = max_emails
        self.lookback_hours = lookback_hours
        self._summarizer_class = summarizer_class or EmailImportantSummarizer
        self.items: List[Dict[str, Any]] = []
        self._setup_styles()

    def _setup_styles(self) -> None:
        base = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "ImportantTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=17,
            spaceBefore=0,
            spaceAfter=3,
            textColor=colors.HexColor("#8b0000"),  # subtle deep red to stand out as priority
        )
        self._subtitle_style = ParagraphStyle(
            "ImportantSubtitle",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=11.5,
            textColor=colors.HexColor("#555555"),
            spaceAfter=5,
        )
        self._item_header_style = ParagraphStyle(
            "ImportantItemHeader",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13.5,
            textColor=colors.HexColor("#111111"),
            spaceBefore=3,
            spaceAfter=1.5,
        )
        self._item_meta_style = ParagraphStyle(
            "ImportantItemMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#666666"),
            spaceAfter=2.5,
        )
        self._item_body_style = ParagraphStyle(
            "ImportantItemBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=4,
        )

    def fetch_data(self) -> None:
        if self.items or not self.important_senders:
            return

        emails = self.provider.fetch_important_emails(
            important_senders=self.important_senders,
            since=self.date,
            lookback_hours=self.lookback_hours,
        )

        if not emails:
            self.items = []
            return

        emails = emails[: self.max_emails]

        try:
            summarizer = self._summarizer_class(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                grok_api_key=os.getenv("GROK_API_KEY"),
            )
        except Exception as e:
            logger.warning("Failed to initialize EmailImportantSummarizer: %s", e)
            summarizer = None

        processed: List[Dict[str, Any]] = []
        for em in emails:
            sender = em.get("sender", "Priority Contact")
            subject = em.get("subject", "(No Subject)")
            body = em.get("body", "")
            em_date = em.get("date")

            summary_text = ""
            if summarizer and body:
                try:
                    summary_text = summarizer.generate_summary(
                        llm_choice="gemini",
                        data={
                            "sender": sender,
                            "subject": subject,
                            "body": body,
                            "date": self.date.strftime("%Y-%m-%d"),
                        },
                    )
                except Exception as e:
                    logger.warning("LLM summarization failed for important email %r: %s", subject, e)
                    summary_text = body[:280] + "..." if len(body) > 280 else body
            else:
                summary_text = body[:280] + "..." if len(body) > 280 else body

            summary_text = summary_text.strip().strip('"').strip("'")
            processed.append(
                {
                    "sender": sender,
                    "subject": subject,
                    "date": em_date,
                    "summary": summary_text,
                }
            )

        self.items = processed
        logger.info("ImportantEmailsSection prepared %d summary items", len(self.items))

    def has_content(self) -> bool:
        if not self.items:
            self.fetch_data()
        return len(self.items) > 0

    def render(self) -> List[Any]:
        if not self.items:
            self.fetch_data()

        if not self.items:
            return []

        flowables: List[Any] = []

        flowables.append(Paragraph(f"<b>{html.escape(self.title.upper())}</b>", self._title_style))
        flowables.append(
            Paragraph(
                f"Priority updates received in past 24 hours &bull; {len(self.items)} notice{'s' if len(self.items) != 1 else ''}",
                self._subtitle_style,
            )
        )
        flowables.append(
            HRFlowable(
                width="100%",
                thickness=1.0,
                color=colors.HexColor("#8b0000"),
                spaceAfter=5,
            )
        )

        for i, item in enumerate(self.items):
            sender_safe = html.escape(item.get("sender", "Contact"))
            subj_safe = html.escape(item.get("subject", ""))
            summary_safe = html.escape(item.get("summary", ""))

            dt = item.get("date")
            if isinstance(dt, datetime):
                meta_line = f"Received {dt.strftime('%b %d, %Y at %I:%M %p').replace(' 0', ' ')}"
            else:
                meta_line = ""

            header_text = f"<b>{sender_safe}</b> &mdash; {subj_safe}"
            flowables.append(Paragraph(header_text, self._item_header_style))

            if meta_line:
                flowables.append(Paragraph(meta_line, self._item_meta_style))

            flowables.append(Paragraph(summary_safe, self._item_body_style))

            if i < len(self.items) - 1:
                flowables.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.4,
                        color=colors.HexColor("#e0e0e0"),
                        spaceBefore=2.5,
                        spaceAfter=3.5,
                    )
                )

        return flowables

    def render_markdown(self) -> str:
        if not self.items:
            self.fetch_data()

        if not self.items:
            return ""

        lines = [f"## {self.title.upper()}\n"]
        for item in self.items:
            sender = item.get("sender", "Contact")
            subj = item.get("subject", "")
            summary = item.get("summary", "")
            dt = item.get("date")
            meta_str = f" *({dt.strftime('%b %d, %Y %I:%M %p')})*" if isinstance(dt, datetime) else ""

            lines.append(f"### {sender} — {subj}{meta_str}\n")
            lines.append(f"{summary}\n")
            lines.append("---\n")

        return "\n".join(lines)

"""Email news digest section renderer for the Morning Briefing screamsheet (Page 2)."""
from __future__ import annotations

import html
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, Spacer

from ..base import Section
from ..llm.summary import EmailNewsSummarizer
from ..providers.gmail_provider import GmailNewsProvider

logger = logging.getLogger(__name__)


class EmailNewsSection(Section):
    """
    Renders summarized email news flashes on the back page of the Morning Briefing screamsheet.
    """

    def __init__(
        self,
        provider: Optional[GmailNewsProvider] = None,
        date: Optional[datetime] = None,
        title: str = "Morning News Briefing",
        max_emails: int = 8,
        lookback_hours: int = 24,
        summarizer_class=None,
    ) -> None:
        super().__init__(title)
        self.page_slot = "back"
        self.provider = provider or GmailNewsProvider()
        self.date = date or datetime.now()
        self.max_emails = max_emails
        self.lookback_hours = lookback_hours
        self._summarizer_class = summarizer_class or EmailNewsSummarizer
        self.items: List[Dict[str, Any]] = []
        self._setup_styles()

    def _setup_styles(self) -> None:
        base = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "EmailNewsTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            spaceBefore=0,
            spaceAfter=4,
            textColor=colors.HexColor("#111111"),
        )
        self._subtitle_style = ParagraphStyle(
            "EmailNewsSubtitle",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#555555"),
            spaceAfter=6,
        )
        self._item_header_style = ParagraphStyle(
            "EmailNewsItemHeader",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13.5,
            textColor=colors.HexColor("#1a1a1a"),
            spaceBefore=4,
            spaceAfter=2,
        )
        self._item_meta_style = ParagraphStyle(
            "EmailNewsItemMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#666666"),
            spaceAfter=3,
        )
        self._item_body_style = ParagraphStyle(
            "EmailNewsItemBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#222222"),
            spaceAfter=4,
        )

    def fetch_data(self) -> None:
        """Fetch emails from provider and summarize them with LLM."""
        if self.items:
            return

        emails = self.provider.fetch_emails(since=self.date, lookback_hours=self.lookback_hours)
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
            logger.warning("Failed to initialize EmailNewsSummarizer: %s. Using raw bodies.", e)
            summarizer = None

        processed_items: List[Dict[str, Any]] = []
        for em in emails:
            sender = em.get("sender", "News Source")
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
                    logger.warning("LLM summarization failed for email %r: %s", subject, e)
                    summary_text = body[:280] + "..." if len(body) > 280 else body
            else:
                summary_text = body[:280] + "..." if len(body) > 280 else body

            # Clean any surrounding quotes or markdown artifacts
            summary_text = summary_text.strip().strip('"').strip("'")

            processed_items.append(
                {
                    "sender": sender,
                    "subject": subject,
                    "date": em_date,
                    "summary": summary_text,
                }
            )

        self.items = processed_items
        logger.info("EmailNewsSection prepared %d summary items", len(self.items))

    def has_content(self) -> bool:
        """Only render if there are email summaries to show."""
        if not self.items:
            self.fetch_data()
        return len(self.items) > 0

    def build_banner_flowables(
        self,
        title_override: Optional[str] = None,
        subtitle_override: Optional[str] = None,
    ) -> List[Any]:
        t_text = title_override or self.title.upper()
        flowables: List[Any] = [Paragraph(f"<b>{html.escape(t_text)}</b>", self._title_style)]
        if subtitle_override is not None:
            sub = subtitle_override
        else:
            sub = f"Past 24 hours &bull; {len(self.items)} source{'s' if len(self.items) != 1 else ''} summarized"
        if sub:
            flowables.append(Paragraph(sub, self._subtitle_style))
        flowables.append(
            HRFlowable(
                width="100%",
                thickness=1.0,
                color=colors.HexColor("#222222"),
                spaceAfter=5,
            )
        )
        return flowables

    def build_item_flowables(self, item: Dict[str, Any], is_last: bool = False) -> List[Any]:
        flowables: List[Any] = []
        sender_safe = html.escape(item.get("sender", "News Source"))
        subj_safe = html.escape(item.get("subject", ""))
        summary_safe = html.escape(item.get("summary", ""))

        dt = item.get("date")
        if isinstance(dt, datetime):
            time_str = dt.strftime("%I:%M %p").lstrip("0")
            date_str = dt.strftime("%b %d, %Y")
            meta_line = f"{date_str} at {time_str}"
        else:
            meta_line = ""

        header_text = f"<b>{sender_safe}</b> &mdash; {subj_safe}"
        flowables.append(Paragraph(header_text, self._item_header_style))

        if meta_line:
            flowables.append(Paragraph(f"Received {meta_line}", self._item_meta_style))

        flowables.append(Paragraph(summary_safe, self._item_body_style))

        if not is_last:
            flowables.append(
                HRFlowable(
                    width="100%",
                    thickness=0.4,
                    color=colors.HexColor("#dddddd"),
                    spaceBefore=2.5,
                    spaceAfter=3.5,
                )
            )
        return flowables

    def render(self) -> List[Any]:
        if not self.items:
            self.fetch_data()

        if not self.items:
            return []

        flowables: List[Any] = []
        flowables.extend(self.build_banner_flowables())
        for i, item in enumerate(self.items):
            flowables.extend(self.build_item_flowables(item, is_last=(i == len(self.items) - 1)))
        return flowables

    def render_markdown(self) -> str:
        if not self.items:
            self.fetch_data()

        if not self.items:
            return ""

        lines = [f"## {self.title.upper()}\n"]
        for item in self.items:
            sender = item.get("sender", "News Source")
            subj = item.get("subject", "")
            summary = item.get("summary", "")
            dt = item.get("date")
            meta_str = f" *({dt.strftime('%b %d, %Y %I:%M %p')})*" if isinstance(dt, datetime) else ""

            lines.append(f"### {sender} — {subj}{meta_str}\n")
            lines.append(f"{summary}\n")
            lines.append("---\n")

        return "\n".join(lines)

"""ReportLab section renderer for the Presidential Screamsheet."""
import logging
import os
from typing import Any, List, Optional

from dotenv import load_dotenv
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..providers.political_news_provider import (
    PoliticalRSSProvider,
    WhiteHouseProvider,
)
from .processor import PoliticalNewsProcessor

try:
    from ..llm.summarizers import NewsSummarizer
except Exception:  # pragma: no cover
    NewsSummarizer = None  # type: ignore[assignment,misc]

load_dotenv()
logger = logging.getLogger(__name__)


class PresidentialSection(Section):
    """
    ReportLab section that runs the full presidential news pipeline:
    fetch → process → (optional LLM summarize) → render.

    When *pre_fetched_entries* is supplied (a list already returned by
    :meth:`PresidentialScreamsheet._fetch_and_process`) the pipeline step is
    skipped and the section renders only the slice
    ``pre_fetched_entries[start_index : start_index + max_articles]``.
    This mirrors the ``start_index`` pattern used by
    :class:`~screamsheet.renderers.news_articles.NewsArticlesSection` so
    two sections can share one network round-trip.
    """

    def __init__(
        self,
        title: str = "Top Stories",
        max_articles: int = 2,
        start_index: int = 0,
        pre_fetched_entries: Optional[List[dict]] = None,
    ):
        super().__init__(title)
        self.max_articles = max_articles
        self.start_index = start_index
        self._pre_fetched = pre_fetched_entries

        styles = getSampleStyleSheet()

        self.headline_style = ParagraphStyle(
            name="PresidentialHeadline",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceAfter=4,
        )
        self.byline_style = ParagraphStyle(
            name="PresidentialByline",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor="#666666",
            spaceAfter=6,
        )
        self.body_style = ParagraphStyle(
            name="PresidentialBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
        )

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def fetch_data(self):
        """Run the full pipeline and populate ``self.data``.

        If *pre_fetched_entries* was provided at construction time, the
        network/processing pipeline is skipped and the section uses only
        the relevant slice of that list.
        """
        if self._pre_fetched is not None:
            slice_ = self._pre_fetched[self.start_index : self.start_index + self.max_articles]
            self.data = self._summarize(slice_)
            logger.info(
                "PresidentialSection '%s': %d stories from pre-fetched list",
                self.title, len(self.data),
            )
            return

        # --- Full pipeline: fetch + process + (optional) LLM ---
        try:
            rss = PoliticalRSSProvider().get_articles()
        except Exception as exc:
            logger.error("PresidentialSection: RSS fetch failed: %s", exc)
            rss = []

        try:
            wh = WhiteHouseProvider().get_articles()
        except Exception as exc:
            logger.error("PresidentialSection: White House fetch failed: %s", exc)
            wh = []

        processor = PoliticalNewsProcessor()
        candidates = processor.process(rss + wh)
        top = candidates[self.start_index : self.start_index + self.max_articles]

        # --- Step 3: optional LLM summarization ---
        self.data = self._summarize(top)
        logger.info(
            "PresidentialSection: %d stories ready for render", len(self.data)
        )

    def render(self) -> List[Any]:
        """Render the section into ReportLab flowables."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        _TABLE_STYLE = TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (0,  0),  0),
            ("RIGHTPADDING", (0, 0), (0,  0),  10),
            ("RIGHTPADDING", (1, 0), (1,  0),  0),
        ])

        elements: List[Any] = []
        # One table per pair of stories — each table can flow to a new page
        # independently, preventing ReportLab LayoutError on tall content.
        for i in range(0, len(self.data), 2):
            left_col  = self._render_article(self.data[i])
            right_col = self._render_article(self.data[i + 1]) if i + 1 < len(self.data) else []
            table = Table([[left_col, right_col]], colWidths=[270, 270])
            table.setStyle(_TABLE_STYLE)
            elements.append(table)
            elements.append(Spacer(1, 12))
        return elements

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_article(self, article: dict) -> List[Any]:
        """Return ReportLab flowables for a single story."""
        elements: List[Any] = [
            Paragraph(f"<b>{article['title']}</b>", self.headline_style),
        ]

        # Source + date byline
        byline_parts = []
        if article.get("source"):
            byline_parts.append(article["source"])
        if article.get("pub_date"):
            byline_parts.append(article["pub_date"])
        if byline_parts:
            elements.append(Paragraph(" — ".join(byline_parts), self.byline_style))

        # Body: split on double newlines so LLM paragraphs render cleanly.
        # Cap at 800 chars so a single very long LLM response can't overflow a page.
        raw_summary = (article.get("summary") or "")[:800]
        for para in raw_summary.split("\n\n"):
            para = para.strip()
            if para:
                elements.append(Paragraph(para, self.body_style))
                elements.append(Spacer(1, 4))

        elements.append(Spacer(1, 12))
        return elements

    def _summarize(self, entries: list) -> list:
        """
        Optionally run each entry through :class:`NewsSummarizer`.

        Falls back to a truncated original summary if no API key is
        configured or if the LLM call fails.
        """
        gemini_key = os.getenv("GEMINI_API_KEY")
        grok_key   = os.getenv("GROK_API_KEY")

        summarizer = None
        if (gemini_key or grok_key) and NewsSummarizer is not None:
            try:
                summarizer = NewsSummarizer(
                    gemini_api_key=gemini_key,
                    grok_api_key=grok_key,
                )
            except Exception as exc:
                logger.warning("PresidentialSection: LLM init failed: %s", exc)

        result = []
        for entry in entries:
            pub_date: Optional[str] = None
            try:
                if entry.get("published"):
                    pub_date = entry["published"].strftime("%B %d, %Y")
            except Exception:
                pass

            summary_text = self._llm_summary(entry, summarizer)

            result.append({
                "title":    entry.get("title", ""),
                "summary":  summary_text,
                "source":   entry.get("source", ""),
                "pub_date": pub_date,
                "link":     entry.get("link", ""),
            })
        return result

    def _llm_summary(self, entry: dict, summarizer) -> str:
        """Return an LLM summary or fall back to the truncated original."""
        original = (entry.get("summary") or "").strip()
        fallback = (original[:500] + "...") if len(original) > 500 else original

        if summarizer is None:
            return fallback

        llm_choice = "grok" if summarizer.llm_grok else "gemini"
        try:
            return summarizer.generate_summary(
                llm_choice=llm_choice,
                data={"title": entry.get("title", ""), "summary": original},
            )
        except Exception as exc:
            logger.warning(
                "PresidentialSection: LLM summary failed for '%s': %s",
                entry.get("title", ""), exc,
            )
            return fallback

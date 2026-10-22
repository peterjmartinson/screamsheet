"""Base NewsStoryComponent with screamsheet-level deduplication and 2-column page overflow."""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent

load_dotenv()

logger = logging.getLogger(__name__)


def _extract_story_keys(article_or_entry: Dict[str, Any]) -> Set[str]:
    """Extract canonical deduplication keys (URL, ID, normalized title) for an article."""
    entry = article_or_entry.get("entry", article_or_entry)
    keys: Set[str] = set()
    for field in ("id", "link"):
        val = str(entry.get(field) or article_or_entry.get(field) or "").strip()
        if val:
            keys.add(f"url:{val.lower()}")
    title = str(entry.get("title") or article_or_entry.get("title") or "").strip()
    if title:
        norm_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        if norm_title:
            keys.add(f"title:{norm_title}")
    return keys


class _NewsPageUnitComponent(ScreamsheetComponent):
    """Internal page-packing unit representing up to 2 articles (left half + right half) on a single page."""

    def __init__(
        self,
        parent: "NewsStoryComponent",
        articles_chunk: List[Dict[str, Any]],
        schedule_items: Optional[List[str]] = None,
        schedule_title: str = "Today's Broadcasts",
        title: str = "",
    ) -> None:
        weight = 0.65 if len(articles_chunk) >= 2 else 0.45
        spec = ComponentLayoutSpec(
            weight=weight,
            component_family="news",
            max_on_front_page=1,
            max_per_page=1,
            renders_own_header=False,
            preferred_top_divider=True,
        )
        super().__init__(title=title, provider=parent.provider, date=parent.date, layout_spec=spec)
        self.parent = parent
        self.data = list(articles_chunk)
        self.schedule_items = list(schedule_items) if schedule_items else []
        self.schedule_title = schedule_title

    def fetch_data(self) -> None:
        pass

    def has_content(self) -> bool:
        return bool(self.data or self.schedule_items)

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        return self.parent._render_articles_two_column(
            self.data,
            schedule_items=self.schedule_items,
            schedule_title=self.schedule_title,
        )

    def render_markdown(self) -> str:
        return self.parent._render_articles_markdown(
            self.data,
            schedule_items=self.schedule_items,
            schedule_title=self.schedule_title,
        )


class NewsStoryComponent(ScreamsheetComponent):
    """Base component for displaying summarized news articles.

    Features:
      - Default ``max_articles = 4``.
      - Screamsheet-level deduplication via ``seen_story_keys`` so no story is
        ever repeated across components or pages within the same screamsheet.
      - Sequential 2-column page overflow via :meth:`expand_page_units`:
        Article 1 -> Left column (Page N), Article 2 -> Right column (Page N),
        Article 3 -> Left column (Page N+1), Article 4 -> Right column (Page N+1), etc.
    """

    layout_spec = ComponentLayoutSpec(
        weight=0.65,
        component_family="news",
        max_on_front_page=1,
        max_per_page=1,
        renders_own_header=False,
        preferred_top_divider=True,
    )

    def __init__(
        self,
        title: str = "Top Stories",
        provider: Optional[DataProvider] = None,
        max_articles: int = 4,
        start_index: int = 0,
        summarizer_class: Any = None,
        schedule_items: Optional[List[str]] = None,
        schedule_title: str = "Today's Broadcasts",
        seen_story_keys: Optional[Set[str]] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        self.max_articles = max_articles if max_articles is not None else 4
        self.start_index = start_index
        self._summarizer_class = summarizer_class
        self.schedule_items = schedule_items or []
        self.schedule_title = schedule_title
        self.seen_story_keys: Optional[Set[str]] = seen_story_keys
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            max_articles=self.max_articles,
            start_index=start_index,
            **kwargs,
        )
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

        self.article_heading_style = ParagraphStyle(
            name="ArticleHeading",
            parent=self.styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceAfter=6,
        )

        self.article_text_style = ParagraphStyle(
            name="ArticleText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
        )

    def bind_screamsheet_context(self, seen_story_keys: Set[str]) -> None:
        """Bind screamsheet-wide story deduplication state to this component."""
        self.seen_story_keys = seen_story_keys

    def _filter_and_Select_articles(self, articles: List[dict], limit: int) -> List[dict]:
        """Select up to ``limit`` articles starting at ``start_index``, skipping seen stories."""
        if self.seen_story_keys is None:
            return articles[self.start_index : self.start_index + limit]

        selected: List[dict] = []
        skipped_for_start = 0
        for article in articles:
            keys = _extract_story_keys(article)
            if keys and (keys & self.seen_story_keys):
                continue
            if skipped_for_start < self.start_index:
                skipped_for_start += 1
                continue
            selected.append(article)
            self.seen_story_keys.update(keys)
            if len(selected) >= limit:
                break
        return selected

    def fetch_data(self) -> None:
        """Fetch articles from the provider, deduplicate, and generate LLM summaries."""
        if self.provider is None:
            self.data = []
            return
        articles = self.provider.get_articles()

        try:
            articles = self.provider.sanitize_articles(articles)
        except Exception as e:
            logger.warning("Error during article sanitization: %s", e)

        limit = min(self.max_articles, 3) if self.schedule_items else self.max_articles
        articles_slice = self._filter_and_Select_articles(articles, limit)

        try:
            from ...llm.summary import NewsSummarizer

            summarizer_cls = self._summarizer_class or NewsSummarizer
            summarizer = summarizer_cls(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                grok_api_key=os.getenv("GROK_API_KEY"),
            )

            summarized_slice = self._generate_summaries(articles_slice, summarizer)
            self.data = summarized_slice
            logger.info("Section '%s' fetched %d articles", self.title, len(self.data))
        except Exception as e:
            logger.error("Error generating article summaries: %s", e)
            try:
                fallback = []
                for article in articles_slice:
                    entry = article.get("entry", {})
                    title = entry.get("title", "Untitled")
                    summary_text = entry.get("summary", "") or entry.get("description", "") or ""
                    link = entry.get("link", "")

                    pub_date_str = None
                    try:
                        if entry.get("published_parsed"):
                            pub_date = datetime.fromtimestamp(time.mktime(entry["published_parsed"]))
                            pub_date_str = pub_date.strftime("%B %d, %Y")
                    except Exception:
                        pub_date_str = None

                    fallback.append(
                        {
                            "slot": article.get("slot", "Section"),
                            "id": entry.get("id", link),
                            "title": title,
                            "summary": (summary_text[:500] + "...") if summary_text else "",
                            "link": link,
                            "source": entry.get("source"),
                            "pub_date": pub_date_str,
                        }
                    )

                self.data = fallback
            except Exception:
                self.data = []

    def _generate_summaries(self, articles: List[dict], summarizer: Any) -> List[dict]:
        """Generate LLM summaries for articles."""
        summarized_articles = []
        has_llm = summarizer.llm_gemini is not None or summarizer.llm_grok is not None

        for article in articles:
            entry = article["entry"]
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            summary_text = entry.get("summary", "")

            pub_date_str = None
            try:
                if entry.get("published_parsed"):
                    pub_date = datetime.fromtimestamp(time.mktime(entry["published_parsed"]))
                    pub_date_str = pub_date.strftime("%B %d, %Y")
            except Exception as e:
                logger.debug("Error parsing date for '%s': %s", title, e)

            if has_llm:
                try:
                    story_data = {
                        "id": entry.get("id", entry.get("link", "")),
                        "title": title,
                        "summary": summary_text,
                        "link": link,
                        "source": entry.get("source", ""),
                    }
                    if entry.get("sources"):
                        story_data["sources"] = entry["sources"]
                    if entry.get("reports"):
                        story_data["reports"] = entry["reports"]

                    _llm_choice = "gemini" if summarizer.llm_gemini is not None else "grok"
                    llm_summary = summarizer.generate_summary(
                        llm_choice=_llm_choice,
                        data=story_data,
                    )
                    word_count = len(str(llm_summary).split())
                    logger.info("Article '%s' summarized: %d words", title[:60], word_count)

                    summarized_articles.append(
                        {
                            "slot": article["slot"],
                            "id": story_data.get("id"),
                            "title": title,
                            "summary": llm_summary,
                            "link": link,
                            "source": entry.get("source"),
                            "pub_date": pub_date_str,
                        }
                    )
                except Exception as e:
                    logger.warning("Error summarizing article '%s': %s", title[:60], e)
                    summarized_articles.append(
                        {
                            "slot": article["slot"],
                            "id": entry.get("id", link),
                            "title": title,
                            "summary": summary_text[:500] + "...",
                            "link": link,
                            "source": entry.get("source"),
                            "pub_date": pub_date_str,
                        }
                    )
            else:
                logger.warning("No LLM available for article '%s', using original summary", title[:60])
                summarized_articles.append(
                    {
                        "slot": article["slot"],
                        "id": entry.get("id", entry.get("link", "")),
                        "title": title,
                        "summary": summary_text[:500] + "...",
                        "link": link,
                        "source": entry.get("source"),
                        "pub_date": pub_date_str,
                    }
                )

        return summarized_articles

    def expand_page_units(self) -> List[ScreamsheetComponent]:
        """Split articles into 2-article (left half + right half) page units for overflow across pages."""
        if self.data is None:
            self.fetch_data()
        articles = self.data or []
        if not articles and not self.schedule_items:
            return []

        if len(articles) <= 2:
            return [
                _NewsPageUnitComponent(
                    parent=self,
                    articles_chunk=articles,
                    schedule_items=self.schedule_items,
                    schedule_title=self.schedule_title,
                    title=self.title,
                )
            ]

        units: List[ScreamsheetComponent] = []
        for idx in range(0, len(articles), 2):
            chunk = articles[idx : idx + 2]
            is_last_chunk = idx + 2 >= len(articles)
            chunk_title = self.title if idx == 0 else (f"{self.title} (Cont.)" if self.title else "")
            units.append(
                _NewsPageUnitComponent(
                    parent=self,
                    articles_chunk=chunk,
                    schedule_items=self.schedule_items if is_last_chunk else None,
                    schedule_title=self.schedule_title,
                    title=chunk_title,
                )
            )
        return units

    def _render_articles_two_column(
        self,
        articles_to_render: List[Dict[str, Any]],
        schedule_items: Optional[List[str]] = None,
        schedule_title: str = "Today's Broadcasts",
    ) -> List[Any]:
        """Render a slice of articles in a 2-column (left half -> right half) layout."""
        if not articles_to_render and not schedule_items:
            return []

        elements = []
        left_column = []
        right_column = []

        for i, article in enumerate(articles_to_render):
            summary_paragraphs = [p for p in article["summary"].split("\n\n") if p.strip()]

            article_elements = [
                Paragraph(f"<b>{article['title']}</b>", self.article_heading_style),
            ]

            byline_parts = []
            if article.get("source"):
                byline_parts.append(article["source"])
            if article.get("pub_date"):
                byline_parts.append(article["pub_date"])
            if byline_parts:
                date_style = ParagraphStyle(
                    name="ArticleDate",
                    parent=self.styles["Normal"],
                    fontName="Helvetica-Oblique",
                    fontSize=9,
                    textColor="#666666",
                    spaceAfter=6,
                )
                article_elements.append(Paragraph(" — ".join(byline_parts), date_style))

            for paragraph in summary_paragraphs:
                article_elements.append(Paragraph(paragraph, self.article_text_style))
                article_elements.append(Spacer(1, 6))

            article_elements.append(Spacer(1, 12))

            if i % 2 == 0:
                left_column.extend(article_elements)
            else:
                right_column.extend(article_elements)

        if schedule_items:
            schedule_elements = [
                Paragraph(f"<b>{schedule_title}</b>", self.article_heading_style),
            ]
            item_font_size = 8.5 if len(schedule_items) > 6 else 9.5
            item_leading = 11 if len(schedule_items) > 6 else 13
            item_style = ParagraphStyle(
                name="ScheduleItemText",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=item_font_size,
                leading=item_leading,
                spaceAfter=2,
            )
            for item in schedule_items:
                schedule_elements.append(Paragraph(item, item_style))

            if len(left_column) > len(right_column):
                right_column.extend(schedule_elements)
            else:
                left_column.extend(schedule_elements)

        news_table = Table(
            [[left_column, right_column]],
            colWidths=[270, 270],
        )

        news_style = TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ]
        )
        news_table.setStyle(news_style)
        elements.append(news_table)
        return elements

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        """Render the news articles component."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        return self._render_articles_two_column(
            self.data,
            schedule_items=self.schedule_items,
            schedule_title=self.schedule_title,
        )

    def _render_articles_markdown(
        self,
        articles_to_render: List[Dict[str, Any]],
        schedule_items: Optional[List[str]] = None,
        schedule_title: str = "Today's Broadcasts",
    ) -> str:
        if not articles_to_render and not schedule_items:
            return ""

        lines = []
        for article in articles_to_render:
            title = article.get("title", "Untitled")
            summary = article.get("summary", "").strip()
            link = article.get("link", "")
            source = article.get("source")
            pub_date = article.get("pub_date")

            byline = []
            if source:
                byline.append(source)
            if pub_date:
                byline.append(pub_date)
            byline_str = f"_{' — '.join(byline)}_\n\n" if byline else ""

            link_str = f"\n\n[Source]({link})" if link else ""
            lines.append(f"### {title}\n\n{byline_str}{summary}{link_str}")

        if schedule_items:
            sched_lines = [f"### {schedule_title}\n"]
            for item in schedule_items:
                clean_item = item.replace("<b>", "**").replace("</b>", "**")
                sched_lines.append(f"- {clean_item}")
            lines.append("\n".join(sched_lines))

        return "\n\n---\n\n".join(lines)

    def render_markdown(self) -> str:
        """Render news articles sequentially in single-column Markdown."""
        if not self.data:
            self.fetch_data()

        if not self.data and not self.schedule_items:
            return ""

        return self._render_articles_markdown(
            self.data,
            schedule_items=self.schedule_items,
            schedule_title=self.schedule_title,
        )

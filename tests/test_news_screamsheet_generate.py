"""Unit tests for NewsScreamsheet.generate() two-page constraint."""
from __future__ import annotations

import re
from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.base.section import Section
from screamsheet.news.base_news import NewsScreamsheet
from screamsheet.renderers.news_articles import NewsArticlesSection


# ---------------------------------------------------------------------------
# Minimal stub helpers
# ---------------------------------------------------------------------------

class _StubFrontSection(Section):
    """A front-page section with lots of content."""

    def fetch_data(self) -> None:
        self.data = list(range(200))

    def render(self) -> List:
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        out: List = []
        for i in range(200):
            out.append(Paragraph(f"Front content row {i}", styles["Normal"]))
            out.append(Spacer(1, 6))
        return out


class _StubBackSection(Section):
    """A back-page section (page_slot='back')."""

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.page_slot = "back"

    def fetch_data(self) -> None:
        self.data = {"content": True}

    def render(self) -> List:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        return [Paragraph("Back page content.", styles["Normal"])]


class _StubNewsSheet(NewsScreamsheet):
    """Minimal concrete NewsScreamsheet for testing."""

    def __init__(self, output_filename: str, sections: List[Section]) -> None:
        self._test_sections = sections
        super().__init__(
            news_source="Test News",
            output_filename=output_filename,
            include_weather=False,
        )

    def build_sections(self) -> List[Section]:
        return self._test_sections


def _count_pdf_pages(path: str) -> int:
    with open(path, "rb") as f:
        content = f.read()
    return len(re.findall(rb"/Type\s*/Page[^s]", content))


# ---------------------------------------------------------------------------
# NewsScreamsheet generate() — two-page layout
# ---------------------------------------------------------------------------

class TestNewsScreamshetGenerateTwoPage:
    def test_front_only_produces_single_page(self, tmp_path):
        """When there is no back-page content the PDF is exactly 1 page."""
        pdf_path = str(tmp_path / "front_only.pdf")
        sheet = _StubNewsSheet(pdf_path, [_StubFrontSection("front")])
        sheet.generate()
        assert _count_pdf_pages(pdf_path) == 1

    def test_back_section_produces_two_pages(self, tmp_path):
        """When a back-page section is present the PDF is exactly 2 pages."""
        pdf_path = str(tmp_path / "two_page.pdf")
        sheet = _StubNewsSheet(pdf_path, [
            _StubFrontSection("front"),
            _StubBackSection("back"),
        ])
        sheet.generate()
        assert _count_pdf_pages(pdf_path) == 2

    def test_overflow_front_content_stays_on_page_one(self, tmp_path):
        """Front content that overflows is shrunk to fit; PDF stays ≤ 2 pages."""
        pdf_path = str(tmp_path / "overflow.pdf")
        sheet = _StubNewsSheet(pdf_path, [
            _StubFrontSection("bulk"),
            _StubBackSection("back"),
        ])
        sheet.generate()
        assert _count_pdf_pages(pdf_path) <= 2

    def test_generate_returns_output_filename(self, tmp_path):
        """generate() returns the output filename."""
        pdf_path = str(tmp_path / "out.pdf")
        sheet = _StubNewsSheet(pdf_path, [_StubFrontSection("front")])
        result = sheet.generate()
        assert result == pdf_path


# ---------------------------------------------------------------------------
# Branding footer — news screamsheet
# ---------------------------------------------------------------------------

class TestNewsScreamshetBrandingOnBackOnly:
    def test_branding_callback_not_on_front_page_template(self):
        """The Front PageTemplate must not have an onPage branding callback."""
        from reportlab.platypus import BaseDocTemplate
        captured_templates = []

        class _CapturingDoc(BaseDocTemplate):
            def addPageTemplates(self, templates):  # type: ignore[override]
                captured_templates.extend(templates)
                super().addPageTemplates(templates)

        with patch(
            "screamsheet.base.screamsheet.BaseDocTemplate",
            _CapturingDoc,
        ):
            sheet = _StubNewsSheet(
                "/tmp/branding_test.pdf",
                [_StubFrontSection("front"), _StubBackSection("back")],
            )
            sheet.branding = "DISTRACTEDFORTUNE.COM"
            try:
                sheet.generate()
            except Exception:
                pass

        front_templates = [t for t in captured_templates if t.id == "Front"]
        assert front_templates, "Front PageTemplate not found"
        # Front template must not fire branding callback
        front_page_cb = getattr(front_templates[0], "onPage", None)
        canvas_mock = MagicMock()
        if callable(front_page_cb):
            front_page_cb(canvas_mock, MagicMock())
        canvas_mock.drawCentredString.assert_not_called()


# ---------------------------------------------------------------------------
# Second NewsArticlesSection page_slot=back — subclass builders
# ---------------------------------------------------------------------------

class TestNewsArticlesSectionPageSlot:
    def test_mlb_trade_rumors_second_section_is_back_page(self):
        """MLBTradeRumorsScreamsheet: second NewsArticlesSection has page_slot='back'."""
        from screamsheet.news.mlb_trade_rumors import MLBTradeRumorsScreamsheet
        sheet = MLBTradeRumorsScreamsheet("out.pdf", include_weather=False)
        sections = sheet.build_sections()
        news_sections = [s for s in sections if isinstance(s, NewsArticlesSection)]
        assert len(news_sections) >= 2
        assert news_sections[1].page_slot == "back"

    def test_mlb_news_second_section_is_back_page(self):
        """MLBNewsScreamsheet: second NewsArticlesSection has page_slot='back'."""
        from screamsheet.news.mlb_news import MLBNewsScreamsheet
        sheet = MLBNewsScreamsheet("out.pdf", include_weather=False)
        sections = sheet.build_sections()
        news_sections = [s for s in sections if isinstance(s, NewsArticlesSection)]
        assert len(news_sections) >= 2
        assert news_sections[1].page_slot == "back"

    def test_presidential_second_section_is_back_page(self):
        """PresidentialScreamsheet: second NewsArticlesSection has page_slot='back'."""
        from screamsheet.political.screamsheet import PresidentialScreamsheet
        sheet = PresidentialScreamsheet("out.pdf", include_weather=False)
        sections = sheet.build_sections()
        news_sections = [s for s in sections if isinstance(s, NewsArticlesSection)]
        assert len(news_sections) >= 2
        assert news_sections[1].page_slot == "back"

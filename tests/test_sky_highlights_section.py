"""Tests for SkyHighlightsSection."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from screamsheet.renderers.sky_highlights import SkyHighlightsSection


def _make_provider(highlights=None):
    provider = MagicMock()
    provider.get_sky_data.return_value = {
        "planets": [
            {"name": "Venus", "zodiac": "Taurus", "ecliptic_lon": 45.0, "two_letter": "Ve"},
        ],
        "moon_phase": "Full Moon (100% illuminated)",
        "highlights": highlights if highlights is not None else [
            "The Moon is Full Moon (100% illuminated).",
            "Venus is in Taurus.",
        ],
        "visible_constellations": ["Taurus", "Orion"],
    }
    return provider


class TestSkyHighlightsSectionInit:
    def test_title_stored(self):
        s = SkyHighlightsSection("Sky Highlights", _make_provider(), datetime(2026, 4, 18), "Bryn Mawr, PA")
        assert s.title == "Sky Highlights"

    def test_data_initially_none(self):
        s = SkyHighlightsSection("Sky Highlights", _make_provider(), datetime(2026, 4, 18), "Bryn Mawr, PA")
        assert s.data is None


class TestSkyHighlightsSectionFetchData:
    def test_fetch_data_populates_data(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        s.fetch_data()
        assert s.data is not None

    def test_fetch_data_is_list(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        s.fetch_data()
        assert isinstance(s.data, list)

    def test_fetch_data_includes_highlights(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        s.fetch_data()
        assert len(s.data) > 0


class TestSkyHighlightsSectionHasContent:
    def test_true_when_highlights_present(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        assert s.has_content() is True

    def test_false_when_no_highlights(self):
        s = SkyHighlightsSection("Highlights", _make_provider(highlights=[]), datetime(2026, 4, 18), "Test")
        assert s.has_content() is False


class TestSkyHighlightsSectionRender:
    def test_render_returns_list(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        result = s.render()
        assert isinstance(result, list)

    def test_render_returns_non_empty(self):
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        result = s.render()
        assert len(result) > 0

    def test_render_contains_paragraph(self):
        from reportlab.platypus import Paragraph
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        result = s.render()
        paragraphs = [f for f in result if isinstance(f, Paragraph)]
        assert len(paragraphs) >= 1

    def test_render_graceful_when_no_llm(self):
        """render() should not raise even when SkyNightSummarizer has no API keys."""
        s = SkyHighlightsSection("Highlights", _make_provider(), datetime(2026, 4, 18), "Test")
        # Should not raise
        result = s.render()
        assert isinstance(result, list)

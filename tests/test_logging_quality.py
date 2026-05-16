"""Unit tests for logging quality improvements across screamsheet modules."""
from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# LLM base — no print() calls for LLM selection
# ---------------------------------------------------------------------------

class TestLLMBaseLogging:
    def test_gemini_selection_does_not_print(self, capsys):
        """_select_llm_instance('gemini') must not print to stdout."""
        from screamsheet.llm.base import BaseGameSummaryGenerator
        gen = BaseGameSummaryGenerator(gemini_api_key="fake_key")
        gen._select_llm_instance("gemini")
        captured = capsys.readouterr()
        assert "GEMINI" not in captured.out.upper()

    def test_grok_selection_does_not_print(self, capsys):
        """_select_llm_instance('grok') must not print to stdout."""
        from screamsheet.llm.base import BaseGameSummaryGenerator
        gen = BaseGameSummaryGenerator(grok_api_key="fake_key")
        gen._select_llm_instance("grok")
        captured = capsys.readouterr()
        assert "GROK" not in captured.out.upper()

    def test_no_llm_does_not_print(self, capsys):
        """_select_llm_instance with no LLM must not print to stdout."""
        from screamsheet.llm.base import BaseGameSummaryGenerator
        gen = BaseGameSummaryGenerator()
        gen._select_llm_instance("gemini")
        captured = capsys.readouterr()
        assert "No LLM" not in captured.out


# ---------------------------------------------------------------------------
# SkyHoroscopeSection — logs word count after generation
# ---------------------------------------------------------------------------

class TestSkyHoroscopeLogging:
    def test_horoscope_logs_word_count(self, caplog):
        """_get_horoscope() must emit an INFO log with word count per person."""
        from screamsheet.renderers.sky_horoscope import SkyHoroscopeSection
        from screamsheet.config import PersonConfig

        provider = MagicMock()
        provider.get_sky_data.return_value = {
            "planets": [], "highlights": [], "moon_phase": "Full Moon",
        }

        person = PersonConfig(
            name="Alice", birth_date="1990-01-01",
            birth_time="12:00", birth_location="New York",
        )
        section = SkyHoroscopeSection(
            title="Horoscopes",
            provider=provider,
            date=datetime(2026, 5, 16),
            location_name="Test",
            people=[person],
        )
        section.fetch_data()

        with caplog.at_level(logging.INFO, logger="screamsheet.renderers.sky_horoscope"):
            section._get_horoscope(person)

        assert any("Alice" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# NewsArticlesSection — uses logger not print
# ---------------------------------------------------------------------------

class TestNewsArticlesLogging:
    def test_sanitization_error_uses_logger_not_print(self, capsys):
        """Error during article sanitization must not print to stdout."""
        from screamsheet.renderers.news_articles import NewsArticlesSection
        provider = MagicMock()
        provider.get_articles.return_value = []
        provider.sanitize_articles.side_effect = RuntimeError("oops")
        section = NewsArticlesSection(title="Test", provider=provider)
        section.fetch_data()
        captured = capsys.readouterr()
        assert "error during article sanitization" not in captured.out.lower()


# ---------------------------------------------------------------------------
# WeatherSection — uses logger not print
# ---------------------------------------------------------------------------

class TestWeatherSectionLogging:
    def test_fetch_error_uses_logger_not_print(self, capsys):
        """WeatherSection.fetch_data() error must not print to stdout."""
        from screamsheet.renderers.weather import WeatherSection
        section = WeatherSection(
            title="Weather", date=datetime(2026, 5, 16),
            lat=40.0, lon=-75.0, location_name="Test",
        )
        with patch.object(section.provider, "get_5_day_forecast", side_effect=RuntimeError("fail")):
            section.fetch_data()
        captured = capsys.readouterr()
        assert "Error getting weather" not in captured.out


# ---------------------------------------------------------------------------
# Branding footer Y position
# ---------------------------------------------------------------------------

class TestBrandingFooterYPosition:
    def test_footer_y_position_is_at_least_18_points(self):
        """Branding footer must be drawn at y == 20 to avoid printer clip (min 18 pts)."""
        from screamsheet.base.screamsheet import BaseScreamsheet
        from screamsheet.base.section import Section

        class _Stub(BaseScreamsheet):
            def build_sections(self):
                return []
            def get_title(self):
                return "Test"

        s = _Stub("out.pdf")
        s.branding = "DISTRACTEDFORTUNE.COM"
        canvas_mock = MagicMock()
        s._draw_branding_footer(canvas_mock, MagicMock())
        call_args = canvas_mock.drawCentredString.call_args
        y_coord = call_args[0][1]
        assert y_coord >= 20, f"Footer Y={y_coord} is too low — risk of printer clip (expected ≥ 20)"


# ---------------------------------------------------------------------------
# BaseScreamsheet.generate() — branding not on first page
# ---------------------------------------------------------------------------

class TestBaseScreamshetGenerateBrandingPage:
    def test_branding_not_on_first_page_callback(self):
        """BaseScreamsheet.generate() must not fire branding on the first page."""
        from screamsheet.base.screamsheet import BaseScreamsheet
        from screamsheet.base.section import Section
        from reportlab.platypus import SimpleDocTemplate

        class _Stub(BaseScreamsheet):
            def build_sections(self):
                return []
            def get_title(self):
                return "Test"

        captured_callbacks: dict = {}

        class _CapturingDoc(SimpleDocTemplate):
            def build(self, story, onFirstPage=None, onLaterPages=None, **kw):
                captured_callbacks["onFirstPage"] = onFirstPage
                captured_callbacks["onLaterPages"] = onLaterPages

        with patch("screamsheet.base.screamsheet.SimpleDocTemplate", _CapturingDoc):
            s = _Stub("/tmp/test_brand.pdf")
            s.branding = "DISTRACTEDFORTUNE.COM"
            s.generate()

        canvas_mock = MagicMock()
        first_page_cb = captured_callbacks.get("onFirstPage")
        if callable(first_page_cb):
            first_page_cb(canvas_mock, MagicMock())
        canvas_mock.drawCentredString.assert_not_called()

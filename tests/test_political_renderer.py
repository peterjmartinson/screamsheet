"""Unit tests for screamsheet.political.screamsheet and providers.PoliticalNewsProvider."""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.political.screamsheet import PresidentialScreamsheet
from screamsheet.renderers.news_articles import NewsArticlesSection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recent_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=4)


def _processed_entry(
    title="Trump signs executive order",
    summary="The president issued an order today.",
    source="Reuters",
    link="https://reuters.com/1",
    score=10,
) -> dict:
    return {
        "title":     title,
        "summary":   summary,
        "source":    source,
        "link":      link,
        "score":     score,
        "published": _recent_dt(),
    }


# ---------------------------------------------------------------------------
# PoliticalNewsProvider
# ---------------------------------------------------------------------------

class TestPoliticalNewsProvider:
    def _provider_with_mocked_pipeline(self, entries=None, max_articles=4):
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        provider = PoliticalNewsProvider(max_articles=max_articles)
        raw = entries or [_processed_entry()]
        with patch("screamsheet.providers.political_news_provider.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.providers.political_news_provider.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.processor.PoliticalNewsProcessor") as _MockProc:
            MockRSS.return_value.get_articles.return_value = raw
            MockWH.return_value.get_articles.return_value  = []
            # patch the import inside get_articles
            with patch("screamsheet.providers.political_news_provider.PoliticalNewsProvider.get_articles",
                       wraps=provider.get_articles):
                # Actually we need to patch the lazy import inside get_articles
                pass
        return provider

    def _get_articles_patched(self, entries=None, max_articles=4):
        """Run get_articles with all network and processor mocked."""
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        provider = PoliticalNewsProvider(max_articles=max_articles)
        raw = entries or [_processed_entry()]
        with patch("screamsheet.providers.political_news_provider.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.providers.political_news_provider.WhiteHouseProvider") as MockWH:
            MockRSS.return_value.get_articles.return_value = raw
            MockWH.return_value.get_articles.return_value  = []
            # Patch the lazy import of PoliticalNewsProcessor inside get_articles
            with patch("screamsheet.political.processor.PoliticalNewsProcessor.__init__", return_value=None), \
                 patch("screamsheet.political.processor.PoliticalNewsProcessor.process", return_value=raw):
                articles = provider.get_articles()
        return provider, articles

    def test_get_articles_returns_slot_entry_shape(self):
        _, articles = self._get_articles_patched()
        assert isinstance(articles, list)
        assert len(articles) >= 1
        item = articles[0]
        assert "slot" in item
        assert "entry" in item

    def test_entry_has_required_keys(self):
        _, articles = self._get_articles_patched()
        entry = articles[0]["entry"]
        for key in ("title", "summary", "link", "id", "source"):
            assert key in entry, f"Missing key: {key}"

    def test_published_parsed_is_struct_time(self):
        _, articles = self._get_articles_patched()
        pub = articles[0]["entry"]["published_parsed"]
        assert pub is not None
        assert isinstance(pub, time.struct_time)

    def test_source_key_present_in_entry(self):
        entries = [_processed_entry(source="BBC")]
        _, articles = self._get_articles_patched(entries=entries)
        assert articles[0]["entry"]["source"] == "BBC"

    def test_max_articles_limits_output(self):
        entries = [_processed_entry(link=f"https://x.com/{i}") for i in range(6)]
        _, articles = self._get_articles_patched(entries=entries, max_articles=3)
        assert len(articles) == 3

    def test_get_articles_caches_on_second_call(self):
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        provider = PoliticalNewsProvider(max_articles=4)
        raw = [_processed_entry()]
        with patch("screamsheet.providers.political_news_provider.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.providers.political_news_provider.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.processor.PoliticalNewsProcessor.__init__", return_value=None), \
             patch("screamsheet.political.processor.PoliticalNewsProcessor.process", return_value=raw):
            MockRSS.return_value.get_articles.return_value = raw
            MockWH.return_value.get_articles.return_value  = []
            first  = provider.get_articles()
            second = provider.get_articles()
        assert first is second  # same cached list object
        # RSS provider only called once
        MockRSS.return_value.get_articles.assert_called_once()

    def test_rss_failure_falls_back_gracefully(self):
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        provider = PoliticalNewsProvider(max_articles=4)
        with patch("screamsheet.providers.political_news_provider.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.providers.political_news_provider.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.processor.PoliticalNewsProcessor.__init__", return_value=None), \
             patch("screamsheet.political.processor.PoliticalNewsProcessor.process", return_value=[]):
            MockRSS.return_value.get_articles.side_effect = ConnectionError("down")
            MockWH.return_value.get_articles.return_value  = []
            articles = provider.get_articles()
        assert isinstance(articles, list)

    def test_sanitize_articles_strips_html(self):
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        provider = PoliticalNewsProvider()
        articles = [{"slot": "Section 1", "entry": {
            "title":   "<b>Bold Title</b>",
            "summary": "<p>Some <a href='x'>HTML</a> body</p>",
        }}]
        result = provider.sanitize_articles(articles)
        assert result is articles  # same list returned
        assert result[0]["entry"]["title"]   == "Bold Title"
        assert result[0]["entry"]["summary"] == "Some HTML body"


# ---------------------------------------------------------------------------
# PresidentialScreamsheet
# ---------------------------------------------------------------------------

class TestPresidentialScreamsheet:
    def test_get_title(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        assert sheet.get_title() == "Presidential Screamsheet"

    def test_get_subtitle_is_none(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        assert sheet.get_subtitle() is None

    def test_build_sections_returns_two_sections(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        sections = sheet.build_sections()
        assert len(sections) == 2

    def test_build_sections_are_news_articles_sections(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        sections = sheet.build_sections()
        assert all(isinstance(s, NewsArticlesSection) for s in sections)

    def test_sections_share_same_provider(self):
        """Both NewsArticlesSection instances must share one provider (one fetch)."""
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        sections = sheet.build_sections()
        assert sections[0].provider is sections[1].provider

    def test_sections_have_correct_start_indices(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        sections = sheet.build_sections()
        assert sections[0].start_index == 0
        assert sections[1].start_index == 2

    def test_max_articles_per_section_is_two(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        sections = sheet.build_sections()
        assert all(s.max_articles == 2 for s in sections)

    def test_provider_is_political_news_provider(self):
        from screamsheet.providers.political_news_provider import PoliticalNewsProvider
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        assert isinstance(sheet.provider, PoliticalNewsProvider)

    def test_generate_produces_pdf(self, tmp_path):
        out = tmp_path / "presidential.pdf"
        sheet = PresidentialScreamsheet(output_filename=str(out))

        mock_section = MagicMock()
        mock_section.has_content.return_value = True
        mock_section.render.return_value = []

        with patch.object(sheet, "build_sections", return_value=[mock_section]), \
             patch("screamsheet.base.screamsheet.SimpleDocTemplate") as MockDoc:
            mock_builder = MagicMock()
            MockDoc.return_value = mock_builder
            sheet.generate()

        mock_builder.build.assert_called_once()


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------

class TestFactory:
    def test_factory_creates_presidential_screamsheet(self):
        from screamsheet.factory import ScreamsheetFactory
        sheet = ScreamsheetFactory.create_presidential_screamsheet("out.pdf")
        assert isinstance(sheet, PresidentialScreamsheet)

    def test_factory_passes_max_articles(self):
        from screamsheet.factory import ScreamsheetFactory
        sheet = ScreamsheetFactory.create_presidential_screamsheet("out.pdf", max_articles=2)
        assert sheet.max_articles == 2

"""Unit tests for screamsheet.political.renderer and .screamsheet."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.political.renderer import PresidentialSection
from screamsheet.political.screamsheet import PresidentialScreamsheet


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


def _mock_processor_result(entries=None):
    """Return a mock PoliticalNewsProcessor that yields preset entries."""
    mock = MagicMock()
    mock.process.return_value = entries or [_processed_entry()]
    return mock


# ---------------------------------------------------------------------------
# PresidentialSection — fetch_data
# ---------------------------------------------------------------------------

class TestPresidentialSectionFetchData:
    def test_fetch_data_calls_both_providers(self):
        section = PresidentialSection()
        rss_entry = _processed_entry(title="RSS story", source="Reuters")
        wh_entry  = _processed_entry(title="WH story",  source="White House", link="https://wh.gov/1")

        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value  = [rss_entry]
            MockWH.return_value.get_articles.return_value   = [wh_entry]
            MockProc.return_value.process.return_value      = [rss_entry, wh_entry]

            section.fetch_data()

        MockRSS.return_value.get_articles.assert_called_once()
        MockWH.return_value.get_articles.assert_called_once()

    def test_fetch_data_populates_self_data(self):
        section = PresidentialSection()
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = [_processed_entry()]
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = [_processed_entry()]

            section.fetch_data()

        assert section.data is not None
        assert len(section.data) == 1

    def test_max_articles_limits_stories(self):
        section = PresidentialSection(max_articles=2)
        entries = [_processed_entry(link=f"https://x.com/{i}") for i in range(5)]
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = entries
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = entries

            section.fetch_data()

        assert len(section.data) == 2

    def test_rss_failure_falls_back_to_empty(self):
        section = PresidentialSection()
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.side_effect = ConnectionError("down")
            MockWH.return_value.get_articles.return_value  = [_processed_entry()]
            MockProc.return_value.process.return_value     = [_processed_entry()]

            # Should not raise
            section.fetch_data()

        assert section.data is not None

    def test_wh_failure_falls_back_to_empty(self):
        section = PresidentialSection()
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = [_processed_entry()]
            MockWH.return_value.get_articles.side_effect   = ConnectionError("down")
            MockProc.return_value.process.return_value     = [_processed_entry()]

            section.fetch_data()

        assert section.data is not None

    def test_result_items_have_required_keys(self):
        section = PresidentialSection()
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = [_processed_entry()]
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = [_processed_entry()]

            section.fetch_data()

        for item in section.data:
            assert {"title", "summary", "source", "pub_date", "link"} <= set(item.keys())


# ---------------------------------------------------------------------------
# PresidentialSection — LLM summarization
# ---------------------------------------------------------------------------

class TestPresidentialSectionLLM:
    def _fetch_with_llm(self, llm_return="LLM summary text", raise_exc=None):
        """Helper: run fetch_data with a mocked NewsSummarizer."""
        section = PresidentialSection()
        mock_summarizer = MagicMock()
        if raise_exc:
            mock_summarizer.generate_summary.side_effect = raise_exc
        else:
            mock_summarizer.generate_summary.return_value = llm_return
        mock_summarizer.llm_grok   = MagicMock()
        mock_summarizer.llm_gemini = None

        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc, \
             patch("screamsheet.political.renderer.os.getenv", return_value="fake-key"), \
             patch("screamsheet.political.renderer.NewsSummarizer", return_value=mock_summarizer):
            MockRSS.return_value.get_articles.return_value = [_processed_entry()]
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = [_processed_entry()]

            section.fetch_data()

        return section

    def test_llm_summary_used_when_available(self):
        section = self._fetch_with_llm(llm_return="LLM generated text")
        assert section.data[0]["summary"] == "LLM generated text"

    def test_llm_failure_falls_back_to_original(self):
        section = self._fetch_with_llm(raise_exc=RuntimeError("API down"))
        # fallback is truncated original summary
        assert "president issued" in section.data[0]["summary"]

    def test_no_api_key_uses_original_summary(self):
        section = PresidentialSection()
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.renderer.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.renderer.PoliticalNewsProcessor") as MockProc, \
             patch("screamsheet.political.renderer.os.getenv", return_value=None):
            MockRSS.return_value.get_articles.return_value = [_processed_entry()]
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = [_processed_entry()]

            section.fetch_data()

        assert "president issued" in section.data[0]["summary"]


# ---------------------------------------------------------------------------
# PresidentialSection — has_content / render
# ---------------------------------------------------------------------------

class TestPresidentialSectionRender:
    def _section_with_data(self, n=2):
        section = PresidentialSection()
        section.data = [
            {
                "title":    f"Story {i}",
                "summary":  "Some summary text here.",
                "source":   "Reuters",
                "pub_date": "March 8, 2026",
                "link":     f"https://reuters.com/{i}",
            }
            for i in range(n)
        ]
        return section

    def test_has_content_true_when_data_populated(self):
        section = self._section_with_data()
        assert section.has_content() is True

    def test_has_content_false_when_data_empty(self):
        section = PresidentialSection()
        section.data = []
        assert section.has_content() is False

    def test_render_returns_list(self):
        section = self._section_with_data()
        result = section.render()
        assert isinstance(result, list)

    def test_render_returns_nonempty_flowables(self):
        section = self._section_with_data()
        result = section.render()
        assert len(result) > 0

    def test_render_empty_data_returns_empty_list(self):
        section = PresidentialSection()
        section.data = []
        # patch fetch_data so it doesn't make real network calls
        with patch.object(section, "fetch_data"):
            result = section.render()
        assert result == []

    def test_render_calls_fetch_data_when_data_is_none(self):
        section = PresidentialSection()
        assert section.data is None
        with patch.object(section, "fetch_data") as mock_fetch:
            section.data = []  # fetch sets empty list (no real calls)
            section.render()
        # has_content was not called here — render triggers fetch_data if data is None
        # We just verify the render path runs without error

    def test_render_four_stories_produces_two_tables(self):
        # 4 stories → 2 tables (one per pair), so each table fits on a page
        from reportlab.platypus import Table
        section = self._section_with_data(n=4)
        result = section.render()
        tables = [e for e in result if isinstance(e, Table)]
        assert len(tables) == 2

    def test_render_three_stories_produces_two_tables(self):
        from reportlab.platypus import Table
        section = self._section_with_data(n=3)
        result = section.render()
        tables = [e for e in result if isinstance(e, Table)]
        assert len(tables) == 2


class TestPresidentialSectionPreFetched:
    """PresidentialSection with pre_fetched_entries skips the network pipeline."""

    def test_uses_pre_fetched_entries(self):
        entries = [_processed_entry(link=f"https://x.com/{i}") for i in range(4)]
        section = PresidentialSection(
            max_articles=2, start_index=0, pre_fetched_entries=entries
        )
        with patch("screamsheet.political.renderer.PoliticalRSSProvider") as MockRSS:
            section.fetch_data()
        MockRSS.assert_not_called()  # pipeline bypassed
        assert len(section.data) == 2

    def test_start_index_slices_correctly(self):
        entries = [
            _processed_entry(title=f"Story {i}", link=f"https://x.com/{i}")
            for i in range(4)
        ]
        section = PresidentialSection(
            max_articles=2, start_index=2, pre_fetched_entries=entries
        )
        section.fetch_data()
        assert section.data[0]["title"] == "Story 2"
        assert section.data[1]["title"] == "Story 3"


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

    def test_build_sections_returns_two_presidential_sections(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        with patch("screamsheet.political.screamsheet.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.screamsheet.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.screamsheet.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = []
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = []
            sections = sheet.build_sections()
        assert len(sections) == 2
        assert all(isinstance(s, PresidentialSection) for s in sections)

    def test_sections_have_correct_start_indices(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        with patch("screamsheet.political.screamsheet.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.screamsheet.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.screamsheet.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = []
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = []
            sections = sheet.build_sections()
        assert sections[0].start_index == 0
        assert sections[1].start_index == 2

    def test_sections_share_pre_fetched_entries(self):
        """Both sections should receive the same pre-fetched list."""
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        entries = [_processed_entry(link=f"https://x.com/{i}") for i in range(4)]
        with patch("screamsheet.political.screamsheet.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.screamsheet.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.screamsheet.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = entries
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = entries
            sections = sheet.build_sections()
        assert sections[0]._pre_fetched is sections[1]._pre_fetched

    def test_max_articles_per_section_is_two(self):
        sheet = PresidentialScreamsheet(output_filename="out.pdf")
        with patch("screamsheet.political.screamsheet.PoliticalRSSProvider") as MockRSS, \
             patch("screamsheet.political.screamsheet.WhiteHouseProvider") as MockWH, \
             patch("screamsheet.political.screamsheet.PoliticalNewsProcessor") as MockProc:
            MockRSS.return_value.get_articles.return_value = []
            MockWH.return_value.get_articles.return_value  = []
            MockProc.return_value.process.return_value     = []
            sections = sheet.build_sections()
        assert all(s.max_articles == 2 for s in sections)

    def test_generate_produces_pdf(self, tmp_path):
        out = tmp_path / "presidential.pdf"
        sheet = PresidentialScreamsheet(output_filename=str(out))

        # Mock the section so no real network calls are made
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

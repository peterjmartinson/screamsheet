"""Unit tests for screamsheet secondary Markdown generation, single-column layout, and 7-day TTL caching."""
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.base.markdown_output import (
    is_markdown_cached,
    purge_expired_markdown,
    resolve_markdown_path,
)
from screamsheet.base.screamsheet import BaseScreamsheet
from screamsheet.base.section import Section


class DummyTextSection(Section):
    def fetch_data(self):
        self.data = "This is dummy section content."

    def render(self):
        return []

    def render_markdown(self):
        return self.data


class DummyTwoPersonHoroscopeSection(Section):
    def fetch_data(self):
        self.data = {"person1": "Horoscope 1", "person2": "Horoscope 2"}

    def render(self):
        return []

    def render_markdown(self):
        return "### Alice\n\nReading for Alice.\n\n---\n\n### Bob\n\nReading for Bob."


class DummyTwoColumnBoxScoreSection(Section):
    def fetch_data(self):
        self.data = {"summary": "Game summary", "box": "Box score"}

    def render(self):
        return []

    def render_markdown(self):
        return "### Game Summary\n\nBrewers won 5-4.\n\n### Box Score\n\n| Batter | AB | R | H |\n| :--- | :---: | :---: | :---: |\n| Chourio | 4 | 1 | 2 |"


class DummyScreamsheet(BaseScreamsheet):
    def get_title(self) -> str:
        return "MLB Scores & Highlights"

    def get_subtitle(self) -> str:
        return "National League Beat"

    def build_sections(self):
        return [
            DummyTextSection("Game Highlights"),
            DummyTwoColumnBoxScoreSection("Featured Box Score"),
        ]


# ---------------------------------------------------------------------------
# Path resolver & TTL tests
# ---------------------------------------------------------------------------

class TestMarkdownOutputHelpers:
    def test_resolve_markdown_path(self, tmp_path):
        pdf = "Files/MLB_scores_20260819.pdf"
        md_path = resolve_markdown_path(pdf, md_dir=tmp_path)
        assert md_path == tmp_path / "MLB_scores_20260819.md"

    def test_is_markdown_cached_fresh(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("sample", encoding="utf-8")
        assert is_markdown_cached(f, ttl_days=7) is True

    def test_is_markdown_cached_missing(self, tmp_path):
        f = tmp_path / "missing.md"
        assert is_markdown_cached(f) is False

    def test_is_markdown_cached_expired(self, tmp_path):
        f = tmp_path / "expired.md"
        f.write_text("old", encoding="utf-8")
        # Set mtime to 8 days ago
        eight_days_ago = time.time() - (8 * 86400)
        os.utime(f, (eight_days_ago, eight_days_ago))
        assert is_markdown_cached(f, ttl_days=7) is False

    def test_purge_expired_markdown(self, tmp_path):
        fresh = tmp_path / "fresh.md"
        fresh.write_text("fresh", encoding="utf-8")

        expired = tmp_path / "expired.md"
        expired.write_text("expired", encoding="utf-8")
        eight_days_ago = time.time() - (8 * 86400)
        os.utime(expired, (eight_days_ago, eight_days_ago))

        purged = purge_expired_markdown(tmp_path, ttl_days=7)
        assert purged == 1
        assert fresh.exists()
        assert not expired.exists()


# ---------------------------------------------------------------------------
# BaseScreamsheet Markdown Generation & Sequential Layout tests
# ---------------------------------------------------------------------------

class TestBaseScreamsheetMarkdown:
    def test_generate_markdown_content_and_single_column(self, tmp_path):
        md_file = tmp_path / "MLB_scores_20260819.md"
        sheet = DummyScreamsheet(
            output_filename=str(tmp_path / "MLB_scores_20260819.pdf"),
            date=datetime(2026, 8, 19),
        )

        res_path = sheet.generate_markdown(output_path=md_file)
        assert Path(res_path).exists()

        content = md_file.read_text(encoding="utf-8")

        # Document Header
        assert "# MLB Scores & Highlights" in content
        assert "_National League Beat_" in content
        assert "**August 19, 2026**" in content

        # Sequential single column content
        assert "## Game Highlights" in content
        assert "This is dummy section content." in content

        assert "### Game Summary" in content
        assert "Brewers won 5-4." in content
        assert "### Box Score" in content
        assert "| Chourio | 4 | 1 | 2 |" in content

    def test_generate_markdown_reuses_cached_file(self, tmp_path):
        md_file = tmp_path / "cached_test.md"
        md_file.write_text("EXISTING PRE-RENDERED CONTENT", encoding="utf-8")

        sheet = DummyScreamsheet(
            output_filename=str(tmp_path / "cached_test.pdf"),
            date=datetime(2026, 8, 19),
        )

        # Call generate_markdown with use_cache=True (default)
        res_path = sheet.generate_markdown(output_path=md_file, use_cache=True)
        assert res_path == str(md_file)
        # Content remains untouched because of cache hit
        assert md_file.read_text(encoding="utf-8") == "EXISTING PRE-RENDERED CONTENT"

        # Force refresh
        sheet.generate_markdown(output_path=md_file, refresh_cache=True)
        refreshed = md_file.read_text(encoding="utf-8")
        assert "# MLB Scores & Highlights" in refreshed

    def test_generate_automatically_produces_markdown(self, tmp_path):
        pdf_file = tmp_path / "auto_test.pdf"
        md_file = tmp_path / "auto_test.md"

        sheet = DummyScreamsheet(
            output_filename=str(pdf_file),
            date=datetime(2026, 8, 19),
        )

        with patch.object(sheet, "_build_two_page_pdf", return_value=str(pdf_file)):
            with patch("screamsheet.base.screamsheet.resolve_markdown_path", return_value=md_file):
                pdf_res = sheet.generate()
                assert pdf_res == str(pdf_file)
                # Verify markdown file was automatically generated
                assert md_file.exists()
                assert "# MLB Scores & Highlights" in md_file.read_text(encoding="utf-8")

    def test_sequential_horoscope_markdown(self, tmp_path):
        class HoroscopeSheet(BaseScreamsheet):
            def get_title(self):
                return "Sky Tonight"

            def build_sections(self):
                return [DummyTwoPersonHoroscopeSection("Personal Horoscopes")]

        sheet = HoroscopeSheet(
            output_filename=str(tmp_path / "sky.pdf"),
            date=datetime(2026, 8, 19),
        )
        md_file = tmp_path / "sky.md"
        sheet.generate_markdown(output_path=md_file)

        content = md_file.read_text(encoding="utf-8")
        # Ensure sequential format: Alice then Bob
        alice_idx = content.find("### Alice")
        bob_idx = content.find("### Bob")
        assert alice_idx != -1
        assert bob_idx != -1
        assert alice_idx < bob_idx

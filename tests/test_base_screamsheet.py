"""Unit tests for screamsheet.base.screamsheet (BaseScreamsheet ABC)."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.base.screamsheet import BaseScreamsheet
from screamsheet.base.section import Section


# ---------------------------------------------------------------------------
# Minimal concrete implementations
# ---------------------------------------------------------------------------

class _StubSection(Section):
    def fetch_data(self):
        self.data = []

    def render(self):
        return []


class _ConcreteScreamsheet(BaseScreamsheet):
    def build_sections(self):
        return [_StubSection("stub")]

    def get_title(self):
        return "Test Screamsheet"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestBaseScreamseetInit:
    def test_output_filename_stored(self):
        s = _ConcreteScreamsheet("output.pdf")
        assert s.output_filename == "output.pdf"

    def test_defaults_to_yesterday(self):
        s = _ConcreteScreamsheet("output.pdf")
        yesterday = datetime.now() - timedelta(days=1)
        # Allow 5-second window for test execution time
        assert abs((s.date - yesterday).total_seconds()) < 5

    def test_explicit_date_used(self):
        d = datetime(2025, 3, 15)
        s = _ConcreteScreamsheet("output.pdf", date=d)
        assert s.date == d

    def test_sections_list_initially_empty(self):
        s = _ConcreteScreamsheet("output.pdf")
        assert s.sections == []


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------

class TestBaseScreamshetHelpers:
    def setup_method(self):
        self.s = _ConcreteScreamsheet("output.pdf", date=datetime(2025, 3, 15))

    def test_get_title(self):
        assert self.s.get_title() == "Test Screamsheet"

    def test_get_subtitle_returns_none_by_default(self):
        assert self.s.get_subtitle() is None

    def test_get_date_string(self):
        assert self.s.get_date_string() == "March 15, 2025"


# ---------------------------------------------------------------------------
# display_date
# ---------------------------------------------------------------------------

class TestBaseScreamshetDisplayDate:
    def test_display_date_defaults_to_game_date(self):
        """When no display_date is given, get_date_string() reflects self.date."""
        d = datetime(2026, 3, 21)
        s = _ConcreteScreamsheet("output.pdf", date=d)
        assert s.get_date_string() == "March 21, 2026"

    def test_display_date_overrides_date_string(self):
        """When display_date differs from date, get_date_string() returns display_date."""
        game_date = datetime(2026, 3, 21)
        run_date = datetime(2026, 3, 22)
        s = _ConcreteScreamsheet("output.pdf", date=game_date, display_date=run_date)
        assert s.get_date_string() == "March 22, 2026"

    def test_display_date_does_not_affect_self_date(self):
        """display_date never changes the game-lookup date stored in self.date."""
        game_date = datetime(2026, 3, 21)
        run_date = datetime(2026, 3, 22)
        s = _ConcreteScreamsheet("output.pdf", date=game_date, display_date=run_date)
        assert s.date == game_date


# ---------------------------------------------------------------------------
# Brand footer
# ---------------------------------------------------------------------------

class TestBaseScreamshetBrandFooter:
    def test_brand_footer_text_stored(self):
        s = _ConcreteScreamsheet("output.pdf", brand_footer_text="example.com")
        assert s.brand_footer_text == "example.com"

    def test_brand_footer_defaults_to_empty_string(self):
        s = _ConcreteScreamsheet("output.pdf")
        assert s.brand_footer_text == ""

    def test_generate_passes_page_callbacks_when_footer_set(self, tmp_path):
        s = _ConcreteScreamsheet(
            str(tmp_path / "out.pdf"), brand_footer_text="distractedfortune.com"
        )
        with patch("screamsheet.base.screamsheet.SimpleDocTemplate") as mock_cls:
            mock_doc = MagicMock()
            mock_cls.return_value = mock_doc
            s.generate()
        kwargs = mock_doc.build.call_args.kwargs
        assert "onFirstPage" in kwargs
        assert "onLaterPages" in kwargs

    def test_generate_no_page_callbacks_when_footer_empty(self, tmp_path):
        s = _ConcreteScreamsheet(str(tmp_path / "out.pdf"))
        with patch("screamsheet.base.screamsheet.SimpleDocTemplate") as mock_cls:
            mock_doc = MagicMock()
            mock_cls.return_value = mock_doc
            s.generate()
        kwargs = mock_doc.build.call_args.kwargs
        assert "onFirstPage" not in kwargs
        assert "onLaterPages" not in kwargs

    def test_both_callbacks_are_the_same_function(self, tmp_path):
        s = _ConcreteScreamsheet(
            str(tmp_path / "out.pdf"), brand_footer_text="distractedfortune.com"
        )
        with patch("screamsheet.base.screamsheet.SimpleDocTemplate") as mock_cls:
            mock_doc = MagicMock()
            mock_cls.return_value = mock_doc
            s.generate()
        kwargs = mock_doc.build.call_args.kwargs
        assert kwargs["onFirstPage"] is kwargs["onLaterPages"]

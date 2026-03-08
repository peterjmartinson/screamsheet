"""Unit tests for screamsheet.base.screamsheet (BaseScreamsheet ABC)."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

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

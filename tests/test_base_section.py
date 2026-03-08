"""Unit tests for screamsheet.base.section (Section ABC)."""
from unittest.mock import patch

import pytest

from screamsheet.base.section import Section


# ---------------------------------------------------------------------------
# Concrete subclass for exercising the abstract base
# ---------------------------------------------------------------------------

class _ConcreteSection(Section):
    """Minimal concrete Section used only for testing."""

    def fetch_data(self):
        self.data = ["item1", "item2"]

    def render(self):
        return []


class _EmptyListSection(Section):
    def fetch_data(self):
        self.data = []

    def render(self):
        return []


class _NoneDataSection(Section):
    def fetch_data(self):
        self.data = None

    def render(self):
        return []


class _DictDataSection(Section):
    def fetch_data(self):
        self.data = {"key": "value"}

    def render(self):
        return []


class _EmptyDictSection(Section):
    def fetch_data(self):
        self.data = {}

    def render(self):
        return []


class _ScalarDataSection(Section):
    """Section where data is a non-collection truthy value."""

    def fetch_data(self):
        self.data = "some text"

    def render(self):
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSectionInit:
    def test_title_stored(self):
        s = _ConcreteSection("My Title")
        assert s.title == "My Title"

    def test_data_initially_none(self):
        s = _ConcreteSection("t")
        assert s.data is None


class TestSectionHasContent:
    def test_true_for_nonempty_list(self):
        s = _ConcreteSection("t")
        assert s.has_content() is True

    def test_false_for_empty_list(self):
        s = _EmptyListSection("t")
        assert s.has_content() is False

    def test_false_when_data_is_none(self):
        s = _NoneDataSection("t")
        assert s.has_content() is False

    def test_true_for_nonempty_dict(self):
        s = _DictDataSection("t")
        assert s.has_content() is True

    def test_false_for_empty_dict(self):
        s = _EmptyDictSection("t")
        assert s.has_content() is False

    def test_true_for_scalar_value(self):
        s = _ScalarDataSection("t")
        assert s.has_content() is True

    def test_has_content_calls_fetch_data_when_data_is_none(self):
        s = _ConcreteSection("t")
        # data starts as None; has_content should trigger fetch_data
        assert s.data is None
        s.has_content()
        assert s.data is not None

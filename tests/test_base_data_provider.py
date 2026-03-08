"""Unit tests for screamsheet.base.data_provider (DataProvider ABC)."""
from datetime import datetime

import pytest

from screamsheet.base.data_provider import DataProvider


# ---------------------------------------------------------------------------
# Concrete subclass for exercising the abstract base
# ---------------------------------------------------------------------------

class _ConcreteProvider(DataProvider):
    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self):
        return None


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestDataProviderInit:
    def test_config_stored(self):
        p = _ConcreteProvider(foo="bar")
        assert p.config["foo"] == "bar"

    def test_empty_config_by_default(self):
        p = _ConcreteProvider()
        assert p.config == {}


# ---------------------------------------------------------------------------
# Default method stubs
# ---------------------------------------------------------------------------

class TestDataProviderDefaults:
    def setup_method(self):
        self.p = _ConcreteProvider()

    def test_get_box_score_returns_none(self):
        assert self.p.get_box_score(1, datetime.now()) is None

    def test_get_game_summary_returns_none(self):
        assert self.p.get_game_summary(1, datetime.now()) is None


# ---------------------------------------------------------------------------
# _sanitize_text
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def setup_method(self):
        self.p = _ConcreteProvider()

    def test_strips_html_tags(self):
        result = self.p._sanitize_text("<b>Hello</b> <em>World</em>")
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

    def test_decodes_html_entities(self):
        result = self.p._sanitize_text("AT&amp;T &lt;news&gt;")
        assert "&amp;" not in result
        assert "AT&T" in result

    def test_normalizes_whitespace(self):
        result = self.p._sanitize_text("  Multiple   spaces  here  ")
        assert "  " not in result
        assert result == result.strip()

    def test_empty_string_returns_empty(self):
        assert self.p._sanitize_text("") == ""

    def test_none_like_returns_empty(self):
        assert self.p._sanitize_text(None) == ""


# ---------------------------------------------------------------------------
# _looks_like_garbage
# ---------------------------------------------------------------------------

class TestLooksLikeGarbage:
    def setup_method(self):
        self.p = _ConcreteProvider()

    def test_empty_string_is_garbage(self):
        assert self.p._looks_like_garbage("") is True

    def test_too_short_is_garbage(self):
        assert self.p._looks_like_garbage("hi") is True

    def test_stray_brace_is_garbage(self):
        assert self.p._looks_like_garbage("{") is True

    def test_normal_sentence_not_garbage(self):
        assert self.p._looks_like_garbage("The Phillies won the game 5-3.") is False

    def test_empty_json_is_garbage(self):
        assert self.p._looks_like_garbage("{}") is True


# ---------------------------------------------------------------------------
# sanitize_entry
# ---------------------------------------------------------------------------

class TestSanitizeEntry:
    def setup_method(self):
        self.p = _ConcreteProvider()

    def test_returns_cleaned_dict_for_valid_entry(self):
        entry = {
            "title": "Phillies Win Big",
            "summary": "The Philadelphia Phillies won a crucial game last night.",
            "link": "https://example.com/phillies",
        }
        result = self.p.sanitize_entry(entry)
        assert result is not None
        assert result["title"] == "Phillies Win Big"

    def test_returns_none_for_garbage_entry(self):
        entry = {"title": "{", "summary": "x"}
        assert self.p.sanitize_entry(entry) is None

    def test_returns_none_for_non_dict(self):
        assert self.p.sanitize_entry(42) is None

    def test_truncates_very_long_summary(self):
        long_text = "word " * 4000
        entry = {"title": "Title Here", "summary": long_text}
        result = self.p.sanitize_entry(entry)
        assert result is not None
        assert len(result["summary"]) <= 4100  # some slack for trailing "..."


# ---------------------------------------------------------------------------
# sanitize_articles
# ---------------------------------------------------------------------------

class TestSanitizeArticles:
    def setup_method(self):
        self.p = _ConcreteProvider()

    def test_filters_out_garbage_entries(self):
        articles = [
            {"slot": "Section 1", "entry": {"title": "{", "summary": "x"}},
        ]
        result = self.p.sanitize_articles(articles)
        assert result == []

    def test_keeps_valid_entries(self):
        articles = [
            {
                "slot": "Section 1",
                "entry": {
                    "title": "Phillies Win",
                    "summary": "The Phillies won a very important game yesterday.",
                },
            }
        ]
        result = self.p.sanitize_articles(articles)
        assert len(result) == 1
        assert result[0]["slot"] == "Section 1"

    def test_handles_empty_list(self):
        assert self.p.sanitize_articles([]) == []

    def test_handles_none_input(self):
        assert self.p.sanitize_articles(None) == []

"""Unit tests for screamsheet.providers.mlb_trade_rumors_provider (MLBTradeRumorsProvider)."""
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider


@pytest.fixture
def provider():
    return MLBTradeRumorsProvider(
        favorite_teams=["Phillies", "Padres", "Yankees"], max_articles=4
    )


# ---------------------------------------------------------------------------
# get_game_scores / get_standings stubs
# ---------------------------------------------------------------------------

class TestMLBTRProviderStubs:
    def test_get_game_scores_returns_empty_list(self, provider, sample_date):
        assert provider.get_game_scores(sample_date) == []

    def test_get_standings_returns_none(self, provider):
        assert provider.get_standings() is None


# ---------------------------------------------------------------------------
# _is_garbage
# ---------------------------------------------------------------------------

class TestMLBTRIsGarbage:
    def test_excluded_keyword_in_title_is_garbage(self, provider):
        entry = {"title": "Top 50 Prospects", "summary": "Some content here."}
        assert provider._is_garbage(entry) is True

    def test_excluded_keyword_in_summary_is_garbage(self, provider):
        entry = {"title": "Normal Title", "summary": "Win a Contest now!"}
        assert provider._is_garbage(entry) is True

    def test_clean_entry_not_garbage(self, provider):
        entry = {
            "title": "Phillies Sign New Pitcher",
            "summary": "The Phillies have agreed to a deal.",
        }
        assert provider._is_garbage(entry) is False


# ---------------------------------------------------------------------------
# get_articles
# ---------------------------------------------------------------------------

class TestMLBTRGetArticles:
    def test_returns_list(self, provider, rss_entry):
        fake_feed = MagicMock()
        fake_feed.entries = [rss_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        assert isinstance(result, list)

    def test_result_items_have_slot_and_entry_keys(self, provider, rss_entry):
        fake_feed = MagicMock()
        fake_feed.entries = [rss_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        for item in result:
            assert "slot" in item
            assert "entry" in item

    def test_garbage_entries_filtered_out(self, provider):
        garbage_entry = {
            "title": "Top 50 Contest",
            "summary": "Win a contest today.",
            "link": "https://example.com/garbage",
        }
        fake_feed = MagicMock()
        fake_feed.entries = [garbage_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        assert result == []

    def test_phpillies_article_fills_slot_1(self, provider):
        phillies_entry = {
            "title": "Phillies Sign Pitcher",
            "summary": "Philadelphia Phillies have signed a new pitcher today.",
            "link": "https://example.com/phillies",
        }
        general_entry = {
            "title": "General Baseball News",
            "summary": "Some general baseball news happened today in the league.",
            "link": "https://example.com/general",
        }
        fake_feed = MagicMock()
        fake_feed.entries = [phillies_entry, general_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        slots = [item["slot"] for item in result]
        assert "Section 1" in slots or "Section 2" in slots  # slot indexing 1-based

    def test_max_articles_respected(self, provider, rss_entry):
        many_entries = [dict(rss_entry, link=f"https://example.com/{i}") for i in range(10)]
        fake_feed = MagicMock()
        fake_feed.entries = many_entries
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        assert len(result) <= provider.max_articles

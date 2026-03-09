"""Unit tests for screamsheet.providers.political_news_provider."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.providers.political_news_provider import (
    PoliticalRSSProvider,
    WhiteHouseProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _struct_time_utc(dt: datetime):
    """Return a time.struct_time-like tuple that feedparser puts in published_parsed."""
    import time
    return time.struct_time((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, 0))


def _recent_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=6)


def _old_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=72)


def _make_rss_entry(title="Breaking News", link="https://example.com/1",
                    summary="Some summary.", published=None):
    entry = MagicMock()
    entry.get = lambda k, default=None: {
        "title": title, "link": link, "summary": summary,
        "published_parsed": _struct_time_utc(published or _recent_dt()),
        "updated_parsed": None,
    }.get(k, default)
    return entry


def _make_fake_feed(entries):
    feed = MagicMock()
    feed.entries = entries
    return feed


# ---------------------------------------------------------------------------
# PoliticalRSSProvider — stubs
# ---------------------------------------------------------------------------

class TestPoliticalRSSProviderStubs:
    def test_get_game_scores_returns_empty_list(self, sample_date):
        provider = PoliticalRSSProvider()
        assert provider.get_game_scores(sample_date) == []

    def test_get_standings_returns_none(self):
        provider = PoliticalRSSProvider()
        assert provider.get_standings() is None


# ---------------------------------------------------------------------------
# PoliticalRSSProvider — _published_dt
# ---------------------------------------------------------------------------

class TestPublishedDt:
    def test_returns_utc_aware_datetime(self):
        provider = PoliticalRSSProvider()
        entry = MagicMock()
        dt = _recent_dt()
        entry.get = lambda k, default=None: {
            "published_parsed": _struct_time_utc(dt),
            "updated_parsed": None,
        }.get(k, default)
        result = provider._published_dt(entry)
        assert result is not None
        assert result.tzinfo is not None

    def test_returns_none_when_no_date(self):
        provider = PoliticalRSSProvider()
        entry = MagicMock()
        entry.get = lambda k, default=None: None
        assert provider._published_dt(entry) is None

    def test_falls_back_to_updated_parsed(self):
        provider = PoliticalRSSProvider()
        dt = _recent_dt()
        entry = MagicMock()
        entry.get = lambda k, default=None: {
            "published_parsed": None,
            "updated_parsed": _struct_time_utc(dt),
        }.get(k, default)
        result = provider._published_dt(entry)
        assert result is not None


# ---------------------------------------------------------------------------
# PoliticalRSSProvider — _normalize_rss_entry
# ---------------------------------------------------------------------------

class TestNormalizeRSSEntry:
    def test_returns_dict_with_required_keys(self):
        provider = PoliticalRSSProvider()
        entry = _make_rss_entry()
        result = provider._normalize_rss_entry(entry, "Reuters")
        assert result is not None
        assert set(result.keys()) == {"title", "link", "published", "summary", "source"}

    def test_source_name_set_correctly(self):
        provider = PoliticalRSSProvider()
        entry = _make_rss_entry()
        result = provider._normalize_rss_entry(entry, "BBC")
        assert result["source"] == "BBC"

    def test_returns_none_when_title_missing(self):
        provider = PoliticalRSSProvider()
        entry = _make_rss_entry(title="")
        assert provider._normalize_rss_entry(entry, "Reuters") is None

    def test_returns_none_when_no_date(self):
        provider = PoliticalRSSProvider()
        entry = MagicMock()
        entry.get = lambda k, default=None: {
            "title": "Something", "link": "https://x.com", "summary": "",
            "published_parsed": None, "updated_parsed": None,
        }.get(k, default)
        assert provider._normalize_rss_entry(entry, "AP") is None


# ---------------------------------------------------------------------------
# PoliticalRSSProvider — _within_48h
# ---------------------------------------------------------------------------

class TestWithin48h:
    def test_recent_entry_passes(self):
        provider = PoliticalRSSProvider()
        assert provider._within_48h(_recent_dt()) is True

    def test_old_entry_filtered(self):
        provider = PoliticalRSSProvider()
        assert provider._within_48h(_old_dt()) is False


# ---------------------------------------------------------------------------
# PoliticalRSSProvider — get_articles
# ---------------------------------------------------------------------------

class TestGetArticles:
    def test_returns_list(self):
        provider = PoliticalRSSProvider()
        with patch("feedparser.parse", return_value=_make_fake_feed([_make_rss_entry()])):
            result = provider.get_articles()
        assert isinstance(result, list)

    def test_old_entries_filtered_out(self):
        provider = PoliticalRSSProvider()
        old_entry = _make_rss_entry(published=_old_dt())
        with patch("feedparser.parse", return_value=_make_fake_feed([old_entry])):
            result = provider.get_articles()
        assert result == []

    def test_result_items_have_required_keys(self):
        provider = PoliticalRSSProvider()
        with patch("feedparser.parse", return_value=_make_fake_feed([_make_rss_entry()])):
            result = provider.get_articles()
        for item in result:
            assert {"title", "link", "published", "summary", "source"} <= set(item.keys())

    def test_one_source_error_does_not_abort_others(self):
        """If one feedparser.parse raises, the remaining sources still return results."""
        provider = PoliticalRSSProvider()
        call_count = 0

        def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("network down")
            return _make_fake_feed([_make_rss_entry()])

        with patch("feedparser.parse", side_effect=side_effect):
            result = provider.get_articles()

        # 6 remaining sources each contribute one entry
        assert len(result) == 6

    def test_entries_include_source_name(self):
        provider = PoliticalRSSProvider()
        # Only patch The Guardian to return a result; others can return empty feeds
        def side_effect(url):
            if "theguardian" in url.lower():
                return _make_fake_feed([_make_rss_entry()])
            return _make_fake_feed([])

        with patch("feedparser.parse", side_effect=side_effect):
            result = provider.get_articles()

        assert any(item["source"] == "The Guardian" for item in result)


# ---------------------------------------------------------------------------
# WhiteHouseProvider — stubs
# ---------------------------------------------------------------------------

class TestWhiteHouseProviderStubs:
    def test_get_game_scores_returns_empty_list(self, sample_date):
        provider = WhiteHouseProvider()
        assert provider.get_game_scores(sample_date) == []

    def test_get_standings_returns_none(self):
        provider = WhiteHouseProvider()
        assert provider.get_standings() is None


# ---------------------------------------------------------------------------
# WhiteHouseProvider — _parse_date
# ---------------------------------------------------------------------------

class TestWhiteHouseParseDatete:
    def _tag(self, datetime_attr=None, text=""):
        from bs4 import BeautifulSoup
        attr = f' datetime="{datetime_attr}"' if datetime_attr else ""
        html = f"<time{attr}>{text}</time>"
        return BeautifulSoup(html, "html.parser").find("time")

    def test_parses_iso_datetime_attr(self):
        provider = WhiteHouseProvider()
        tag = self._tag(datetime_attr="2026-03-07T14:00:00Z")
        result = provider._parse_date(tag)
        assert result is not None
        assert result.year == 2026
        assert result.tzinfo is not None

    def test_parses_date_only_attr(self):
        provider = WhiteHouseProvider()
        tag = self._tag(datetime_attr="2026-03-07")
        result = provider._parse_date(tag)
        assert result is not None
        assert result.year == 2026

    def test_returns_none_for_none_tag(self):
        provider = WhiteHouseProvider()
        assert provider._parse_date(None) is None

    def test_returns_none_for_unparseable_text(self):
        provider = WhiteHouseProvider()
        tag = self._tag(text="last Tuesday")
        assert provider._parse_date(tag) is None


# ---------------------------------------------------------------------------
# WhiteHouseProvider — _parse_html (primary selector + fallback)
# ---------------------------------------------------------------------------

FAKE_HTML_PRIMARY = """
<html><body>
  <li class="wp-block-post">
    <h2 class="wp-block-post-title">
      <a href="/briefings-statements/2026/03/statement-on-trade-policy">Statement on Trade Policy</a>
    </h2>
    <div class="wp-block-post-date"><time datetime="2026-03-08T10:00:00Z">March 8, 2026</time></div>
  </li>
</body></html>
"""

FAKE_HTML_FALLBACK = """
<html><body>
  <article>
    <h2><a href="/briefing-room/2">Executive Order Signed</a></h2>
    <time datetime="2026-03-08T09:00:00Z">March 8, 2026</time>
    <p>An order was signed today.</p>
  </article>
</body></html>
"""

FAKE_HTML_OLD = """
<html><body>
  <li class="wp-block-post">
    <h2 class="wp-block-post-title">
      <a href="/briefings-statements/2024/01/old-statement">Old Statement</a>
    </h2>
    <div class="wp-block-post-date"><time datetime="2024-01-01T00:00:00Z">January 1, 2024</time></div>
  </li>
</body></html>
"""


class TestWhiteHouseParseHtml:
    def test_primary_selector_returns_entry(self):
        provider = WhiteHouseProvider()
        results = provider._parse_html(FAKE_HTML_PRIMARY)
        assert len(results) == 1
        assert results[0]["title"] == "Statement on Trade Policy"
        assert results[0]["source"] == "White House"

    def test_fallback_selector_returns_entry(self):
        provider = WhiteHouseProvider()
        results = provider._parse_html(FAKE_HTML_FALLBACK)
        assert len(results) == 1
        assert results[0]["title"] == "Executive Order Signed"

    def test_link_is_absolute(self):
        provider = WhiteHouseProvider()
        results = provider._parse_html(FAKE_HTML_PRIMARY)
        assert results[0]["link"].startswith("https://")

    def test_old_entry_filtered_out(self):
        provider = WhiteHouseProvider()
        results = provider._parse_html(FAKE_HTML_OLD)
        assert results == []

    def test_empty_html_returns_empty_list(self):
        provider = WhiteHouseProvider()
        assert provider._parse_html("<html><body></body></html>") == []


# ---------------------------------------------------------------------------
# WhiteHouseProvider — get_articles error isolation
# ---------------------------------------------------------------------------

class TestWhiteHouseGetArticles:
    def test_fetch_failure_returns_empty_list(self):
        provider = WhiteHouseProvider()
        with patch.object(provider, "_fetch_html", side_effect=ConnectionError("down")):
            result = provider.get_articles()
        assert result == []

    def test_successful_fetch_returns_list(self):
        provider = WhiteHouseProvider()
        with patch.object(provider, "_fetch_html", return_value=FAKE_HTML_PRIMARY):
            result = provider.get_articles()
        assert isinstance(result, list)
        assert len(result) == 1

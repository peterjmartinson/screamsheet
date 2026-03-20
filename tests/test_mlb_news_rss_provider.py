"""Unit tests for screamsheet.providers.mlb_news_rss_provider (MLBNewsRssProvider)."""
from unittest.mock import patch, MagicMock

import pytest
import requests

from screamsheet.providers.mlb_news_rss_provider import MLBNewsRssProvider


@pytest.fixture
def provider() -> MLBNewsRssProvider:
    return MLBNewsRssProvider(
        favorite_teams=["Phillies", "Padres", "Yankees"], max_articles=4
    )


# ---------------------------------------------------------------------------
# TEAM_FEEDS class constant
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderFeedUrls:
    def test_phillies_feed_url_in_team_feeds(self) -> None:
        assert "Phillies" in MLBNewsRssProvider.TEAM_FEEDS

    def test_padres_feed_url_in_team_feeds(self) -> None:
        assert "Padres" in MLBNewsRssProvider.TEAM_FEEDS

    def test_yankees_feed_url_in_team_feeds(self) -> None:
        assert "Yankees" in MLBNewsRssProvider.TEAM_FEEDS

    def test_general_mlb_feed_url_present(self) -> None:
        assert None in MLBNewsRssProvider.TEAM_FEEDS


# ---------------------------------------------------------------------------
# Default priority order
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderDefaults:
    def test_default_priority_order(self) -> None:
        p = MLBNewsRssProvider()
        assert p.favorite_teams == ["Phillies", "Padres", "Yankees"]

    def test_default_max_articles_is_four(self) -> None:
        p = MLBNewsRssProvider()
        assert p.max_articles == 4


# ---------------------------------------------------------------------------
# get_game_scores / get_standings stubs
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderStubs:
    def test_get_game_scores_returns_empty_list(
        self, provider: MLBNewsRssProvider, sample_date: object
    ) -> None:
        assert provider.get_game_scores(sample_date) == []  # type: ignore[arg-type]

    def test_get_standings_returns_none(self, provider: MLBNewsRssProvider) -> None:
        assert provider.get_standings() is None


# ---------------------------------------------------------------------------
# get_articles — shape and count
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderGetArticles:
    def test_returns_list(self, provider: MLBNewsRssProvider, rss_entry: dict) -> None:
        fake_feed = MagicMock()
        fake_feed.entries = [rss_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        assert isinstance(result, list)

    def test_result_items_have_slot_key(
        self, provider: MLBNewsRssProvider, rss_entry: dict
    ) -> None:
        fake_feed = MagicMock()
        fake_feed.entries = [rss_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        for item in result:
            assert "slot" in item

    def test_result_items_have_entry_key(
        self, provider: MLBNewsRssProvider, rss_entry: dict
    ) -> None:
        fake_feed = MagicMock()
        fake_feed.entries = [rss_entry]
        with patch("feedparser.parse", return_value=fake_feed):
            result = provider.get_articles()
        for item in result:
            assert "entry" in item

    def test_returns_four_articles_when_feeds_populated(
        self, provider: MLBNewsRssProvider
    ) -> None:
        call_count: list = [0]

        def fake_parse(url: str) -> MagicMock:
            call_count[0] += 1
            entry = {
                "title": f"Article {call_count[0]}",
                "link": f"https://mlb.com/article/{call_count[0]}",
                "summary": "test",
            }
            feed = MagicMock()
            feed.entries = [entry]
            return feed

        with patch("feedparser.parse", side_effect=fake_parse):
            result = provider.get_articles()
        assert len(result) == 4


# ---------------------------------------------------------------------------
# get_articles — priority ordering
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderPriority:
    def test_phillies_entry_appears_first_when_available(self) -> None:
        phillies_entry = {
            "title": "Phillies Win Big",
            "link": "https://phillies.com/1",
            "summary": "test",
        }
        general_entry = {
            "title": "General MLB News",
            "link": "https://mlb.com/1",
            "summary": "test",
        }

        def fake_parse(url: str) -> MagicMock:
            feed = MagicMock()
            feed.entries = [phillies_entry] if "phillies" in url.lower() else [general_entry]
            return feed

        p = MLBNewsRssProvider(
            favorite_teams=["Phillies", "Padres", "Yankees"], max_articles=4
        )
        with patch("feedparser.parse", side_effect=fake_parse):
            result = p.get_articles()
        assert result[0]["entry"]["title"] == "Phillies Win Big"

    def test_custom_priority_order_is_respected(self) -> None:
        yankees_entry = {
            "title": "Yankees Score",
            "link": "https://yankees.com/1",
            "summary": "y",
        }
        other_entry = {
            "title": "Other News",
            "link": "https://other.com/1",
            "summary": "o",
        }

        def fake_parse(url: str) -> MagicMock:
            feed = MagicMock()
            feed.entries = [yankees_entry] if "yankees" in url.lower() else [other_entry]
            return feed

        p = MLBNewsRssProvider(
            favorite_teams=["Yankees", "Phillies", "Padres"], max_articles=4
        )
        with patch("feedparser.parse", side_effect=fake_parse):
            result = p.get_articles()
        assert result[0]["entry"]["title"] == "Yankees Score"


# ---------------------------------------------------------------------------
# get_articles — fallback to general MLB feed
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderFallback:
    def test_falls_back_to_general_when_team_feed_is_empty(self) -> None:
        general_entry = {
            "title": "MLB General News",
            "link": "https://mlb.com/1",
            "summary": "general",
        }

        def fake_parse(url: str) -> MagicMock:
            feed = MagicMock()
            # Only the general (non-team) MLB feed has entries
            feed.entries = [] if any(t in url for t in ["phillies", "padres", "yankees"]) else [general_entry]
            return feed

        p = MLBNewsRssProvider(favorite_teams=["Phillies"], max_articles=1)
        with patch("feedparser.parse", side_effect=fake_parse):
            result = p.get_articles()
        assert len(result) == 1
        assert result[0]["entry"]["title"] == "MLB General News"


# ---------------------------------------------------------------------------
# _is_junk_article
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderIsJunkArticle:
    def test_spring_breakout_in_title_is_junk(self, provider: MLBNewsRssProvider) -> None:
        entry = {"title": "Spring Breakout: Yankees vs Phillies", "link": "https://mlb.com/1"}
        assert provider._is_junk_article(entry) is True

    def test_spring_breakout_case_insensitive(self, provider: MLBNewsRssProvider) -> None:
        entry = {"title": "spring breakout recap", "link": "https://mlb.com/1"}
        assert provider._is_junk_article(entry) is True

    def test_regular_phillies_article_is_not_junk(self, provider: MLBNewsRssProvider) -> None:
        entry = {"title": "Phillies sign new starter", "link": "https://mlb.com/2"}
        assert provider._is_junk_article(entry) is False

    def test_empty_title_is_not_junk(self, provider: MLBNewsRssProvider) -> None:
        entry = {"title": "", "link": "https://mlb.com/3"}
        assert provider._is_junk_article(entry) is False


# ---------------------------------------------------------------------------
# _is_junk_article — integration with get_articles selection
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderJunkFiltering:
    def test_spring_breakout_article_skipped_during_selection(self) -> None:
        junk_entry = {
            "title": "Spring Breakout: Padres edition",
            "link": "https://mlb.com/junk",
            "summary": "",
        }
        good_entry = {
            "title": "Padres Ace Looks Dominant",
            "link": "https://mlb.com/good",
            "summary": "Great stuff.",
        }

        def fake_parse(url: str) -> MagicMock:
            feed = MagicMock()
            feed.entries = [junk_entry, good_entry]
            return feed

        p = MLBNewsRssProvider(favorite_teams=["Padres"], max_articles=1)
        with patch("feedparser.parse", side_effect=fake_parse):
            result = p.get_articles()
        assert len(result) == 1
        assert result[0]["entry"]["title"] == "Padres Ace Looks Dominant"

    def test_spring_breakout_filtered_in_sanitize_articles(
        self, provider: MLBNewsRssProvider
    ) -> None:
        junk_item = {
            "slot": "Section 1",
            "entry": {
                "title": "Spring Breakout highlights",
                "link": "https://mlb.com/junk",
                "summary": "some text here for length",
            },
        }
        with patch.object(provider, "_scrape_article_text", return_value=""):
            result = provider.sanitize_articles([junk_item])
        assert result == []


# ---------------------------------------------------------------------------
# _scrape_article_text
# ---------------------------------------------------------------------------

FAKE_MLB_HTML = """
<html><body>
  <article>
    <p>The Phillies rotation is shaping up nicely.</p>
    <p>Zack Wheeler looked sharp in his outing.</p>
  </article>
</body></html>
"""


class TestMLBNewsRssProviderScrapeArticleText:
    def test_scrape_returns_paragraph_text(
        self, provider: MLBNewsRssProvider
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = FAKE_MLB_HTML
        with patch("requests.get", return_value=mock_resp):
            result = provider._scrape_article_text("https://mlb.com/article/1")
        assert "Phillies rotation" in result
        assert "Wheeler" in result

    def test_scrape_returns_empty_on_non_200_status(
        self, provider: MLBNewsRssProvider
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("requests.get", return_value=mock_resp):
            result = provider._scrape_article_text("https://mlb.com/gone")
        assert result == ""

    def test_scrape_returns_empty_on_request_exception(
        self, provider: MLBNewsRssProvider
    ) -> None:
        with patch("requests.get", side_effect=requests.RequestException("timeout")):
            result = provider._scrape_article_text("https://mlb.com/article/1")
        assert result == ""


# ---------------------------------------------------------------------------
# sanitize_articles — body text enrichment
# ---------------------------------------------------------------------------


class TestMLBNewsRssProviderBodyEnrichment:
    def test_scraped_text_replaces_empty_summary(
        self, provider: MLBNewsRssProvider
    ) -> None:
        item = {
            "slot": "Section 1",
            "entry": {
                "title": "Phillies ace dominates spring",
                "link": "https://www.mlb.com/phillies/news/article",
                "summary": "",
                "id": "https://www.mlb.com/phillies/news/article",
            },
        }
        scraped_text = "Wheeler threw seven innings of shutout ball in his spring outing."
        with patch.object(provider, "_scrape_article_text", return_value=scraped_text):
            result = provider.sanitize_articles([item])
        assert len(result) == 1
        assert result[0]["entry"]["summary"] == scraped_text

    def test_existing_summary_not_overwritten(
        self, provider: MLBNewsRssProvider
    ) -> None:
        original_summary = "A" * 50  # long enough to pass garbage check
        item = {
            "slot": "Section 1",
            "entry": {
                "title": "Phillies offense explodes for ten runs",
                "link": "https://www.mlb.com/phillies/news/article2",
                "summary": original_summary,
                "id": "https://www.mlb.com/phillies/news/article2",
            },
        }
        with patch.object(provider, "_scrape_article_text") as mock_scrape:
            result = provider.sanitize_articles([item])
        mock_scrape.assert_not_called()
        assert result[0]["entry"]["summary"] == original_summary


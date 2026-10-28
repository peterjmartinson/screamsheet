"""Unit tests for screamsheet.providers.nhl_news_rss_provider (NHLNewsRssProvider)."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.nhl_news_rss_provider import NHLNewsRssProvider


@pytest.fixture
def provider() -> NHLNewsRssProvider:
    return NHLNewsRssProvider(
        favorite_teams=["Flyers", "Golden Knights", "Penguins"], max_articles=4
    )


def _news_card(title: str, link: str, published: datetime) -> str:
        return f'''
        <a class="nhl-c-card-wrap -story" href="{link}">
            <article class="nhl-c-card -default oc-card--boxed-vertical-40 -no-description">
                <div class="nhl-c-card__content">
                    <div class="fa-text">
                        <h3 class="fa-text__title">{title}</h3>
                        <span class="fa-text__meta">
                            <time datetime="{published.isoformat()}">{published.strftime("%b %d, %Y")}</time>
                        </span>
                    </div>
                </div>
            </article>
        </a>
        '''


def _page_html(cards: list[str]) -> str:
        return "<html><body>" + "\n".join(cards) + "</body></html>"


def _response(html: str) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        response.text = html
        return response


# ---------------------------------------------------------------------------
# TEAM_FEEDS class constant
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderFeedUrls:
    def test_flyers_feed_url_in_team_feeds(self) -> None:
        assert "Flyers" in NHLNewsRssProvider.TEAM_FEEDS

    def test_golden_knights_feed_url_in_team_feeds(self) -> None:
        assert "Golden Knights" in NHLNewsRssProvider.TEAM_FEEDS

    def test_penguins_feed_url_in_team_feeds(self) -> None:
        assert "Penguins" in NHLNewsRssProvider.TEAM_FEEDS

    def test_general_nhl_feed_url_present(self) -> None:
        assert None in NHLNewsRssProvider.TEAM_FEEDS


# ---------------------------------------------------------------------------
# Default priority order
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderDefaults:
    def test_default_favorite_teams_is_empty(self) -> None:
        p = NHLNewsRssProvider()
        assert p.favorite_teams == []

    def test_default_max_articles_is_four(self) -> None:
        p = NHLNewsRssProvider()
        assert p.max_articles == 4


# ---------------------------------------------------------------------------
# get_game_scores / get_standings stubs
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderStubs:
    def test_get_game_scores_returns_empty_list(
        self, provider: NHLNewsRssProvider, sample_date: object
    ) -> None:
        assert provider.get_game_scores(sample_date) == []  # type: ignore[arg-type]

    def test_get_standings_returns_none(self, provider: NHLNewsRssProvider) -> None:
        assert provider.get_standings() is None


# ---------------------------------------------------------------------------
# get_articles - shape and count
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderGetArticles:
    def test_returns_list(self, provider: NHLNewsRssProvider, rss_entry: dict) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("Flyers Win Big", "https://nhl.com/flyers/1", now),
        ])
        with patch("requests.get", return_value=_response(html)):
            result = provider.get_articles()
        assert isinstance(result, list)

    def test_result_items_have_slot_key(
        self, provider: NHLNewsRssProvider, rss_entry: dict
    ) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("Flyers Win Big", "https://nhl.com/flyers/1", now),
        ])
        with patch("requests.get", return_value=_response(html)):
            result = provider.get_articles()
        for item in result:
            assert "slot" in item

    def test_result_items_have_entry_key(
        self, provider: NHLNewsRssProvider, rss_entry: dict
    ) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("Flyers Win Big", "https://nhl.com/flyers/1", now),
        ])
        with patch("requests.get", return_value=_response(html)):
            result = provider.get_articles()
        for item in result:
            assert "entry" in item

    def test_returns_four_articles_when_feeds_populated(
        self, provider: NHLNewsRssProvider
    ) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html(
            [
                _news_card("Flyers Win Big", "https://nhl.com/flyers/1", now),
                _news_card("Golden Knights Rally", "https://nhl.com/knights/1", now),
                _news_card("Penguins Sign Veteran", "https://nhl.com/pens/1", now),
                _news_card("League Roundup", "https://nhl.com/league/1", now),
            ]
        )
        with patch("requests.get", return_value=_response(html)):
            result = provider.get_articles()
        assert len(result) == 4


# ---------------------------------------------------------------------------
# get_articles - priority ordering
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderPriority:
    def test_flyers_entry_appears_first_when_available(self) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("Flyers Win Big", "https://nhl.com/flyers/1", now),
            _news_card("General NHL News", "https://nhl.com/news/1", now),
        ])

        p = NHLNewsRssProvider(
            favorite_teams=["Flyers", "Golden Knights", "Penguins"], max_articles=4
        )
        with patch("requests.get", return_value=_response(html)):
            result = p.get_articles()
        assert result[0]["entry"]["title"] == "Flyers Win Big"

    def test_custom_priority_order_is_respected(self) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("Penguins Score", "https://nhl.com/penguins/1", now),
            _news_card("Other News", "https://nhl.com/other/1", now),
        ])

        p = NHLNewsRssProvider(
            favorite_teams=["Penguins", "Flyers", "Golden Knights"], max_articles=4
        )
        with patch("requests.get", return_value=_response(html)):
            result = p.get_articles()
        assert result[0]["entry"]["title"] == "Penguins Score"


# ---------------------------------------------------------------------------
# get_articles - fallback to general NHL feed
# ---------------------------------------------------------------------------


class TestNHLNewsRssProviderFallback:
    def test_falls_back_to_general_when_team_feed_is_empty(self) -> None:
        now = datetime.now(timezone.utc)
        html = _page_html([
            _news_card("NHL General News", "https://nhl.com/news/1", now),
        ])

        p = NHLNewsRssProvider(favorite_teams=["Flyers"], max_articles=1)
        with patch("requests.get", return_value=_response(html)):
            result = p.get_articles()
        assert len(result) == 1
        assert result[0]["entry"]["title"] == "NHL General News"

    def test_multi_source_clusters_and_preserves_sources(self) -> None:
        now = datetime.now(timezone.utc)
        nhl_html = _page_html([
            _news_card(
                "Flyers trade defenseman to Oilers for draft picks",
                "https://www.nhl.com/news/flyers-oilers-trade",
                now,
            ),
        ])
        rss_xml = """<?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0"><channel>
          <item>
            <title>Flyers trade defenseman to Oilers for draft picks in blockbuster deal</title>
            <link>https://www.espn.com/nhl/story/flyers-oilers-trade</link>
            <description>Philadelphia and Edmonton completed a major trade involving draft picks.</description>
          </item>
        </channel></rss>
        """

        def fake_get(url: str, **kwargs: object) -> MagicMock:
            if "nhl.com" in url:
                return _response(nhl_html)
            if "espn.com" in url:
                return _response(rss_xml)
            return _response("")

        p = NHLNewsRssProvider(
            favorite_teams=["Flyers"],
            max_articles=1,
            mode="multi",
            extra_feeds={"ESPN": "https://www.espn.com/espn/rss/nhl/news"},
        )
        with patch("requests.get", side_effect=fake_get):
            articles = p.get_articles()
            sanitized = p.sanitize_articles(articles)

        assert len(sanitized) == 1
        entry = sanitized[0]["entry"]
        assert "NHL.com" in entry["sources"]
        assert "ESPN" in entry["sources"]
        assert "NHL.com" in entry["source"]
        assert "ESPN" in entry["source"]
        assert len(entry["reports"]) == 2

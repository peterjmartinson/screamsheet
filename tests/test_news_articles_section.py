"""Unit tests for screamsheet.renderers.news_articles (NewsArticlesSection)."""
from unittest.mock import MagicMock

import pytest
from reportlab.platypus import KeepTogether

from screamsheet.renderers.news_articles import NewsArticlesSection

_FAKE_ARTICLES = [
    {
        "slot": "MLB",
        "id": "art1",
        "title": "Phillies Win",
        "summary": "The Phillies won the game.\n\nGreat performance by the team.",
        "link": "http://example.com/1",
        "pub_date": "May 06, 2026",
        "source": "MLB.com",
    },
    {
        "slot": "MLB",
        "id": "art2",
        "title": "Padres Lose",
        "summary": "The Padres lost in extra innings.",
        "link": "http://example.com/2",
        "pub_date": None,
    },
    {
        "slot": "MLB",
        "id": "art3",
        "title": "Yankees Trade",
        "summary": "The Yankees made a trade.",
        "link": "http://example.com/3",
        "pub_date": "May 05, 2026",
    },
]


class TestNewsArticlesSectionRenderKeepTogether:
    def test_render_returns_empty_when_no_data(self) -> None:
        sec = NewsArticlesSection("News", MagicMock())
        sec.data = []
        assert sec.render() == []

    def test_render_all_top_level_elements_are_keep_together(self) -> None:
        sec = NewsArticlesSection("News", MagicMock())
        sec.data = _FAKE_ARTICLES
        elements = sec.render()
        assert all(isinstance(e, KeepTogether) for e in elements)

    def test_render_one_keep_together_per_article(self) -> None:
        sec = NewsArticlesSection("News", MagicMock())
        sec.data = _FAKE_ARTICLES
        elements = sec.render()
        assert len(elements) == len(_FAKE_ARTICLES)

    def test_render_single_article_returns_one_keep_together(self) -> None:
        sec = NewsArticlesSection("News", MagicMock())
        sec.data = [_FAKE_ARTICLES[0]]
        elements = sec.render()
        assert len(elements) == 1
        assert isinstance(elements[0], KeepTogether)

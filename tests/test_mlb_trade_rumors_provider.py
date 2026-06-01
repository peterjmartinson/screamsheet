"""Tests for MLBTradeRumorsProvider — no hardcoded teams; fallback to general feed."""
from unittest.mock import MagicMock, patch

from screamsheet.providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider


def _make_feed(entries: list) -> MagicMock:
    feed = MagicMock()
    feed.entries = entries
    return feed


GENERAL_ENTRIES = [
    {"title": "Blue Jays Sign Pitcher", "link": "http://ex.com/1", "summary": ""},
    {"title": "Cubs Trade Outfielder", "link": "http://ex.com/2", "summary": ""},
    {"title": "Rangers Extension Update", "link": "http://ex.com/3", "summary": ""},
    {"title": "Mets DFA Veteran", "link": "http://ex.com/4", "summary": ""},
]

ENTRIES_WITH_PHILLIES = [
    {"title": "Phillies Acquire Reliever", "link": "http://ex.com/p1", "summary": ""},
    {"title": "Blue Jays Sign Pitcher", "link": "http://ex.com/1", "summary": ""},
    {"title": "Cubs Trade Outfielder", "link": "http://ex.com/2", "summary": ""},
    {"title": "Rangers Extension Update", "link": "http://ex.com/3", "summary": ""},
    {"title": "Mets DFA Veteran", "link": "http://ex.com/4", "summary": ""},
]


def test_default_favorite_teams_is_empty():
    provider = MLBTradeRumorsProvider()
    assert provider.favorite_teams == []


@patch("screamsheet.providers.mlb_trade_rumors_provider.feedparser.parse")
def test_empty_favorite_teams_fills_all_slots_from_general_feed(mock_parse):
    mock_parse.return_value = _make_feed(GENERAL_ENTRIES)
    provider = MLBTradeRumorsProvider(favorite_teams=[])
    articles = provider.get_articles()
    assert len(articles) == 4


@patch("screamsheet.providers.mlb_trade_rumors_provider.feedparser.parse")
def test_empty_favorite_teams_uses_general_article_content(mock_parse):
    mock_parse.return_value = _make_feed(GENERAL_ENTRIES)
    provider = MLBTradeRumorsProvider(favorite_teams=[])
    articles = provider.get_articles()
    titles = [a["entry"]["title"] for a in articles]
    assert "Blue Jays Sign Pitcher" in titles


@patch("screamsheet.providers.mlb_trade_rumors_provider.feedparser.parse")
def test_favorite_team_article_is_included_when_title_matches(mock_parse):
    mock_parse.return_value = _make_feed(ENTRIES_WITH_PHILLIES)
    provider = MLBTradeRumorsProvider(favorite_teams=["Phillies"])
    articles = provider.get_articles()
    titles = [a["entry"]["title"] for a in articles]
    assert "Phillies Acquire Reliever" in titles


@patch("screamsheet.providers.mlb_trade_rumors_provider.feedparser.parse")
def test_unmatched_team_slots_filled_with_general_articles(mock_parse):
    mock_parse.return_value = _make_feed(GENERAL_ENTRIES)
    provider = MLBTradeRumorsProvider(favorite_teams=["Phillies"])
    articles = provider.get_articles()
    assert len(articles) == 4

"""Unit tests for the central news source catalog and UnifiedNewsProvider."""
from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.components import (
    ComponentRegistry,
    MLBNewsComponent,
    MLBTradeRumorsComponent,
    NFLNewsComponent,
    NHLNewsComponent,
    PresidentialNewsComponent,
    UnifiedNewsComponent,
)
from screamsheet.config import _parse_news
from screamsheet.order import build_custom_sheet_options_from_dict
from screamsheet.providers import (
    DEFAULT_SHEET_SOURCES,
    MLBNewsRssProvider,
    MLBTradeRumorsProvider,
    NEWS_SOURCE_CATALOG,
    NFLNewsProvider,
    NHLNewsRssProvider,
    PoliticalNewsProvider,
    UnifiedNewsProvider,
    resolve_news_sources,
)


def _make_feed(entries: list) -> MagicMock:
    feed = MagicMock()
    feed.entries = entries
    return feed


def _recent_struct_time():
    dt = datetime.now(timezone.utc) - timedelta(hours=3)
    return time.struct_time(
        (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, 0)
    )


class TestNewsSourceCatalog:
    def test_catalog_contains_all_expected_sources(self) -> None:
        expected_ids = {
            # MLB
            "mlb_com",
            "espn_mlb",
            "cbs_mlb",
            "yahoo_mlb",
            "mlb_trade_rumors",
            "fangraphs",
            "fox_mlb",
            # NHL
            "nhl_com",
            "espn_nhl",
            "cbs_nhl",
            "yahoo_nhl",
            "pro_hockey_rumors",
            "the_hockey_news",
            "sportsnet_nhl",
            # NFL
            "espn_nfl",
            "nfl_com",
            "pro_football_talk",
            "cbs_nfl",
            "yahoo_nfl",
            "nfl_trade_rumors",
            "fox_nfl",
            # Political
            "white_house",
            "the_guardian",
            "google_news",
            "bbc",
            "nyt",
            "politico",
            "npr",
            "washington_post",
        }
        assert expected_ids.issubset(set(NEWS_SOURCE_CATALOG.keys()))

    def test_default_sheet_sources_cover_all_five_sheets(self) -> None:
        for sheet in (
            "mlb_news",
            "mlb_trade_rumors",
            "nhl_news",
            "nfl_news",
            "presidential",
        ):
            assert sheet in DEFAULT_SHEET_SOURCES
            resolved = resolve_news_sources(default_sheet=sheet)
            assert len(resolved) >= 1


class TestResolveNewsSources:
    def test_resolve_cherry_picked_strings_and_weighted_dicts(self) -> None:
        sources = [
            {"id": "mlb_com", "bonus": 40},
            "fangraphs",
            {"id": "mlb_trade_rumors", "bonus": 15},
            {"name": "Custom Baseball Blog", "url": "https://example.com/rss", "bonus": 5},
        ]
        resolved = resolve_news_sources(sources=sources, category="mlb")
        assert len(resolved) == 4
        assert resolved[0].id == "mlb_com"
        assert resolved[0].bonus == 40
        assert resolved[0].kind == "mlb_team_rss"

        assert resolved[1].id == "fangraphs"
        assert resolved[1].name == "FanGraphs"
        assert resolved[1].bonus == 0

        assert resolved[2].id == "mlb_trade_rumors"
        assert resolved[2].bonus == 15

        assert resolved[3].name == "Custom Baseball Blog"
        assert resolved[3].url == "https://example.com/rss"
        assert resolved[3].bonus == 5

    def test_resolve_single_source_cherry_pick(self) -> None:
        resolved = resolve_news_sources(
            sources=[{"id": "mlb_com", "bonus": 25}],
            default_sheet="mlb_news",
        )
        assert len(resolved) == 1
        assert resolved[0].id == "mlb_com"
        assert resolved[0].bonus == 25


class TestUnifiedNewsProviderCherryPicking:
    def test_mlb_cherry_picked_sources_only_polls_selected_feeds(self) -> None:
        polled_urls: list[str] = []

        def fake_parse(url: str) -> MagicMock:
            polled_urls.append(url)
            if "fangraphs" in url:
                return _make_feed(
                    [
                        {
                            "title": "Phillies pitching analysis and velocity gains",
                            "link": "https://blogs.fangraphs.com/phillies-pitching",
                            "summary": "Deep dive into the Philadelphia Phillies starting rotation.",
                        }
                    ]
                )
            if "MlbTradeRumors" in url:
                return _make_feed(
                    [
                        {
                            "title": "Dodgers acquire veteran closer in blockbuster trade",
                            "link": "https://mlbtraderumors.com/dodgers-closer",
                            "summary": "Los Angeles added a ninth-inning reliever from the American League.",
                        }
                    ]
                )
            return _make_feed([])

        provider = MLBNewsRssProvider(
            favorite_teams=["Phillies"],
            max_articles=2,
            sources=[
                {"id": "fangraphs", "bonus": 20},
                "mlb_trade_rumors",
            ],
        )
        with patch("feedparser.parse", side_effect=fake_parse):
            articles = provider.get_articles()

        # MLB.com, ESPN, CBS, Yahoo, Fox should NOT have been polled
        assert len(polled_urls) == 2
        assert any("fangraphs" in u for u in polled_urls)
        assert any("MlbTradeRumors" in u for u in polled_urls)
        assert not any("mlb.com" in u for u in polled_urls)
        assert len(articles) == 2
        sources_returned = {a["entry"]["source"] for a in articles}
        assert "FanGraphs" in sources_returned
        assert "MLB Trade Rumors" in sources_returned

    def test_mlb_trade_rumors_provider_with_extra_cherry_picked_sources(self) -> None:
        def fake_parse(url: str) -> MagicMock:
            if "MlbTradeRumors" in url:
                return _make_feed(
                    [
                        {
                            "title": "Padres sign starter to two-year deal",
                            "link": "https://mlbtraderumors.com/padres-sign",
                            "summary": "San Diego Padres sign veteran right-hander to a two-year contract.",
                        }
                    ]
                )
            if "espn.com" in url:
                return _make_feed(
                    [
                        {
                            "title": "Padres sign starter to two-year contract in San Diego",
                            "link": "https://espn.com/mlb/padres-sign",
                            "summary": "The San Diego Padres finalized a two-year deal with the veteran starter.",
                        }
                    ]
                )
            return _make_feed([])

        provider = MLBTradeRumorsProvider(
            favorite_teams=["Padres"],
            max_articles=1,
            sources=[
                {"id": "mlb_trade_rumors", "bonus": 25},
                "espn_mlb",
            ],
        )
        with patch("screamsheet.providers.mlb_trade_rumors_provider.feedparser.parse", side_effect=fake_parse):
            articles = provider.get_articles()

        assert len(articles) == 1
        entry = articles[0]["entry"]
        assert "MLB Trade Rumors" in entry["sources"]
        assert "ESPN" in entry["sources"]

    def test_political_news_provider_cherry_picked_sources(self) -> None:
        polled_urls: list[str] = []

        def fake_parse(url: str) -> MagicMock:
            polled_urls.append(url)
            if "bbci.co.uk" in url:
                return _make_feed(
                    [
                        {
                            "title": "President announces new tariff and trade deal framework",
                            "link": "https://bbc.co.uk/news/tariff-deal",
                            "summary": "The White House and Congress debated the new trade deal and tariffs.",
                            "published_parsed": _recent_struct_time(),
                        }
                    ]
                )
            if "nytimes.com" in url:
                return _make_feed(
                    [
                        {
                            "title": "Senate votes on immigration and border legislation",
                            "link": "https://nytimes.com/senate-border",
                            "summary": "The Senate held a key vote on border and immigration policy.",
                            "published_parsed": _recent_struct_time(),
                        }
                    ]
                )
            return _make_feed([])

        provider = PoliticalNewsProvider(
            max_articles=2,
            sources=[
                {"id": "bbc", "bonus": 15},
                "nyt",
            ],
        )
        with patch("feedparser.parse", side_effect=fake_parse):
            articles = provider.get_articles()

        assert len(polled_urls) == 2
        assert len(articles) == 2
        returned_sources = {a["entry"]["source"] for a in articles}
        assert "BBC" in returned_sources
        assert "NYT" in returned_sources


class TestConfigAndComponentSourcesWiring:
    def test_parse_news_config_with_sources_list(self) -> None:
        raw_news = {
            "mlb_news": {
                "sources": [
                    {"id": "mlb_com", "bonus": 30},
                    "espn_mlb",
                    "fangraphs",
                ]
            },
            "presidential": {
                "sources": [
                    {"id": "white_house", "bonus": 35},
                    "bbc",
                    "politico",
                ]
            },
        }
        cfg = _parse_news(raw_news)
        assert cfg.mlb_news.sources == [
            {"id": "mlb_com", "bonus": 30},
            "espn_mlb",
            "fangraphs",
        ]
        assert cfg.presidential.sources == [
            {"id": "white_house", "bonus": 35},
            "bbc",
            "politico",
        ]

    def test_components_pass_sources_to_providers(self) -> None:
        mlb_comp = MLBNewsComponent(sources=["espn_mlb", "fangraphs"])
        assert isinstance(mlb_comp.provider, MLBNewsRssProvider)
        assert [s.id for s in mlb_comp.provider.resolved_sources] == ["espn_mlb", "fangraphs"]

        mtr_comp = MLBTradeRumorsComponent(sources=["mlb_trade_rumors", "cbs_mlb"])
        assert isinstance(mtr_comp.provider, MLBTradeRumorsProvider)
        assert [s.id for s in mtr_comp.provider.resolved_sources] == ["mlb_trade_rumors", "cbs_mlb"]

        nhl_comp = NHLNewsComponent(sources=["espn_nhl", "sportsnet_nhl"])
        assert isinstance(nhl_comp.provider, NHLNewsRssProvider)
        assert [s.id for s in nhl_comp.provider.resolved_sources] == ["espn_nhl", "sportsnet_nhl"]

        nfl_comp = NFLNewsComponent(sources=[{"id": "nfl_com", "bonus": 20}, "pro_football_talk"])
        assert isinstance(nfl_comp.provider, NFLNewsProvider)
        assert [s.id for s in nfl_comp.provider.resolved_sources] == ["nfl_com", "pro_football_talk"]

        pres_comp = PresidentialNewsComponent(sources=[{"id": "white_house", "bonus": 25}, "npr"])
        assert isinstance(pres_comp.provider, PoliticalNewsProvider)
        assert [s.id for s in pres_comp.provider.resolved_sources] == ["white_house", "npr"]

    def test_unified_news_component_registered_in_component_registry(self) -> None:
        comp = ComponentRegistry.create(
            "news",
            title="Custom Baseball Digest",
            favorite_teams=["Phillies"],
            sources=[{"id": "mlb_trade_rumors", "bonus": 20}, "fangraphs"],
        )
        assert isinstance(comp, UnifiedNewsComponent)
        assert isinstance(comp.provider, UnifiedNewsProvider)
        assert [s.id for s in comp.provider.resolved_sources] == ["mlb_trade_rumors", "fangraphs"]

    def test_custom_sheet_dict_preserves_component_sources_option(self) -> None:
        raw = {
            "screamsheet_title": "Morning Sports & Politics",
            "components": [
                {
                    "type": "mlb_news",
                    "title": "Hot Stove & Analytics",
                    "teams": ["Phillies"],
                    "sources": [
                        {"id": "mlb_trade_rumors", "bonus": 20},
                        "fangraphs",
                    ],
                },
                {
                    "type": "presidential_news",
                    "title": "Washington Wire",
                    "sources": [
                        {"id": "white_house", "bonus": 25},
                        "politico",
                        "npr",
                    ],
                },
            ],
        }
        opts = build_custom_sheet_options_from_dict("custom_digest", raw)
        assert len(opts.components) == 2
        assert opts.components[0].options["sources"] == [
            {"id": "mlb_trade_rumors", "bonus": 20},
            "fangraphs",
        ]
        assert opts.components[1].options["sources"] == [
            {"id": "white_house", "bonus": 25},
            "politico",
            "npr",
        ]

"""Unit tests for Stage 4: News & Weather Components + Overflow & Deduplication."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from screamsheet.components import (
    ComponentRegistry,
    CustomScreamsheet,
    FrenchMLBArticlesComponent,
    FrenchMLBLexiconComponent,
    MLBNewsComponent,
    MLBTradeRumorsComponent,
    NewsStoryComponent,
    NFLNewsComponent,
    NHLNewsComponent,
    PresidentialNewsComponent,
    WeatherComponent,
)
from screamsheet.providers.french_mlb_content_provider import FrenchMLBContent


def _make_article(idx: int, title: str = "", link: str = "") -> dict:
    t = title or f"Story Headline {idx}"
    url = link or f"https://example.com/story-{idx}"
    return {
        "slot": f"Slot {idx}",
        "entry": {
            "id": url,
            "title": t,
            "summary": f"Summary paragraph one for story {idx}.\n\nSummary paragraph two for story {idx}.",
            "link": url,
            "source": "Test Wire",
        },
    }


class TestStage4ComponentRegistry:
    """Verify all Stage 4 components are registered in ComponentRegistry."""

    @pytest.mark.parametrize(
        "key,expected_cls",
        [
            ("weather", WeatherComponent),
            ("presidential_news", PresidentialNewsComponent),
            ("mlb_trade_rumors", MLBTradeRumorsComponent),
            ("mlb_news", MLBNewsComponent),
            ("nhl_news", NHLNewsComponent),
            ("nfl_news", NFLNewsComponent),
            ("french_mlb_articles", FrenchMLBArticlesComponent),
            ("french_mlb_lexicon", FrenchMLBLexiconComponent),
        ],
    )
    def test_registered_in_component_registry(self, key, expected_cls):
        assert ComponentRegistry.get(key) is expected_cls


class TestWeatherComponent:
    def test_weather_component_renders_and_markdown(self):
        provider = MagicMock()
        provider.location_name = "Bryn Mawr, PA"
        provider.get_5_day_forecast.return_value = [
            {
                "day": "Mon",
                "max_temp": 75,
                "min_temp": 58,
                "description": "Sunny",
                "icon_url": "/nonexistent/icon.png",
            }
        ]
        comp = WeatherComponent(provider=provider, date=datetime(2026, 7, 4))
        assert comp.layout_spec.weight == 0.18
        assert comp.layout_spec.component_family == "weather"
        flowables = comp.render()
        assert len(flowables) == 2
        md = comp.render_markdown()
        assert "Bryn Mawr, PA" in md
        assert "MON" in md


class TestNewsStoryComponentOverflowAndDeduplication:
    def test_default_max_articles_is_four(self):
        provider = MagicMock()
        comp = MLBNewsComponent(provider=provider)
        assert comp.max_articles == 4

    def test_expand_page_units_splits_four_articles_into_two_page_units(self):
        provider = MagicMock()
        provider.get_articles.return_value = [_make_article(i) for i in range(1, 6)]
        provider.sanitize_articles.side_effect = lambda x: x

        comp = MLBNewsComponent(title="MLB News", provider=provider)
        # Patch _generate_summaries to avoid LLM calls
        comp._generate_summaries = lambda articles, summarizer: [
            {
                "slot": a["slot"],
                "id": a["entry"]["id"],
                "title": a["entry"]["title"],
                "summary": a["entry"]["summary"],
                "link": a["entry"]["link"],
                "source": a["entry"]["source"],
                "pub_date": "July 04, 2026",
            }
            for a in articles
        ]

        units = comp.expand_page_units()
        assert len(units) == 2
        assert len(units[0].data) == 2
        assert len(units[1].data) == 2
        assert units[0].data[0]["title"] == "Story Headline 1"
        assert units[0].data[1]["title"] == "Story Headline 2"
        assert units[1].data[0]["title"] == "Story Headline 3"
        assert units[1].data[1]["title"] == "Story Headline 4"

        # Verify each unit renders a 2-column table (left half = article 0, right half = article 1)
        table_0 = units[0].render()[0]
        assert len(table_0._cellvalues[0][0]) > 0  # left column has article 1
        assert len(table_0._cellvalues[0][1]) > 0  # right column has article 2

    def test_screamsheet_deduplicates_stories_across_news_components(self, tmp_path):
        """Stories already used by an earlier component on the screamsheet must not repeat."""
        shared_articles = [
            _make_article(1, title="Phillies Sign Ace Pitcher", link="https://mlb.com/1"),
            _make_article(2, title="Padres Acquire Slugger", link="https://mlb.com/2"),
            _make_article(3, title="Yankees Extend Captain", link="https://mlb.com/3"),
            _make_article(4, title="Dodgers Call Up Prospect", link="https://mlb.com/4"),
        ]
        provider1 = MagicMock()
        provider1.get_articles.return_value = list(shared_articles)
        provider1.sanitize_articles.side_effect = lambda x: x

        provider2 = MagicMock()
        # First 2 stories are duplicates (one by URL, one by title!)
        provider2.get_articles.return_value = [
            _make_article(10, title="Different Headline Same Link", link="https://mlb.com/1"),
            _make_article(20, title="Padres Acquire Slugger!", link="https://mtr.com/different-url"),
            _make_article(3, title="Yankees Extend Captain", link="https://mlb.com/3"),
            _make_article(4, title="Dodgers Call Up Prospect", link="https://mlb.com/4"),
        ]
        provider2.sanitize_articles.side_effect = lambda x: x

        comp1 = MLBNewsComponent(title="MLB News", provider=provider1, max_articles=2)
        comp2 = MLBTradeRumorsComponent(title="Trade Rumors", provider=provider2, max_articles=2)

        for c in (comp1, comp2):
            c._generate_summaries = lambda articles, summarizer: [
                {
                    "slot": a["slot"],
                    "id": a["entry"]["id"],
                    "title": a["entry"]["title"],
                    "summary": a["entry"]["summary"],
                    "link": a["entry"]["link"],
                    "source": a["entry"]["source"],
                    "pub_date": None,
                }
                for a in articles
            ]

        sheet = CustomScreamsheet(
            output_filename=str(tmp_path / "dedup.pdf"),
            components=[comp1, comp2],
            screamsheet_title="Baseball Daily",
        )
        pages = sheet.pack_components_into_pages()
        assert len(pages) == 2

        titles_comp1 = [a["title"] for a in comp1.data]
        titles_comp2 = [a["title"] for a in comp2.data]
        assert titles_comp1 == ["Phillies Sign Ace Pitcher", "Padres Acquire Slugger"]
        assert titles_comp2 == ["Yankees Extend Captain", "Dodgers Call Up Prospect"]


class TestFrenchMLBComponents:
    def test_french_mlb_articles_and_lexicon_render(self):
        content = FrenchMLBContent(
            lane_a="Les Phillies ont gagné hier soir.",
            lane_b="Les Phillies de Philadelphie ont remporté une victoire décisive.",
            lexicon={
                "vocabulary": [
                    {
                        "french_lemma": "remporter",
                        "part_of_speech": "verbe",
                        "english_translation": "to win",
                    }
                ],
                "idiomatic_phrases": [
                    {
                        "french_phrase": "coup de circuit",
                        "literal_translation": "circuit blow",
                        "contextual_meaning": "home run",
                    }
                ],
            },
        )
        art_comp = FrenchMLBArticlesComponent(content=content)
        lex_comp = FrenchMLBLexiconComponent(content=content)

        assert len(art_comp.render()) > 0
        assert "Niveau A2" in art_comp.render_markdown()
        assert len(lex_comp.render()) > 0
        assert "remporter" in lex_comp.render_markdown()

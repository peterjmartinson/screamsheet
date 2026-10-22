"""Stage 6 tests for multi-page CustomScreamsheet layout engine and formatting polish."""
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from reportlab.platypus import HRFlowable

from screamsheet.components import (
    CustomScreamsheet,
    MLBBoxScoreComponent,
    MLBGameScoresComponent,
    MLBNewsComponent,
    MLBStandingsComponent,
    NBAStandingsComponent,
    NHLStandingsComponent,
    WeatherComponent,
)


def _count_pdf_pages(pdf_path: str | Path) -> int:
    pdf_bytes = Path(pdf_path).read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))


def _make_article(idx: int) -> dict:
    return {
        "slot": f"Slot {idx}",
        "entry": {
            "id": f"https://example.com/article-{idx}",
            "title": f"Article Headline {idx}",
            "summary": f"First paragraph of article {idx}.\n\nSecond paragraph of article {idx}.",
            "link": f"https://example.com/article-{idx}",
            "source": "AP",
        },
    }


def _mock_news_component(num_articles: int = 4, max_articles: int = 4) -> MLBNewsComponent:
    provider = MagicMock()
    provider.get_articles.return_value = [_make_article(i) for i in range(1, num_articles + 1)]
    provider.sanitize_articles.side_effect = lambda x: x
    comp = MLBNewsComponent(title="MLB News", provider=provider, max_articles=max_articles)
    comp._generate_summaries = lambda articles, summarizer: [
        {
            "slot": a["slot"],
            "id": a["entry"]["id"],
            "title": a["entry"]["title"],
            "summary": a["entry"]["summary"],
            "link": a["entry"]["link"],
            "source": a["entry"]["source"],
            "pub_date": "October 21, 2026",
        }
        for a in articles
    ]
    return comp


def test_standings_plus_news_on_front_page_overflows_remaining_articles_to_page_2(
    tmp_path,
    mlb_standings_df,
):
    """1 Standings + 4-article News: Page 1 gets Standings + Articles 1-2; Page 2 gets Articles 3-4."""
    standings_provider = MagicMock()
    standings_provider.get_standings.return_value = mlb_standings_df
    standings = MLBStandingsComponent(provider=standings_provider)
    news = _mock_news_component(num_articles=5, max_articles=4)

    out_pdf = tmp_path / "standings_and_news.pdf"
    sheet = CustomScreamsheet(
        output_filename=str(out_pdf),
        components=[standings, news],
        screamsheet_title="Morning Baseball Digest",
        date=datetime(2026, 10, 21),
    )

    pages = sheet.pack_components_into_pages()
    assert len(pages) == 2
    assert len(pages[0]) == 2  # Standings + News Unit 1 (Articles 1 & 2)
    assert pages[0][0] is standings
    assert [a["title"] for a in pages[0][1].data] == ["Article Headline 1", "Article Headline 2"]

    assert len(pages[1]) == 1  # News Unit 2 (Articles 3 & 4)
    assert [a["title"] for a in pages[1][0].data] == ["Article Headline 3", "Article Headline 4"]

    # Check inter-component HRFlowable divider between Standings and News on Page 1
    chrome_flowables = sheet._render_component_with_chrome(pages[0][1], is_first_on_page=False)
    assert any(isinstance(f, HRFlowable) for f in chrome_flowables)

    sheet.generate()
    assert _count_pdf_pages(out_pdf) == 2


def test_weather_scores_and_one_standings_on_front_two_standings_on_back(
    tmp_path,
    mlb_standings_df,
    nhl_standings_df,
):
    """Weather + GameScores + 1 Standings fit on Page 1; 2 more Standings fit on Page 2."""
    weather_provider = MagicMock()
    weather_provider.location_name = "Bryn Mawr, PA"
    weather_provider.get_5_day_forecast.return_value = [
        {"day": "Wed", "max_temp": 68, "min_temp": 50, "description": "Clear", "icon_url": "/no/icon.png"}
    ]
    weather = WeatherComponent(provider=weather_provider, date=datetime(2026, 10, 21))

    scores_provider = MagicMock()
    scores_provider.get_game_scores.return_value = [
        {"away_team": "New York Mets", "away_score": 2, "home_team": "Philadelphia Phillies", "home_score": 6, "status": "Final"}
    ]
    scores = MLBGameScoresComponent(provider=scores_provider, favorite_teams=[(143, "Phillies")])

    mlb_p = MagicMock()
    mlb_p.get_standings.return_value = mlb_standings_df
    mlb_standings = MLBStandingsComponent(provider=mlb_p)

    nhl_p = MagicMock()
    nhl_p.get_standings.return_value = nhl_standings_df
    nhl_standings = NHLStandingsComponent(provider=nhl_p)

    nba_p = MagicMock()
    nba_p.get_standings.return_value = pd.DataFrame(
        [
            {"conference": "East", "team": "Boston Celtics", "wins": 50, "losses": 15, "pct": 0.769},
            {"conference": "West", "team": "Denver Nuggets", "wins": 47, "losses": 18, "pct": 0.723},
        ]
    )
    nba_standings = NBAStandingsComponent(provider=nba_p)

    out_pdf = tmp_path / "weather_scores_standings.pdf"
    sheet = CustomScreamsheet(
        output_filename=str(out_pdf),
        components=[weather, scores, mlb_standings, nhl_standings, nba_standings],
        screamsheet_title="Philly Sports & Weather",
        date=datetime(2026, 10, 21),
    )

    pages = sheet.pack_components_into_pages()
    assert len(pages) == 2
    assert pages[0] == [weather, scores, mlb_standings]
    assert pages[1] == [nhl_standings, nba_standings]

    sheet.generate()
    assert _count_pdf_pages(out_pdf) == 2


def test_full_page_box_score_isolates_on_its_own_page(
    tmp_path,
    mlb_standings_df,
):
    """A full_page_only component (BoxScoreComponent) starts on a fresh page and prevents subsequent components from sharing its page."""
    mlb_p = MagicMock()
    mlb_p.get_standings.return_value = mlb_standings_df
    standings_1 = MLBStandingsComponent(provider=mlb_p)
    standings_2 = MLBStandingsComponent(provider=mlb_p, title="NL Standings Copy")

    box_provider = MagicMock()
    box_provider.has_recent_game.return_value = True
    box_provider.get_box_score.return_value = {
        "away_team": "Mets",
        "home_team": "Phillies",
        "away_batting": [["Lindor", "4", "0", "1", "0", "0", "1"]],
        "home_batting": [["Harper", "4", "2", "2", "3", "1", "0"]],
        "away_pitching": [["Severino", "6.0", "6", "3", "3", "2", "5"]],
        "home_pitching": [["Wheeler", "7.0", "3", "0", "0", "1", "9"]],
        "away_Innings": [0, 0, 0, 0, 0, 0, 0, 0, 0],
        "home_Innings": [1, 0, 2, 0, 0, 0, 0, 0, "X"],
        "away_runs": 0,
        "home_runs": 3,
        "away_hits": 3,
        "home_hits": 6,
        "away_errors": 1,
        "home_errors": 0,
    }
    box_provider.get_game_summary.return_value = "Zack Wheeler pitched seven scoreless innings."
    box = MLBBoxScoreComponent(
        provider=box_provider,
        favorite_teams=[(143, "Philadelphia Phillies")],
        date=datetime(2026, 10, 21),
    )

    out_pdf = tmp_path / "full_page_isolation.pdf"
    sheet = CustomScreamsheet(
        output_filename=str(out_pdf),
        components=[standings_1, box, standings_2],
        screamsheet_title="Phillies Extra",
        date=datetime(2026, 10, 21),
    )

    pages = sheet.pack_components_into_pages()
    assert len(pages) == 3
    assert pages[0] == [standings_1]
    assert pages[1] == [box]
    assert pages[2] == [standings_2]

    sheet.generate()
    assert _count_pdf_pages(out_pdf) == 3

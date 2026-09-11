"""Tests for NFL screamsheet rendering and strategy integration."""
from datetime import datetime
import os
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from screamsheet.sports.nfl import NFLScreamsheet
from screamsheet.sports.nfl_router import NFLDayStrategy


@pytest.fixture
def mock_nfl_provider():
    provider = MagicMock()
    provider.current_week = {
        "SeasonName": "Regular Season",
        "SeasonValue": 2,
        "WeekName": "Week 1",
        "WeekDetail": "Sep 5-9",
        "WeekValue": 1
    }
    provider.get_game_scores.return_value = [
        {
            "gameId": "101",
            "gameDate": "2024-09-08",
            "away_team": "Pittsburgh Steelers",
            "away_score": "18",
            "home_team": "Atlanta Falcons",
            "home_score": "10",
            "status": "STATUS_FINAL"
        }
    ]
    provider.get_standings.return_value = pd.DataFrame([
        {
            "conference": "AFC",
            "team": "Pittsburgh Steelers",
            "wins": 1,
            "losses": 0,
            "ties": 0,
            "winPercent": 1.0,
            "pointDifferential": 8,
            "divisionWinPercent": 1.0
        },
        {
            "conference": "NFC",
            "team": "Atlanta Falcons",
            "wins": 0,
            "losses": 1,
            "ties": 0,
            "winPercent": 0.0,
            "pointDifferential": -8,
            "divisionWinPercent": 0.0
        }
    ])
    provider.get_game_summary.return_value = (
        "The Steelers defeated the Falcons 18-10 in a defensive showdown with **Chris Boswell** kicking six field goals.\n\n"
        "Atlanta struggled to find offensive rhythm against a fierce defense.\n\n"
        "3 Key Takeaways:\n"
        "• **Chris Boswell:** Kicks six field goals.\n"
        "• **Turnovers:** Defense forces three turnovers.\n"
        "• **Road Victory:** Pittsburgh secures season-opening victory."
    )
    provider.get_box_score.return_value = {
        "away_team": "Pittsburgh Steelers",
        "away_abbrev": "PIT",
        "away_score": 18,
        "away_linescores": ["6", "3", "3", "6"],
        "home_team": "Atlanta Falcons",
        "home_abbrev": "ATL",
        "home_score": 10,
        "home_linescores": ["0", "10", "0", "0"],
        "quarter_labels": ["1", "2", "3", "4"],
        "team_stats": [
            {"stat": "Total Yards", "away": "270", "home": "226"},
            {"stat": "Net Passing Yards", "away": "133", "home": "137"},
            {"stat": "Rushing Yards", "away": "137", "home": "89"},
            {"stat": "Turnovers", "away": "0", "home": "3"},
            {"stat": "Third Down Efficiency", "away": "8-17", "home": "2-9"},
            {"stat": "Time Of Possession", "away": "35:36", "home": "24:24"},
        ],
        "top_performers": [
            {"category": "PASS (PIT)", "player": "Justin Fields", "stat": "17/23, 156 YDS"},
            {"category": "RUSH (PIT)", "player": "Najee Harris", "stat": "20 CAR, 70 YDS"},
            {"category": "PASS (ATL)", "player": "Kirk Cousins", "stat": "16/26, 155 YDS, 1 TD, 2 INT"},
        ]
    }
    provider.get_injuries.return_value = [
        {
            "athlete": "Russell Wilson",
            "position": "QB",
            "status": "Questionable",
            "injury_date": "2024-09-06",
            "description": "Calf tightness"
        }
    ]
    provider.has_game.return_value = True
    provider.get_all_teams_for_date.return_value = [(23, "Pittsburgh Steelers"), (1, "Atlanta Falcons")]
    return provider


def test_nfl_screamsheet_monday_recap(tmp_path, mock_nfl_provider):
    from screamsheet.renderers import BoxScoreSection
    pdf_path = str(tmp_path / "nfl_recap.pdf")
    monday_date = datetime(2024, 9, 9)  # Monday
    
    with patch("screamsheet.sports.nfl.NFLDataProvider", return_value=mock_nfl_provider):
        sheet = NFLScreamsheet(
            output_filename=pdf_path,
            favorite_teams=[(23, "Pittsburgh Steelers")],
            date=monday_date,
        )
        assert sheet.strategy == NFLDayStrategy.RECAP
        sections = sheet.build_sections()
        assert len(sections) >= 3
        assert any(isinstance(s, BoxScoreSection) for s in sections)
        
        sheet.generate()
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_nfl_screamsheet_preseason(tmp_path, mock_nfl_provider):
    pdf_path = str(tmp_path / "nfl_preseason.pdf")
    august_date = datetime(2024, 8, 17)  # Saturday in preseason
    
    mock_nfl_provider._get_current_week.return_value = {
        "SeasonName": "Preseason",
        "SeasonValue": 1,
        "WeekName": "Preseason Week 2",
        "WeekDetail": "Aug 15-19",
        "WeekValue": 2
    }
    
    with patch("screamsheet.sports.nfl.NFLDataProvider", return_value=mock_nfl_provider):
        sheet = NFLScreamsheet(
            output_filename=pdf_path,
            favorite_teams=[(23, "Pittsburgh Steelers")],
            date=august_date,
        )
        assert sheet.strategy == NFLDayStrategy.WEEKEND_PREP
        sections = sheet.build_sections()
        assert len(sections) >= 2
        
        sheet.generate()
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_nfl_screamsheet_postseason_superbowl(tmp_path, mock_nfl_provider):
    pdf_path = str(tmp_path / "nfl_superbowl.pdf")
    superbowl_date = datetime(2025, 2, 9)  # Super Bowl Sunday
    
    mock_nfl_provider._get_current_week.return_value = {
        "SeasonName": "Postseason",
        "SeasonValue": 3,
        "WeekName": "Super Bowl",
        "WeekDetail": "Feb 9",
        "WeekValue": 5
    }
    
    with patch("screamsheet.sports.nfl.NFLDataProvider", return_value=mock_nfl_provider):
        sheet = NFLScreamsheet(
            output_filename=pdf_path,
            favorite_teams=[(23, "Pittsburgh Steelers")],
            date=superbowl_date,
        )
        assert sheet.strategy == NFLDayStrategy.GAMEDAY_CARD
        sections = sheet.build_sections()
        assert len(sections) >= 2
        
        sheet.generate()
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0



def test_nfl_screamsheet_tuesday_injuries(tmp_path, mock_nfl_provider):
    pdf_path = str(tmp_path / "nfl_tuesday.pdf")
    tuesday_date = datetime(2024, 9, 10)  # Tuesday
    
    with patch("screamsheet.sports.nfl.NFLDataProvider", return_value=mock_nfl_provider):
        sheet = NFLScreamsheet(
            output_filename=pdf_path,
            favorite_teams=[(23, "Pittsburgh Steelers")],
            date=tuesday_date,
        )
        assert sheet.strategy == NFLDayStrategy.STANDINGS_AND_INJURIES
        sections = sheet.build_sections()
        assert len(sections) >= 2
        
        sheet.generate()
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_nfl_screamsheet_non_game_day_with_news(tmp_path, mock_nfl_provider):
    pdf_path = str(tmp_path / "nfl_wednesday_news.pdf")
    wednesday_date = datetime(2024, 9, 11)  # Wednesday (no games played)
    
    mock_nfl_provider.get_all_teams_for_date.return_value = []
    mock_nfl_provider.has_game.return_value = False

    mock_news_provider = MagicMock()
    mock_news_provider.get_articles.return_value = [
        {
            "slot": "Section 1",
            "entry": {
                "title": "Star QB returns to practice",
                "summary": "Full practice participation on Wednesday.",
                "link": "https://espn.com/story/1",
                "source": "ESPN"
            }
        }
    ]
    mock_news_provider.sanitize_articles.side_effect = lambda arts: arts

    with patch("screamsheet.sports.nfl.NFLDataProvider", return_value=mock_nfl_provider), \
         patch("screamsheet.sports.nfl.NFLNewsProvider", return_value=mock_news_provider):
        sheet = NFLScreamsheet(
            output_filename=pdf_path,
            favorite_teams=[(23, "Pittsburgh Steelers")],
            date=wednesday_date,
        )
        sections = sheet.build_sections()
        # Wednesday Film Room builds Standings & Power Metrics + Practice & Roster Notes + Film Room & League Intel
        section_titles = [s.title for s in sections]
        assert any("Standings" in t for t in section_titles)
        assert any("Notes" in t or "Injury" in t for t in section_titles)
        assert any("News" in t or "Intel" in t for t in section_titles)

        sheet.generate()
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_box_score_section_renders_nfl(mock_nfl_provider):
    from screamsheet.renderers import BoxScoreSection
    section = BoxScoreSection(
        title="Pittsburgh Steelers Box Score",
        provider=mock_nfl_provider,
        team_id=23,
        date=datetime(2024, 9, 8),
    )
    elements = section.render()
    assert len(elements) == 1
    # Check that summary flowables inside two-column layout have multiple paragraphs/bullets
    two_col_table = elements[0]
    summary_frame = two_col_table._cellvalues[0][0]
    # Summary frame content should have distinct paragraphs and bullet items
    assert len(summary_frame._content) >= 3
    summary_texts = [f.text for f in summary_frame._content if hasattr(f, "text")]
    for st in summary_texts:
        assert "**" not in st
        assert "•" not in st
        assert "&bull;" not in st
    assert any("<b>Chris Boswell:</b>" in st for st in summary_texts)

    # Check right column elements (tables and legend)
    right_col = two_col_table._cellvalues[0][1]
    legend_texts = [p.text for p in right_col if hasattr(p, "text")]
    assert any("PASS = Passing" in t for t in legend_texts)
    assert any("RUSH = Rushing" in t for t in legend_texts)
    assert any("REC = Receiving" in t for t in legend_texts)
    assert any("YDS = Yards" in t for t in legend_texts)
    assert any("TD = Touchdowns" in t for t in legend_texts)
    assert any("CAR = Carries" in t for t in legend_texts)
    assert any("INT = Interceptions" in t for t in legend_texts)
    # Ensure TOT, TO, TOP are not in the legend
    assert not any("TOT =" in t for t in legend_texts)
    assert not any("TO =" in t for t in legend_texts)
    assert not any("TOP =" in t for t in legend_texts)

    md = section.render_markdown()
    assert "Linescore" in md
    assert "Team Comparison" in md
    assert "Top Performers" in md
    assert "Pittsburgh Steelers" in md
    assert "Justin Fields" in md
    assert "Third Down Efficiency" in md
    assert "Time Of Possession" in md


def test_box_score_section_renders_run_on_takeaways(mock_nfl_provider):
    from screamsheet.renderers import BoxScoreSection
    run_on_text = (
        "San Francisco commanded the line of scrimmage throughout Sunday's matchup.\n\n"
        "3 Key Takeaways: Purdy's Efficiency: Brock Purdy delivered an effective performance, "
        "completing 25 of 34 passes for 205 yards and three touchdowns, offsetting his lone interception. "
        "His deep strike in the second quarter shifted momentum. Turnover Battle: The 49ers won "
        "the turnover differential 2-1, with Matthew Stafford's interception proving costly for "
        "the Rams' anemic offense. Balanced Attack: San Francisco showcased a well-rounded offensive "
        "effort, accumulating 174 rushing yards and 205 passing yards, demonstrating control."
    )
    mock_nfl_provider.get_game_summary.return_value = run_on_text
    section = BoxScoreSection(
        title="San Francisco 49ers Box Score",
        provider=mock_nfl_provider,
        team_id=25,
        date=datetime(2024, 9, 8),
    )
    elements = section.render()
    assert len(elements) == 1
    two_col_table = elements[0]
    summary_frame = two_col_table._cellvalues[0][0]
    summary_texts = [f.text for f in summary_frame._content if hasattr(f, "text")]
    
    # Verify header is present
    assert any("<b>3 Key Takeaways:</b>" in t for t in summary_texts)
    # Verify each takeaway is an individual flowable with bold lead-in
    assert any("<b>Purdy's Efficiency:</b>" in t for t in summary_texts)
    assert any("<b>Turnover Battle:</b>" in t for t in summary_texts)
    assert any("<b>Balanced Attack:</b>" in t for t in summary_texts)
    # Ensure no raw markdown or bullets leaked
    for st in summary_texts:
        assert "**" not in st
        assert "•" not in st


def test_nfl_data_provider_get_box_score():
    from screamsheet.providers.nfl_provider import NFLDataProvider
    provider = NFLDataProvider()

    mock_summary_payload = {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Pittsburgh Steelers", "abbreviation": "PIT"},
                            "score": 18,
                            "linescores": [{"value": 6}, {"value": 3}, {"value": 3}, {"value": 6}]
                        },
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Atlanta Falcons", "abbreviation": "ATL"},
                            "score": 10,
                            "linescores": [{"value": 0}, {"value": 10}, {"value": 0}, {"value": 0}]
                        }
                    ]
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"displayName": "Pittsburgh Steelers"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "270"}
                    ]
                }
            ]
        },
        "leaders": []
    }

    with patch.object(provider, "_find_event_id", return_value="401547412"), \
         patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_summary_payload
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        box = provider.get_box_score(team_id=23, date=datetime(2024, 9, 8))
        assert box is not None
        assert box["away_team"] == "Pittsburgh Steelers"
        assert box["away_score"] == 18


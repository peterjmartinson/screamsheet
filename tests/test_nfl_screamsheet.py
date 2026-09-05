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
    provider.get_game_summary.return_value = "The Steelers defeated the Falcons 18-10 in a defensive showdown."
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
        assert len(sections) >= 2
        
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

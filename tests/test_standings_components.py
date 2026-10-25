"""Unit tests for Stage 2: StandingsComponent hierarchy and CustomScreamsheet page packing."""
from datetime import datetime
from typing import Any, List, Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest
from reportlab.platypus import Paragraph, Table

from screamsheet.components import (
    ComponentLayoutSpec,
    ComponentRegistry,
    CustomScreamsheet,
    MLBStandingsComponent,
    NBAStandingsComponent,
    NFLStandingsComponent,
    NHLStandingsComponent,
    ScreamsheetComponent,
    StandingsComponent,
    WorldCupStandingsComponent,
)


def _mock_provider_with_df(df: pd.DataFrame) -> MagicMock:
    p = MagicMock()
    p.get_standings.return_value = df
    return p


@pytest.fixture
def nba_standings_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"conference": "East", "team": "Boston Celtics", "wins": 50, "losses": 15, "pct": 0.769},
            {"conference": "East", "team": "Philadelphia 76ers", "wins": 42, "losses": 23, "pct": 0.646},
            {"conference": "West", "team": "Oklahoma City Thunder", "wins": 49, "losses": 16, "pct": 0.754},
            {"conference": "West", "team": "Denver Nuggets", "wins": 47, "losses": 18, "pct": 0.723},
        ]
    )


@pytest.fixture
def nfl_standings_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"conference": "AFC", "team": "Kansas City Chiefs", "wins": 11, "losses": 2, "ties": 0, "winPercent": 0.846},
            {"conference": "AFC", "team": "Buffalo Bills", "wins": 10, "losses": 3, "ties": 0, "winPercent": 0.769},
            {"conference": "NFC", "team": "Philadelphia Eagles", "wins": 11, "losses": 2, "ties": 0, "winPercent": 0.846},
            {"conference": "NFC", "team": "Green Bay Packers", "wins": 9, "losses": 4, "ties": 0, "winPercent": 0.692},
        ]
    )


@pytest.fixture
def worldcup_groups() -> List[List[dict]]:
    return [
        [
            {"group": "Group A", "team": {"name": "USA"}, "points": 7, "goalsDiff": 4},
            {"group": "Group A", "team": {"name": "Mexico"}, "points": 5, "goalsDiff": 2},
        ],
        [
            {"group": "Group B", "team": {"name": "Argentina"}, "points": 9, "goalsDiff": 6},
            {"group": "Group B", "team": {"name": "France"}, "points": 6, "goalsDiff": 3},
        ],
    ]


class TestStandingsComponentRegistry:
    @pytest.mark.parametrize(
        "key,expected_cls",
        [
            ("mlb_standings", MLBStandingsComponent),
            ("nhl_standings", NHLStandingsComponent),
            ("nba_standings", NBAStandingsComponent),
            ("nfl_standings", NFLStandingsComponent),
            ("worldcup_standings", WorldCupStandingsComponent),
        ],
    )
    def test_all_standings_components_registered(self, key, expected_cls):
        assert ComponentRegistry.is_registered(key)
        assert ComponentRegistry.get(key) is expected_cls


class TestStandingsComponentsRendering:
    def test_mlb_standings_component_renders_table(self, mlb_standings_df):
        comp = MLBStandingsComponent(provider=_mock_provider_with_df(mlb_standings_df))
        flowables = comp.render()
        assert len(flowables) == 1
        assert isinstance(flowables[0], Table)
        assert comp.has_content() is True
        assert "Philadelphia Phillies" in comp.render_markdown()

    def test_nhl_standings_component_renders_table(self, nhl_standings_df):
        comp = NHLStandingsComponent(provider=_mock_provider_with_df(nhl_standings_df))
        flowables = comp.render()
        assert len(flowables) == 1
        assert isinstance(flowables[0], Table)
        assert comp.has_content() is True

    def test_nba_standings_component_renders_table(self, nba_standings_df):
        comp = NBAStandingsComponent(provider=_mock_provider_with_df(nba_standings_df))
        flowables = comp.render()
        assert len(flowables) == 1
        assert isinstance(flowables[0], Table)
        assert "Philadelphia 76ers" in comp.render_markdown()

    def test_nfl_standings_component_renders_table(self, nfl_standings_df):
        comp = NFLStandingsComponent(provider=_mock_provider_with_df(nfl_standings_df))
        flowables = comp.render()
        assert len(flowables) == 1
        assert isinstance(flowables[0], Table)
        assert "Philadelphia Eagles" in comp.render_markdown()

    def test_worldcup_standings_component_renders_tables(self, worldcup_groups):
        p = MagicMock()
        p.get_standings.return_value = worldcup_groups
        comp = WorldCupStandingsComponent(provider=p)
        flowables = comp.render()
        assert len(flowables) > 0
        assert any(isinstance(f, Table) for f in flowables)

    def test_empty_standings_returns_empty_and_has_no_content(self):
        comp = MLBStandingsComponent(provider=_mock_provider_with_df(pd.DataFrame()))
        assert comp.has_content() is False
        assert comp.render() == []


class _CompactBannerComponent(ScreamsheetComponent):
    """Lightweight component (like scores or weather) that fits on Page 1 alongside 1 standings chart."""

    DEFAULT_LAYOUT_SPEC = ComponentLayoutSpec(weight=0.25, component_family="scores")

    def __init__(self, title: str = "Scores Banner") -> None:
        super().__init__(title=title)

    def fetch_data(self) -> None:
        self.data = ["PHI 5, NYM 2"]

    def render(self, styles: Optional[Any] = None, max_width: Optional[float] = None) -> List[Any]:
        if self.data is None:
            self.fetch_data()
        return [Paragraph("PHI 5, NYM 2", self.styles["Normal"] if hasattr(self, "styles") else CustomScreamsheet("x.pdf").styles["Normal"])]


class TestCustomScreamsheetStandingsPacking:
    def test_only_one_standings_allowed_on_front_page_two_on_back(
        self,
        tmp_path,
        mlb_standings_df,
        nhl_standings_df,
        nba_standings_df,
        nfl_standings_df,
    ):
        """Page 1 allows at most 1 standings chart; Page 2 fits 2 standings; Page 3 gets the 4th."""
        mlb = MLBStandingsComponent(provider=_mock_provider_with_df(mlb_standings_df))
        nhl = NHLStandingsComponent(provider=_mock_provider_with_df(nhl_standings_df))
        nba = NBAStandingsComponent(provider=_mock_provider_with_df(nba_standings_df))
        nfl = NFLStandingsComponent(provider=_mock_provider_with_df(nfl_standings_df))

        pdf_path = tmp_path / "four_standings.pdf"
        sheet = CustomScreamsheet(
            output_filename=str(pdf_path),
            components=[mlb, nhl, nba, nfl],
            screamsheet_title="Daily Pro Sports Standings",
            date=datetime(2026, 10, 21),
        )
        assert sheet.get_title() == "Daily Pro Sports Standings"

        pages = sheet.pack_components_into_pages()
        assert len(pages) == 3
        assert pages[0] == [mlb]          # Max 1 standings on front page
        assert pages[1] == [nhl, nba]     # 2 standings on back page
        assert pages[2] == [nfl]          # Remaining standings on page 3

        out = sheet.generate()
        assert pdf_path.exists()
        assert out == str(pdf_path)

    def test_front_page_fits_scores_plus_one_standings_and_back_page_fits_two_standings(
        self,
        tmp_path,
        mlb_standings_df,
        nhl_standings_df,
        nba_standings_df,
    ):
        """Scores + 1 standings fit on Page 1 (front), and 2 standings fit on Page 2 (back)."""
        scores = _CompactBannerComponent(title="MLB Game Scores")
        mlb = MLBStandingsComponent(provider=_mock_provider_with_df(mlb_standings_df))
        nhl = NHLStandingsComponent(provider=_mock_provider_with_df(nhl_standings_df))
        nba = NBAStandingsComponent(provider=_mock_provider_with_df(nba_standings_df))

        pdf_path = tmp_path / "two_page_custom.pdf"
        sheet = CustomScreamsheet(
            output_filename=str(pdf_path),
            components=[scores, mlb, nhl, nba],
            date=datetime(2026, 10, 21),
        )
        assert sheet.get_title() == "Screamsheet"  # default when screamsheet_title not specified

        pages = sheet.pack_components_into_pages()
        assert len(pages) == 2
        assert pages[0] == [scores, mlb]  # Page 1: scores + 1 standings
        assert pages[1] == [nhl, nba]     # Page 2: 2 standings

        sheet.generate()
        assert pdf_path.exists()

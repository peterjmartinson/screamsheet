"""Base GameScoresComponent and playoff series badge helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent


def _determine_series_badge(
    away_abbrev: str,
    home_abbrev: str,
    away_score: int,
    home_score: int,
    series_status: Dict[str, Any],
) -> Tuple[str, str]:
    """Return (badge_row, badge_text) for a playoff game.

    badge_row is "away" or "home".
    badge_text is one of "(leads X-Y)", "(won X-Y)", or "(tied X-X)".
    """
    top_abbrev = series_status["top_seed_abbrev"]
    top_wins = series_status["top_seed_wins"]
    bottom_abbrev = series_status["bottom_seed_abbrev"]
    bottom_wins = series_status["bottom_seed_wins"]
    needed = series_status["needed_to_win"]

    # Determine series winner/leader
    if top_wins == needed:
        leader_abbrev = top_abbrev
        badge_text = f"(won {top_wins}-{bottom_wins})"
    elif bottom_wins == needed:
        leader_abbrev = bottom_abbrev
        badge_text = f"(won {bottom_wins}-{top_wins})"
    elif top_wins > bottom_wins:
        leader_abbrev = top_abbrev
        badge_text = f"(leads {top_wins}-{bottom_wins})"
    elif bottom_wins > top_wins:
        leader_abbrev = bottom_abbrev
        badge_text = f"(leads {bottom_wins}-{top_wins})"
    else:
        # Tied — badge goes on game winner's row
        leader_abbrev = away_abbrev if away_score > home_score else home_abbrev
        badge_text = f"(tied {top_wins}-{bottom_wins})"

    badge_row = "away" if leader_abbrev == away_abbrev else "home"
    return badge_row, badge_text


class GameScoresComponent(ScreamsheetComponent):
    """Base component for displaying game scores in a 3-column grid."""

    layout_spec = ComponentLayoutSpec(
        weight=0.25,
        full_page_only=False,
        max_on_front_page=None,
        max_per_page=None,
        component_family="game_scores",
    )

    def __init__(
        self,
        title: str = "Game Scores",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        upcoming_games: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            upcoming_games=upcoming_games,
            **kwargs,
        )
        self.upcoming_games = upcoming_games or []
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

    def fetch_data(self) -> None:
        """Fetch game scores from the provider."""
        if self.provider is None:
            self.data = []
            return
        self.data = self.provider.get_game_scores(self.date)

    def render(self) -> List[Any]:
        """Render the game scores component."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        elements = []

        # Organize games into three columns
        scores_left: List[Any] = []
        scores_center: List[Any] = []
        scores_right: List[Any] = []

        for i, game in enumerate(self.data):
            if game.get("away_score") is not None and game.get("home_score") is not None:
                series_status: Optional[Dict[str, Any]] = game.get("series_status")

                if series_status:
                    badge_row, badge_text = _determine_series_badge(
                        away_abbrev=game.get("away_abbrev", ""),
                        home_abbrev=game.get("home_abbrev", ""),
                        away_score=game["away_score"],
                        home_score=game["home_score"],
                        series_status=series_status,
                    )
                    away_badge = badge_text if badge_row == "away" else ""
                    home_badge = badge_text if badge_row == "home" else ""
                    table_data: List[Any] = [
                        [game["away_team"], str(game["away_score"]), away_badge],
                        [f"@{game['home_team']}", str(game["home_score"]), home_badge],
                    ]
                    col_widths = [75, 20, 55]
                else:
                    table_data = [
                        [game["away_team"], str(game["away_score"])],
                        [f"@{game['home_team']}", str(game["home_score"])],
                    ]
                    col_widths = [130, 25]
                table_style = TableStyle(
                    [
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("LEFTPADDING", (0, 0), (0, -1), 0),
                        ("RIGHTPADDING", (0, 0), (0, -1), 0),
                    ]
                )
                game_table = Table(table_data, colWidths=col_widths)
                game_table.setStyle(table_style)

                if i % 3 == 0:
                    scores_left.append(game_table)
                    scores_left.append(Spacer(1, 10))
                elif i % 3 == 1:
                    scores_center.append(game_table)
                    scores_center.append(Spacer(1, 10))
                else:
                    scores_right.append(game_table)
                    scores_right.append(Spacer(1, 10))

        available_width = 540
        col_width = available_width / 3

        scores_table = Table(
            [[scores_left, scores_center, scores_right]],
            colWidths=[col_width, col_width, col_width],
            hAlign="LEFT",
        )

        elements.append(scores_table)

        if self.upcoming_games:
            elements.append(Spacer(1, 6))
            note_style = ParagraphStyle(
                name="UpcomingGameNote",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                textColor=colors.HexColor("#1a1a1a"),
                alignment=TA_CENTER,
            )
            for ug in self.upcoming_games:
                clean_ug = ug.replace("<b>", "").replace("</b>", "")
                elements.append(Paragraph(f"Tonight: {clean_ug}", note_style))

        return elements

    def render_markdown(self) -> str:
        """Render all game scores into a clean Markdown table."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return "No games scheduled."

        lines = [
            "| Away | Score | Home | Score | Status |",
            "| :--- | :---: | :--- | :---: | :--- |",
        ]
        for g in self.data:
            away = g.get("away_team", "")
            away_score = g.get("away_score", "-")
            home = g.get("home_team", "")
            home_score = g.get("home_score", "-")
            status = g.get("status", "Final")
            lines.append(f"| {away} | {away_score} | {home} | {home_score} | {status} |")

        if self.upcoming_games:
            lines.append("\n**Tonight:** " + ", ".join(self.upcoming_games))

        return "\n".join(lines)

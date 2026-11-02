"""International soccer game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ...providers.soccer_provider import SoccerDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("soccer_game_scores")
class SoccerGameScoresComponent(GameScoresComponent):
    """Renders multi-league soccer scores grouped with clean league headings."""

    component_type = "soccer_game_scores"

    def __init__(
        self,
        title: str = "Yesterday's Scores",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date, **kwargs)
        styles = getSampleStyleSheet()
        self.league_header_style = ParagraphStyle(
            "SoccerLeagueHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=4,
            spaceAfter=2,
        )

    def create_default_provider(self) -> DataProvider:
        return SoccerDataProvider()

    def render(self) -> List[Any]:
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        elements: List[Any] = []
        games_by_league: Dict[str, List[Dict[str, Any]]] = {}
        for game in self.data:
            lname = game.get("league_name", "International")
            games_by_league.setdefault(lname, []).append(game)

        scores_left: List[Any] = []
        scores_center: List[Any] = []
        scores_right: List[Any] = []

        flat_index = 0
        for lname, games in games_by_league.items():
            header_p = Paragraph(f"<b>{lname.upper()}</b>", self.league_header_style)
            # Add header to current bucket
            target_bucket = flat_index % 3
            if target_bucket == 0:
                scores_left.append(header_p)
            elif target_bucket == 1:
                scores_center.append(header_p)
            else:
                scores_right.append(header_p)

            for g in games:
                home = g.get("home_team", "Home")
                away = g.get("away_team", "Away")
                h_score = str(g.get("home_score", 0))
                a_score = str(g.get("away_score", 0))
                status = str(g.get("status_short", "FT"))

                # Formatting table
                table_data = [
                    [away, a_score, status],
                    [home, h_score, ""],
                ]
                col_widths = [110, 25, 35]
                t = Table(table_data, colWidths=col_widths)
                t.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                            ("ALIGN", (2, 0), (2, -1), "CENTER"),
                            ("TEXTCOLOR", (2, 0), (2, -1), colors.dimgrey),
                            ("FONTSIZE", (2, 0), (2, -1), 7),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                        ]
                    )
                )

                b = flat_index % 3
                if b == 0:
                    scores_left.extend([t, Spacer(1, 6)])
                elif b == 1:
                    scores_center.extend([t, Spacer(1, 6)])
                else:
                    scores_right.extend([t, Spacer(1, 6)])
                flat_index += 1

        available_width = 540
        col_w = available_width / 3
        container = Table(
            [[scores_left, scores_center, scores_right]],
            colWidths=[col_w, col_w, col_w],
            hAlign="LEFT",
        )
        container.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(container)
        return elements

"""MLB All-Star game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ...providers.mlb_provider import MLBDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("mlb_all_star_game_scores")
class MLBAllStarGameScoresComponent(GameScoresComponent):
    """Component for displaying the MLB All-Star Game score on the front page."""

    component_type = "mlb_all_star_game_scores"

    def __init__(
        self,
        title: str = "All-Star Game Score",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date, **kwargs)
        self.page_slot = "front"
        self.subtitle_style = ParagraphStyle(
            name="AllStarScoreSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

    def create_default_provider(self) -> DataProvider:
        return MLBDataProvider()

    def fetch_data(self) -> None:
        """Fetch All-Star game scores from the provider."""
        if self.provider is None:
            self.data = []
            return
        self.data = self.provider.get_allstar_game_scores(self.date)

    def render(self) -> List[Any]:
        """Render the All-Star game score section."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return [Paragraph("<b>No completed All-Star Game found for this date.</b>", self.subtitle_style)]

        elements = []
        for game in self.data:
            if game.get("away_score") is not None and game.get("home_score") is not None:
                table_data = [
                    [game["away_team"], str(game["away_score"])],
                    [game["home_team"], str(game["home_score"])],
                ]
                col_widths = [220, 50]
                table_style = TableStyle(
                    [
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 12),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ]
                )
                game_table = Table(table_data, colWidths=col_widths, hAlign="CENTER")
                game_table.setStyle(table_style)
                elements.append(game_table)
                elements.append(Spacer(1, 14))

        return elements

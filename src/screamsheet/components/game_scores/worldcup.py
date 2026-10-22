"""World Cup game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from reportlab.platypus import Spacer, Table, TableStyle

from ...base import DataProvider
from ...providers.worldcup26_provider import WorldCup26Provider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("worldcup_game_scores")
class WorldCupGameScoresComponent(GameScoresComponent):
    """Renders World Cup fixtures without the '@' home indicator."""

    component_type = "worldcup_game_scores"

    def __init__(
        self,
        title: str = "World Cup Scores",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date, **kwargs)

    def create_default_provider(self) -> DataProvider:
        return WorldCup26Provider()

    def render(self) -> List[Any]:
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        scores_left: List[Any] = []
        scores_center: List[Any] = []
        scores_right: List[Any] = []

        for i, game in enumerate(self.data):
            away_score = game.get("away_score")
            home_score = game.get("home_score")
            if away_score is None or home_score is None:
                continue

            away_team = game.get("away_team") or ""
            home_team = game.get("home_team") or ""
            status = game.get("status_short") or ""

            if status == "PEN":
                away_pen = game.get("away_penalty")
                home_pen = game.get("home_penalty")
                away_label = f"{away_team} ({away_pen})" if away_pen is not None else away_team
                home_label = f"{home_team} ({home_pen})" if home_pen is not None else home_team
            else:
                away_label = away_team
                home_label = home_team  # No '@' for World Cup

            table_data: List[Any] = [
                [away_label, str(away_score)],
                [home_label, str(home_score)],
            ]
            col_widths = [120, 30]
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

            bucket = i % 3
            if bucket == 0:
                scores_left.extend([game_table, Spacer(1, 10)])
            elif bucket == 1:
                scores_center.extend([game_table, Spacer(1, 10)])
            else:
                scores_right.extend([game_table, Spacer(1, 10)])

        available_width = 540
        col_width = available_width / 3
        scores_table = Table(
            [[scores_left, scores_center, scores_right]],
            colWidths=[col_width, col_width, col_width],
            hAlign="LEFT",
        )
        return [scores_table]

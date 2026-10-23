"""NBA Standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.nba_provider import NBADataProvider
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("nba_standings")
class NBAStandingsComponent(StandingsComponent):
    """Renders NBA standings by Eastern and Western conference."""

    component_key = "nba_standings"

    def __init__(
        self,
        title: str = "NBA Standings",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        page_slot: str = "front",
        layout_spec: Optional[ComponentLayoutSpec] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            page_slot=page_slot,
            layout_spec=layout_spec,
            **kwargs,
        )

    def _create_provider(self) -> DataProvider:
        return NBADataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []
        return [self.render_nba_table(self.data, self.centered_style)]

    @staticmethod
    def render_nba_table(standings_df: pd.DataFrame, centered_style: Any) -> Table:
        """Render NBA standings by conference."""
        eastern = standings_df[standings_df["conference"] == "East"]
        western = standings_df[standings_df["conference"] == "West"]

        grid_data: List[List[Any]] = [
            [
                Paragraph("<b>Eastern Conference</b>", centered_style),
                Paragraph("<b>Western Conference</b>", centered_style),
            ],
        ]

        row_list: List[Any] = []
        for conf_data in [eastern, western]:
            if not conf_data.empty:
                header = ["Team", "W", "L", "%"]
                table_data = (
                    [header]
                    + conf_data[["team", "wins", "losses", "pct"]].values.tolist()
                )

                table_style = TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ]
                )
                standings_table = Table(table_data, colWidths=[150, 30, 30, 40])
                standings_table.setStyle(table_style)
                row_list.append(standings_table)
            else:
                row_list.append("")

        grid_data.append(row_list)

        master_style = TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )

        final_table = Table(grid_data, colWidths=[270, 270])
        final_table.setStyle(master_style)
        return final_table

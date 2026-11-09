"""MLS Standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.mls_provider import MLSDataProvider
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("mls_standings")
class MLSStandingsComponent(StandingsComponent):
    """Renders Major League Soccer standings by Eastern and Western conferences."""

    component_key = "mls_standings"

    def __init__(
        self,
        title: str = "MLS Standings",
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
        return MLSDataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []
        return [self.render_mls_table(self.data, self.centered_style)]

    @staticmethod
    def render_mls_table(standings_df: pd.DataFrame, centered_style: Any) -> Table:
        """Render MLS standings by conference in a clean 2-column layout."""
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
                header = ["Team", "W", "D", "L", "GD", "PTS"]
                formatted_rows: List[List[Any]] = []
                for _, row in conf_data.iterrows():
                    team_str = str(row.get("team", ""))
                    # Shorten longer club names if needed
                    team_str = (
                        team_str.replace(" Major League Soccer", "")
                        .replace("Football Club", "FC")
                    )
                    w = str(row.get("w", 0))
                    d = str(row.get("d", 0))
                    l = str(row.get("l", 0))
                    gd = str(row.get("gd", "0"))
                    pts = str(row.get("pts", 0))
                    formatted_rows.append([team_str, w, d, l, gd, pts])

                table_data = [header] + formatted_rows

                table_style = TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                    ]
                )
                standings_table = Table(table_data, colWidths=[125, 25, 25, 25, 30, 35])
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

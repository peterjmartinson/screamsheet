"""NFL Standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.nfl_provider import NFLDataProvider
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("nfl_standings")
class NFLStandingsComponent(StandingsComponent):
    """Renders NFL standings by AFC and NFC conference."""

    component_key = "nfl_standings"

    def __init__(
        self,
        title: str = "NFL Standings",
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
        return NFLDataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []
        return [self.render_nfl_table(self.data, self.centered_style)]

    @staticmethod
    def render_nfl_table(standings_df: pd.DataFrame, centered_style: Any) -> Table:
        """Render NFL standings by AFC/NFC conference."""
        afc = standings_df[standings_df["conference"] == "AFC"]
        nfc = standings_df[standings_df["conference"] == "NFC"]

        grid_data: List[List[Any]] = [
            [
                Paragraph("<b>AFC</b>", centered_style),
                Paragraph("<b>NFC</b>", centered_style),
            ],
        ]

        row_list: List[Any] = []
        for conf_data in [afc, nfc]:
            if not conf_data.empty:
                header = ["Team", "W", "L", "T", "%"]
                formatted_data = []
                for _, row in conf_data.iterrows():
                    formatted_data.append(
                        [
                            row["team"],
                            int(row["wins"]),
                            int(row["losses"]),
                            int(row["ties"]),
                            f"{row['winPercent']:.3f}",
                        ]
                    )
                table_data = [header] + formatted_data

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
                standings_table = Table(table_data, colWidths=[150, 25, 25, 25, 40])
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

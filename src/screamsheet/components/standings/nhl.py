"""NHL Standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.nhl_provider import NHLDataProvider
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("nhl_standings")
class NHLStandingsComponent(StandingsComponent):
    """Renders NHL standings by Eastern and Western conference and division."""

    component_key = "nhl_standings"

    def __init__(
        self,
        title: str = "NHL Standings",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        page_slot: str = "front",
        layout_spec: Optional[ComponentLayoutSpec] = None,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            page_slot=page_slot,
            layout_spec=layout_spec,
        )

    def _create_provider(self) -> DataProvider:
        return NHLDataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []
        return [self.render_nhl_table(self.data, self.centered_style)]

    @staticmethod
    def render_nhl_table(standings_df: pd.DataFrame, centered_style: Any) -> Table:
        """Render NHL standings by conference and division."""
        eastern_conf = standings_df[standings_df["conference"] == "Eastern"]
        western_conf = standings_df[standings_df["conference"] == "Western"]

        grid_data: List[List[Any]] = [
            [
                Paragraph("<b>EASTERN CONFERENCE</b>", centered_style),
                Paragraph("<b>WESTERN CONFERENCE</b>", centered_style),
            ],
        ]

        division_layout = [
            {"east": "Atlantic", "west": "Central"},
            {"east": "Metropolitan", "west": "Pacific"},
        ]

        inner_col_widths = [130, 20, 20, 25, 25]

        for row_info in division_layout:
            east_div_name = row_info["east"]
            west_div_name = row_info["west"]

            row_list: List[Any] = []

            for conf_data, div_name in [
                (eastern_conf, east_div_name),
                (western_conf, west_div_name),
            ]:
                group = conf_data[conf_data["division"] == div_name]

                if not group.empty:
                    inner_header = [f"{div_name} Division", "W", "L", "OTL", "P"]
                    table_data = (
                        [inner_header]
                        + group[["team", "W", "L", "OTL", "P"]].values.tolist()
                    )

                    table_style = TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("ALIGN", (0, 0), (0, -1), "LEFT"),
                            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ]
                    )

                    inner_table = Table(table_data, colWidths=inner_col_widths)
                    inner_table.setStyle(table_style)
                    row_list.append(inner_table)
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

"""MLB Standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.mlb_provider import MLBDataProvider
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("mlb_standings")
class MLBStandingsComponent(StandingsComponent):
    """Renders MLB standings in American League / National League division format."""

    component_key = "mlb_standings"

    def __init__(
        self,
        title: str = "MLB Standings",
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
        return MLBDataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []
        return [self.render_mlb_table(self.data, self.centered_style)]

    @staticmethod
    def render_mlb_table(standings_df: pd.DataFrame, centered_style: Any) -> Table:
        """Render MLB standings in AL/NL East/Central/West format."""
        al_divisions = standings_df[
            standings_df["division"].str.contains("American League")
        ]
        nl_divisions = standings_df[
            standings_df["division"].str.contains("National League")
        ]
        divisions_order = ["East", "Central", "West"]

        grid_data: List[List[Any]] = [
            [
                "",
                Paragraph("<b>American League</b>", centered_style),
                Paragraph("<b>National League</b>", centered_style),
            ],
        ]

        for geography in divisions_order:
            row_list: List[Any] = [Paragraph(f"<b>{geography}</b>", centered_style)]
            al_group = al_divisions[al_divisions["division"].str.contains(geography)]
            nl_group = nl_divisions[nl_divisions["division"].str.contains(geography)]

            for group in [al_group, nl_group]:
                if not group.empty:
                    header = ["Team", "W", "L", "%"]
                    table_data = (
                        [header]
                        + group[["team", "wins", "losses", "pct"]].values.tolist()
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
                    standings_table = Table(table_data, colWidths=[150, 30, 30, 30])
                    standings_table.setStyle(table_style)
                    row_list.append(standings_table)
                else:
                    row_list.append("")
            grid_data.append(row_list)

        master_table_style = TableStyle(
            [
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
            ]
        )
        final_standings_table = Table(grid_data, colWidths=[60, 250, 250])
        final_standings_table.setStyle(master_table_style)
        return final_standings_table

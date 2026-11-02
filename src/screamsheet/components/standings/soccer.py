"""International soccer standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.soccer_provider import SoccerDataProvider, AL_NASSR_TEAM_ID
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("soccer_standings")
class SoccerStandingsComponent(StandingsComponent):
    """Renders dual mini-standings tables (e.g. Saudi Pro League & Premier League)."""

    component_key = "soccer_standings"

    def __init__(
        self,
        title: str = "League Standings",
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
        self.table_header_style = ParagraphStyle(
            "SoccerTableTitle",
            parent=self.styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=9,
            spaceAfter=4,
            alignment=TA_CENTER,
        )

    def _create_provider(self) -> DataProvider:
        return SoccerDataProvider()

    def _build_standings_flowables(self) -> List[Any]:
        if not self.data or not isinstance(self.data, dict):
            return []

        sub_tables: List[Any] = []
        for league_name, df in self.data.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            header_p = Paragraph(f"<b>{league_name}</b>", self.table_header_style)
            # Take top 6 rows
            subset = df.head(6)

            header = ["#", "Club", "MP", "GD", "Pts", "Form"]
            rows: List[List[str]] = [header]
            al_nassr_row_idx = -1

            for idx, r in enumerate(subset.iterrows()):
                row_data = r[1]
                t_name = str(row_data.get("team", ""))
                tid = row_data.get("team_id")
                if tid == AL_NASSR_TEAM_ID or "nassr" in t_name.lower():
                    al_nassr_row_idx = idx + 1  # 1-indexed because header is row 0

                rows.append([
                    str(row_data.get("rank", idx + 1)),
                    t_name,
                    str(row_data.get("mp", 0)),
                    str(row_data.get("gd", 0)),
                    str(row_data.get("pts", 0)),
                    str(row_data.get("form", "")[:5]),
                ])

            table_style_commands = [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]

            # Highlight Al-Nassr with Gold Accent
            if al_nassr_row_idx != -1:
                table_style_commands.append(
                    ("BACKGROUND", (0, al_nassr_row_idx), (-1, al_nassr_row_idx), colors.HexColor("#FEF08A"))
                )
                table_style_commands.append(
                    ("FONTNAME", (0, al_nassr_row_idx), (-1, al_nassr_row_idx), "Helvetica-Bold")
                )

            t = Table(rows, colWidths=[18, 110, 24, 26, 26, 44])
            t.setStyle(TableStyle(table_style_commands))
            sub_tables.append([header_p, t])

        if not sub_tables:
            return []

        # If we have 2 tables, render side by side
        if len(sub_tables) >= 2:
            left_col = sub_tables[0]
            right_col = sub_tables[1]
            master = Table([[left_col, right_col]], colWidths=[265, 265])
            master.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            return [master]

        return [item for sub in sub_tables for item in sub]

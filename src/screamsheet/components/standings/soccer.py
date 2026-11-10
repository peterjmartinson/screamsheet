"""International soccer standings component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base.data_provider import DataProvider
from ...providers.soccer_provider import (
    AL_NASSR_TEAM_ID,
    SoccerDataProvider,
    resolve_team_list,
)
from ..base import ComponentLayoutSpec
from ..registry import ComponentRegistry
from .base import StandingsComponent


@ComponentRegistry.register("soccer_standings")
class SoccerStandingsComponent(StandingsComponent):
    """Renders dual mini-standings tables (e.g. Saudi Pro League & Premier League, or custom leagues)."""

    component_key = "soccer_standings"

    def __init__(
        self,
        title: str = "League Standings",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        page_slot: str = "front",
        layout_spec: Optional[ComponentLayoutSpec] = None,
        favorite_teams: Optional[List[Any]] = None,
        standings: Optional[List[Any]] = None,
        standings_leagues: Optional[List[Any]] = None,
        leagues: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._init_favorite_teams = favorite_teams
        self._init_standings = standings_leagues if standings_leagues is not None else standings
        self._init_leagues = leagues
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            page_slot=page_slot,
            layout_spec=layout_spec,
            **kwargs,
        )
        self.favorite_teams = (
            resolve_team_list(favorite_teams)
            if favorite_teams is not None
            else getattr(self.provider, "favorite_teams", [(AL_NASSR_TEAM_ID, "Al-Nassr")])
        )
        self.table_header_style = ParagraphStyle(
            "SoccerTableTitle",
            parent=self.styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            textColor=colors.black,
            spaceAfter=4,
            alignment=TA_CENTER,
        )

    def _create_provider(self) -> DataProvider:
        return SoccerDataProvider(
            favorite_teams=self._init_favorite_teams,
            standings=self._init_standings,
            leagues=self._init_leagues,
        )

    def _build_standings_flowables(self) -> List[Any]:
        if not self.data or not isinstance(self.data, dict):
            return []

        fav_ids = {tid for tid, _ in self.favorite_teams}
        fav_names = {tname.lower() for _, tname in self.favorite_teams}

        sub_tables: List[Any] = []
        for league_name, df in self.data.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            header_p = Paragraph(f"<b>{league_name}</b>", self.table_header_style)
            # Take top 6 rows
            subset = df.head(6)

            header = ["#", "Club", "MP", "GD", "Pts", "Form"]
            rows: List[List[str]] = [header]
            highlight_row_indices: List[int] = []

            for idx, r in enumerate(subset.iterrows()):
                row_data = r[1]
                t_name = str(row_data.get("team", ""))
                tid = row_data.get("team_id")
                if (
                    (tid is not None and tid in fav_ids)
                    or any(fn in t_name.lower() for fn in fav_names)
                ):
                    highlight_row_indices.append(idx + 1)

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
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]

            for r_idx in highlight_row_indices:
                table_style_commands.append(
                    ("FONTNAME", (0, r_idx), (-1, r_idx), "Helvetica-Bold")
                )

            t = Table(rows, colWidths=[18, 108, 24, 26, 26, 48])
            t.setStyle(TableStyle(table_style_commands))
            sub_tables.append([header_p, t])

        if not sub_tables:
            return []

        elements: List[Any] = []

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
            elements.append(master)
        else:
            elements.extend([item for sub in sub_tables for item in sub])

        # Legend explaining columns and form guide (definitions formatted as a clean list)
        legend_style = ParagraphStyle(
            "SoccerStandingsLegend",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.black,
            alignment=TA_LEFT,
        )
        legend_lines = [
            "<b>STANDINGS & FORM DEFINITIONS:</b>",
            "• <b>MP:</b> Matches Played in the current league season",
            "• <b>GD:</b> Goal Difference (Total Goals Scored minus Goals Conceded)",
            "• <b>Pts:</b> Points (Win = 3, Draw = 1, Loss = 0)",
            "• <b>Form:</b> Recent 5 league fixtures, from oldest to newest (W = Win, D = Draw, L = Loss)",
        ]
        legend_html = "<br/>".join(legend_lines)
        legend_table = Table([[Paragraph(legend_html, legend_style)]], colWidths=[530])
        legend_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(Spacer(1, 4))
        elements.append(legend_table)

        return elements

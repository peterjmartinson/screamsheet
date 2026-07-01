"""World Cup group standings renderer."""
from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section, DataProvider


class WorldCupStandingsSection(Section):
    """Renders FIFA World Cup group-stage standings as a grid of group tables."""

    COLS_PER_ROW = 4  # groups shown side-by-side per row on the page

    def __init__(self, title: str, provider: DataProvider) -> None:
        super().__init__(title)
        self.provider = provider
        styles = getSampleStyleSheet()
        self.group_header_style = ParagraphStyle(
            "WCGroupHeader",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=9,
            spaceAfter=2,
            alignment=TA_CENTER,
        )

    def fetch_data(self) -> None:
        self.data = self.provider.get_standings()

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()
        if not self.data:
            return []

        groups: List[List[Dict[str, Any]]] = self.data  # list of group arrays
        group_tables: List[Any] = []

        for group_rows in groups:
            if not group_rows:
                continue
            group_name: str = group_rows[0].get("group") or "Group"
            header = Paragraph(f"<b>{group_name}</b>", self.group_header_style)

            # Table: Team | Pts | GD
            table_data: List[List[Any]] = [["Team", "Pts", "GD"]]
            for row in group_rows:
                team_name: str = (row.get("team") or {}).get("name") or ""
                pts: Any = row.get("points", "-")
                gd: Any = row.get("goalsDiff", "-")
                table_data.append([team_name, str(pts), str(gd)])

            t = Table(
                table_data,
                colWidths=[80, 25, 25],
            )
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            group_tables.append([header, t])

        if not group_tables:
            return []

        # Arrange groups into rows of COLS_PER_ROW
        elements: List[Any] = []
        n = self.COLS_PER_ROW
        for chunk_start in range(0, len(group_tables), n):
            chunk = group_tables[chunk_start : chunk_start + n]
            # Pad to full width so table columns are even
            while len(chunk) < n:
                chunk.append(["", ""])

            col_contents_header = [item[0] for item in chunk]
            col_contents_table = [item[1] for item in chunk]

            page_width = 540  # usable width (letter minus margins)
            col_w = page_width / n

            header_row = Table([col_contents_header], colWidths=[col_w] * n)
            header_row.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            elements.append(header_row)

            body_row = Table([col_contents_table], colWidths=[col_w] * n)
            body_row.setStyle(
                TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
            )
            elements.append(body_row)
            elements.append(Spacer(1, 12))

        return elements

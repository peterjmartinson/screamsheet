"""NFL Injury Report component."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import DataProvider
from ..providers.nfl_provider import NFLDataProvider
from .base import ComponentLayoutSpec, ScreamsheetComponent
from .registry import ComponentRegistry


@ComponentRegistry.register("nfl_injuries")
class NFLInjuriesComponent(ScreamsheetComponent):
    """Component for displaying NFL team injuries."""

    component_type = "nfl_injuries"
    layout_spec = ComponentLayoutSpec(
        weight=0.35,
        full_page_only=False,
        max_on_front_page=None,
        max_per_page=None,
        component_family="injuries",
    )

    def __init__(
        self,
        title: str = "NFL Injury Report",
        provider: Optional[DataProvider] = None,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            team_id=team_id,
            favorite_teams=favorite_teams,
            **kwargs,
        )
        if team_id is None and favorite_teams:
            self.team_id = favorite_teams[0][0]
            self.team_name = team_name or favorite_teams[0][1]
            if self.title == "NFL Injury Report":
                self.title = f"{favorite_teams[0][1]} Injury Report"
        else:
            self.team_id = team_id or 0
            self.team_name = team_name or (favorite_teams[0][1] if favorite_teams else "")
        self.styles = getSampleStyleSheet()

        self.title_style = ParagraphStyle(
            name="InjuriesSectionTitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        self.cell_style = ParagraphStyle(
            name="InjuriesCell",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )
        self.bold_cell_style = ParagraphStyle(
            name="InjuriesBoldCell",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
        )

    def create_default_provider(self) -> DataProvider:
        return NFLDataProvider()

    def fetch_data(self) -> None:
        """Fetch injuries from provider if available."""
        if self.provider is not None and hasattr(self.provider, "get_injuries") and self.team_id:
            try:
                self.data = self.provider.get_injuries(self.team_id, team_name=self.team_name)
            except TypeError:
                self.data = self.provider.get_injuries(self.team_id)
        else:
            self.data = []

    def render(self) -> List[Any]:
        """Render the injuries section."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return []

        elements = []
        elements.append(Paragraph(f"<b>{self.title}</b>", self.title_style))

        header = ["Player", "Pos", "Status", "Details"]
        table_rows = [[Paragraph(f"<b>{h}</b>", self.bold_cell_style) for h in header]]

        for item in self.data[:8]:
            table_rows.append(
                [
                    Paragraph(item.get("athlete", "Unknown"), self.bold_cell_style),
                    Paragraph(item.get("position", ""), self.cell_style),
                    Paragraph(item.get("status", ""), self.cell_style),
                    Paragraph(item.get("description", "")[:60], self.cell_style),
                ]
            )

        table = Table(table_rows, colWidths=[130, 40, 90, 280])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 10))
        return elements

    def render_markdown(self) -> str:
        """Render NFL injury report in Markdown table format."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return ""

        lines = [
            "| Player | Position | Status | Details |",
            "| :--- | :---: | :---: | :--- |",
        ]
        for item in self.data[:12]:
            player = item.get("athlete", "Unknown")
            pos = item.get("position", "")
            status = item.get("status", "")
            desc = item.get("description", "")
            lines.append(f"| {player} | {pos} | {status} | {desc} |")

        return "\n".join(lines)

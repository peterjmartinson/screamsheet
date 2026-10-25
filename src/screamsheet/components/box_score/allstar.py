"""MLB All-Star game summary and side-by-side box score components."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ...providers.mlb_provider import MLBDataProvider
from ..registry import ComponentRegistry
from .base import BoxScoreComponent, GameSummaryComponent


@ComponentRegistry.register("mlb_all_star_game_summary")
class MLBAllStarGameSummaryComponent(GameSummaryComponent):
    """Component for displaying the ~500-word regular All-Star game summary on the front page."""

    component_type = "mlb_all_star_game_summary"

    def __init__(
        self,
        title: str = "All-Star Game Summary",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date, **kwargs)
        self.page_slot = "front"
        self.summary_text_style = ParagraphStyle(
            name="AllStarSummaryText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14.5,
            spaceAfter=10,
            alignment=TA_LEFT,
        )

    def create_default_provider(self) -> DataProvider:
        return MLBDataProvider()

    def fetch_data(self) -> None:
        """Fetch game summary from the provider."""
        if self.provider is None:
            self.data = None
            return
        self.data = self.provider.get_allstar_game_summary(self.date)

    def render(self) -> List[Any]:
        """Render the All-Star game summary section."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return []

        elements = []
        paragraphs = [p.strip() for p in self.data.split("\n\n") if p.strip()]
        for p in paragraphs:
            elements.append(Paragraph(p, self.summary_text_style))

        return elements

    def render_markdown(self) -> str:
        """Render All-Star game summary in Markdown."""
        if self.data is None:
            self.fetch_data()
        return self.data.strip() if self.data else ""


@ComponentRegistry.register("mlb_all_star_box_score")
class MLBAllStarBoxScoreComponent(BoxScoreComponent):
    """Side-by-side box scores on the back page (AL left, NL right)."""

    component_type = "mlb_all_star_box_score"

    def __init__(
        self,
        title: str = "All-Star Game Box Scores",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date, **kwargs)
        self.page_slot = "back"
        self.team_header_style = ParagraphStyle(
            name="AllStarTeamHeader",
            parent=self.styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=11,
            spaceAfter=6,
            alignment=TA_CENTER,
        )

    def create_default_provider(self) -> DataProvider:
        return MLBDataProvider()

    def fetch_data(self) -> None:
        """Fetch side-by-side AL and NL box scores from the provider."""
        if self.provider is None:
            self.data = None
            return
        self.data = self.provider.get_allstar_box_scores(self.date)

    def render(self) -> List[Any]:
        """Render side-by-side two-column box scores."""
        if not self.data:
            self.fetch_data()

        if not self.data or not isinstance(self.data, dict):
            return []

        al_column = self._render_team_column(self.data.get("AL", {}))
        nl_column = self._render_team_column(self.data.get("NL", {}))

        two_column_table = Table(
            [[al_column, nl_column]],
            colWidths=["50%", "50%"],
            rowHeights=[None],
        )
        two_column_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 8),
                    ("LEFTPADDING", (1, 0), (1, 0), 8),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        return [two_column_table]

    def render_markdown(self) -> str:
        """Render AL and NL box scores sequentially in single-column Markdown."""
        if not self.data:
            self.fetch_data()

        if not self.data or not isinstance(self.data, dict):
            return ""

        lines = []
        for league_key in ["AL", "NL"]:
            tdata = self.data.get(league_key, {})
            if not tdata:
                continue
            team_name = tdata.get("team_name", f"{league_key} All-Stars")
            lines.append(f"### {team_name}\n")

            batting = tdata.get("batting_stats", [])
            if batting:
                lines.append("#### Batting")
                lines.append("| Batter | AB | R | H | HR | RBI | BB | SO |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
                for p in batting:
                    lines.append(
                        f"| {p.get('name')} | {p.get('AB', 0)} | {p.get('R', 0)} | {p.get('H', 0)} | {p.get('HR', 0)} | {p.get('RBI', 0)} | {p.get('BB', 0)} | {p.get('SO', 0)} |"
                    )
                lines.append("")

            pitching = tdata.get("pitching_stats", [])
            if pitching:
                lines.append("#### Pitching")
                lines.append("| Pitcher | IP | H | R | ER | BB | SO |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
                for p in pitching:
                    lines.append(
                        f"| {p.get('name')} | {p.get('IP', '0.0')} | {p.get('H', 0)} | {p.get('R', 0)} | {p.get('ER', 0)} | {p.get('BB', 0)} | {p.get('SO', 0)} |"
                    )
                lines.append("")

        return "\n".join(lines)

    def _render_team_column(self, team_data: dict) -> List[Any]:
        """Render batting and pitching tables for a single league column."""
        if not team_data:
            return [Paragraph("No box score data", self.styles["Normal"])]

        elements = []
        team_name = team_data.get("team_name", "Unknown Team")
        elements.append(Paragraph(f"<b>{team_name}</b>", self.team_header_style))

        batting_stats = team_data.get("batting_stats", [])
        if batting_stats:
            hitting_header = ["Batter", "AB", "R", "H", "HR", "RBI", "BB", "SO"]
            hitting_data = [hitting_header]
            for p in batting_stats:
                hitting_data.append(
                    [
                        p["name"],
                        str(p.get("AB", 0)),
                        str(p.get("R", 0)),
                        str(p.get("H", 0)),
                        str(p.get("HR", 0)),
                        str(p.get("RBI", 0)),
                        str(p.get("BB", 0)),
                        str(p.get("SO", 0)),
                    ]
                )

            hitting_style = TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
            hitting_table = Table(hitting_data, colWidths=[100, 22, 22, 22, 22, 22, 22, 22])
            hitting_table.setStyle(hitting_style)
            elements.append(hitting_table)
            elements.append(Spacer(1, 8))

        pitching_stats = team_data.get("pitching_stats", [])
        if pitching_stats:
            pitching_header = ["Pitcher", "IP", "H", "R", "ER", "BB", "SO"]
            pitching_data = [pitching_header]
            for p in pitching_stats:
                pitching_data.append(
                    [
                        p["name"],
                        str(p.get("IP", "0.0")),
                        str(p.get("H", 0)),
                        str(p.get("R", 0)),
                        str(p.get("ER", 0)),
                        str(p.get("BB", 0)),
                        str(p.get("SO", 0)),
                    ]
                )

            pitching_style = TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
            pitching_table = Table(pitching_data, colWidths=[110, 24, 24, 24, 24, 24, 24])
            pitching_table.setStyle(pitching_style)
            elements.append(pitching_table)

        return elements

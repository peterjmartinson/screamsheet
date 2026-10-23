"""Abstract base class for league standings components."""
from __future__ import annotations

import inspect
from abc import abstractmethod
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Table, TableStyle

from ...base.data_provider import DataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent


class StandingsComponent(ScreamsheetComponent):
    """Abstract base class for displaying league standings.

    Layout rules:
      - At most 1 standings component fits on Page 1 (front page).
      - Up to 2 standings components fit on Page 2+ (back and subsequent pages).
    """

    DEFAULT_LAYOUT_SPEC = ComponentLayoutSpec(
        weight=0.48,
        component_family="standings",
        max_on_front_page=1,
        max_per_page=2,
        renders_own_header=False,
        preferred_top_divider=True,
    )

    def __init__(
        self,
        title: str = "Standings",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        page_slot: str = "front",
        layout_spec: Optional[ComponentLayoutSpec] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, page_slot=page_slot, layout_spec=layout_spec, **kwargs)
        self.provider: Optional[DataProvider] = provider or self._create_provider()
        self.date: Optional[datetime] = date
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

        self.centered_style = ParagraphStyle(
            name="CenteredText",
            alignment=TA_CENTER,
        )

    def _create_provider(self) -> Optional[DataProvider]:
        """Instantiate the default sport provider when none is passed explicitly."""
        return None

    def fetch_data(self) -> None:
        """Fetch standings from the provider."""
        if self.provider is None:
            self.data = None
            return
        sig = inspect.signature(self.provider.get_standings)
        if "date" in sig.parameters and self.date is not None:
            self.data = self.provider.get_standings(self.date)
        else:
            self.data = self.provider.get_standings()

    def has_content(self) -> bool:
        """Return True if non-empty standings data is available."""
        if self.data is None:
            self.fetch_data()
        if self.data is None:
            return False
        if isinstance(self.data, pd.DataFrame):
            return not self.data.empty
        if isinstance(self.data, (list, dict)):
            return len(self.data) > 0
        return True

    @abstractmethod
    def _build_standings_flowables(self) -> List[Any]:
        """Build sport-specific ReportLab flowables from ``self.data``."""
        pass

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        """Render the standings component into ReportLab flowables."""
        if self.data is None:
            self.fetch_data()

        if self.data is None or (
            isinstance(self.data, pd.DataFrame) and self.data.empty
        ):
            return []
        if isinstance(self.data, (list, dict)) and len(self.data) == 0:
            return []

        return self._build_standings_flowables()

    def render_markdown(self) -> str:
        """Render league standings as Markdown tables."""
        if self.data is None:
            self.fetch_data()

        if self.data is None or (
            isinstance(self.data, pd.DataFrame) and self.data.empty
        ):
            return "No standings data available."

        if isinstance(self.data, pd.DataFrame):
            try:
                df = self.data.copy()
                cols_to_drop = [c for c in ["team_id", "id"] if c in df.columns]
                if cols_to_drop:
                    df = df.drop(columns=cols_to_drop)
                return df.to_markdown(index=False)
            except Exception:
                lines = ["| " + " | ".join(str(c) for c in self.data.columns) + " |"]
                lines.append("| " + " | ".join([":---"] * len(self.data.columns)) + " |")
                for _, row in self.data.iterrows():
                    lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
                return "\n".join(lines)

        return super().render_markdown()

    @staticmethod
    def build_generic_table(standings_df: pd.DataFrame) -> Table:
        """Render a generic DataFrame into a basic bordered ReportLab Table."""
        header = list(standings_df.columns)
        table_data = [header] + standings_df.values.tolist()

        table_style = TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )

        standings_table = Table(table_data)
        standings_table.setStyle(table_style)
        return standings_table

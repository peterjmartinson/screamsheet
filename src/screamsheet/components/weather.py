"""Weather forecast component."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Table, TableStyle

from ..base import DataProvider
from ..providers.weather_provider import WeatherProvider
from .base import ComponentLayoutSpec, ScreamsheetComponent
from .registry import ComponentRegistry

logger = logging.getLogger(__name__)


@ComponentRegistry.register("weather")
class WeatherComponent(ScreamsheetComponent):
    """Self-contained component for displaying a 5-day NWS weather forecast."""

    component_type = "weather"
    layout_spec = ComponentLayoutSpec(
        weight=0.18,
        component_family="weather",
        max_on_front_page=1,
        max_per_page=1,
        renders_own_header=False,
        preferred_top_divider=False,
    )

    def __init__(
        self,
        title: str = "Weather Report",
        date: Optional[datetime] = None,
        lat: float = 40.02,
        lon: float = -75.34,
        location_name: str = "Bryn Mawr, PA",
        show_description: bool = True,
        provider: Optional[DataProvider] = None,
        **kwargs: Any,
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self.show_description = show_description
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            lat=lat,
            lon=lon,
            location_name=location_name,
            show_description=show_description,
            **kwargs,
        )

        base = getSampleStyleSheet()
        self._day_style = ParagraphStyle(
            "WDay",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            alignment=1,
        )
        self._temp_style = ParagraphStyle(
            "WTemp",
            parent=base["Normal"],
            fontSize=8,
            alignment=1,
            spaceAfter=2,
        )
        self._desc_style = ParagraphStyle(
            "WDesc",
            parent=base["Normal"],
            fontSize=7,
            alignment=1,
        )
        self._location_style = ParagraphStyle(
            "WLocation",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            alignment=TA_CENTER,
            spaceAfter=4,
        )

    def create_default_provider(self) -> DataProvider:
        return WeatherProvider(lat=self.lat, lon=self.lon, location_name=self.location_name)

    def fetch_data(self) -> None:
        """Fetch forecast data from NWS via WeatherProvider."""
        try:
            self.data = self.provider.get_5_day_forecast()
        except Exception as e:
            logger.error("Error getting weather report: %s", e)
            self.data = []

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        """Build and return the ReportLab Table flowable for the forecast."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        location_para = Paragraph(self.provider.location_name, self._location_style)
        return [location_para, self._build_flowable(self.data)]

    def render_markdown(self) -> str:
        """Render 5-day weather forecast in Markdown table format."""
        if not self.data:
            self.fetch_data()
        if not self.data:
            return "No weather forecast available."

        lines = [
            f"**Location:** {self.provider.location_name}\n",
            "| Day | High / Low | Forecast |",
            "| :--- | :---: | :--- |",
        ]
        for d in self.data:
            day = d.get("day", "").upper()
            temps = f"{d.get('max_temp', '')}° / {d.get('min_temp', '')}°F"
            desc = d.get("description", "")
            lines.append(f"| {day} | {temps} | {desc} |")

        return "\n".join(lines)

    def _build_flowable(self, forecast_data: list) -> Table:
        """Assemble the 5-column weather Table."""
        col_width = 1.3 * inch

        day_row = [
            Paragraph(d["day"].upper(), self._day_style)
            for d in forecast_data
        ]

        icon_temp_row = []
        for d in forecast_data:
            icon_path = d["icon_url"]
            if os.path.exists(icon_path):
                icon_cell = Image(
                    icon_path,
                    width=0.45 * inch,
                    height=0.45 * inch,
                    kind="proportional",
                )
            else:
                icon_cell = Paragraph("[-]", self._desc_style)

            temp_para = Paragraph(
                f"<b>{d['max_temp']}°</b> / {d['min_temp']}°F",
                self._temp_style,
            )

            nested = Table(
                [[icon_cell], [temp_para]],
                colWidths=[col_width - 0.2 * inch],
                rowHeights=[0.5 * inch, 0.2 * inch],
            )
            nested.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (0, 0), "BOTTOM"),
                        ("VALIGN", (0, 1), (0, 1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            icon_temp_row.append(nested)

        table_data = [day_row, icon_temp_row]
        if self.show_description:
            desc_row = [
                Paragraph(d["description"], self._desc_style)
                for d in forecast_data
            ]
            table_data.append(desc_row)

        table = Table(
            table_data,
            colWidths=[col_width] * len(forecast_data),
        )
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                    ("LINEBEFORE", (1, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

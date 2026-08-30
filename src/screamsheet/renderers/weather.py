"""Weather section renderer."""
import logging
import os
from datetime import datetime
from typing import List, Any, Optional

from reportlab.platypus import Paragraph, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import inch

from ..base import Section
from ..providers.weather_provider import WeatherProvider

logger = logging.getLogger(__name__)


class WeatherSection(Section):
    """
    Section for displaying a 5-day NWS weather forecast.

    Args:
        title:         Section title label.
        date:          Target date for the screamsheet.
        lat:           Latitude of the forecast location.
        lon:           Longitude of the forecast location.
        location_name: Human-readable location label.
    """

    def __init__(
        self,
        title: str,
        date: datetime,
        lat: float = 40.02,
        lon: float = -75.34,
        location_name: str = 'Bryn Mawr, PA',
        show_description: bool = True,
    ):
        super().__init__(title)
        self.date = date
        self.show_description = show_description
        self.provider = WeatherProvider(lat=lat, lon=lon, location_name=location_name)

        # Build styles once
        base = getSampleStyleSheet()
        self._day_style = ParagraphStyle(
            'WDay', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=10, alignment=1,
        )
        self._temp_style = ParagraphStyle(
            'WTemp', parent=base['Normal'],
            fontSize=8, alignment=1, spaceAfter=2,
        )
        self._desc_style = ParagraphStyle(
            'WDesc', parent=base['Normal'],
            fontSize=7, alignment=1,
        )
        self._location_style = ParagraphStyle(
            'WLocation', parent=base['Normal'],
            fontName='Helvetica', fontSize=9,
            alignment=TA_CENTER, spaceAfter=4,
        )

    # ------------------------------------------------------------------
    # Section protocol
    # ------------------------------------------------------------------

    def fetch_data(self):
        """Fetch forecast data from NWS via WeatherProvider."""
        try:
            self.data = self.provider.get_5_day_forecast()
        except Exception as e:
            logger.error("Error getting weather report: %s", e)
            self.data = []

    def render(self) -> List[Any]:
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
            day = d.get('day', '').upper()
            temps = f"{d.get('max_temp', '')}° / {d.get('min_temp', '')}°F"
            desc = d.get('description', '')
            lines.append(f"| {day} | {temps} | {desc} |")
        
        return "\n".join(lines)


    # ------------------------------------------------------------------
    # Flowable builder (ported from src/print_weather.py)
    # ------------------------------------------------------------------

    def _build_flowable(self, forecast_data: list) -> Table:
        """Assemble the 5-column weather Table."""
        col_width = 1.3 * inch

        # Row 1 — Day names
        day_row = [
            Paragraph(d['day'].upper(), self._day_style)
            for d in forecast_data
        ]

        # Row 2 — Icon + temperature (nested table per cell)
        icon_temp_row = []
        for d in forecast_data:
            icon_path = d['icon_url']
            if os.path.exists(icon_path):
                icon_cell = Image(
                    icon_path,
                    width=0.45 * inch,
                    height=0.45 * inch,
                    kind='proportional',
                )
            else:
                icon_cell = Paragraph('[-]', self._desc_style)

            temp_para = Paragraph(
                f"<b>{d['max_temp']}°</b> / {d['min_temp']}°F",
                self._temp_style,
            )

            nested = Table(
                [[icon_cell], [temp_para]],
                colWidths=[col_width - 0.2 * inch],
                rowHeights=[0.5 * inch, 0.2 * inch],
            )
            nested.setStyle(TableStyle([
                ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN',        (0, 0), (0,  0),  'BOTTOM'),
                ('VALIGN',        (0, 1), (0,  1),  'TOP'),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            icon_temp_row.append(nested)

        table_data = [day_row, icon_temp_row]
        if self.show_description:
            # Row 3 — Short description
            desc_row = [
                Paragraph(d['description'], self._desc_style)
                for d in forecast_data
            ]
            table_data.append(desc_row)

        table = Table(
            table_data,
            colWidths=[col_width] * len(forecast_data),
        )
        table.setStyle(TableStyle([
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('BOX',          (0, 0), (-1, -1), 0.5,  colors.black),
            ('LINEBEFORE',   (1, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND',   (0, 0), (-1,  0), colors.whitesmoke),
            ('TOPPADDING',   (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ]))
        return table

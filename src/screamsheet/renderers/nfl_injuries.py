"""NFL Injury Report section renderer."""
from typing import List, Any
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from ..base import Section, DataProvider


class NFLInjuriesSection(Section):
    """Section for displaying NFL team injuries."""

    def __init__(self, title: str, provider: DataProvider, team_id: int):
        super().__init__(title)
        self.provider = provider
        self.team_id = team_id
        self.styles = getSampleStyleSheet()

        self.title_style = ParagraphStyle(
            name="InjuriesSectionTitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT
        )
        self.cell_style = ParagraphStyle(
            name="InjuriesCell",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
        )
        self.bold_cell_style = ParagraphStyle(
            name="InjuriesBoldCell",
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
        )

    def fetch_data(self):
        """Fetch injuries from provider if available."""
        if hasattr(self.provider, "get_injuries"):
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
        table_rows = [
            [
                Paragraph(f"<b>{h}</b>", self.bold_cell_style)
                for h in header
            ]
        ]

        # Limit to top 8 entries to ensure single-page fit
        for item in self.data[:8]:
            table_rows.append([
                Paragraph(item.get("athlete", "Unknown"), self.bold_cell_style),
                Paragraph(item.get("position", ""), self.cell_style),
                Paragraph(item.get("status", ""), self.cell_style),
                Paragraph(item.get("description", "")[:60], self.cell_style),
            ])

        table = Table(table_rows, colWidths=[130, 40, 90, 280])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 10))
        return elements

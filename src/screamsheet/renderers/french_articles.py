"""Two-column French MLB article renderer (Lane A left, Lane B right)."""
from typing import Any, List
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..providers.french_mlb_content_provider import FrenchMLBContent


class FrenchArticlesSection(Section):
    """
    Front-page two-column section displaying CEFR-levelled French articles.

    Left column  — Lane A (CEFR A2, simplified)
    Right column — Lane B (CEFR B2/C1, advanced)

    The section is initialised with a pre-computed :class:`FrenchMLBContent`
    object, so ``fetch_data`` is a no-op that simply stores the reference.
    """

    page_slot: str = "front"

    def __init__(self, title: str, content: FrenchMLBContent) -> None:
        super().__init__(title)
        self._content = content
        styles = getSampleStyleSheet()
        self._header_style = ParagraphStyle(
            name="FrenchColumnHeader",
            parent=styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceBefore=4,
            spaceAfter=6,
        )
        self._body_style = ParagraphStyle(
            name="FrenchArticleBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            spaceAfter=4,
        )

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def fetch_data(self) -> None:
        self.data = self._content

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        page_width, _ = letter
        margin = 0.65 * inch
        col_width = (page_width - 2 * margin - 12) / 2  # 12pt gutter

        a2_header = Paragraph("Niveau A2", self._header_style)
        b2_header = Paragraph("Niveau B2\u2013C1", self._header_style)

        lane_a_text = _xml_escape(self._content.lane_a or "").replace("\n", "<br/>")
        lane_b_text = _xml_escape(self._content.lane_b or "").replace("\n", "<br/>")

        a2_body = Paragraph(lane_a_text, self._body_style)
        b2_body = Paragraph(lane_b_text, self._body_style)

        table_data = [
            [a2_header, b2_header],
            [a2_body, b2_body],
        ]

        table = Table(table_data, colWidths=[col_width, col_width])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        return [Spacer(1, 6), table, Spacer(1, 8)]

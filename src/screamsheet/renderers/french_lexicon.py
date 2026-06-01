"""Back-page French MLB lexicon renderer."""
from typing import Any, List
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..providers.french_mlb_content_provider import FrenchMLBContent


class FrenchLexiconSection(Section):
    """
    Back-page section displaying the vocabulary lexicon and idioms.

    Renders two blocks:

    1. **Le Lexique Essentiel** — table of uncommon words with part of speech
       and English translation.
    2. **Les Tournures de Phrase** — idioms block with literal and contextual
       meanings.

    Initialised with a pre-computed :class:`FrenchMLBContent`; ``fetch_data``
    stores the reference without any network I/O.
    """

    def __init__(self, title: str, content: FrenchMLBContent) -> None:
        super().__init__(title)
        self.page_slot = "back"
        self._content = content
        styles = getSampleStyleSheet()
        self._section_title_style = ParagraphStyle(
            name="LexiconSectionTitle",
            parent=styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=13,
            spaceBefore=12,
            spaceAfter=6,
        )
        self._table_header_style = ParagraphStyle(
            name="LexiconTableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
        )
        self._cell_style = ParagraphStyle(
            name="LexiconCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
        )
        self._idiom_label_style = ParagraphStyle(
            name="IdiomLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            spaceAfter=2,
        )
        self._idiom_detail_style = ParagraphStyle(
            name="IdiomDetail",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            leftIndent=12,
            spaceAfter=6,
        )

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def fetch_data(self) -> None:
        self.data = self._content

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        flowables: List[Any] = []
        lexicon = self._content.lexicon or {}
        vocab = lexicon.get("vocabulary", [])
        idioms = lexicon.get("idiomatic_phrases", [])

        # ------------------------------------------------------------------
        # Block 1 — Le Lexique Essentiel (vocabulary table)
        # ------------------------------------------------------------------
        flowables.append(
            Paragraph("Le Lexique Essentiel", self._section_title_style)
        )

        page_width, _ = letter
        margin = 0.65 * inch
        available_width = page_width - 2 * margin
        col_widths = [
            available_width * 0.30,
            available_width * 0.20,
            available_width * 0.50,
        ]

        header_row = [
            Paragraph("Mot", self._table_header_style),
            Paragraph("Classe", self._table_header_style),
            Paragraph("Traduction", self._table_header_style),
        ]
        rows: List[List[Any]] = [header_row]
        for entry in vocab:
            rows.append(
                [
                    Paragraph(_xml_escape(entry.get("french_lemma", "")), self._cell_style),
                    Paragraph(_xml_escape(entry.get("part_of_speech", "")), self._cell_style),
                    Paragraph(_xml_escape(entry.get("english_translation", "")), self._cell_style),
                ]
            )

        if len(rows) > 1:
            vocab_table = Table(rows, colWidths=col_widths)
            vocab_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            flowables.append(vocab_table)
        else:
            flowables.append(
                Paragraph(
                    "<i>Aucun vocabulaire disponible.</i>", self._cell_style
                )
            )

        flowables.append(Spacer(1, 16))

        # ------------------------------------------------------------------
        # Block 2 — Les Tournures de Phrase (idioms)
        # ------------------------------------------------------------------
        flowables.append(
            Paragraph("Les Tournures de Phrase", self._section_title_style)
        )

        if idioms:
            for entry in idioms:
                phrase = entry.get("french_phrase", "")
                literal = entry.get("literal_translation", "")
                contextual = entry.get("contextual_meaning", "")
                flowables.append(
                    Paragraph(f"\u00ab\u00a0{_xml_escape(phrase)}\u00a0\u00bb", self._idiom_label_style)
                )
                if literal:
                    flowables.append(
                        Paragraph(
                            f"<i>Litt\u00e9ralement\u00a0:</i> {_xml_escape(literal)}",
                            self._idiom_detail_style,
                        )
                    )
                if contextual:
                    flowables.append(
                        Paragraph(
                            f"<i>Sens\u00a0:</i> {_xml_escape(contextual)}",
                            self._idiom_detail_style,
                        )
                    )
        else:
            flowables.append(
                Paragraph(
                    "<i>Aucune tournure disponible.</i>", self._cell_style
                )
            )

        return flowables

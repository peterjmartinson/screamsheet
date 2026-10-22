"""French MLB News components (CEFR A2/B2-C1 articles + back-page lexicon)."""
from __future__ import annotations

import os
from typing import Any, List, Optional
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...providers.french_mlb_content_provider import FrenchMLBContent, FrenchMLBContentProvider
from ...providers.french_mlb_scraper_provider import FrenchMLBScraperProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry


def _fetch_french_mlb_content(
    favorite_teams: Optional[List[str]] = None,
    grok_api_key: Optional[str] = None,
) -> FrenchMLBContent:
    scraper = FrenchMLBScraperProvider(favorite_teams=favorite_teams or [])
    articles = scraper.get_articles()
    content_provider = FrenchMLBContentProvider(grok_api_key=grok_api_key or os.getenv("GROK_API_KEY"))
    return content_provider.generate(articles)


@ComponentRegistry.register("french_mlb_articles")
class FrenchMLBArticlesComponent(ScreamsheetComponent):
    """Front-page two-column component displaying CEFR-levelled French MLB articles."""

    component_type = "french_mlb_articles"
    layout_spec = ComponentLayoutSpec(
        weight=0.80,
        component_family="french_mlb_articles",
        max_on_front_page=1,
        max_per_page=1,
    )

    def __init__(
        self,
        title: str = "MLB en Français",
        content: Optional[FrenchMLBContent] = None,
        favorite_teams: Optional[List[str]] = None,
        grok_api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, page_slot="front", **kwargs)
        self._content: Optional[FrenchMLBContent] = content
        self.favorite_teams: List[str] = list(favorite_teams) if favorite_teams else []
        self._grok_api_key: Optional[str] = grok_api_key

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

    def fetch_data(self) -> None:
        if self._content is None:
            self._content = _fetch_french_mlb_content(
                favorite_teams=self.favorite_teams,
                grok_api_key=self._grok_api_key,
            )
        self.data = self._content

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        page_width, _ = letter
        margin = 0.65 * inch
        col_width = (page_width - 2 * margin - 12) / 2

        a2_header = Paragraph("Niveau A2", self._header_style)
        b2_header = Paragraph("Niveau B2\u2013C1", self._header_style)

        lane_a_text = _xml_escape((self._content.lane_a if self._content else "") or "").replace("\n", "<br/>")
        lane_b_text = _xml_escape((self._content.lane_b if self._content else "") or "").replace("\n", "<br/>")

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

    def render_markdown(self) -> str:
        """Render French MLB articles sequentially (Lane A, then Lane B)."""
        if self.data is None:
            self.fetch_data()
        lines = []
        if self._content and self._content.lane_a:
            lines.append("### Niveau A2\n\n" + self._content.lane_a.strip())
        if self._content and self._content.lane_b:
            lines.append("### Niveau B2–C1\n\n" + self._content.lane_b.strip())
        return "\n\n---\n\n".join(lines)


@ComponentRegistry.register("french_mlb_lexicon")
class FrenchMLBLexiconComponent(ScreamsheetComponent):
    """Back-page component displaying the French MLB vocabulary lexicon and idioms."""

    component_type = "french_mlb_lexicon"
    layout_spec = ComponentLayoutSpec(
        weight=0.80,
        component_family="french_mlb_lexicon",
        max_on_front_page=1,
        max_per_page=1,
    )

    def __init__(
        self,
        title: str = "Le Lexique",
        content: Optional[FrenchMLBContent] = None,
        favorite_teams: Optional[List[str]] = None,
        grok_api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title=title, page_slot="back", **kwargs)
        self._content: Optional[FrenchMLBContent] = content
        self.favorite_teams: List[str] = list(favorite_teams) if favorite_teams else []
        self._grok_api_key: Optional[str] = grok_api_key

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

    def fetch_data(self) -> None:
        if self._content is None:
            self._content = _fetch_french_mlb_content(
                favorite_teams=self.favorite_teams,
                grok_api_key=self._grok_api_key,
            )
        self.data = self._content

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        flowables: List[Any] = []
        lexicon = (self._content.lexicon if self._content else None) or {}
        vocab = lexicon.get("vocabulary", [])
        idioms = lexicon.get("idiomatic_phrases", [])

        flowables.append(Paragraph("Le Lexique Essentiel", self._section_title_style))

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
            flowables.append(Paragraph("<i>Aucun vocabulaire disponible.</i>", self._cell_style))

        flowables.append(Spacer(1, 16))
        flowables.append(Paragraph("Les Tournures de Phrase", self._section_title_style))

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
            flowables.append(Paragraph("<i>Aucune tournure disponible.</i>", self._cell_style))

        return flowables

    def render_markdown(self) -> str:
        """Render vocabulary table and idioms in Markdown."""
        if self.data is None:
            self.fetch_data()
        lexicon = (self._content.lexicon if self._content else None) or {}
        vocab = lexicon.get("vocabulary", [])
        idioms = lexicon.get("idiomatic_phrases", [])
        lines = []

        if vocab:
            lines.append("### Le Lexique Essentiel\n")
            lines.append("| Mot | Classe | Traduction |")
            lines.append("| :--- | :--- | :--- |")
            for entry in vocab:
                lines.append(
                    f"| {entry.get('french_lemma', '')} | {entry.get('part_of_speech', '')} | {entry.get('english_translation', '')} |"
                )
            lines.append("")

        if idioms:
            lines.append("### Les Tournures de Phrase\n")
            for idx, item in enumerate(idioms, 1):
                phrase = item.get("french_phrase", "")
                lit = item.get("literal_english", "")
                ctx = item.get("contextual_english", "")
                note = item.get("usage_note", "")
                lines.append(f"**{idx}. {phrase}**")
                if lit:
                    lines.append(f"* *Littéral:* {lit}")
                if ctx:
                    lines.append(f"* *Sens:* {ctx}")
                if note:
                    lines.append(f"* *Note:* {note}")
                lines.append("")

        return "\n".join(lines)

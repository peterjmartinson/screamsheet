"""Sky highlights section renderer for the Sky Tonight screamsheet.

Renders data-driven bullets from the SkyDataProvider plus an optional
LLM-generated playful astronomy/astrology bullet at the end.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, List, cast

from reportlab.lib.colors import black, HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..llm.summarizers import SkyNightSummarizer
from ..llm.config import DEFAULT_LLM_CONFIG


class SkyHighlightsSection(Section):
    """Renders a bulleted sky-highlights list with an optional LLM finale.

    Args:
        title:         Section heading.
        provider:      SkyDataProvider instance.
        date:          Target date (tonight).
        location_name: Observer location for the LLM prompt.
    """

    def __init__(
        self,
        title: str,
        provider: Any,
        date: datetime,
        location_name: str,
    ) -> None:
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.location_name = location_name

        base = getSampleStyleSheet()
        self._bullet_style = ParagraphStyle(
            "SkyBullet",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            leftIndent=12,
            spaceAfter=3,
        )
        self._heading_style = base["Heading2"]
        self._glyph_style = ParagraphStyle(
            "SkyGlyph",
            parent=base["Normal"],
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        )
        self._gloss_style = ParagraphStyle(
            "SkyGloss",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
        )

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def fetch_data(self) -> None:
        sky = self.provider.get_sky_data(self.date)
        self.data = sky.get("highlights", [])
        self._sky_data = sky  # keep full payload for LLM prompt

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        elements: List[Any] = []
        elements.append(Paragraph(self.title, self._heading_style))
        elements.append(Spacer(1, 4))

        # Prefer LLM-generated bullets; fall back to raw highlights if unavailable.
        llm_output = self._get_llm_bullet()
        if llm_output:
            # The LLM returns one "• text" line per bullet — render each separately.
            for line in llm_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Strip a leading bullet character the LLM already added.
                text = line.lstrip("•").strip()
                if text:
                    elements.append(Paragraph(f"• {text}", self._bullet_style))
        else:
            bullets: List[str] = cast(List[str], self.data) if isinstance(self.data, list) else []
            for bullet in bullets:
                elements.append(Paragraph(f"• {bullet}", self._bullet_style))

        # Glossary: symbol → planet name
        elements.append(Spacer(1, 8))
        elements.extend(self._build_glossary())

        return elements

    # ------------------------------------------------------------------
    # LLM integration (graceful no-op if no API keys)
    # ------------------------------------------------------------------

    def _get_llm_bullet(self) -> str:
        """Return a single LLM-generated sky bullet, or empty string on failure."""
        sky = getattr(self, "_sky_data", {})
        if not sky:
            return ""

        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        grok_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")

        if not gemini_key and not grok_key:
            return ""

        try:
            summarizer = SkyNightSummarizer(
                gemini_api_key=gemini_key,
                grok_api_key=grok_key,
                config=DEFAULT_LLM_CONFIG,
            )
            planets_str = ", ".join(
                f"{p['name']} in {p['zodiac']}"
                for p in sky.get("planets", [])
                if p.get("name") not in {"Uranus", "Neptune"}
            )
            llm_choice = "gemini" if gemini_key else "grok"
            result = summarizer.generate_summary(
                llm_choice=llm_choice,
                data={
                    "planets": planets_str,
                    "moon_phase": sky.get("moon_phase", ""),
                    "highlights": "\n".join(sky.get("highlights", [])),
                    "location": self.location_name,
                    "date": self.date.strftime("%B %d, %Y"),
                },
            )
            return str(result).strip() if result else ""
        except Exception:  # noqa: BLE001
            return ""

    # ------------------------------------------------------------------
    # Symbol glossary
    # ------------------------------------------------------------------

    def _build_glossary(self) -> List[Any]:
        """Return a compact one-row symbol glossary as a ReportLab Table."""
        from .zodiac_wheel import _PLANET_SYMBOLS, _UNICODE_FONT  # local import avoids circularity

        ordered = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune",
        ]

        symbol_cells = [Paragraph(f"<font name='{_UNICODE_FONT}' size='11'>{_PLANET_SYMBOLS[n]}</font>",
                                   self._glyph_style) for n in ordered]
        name_cells   = [Paragraph(n, self._gloss_style) for n in ordered]

        col_w = 50  # points per column
        table = Table([symbol_cells, name_cells],
                      colWidths=[col_w] * len(ordered))
        table.setStyle(TableStyle([
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEABOVE",   (0, 0), (-1, 0),  0.5, HexColor("#AAAAAA")),
        ]))
        return [table]

"""Sky highlights component for the Sky Tonight screamsheet."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, List, Optional, cast

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph

from ...llm.config import DEFAULT_LLM_CONFIG
from ...llm.summarizers import SkyNightSummarizer
from ...providers.sky_provider import SkyDataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry


@ComponentRegistry.register("sky_highlights")
@ComponentRegistry.register("sky_summary")
@ComponentRegistry.register("sky_tonight_summary")
class SkyHighlightsComponent(ScreamsheetComponent):
    """Renders a bulleted sky-highlights list with an optional LLM finale."""

    component_type = "sky_highlights"
    layout_spec = ComponentLayoutSpec(
        weight=0.25,
        columns=1,
        expand_when_unpaired=True,
        component_family="sky_highlights",
        max_on_front_page=2,
        max_per_page=2,
    )

    def __init__(
        self,
        title: str = "Sky Highlights",
        provider: Optional[Any] = None,
        date: Optional[datetime] = None,
        location_name: str = "Bryn Mawr, PA",
        lat: float = 40.02,
        lon: float = -75.34,
        **kwargs: Any,
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        super().__init__(
            title=title,
            provider=provider,
            date=date if date is not None else datetime.now(),
            location_name=location_name,
            lat=lat,
            lon=lon,
            **kwargs,
        )

        base = getSampleStyleSheet()
        self._bullet_style = ParagraphStyle(
            "SkyBullet",
            parent=base["Normal"],
            fontSize=13,
            leading=17.5,
            leftIndent=12,
            spaceAfter=6,
        )
        self._col_bullet_style = ParagraphStyle(
            "SkyColumnBullet",
            parent=base["Normal"],
            fontSize=10.5,
            leading=14.0,
            leftIndent=0,
            spaceAfter=6,
        )
        self._heading_style = base["Heading2"]

    def create_default_provider(self) -> Any:
        return SkyDataProvider(lat=self.lat, lon=self.lon, location_name=self.location_name)

    def fetch_data(self) -> None:
        sky = self.provider.get_sky_data(self.date)
        self.data = sky.get("highlights", [])
        self._sky_data = sky

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        elements: List[Any] = []
        active_style = (
            self._col_bullet_style
            if (max_width is not None and max_width <= 280)
            else self._bullet_style
        )

        llm_output = self._get_llm_bullet()
        if llm_output:
            for line in llm_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                text = line.lstrip("•").strip()
                if text:
                    elements.append(Paragraph(text, active_style))
        else:
            bullets: List[str] = cast(List[str], self.data) if isinstance(self.data, list) else []
            for bullet in bullets:
                elements.append(Paragraph(bullet, active_style))

        return elements

    def render_markdown(self) -> str:
        """Render sky tonight highlights in Markdown."""
        if self.data is None:
            self.fetch_data()

        llm_output = self._get_llm_bullet()
        if llm_output:
            lines = []
            for line in llm_output.splitlines():
                line = line.strip()
                if line:
                    text = line.lstrip("•").strip()
                    if text:
                        lines.append(f"* {text}")
            return "\n".join(lines)

        bullets = self.data if isinstance(self.data, list) else []
        return "\n".join(f"* {b}" for b in bullets if b)

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
            pheno_map = {p["name"]: p for p in sky.get("planet_pheno", [])}
            planet_parts: List[str] = []
            for p in sky.get("planets", []):
                if p.get("name") not in {"Uranus", "Neptune"}:
                    ph = pheno_map.get(p["name"])
                    mag_info = f" (mag {ph['magnitude']:.1f})" if ph else ""
                    planet_parts.append(f"{p['name']} in {p['zodiac']}{mag_info}")
            planets_str = ", ".join(planet_parts)

            const_str = ", ".join(
                c.get("description", c.get("name", ""))
                for c in sky.get("constellation_details", [])[:4]
            )
            messier_str = "; ".join(
                m.get("formatted", "") for m in sky.get("messier_objects", [])
            )
            dark_sky = sky.get("dark_sky_window", "")

            llm_choice = "gemini" if gemini_key else "grok"
            result = summarizer.generate_summary(
                llm_choice=llm_choice,
                data={
                    "planets": planets_str,
                    "moon_phase": sky.get("moon_phase", ""),
                    "highlights": "\n".join(sky.get("highlights", [])),
                    "constellations": const_str,
                    "messier_objects": messier_str,
                    "dark_sky_window": dark_sky,
                    "location": self.location_name,
                    "date": self.date.strftime("%B %d, %Y"),
                },
            )
            return str(result).strip() if result else ""
        except Exception:
            return ""

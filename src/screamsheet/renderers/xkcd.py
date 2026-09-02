"""XKCD Comic section renderer for screamsheets."""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Image as RLImage, Paragraph, Spacer

from ..base import Section
from ..providers.xkcd_provider import XKCDProvider

logger = logging.getLogger("screamsheet.xkcd.renderer")

_CACHE_DIR = Path.home() / ".cache" / "screamsheet" / "xkcd"


class XKCDSection(Section):
    """Renders the XKCD comic strip (title, comic image, and hover alt text)."""

    def __init__(
        self,
        provider: Optional[XKCDProvider] = None,
        comic_data: Optional[Dict[str, Any]] = None,
        title: str = "XKCD",
        max_width: float = 520.0,
        max_height: float = 220.0,
    ):
        super().__init__(title)
        self.provider = provider or XKCDProvider()
        self.comic_data = comic_data
        self.max_width = max_width
        self.max_height = max_height
        self._setup_styles()

    def _setup_styles(self):
        base = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "XKCDTitle",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            spaceBefore=4,
            spaceAfter=2,
            textColor=colors.HexColor("#111111"),
        )
        self._alt_style = ParagraphStyle(
            "XKCDAlt",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            alignment=1,  # Center aligned
            textColor=colors.HexColor("#444444"),
            spaceBefore=3,
            spaceAfter=3,
        )
        self._empty_style = ParagraphStyle(
            "XKCDEmpty",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=11.5,
            textColor=colors.HexColor("#777777"),
        )

    def fetch_data(self):
        if not self.comic_data and self.provider:
            self.comic_data = self.provider.get_comic()

    def has_content(self) -> bool:
        if not self.comic_data and self.provider:
            self.fetch_data()
        return bool(self.comic_data)

    def _download_and_scale_image(self, img_url: str, num: int) -> Optional[RLImage]:
        """Download image to disk cache and compute scaled ReportLab Image flowable."""
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            suffix = Path(img_url).suffix or ".png"
            local_path = _CACHE_DIR / f"xkcd_{num}{suffix}"

            if not local_path.exists():
                resp = requests.get(
                    img_url,
                    headers={"User-Agent": "screamsheet/1.0"},
                    timeout=15,
                )
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)

            with PILImage.open(local_path) as pil_img:
                orig_w, orig_h = pil_img.size

            if orig_w <= 0 or orig_h <= 0:
                return None

            # Calculate proportional scale to fit within max_width and max_height
            scale = min(self.max_width / orig_w, self.max_height / orig_h, 1.0)
            target_w = orig_w * scale
            target_h = orig_h * scale

            rl_img = RLImage(str(local_path), width=target_w, height=target_h)
            rl_img.hAlign = "CENTER"
            return rl_img
        except Exception as e:
            logger.error("Failed to load/scale XKCD image from %s: %s", img_url, e)
            return None

    def render(self) -> List[Any]:
        if not self.comic_data and self.provider:
            self.fetch_data()

        flowables: List[Any] = []
        if not self.comic_data:
            flowables.append(Paragraph("<i>XKCD comic unavailable</i>", self._empty_style))
            return flowables

        num = self.comic_data.get("num", 0)
        c_title = self.comic_data.get("title", "")
        img_url = self.comic_data.get("img", "")
        alt_text = self.comic_data.get("alt", "")

        header_text = f"<b>XKCD #{num}: {c_title}</b>" if num else f"<b>XKCD: {c_title}</b>"
        flowables.append(Paragraph(header_text, self._title_style))
        flowables.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#333333"),
                spaceBefore=1,
                spaceAfter=4,
            )
        )

        rl_img = self._download_and_scale_image(img_url, num)
        if rl_img:
            flowables.append(rl_img)
            flowables.append(Spacer(1, 2))

        if alt_text:
            clean_alt = alt_text.replace("\n", " ").strip()
            flowables.append(Paragraph(f"&ldquo;{clean_alt}&rdquo;", self._alt_style))

        flowables.append(Spacer(1, 4))
        return flowables

    def render_markdown(self) -> str:
        if not self.comic_data and self.provider:
            self.fetch_data()

        if not self.comic_data:
            return "## XKCD\n\n_XKCD comic unavailable_\n"

        num = self.comic_data.get("num", 0)
        c_title = self.comic_data.get("title", "")
        img_url = self.comic_data.get("img", "")
        alt_text = self.comic_data.get("alt", "").replace("\n", " ").strip()

        lines = [
            f"## XKCD #{num}: {c_title}\n",
            f"![{c_title}]({img_url})\n",
            f"_{alt_text}_\n",
        ]
        return "\n".join(lines)

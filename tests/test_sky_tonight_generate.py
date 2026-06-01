"""Unit tests for SkyTonightScreamsheet.generate() two-page constraint."""
from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from screamsheet.sky.sky_tonight import SkyTonightScreamsheet
from screamsheet.renderers.sky_horoscope import SkyHoroscopeSection


def _count_pdf_pages(path: str) -> int:
    with open(path, "rb") as f:
        content = f.read()
    return len(re.findall(rb"/Type\s*/Page[^s]", content))


# ---------------------------------------------------------------------------
# SkyHoroscopeSection page_slot
# ---------------------------------------------------------------------------

class TestSkyHoroscopeSectionPageSlot:
    def test_horoscope_section_page_slot_is_back(self):
        """SkyHoroscopeSection must declare page_slot='back'."""
        from screamsheet.config import PersonConfig
        provider = MagicMock()
        section = SkyHoroscopeSection(
            title="Horoscopes",
            provider=provider,
            date=datetime(2026, 5, 16),
            location_name="Test",
            people=[
                PersonConfig(
                    name="Alice",
                    birth_date="1990-01-01",
                    birth_time="12:00",
                    birth_location="New York",
                )
            ],
        )
        assert section.page_slot == "back"


# ---------------------------------------------------------------------------
# SkyTonightScreamsheet build_sections — horoscope is back-page slot
# ---------------------------------------------------------------------------

class TestSkyTonightBuildSectionsPageSlots:
    def test_horoscope_built_with_back_page_slot(self):
        """build_sections() places SkyHoroscopeSection on the back page slot."""
        from screamsheet.config import PersonConfig
        sheet = SkyTonightScreamsheet(
            "out.pdf", lat=40.0, lon=-75.0, location_name="Test",
            date=datetime(2026, 5, 16),
            people=[
                PersonConfig(
                    name="Alice", birth_date="1990-01-01",
                    birth_time="12:00", birth_location="New York",
                )
            ],
        )
        sections = sheet.build_sections()
        horoscope_sections = [s for s in sections if isinstance(s, SkyHoroscopeSection)]
        assert horoscope_sections, "SkyHoroscopeSection not found"
        assert horoscope_sections[0].page_slot == "back"

    def test_zodiac_and_highlights_are_front_page(self):
        """ZodiacWheelSection and SkyHighlightsSection land on the front page slot."""
        from screamsheet.renderers.zodiac_wheel import ZodiacWheelSection
        from screamsheet.renderers.sky_highlights import SkyHighlightsSection
        sheet = SkyTonightScreamsheet(
            "out.pdf", lat=40.0, lon=-75.0, location_name="Test",
            date=datetime(2026, 5, 16),
        )
        sections = sheet.build_sections()
        for sec in sections:
            if isinstance(sec, (ZodiacWheelSection, SkyHighlightsSection)):
                assert getattr(sec, "page_slot", "front") == "front"


# ---------------------------------------------------------------------------
# SkyTonightScreamsheet.generate() — two-page PDF layout
# ---------------------------------------------------------------------------

class TestSkyTonightGenerateTwoPage:
    def test_generate_returns_output_filename(self, tmp_path):
        """generate() must return the output filename."""
        from unittest.mock import patch
        sheet = SkyTonightScreamsheet(
            str(tmp_path / "sky.pdf"), lat=40.0, lon=-75.0, location_name="Test",
            date=datetime(2026, 5, 16),
        )
        with (
            patch.object(sheet.provider, "get_sky_data", return_value={
                "planets": [], "highlights": [], "moon_phase": "Full Moon",
                "visible_signs": [],
            }),
        ):
            result = sheet.generate()
        assert result == str(tmp_path / "sky.pdf")

    def test_no_people_single_page(self, tmp_path):
        """With no horoscope people, only the front page is generated."""
        from unittest.mock import patch
        pdf_path = str(tmp_path / "sky_front_only.pdf")
        sheet = SkyTonightScreamsheet(
            pdf_path, lat=40.0, lon=-75.0, location_name="Test",
            date=datetime(2026, 5, 16), people=[],
        )
        sky_data = {
            "planets": [], "highlights": ["Mercury is visible tonight."],
            "moon_phase": "Waxing Crescent", "visible_signs": [],
        }
        with (
            patch.object(sheet.provider, "get_sky_data", return_value=sky_data),
        ):
            sheet.generate()
        assert _count_pdf_pages(pdf_path) == 1


# ---------------------------------------------------------------------------
# Branding footer — sky tonight screamsheet
# ---------------------------------------------------------------------------

class TestSkyTonightBrandingOnBothPages:
    def test_front_page_template_has_branding_callback(self):
        """The Sky Tonight Front PageTemplate must fire the branding callback on every page."""
        from unittest.mock import patch
        from reportlab.platypus import BaseDocTemplate

        captured_templates: list = []

        class _CapturingDoc(BaseDocTemplate):
            def addPageTemplates(self, templates):  # type: ignore[override]
                captured_templates.extend(templates)
                super().addPageTemplates(templates)

        with patch("screamsheet.base.screamsheet.BaseDocTemplate", _CapturingDoc):
            sheet = SkyTonightScreamsheet(
                "/tmp/sky_brand.pdf", lat=40.0, lon=-75.0, location_name="Test",
                date=datetime(2026, 5, 16),
            )
            sheet.branding = "DISTRACTEDFORTUNE.COM"
            sky_data = {
                "planets": [], "highlights": ["Test highlight."],
                "moon_phase": "Full Moon", "visible_signs": [],
            }
            with patch.object(sheet.provider, "get_sky_data", return_value=sky_data):
                try:
                    sheet.generate()
                except Exception:
                    pass

        front_templates = [t for t in captured_templates if t.id == "Front"]
        assert front_templates, "Front PageTemplate not found"
        front_page_cb = getattr(front_templates[0], "onPage", None)
        canvas_mock = MagicMock()
        if callable(front_page_cb):
            front_page_cb(canvas_mock, MagicMock())
        canvas_mock.drawCentredString.assert_called_once()

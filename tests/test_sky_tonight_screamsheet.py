"""Tests for SkyTonightScreamsheet and factory method."""
from __future__ import annotations

from datetime import datetime

import pytest

from screamsheet.sky.sky_tonight import SkyTonightScreamsheet
from screamsheet.factory import ScreamsheetFactory
from screamsheet.renderers.zodiac_wheel import ZodiacWheelSection
from screamsheet.renderers.sky_highlights import SkyHighlightsSection


class TestSkyTonightScreamshetInit:
    def test_output_filename_stored(self):
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test")
        assert s.output_filename == "out.pdf"

    def test_lat_stored(self):
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test")
        assert s.lat == 40.0

    def test_lon_stored(self):
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test")
        assert s.lon == -75.0

    def test_location_name_stored(self):
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Bryn Mawr")
        assert s.location_name == "Bryn Mawr"

    def test_default_date_is_today(self):
        before = datetime.now()
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test")
        after = datetime.now()
        assert before <= s.date <= after

    def test_explicit_date_used(self):
        d = datetime(2026, 4, 18)
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test", date=d)
        assert s.date == d


class TestSkyTonightScreamshetTitle:
    def test_get_title(self):
        s = SkyTonightScreamsheet("out.pdf", lat=40.0, lon=-75.0, location_name="Test")
        assert s.get_title() == "Sky Tonight Screamsheet"


class TestSkyTonightScreamshetSections:
    def setup_method(self) -> None:
        self.sheet = SkyTonightScreamsheet(
            "out.pdf", lat=40.0, lon=-75.0, location_name="Test",
            date=datetime(2026, 4, 18),
        )

    def test_build_sections_returns_list(self):
        sections = self.sheet.build_sections()
        assert isinstance(sections, list)

    def test_build_sections_has_three_sections(self):
        sections = self.sheet.build_sections()
        assert len(sections) == 3

    def test_first_section_is_zodiac_wheel(self):
        sections = self.sheet.build_sections()
        assert isinstance(sections[0], ZodiacWheelSection)

    def test_second_section_is_sky_highlights(self):
        sections = self.sheet.build_sections()
        assert isinstance(sections[1], SkyHighlightsSection)


class TestScreamsheetFactorySkyTonight:
    def test_returns_sky_tonight_instance(self):
        s = ScreamsheetFactory.create_sky_tonight_screamsheet(
            "out.pdf", lat=40.0, lon=-75.0, location_name="Test"
        )
        assert isinstance(s, SkyTonightScreamsheet)

    def test_output_filename_passed(self):
        s = ScreamsheetFactory.create_sky_tonight_screamsheet(
            "sky.pdf", lat=40.0, lon=-75.0, location_name="Test"
        )
        assert s.output_filename == "sky.pdf"

    def test_lat_lon_passed(self):
        s = ScreamsheetFactory.create_sky_tonight_screamsheet(
            "out.pdf", lat=51.5, lon=-0.1, location_name="London"
        )
        assert s.lat == 51.5
        assert s.lon == -0.1

    def test_explicit_date_passed(self):
        d = datetime(2026, 6, 21)
        s = ScreamsheetFactory.create_sky_tonight_screamsheet(
            "out.pdf", lat=40.0, lon=-75.0, location_name="Test", date=d
        )
        assert s.date == d

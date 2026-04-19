"""Tests for ZodiacWheelSection."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.renderers.zodiac_wheel import ZodiacWheelSection


def _make_provider(planets=None):
    provider = MagicMock()
    if planets is None:
        planets = [
            {"name": "Venus", "zodiac": "Taurus", "ecliptic_lon": 45.0, "two_letter": "Ve"},
            {"name": "Mars", "zodiac": "Gemini", "ecliptic_lon": 75.0, "two_letter": "Ma"},
        ]
    provider.get_sky_data.return_value = {
        "planets": planets,
        "moon_phase": "Waxing Crescent (35% illuminated)",
        "highlights": [],
        "visible_constellations": ["Taurus", "Gemini"],
    }
    return provider


class TestZodiacWheelSectionInit:
    def test_title_stored(self):
        s = ZodiacWheelSection("Tonight's Wheel", _make_provider(), datetime(2026, 4, 18))
        assert s.title == "Tonight's Wheel"

    def test_data_initially_none(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        assert s.data is None


class TestZodiacWheelSectionFetchData:
    def test_fetch_data_populates_data(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        s.fetch_data()
        assert s.data is not None

    def test_fetch_data_contains_planets(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        s.fetch_data()
        assert isinstance(s.data, dict)
        assert "planets" in s.data

    def test_fetch_data_contains_visible_constellations(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        s.fetch_data()
        assert "visible_constellations" in s.data


class TestZodiacWheelSectionHasContent:
    def test_true_when_planets_present(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        assert s.has_content() is True

    def test_false_when_no_planets(self):
        provider = _make_provider(planets=[])
        s = ZodiacWheelSection("Wheel", provider, datetime(2026, 4, 18))
        assert s.has_content() is False


class TestZodiacWheelSectionRender:
    def test_render_returns_non_empty_list(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        result = s.render()
        assert len(result) > 0

    def test_render_returns_list(self):
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        result = s.render()
        assert isinstance(result, list)

    def test_render_contains_drawing(self):
        from reportlab.graphics.shapes import Drawing
        s = ZodiacWheelSection("Wheel", _make_provider(), datetime(2026, 4, 18))
        flowables = s.render()
        drawing_types = [f for f in flowables if isinstance(f, Drawing)]
        assert len(drawing_types) >= 1

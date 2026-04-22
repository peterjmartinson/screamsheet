"""Tests for SkyHoroscopeSection renderer."""
from __future__ import annotations

from unittest.mock import MagicMock
from datetime import datetime

from screamsheet.config import PersonConfig
from screamsheet.renderers.sky_horoscope import SkyHoroscopeSection


def _make_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_sky_data.return_value = {
        "planets": [
            {"name": "Sun", "zodiac": "Taurus", "ecliptic_lon": 31.0, "two_letter": "Su"},
            {"name": "Moon", "zodiac": "Cancer", "ecliptic_lon": 92.0, "two_letter": "Mo"},
        ],
        "moon_phase": "Waxing Crescent",
        "highlights": ["The Moon is Waxing Crescent."],
        "visible_constellations": ["Leo", "Orion"],
    }
    return provider


def _make_people() -> list[PersonConfig]:
    return [
        PersonConfig(
            name="Alice",
            birth_date="1978-02-26",
            birth_time="01:20",
            birth_location="Wauwatosa, WI",
        ),
        PersonConfig(
            name="Bob",
            birth_date="1980-06-15",
            birth_time="14:30",
            birth_location="Chicago, IL",
        ),
    ]


def test_has_content_false_when_no_people() -> None:
    section = SkyHoroscopeSection(
        title="Horoscopes",
        provider=_make_provider(),
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
        people=[],
    )
    assert section.has_content() is False


def test_has_content_true_when_people_configured() -> None:
    section = SkyHoroscopeSection(
        title="Horoscopes",
        provider=_make_provider(),
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
        people=_make_people(),
    )
    assert section.has_content() is True


def test_render_returns_list_with_no_api_keys(monkeypatch) -> None:
    """Render must return a non-empty list of flowables even without LLM keys."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    section = SkyHoroscopeSection(
        title="Horoscopes",
        provider=_make_provider(),
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
        people=_make_people(),
    )
    result = section.render()
    assert isinstance(result, list)
    assert len(result) > 0

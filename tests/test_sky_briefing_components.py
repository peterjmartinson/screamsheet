"""Tests for Sky Tonight and Morning Briefing components (Stage 5)."""
from datetime import datetime
from unittest.mock import MagicMock

from screamsheet.components import (
    AgendaComponent,
    BriefingBackComponent,
    ComponentRegistry,
    EmailNewsComponent,
    ImportantEmailsComponent,
    SkyHighlightsComponent,
    SkyHoroscopeComponent,
    XKCDComponent,
    ZodiacWheelComponent,
)
from screamsheet.config import PersonConfig


def test_sky_and_briefing_components_registered():
    expected = {
        "zodiac_wheel": ZodiacWheelComponent,
        "sky_highlights": SkyHighlightsComponent,
        "sky_horoscope": SkyHoroscopeComponent,
        "agenda": AgendaComponent,
        "email_news": EmailNewsComponent,
        "important_emails": ImportantEmailsComponent,
        "briefing_back": BriefingBackComponent,
        "xkcd": XKCDComponent,
    }
    for name, cls in expected.items():
        assert ComponentRegistry.get(name) is cls


def test_sky_components_render_and_layout_specs():
    mock_sky_provider = MagicMock()
    mock_sky_provider.get_sky_data.return_value = {
        "planets": [
            {"name": "Sun", "zodiac": "Taurus", "ecliptic_lon": 31.0, "two_letter": "Su"},
            {"name": "Moon", "zodiac": "Cancer", "ecliptic_lon": 92.0, "two_letter": "Mo"},
        ],
        "moon_phase": "Waxing Crescent",
        "highlights": ["The Moon is Waxing Crescent."],
        "visible_constellations": ["Leo", "Orion"],
    }

    wheel = ZodiacWheelComponent(provider=mock_sky_provider, date=datetime(2026, 4, 21))
    assert wheel.has_content() is True
    assert len(wheel.render()) == 3
    assert wheel.layout_spec.component_family == "zodiac_wheel"

    highlights = SkyHighlightsComponent(
        provider=mock_sky_provider,
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
    )
    assert highlights.has_content() is True
    assert len(highlights.render()) > 0
    assert highlights.layout_spec.component_family == "sky_highlights"

    horoscope = SkyHoroscopeComponent(
        provider=mock_sky_provider,
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
        people=[
            PersonConfig(
                name="Alice",
                birth_date="1978-02-26",
                birth_time="01:20",
                birth_location="Wauwatosa, WI",
            )
        ],
    )
    assert horoscope.page_slot == "back"
    assert horoscope.layout_spec.component_family == "sky_horoscope"
    assert horoscope.has_content() is True


def test_briefing_components_layout_specs():
    agenda = AgendaComponent(
        date=datetime(2026, 8, 28),
        multi_day_data=[
            {
                "date": "2026-08-28",
                "agenda": [{"id": "1", "type": "event", "title": "Standup", "time": "09:00 AM - 09:30 AM"}],
                "sections": [],
            }
        ],
    )
    assert agenda.layout_spec.component_family == "agenda"
    assert agenda.layout_spec.renders_own_header is True
    assert agenda.has_content() is True
    assert len(agenda.render()) == 1

    back = BriefingBackComponent()
    assert back.page_slot == "back"
    assert back.layout_spec.full_page_only is True
    assert back.has_content() is False

"""Tests for SkyHoroscopeSection renderer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
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


# ---------------------------------------------------------------------------
# AstroDataProvider injection
# ---------------------------------------------------------------------------

def _make_astro_provider() -> MagicMock:
    astro = MagicMock()
    astro.get_horoscope_data.return_value = {
        "planets": [
            {"name": "Sun", "zodiac": "Taurus", "ecliptic_lon": 31.0, "two_letter": "Su"},
            {"name": "Moon", "zodiac": "Cancer", "ecliptic_lon": 92.0, "two_letter": "Mo"},
        ],
        "aspects": [
            {"planet_a": "Sun", "planet_b": "Moon", "aspect": "Square", "orb": 1.0},
        ],
        "moon_phase": "Waxing Crescent",
    }
    # Transit Moon at 92.0° hits natal Moon at 92.5° (orb 0.5° < 3°)
    astro.get_natal_positions.return_value = [
        {"name": "Sun",  "zodiac": "Virgo",  "ecliptic_lon": 157.0, "two_letter": "Su"},
        {"name": "Moon", "zodiac": "Cancer", "ecliptic_lon": 92.5,  "two_letter": "Mo"},
    ]
    return astro


def test_astro_provider_is_called_during_fetch(monkeypatch) -> None:
    """AstroDataProvider.get_horoscope_data must be called when injected."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    astro = _make_astro_provider()
    section = SkyHoroscopeSection(
        title="Horoscopes",
        provider=_make_provider(),
        date=datetime(2026, 4, 21),
        location_name="Bryn Mawr, PA",
        people=_make_people(),
        astro_provider=astro,
    )
    section.fetch_data()
    astro.get_horoscope_data.assert_called_once_with(datetime(2026, 4, 21))


def test_astro_provider_none_does_not_raise(monkeypatch) -> None:
    """Section must work correctly when astro_provider is not injected."""
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
        astro_provider=None,
    )
    result = section.render()
    assert isinstance(result, list)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# LLM data structure: subject_natal / current_sky separation
# ---------------------------------------------------------------------------

def _make_person_with_natal() -> PersonConfig:
    return PersonConfig(
        name="Alice",
        birth_date="1978-02-26",
        birth_time="01:20",
        birth_location="Wauwatosa, WI",
        sun_sign="Virgo",
        moon_sign="Cancer",
        ascendant="Scorpio",
    )


def _call_get_horoscope_with_mock_summarizer(
    monkeypatch, astro_provider: MagicMock
) -> dict:
    """Helper: run _get_horoscope with a mocked summarizer; return the data kwarg."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("screamsheet.renderers.sky_horoscope.HoroscopeSummarizer") as MockSummarizer:
        mock_instance = MockSummarizer.return_value
        mock_instance.generate_summary.return_value = "A reading."
        section = SkyHoroscopeSection(
            title="Horoscopes",
            provider=_make_provider(),
            date=datetime(2026, 4, 21),
            location_name="Bryn Mawr, PA",
            people=[_make_person_with_natal()],
            astro_provider=astro_provider,
        )
        section.fetch_data()
        section._get_horoscope(_make_person_with_natal())
        return mock_instance.generate_summary.call_args.kwargs["data"]


def test_llm_data_has_subject_natal_key(monkeypatch) -> None:
    """generate_summary data must include a 'subject_natal' key."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "subject_natal" in data


def test_llm_data_has_current_sky_key(monkeypatch) -> None:
    """generate_summary data must include a 'current_sky' key."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "current_sky" in data


def test_llm_data_subject_natal_contains_sun_sign(monkeypatch) -> None:
    """subject_natal string must contain the person's natal Sun sign."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "Virgo" in data["subject_natal"]


def test_llm_data_current_sky_contains_transit_planets(monkeypatch) -> None:
    """current_sky string must contain transit planet text."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "Transit planets" in data["current_sky"]


def test_llm_data_current_sky_contains_aspects(monkeypatch) -> None:
    """current_sky string must contain aspect text."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "Key aspects" in data["current_sky"]


def test_llm_data_does_not_have_flat_sun_sign_key(monkeypatch) -> None:
    """Flat 'sun_sign' key must not appear in data — it lives inside subject_natal."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "sun_sign" not in data


def test_llm_data_does_not_have_flat_planets_key(monkeypatch) -> None:
    """Flat 'planets' key must not appear in data — it lives inside current_sky."""
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "planets" not in data


# ---------------------------------------------------------------------------
# Enriched current_sky: house placement, dignity, hits
# ---------------------------------------------------------------------------

def test_llm_data_current_sky_contains_house_number(monkeypatch) -> None:
    """current_sky must reference a house number."""
    # Sun in Taurus, Scorpio ASC → House 7
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "House 7" in data["current_sky"]


def test_llm_data_current_sky_contains_house_meaning(monkeypatch) -> None:
    """current_sky must include the house meaning text."""
    # House 7 meaning includes 'Partnerships'
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "Partnerships" in data["current_sky"]


def test_llm_data_current_sky_contains_dignity(monkeypatch) -> None:
    """current_sky must label each transit planet's dignity."""
    # Sun in Taurus is Peregrine (not Leo/Aries/Aquarius/Libra)
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "Peregrine" in data["current_sky"]


def test_llm_data_current_sky_contains_hits(monkeypatch) -> None:
    """current_sky must list conjunctions of transit and natal planets."""
    # Transit Moon at 92.0° conjuncts natal Moon at 92.5° (orb 0.5°)
    data = _call_get_horoscope_with_mock_summarizer(monkeypatch, _make_astro_provider())
    assert "conjunct natal Moon" in data["current_sky"]

"""Tests for AstroDataProvider (Swiss Ephemeris / pyswisseph).

Each test verifies exactly one behaviour (SRP).
All planet-position and aspect computations use the Moshier built-in ephemeris
(swe.FLG_MOSEPH), so no external data files are required.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.astro_provider import AstroDataProvider

_DATE = datetime(2026, 4, 23)
_PROVIDER = AstroDataProvider()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestAstroDataProviderInit:
    def test_instantiates_without_arguments(self) -> None:
        provider = AstroDataProvider()
        assert provider is not None


# ---------------------------------------------------------------------------
# DataProvider stub overrides
# ---------------------------------------------------------------------------

class TestDataProviderStubs:
    def test_get_game_scores_returns_empty_list(self) -> None:
        assert _PROVIDER.get_game_scores(_DATE) == []

    def test_get_standings_returns_empty_list(self) -> None:
        assert _PROVIDER.get_standings() == []


# ---------------------------------------------------------------------------
# _ecliptic_lon_to_zodiac  (pure static helper — same mapping as SkyProvider)
# ---------------------------------------------------------------------------

class TestEclipticLonToZodiac:
    def test_zero_degrees_is_aries(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(0.0) == "Aries"

    def test_29_degrees_is_aries(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(29.9) == "Aries"

    def test_30_degrees_is_taurus(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(30.0) == "Taurus"

    def test_180_degrees_is_libra(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(180.0) == "Libra"

    def test_330_degrees_is_pisces(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(330.0) == "Pisces"

    def test_360_wraps_to_aries(self) -> None:
        assert AstroDataProvider._ecliptic_lon_to_zodiac(360.0) == "Aries"


# ---------------------------------------------------------------------------
# get_planet_longitudes
# ---------------------------------------------------------------------------

class TestGetPlanetLongitudes:
    def test_returns_nine_planets(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        assert len(planets) == 9

    def test_each_planet_has_name_key(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        for p in planets:
            assert "name" in p

    def test_each_planet_has_float_longitude(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        for p in planets:
            assert isinstance(p["ecliptic_lon"], float)

    def test_each_planet_has_zodiac_sign(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        valid_signs = {
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
        }
        for p in planets:
            assert p["zodiac"] in valid_signs

    def test_longitudes_in_range_0_to_360(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        for p in planets:
            assert 0.0 <= p["ecliptic_lon"] < 360.0

    def test_includes_sun(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        names = [p["name"] for p in planets]
        assert "Sun" in names

    def test_includes_neptune(self) -> None:
        planets = _PROVIDER.get_planet_longitudes(_DATE)
        names = [p["name"] for p in planets]
        assert "Neptune" in names


# ---------------------------------------------------------------------------
# _compute_aspects  (pure helper — use controlled longitude inputs)
# ---------------------------------------------------------------------------

class TestComputeAspects:
    def _lons(self, pairs: dict[str, float]) -> list[dict]:
        """Build a minimal planet list from name→longitude mapping."""
        return [{"name": name, "ecliptic_lon": lon} for name, lon in pairs.items()]

    def test_conjunction_detected_within_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 3.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Conjunction" for a in aspects)

    def test_conjunction_not_detected_outside_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 10.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert not any(a["aspect"] == "Conjunction" for a in aspects)

    def test_opposition_detected_within_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 177.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Opposition" for a in aspects)

    def test_square_detected_within_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 93.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Square" for a in aspects)

    def test_trine_detected_within_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 122.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Trine" for a in aspects)

    def test_sextile_detected_within_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 63.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Sextile" for a in aspects)

    def test_sextile_not_detected_outside_orb(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 68.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert not any(a["aspect"] == "Sextile" for a in aspects)

    def test_aspect_dict_has_required_keys(self) -> None:
        lons = self._lons({"Sun": 0.0, "Moon": 0.5})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert len(aspects) >= 1
        a = aspects[0]
        assert "planet_a" in a
        assert "planet_b" in a
        assert "aspect" in a
        assert "orb" in a

    def test_no_aspects_for_unrelated_pair(self) -> None:
        # 45° is not a major aspect angle
        lons = self._lons({"Sun": 0.0, "Moon": 45.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert len(aspects) == 0

    def test_angle_wraps_correctly_across_360(self) -> None:
        # 350° and 5° are 15° apart — no conjunction (>8°)
        lons = self._lons({"Sun": 350.0, "Moon": 5.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert not any(a["aspect"] == "Conjunction" for a in aspects)

    def test_angle_wraps_correctly_within_orb(self) -> None:
        # 355° and 2° are 7° apart — conjunction within ±8°
        lons = self._lons({"Sun": 355.0, "Moon": 2.0})
        aspects = AstroDataProvider._compute_aspects(lons)
        assert any(a["aspect"] == "Conjunction" for a in aspects)


# ---------------------------------------------------------------------------
# get_moon_phase
# ---------------------------------------------------------------------------

class TestGetMoonPhase:
    def test_returns_non_empty_string(self) -> None:
        result = _PROVIDER.get_moon_phase(_DATE)
        assert isinstance(result, str) and len(result) > 0

    def test_returns_known_phase_name(self) -> None:
        known_phases = {
            "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
            "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
        }
        result = _PROVIDER.get_moon_phase(_DATE)
        assert result in known_phases


# ---------------------------------------------------------------------------
# get_horoscope_data
# ---------------------------------------------------------------------------

class TestGetHoroscopeData:
    def test_returns_dict(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert isinstance(result, dict)

    def test_has_planets_key(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert "planets" in result

    def test_has_aspects_key(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert "aspects" in result

    def test_has_moon_phase_key(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert "moon_phase" in result

    def test_planets_is_list(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert isinstance(result["planets"], list)

    def test_aspects_is_list(self) -> None:
        result = _PROVIDER.get_horoscope_data(_DATE)
        assert isinstance(result["aspects"], list)


# ---------------------------------------------------------------------------
# get_natal_positions
# ---------------------------------------------------------------------------

class TestGetNatalPositions:
    def test_returns_nine_planets(self) -> None:
        planets = _PROVIDER.get_natal_positions("1978-02-26", "01:20")
        assert len(planets) == 9

    def test_each_planet_has_float_longitude(self) -> None:
        planets = _PROVIDER.get_natal_positions("1978-02-26", "01:20")
        for p in planets:
            assert isinstance(p["ecliptic_lon"], float)

    def test_longitudes_in_range_0_to_360(self) -> None:
        planets = _PROVIDER.get_natal_positions("1978-02-26", "01:20")
        for p in planets:
            assert 0.0 <= p["ecliptic_lon"] < 360.0

    def test_accepts_string_birth_date_and_time(self) -> None:
        planets = _PROVIDER.get_natal_positions("2000-01-01", "12:00")
        assert len(planets) > 0

    def test_sun_position_differs_from_transit(self) -> None:
        natal = _PROVIDER.get_natal_positions("1978-02-26", "01:20")
        transit = _PROVIDER.get_planet_longitudes(_DATE)
        natal_sun = next(p["ecliptic_lon"] for p in natal if p["name"] == "Sun")
        transit_sun = next(p["ecliptic_lon"] for p in transit if p["name"] == "Sun")
        assert natal_sun != transit_sun


# ---------------------------------------------------------------------------
# _assign_house  (pure static helper)
# ---------------------------------------------------------------------------

class TestAssignHouse:
    def test_asc_sign_is_house_1(self) -> None:
        assert AstroDataProvider._assign_house("Scorpio", "Scorpio") == 1

    def test_next_sign_is_house_2(self) -> None:
        assert AstroDataProvider._assign_house("Sagittarius", "Scorpio") == 2

    def test_taurus_is_house_7_for_scorpio_asc(self) -> None:
        assert AstroDataProvider._assign_house("Taurus", "Scorpio") == 7

    def test_wraps_correctly_at_house_12(self) -> None:
        assert AstroDataProvider._assign_house("Libra", "Scorpio") == 12

    def test_unknown_sign_returns_zero(self) -> None:
        assert AstroDataProvider._assign_house("NotASign", "Scorpio") == 0


# ---------------------------------------------------------------------------
# get_whole_sign_houses  (pure static helper)
# ---------------------------------------------------------------------------

class TestGetWholeSignHouses:
    def test_returns_12_entries(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("Scorpio")
        assert len(houses) == 12

    def test_house_1_is_ascendant_sign(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("Scorpio")
        assert houses[1]["sign"] == "Scorpio"

    def test_house_2_is_next_sign(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("Scorpio")
        assert houses[2]["sign"] == "Sagittarius"

    def test_house_7_is_opposite_sign_for_scorpio(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("Scorpio")
        assert houses[7]["sign"] == "Taurus"

    def test_each_entry_has_meaning(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("Scorpio")
        for num, info in houses.items():
            assert "meaning" in info
            assert len(info["meaning"]) > 0

    def test_unknown_ascendant_returns_empty(self) -> None:
        houses = AstroDataProvider.get_whole_sign_houses("NotASign")
        assert houses == {}


# ---------------------------------------------------------------------------
# _get_planet_dignity  (pure static helper)
# ---------------------------------------------------------------------------

class TestGetPlanetDignity:
    def test_sun_in_leo_is_domicile(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Sun", "Leo") == "Domicile"

    def test_sun_in_aries_is_exaltation(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Sun", "Aries") == "Exaltation"

    def test_sun_in_aquarius_is_detriment(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Sun", "Aquarius") == "Detriment"

    def test_sun_in_libra_is_fall(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Sun", "Libra") == "Fall"

    def test_sun_in_taurus_is_peregrine(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Sun", "Taurus") == "Peregrine"

    def test_mars_in_aries_is_domicile(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Mars", "Aries") == "Domicile"

    def test_saturn_in_aries_is_fall(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Saturn", "Aries") == "Fall"

    def test_unknown_planet_returns_peregrine(self) -> None:
        assert AstroDataProvider._get_planet_dignity("Pluto", "Scorpio") == "Peregrine"


# ---------------------------------------------------------------------------
# _find_transit_hits  (pure static helper)
# ---------------------------------------------------------------------------

class TestFindTransitHits:
    def _planets(self, pairs: dict[str, float]) -> list[dict]:
        return [{"name": n, "ecliptic_lon": lon} for n, lon in pairs.items()]

    def test_returns_hit_within_orb(self) -> None:
        transit = self._planets({"Mars": 30.0})
        natal = self._planets({"Sun": 31.5})
        hits = AstroDataProvider._find_transit_hits(transit, natal, orb=3.0)
        assert len(hits) == 1

    def test_returns_empty_outside_orb(self) -> None:
        transit = self._planets({"Mars": 30.0})
        natal = self._planets({"Sun": 35.0})
        hits = AstroDataProvider._find_transit_hits(transit, natal, orb=3.0)
        assert len(hits) == 0

    def test_hit_dict_has_required_keys(self) -> None:
        transit = self._planets({"Mars": 30.0})
        natal = self._planets({"Sun": 30.5})
        hits = AstroDataProvider._find_transit_hits(transit, natal, orb=3.0)
        assert "transit_planet" in hits[0]
        assert "natal_planet" in hits[0]
        assert "orb" in hits[0]

    def test_correct_planet_names_in_hit(self) -> None:
        transit = self._planets({"Mars": 30.0})
        natal = self._planets({"Sun": 30.5})
        hits = AstroDataProvider._find_transit_hits(transit, natal, orb=3.0)
        assert hits[0]["transit_planet"] == "Mars"
        assert hits[0]["natal_planet"] == "Sun"

    def test_wraps_across_360_degrees(self) -> None:
        transit = self._planets({"Mars": 1.0})
        natal = self._planets({"Sun": 359.0})
        hits = AstroDataProvider._find_transit_hits(transit, natal, orb=3.0)
        assert len(hits) == 1

    def test_returns_empty_list_for_no_planets(self) -> None:
        hits = AstroDataProvider._find_transit_hits([], [], orb=3.0)
        assert hits == []

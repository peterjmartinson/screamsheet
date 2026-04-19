"""Tests for SkyDataProvider.

Each test verifies exactly one behaviour (SRP).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.providers.sky_provider import SkyDataProvider

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestSkyDataProviderInit:
    def test_lat_stored(self):
        p = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")
        assert p.lat == 40.02

    def test_lon_stored(self):
        p = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")
        assert p.lon == -75.34

    def test_location_name_stored(self):
        p = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")
        assert p.location_name == "Bryn Mawr, PA"


# ---------------------------------------------------------------------------
# DataProvider stub overrides
# ---------------------------------------------------------------------------

class TestSkyDataProviderStubs:
    def setup_method(self) -> None:
        self.provider = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")

    def test_get_game_scores_returns_empty_list(self):
        assert self.provider.get_game_scores(datetime(2026, 4, 18)) == []

    def test_get_standings_returns_empty_list(self):
        assert self.provider.get_standings() == []


# ---------------------------------------------------------------------------
# _ecliptic_lon_to_zodiac  (pure static helper)
# ---------------------------------------------------------------------------

class TestEclipticLonToZodiac:
    def setup_method(self) -> None:
        self.provider = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")

    def test_zero_degrees_is_aries(self):
        assert self.provider._ecliptic_lon_to_zodiac(0.0) == "Aries"

    def test_29_degrees_is_aries(self):
        assert self.provider._ecliptic_lon_to_zodiac(29.9) == "Aries"

    def test_30_degrees_is_taurus(self):
        assert self.provider._ecliptic_lon_to_zodiac(30.0) == "Taurus"

    def test_45_degrees_is_taurus(self):
        assert self.provider._ecliptic_lon_to_zodiac(45.0) == "Taurus"

    def test_75_degrees_is_gemini(self):
        assert self.provider._ecliptic_lon_to_zodiac(75.0) == "Gemini"

    def test_90_degrees_is_cancer(self):
        assert self.provider._ecliptic_lon_to_zodiac(90.0) == "Cancer"

    def test_180_degrees_is_libra(self):
        assert self.provider._ecliptic_lon_to_zodiac(180.0) == "Libra"

    def test_270_degrees_is_capricorn(self):
        assert self.provider._ecliptic_lon_to_zodiac(270.0) == "Capricorn"

    def test_330_degrees_is_pisces(self):
        assert self.provider._ecliptic_lon_to_zodiac(330.0) == "Pisces"

    def test_359_degrees_is_pisces(self):
        assert self.provider._ecliptic_lon_to_zodiac(359.9) == "Pisces"


# ---------------------------------------------------------------------------
# _moon_phase_name  (pure static helper)
# ---------------------------------------------------------------------------

class TestMoonPhaseName:
    def setup_method(self) -> None:
        self.provider = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Test")

    def test_zero_elongation_is_new_moon(self):
        assert SkyDataProvider._moon_phase_name(0.0) == "New Moon"

    def test_90_elongation_is_first_quarter(self):
        assert SkyDataProvider._moon_phase_name(90.0) == "First Quarter"

    def test_180_elongation_is_full_moon(self):
        assert SkyDataProvider._moon_phase_name(180.0) == "Full Moon"

    def test_270_elongation_is_last_quarter(self):
        assert SkyDataProvider._moon_phase_name(270.0) == "Last Quarter"

    def test_45_elongation_is_waxing_crescent(self):
        assert SkyDataProvider._moon_phase_name(45.0) == "Waxing Crescent"

    def test_135_elongation_is_waxing_gibbous(self):
        assert SkyDataProvider._moon_phase_name(135.0) == "Waxing Gibbous"

    def test_225_elongation_is_waning_gibbous(self):
        assert SkyDataProvider._moon_phase_name(225.0) == "Waning Gibbous"

    def test_315_elongation_is_waning_crescent(self):
        assert SkyDataProvider._moon_phase_name(315.0) == "Waning Crescent"


# ---------------------------------------------------------------------------
# get_sky_data  (assembly — mocks internal computation methods)
# ---------------------------------------------------------------------------

class TestGetSkyData:
    def setup_method(self) -> None:
        self.provider = SkyDataProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")
        self._date = datetime(2026, 4, 18)

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_returns_dict(self, mock_vis, mock_hi, mock_moon, mock_planets):
        mock_planets.return_value = []
        mock_moon.return_value = "Full Moon (100% illuminated)"
        mock_hi.return_value = []
        mock_vis.return_value = []
        result = self.provider.get_sky_data(self._date)
        assert isinstance(result, dict)

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_has_planets_key(self, mock_vis, mock_hi, mock_moon, mock_planets):
        mock_planets.return_value = [{"name": "Venus"}]
        mock_moon.return_value = "Waxing Crescent (35% illuminated)"
        mock_hi.return_value = []
        mock_vis.return_value = []
        result = self.provider.get_sky_data(self._date)
        assert "planets" in result

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_has_moon_phase_key(self, mock_vis, mock_hi, mock_moon, mock_planets):
        mock_planets.return_value = []
        mock_moon.return_value = "Full Moon (100% illuminated)"
        mock_hi.return_value = []
        mock_vis.return_value = []
        result = self.provider.get_sky_data(self._date)
        assert "moon_phase" in result

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_has_highlights_key(self, mock_vis, mock_hi, mock_moon, mock_planets):
        mock_planets.return_value = []
        mock_moon.return_value = ""
        mock_hi.return_value = ["Something cool"]
        mock_vis.return_value = []
        result = self.provider.get_sky_data(self._date)
        assert "highlights" in result

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_has_visible_constellations_key(self, mock_vis, mock_hi, mock_moon, mock_planets):
        mock_planets.return_value = []
        mock_moon.return_value = ""
        mock_hi.return_value = []
        mock_vis.return_value = ["Orion"]
        result = self.provider.get_sky_data(self._date)
        assert "visible_constellations" in result

    @patch.object(SkyDataProvider, "_compute_planet_positions")
    @patch.object(SkyDataProvider, "_compute_moon_phase")
    @patch.object(SkyDataProvider, "_get_highlights")
    @patch.object(SkyDataProvider, "_get_visible_constellations")
    def test_values_passed_through(self, mock_vis, mock_hi, mock_moon, mock_planets):
        planets = [{"name": "Mars", "zodiac": "Gemini", "ecliptic_lon": 75.3, "two_letter": "Ma"}]
        mock_planets.return_value = planets
        mock_moon.return_value = "First Quarter (50% illuminated)"
        mock_hi.return_value = ["Mars is high in the east"]
        mock_vis.return_value = ["Gemini", "Orion"]
        result = self.provider.get_sky_data(self._date)
        assert result["planets"] == planets
        assert result["moon_phase"] == "First Quarter (50% illuminated)"
        assert result["highlights"] == ["Mars is high in the east"]
        assert result["visible_constellations"] == ["Gemini", "Orion"]


# ---------------------------------------------------------------------------
# Polar-day / no-dusk edge case
# ---------------------------------------------------------------------------

class TestPolarEdgeCase:
    def test_no_dusk_returns_empty_visible_constellations(self):
        """When _find_astronomical_dusk returns None (polar day/night), no crash."""
        provider = SkyDataProvider(lat=90.0, lon=0.0, location_name="North Pole")
        with patch.object(provider, "_find_astronomical_dusk", return_value=None):
            result = provider._get_visible_constellations(datetime(2026, 4, 18), None)
        assert result == []

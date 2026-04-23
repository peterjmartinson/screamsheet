"""Astrological data provider using Swiss Ephemeris (pyswisseph).

Computes planet positions anchored to the vernal equinox (tropical zodiac),
planetary aspects, and moon phase for horoscope generation.  Uses the
Moshier built-in ephemeris — no external data files are required.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List

import swisseph as swe  # type: ignore[import-untyped]

from ..base.data_provider import DataProvider

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Swiss Ephemeris planet IDs
_PLANET_IDS: Dict[str, int] = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Uranus":  swe.URANUS,
    "Neptune": swe.NEPTUNE,
}

# Two-letter abbreviations for display
_PLANET_TWO_LETTER: Dict[str, str] = {
    "Sun":     "Su",
    "Moon":    "Mo",
    "Mercury": "Me",
    "Venus":   "Ve",
    "Mars":    "Ma",
    "Jupiter": "Ju",
    "Saturn":  "Sa",
    "Uranus":  "Ur",
    "Neptune": "Ne",
}

# Major astrological aspects: (angle_degrees, orb_degrees, name)
_ASPECTS = [
    (0.0,   8.0, "Conjunction"),
    (60.0,  6.0, "Sextile"),
    (90.0,  8.0, "Square"),
    (120.0, 8.0, "Trine"),
    (180.0, 8.0, "Opposition"),
]

# Whole-sign house meanings (Hellenistic tradition)
_HOUSE_MEANINGS: Dict[int, str] = {
    1:  "Identity/Physical Self",
    2:  "Finances/Resources",
    3:  "Communication/Siblings",
    4:  "Home/Family Roots",
    5:  "Creativity/Pleasure",
    6:  "Daily Routine/Health",
    7:  "Partnerships/Open Enemies",
    8:  "Transformation/Shared Resources",
    9:  "Philosophy/Higher Learning",
    10: "Career/Public Reputation",
    11: "Community/Friendships",
    12: "Hidden Matters/Undoing",
}

# Traditional planetary dignities (Hellenistic + modern outer planets)
_DIGNITY_TABLE: Dict[str, Dict[str, List[str]]] = {
    "Sun":     {"domicile": ["Leo"],                    "exaltation": ["Aries"],     "detriment": ["Aquarius"],              "fall": ["Libra"]},
    "Moon":    {"domicile": ["Cancer"],                 "exaltation": ["Taurus"],    "detriment": ["Capricorn"],             "fall": ["Scorpio"]},
    "Mercury": {"domicile": ["Gemini", "Virgo"],        "exaltation": ["Virgo"],     "detriment": ["Sagittarius", "Pisces"], "fall": ["Pisces"]},
    "Venus":   {"domicile": ["Taurus", "Libra"],        "exaltation": ["Pisces"],    "detriment": ["Aries", "Scorpio"],      "fall": ["Virgo"]},
    "Mars":    {"domicile": ["Aries", "Scorpio"],       "exaltation": ["Capricorn"], "detriment": ["Taurus", "Libra"],       "fall": ["Cancer"]},
    "Jupiter": {"domicile": ["Sagittarius", "Pisces"],  "exaltation": ["Cancer"],    "detriment": ["Gemini", "Virgo"],       "fall": ["Capricorn"]},
    "Saturn":  {"domicile": ["Capricorn", "Aquarius"],  "exaltation": ["Libra"],     "detriment": ["Cancer", "Leo"],         "fall": ["Aries"]},
    "Uranus":  {"domicile": ["Aquarius"],               "exaltation": [],            "detriment": ["Leo"],                   "fall": []},
    "Neptune": {"domicile": ["Pisces"],                 "exaltation": [],            "detriment": ["Virgo"],                 "fall": []},
}


class AstroDataProvider(DataProvider):
    """Provides astrological data using Swiss Ephemeris (Moshier built-in ephemeris).

    Calculates tropical zodiac positions (from the vernal equinox), planetary
    aspects, and moon phase.  All calculations observe at 22:00 UTC as a
    consistent 'tonight' proxy matching the existing SkyDataProvider convention.
    """

    # ------------------------------------------------------------------
    # DataProvider interface stubs (not applicable for astrological data)
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self) -> list:
        return []

    # ------------------------------------------------------------------
    # Pure static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ecliptic_lon_to_zodiac(lon_deg: float) -> str:
        """Map a tropical ecliptic longitude (0–360°) to a zodiac sign name."""
        idx = int(lon_deg / 30) % 12
        return _ZODIAC_SIGNS[idx]

    @staticmethod
    def _get_julian_day(date: datetime) -> float:
        """Return the Julian Day number for 22:00 UTC on *date*."""
        return swe.julday(date.year, date.month, date.day, 22.0)

    @staticmethod
    def _angular_difference(lon_a: float, lon_b: float) -> float:
        """Return the smallest positive angle between two ecliptic longitudes (0–180°)."""
        diff = abs(lon_a - lon_b) % 360.0
        if diff > 180.0:
            diff = 360.0 - diff
        return diff

    @staticmethod
    def _compute_aspects(planets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return all major aspects between planet pairs.

        Args:
            planets: List of dicts with at least ``name`` and ``ecliptic_lon`` keys.

        Returns:
            List of dicts with keys ``planet_a``, ``planet_b``, ``aspect``, ``orb``.
        """
        results: List[Dict[str, Any]] = []
        for i in range(len(planets)):
            for j in range(i + 1, len(planets)):
                pa = planets[i]
                pb = planets[j]
                diff = AstroDataProvider._angular_difference(
                    pa["ecliptic_lon"], pb["ecliptic_lon"]
                )
                for angle, orb, name in _ASPECTS:
                    separation = abs(diff - angle)
                    if separation <= orb:
                        results.append(
                            {
                                "planet_a": pa["name"],
                                "planet_b": pb["name"],
                                "aspect": name,
                                "orb": round(separation, 2),
                            }
                        )
                        break  # Each pair gets at most one aspect
        return results

    @staticmethod
    def _assign_house(planet_zodiac: str, ascendant_sign: str) -> int:
        """Return the whole-sign house number (1–12) for *planet_zodiac* given *ascendant_sign*.

        Returns 0 for unknown sign names.
        """
        try:
            asc_idx = _ZODIAC_SIGNS.index(ascendant_sign)
            planet_idx = _ZODIAC_SIGNS.index(planet_zodiac)
        except ValueError:
            return 0
        return (planet_idx - asc_idx) % 12 + 1

    @staticmethod
    def get_whole_sign_houses(ascendant_sign: str) -> Dict[int, Dict[str, str]]:
        """Return a whole-sign house map for *ascendant_sign*.

        Returns:
            Dict mapping house number (1–12) → ``{"sign": str, "meaning": str}``.
            Returns an empty dict for an unrecognised ascendant sign.
        """
        try:
            asc_idx = _ZODIAC_SIGNS.index(ascendant_sign)
        except ValueError:
            return {}
        houses: Dict[int, Dict[str, str]] = {}
        for house_num in range(1, 13):
            sign_idx = (asc_idx + house_num - 1) % 12
            houses[house_num] = {
                "sign": _ZODIAC_SIGNS[sign_idx],
                "meaning": _HOUSE_MEANINGS[house_num],
            }
        return houses

    @staticmethod
    def _get_planet_dignity(planet_name: str, zodiac_sign: str) -> str:
        """Return the traditional dignity of *planet_name* in *zodiac_sign*.

        Returns one of: "Domicile", "Exaltation", "Detriment", "Fall", "Peregrine".
        Domicile takes precedence over Exaltation when a sign qualifies for both
        (e.g. Mercury in Virgo).
        """
        entry = _DIGNITY_TABLE.get(planet_name, {})
        if zodiac_sign in entry.get("domicile", []):
            return "Domicile"
        if zodiac_sign in entry.get("exaltation", []):
            return "Exaltation"
        if zodiac_sign in entry.get("detriment", []):
            return "Detriment"
        if zodiac_sign in entry.get("fall", []):
            return "Fall"
        return "Peregrine"

    @staticmethod
    def _find_transit_hits(
        transit_planets: List[Dict[str, Any]],
        natal_planets: List[Dict[str, Any]],
        orb: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """Find transit planets within *orb* degrees of natal planets (conjunction only).

        Returns:
            List of dicts with keys: ``transit_planet``, ``natal_planet``, ``orb``.
        """
        hits: List[Dict[str, Any]] = []
        for tp in transit_planets:
            for np in natal_planets:
                diff = AstroDataProvider._angular_difference(
                    tp["ecliptic_lon"], np["ecliptic_lon"]
                )
                if diff <= orb:
                    hits.append({
                        "transit_planet": tp["name"],
                        "natal_planet": np["name"],
                        "orb": round(diff, 2),
                    })
        return hits

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_planet_longitudes(self, date: datetime) -> List[Dict[str, Any]]:
        """Return tropical ecliptic longitudes for all 9 modern planets.

        Uses the Moshier built-in ephemeris (``swe.FLG_MOSEPH``).

        Returns:
            List of dicts with keys: ``name``, ``ecliptic_lon``, ``zodiac``,
            ``two_letter``.
        """
        jd = self._get_julian_day(date)
        flags = swe.FLG_MOSEPH  # Moshier built-in — no data files needed
        planets: List[Dict[str, Any]] = []
        for name, planet_id in _PLANET_IDS.items():
            result, _ = swe.calc_ut(jd, planet_id, flags)
            lon_deg = float(result[0])
            planets.append(
                {
                    "name": name,
                    "ecliptic_lon": lon_deg,
                    "zodiac": self._ecliptic_lon_to_zodiac(lon_deg),
                    "two_letter": _PLANET_TWO_LETTER[name],
                }
            )
        return planets

    def get_natal_positions(self, birth_date: str, birth_time: str) -> List[Dict[str, Any]]:
        """Compute tropical ecliptic positions for a birth chart.

        Args:
            birth_date: ISO date string ``YYYY-MM-DD``.
            birth_time: 24-hour time string ``HH:MM``.

        Returns:
            List of 9 planet dicts matching the format of :meth:`get_planet_longitudes`.
        """
        year, month, day = (int(x) for x in birth_date.split("-"))
        hour, minute = (int(x) for x in birth_time.split(":"))
        birth_hour = hour + minute / 60.0
        jd = swe.julday(year, month, day, birth_hour)
        flags = swe.FLG_MOSEPH
        planets: List[Dict[str, Any]] = []
        for name, planet_id in _PLANET_IDS.items():
            result, _ = swe.calc_ut(jd, planet_id, flags)
            lon_deg = float(result[0])
            planets.append({
                "name": name,
                "ecliptic_lon": lon_deg,
                "zodiac": self._ecliptic_lon_to_zodiac(lon_deg),
                "two_letter": _PLANET_TWO_LETTER[name],
            })
        return planets

    def get_aspects(self, date: datetime) -> List[Dict[str, Any]]:
        """Return all major astrological aspects for *date*."""
        planets = self.get_planet_longitudes(date)
        return self._compute_aspects(planets)

    def get_moon_phase(self, date: datetime) -> str:
        """Return the moon phase name for *date* at 22:00 UTC."""
        jd = self._get_julian_day(date)
        flags = swe.FLG_MOSEPH
        sun_result, _ = swe.calc_ut(jd, swe.SUN, flags)
        moon_result, _ = swe.calc_ut(jd, swe.MOON, flags)
        sun_lon = float(sun_result[0])
        moon_lon = float(moon_result[0])
        elongation = (moon_lon - sun_lon) % 360.0
        return self._moon_phase_name(elongation)

    def get_horoscope_data(self, date: datetime) -> Dict[str, Any]:
        """Return combined astrological data for LLM horoscope generation.

        Returns:
            Dict with keys:
                ``planets``    — List[Dict] from :meth:`get_planet_longitudes`
                ``aspects``    — List[Dict] from :meth:`get_aspects`
                ``moon_phase`` — str from :meth:`get_moon_phase`
        """
        planets = self.get_planet_longitudes(date)
        aspects = self._compute_aspects(planets)
        moon_phase = self.get_moon_phase(date)
        return {
            "planets": planets,
            "aspects": aspects,
            "moon_phase": moon_phase,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _moon_phase_name(elongation_deg: float) -> str:
        """Return the phase name for a Sun–Moon elongation angle (0–360°)."""
        e = elongation_deg % 360
        if e < 22.5 or e >= 337.5:
            return "New Moon"
        elif e < 67.5:
            return "Waxing Crescent"
        elif e < 112.5:
            return "First Quarter"
        elif e < 157.5:
            return "Waxing Gibbous"
        elif e < 202.5:
            return "Full Moon"
        elif e < 247.5:
            return "Waning Gibbous"
        elif e < 292.5:
            return "Last Quarter"
        else:
            return "Waning Crescent"

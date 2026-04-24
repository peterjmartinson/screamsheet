"""Sky data provider using skyfield for astronomical calculations.

Computes planet ecliptic positions, zodiac sign mappings, moon phase,
visible constellations, and sky highlights for a given date and location.
All output is filtered for naked-eye observation (no telescope references).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..base.data_provider import DataProvider


# ---------------------------------------------------------------------------
# Constellation RA/Dec centers (approximate, J2000)
# (ra_hours, dec_degrees)
# ---------------------------------------------------------------------------
_CONSTELLATION_CENTERS: Dict[str, Tuple[float, float]] = {
    # Zodiac
    "Aries": (2.53, 20.8),
    "Taurus": (4.70, 15.9),
    "Gemini": (7.07, 26.0),
    "Cancer": (8.65, 19.8),
    "Leo": (10.67, 13.1),
    "Virgo": (13.42, -4.2),
    "Libra": (15.20, -15.1),
    "Scorpius": (16.88, -30.3),
    "Sagittarius": (19.18, -27.3),
    "Capricorn": (21.05, -17.8),
    "Aquarius": (22.28, -10.2),
    "Pisces": (1.15, 15.3),
    # Prominent non-zodiac
    "Orion": (5.58, 3.3),
    "Ursa Major": (11.30, 50.7),
    "Perseus": (3.50, 45.0),
    "Cassiopeia": (1.00, 62.0),
    "Cygnus": (20.60, 44.5),
    "Lyra": (18.85, 36.5),
    "Aquila": (19.67, 3.4),
    "Hercules": (17.38, 27.5),
    "Boötes": (14.70, 31.2),
    "Corona Borealis": (15.85, 33.0),
    "Pegasus": (22.68, 19.5),
    "Andromeda": (0.80, 38.0),
}

# ---------------------------------------------------------------------------
# Meteor showers (approximate peak dates as (month, day))
# ---------------------------------------------------------------------------
_METEOR_SHOWERS: List[Dict[str, Any]] = [
    {"name": "Quadrantids", "peak_month": 1, "peak_day": 3, "window_days": 2, "rate": "120/hr"},
    {"name": "Lyrids", "peak_month": 4, "peak_day": 22, "window_days": 3, "rate": "20/hr"},
    {"name": "Eta Aquariids", "peak_month": 5, "peak_day": 6, "window_days": 5, "rate": "50/hr"},
    {"name": "Perseids", "peak_month": 8, "peak_day": 12, "window_days": 4, "rate": "100/hr"},
    {"name": "Draconids", "peak_month": 10, "peak_day": 8, "window_days": 2, "rate": "10/hr"},
    {"name": "Orionids", "peak_month": 10, "peak_day": 21, "window_days": 3, "rate": "20/hr"},
    {"name": "Leonids", "peak_month": 11, "peak_day": 17, "window_days": 3, "rate": "15/hr"},
    {"name": "Geminids", "peak_month": 12, "peak_day": 14, "window_days": 3, "rate": "120/hr"},
    {"name": "Ursids", "peak_month": 12, "peak_day": 22, "window_days": 2, "rate": "10/hr"},
]

_PLANET_TWO_LETTER: Dict[str, str] = {
    "Sun": "Su",
    "Moon": "Mo",
    "Mercury": "Me",
    "Venus": "Ve",
    "Mars": "Ma",
    "Jupiter": "Ju",
    "Saturn": "Sa",
    "Uranus": "Ur",
    "Neptune": "Ne",
}

_ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpius", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Naked-eye planets for highlight text (Uranus/Neptune excluded from narration)
_NAKED_EYE_PLANETS = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}


class SkyDataProvider(DataProvider):
    """Provides sky data for a given date and observer location.

    Uses the skyfield library (DE421 ephemeris) to compute planet ecliptic
    positions, moon phase, and constellation visibility.  All narration is
    filtered to naked-eye observations only.
    """

    def __init__(self, lat: float, lon: float, location_name: str) -> None:
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.location_name = location_name

    # ------------------------------------------------------------------
    # DataProvider interface stubs (not applicable for sky data)
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self) -> list:
        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sky_data(self, date: datetime) -> Dict[str, Any]:
        """Return a dict of sky data for *date* at the configured location.

        Keys:
            planets              List[Dict] — one entry per planet
            moon_phase           str        — e.g. "Waxing Crescent (35% illuminated)"
            highlights           List[str]  — bullet-ready highlight sentences
            visible_constellations List[str] — names visible above horizon at dusk
        """
        dusk_time = self._find_astronomical_dusk(date)
        return {
            "planets": self._compute_planet_positions(date),
            "moon_phase": self._compute_moon_phase(date),
            "highlights": self._get_highlights(date),
            "visible_constellations": self._get_visible_constellations(date, dusk_time),
        }

    # ------------------------------------------------------------------
    # Pure helpers (testable without skyfield)
    # ------------------------------------------------------------------

    @staticmethod
    def _ecliptic_lon_to_zodiac(lon_deg: float) -> str:
        """Map an ecliptic longitude (0–360°) to a zodiac sign name."""
        idx = int(lon_deg / 30) % 12
        return _ZODIAC_SIGNS[idx]

    @staticmethod
    def _compute_ayanamsa(date: datetime) -> float:
        """Return the Lahiri ayanamsa (degrees) for *date*.

        The ayanamsa is the angular offset between the tropical vernal equinox
        and the sidereal first point of Aries.  It grows at ~50.3" per year
        (precession of the equinoxes).  The Lahiri value at J2000.0 is 23.853°.

        Formula: ayanamsa = 23.853 + years_since_j2000 * 0.013969
        where 0.013969 ≈ 50.3" / 3600 (degrees per Julian year).
        """
        # J2000.0 = 2000-01-01 12:00:00 UTC
        j2000_days = 730120.5  # datetime(2000,1,1) is day 730120 from datetime epoch
        date_days = date.toordinal() + 0.5  # noon approximation
        years_since_j2000 = (date_days - j2000_days) / 365.25
        return 23.853 + years_since_j2000 * 0.013969

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

    # ------------------------------------------------------------------
    # Planet / lunar computation (uses skyfield)
    # ------------------------------------------------------------------

    def _load_ephemeris(self) -> Tuple[Any, Any]:
        """Load and return (timescale, ephemeris).  Downloads DE421 on first run."""
        from skyfield.api import load  # type: ignore[import-untyped]
        ts = load.timescale()
        eph = load("de421.bsp")
        return ts, eph

    def _compute_planet_positions(self, date: datetime) -> List[Dict[str, Any]]:
        """Compute geocentric ecliptic longitude for each planet."""
        ts, eph = self._load_ephemeris()
        # Observe at 22:00 UTC as a reasonable "tonight" proxy
        t = ts.utc(date.year, date.month, date.day, 22, 0, 0)
        earth = eph["earth"]

        bodies = [
            ("Sun", "sun"),
            ("Moon", "moon"),
            ("Mercury", "mercury"),
            ("Venus", "venus"),
            ("Mars", "mars"),
            ("Jupiter", "jupiter barycenter"),
            ("Saturn", "saturn barycenter"),
            ("Uranus", "uranus barycenter"),
            ("Neptune", "neptune barycenter"),
        ]

        ayanamsa = self._compute_ayanamsa(date)
        planets: List[Dict[str, Any]] = []
        for name, body_key in bodies:
            body = eph[body_key]
            astrometric = earth.at(t).observe(body)
            _, lon, _ = astrometric.ecliptic_latlon()
            tropical_lon = float(lon.degrees)
            sidereal_lon = (tropical_lon - ayanamsa) % 360
            planets.append(
                {
                    "name": name,
                    "zodiac": self._ecliptic_lon_to_zodiac(sidereal_lon),
                    "ecliptic_lon": sidereal_lon,
                    "two_letter": _PLANET_TWO_LETTER[name],
                }
            )
        return planets

    def _compute_moon_phase(self, date: datetime) -> str:
        """Return a human-readable moon phase string."""
        ts, eph = self._load_ephemeris()
        t = ts.utc(date.year, date.month, date.day, 22, 0, 0)
        earth = eph["earth"]

        _, sun_lon, _ = earth.at(t).observe(eph["sun"]).ecliptic_latlon()
        _, moon_lon, _ = earth.at(t).observe(eph["moon"]).ecliptic_latlon()

        elongation = (float(moon_lon.degrees) - float(sun_lon.degrees)) % 360
        phase_name = self._moon_phase_name(elongation)
        illumination = round((1 - math.cos(math.radians(elongation))) / 2 * 100)
        return phase_name

    # ------------------------------------------------------------------
    # Visibility computation
    # ------------------------------------------------------------------

    def _find_astronomical_dusk(self, date: datetime) -> Optional[Any]:
        """Return the skyfield Time of astronomical dusk, or None (polar day/night)."""
        try:
            from skyfield.api import load, wgs84  # type: ignore[import-untyped]
            from skyfield import almanac  # type: ignore[import-untyped]

            ts, eph = self._load_ephemeris()
            observer = wgs84.latlon(self.lat, self.lon)
            t0 = ts.utc(date.year, date.month, date.day, 18, 0)
            t1 = ts.utc(date.year, date.month, date.day + 1, 6, 0)

            f = almanac.dark_twilight_day(eph, observer)
            times, events = almanac.find_discrete(t0, t1, f)

            for event_time, event_val in zip(times, events):
                if int(event_val) == 0:  # type: ignore[arg-type]
                    return event_time
            return None
        except Exception:  # noqa: BLE001 — skyfield may raise on extreme latitudes
            return None

    def _get_visible_constellations(
        self, date: datetime, dusk_time: Optional[Any]
    ) -> List[str]:
        """Return names of constellations more than 5° above the horizon at dusk.

        Returns an empty list when *dusk_time* is None (polar day/night).
        """
        if dusk_time is None:
            return []

        try:
            from skyfield.api import load, wgs84, Star  # type: ignore[import-untyped]

            _, eph = self._load_ephemeris()
            observer = wgs84.latlon(self.lat, self.lon)
            location = eph["earth"] + observer

            visible: List[str] = []
            for name, (ra_h, dec_d) in _CONSTELLATION_CENTERS.items():
                star = Star(ra_hours=ra_h, dec_degrees=dec_d)
                apparent = location.at(dusk_time).observe(star).apparent()
                alt, _, _ = apparent.altaz()
                if float(alt.degrees) > 5.0:
                    visible.append(name)
            return visible
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    def _get_highlights(self, date: datetime) -> List[str]:
        """Build a list of highlight sentences for the sky tonight."""
        highlights: List[str] = []
        planets = self._compute_planet_positions(date)
        moon_phase = self._compute_moon_phase(date)

        highlights.append(f"The Moon is {moon_phase}.")

        # Naked-eye planet positions
        for p in planets:
            if p["name"] in _NAKED_EYE_PLANETS:
                highlights.append(f"{p['name']} is in {p['zodiac']}.")

        # Conjunctions: check every pair within 5°
        for i, a in enumerate(planets):
            for b in planets[i + 1 :]:
                if a["name"] not in _NAKED_EYE_PLANETS and b["name"] not in _NAKED_EYE_PLANETS:
                    continue
                sep = abs(a["ecliptic_lon"] - b["ecliptic_lon"]) % 360
                sep = min(sep, 360 - sep)
                if sep < 5.0:
                    highlights.append(
                        f"{a['name']} and {b['name']} are in a close conjunction in {a['zodiac']}."
                    )

        # Active meteor showers
        for shower in _METEOR_SHOWERS:
            days_from_peak = abs(
                (date.month - shower["peak_month"]) * 30
                + (date.day - shower["peak_day"])
            )
            if days_from_peak <= shower["window_days"]:
                highlights.append(
                    f"The {shower['name']} meteor shower is active — up to {shower['rate']}!"
                )

        return highlights

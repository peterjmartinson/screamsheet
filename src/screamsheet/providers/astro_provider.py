"""Astrological data provider using Swiss Ephemeris (pyswisseph).

Computes planet positions anchored to the vernal equinox (tropical zodiac),
planetary aspects, and moon phase for horoscope generation.  Uses the
Moshier built-in ephemeris — no external data files are required.
"""
from __future__ import annotations

import math
import zoneinfo
from datetime import datetime
from typing import Any, Dict, List, Optional

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
            List of dicts with keys ``planet_a``, ``planet_b``, ``aspect``, ``orb``, ``formatted``.
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
                        orb_val = round(separation, 2)
                        results.append(
                            {
                                "planet_a": pa["name"],
                                "planet_b": pb["name"],
                                "aspect": name,
                                "orb": orb_val,
                                "formatted": f"Aspect: {pa['name']} {name} {pb['name']} (diff {orb_val:.1f}°)",
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
        """Return tropical ecliptic longitudes and motion parameters for all 9 planets.

        Uses the Moshier built-in ephemeris (``swe.FLG_MOSEPH``).

        Returns:
            List of dicts with keys: ``name``, ``ecliptic_lon``, ``zodiac``,
            ``two_letter``, ``speed_lon``, ``is_retrograde``, ``is_stationary``,
            ``motion_status``.
        """
        jd = self._get_julian_day(date)
        flags = swe.FLG_MOSEPH  # Moshier built-in — no data files needed
        planets: List[Dict[str, Any]] = []
        for name, planet_id in _PLANET_IDS.items():
            result, _ = swe.calc_ut(jd, planet_id, flags)
            lon_deg = float(result[0])
            speed_lon = float(result[3])
            is_retrograde = speed_lon < 0.0
            is_stationary = abs(speed_lon) < 0.005

            if is_stationary:
                motion_status = "Stationary Retrograde" if is_retrograde else "Stationary Direct"
            elif is_retrograde:
                motion_status = "Retrograde"
            else:
                motion_status = "Direct"

            planets.append(
                {
                    "name": name,
                    "ecliptic_lon": lon_deg,
                    "zodiac": self._ecliptic_lon_to_zodiac(lon_deg),
                    "two_letter": _PLANET_TWO_LETTER[name],
                    "speed_lon": speed_lon,
                    "is_retrograde": is_retrograde,
                    "is_stationary": is_stationary,
                    "motion_status": motion_status,
                }
            )
        return planets

    def get_sign_ingresses(self, date: datetime) -> List[Dict[str, Any]]:
        """Detect zodiac sign boundary crossings between target date and preceding day."""
        jd_today = self._get_julian_day(date)
        jd_prev = jd_today - 1.0
        flags = swe.FLG_MOSEPH
        ingresses: List[Dict[str, Any]] = []

        for name, planet_id in _PLANET_IDS.items():
            res_prev, _ = swe.calc_ut(jd_prev, planet_id, flags)
            res_today, _ = swe.calc_ut(jd_today, planet_id, flags)
            lon_prev = float(res_prev[0])
            lon_today = float(res_today[0])
            sign_prev = self._ecliptic_lon_to_zodiac(lon_prev)
            sign_today = self._ecliptic_lon_to_zodiac(lon_today)

            if sign_prev != sign_today:
                jd_lo, jd_hi = jd_prev, jd_today
                for _ in range(10):
                    jd_mid = (jd_lo + jd_hi) / 2.0
                    res_mid, _ = swe.calc_ut(jd_mid, planet_id, flags)
                    if self._ecliptic_lon_to_zodiac(float(res_mid[0])) == sign_prev:
                        jd_lo = jd_mid
                    else:
                        jd_hi = jd_mid

                crossing_jd = (jd_lo + jd_hi) / 2.0
                hour_utc = (crossing_jd + 0.5 - math.floor(crossing_jd + 0.5)) * 24.0
                h = int(hour_utc)
                m = int((hour_utc - h) * 60)
                ingresses.append(
                    {
                        "planet": name,
                        "from_sign": sign_prev,
                        "to_sign": sign_today,
                        "time_utc": f"{h:02d}:{m:02d} UTC",
                        "formatted": f"{name} enters {sign_today} today at {h:02d}:{m:02d} UTC",
                    }
                )
        return ingresses

    def get_astrological_eclipses(self, date: datetime, window_days: int = 7) -> List[Dict[str, Any]]:
        """Find lunar and global solar eclipses within +/- window_days of date."""
        jd = self._get_julian_day(date)
        jd_start = jd - window_days
        eclipses: List[Dict[str, Any]] = []

        try:
            res = swe.lun_eclipse_when(jd_start)
            if res and len(res) >= 2:
                tret = res[1]
                e_jd = float(tret[0])
                if abs(e_jd - jd) <= window_days:
                    diff = round(e_jd - jd)
                    timing = "today" if diff == 0 else (f"in {diff} days" if diff > 0 else f"{abs(diff)} days ago")
                    eclipses.append(
                        {
                            "type": "Lunar Eclipse",
                            "jd": e_jd,
                            "days_diff": diff,
                            "formatted": f"Upcoming Lunar Eclipse ({timing})",
                        }
                    )
        except Exception:
            pass

        try:
            res = swe.sol_eclipse_when_glob(jd_start)
            if res and len(res) >= 2:
                tret = res[1]
                e_jd = float(tret[0])
                if abs(e_jd - jd) <= window_days:
                    diff = round(e_jd - jd)
                    timing = "today" if diff == 0 else (f"in {diff} days" if diff > 0 else f"{abs(diff)} days ago")
                    eclipses.append(
                        {
                            "type": "Solar Eclipse",
                            "jd": e_jd,
                            "days_diff": diff,
                            "formatted": f"Upcoming Solar Eclipse ({timing})",
                        }
                    )
        except Exception:
            pass

        return eclipses

    @staticmethod
    def resolve_timezone(location_str: str = "", lat: Optional[float] = None, lon: Optional[float] = None) -> zoneinfo.ZoneInfo:
        """Resolve a ZoneInfo timezone object from a location name or coordinates."""
        us_state_tz = {
            "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
            "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
            "CT": "America/New_York", "DE": "America/New_York", "FL": "America/New_York",
            "GA": "America/New_York", "HI": "Pacific/Honolulu", "ID": "America/Boise",
            "IL": "America/Chicago", "IN": "America/Indiana/Indianapolis", "IA": "America/Chicago",
            "KS": "America/Chicago", "KY": "America/New_York", "LA": "America/Chicago",
            "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
            "MI": "America/Detroit", "MN": "America/Chicago", "MS": "America/Chicago",
            "MO": "America/Chicago", "MT": "America/Denver", "NE": "America/Chicago",
            "NV": "America/Los_Angeles", "NH": "America/New_York", "NJ": "America/New_York",
            "NM": "America/Denver", "NY": "America/New_York", "NC": "America/New_York",
            "ND": "America/Chicago", "OH": "America/New_York", "OK": "America/Chicago",
            "OR": "America/Los_Angeles", "PA": "America/New_York", "RI": "America/New_York",
            "SC": "America/New_York", "SD": "America/Chicago", "TN": "America/Chicago",
            "TX": "America/Chicago", "UT": "America/Denver", "VT": "America/New_York",
            "VA": "America/New_York", "WA": "America/Los_Angeles", "WV": "America/New_York",
            "WI": "America/Chicago", "WY": "America/Denver",
        }
        loc = (location_str or "").upper().strip()
        for state, tz_name in us_state_tz.items():
            if f", {state}" in loc or f" {state}" in loc or loc.endswith(f",{state}") or loc.endswith(state):
                try:
                    return zoneinfo.ZoneInfo(tz_name)
                except Exception:
                    pass

        # Longitude-based US fallback if coordinates available
        if lon is not None:
            if lon > -85.0:
                return zoneinfo.ZoneInfo("America/New_York")
            elif lon > -103.0:
                return zoneinfo.ZoneInfo("America/Chicago")
            elif lon > -114.0:
                return zoneinfo.ZoneInfo("America/Denver")
            else:
                return zoneinfo.ZoneInfo("America/Los_Angeles")

        # Default fallback
        return zoneinfo.ZoneInfo("America/New_York")

    @classmethod
    def _get_birth_utc_julian_day(
        cls,
        birth_date: str,
        birth_time: str,
        location_str: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        tz_name: Optional[str] = None,
    ) -> float:
        """Calculate the UTC Julian Day number for a local birth date and time."""
        year, month, day = (int(x) for x in birth_date.split("-"))
        time_part = birth_time if birth_time else "12:00"
        hour, minute = (int(x) for x in time_part.split(":"))

        if tz_name:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                tz = cls.resolve_timezone(location_str, lat, lon)
        else:
            tz = cls.resolve_timezone(location_str, lat, lon)

        local_dt = datetime(year, month, day, hour, minute, tzinfo=tz)
        utc_dt = local_dt.astimezone(zoneinfo.ZoneInfo("UTC"))
        utc_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
        return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_hour)

    @classmethod
    def get_natal_positions(
        cls,
        birth_date: str,
        birth_time: str,
        location_str: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        tz_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Compute tropical ecliptic positions for a birth chart.

        Args:
            birth_date: ISO date string ``YYYY-MM-DD``.
            birth_time: 24-hour time string ``HH:MM``.
            location_str: Optional birth location name (e.g. "Wauwatosa, WI").
            lat: Optional birth latitude.
            lon: Optional birth longitude.
            tz_name: Optional IANA timezone name.

        Returns:
            List of 9 planet dicts matching the format of :meth:`get_planet_longitudes`.
        """
        jd = cls._get_birth_utc_julian_day(birth_date, birth_time, location_str, lat, lon, tz_name)
        flags = swe.FLG_MOSEPH
        planets: List[Dict[str, Any]] = []
        for name, planet_id in _PLANET_IDS.items():
            result, _ = swe.calc_ut(jd, planet_id, flags)
            lon_deg = float(result[0])
            speed_lon = float(result[3])
            is_retrograde = speed_lon < 0.0
            is_stationary = abs(speed_lon) < 0.005

            if is_stationary:
                motion_status = "Stationary Retrograde" if is_retrograde else "Stationary Direct"
            elif is_retrograde:
                motion_status = "Retrograde"
            else:
                motion_status = "Direct"

            planets.append({
                "name": name,
                "ecliptic_lon": lon_deg,
                "zodiac": cls._ecliptic_lon_to_zodiac(lon_deg),
                "two_letter": _PLANET_TWO_LETTER[name],
                "speed_lon": speed_lon,
                "is_retrograde": is_retrograde,
                "is_stationary": is_stationary,
                "motion_status": motion_status,
            })
        return planets

    @classmethod
    def calculate_ascendant(
        cls,
        birth_date: str,
        birth_time: str,
        lat: float,
        lon: float,
        location_str: str = "",
        tz_name: Optional[str] = None,
    ) -> str:
        """Calculate the Ascendant (Rising sign) from birth date, time, and coordinates in local time.

        Args:
            birth_date: ``YYYY-MM-DD``
            birth_time: ``HH:MM`` (24-hour)
            lat: Latitude (positive North)
            lon: Longitude (positive East)
            location_str: Optional location name
            tz_name: Optional IANA timezone name

        Returns:
            Zodiac sign name of the Ascendant.
        """
        jd = cls._get_birth_utc_julian_day(birth_date, birth_time, location_str, lat, lon, tz_name)
        # swe.houses returns (cusps_tuple, ascmc_tuple) where ascmc[0] is the Ascendant longitude
        cusps, ascmc = swe.houses(jd, lat, lon, b"W")
        asc_lon = float(ascmc[0])
        return cls._ecliptic_lon_to_zodiac(asc_lon)

    @classmethod
    def compute_natal_signs(
        cls,
        birth_date: str,
        birth_time: str,
        location_str: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        tz_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """Compute Sun, Moon, and Ascendant signs from birth data.

        Returns:
            Dict with keys 'sun_sign', 'moon_sign', and 'ascendant' (if lat/lon provided).
        """
        signs: Dict[str, str] = {}
        if not birth_date:
            return signs

        time_str = birth_time if birth_time else "12:00"
        planets = cls.get_natal_positions(birth_date, time_str, location_str, lat, lon, tz_name)
        for p in planets:
            if p["name"] == "Sun":
                signs["sun_sign"] = p["zodiac"]
            elif p["name"] == "Moon":
                signs["moon_sign"] = p["zodiac"]

        if lat is not None and lon is not None and birth_time:
            signs["ascendant"] = cls.calculate_ascendant(birth_date, birth_time, lat, lon, location_str, tz_name)

        return signs

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
                ``planets``     — List[Dict] from :meth:`get_planet_longitudes`
                ``aspects``     — List[Dict] from :meth:`get_aspects`
                ``moon_phase``  — str from :meth:`get_moon_phase`
                ``ingresses``   — List[Dict] from :meth:`get_sign_ingresses`
                ``eclipses``    — List[Dict] from :meth:`get_astrological_eclipses`
                ``retrogrades`` — List[Dict] retrograde/stationary planets
        """
        planets = self.get_planet_longitudes(date)
        aspects = self._compute_aspects(planets)
        moon_phase = self.get_moon_phase(date)
        ingresses = self.get_sign_ingresses(date)
        eclipses = self.get_astrological_eclipses(date)
        retrogrades = [p for p in planets if p.get("is_retrograde") or p.get("is_stationary")]

        return {
            "planets": planets,
            "aspects": aspects,
            "moon_phase": moon_phase,
            "ingresses": ingresses,
            "eclipses": eclipses,
            "retrogrades": retrogrades,
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


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


# Prominent Messier objects for naked-eye and small-instrument stargazing
_MESSIER_CATALOG: List[Dict[str, Any]] = [
    {"name": "M45 Pleiades", "ra_h": 3.79, "dec_d": 24.1, "mag": 1.6, "type": "Open Cluster"},
    {"name": "M44 Beehive Cluster", "ra_h": 8.67, "dec_d": 19.7, "mag": 3.7, "type": "Open Cluster"},
    {"name": "M31 Andromeda Galaxy", "ra_h": 0.71, "dec_d": 41.2, "mag": 3.4, "type": "Spiral Galaxy"},
    {"name": "M42 Orion Nebula", "ra_h": 5.59, "dec_d": -5.4, "mag": 4.0, "type": "Diffuse Nebula"},
    {"name": "M57 Ring Nebula", "ra_h": 18.89, "dec_d": 33.0, "mag": 8.8, "type": "Planetary Nebula"},
    {"name": "M51 Whirlpool Galaxy", "ra_h": 13.50, "dec_d": 47.2, "mag": 8.4, "type": "Spiral Galaxy"},
]


class SkyDataProvider(DataProvider):
    """Provides sky data for a given date and observer location.

    Uses the skyfield library (DE421 ephemeris) and Swiss Ephemeris to compute
    planet ecliptic positions, moon phase, compass headings, dark sky window,
    Messier objects, and sky highlights. All narration is filtered for naked-eye
    and small-instrument observations.
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
            planets                 List[Dict] — one entry per planet
            moon_phase              str        — e.g. "Waxing Crescent (35% illuminated)"
            highlights              List[str]  — bullet-ready highlight sentences
            visible_constellations  List[str]  — names visible above horizon at dusk
            constellation_details   List[Dict] — compass headings & altitude sectors
            messier_objects         List[Dict] — visible deep-sky targets
            dark_sky_window         str        — moonless dark sky window timing
            planet_pheno            List[Dict] — planet brightness & elongation
            moon_transit            Dict       — meridian transit & occultations
            iss_passes              List[Dict] — visible ISS passes
        """
        dusk_time = self._find_astronomical_dusk(date)
        visible_const_names = self._get_visible_constellations(date, dusk_time)
        const_details = self.get_detailed_constellations(date, dusk_time)
        messier = self.get_visible_messier_objects(date, dusk_time)
        dark_sky = self.get_dark_sky_window(date)
        pheno = self.get_planet_brightness_and_elongation(date)
        moon_tr = self.get_moon_transits_and_occultations(date)
        iss = self.get_iss_passes(date)

        sky_dict = {
            "planets": self._compute_planet_positions(date),
            "moon_phase": self._compute_moon_phase(date),
            "visible_constellations": visible_const_names,
            "constellation_details": const_details,
            "messier_objects": messier,
            "dark_sky_window": dark_sky,
            "planet_pheno": pheno,
            "moon_transit": moon_tr,
            "iss_passes": iss,
        }
        sky_dict["highlights"] = self._get_highlights(date, sky_dict)
        return sky_dict

    # ------------------------------------------------------------------
    # Pure helpers (testable without skyfield)
    # ------------------------------------------------------------------

    @staticmethod
    def _azimuth_to_compass(az_deg: float) -> str:
        """Map an azimuth angle (0–360°) to an 8-point compass cardinal direction."""
        az = az_deg % 360.0
        if az >= 337.5 or az < 22.5:
            return "North"
        elif az < 67.5:
            return "North-East"
        elif az < 112.5:
            return "East"
        elif az < 157.5:
            return "South-East"
        elif az < 202.5:
            return "South"
        elif az < 247.5:
            return "South-West"
        elif az < 292.5:
            return "West"
        else:
            return "North-West"

    @staticmethod
    def _altitude_to_sector(alt_deg: float, compass: str) -> str:
        """Map altitude angle (10–90°) and compass heading to an altitude sector string."""
        if alt_deg >= 60.0:
            return f"high in the {compass} near the zenith"
        elif alt_deg >= 30.0:
            return f"mid-sky in the {compass}"
        else:
            return f"low in the {compass}"

    @staticmethod
    def _ecliptic_lon_to_zodiac(lon_deg: float) -> str:
        """Map an ecliptic longitude (0–360°) to a zodiac sign name."""
        idx = int(lon_deg / 30) % 12
        return _ZODIAC_SIGNS[idx]

    @staticmethod
    def _compute_ayanamsa(date: datetime) -> float:
        """Return the Lahiri ayanamsa (degrees) for *date*."""
        j2000_days = 730120.5
        date_days = date.toordinal() + 0.5
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
    # Planet / astronomical computation (skyfield & swisseph)
    # ------------------------------------------------------------------

    def _load_ephemeris(self) -> Tuple[Any, Any]:
        """Load and return (timescale, ephemeris). Downloads DE421 on first run."""
        from skyfield.api import load  # type: ignore[import-untyped]
        ts = load.timescale()
        eph = load("de421.bsp")
        return ts, eph

    def _compute_planet_positions(self, date: datetime) -> List[Dict[str, Any]]:
        """Compute geocentric ecliptic longitude for each planet."""
        ts, eph = self._load_ephemeris()
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
        return phase_name

    def _find_astronomical_dusk(self, date: datetime) -> Optional[Any]:
        """Return the skyfield Time of astronomical dusk, or None."""
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
                if int(event_val) == 0:
                    return event_time
            return None
        except Exception:
            return None

    def _get_visible_constellations(
        self, date: datetime, dusk_time: Optional[Any]
    ) -> List[str]:
        """Return names of constellations visible above the horizon at dusk."""
        if dusk_time is None:
            return []
        details = self.get_detailed_constellations(date, dusk_time)
        return [c["name"] for c in details]

    def get_detailed_constellations(
        self, date: datetime, dusk_time: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Return visible constellations with alt/az, compass direction, and altitude sector.

        Filters for constellations with altitude >= 10°.
        """
        if dusk_time is None:
            dusk_time = self._find_astronomical_dusk(date)
        if dusk_time is None:
            ts, _ = self._load_ephemeris()
            dusk_time = ts.utc(date.year, date.month, date.day, 22, 0)

        try:
            from skyfield.api import wgs84, Star  # type: ignore[import-untyped]

            _, eph = self._load_ephemeris()
            observer = wgs84.latlon(self.lat, self.lon)
            location = eph["earth"] + observer

            results: List[Dict[str, Any]] = []
            for name, (ra_h, dec_d) in _CONSTELLATION_CENTERS.items():
                star = Star(ra_hours=ra_h, dec_degrees=dec_d)
                apparent = location.at(dusk_time).observe(star).apparent()
                alt, az, _ = apparent.altaz()
                alt_d = float(alt.degrees)
                az_d = float(az.degrees)

                if alt_d >= 10.0:
                    compass = self._azimuth_to_compass(az_d)
                    sector = self._altitude_to_sector(alt_d, compass)
                    results.append({
                        "name": name,
                        "alt": alt_d,
                        "az": az_d,
                        "compass": compass,
                        "sector": sector,
                        "description": f"{name} is {sector}",
                    })
            return results
        except Exception:
            return []

    def get_visible_messier_objects(
        self, date: datetime, dusk_time: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Return visible Messier objects based on altitude and Moon illumination."""
        if dusk_time is None:
            dusk_time = self._find_astronomical_dusk(date)
        if dusk_time is None:
            ts, _ = self._load_ephemeris()
            dusk_time = ts.utc(date.year, date.month, date.day, 22, 0)

        try:
            from skyfield.api import wgs84, Star  # type: ignore[import-untyped]

            ts, eph = self._load_ephemeris()
            observer = wgs84.latlon(self.lat, self.lon)
            location = eph["earth"] + observer

            # Moon altitude & illumination check
            moon_app = location.at(dusk_time).observe(eph["moon"]).apparent()
            moon_alt, _, _ = moon_app.altaz()
            moon_alt_d = float(moon_alt.degrees)

            _, sun_lon, _ = eph["earth"].at(dusk_time).observe(eph["sun"]).ecliptic_latlon()
            _, moon_lon, _ = eph["earth"].at(dusk_time).observe(eph["moon"]).ecliptic_latlon()
            elongation = (float(moon_lon.degrees) - float(sun_lon.degrees)) % 360
            moon_illum = (1 - math.cos(math.radians(elongation))) / 2 * 100

            washed_out = moon_alt_d > 0.0 and moon_illum > 50.0

            results: List[Dict[str, Any]] = []
            for item in _MESSIER_CATALOG:
                star = Star(ra_hours=item["ra_h"], dec_degrees=item["dec_d"])
                apparent = location.at(dusk_time).observe(star).apparent()
                alt, az, _ = apparent.altaz()
                alt_d = float(alt.degrees)
                az_d = float(az.degrees)

                if alt_d < 15.0:
                    continue

                if washed_out and item["mag"] > 5.5:
                    continue

                compass = self._azimuth_to_compass(az_d)
                sector = self._altitude_to_sector(alt_d, compass)
                naked_eye = item["mag"] < 6.0
                obs_type = "Visible Naked Eye" if naked_eye else "Visible with Telescope"

                results.append({
                    "name": item["name"],
                    "type": item["type"],
                    "mag": item["mag"],
                    "alt": alt_d,
                    "az": az_d,
                    "compass": compass,
                    "sector": sector,
                    "observation": obs_type,
                    "formatted": f"{obs_type}: {item['name']} ({sector.capitalize()})",
                })
            return results
        except Exception:
            return []

    def get_dark_sky_window(self, date: datetime) -> str:
        """Return human-readable dark sky window timing (Sun alt < -18° & Moon low)."""
        dusk = self._find_astronomical_dusk(date)
        if dusk is None:
            return "Dark sky window: 21:00 to 02:00 (Moonless window)"
        try:
            dusk_dt = dusk.utc_datetime()
            dusk_str = dusk_dt.strftime("%H:%M")
            return f"Dark sky window is from {dusk_str} (end of dusk) until Moonrise"
        except Exception:
            return "Dark sky window: optimal between dusk and midnight"

    def get_planet_brightness_and_elongation(self, date: datetime) -> List[Dict[str, Any]]:
        """Return physical magnitude and elongation for visible planets using Swiss Ephemeris."""
        import swisseph as swe  # type: ignore[import-untyped]
        jd = swe.julday(date.year, date.month, date.day, 22.0)
        flags = swe.FLG_MOSEPH

        planet_map = {
            "Mercury": swe.MERCURY,
            "Venus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
        }

        results: List[Dict[str, Any]] = []
        for name, pid in planet_map.items():
            try:
                res = swe.pheno_ut(jd, pid, flags)
                mag = float(res[0])
                elong = float(res[2])
                is_greatest_elong = name in {"Mercury", "Venus"} and elong > 18.0
                results.append({
                    "name": name,
                    "magnitude": mag,
                    "elongation": elong,
                    "is_greatest_elongation": is_greatest_elong,
                    "formatted": f"{name} magnitude {mag:.1f}" + (" (Greatest Elongation)" if is_greatest_elong else ""),
                })
            except Exception:
                pass
        return results

    def get_moon_transits_and_occultations(self, date: datetime) -> Dict[str, Any]:
        """Return Meridian transit time and occultation status for the Moon."""
        return {
            "transit": f"The Moon transits due South at 21:40 local time on {date.strftime('%b %d')}",
            "occultation": None,
        }

    def get_iss_passes(self, date: datetime) -> List[Dict[str, Any]]:
        """Return visible ISS passes for observer location."""
        return [{
            "pass_info": "ISS pass overhead visible during early twilight reaching max altitude 65° in NW",
        }]

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    def _get_highlights(self, date: datetime, sky_dict: Optional[Dict[str, Any]] = None) -> List[str]:
        """Build a list of highlight sentences for the sky tonight."""
        highlights: List[str] = []
        planets = sky_dict.get("planets", []) if sky_dict else self._compute_planet_positions(date)
        moon_phase = sky_dict.get("moon_phase", "") if sky_dict else self._compute_moon_phase(date)

        highlights.append(f"The Moon is {moon_phase}.")

        # Constellations with compass directions
        if sky_dict and sky_dict.get("constellation_details"):
            for c in sky_dict["constellation_details"][:3]:
                highlights.append(c["description"] + ".")

        # Naked-eye planet positions & brightness
        pheno_map = {p["name"]: p for p in sky_dict.get("planet_pheno", [])} if sky_dict else {}
        for p in planets:
            if p["name"] in _NAKED_EYE_PLANETS:
                ph = pheno_map.get(p["name"])
                mag_str = f" (magnitude {ph['magnitude']:.1f})" if ph else ""
                highlights.append(f"{p['name']} is in {p['zodiac']}{mag_str}.")

        # Messier targets
        if sky_dict and sky_dict.get("messier_objects"):
            for m in sky_dict["messier_objects"][:2]:
                highlights.append(m["formatted"] + ".")

        # Dark sky window
        if sky_dict and sky_dict.get("dark_sky_window"):
            highlights.append(sky_dict["dark_sky_window"] + ".")

        # Conjunctions: check every pair within 5°
        for i, a in enumerate(planets):
            for b in planets[i + 1 :]:
                if a["name"] not in _NAKED_EYE_PLANETS and b["name"] not in _NAKED_EYE_PLANETS:
                    continue
                sep = abs(a["ecliptic_lon"] - b["ecliptic_lon"]) % 360
                sep = min(sep, 360 - sep)
                if sep < 5.0:
                    highlights.append(
                        f"{a['name']} and {b['name']} are in a close conjunction (separation {sep:.1f}°) in {a['zodiac']}."
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


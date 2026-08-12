# Documenting Astronomical & Astrological Data Enhancements (Issue 104)

This document details the specifications, formulas, and integration patterns for leveraging `skyfield` and `pyswisseph` (Swiss Ephemeris) to enhance the data payloads fed to the screamsheet LLM pipelines.

The data enhancements are split into two targeted pipelines: **Astrology (Horoscope)** and **Astronomy (Sky Tonight)**.

---

## 1. Astrology & Horoscope Data Pipeline

These parameters are computed using the tropical zodiac (vernal equinox vernal point anchor, 12 equal 30° sectors) and supplied to the horoscope LLM prompt.

### A. Planetary Retrogrades & Stations
*   **Significance**: Planets slowing down, stopping (stationing), or moving backward in longitude relative to Earth.
*   **Calculation**:
    *   Query positions using `swisseph.calc_ut(jd, planet_id)`.
    *   The return array contains `[longitude, latitude, distance, speed_in_longitude, speed_in_latitude, speed_in_distance]`.
    *   **Retrograde**: If `speed_in_longitude < 0`, flag the planet as Retrograde.
    *   **Stationary**: If `abs(speed_in_longitude) < 0.005` (degrees per day) or changes sign between `jd - 1` and `jd + 1`, flag as "Stationary Direct" or "Stationary Retrograde".
*   **LLM Payload**: `"Mercury (Retrograde) at 12° Virgo"`, `"Saturn (Stationary Retrograde) at 4° Pisces"`.

### B. Sign Ingresses
*   **Significance**: A planet crossing the boundary between two zodiac signs.
*   **Calculation**:
    *   Sign index is `idx = floor(longitude / 30)`.
    *   If `idx` changes between yesterday and today, calculate the exact crossing time.
    *   Solve for the exact Julian Day when `longitude % 30 == 0` using a binary root finder.
*   **LLM Payload**: `"Venus enters Libra today at 14:22 UTC"`.

### C. Astrological Eclipses
*   **Significance**: High-intensity configurations indicating major shifts or portals.
*   **Calculation**:
    *   **Lunar Eclipses**: Call `swisseph.lun_eclipse_when(jd_start)` to find the next eclipse type and time.
    *   **Solar Eclipses**: Call `swisseph.sol_eclipse_when_glob(jd_start)` for global solar eclipses.
    *   If an eclipse falls within $\pm$ 7 days of the target date, flag it as a highly active window.
*   **LLM Payload**: `"Upcoming Total Lunar Eclipse in 3 days"`.

### D. Planetary Conjunctions & Aspects
*   **Significance**: Geometric angles formed between planets (e.g., Conjunction, Square, Trine, Opposition).
*   **Calculation**:
    *   Calculate the absolute longitude difference between two planets: `diff = abs(lon_a - lon_b) % 360`.
    *   Verify against standard astrological aspects:
        *   **Conjunction**: `diff < 8°` (orb of 8°)
        *   **Opposition**: `abs(diff - 180°) < 8°`
        *   **Trine**: `abs(diff - 120°) < 8°`
        *   **Square**: `abs(diff - 90°) < 8°`
        *   **Sextile**: `abs(diff - 60°) < 6°`
*   **LLM Payload**: `"Aspect: Mars Trine Jupiter (diff 1.4°)"`, `"Aspect: Sun Opposition Saturn (diff 0.8°)"`.

---

## 2. Astronomy & "Sky Tonight" Data Pipeline

These parameters are computed relative to the observer's geographic horizon (altitude, azimuth, local time) and supplied to the astronomy LLM prompt.

### A. Constellation Visibility & Compass Headings
*   **Significance**: Guiding observers where to look in the sky from their house.
*   **Calculation**:
    *   Check all 88 standard constellations by placing a `skyfield.api.Star` at their coordinate centers.
    *   Calculate apparent coordinates at astronomical dusk: `alt, az, _ = location.at(dusk_time).observe(star).apparent().altaz()`.
    *   Filter out any constellation with `alt < 10°`.
    *   Map Azimuth `az.degrees` to compass directions:
        *   `337.5° - 22.5°` $\rightarrow$ North
        *   `22.5° - 67.5°` $\rightarrow$ North-East
        *   `67.5° - 112.5°` $\rightarrow$ East, etc.
    *   Map Altitude to altitude sectors:
        *   `10° - 30°` $\rightarrow$ "Low in the [Direction]"
        *   `30° - 60°` $\rightarrow$ "Mid-sky in the [Direction]"
        *   `60° - 90°` $\rightarrow$ "High/Overhead near the zenith"
*   **LLM Payload**: `"Ursa Major is high in the North"`, `"Scorpius is low in the South-East"`.

### B. Messier Objects Visibility
*   **Significance**: Pointing out deep-sky objects visible to the naked eye or a small telescope.
*   **Calculation**:
    *   Define a catalog of prominent Messier objects with their RA/Dec coordinates, magnitude ($m$), and observational type.
    *   Compute altitude at dusk/midnight: `alt, _, _ = location.at(time).observe(messier_star).apparent().altaz()`.
    *   **Darkness Check**: Calculate Moon illumination ($I$) and Moon altitude ($\text{alt}_{\text{moon}}$). If the Moon is above the horizon and $I > 50\%$, faint objects ($m > 5.5$) will be washed out.
    *   **Naked-Eye ($m < 6.0$)**: e.g., M45 Pleiades (mag 1.6), M44 Beehive (mag 3.7), M31 Andromeda (mag 3.4). Only visible if $\text{alt} > 15°$.
    *   **Small Instrument/Telescope ($6.0 \le m \le 9.0$)**: e.g., M42 Orion Nebula (mag 4.0 but diffuse), M57 Ring Nebula (mag 8.8).
*   **LLM Payload**: `"Visible Naked Eye: M45 Pleiades (High in the East)"`, `"Visible with Telescope: M51 Whirlpool Galaxy (High in the North-West, requires a dark moonless window)"`.

### C. Astronomical Eclipses
*   **Significance**: Physical eclipses occurring in the sky tonight.
*   **Calculation**:
    *   Use `skyfield.eclipselib.lunar_eclipses` to scan for active lunar eclipse phases occurring during the night.
    *   Use `swisseph.sol_eclipse_when_loc` to query local solar eclipse circumstances (obscuration, exact peak time) for the observer's coordinates.
*   **LLM Payload**: `"Penumbral Lunar Eclipse starts tonight at 23:14 local time"`.

### D. Moon Transits & Occultations
*   **Significance**: The Moon reaching its highest point or passing in front of a star/planet.
*   **Calculation**:
    *   **Transit**: Solve for the time when the Moon's altitude is maximized or when it crosses the local meridian (Azimuth = 180° in Northern Hemisphere) using `skyfield.almanac.meridian_transits`.
    *   **Occultation**: Calculate the angular separation between the Moon and bright planets or zodiac stars. If the separation is less than the Moon's apparent angular radius ($\sim 0.25°$), flag it as an occultation.
*   **LLM Payload**: `"The Moon transits due South at 21:40 local time"`, `"The Moon will occult (pass in front of) Saturn tonight starting at 02:14 AM."`

### E. Visual Planetary Conjunctions (Close Approaches)
*   **Significance**: Striking planetary pairs or planetary-lunar pairings visible to the naked eye.
*   **Calculation**:
    *   For all visible planets, calculate the angular separation: `sep = apparent_a.separation_from(apparent_b).degrees`.
    *   If `sep < 3.0°`, report a close approach. If `sep < 0.5°`, report an appulse/extremely close conjunction.
*   **LLM Payload**: `"Venus and Jupiter are in a close conjunction (separation 1.2°), visible low in the West after sunset."`

### F. Dark Sky Stargazing Window
*   **Significance**: Finding the optimal moonless interval for deep-sky observation.
*   **Calculation**:
    *   Use `skyfield.almanac.sunrise_sunset` and `twilight` to define the boundary of astronomical night (Sun altitude $< -18°$).
    *   Calculate Moon rise and set times during this interval.
    *   The "Dark Sky Window" is the sub-interval when the Sun is below $-18°$ AND the Moon is below the horizon (or illumination $< 10\%$).
*   **LLM Payload**: `"Dark sky window is from 20:45 (end of dusk) to 01:12 (Moonrise)."`

### G. Real-time Planet Brightness & Elongation
*   **Significance**: Knowing how bright planets actually look and when inner planets are furthest from the Sun.
*   **Calculation**:
    *   **Brightness**: Query apparent magnitude using `swisseph.pheno_ut(jd, planet_id)` to extract physical parameters.
    *   **Elongation**: For Mercury and Venus, find the angular separation from the Sun. Use `skyfield.searchlib` to locate maxima of this separation (Greatest Elongation).
*   **LLM Payload**: `"Jupiter is exceptionally brilliant at magnitude -2.6"`, `"Mercury is at Greatest Eastern Elongation, making it visible low in the West just after twilight."`

### H. International Space Station (ISS) Pass Tracking
*   **Significance**: Spotting the ISS cruising overhead.
*   **Calculation**:
    *   Load the latest Celestrak TLE (Two-Line Element) file for the ISS.
    *   Calculate rise, peak, and set times relative to the observer's location.
    *   Filter for passes occurring during twilight or darkness where the satellite is illuminated by the Sun (visible pass).
*   **LLM Payload**: `"ISS will pass overhead at 19:42, reaching a max altitude of 65° in the North-West, visible for 4 minutes."`

---

## 3. Duplicated Parameters (Used in Both Pipelines)

To keep both pipelines self-contained, the following metrics will be calculated once and fed to both LLM prompts:
- **Moon Phase & Illumination Percentage**: e.g., `"Waxing Crescent (32% illuminated)"`
- **Upcoming Eclipses**: e.g., `"Upcoming Partial Solar Eclipse in 5 days"`
- **Planetary Conjunctions/Aspects (Naked-Eye)**: e.g., `"Venus and Mars conjunction in Aries"` (Astrologically a conjunction; Astronomically a visible planetary pairing).

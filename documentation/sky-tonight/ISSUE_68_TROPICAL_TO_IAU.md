**Problem**

The zodiac wheel on the Sky Tonight screamsheet places planets using the **tropical ecliptic longitude** (degrees measured from the vernal equinox, divided into 12 × 30° sectors). This is the Western astrological convention. It is *not* the same as where a planet visually appears among the stars.

Due to the **precession of the equinoxes**, the vernal equinox has drifted ~24° westward relative to the fixed stars since the zodiac system was defined (~2,000 years ago). As of 2026, every planet shown on the wheel appears roughly one full zodiac sign ahead of where it actually sits in the night sky. Real-world examples observed on 2026-04-23:

| Planet | Wheel shows (tropical) | Actual constellation (Stellarium/IAU) |
|--------|----------------------|---------------------------------------|
| Sun | Taurus | Aries |
| Jupiter | Cancer | Gemini |
| Mercury, Mars, Saturn | Aries | Pisces |
| Uranus, Venus | Gemini/Taurus border | Taurus → Aries |
| Moon | Leo/Cancer border | Cancer → Gemini |

The horoscope on the back page is **intentionally tropical** (Western astrology uses the vernal equinox convention) and must not be changed.

**Goal**

When a user looks at the zodiac wheel and sees "Jupiter is in Gemini," they should be able to walk outside, find the Gemini star pattern, and see Jupiter near it. Exact positional precision is not required — constellation-level accuracy is sufficient.

**Proposed Solution**

In `SkyDataProvider._compute_planet_positions()`, after computing the astrometric position via Skyfield, obtain the planet's **RA/Dec** (already available from the same astrometric object) and look up the **IAU constellation boundary** rather than bucketing the tropical ecliptic longitude.

Recommended approach: use `astropy.coordinates.get_constellation(SkyCoord(ra, dec))`, which implements the full Delporte (1930) IAU boundary table — the same database Stellarium uses.

If `astropy` is not an acceptable dependency, the second option is to subtract the current **ayanamsa** (Lahiri value, ~24.1° in 2026) from the tropical longitude before the `int(lon / 30)` bucket. This is an approximation but accurate to within ~1° and requires zero new dependencies.

**Scope of Change**

- sky_provider.py — `_compute_planet_positions()`: replace tropical bucket with IAU lookup; add helper `_ra_dec_to_constellation(ra_hours, dec_deg, date)`.
- `_ecliptic_lon_to_zodiac()` is used only by `sky_provider`; it can be removed or kept for reference.
- The zodiac **wheel geometry** (rendering) does not change. Only the constellation label assigned to each planet dot changes.
- `AstroDataProvider` and all horoscope code: **no changes**.

**Acceptance Criteria**

1. For a test date of 2026-04-23 at 22:00 UTC, `SkyDataProvider._compute_planet_positions()` returns Jupiter in `"Gemini"`, the Sun in `"Aries"`, and Saturn/Mars/Mercury in `"Pisces"`.
2. All existing `SkyDataProvider` unit tests pass (update expected zodiac strings to sidereal values).
3. `AstroDataProvider` tests are untouched and still pass.
4. `mypy` reports no new errors.
# Refactor Horoscope Pipeline: Use Swiss Ephemeris for Zodiac Sector Calculation and Aspect Analysis 

## Background
Currently, the Sky Tonight screamsheet uses Skyfield to calculate planetary positions both for the visual Zodiac circle (front page) and for generating horoscopes (LLM summaries). For naked-eye and constellation-based representations, Skyfield remains suitable. However, horoscopes require positions anchored to the vernal equinox (astrological degrees, not current constellation boundaries), which has shifted considerably over millennia. Additionally, astrological analysis requires calculation of planetary aspects (angles between planets) in addition to absolute positions.

## Requirements
- **Replace planetary position calculations for horoscopes:**
  - Use [PySwissEph](https://pypi.org/project/pyswisseph/) (Swiss Ephemeris Python bindings) instead of Skyfield for calculating astrological planetary longitudes.
  - Compute each planet's position as the number of degrees from the vernal equinox (Aries 0°), dividing the ecliptic into 12 equal sectors.
  - Provide this data for both daily horoscopes (LLM input) and any technical/verification output.
  
- **Calculate and provide planetary aspects:**
  - Compute all major astrological aspects between relevant planetary bodies (e.g., conjunction, opposition, square, trine, sextile, etc.).
  - Present aspect data in a machine-readable form for LLM consumption.

- **Maintain Current "Sky Tonight" Visuals:**
  - Continue rendering the naked-eye sky map (Zodiac circle, constellation assignment, and Horkheimer-style LLM summary) using Skyfield as before.

## Acceptance Criteria
- Horoscopes and aspects are based entirely on Swiss Ephemeris calculations, **not** Skyfield.
- Zodiac constellation graphics and written sky summary remain Skyfield-based.
- Data pipeline for horoscopes supplies LLM with: (1) planet positions in zodiac sectors from vernal equinox, and (2) complete aspects table.
- All new or changed modules fully typed (mypy clean), tested (TDD), and described in README.md.

## References
- [Swiss Ephemeris Documentation](https://www.astro.com/swisseph/)
- [PySwissEph PyPI](https://pypi.org/project/pyswisseph/)
- [Astrological aspect basics](https://en.wikipedia.org/wiki/Astrological_aspect)

---
**Housekeeping:** Issue-driven, TDD and SRP strictly enforced. Commit message MUST reference this issue number.
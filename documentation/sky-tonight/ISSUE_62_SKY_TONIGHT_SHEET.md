## Feature Overview
Add a new screamsheet type that generates a printable, one-page PDF every morning summarizing the naked-eye night sky: planetary positions in zodiac, visible constellations, and a short AI-generated summary. The LLM prompt should adopt the persona of an enthusiastic amateur astronomer AND someone playfully interested in astrology (but not seriously), always focusing on naked eye observations (never telescopes).

---

### Step-by-Step Plan

**1. Dependencies & Setup**
- [ ] Add `skyfield` to requirements (planet positions, zodiac mapping; optionally use for ISS passes, moon phase)
- [ ] Add any assets needed for constellation boundaries (e.g. CSV files)

**2. Data Provider**
- [ ] Create `src/screamsheet/providers/sky_provider.py`
  - [ ] Compute ecliptic longitudes for all classical planets (Mercury → Pluto), moon, and sun for tonight
  - [ ] Map planet positions to zodiac constellations
  - [ ] Determine which constellations are above the horizon at local sunset/astronomical dusk
  - [ ] Identify highlights: conjunctions, close approaches, ISS passes, meteor showers (as list of dicts, each ≤1 line)
  - [ ] Filter for naked-eye only (planets brighter than ~mag 6.5); Uranus/Neptune/Pluto only for chart, not in AI summary

**3. Renderers**
- [ ] Create `renderers/zodiac_wheel.py`: draws a stylized circle with 12 zodiac wedges, planets marked, and a shaded band for visible portion
- [ ] Create `renderers/sky_highlights.py`: renders a bulleted highlights section (including LLM-generated text)

**4. LLM / AI Summary**
- [ ] Update or add to `src/screamsheet/llm/` as needed to support a prompt:
    - Persona: "Enthusiastic amateur astronomer who loves naked eye observations and is also playfully interested in astrology. Never recommends telescopes."
    - Output: 3–6 concise bullets or 2-sentence narrative + bullets, based on provided highlight data

**5. Screamsheet Glue**
- [ ] Add new screamsheet type at `src/screamsheet/sky/sky_tonight.py`
- [ ] Wire up to factory in `factory.py` as `create_sky_tonight_screamsheet()`
- [ ] Add entry to `config.yaml.example` (lat, lon, location_name)
- [ ] Update main script/cron for daily execution and printout

**6. Testing**
- [ ] Create tests in `tests/test_sky_provider.py` and check date/location edge cases (e.g. polar day/night)

---

**Extra**
- [ ] Make sure summary sections never suggest needing a telescope
- [ ] Output supports both astronomy and fun/astrology remarks where appropriate (in a tongue-in-cheek way)
- [ ] Code modular to allow additional "tonight" style sheets in future

---

### Example Output (expected)

- Zodiac wheel showing planet positions (dots with labels)
- Shaded arc for visible constellations
- Bullet points like:
  - "Venus is brilliant in the west after dusk, just above Taurus."
  - "Jupiter and Mars form a striking pair in Gemini."
  - "The waxing crescent Moon is in Leo tonight."
  - "No major meteor showers, but the ISS passes overhead at 9:17pm."
  - *(And a fun line)*: "Mercury winks at Virgo — perhaps it's a night for clever ideas!"

---
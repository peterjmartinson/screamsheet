### Step 1: Prompt for the ESPN Data Sanitizer

Create a Python module `data/espn_client.py` and `data/parsers.py` using `requests`.
Target endpoints:
1. Scoreboard: https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
2. Game Summary: https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}
3. Standings: https://site.api.espn.com/apis/v2/sports/football/nfl/standings
4. Injuries: https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/injuries

Write pure parser functions with pytest unit tests:
- `extract_scoreboard(raw_json)`: Returns a list of dicts: [ {away_team, away_score, home_team, home_score, status, quarter_scores} ]
- `extract_game_summary(raw_json, favorite_team_id)`: Extracts team totals (yards, turnovers, 3rd down eff), scoring drive narrative log, and top 3 passers/rushers/receivers.
- `extract_standings(raw_json, division_name)`: Returns rank, W-L-T, differential, and streak.
Ensure functions fail gracefully with empty dicts if keys are missing.

---

### Step 2: Prompt for the Day-of-Week Strategy Router

Create `router.py` containing an enum `DayStrategy` and a router class `ScreamSheetRouter`.
Rules:
- Monday: Strategy = RECAP (Fetches Scoreboard + Featured Game Summary)
- Tuesday: Strategy = STANDINGS_AND_INJURIES (Fetches Standings + Team Injuries)
- Wednesday: Strategy = FILM_ROOM (Fetches Season Metrics + Scheme Focus)
- Thursday: Strategy = TNF_SCOUTING (Fetches TNF Scoreboard + Upcoming Opponent Stats)
- Friday: Strategy = KEYS_TO_VICTORY (Fetches Final Practice Injury Designations)
- Saturday: Strategy = WEEKEND_PREP (Fetches Weather Forecast + TV Schedule)
- Sunday: Strategy = GAMEDAY_CARD (Fetches Pre-game Depth Chart + Head-to-Head)

The router should inspect `datetime.today().weekday()` (or accept an override date for testing) and return:
1. The strategy name
2. The specific data loader functions to execute
3. The prompt template key to invoke

---

### Step 3: Prompt for the LLM Prompt Engine (3.7 Flash)


Create `generators/prompt_factory.py` and `generators/llm_client.py` using the official `google-genai` SDK targeting Gemini Flash.

`prompt_factory.py` must build tailored prompts based on DayStrategy:
- System Persona: Veteran sports desk editor creating a crisp, single-page morning sports sheet for a 10-year-old and his dad. Tone is punchy, high-energy, analytical, and scannable.
- Constraints: Output must fit exactly on a single 8.5x11 page when rendered. Use strict Markdown tables for linescores and stats, bullet points for takeaways, and bold highlights for big plays.
- Include day-specific directives (e.g., Monday requires a Drive Chart and 3 Game Takeaways; Tuesday requires a Playoff Bubble tracker).

`llm_client.py`:
- Initialize `genai.Client()`.
- Implement `generate_sheet(prompt_text: str) -> str` with streaming disabled, low temperature (~0.3 for factual accuracy), and error retry logic.



---

### Step 4: Prompt for the Print-Ready CSS Renderer

Create `templates/render_html.py` using `markdown` and `jinja2`.
Requirements:
1. Convert LLM-generated Markdown into a clean HTML document.
2. Include print-optimized CSS with `@media print`:
   - Fixed page size: `@page { size: letter portrait; margin: 0.5in; }`
   - Strict no-overflow rules: `body { overflow: hidden; font-family: system-ui, -apple-system, sans-serif; font-size: 11pt; line-height: 1.35; }`
   - Clean tabular styling for box scores and drive summaries.
   - Column layout (2-column newspaper feel for notes/standings).
3. Provide a helper method `export_pdf()` using `weasyprint` or a headless browser flag if installed.


---

Workflow:
1. `router.get_strategy(date)`
2. `espn_client.fetch_bundle(strategy)`
3. `parsers.clean_bundle(raw_data)`
4. `prompt_factory.build(strategy, clean_data)`
5. `llm_client.generate(prompt)`
6. `render_html.save(output)`
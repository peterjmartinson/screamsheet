We need a new screensheet for the **FIFA World Cup 2026** using API-Football data, formatted like the existing sports screensheets.

## Goals / Layout

### Front page
- **Top:** Yesterday’s scores (all completed World Cup fixtures for yesterday)
- **Bottom:** Current standings for all groups/teams

### Back page
- **Left:** Game summary for one featured match from yesterday
- **Right:** Box score/details for that same featured match

## Featured match selection priority
Pick exactly one fixture from yesterday using this order:
1. USA (team name `"USA"` or `"United States"`)
2. Argentina
3. Portugal
4. If none played yesterday, pick a random completed fixture from yesterday

## Data source (API-Football)

Base URL (direct API-Sports):
- `https://v3.football.api-sports.io/`

Required headers:
- `x-apisports-key: <provided at runtime>`
- `Accept: application/json`

(Alternative RapidAPI route is acceptable if we standardize headers/base URL in config.)

## Constants
- `league=1` (FIFA World Cup)
- `season=2026`
- Fixture requests must include timezone (default `America/New_York`)
- `yesterday = current_date - 1 day` (`YYYY-MM-DD`)

## Endpoints and parsing requirements

### 1) Yesterday scores
`GET /fixtures?league=1&season=2026&date={yesterday}&timezone=America/New_York`

Extract:
- `fixture.id`
- `teams.home.name`
- `teams.away.name`
- `goals.home`
- `goals.away`
- `fixture.status.short` (FT/AET/PEN)

### 2) Standings
`GET /standings?league=1&season=2026`

Extract from `response[0].league.standings` (array of group arrays):
- `group`
- `team.name`
- `points`
- `goalsDiff`
- `rank`

### 3) Featured game details (using selected fixture_id)
- `GET /fixtures/events?fixture={fixture_id}`
  - Keep `type = Goal` and `type = Card`
  - Extract `time.elapsed`, `team.name`, `player.name`, `assist.name`
- `GET /fixtures/statistics?fixture={fixture_id}`
  - Extract possession, total shots, shots on target for both teams

## Output requirements
- Build data structures compatible with existing sports screensheet rendering
- Produce:
  - front/top: scoreboard list
  - front/bottom: grouped standings table
  - back/left: summary input payload
  - back/right: box score stats/events
- Also produce a **minified JSON string** from featured game events + stats for downstream LLM game-summary generation.

## Acceptance criteria
- If yesterday has fixtures, screensheet renders all 4 sections correctly
- Featured game follows team-priority logic exactly
- If no priority teams played, fallback fixture is random from yesterday completed matches
- Handles empty/partial API responses gracefully with clear fallback messaging
- Timezone-aware date handling prevents wrong-day fixture selection

## Open questions
- Confirm canonical timezone (keep `America/New_York` or make user-configurable?)
- Confirm whether penalties should be displayed in front-page scores when `status.short = PEN`
- Confirm exact box score fields already used by current sports template (to match formatting 1:1)
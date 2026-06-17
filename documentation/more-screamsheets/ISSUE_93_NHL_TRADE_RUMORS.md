## Objective

Implement an NHL trade rumors screamsheet page modeled after the MLB trade rumors sheets. The page fetches up to four recent NHL trade rumors from the past 24 hours prioritized by favorite teams, processes each using a configurable Large Language Model (LLM) API to generate ~300-word summaries, and compiles a printable single-page 2×2 layout.

---

## Technical Specifications & Architecture

```
                     [Trade Rumor Feeds (PuckPedia, TSN, The Athletic)]
                                  │
                                  ▼
                     [ Data Scraper & Filter ] 
                       (Check FAVORITE_NHL_TEAMS)
                                  │
                                  ▼
                   [ Configurable LLM API Engine ]
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
 [ Summary 1 (~300w) ]                               [ Summary 2 (~300w) ]
 [ Summary 3 (~300w) ]                               [ Summary 4 (~300w) ]
        │                                                   │
        └─────────────────────────┬─────────────────────────┘
                                  ▼
                   [ Layout Compiler / Markdown ]

```

### Requirements

- Sources: Target dedicated NHL trade rumor feeds and sports outlets.
- Input: `FAVORITE_NHL_TEAMS` configuration array (up to 3 teams). Prioritize team-matching rumors; fill remaining slots from other recent rumors.
- Time window: Only include rumors from the last 24 hours when available.
- LLM: Use the existing LLM driver abstraction (configurable provider/model/key). Each rumor must be processed into an independent ~300-word summary.
- Layout: Generate a printable 2×2 grid (4 summaries) as a Markdown output ready for the layout compiler.
- Testing: Unit tests for ingestion, fallback routing, LLM wrapper, and layout generation. Maintain walking skeleton and small modular commits.

---

## Definition of Done (TDD Criteria)

- [ ] Unit tests verify router selects team-priority rumors and falls back to high-buzz rumors to reach 4 items.
- [ ] Unit tests validate the LLM wrapper enforces ~300-word limits and returns parseable output.
- [ ] Integration test verifies end-to-end pipeline produces a single printable Markdown output with a 2×2 layout.

# Technical Design: PDF Layout Quality Control & Subscriber Config Interface

**PRD:** [prd-layout-quality-control.md](prd-layout-quality-control.md)

## Overview

This document describes the technical approach for migrating the `screamsheet` PDF generator to Platypus-based flowing layouts, adding deterministic overflow recovery, standardizing the layout quality signal, and introducing a subscriber config interface that allows `screamsheet-dispatch` to invoke the generator on behalf of any subscriber.

The existing `ScreamsheetFactory` / `BaseScreamsheet` / `Section` architecture is preserved. Changes are additive — new renderers, a new result type, and a new config-driven entry point.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Layout engine for news sheets | Platypus `SimpleDocTemplate` with `Frame` definitions | Replaces hardcoded page breaks; content flows naturally across front/back frames without manual splitting |
| Sports chart integrity | `KeepTogether` flowable wrapper | Guarantees standings table is never split by the layout engine |
| Overflow recovery strategy | Iterative compression loop on the scores `Table` | Scores table has inherent white space that can be reclaimed; standings must stay intact per product requirement |
| Layout quality signal | New `GenerationResult` dataclass returned by generate methods | Gives callers (dispatch) a structured, typed result rather than requiring them to inspect the PDF |
| Subscriber config interface | Generator accepts a YAML config file path; produces all sheets in one invocation | Matches the dispatch model — one call per subscriber, not one call per sheet type |
| Config schema | Extend existing `config.yaml` schema to support subscriber-specific overrides | The existing schema already models team preferences; subscriber configs are the same shape with a GUID and email added |
| Team name → ID resolution | Generator looks up team IDs from local SQLite tables at runtime; subscriber configs store only canonical team names | Keeps ID knowledge inside the generator domain; dispatch and subscribers never deal with numeric IDs; insulates configs from ID changes |
| Output PDF naming | Generator uses existing `{sheet_type}_{YYYYMMDD}.pdf` convention; dispatch does not rename files | Consistent with personal-use output; no coordination needed between repos |
| Layout config location | Add a `layout:` section to the existing `config.yaml` | One config file to manage; no split between layout and other settings |

---

## Design Decisions (detail)

### Platypus Frame Layout for News Sheets

News sheets define two `Frame` objects — one for the front, one for the back — within a `SimpleDocTemplate`. Article flowables are added to a single story list and Platypus handles pagination automatically. The hardcoded `PageBreak` between article pairs is removed.

The footer (AC-BRAND-01) is implemented as a `onLaterPages` / `onFirstPage` callback on the `SimpleDocTemplate`, which draws the centered bold "distractedfortune.com" text at the bottom of every page.

### Overflow Recovery Loop for Sports Sheets

The scores table is built with a starting row padding. Before rendering the final PDF, the generator checks whether the `KeepTogether`-wrapped standings block would overflow the front frame by measuring the combined height of all flowables destined for the front. If overflow is detected:

1. Reduce scores table row padding by one configured step.
2. Recheck heights.
3. Repeat until the standings fit or the padding floor is reached.

Separately, column widths for the scores table are checked against a minimum column width floor to detect horizontal overlap between team name and score columns. Column widths are adjusted before the overflow recovery loop runs, so both compressions work together.

### GenerationResult

Every `generate()` call returns a `GenerationResult` containing:
- `pdf_path` — path to the written PDF file
- `layout_clean` — `True` if the output is exactly two pages with no warnings
- `issues` — list of human-readable issue strings (empty list when clean)

This is the **only** way layout and data errors are communicated to callers. No exceptions are raised for layout issues — only for hard failures (file I/O errors, etc.).

### Subscriber Config Interface

A new top-level entry point (separate from the existing `__main__.py` personal-use flow) accepts a YAML config path and produces a `list[GenerationResult]`, one per sheet type in the config. The subscriber YAML schema is a superset of the existing `config.yaml` — it adds `guid`, `name`, and `email` fields at the top level, and the existing `nhl`, `mlb`, `nba` sections carry team preferences exactly as they do today.

---

## Interfaces

### GenerationResult

```
GenerationResult:
  pdf_path: str          — absolute path to the written PDF
  sheet_type: str        — e.g. "nhl", "mlb", "news_presidential"
  layout_clean: bool     — True if exactly two pages and no issues
  issues: list[str]      — human-readable issue descriptions; empty when clean
```

### Subscriber Config Schema (YAML)

```
guid: str                          — subscriber GUID (added by dispatch sync)
name: str                          — subscriber display name
email: str                         — subscriber email address

nhl:
  favorite_teams:
    - name: str        — canonical team name exactly as stored in nhl_teams DB table

mlb:
  favorite_teams:
    - name: str        — canonical team name exactly as stored in mlb_teams DB table
  news_names: list[str]

nba:
  favorite_teams:
    - name: str        — canonical team name exactly as stored in nba_teams DB table

news:
  types: list[str]                 — e.g. ["presidential", "mlb_trade_rumors"]
  include_weather: bool            — false for subscriber sheets; weather requires geocoding (deferred)
```

### Generator Entry Point (subscriber invocation)

```
generate_for_subscriber(config_path: str, output_dir: str) -> list[GenerationResult]

  config_path  — path to the subscriber YAML config file
  output_dir   — directory where PDFs are written (dispatch provides outbox/{date}/{guid}/)
  returns      — one GenerationResult per sheet type in the config
```

### Existing Factory (unchanged for personal use)

The existing `ScreamsheetFactory` methods remain. They are unaffected by this work. Personal-use invocation via `uv run screamsheet` continues to work using `config.yaml`.

---

## Data Models

### Layout Config (global config.yaml additions)

```
layout:
  brand_footer_text: str            — default: "distractedfortune.com"
  scores_table:
    initial_row_padding: int        — starting row padding in points
    padding_step: int               — reduction per vertical recovery step
    min_row_padding: int            — vertical compression floor
    min_column_width: int           — horizontal compression floor
    padding_steps_max: int          — maximum vertical recovery iterations
```

---

## Integration Points

- **`screamsheet-dispatch`** calls `generate_for_subscriber(config_path, output_dir)` and receives `list[GenerationResult]`. Dispatch is responsible for logging, alerting, and email delivery — the generator does not know about subscribers beyond what's in the config.
- **Existing `config.yaml`** (personal use) is untouched. The subscriber YAML is a separate file format that happens to share the same team-preference sub-schema.
- **ReportLab Platypus** — `reportlab.platypus.SimpleDocTemplate`, `Frame`, `KeepTogether`, `Table`, `TableStyle` are the key classes. No new third-party dependencies are introduced.
- **Team ID database** — `db/` directory (existing). The generator resolves canonical team names to API IDs via SQLite tables at runtime. See Team ID DB section below.

## Team ID Database

The existing `db/` directory and `uv run db_update` command (which currently syncs NHL player data) are extended to cover all supported sports. Each sport gets its own team table:

```
nhl_teams:  id INT, name TEXT, abbreviation TEXT, last_synced DATETIME
mlb_teams:  id INT, name TEXT, abbreviation TEXT, last_synced DATETIME
nba_teams:  id INT, name TEXT, abbreviation TEXT, last_synced DATETIME
nfl_teams:  id INT, name TEXT, abbreviation TEXT, last_synced DATETIME
```

The `db_update` command is extended with one sync job per sport. Each job hits the sport's API, fetches the current team list, and upserts into the corresponding table. The nightly cron entry for `db_update` runs separately from the morning dispatch run (suggested: 2am) so that a failed sync never delays delivery.

The canonical team name stored in the DB is the exact string expected in subscriber configs and in the signup form dropdown. Name → ID lookup at generation time is a simple `WHERE name = ?` query — no fuzzy matching.

---

## Out of Scope

- **Subscriber weather opt-in** — Weather currently appears automatically on news sheets using hardcoded coordinates from the developer's personal `config.yaml`. For subscriber sheets, `include_weather: false` suppresses it entirely. Enabling per-subscriber weather requires a geocoding integration (city/state → lat/lon) which is deferred to a future update. When implemented, the subscriber config will gain a `weather` block with city/state fields, and the generator will resolve coordinates via a geocoding API (e.g. OpenStreetMap Nominatim) at sync time, storing resolved coordinates in the config.

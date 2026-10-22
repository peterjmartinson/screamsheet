# Stage 1 & Overall Architecture Decisions (Resolved)

This document records the design decisions confirmed prior to executing **Stage 1: Foundation (`ScreamsheetComponent` Base, Registry, & Provider Cleanup)**.

---

## Part A: Stage 1 Specific Decisions

### 1. Provider Hierarchy Refactoring (`src/screamsheet/base/data_provider.py`)
- **Decision**: Approved (`DataProvider` → `SportsDataProvider` / `NewsDataProvider`).
- **Details**:
  - Keep `DataProvider` as the root base class with common text-sanitization helpers (`sanitize_entry`, `sanitize_articles`) and safe default no-op implementations (`get_game_scores() -> []`, `get_standings() -> None`, `get_box_score() -> None`, `get_game_summary() -> None`, `has_game() -> True`, `get_all_teams_for_date() -> []`, `get_day_schedule() -> []`) for backward compatibility with existing tests.
  - Introduce `SportsDataProvider(DataProvider)` with `@abstractmethod get_game_scores` and `@abstractmethod get_standings`.
  - Introduce `NewsDataProvider(DataProvider)` with `@abstractmethod get_articles`.
  - Remove redundant dummy sports stubs from the news providers.

---

### 2. Package & Naming Conventions (`src/screamsheet/components/`)
- **Decision**: Approved.
- **Details**:
  - Package path: `src/screamsheet/components/`.
  - Class suffix: `*Component` (`ScreamsheetComponent`, `StandingsComponent`, `MLBStandingsComponent`, `NewsStoryComponent`, `TVScheduleComponent`, `NFLTVScheduleComponent`, etc.).

---

## Part B: Overall Architecture Decisions

### 3. Game Summary + Box Score Granularity (Stage 3)
- **Decision**: Keep Game Summary (left column) and Box Score (right column) together as a single `BoxScoreComponent` (with standalone `GameSummaryComponent` retained only where needed, e.g., `MLBAllStarScreamsheet`).

---

### 4. News Story Component Overflow & Deduplication (Stage 4 & Stage 6)
- **Decision**:
  - Default `max_articles: 4` when not specified in YAML.
  - Individual articles flow sequentially: starting on the **left half** of the current page, overflowing to the **right half** of the current page, then overflowing to the **left half of the next page**, then the **right half of the next page**, and so on.
  - Each screamsheet tracks all stories (`seen_stories` / `seen_links` + `TopicClusterer`) across the entire screamsheet so stories are never duplicated across components or pages.

---

### 5. Standings Page Capacity & TV Schedule Component (Stage 2 & Stage 3)
- **Decisions**:
  - **Standings Layout Rule**: Only **one** `StandingsComponent` fits on Page 1 (front page); up to **two** `StandingsComponent`s fit on Page 2 (back page) and each subsequent page. Other smaller components (such as game scores, weather, TV schedule, or news articles) can share Page 1 alongside a single standings table.
  - **TV Schedule Component**: Extract an extensible `TVScheduleComponent` base class with `NFLTVScheduleComponent` (`"nfl_tv_schedule"`) initially, designed so other sports can be added in future iterations.

---

### 6. Subscriber YAML Syntax & Custom Screamsheet Title (Stage 7)
- **Decision**:
  - Any sheet entry under `sheets:` containing a `components:` list is treated as a custom screamsheet.
  - Custom screamsheets support a `screamsheet_title` option (e.g., `screamsheet_title: "Daily Pro Sports Standings"`), which replaces the default `"Screamsheet"` masthead title.

---

### 7. Unmerged Branches
- **Decision**: Ignore old unmerged branches (`feature/unified-edition`, `feature/cfb-screamsheet`) and work directly from `master`.

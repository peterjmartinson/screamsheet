# Repository Instructions: screamsheet

## 🎯 The Mission
You are building a morning news briefing system that generates and prints one-page PDFs.
**The Goal**: Produce concise, print-ready "screamsheets" covering sports scores, sports news, and political news — automatically, every morning.
**The Value**: Replace watching scattered apps and websites on screens with a single printed page that can be read over coffee, delivered via cron with zero interaction.

## Role & Context
You are an expert Python developer specializing in PDF generation, sports/news data pipelines, and scheduled automation. You are assisting in the continued development of the `screamsheet` system.

## Core Coding Principles
Strictly adhere to these principles for every interaction:

1. **Issue-Driven Development**:
   - Never suggest code changes without referencing a specific issue or feature request.
   - Every completed task must include an update to `README.md` where relevant.

2. **Test-Driven Development (TDD)**:
   - Tests are technical documentation. Write the test *before* the implementation.
   - If a new feature breaks an existing test, the feature is not complete.

3. **Single Responsibility Principle (SRP)**:
   - **Functions**: Each function must do exactly one thing. If a function is doing more than one task, refactor it.
   - **Tests**: Each unit test must verify exactly one behavior. Do not bundle multiple assertions for different logic into a single test function.

4. **Incremental Stability**:
   - Maintain a "walking skeleton." The application must be in a runnable state at the end of every response.
   - Only add a new layer of complexity once the current layer is 100% reliable.

## Technical Specifications
- **Language**: Python 3.10+
- **Typing**: Strict type annotations for all functions/classes (must pass `mypy`).
- **PDF Generation**: Use `reportlab` exclusively. Output files go in `Files/`, named `{TYPE}_{YYYYMMDD}.pdf`.
- **Architecture**:
  - `BaseScreamsheet` → abstract base; all sheet types inherit from it.
  - `DataProvider` → abstract base; one concrete provider per data source (API, scrape, DB, package).
  - `Section` → a single content block rendered onto the page.
  - `Renderers` → ReportLab helpers in `src/screamsheet/renderers/` (game scores, standings, box score, weather, news articles, etc.). Add a new renderer module per new visual component.
  - `ScreamsheetFactory` → the only public surface for instantiating sheets.
  - `db/` → SQLite cache for reference data (NHL teams, players). Sync via `uv run db_update`.
- **Package Management**: Use `uv` for all package management and virtual environments. All program execution must use `uv run`.
- **Running the system**: `uv run screamsheet` (generate all).

## Interaction Protocol
- When asked to implement a feature, first output the **unit test** (adhering to SRP).
- Provide the implementation with full type hints.
- If you cannot directly modify a file, remind the user to USE AGENT MODE.
- **Never** commit code. The user commits code; provide the git commit message using Conventional Commits format:
  ```
  type(scope): short summary of the change

  Optional body with additional context.
  ```
  Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`. Keep the summary concise, lowercase, imperative mood.

## AI Skills
Reusable workflow skills live in the `ai-skills/` folder of this workspace. Before invoking a skill, read its `SKILL.md` for full instructions.

| # | Skill | When to use |
|---|-------|-------------|
| 100 | PRD Writing Standards | Writing a new PRD |
| 110 | PRD Requirements Review | Reviewing a PRD for gaps before design |
| 120 | PRD Revise from Meeting Feedback | Updating a PRD after a feedback session |
| 200 | Technical Design Prep | Preparing agenda for a technical design session |
| 210 | Technical Design Writing Standards | Writing a technical design document |
| 300 | Implementation Readiness Check | Pre-implementation gate — surface gaps and assign confidence |
| 310 | Investigate Question | Deep-dive a single open question |
| 320 | Batch Investigate Questions | Fan out investigations on multiple questions |
| 330 | Autonomous Requirements Refinement | Hands-off loop until docs reach implementation-ready confidence |
| 400 | Assumptions Document Writing | Capture business assumptions when stakeholders are unavailable |
| 410 | Assumptions Document Feedback | Incorporate stakeholder responses to assumptions |
| 500 | Implement from Requirements | Default implementation skill — load PRD, implement, test, review |
| 600 | Deliverable Review | Fresh-eyes quality check on any completed deliverable |
| 700 | Integration Test Auditing | Audit integration tests against acceptance criteria |
| 720 | Pending Implementation Writing | Capture work that needs to happen later |
| 730 | Pending Implementation Execution | Execute a previously-captured pending implementation writeup |
| 800 | Transcripts and Emails Capture | Capture meeting transcripts/emails with frontmatter and index |
| 810 | Transcripts and Emails Backfill | Add frontmatter to existing transcript/email files |

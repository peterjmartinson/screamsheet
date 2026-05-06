# PRD: PDF Layout Quality Control

## Summary

The `screamsheet` PDF generator currently produces multi-page PDFs using hardcoded page breaks and fixed-position ReportLab drawing calls. This causes recurring layout failures in practice: blank pages, articles starting on the wrong side of the sheet, and standings charts splitting across pages. These failures happen almost every day and degrade the product being delivered to subscribers.

This PRD covers the changes needed to make the generator produce consistently well-formed two-page PDFs — a front side and a back side — with content that flows naturally, sports charts that never break across pages, a graceful overflow recovery strategy when content is too long, consistent branding on every page, and a subscriber config interface so that the `screamsheet-dispatch` system can invoke the generator on behalf of any subscriber.

---

## Acceptance Criteria

### Branding

- [ ] **AC-BRAND-01** — Every generated PDF includes a footer on both the front and back pages displaying centered bold text reading "distractedfortune.com".
- [ ] **AC-BRAND-02** — The footer URL text is defined in configuration, not hardcoded.

### News Sheet Layout

- [ ] **AC-NEWS-01** — News sheet content is rendered using a Platypus `SimpleDocTemplate` with defined frames for the front and back sides; hardcoded page breaks between individual articles are removed.
- [ ] **AC-NEWS-02** — News articles flow continuously from the front frame into the back frame without manual intervention — no fixed "two articles front, two articles back" split.
- [ ] **AC-NEWS-03** — If all news content fits on the front, the back side contains only the branded footer (see AC-BRAND-01) and no other content.
- [ ] **AC-NEWS-04** — A news sheet that overflows beyond two pages signals a layout warning (see AC-QC-01) but still produces a PDF.

### Sports Sheet Layout

The standard sports sheet layout is: scores table at the top of the front (below title/subtitle), standings table below the scores on the front, and a two-column back with game summary on the left and box scores on the right. MLB, NHL, and NBA all use this layout. NFL is not addressed in this PRD.

- [ ] **AC-SPORT-01** — The scores table and standings table are each wrapped in a `KeepTogether` container so neither splits across pages.
- [ ] **AC-SPORT-02** — When a `KeepTogether` standings block cannot fit on the front side with the current scores table, the generator attempts vertical overflow recovery (see AC-OVF section). If recovery is exhausted the standings may split across pages; the generator logs a layout warning and ships the sheet.
- [ ] **AC-SPORT-03** — The scores table also undergoes horizontal compression: column widths are adjusted incrementally to prevent team name text from overlapping score values. The generator backs off compression until no overlap is detected.
- [ ] **AC-SPORT-04** — If horizontal compression reaches its configured minimum column width and overlap still exists, the generator logs a layout warning and ships the sheet as-is.

### Overflow Recovery

- [ ] **AC-OVF-01** — Vertical overflow recovery reduces the row padding of the scores table in defined incremental steps to give the standings table more room on the front page.
- [ ] **AC-OVF-02** — The number of vertical recovery steps, the padding reduction amount per step, and the minimum row padding floor are all defined in configuration, not hardcoded.
- [ ] **AC-OVF-03** — Vertical recovery stops as soon as the standings table fits on the front page; the result at that compression level is used.
- [ ] **AC-OVF-04** — If all vertical recovery steps are exhausted and the standings still overflow, the generator stops retrying, logs a layout warning, and returns the best available PDF with the standings split across pages.
- [ ] **AC-OVF-05** — Horizontal compression step sizes and the minimum column width floor are defined in configuration; the scores table columns are never compressed below this floor.

### Layout Quality Signal

- [ ] **AC-QC-01** — After generation, the generator returns a structured result that includes: the PDF, a boolean indicating whether the layout is clean (fits in exactly two pages), and a human-readable description of any layout issue detected.
- [ ] **AC-QC-02** — A clean two-page output always sets the layout-clean flag to `True` with no issue description.
- [ ] **AC-QC-03** — The structured result is the return value of the generation function and is available to any caller (e.g., the `screamsheet-dispatch` runner) for logging and alerting. Aggregation of per-sheet results into a run-level log is the caller's responsibility.

### API and Data Error Signaling

- [ ] **AC-DATA-01** — If a data provider fails to retrieve expected data (e.g., game scores not found, API rate-limited, network error), the generator records the specific failure in the structured result rather than silently producing an incomplete sheet.
- [ ] **AC-DATA-02** — A data failure for one section does not crash the generator — remaining sections are still rendered and the PDF is still returned.

### Subscriber Config Interface

- [ ] **AC-IFACE-01** — The generator accepts a path to a subscriber YAML config file as its primary input.
- [ ] **AC-IFACE-02** — The generator reads the config to determine which sheet types to produce and what per-sheet options to use (e.g., preferred teams, weather location).
- [ ] **AC-IFACE-03** — A single invocation with a subscriber config produces one PDF per sheet type listed in the config.
- [ ] **AC-IFACE-04** — The generator returns a list of structured results, one per sheet produced, each containing the PDF file path, the layout-clean flag, and any issue descriptions (per AC-QC-01).

---

## Out of Scope

- Changes to the `screamsheet-dispatch` runner, emailer, or run-level logging.
- NFL sheet layout (standings-on-back pattern) — deferred to a follow-on PRD.
- Sky Tonight and other specialty sheets — they retain their existing fixed-position rendering until a follow-on PRD addresses them.
- Adding new sheet types.
- Subscriber management, delivery, dispatch orchestration, or email concerns — those belong in the `screamsheet-dispatch` repo.

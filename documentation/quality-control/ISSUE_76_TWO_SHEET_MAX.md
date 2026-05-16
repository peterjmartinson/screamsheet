Enforce a hard two-page limit on all sports screamsheets (front = scores + standings, back = box score + game summary).

## Root Cause

`BoxScoreSection.render()` unconditionally prepends a `PageBreak()`. When the front-page content (game scores + standings) overflows by even a few points, ReportLab creates a partial second page for the overflow, then the `PageBreak` pushes the box score to a third page. Result: a 3-page PDF with a near-blank middle page.

The underlying structural problem is that `SimpleDocTemplate` flows content freely across pages with no per-page height contract.

## Target Layout

**Page 1 (front)**
- Title + date header
- Yesterday's game scores (top)
- League standings (bottom)
- If front content is too tall → shrink it proportionally to fit (never overflow to a second page)

**Page 2 (back)**
- Game summary (left column)
- Box score (right column)
- If no featured team played → PDF is 1 page only
- If back content is too tall → shrink it proportionally (never create a page 3)

## Implementation Plan

### 1. Switch `BaseScreamsheet.generate()` from `SimpleDocTemplate` to `BaseDocTemplate`

Define two named `PageTemplate`s — `'Front'` and `'Back'` — each containing a single full-page `Frame` (letter size, 36pt margins, ~720pt usable height).

### 2. Add `page_slot` to `Section`

Add an optional `page_slot: str = 'front'` attribute to the `Section` base class. `BoxScoreSection` sets `page_slot = 'back'`.

### 3. Split story in `generate()`

In `generate()`, partition sections by `page_slot`:
- Front sections → wrapped in `KeepInFrame(maxWidth=..., maxHeight=720, content=[...], mode='shrink')`
- If back sections exist → append `NextPageTemplate('Back')` + `FrameBreak()`, then back sections wrapped in their own `KeepInFrame(mode='shrink')`

### 4. Remove `PageBreak()` from `BoxScoreSection.render()`

The `PageBreak` is no longer needed; the `NextPageTemplate` + `FrameBreak` in `generate()` handles the page transition cleanly regardless of how full the front page is.

## Acceptance Criteria

- [ ] A sports screamsheet PDF never exceeds 2 pages
- [ ] A sports screamsheet PDF is exactly 1 page when no featured team played (no back-page content)
- [ ] When front-page content (scores + standings) is too tall to fit on one page, it shrinks proportionally rather than overflowing — no blank or partial middle page
- [ ] When back-page content is too tall, it shrinks proportionally rather than creating a page 3
- [ ] The blank-middle-page bug is eliminated for MLB, NHL, and NBA sheets
- [ ] All existing tests pass
- [ ] A new test verifies: given a mock front-page content that would naturally overflow, the generated PDF contains exactly 1 page (front only, no back) and is not blank
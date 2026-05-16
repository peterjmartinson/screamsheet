# Issue: Parallelize LLM API Calls to Reduce Build Time

## Background

`uv run screamsheet` currently takes approximately 5 minutes to generate all 7 default
screamsheets. The root cause is that every LLM API call is made sequentially — each one
blocks the next. There are roughly **18 calls per morning run** (12 to Grok, 6 to Gemini),
all executed one at a time.

### Current Call Inventory

| Sheet            | LLM    | Calls | Where called                                      |
|------------------|--------|-------|---------------------------------------------------|
| MLB              | Gemini | 1     | `MLBProvider.get_game_summary()`                  |
| MLB Trade Rumors | Grok   | 4     | `NewsArticlesSection._generate_summaries()` loop  |
| MLB News         | Grok   | 4     | `NewsArticlesSection._generate_summaries()` loop  |
| NHL              | Gemini | 1     | `NHLProvider.get_game_summary()`                  |
| NBA              | Gemini | 1     | `NBAProvider.get_game_summary()`                  |
| Presidential     | Grok   | 4     | `NewsArticlesSection._generate_summaries()` loop  |
| Sky Tonight      | Gemini | 3     | `SkyHighlightsSection` (1) + `SkyHoroscopeSection` (2) |
| **Total**        |        | **~18** | All sequential                                  |

Rough math: 18 calls × ~15 s/call = ~4.5 min, matching the observed runtime.

---

## Goal

Reduce total wall-clock build time from ~5 minutes to under 60 seconds with no change
to the content of any generated PDF.

---

## Proposed Changes

### 1. Run All 7 Sheets in Parallel

**File:** `src/screamsheet/__main__.py`

The `_build_sheets()` loop in `main()` runs each sheet serially. The sheets are
completely independent of each other — they share no mutable state after construction.

Replace the sequential loop with a `concurrent.futures.ThreadPoolExecutor`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=len(sheets)) as pool:
    futures = {pool.submit(_run_sheet, label, fn): label for label, fn in sheets}
    for future in as_completed(futures):
        future.result()   # re-raises any exception
```

**Expected impact:** Wall time drops from `sum(all sheets)` to `max(slowest sheet)`.

---

### 2. Parallelize Per-Article Summarization Within Each News Sheet

**File:** `src/screamsheet/renderers/news_articles.py`

`_generate_summaries()` iterates over articles in a `for` loop, blocking on each
`summarizer.generate_summary()` call before starting the next. Each article is
completely independent.

Replace the sequential loop body with a `ThreadPoolExecutor` that fires all articles
at once and collects results in slot order:

```python
from concurrent.futures import ThreadPoolExecutor

def _summarize_one(article, summarizer):
    # existing single-article logic, extracted into a helper
    ...

with ThreadPoolExecutor(max_workers=len(articles)) as pool:
    results = list(pool.map(_summarize_one, articles, [summarizer]*len(articles)))
```

**Expected impact:** 4 sequential Grok calls per news sheet → ~1 call's worth of
latency. Saves ~45 s per news sheet (3 news sheets × ~45 s = ~2.25 min saved).

---

### 3. Batch All Articles in a Single LLM Prompt

**Files:** `src/screamsheet/renderers/news_articles.py`,
`src/screamsheet/llm/summarizers.py`,
`src/screamsheet/llm/prompts/`

Instead of calling the LLM once per article, send all 4 articles in a single prompt
and ask the model to return 4 summaries in a structured format (e.g., delimited by
`---ARTICLE N---` markers). Parse the response into individual summaries.

Steps:
1. Add a `NewsBatchSummarizer` class in `llm/summarizers.py` with a new
   `news_batch.txt` prompt template.
2. The prompt template embeds all N articles and instructs the model to output N
   summaries with a parseable delimiter.
3. Replace `_generate_summaries()`'s per-article loop with a single
   `NewsBatchSummarizer.generate_summary()` call followed by a response parser.

**Expected impact:** 4 Grok round-trips per news sheet → 1. Saves ~45 s per news
sheet even without threading. Combined with change #2 this is the most efficient
path for news sheets. Can be implemented independently.

**Acceptance criteria:**
- A single LLM call produces all 4 summaries.
- Each summary is correctly associated with its article title and link.
- Fallback: if parsing fails, degrade gracefully to the original per-article path.

---

### 4. Combine Both Horoscopes Into a Single Call

**File:** `src/screamsheet/renderers/sky_horoscope.py`

`SkyHoroscopeSection` iterates over `self.people` and calls `generate_summary()` once
per person. Both readings can be requested in a single prompt by embedding both people's
natal data and asking the model to return two horoscopes separated by a delimiter.

Steps:
1. Add a `HoroscopeBatchSummarizer` (or extend `HoroscopeSummarizer`) in
   `llm/summarizers.py` with a `horoscope_batch.txt` prompt that accepts two
   subjects.
2. Replace the per-person loop in `SkyHoroscopeSection` with a single call.
3. Parse the response into two horoscope strings (one per person).

**Expected impact:** Sky Tonight drops from 3 Gemini calls to 2 (1 highlights + 1
combined horoscope), saving ~15 s.

---

## Recommended Implementation Order

| Step | Change          | Effort | Saving     |
|------|-----------------|--------|------------|
| 1    | Sheet-level parallelism | Low | ~3–4 min (biggest win) |
| 2    | Per-article parallelism | Low | ~2 min     |
| 3    | Batch news prompts      | Medium | ~2 min    |
| 4    | Batch horoscopes        | Low    | ~15 s     |

Start with **#1 then #2** — both are pure concurrency changes with no prompt
engineering. They require only `ThreadPoolExecutor` wrappers around existing code.
Changes #3 and #4 involve new prompt files and response parsers and can follow once
#1 and #2 are verified.

---

## Acceptance Criteria

- [ ] `uv run screamsheet` completes in under 60 seconds on a day when all sports
      leagues have games.
- [ ] All generated PDFs are identical in content to the pre-optimization output.
- [ ] No LLM call is made more than once per run for the same data.
- [ ] All existing tests continue to pass (`uv run pytest`).
- [ ] If any individual LLM call fails, it logs the error and the sheet is still
      generated (with a fallback placeholder), matching current error-handling behavior.

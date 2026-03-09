### Goal
Build processing utilities in `/src/screamsheet` to:
- Score news entries by presence/weighting of keywords (e.g. "Trump", "White House", "diplomacy", world leaders/countries)
- Filter to last 48h (using dateutil)
- Deduplicate on normalized link/title (apply fuzzy matching via e.g. `fuzzywuzzy`/`rapidfuzz`)
- Store batch results to JSON or SQLite for review
- Log errors, skipped items, dedup successes/fails

### Requirements
- Accept normalized dicts from previous module
- Keyword lists/weights in one place for tuning
- Script callable stand-alone for batch candidate processing
- Minimal deps (add only if needed)

### Acceptance Criteria
- Achieves score + dedup + filter for fetch module output
- Leaves filtered+scored news for next step (render)
- Comprehensive error/log coverage

_Parent: #epic-news-pipeline-trump-v-world_
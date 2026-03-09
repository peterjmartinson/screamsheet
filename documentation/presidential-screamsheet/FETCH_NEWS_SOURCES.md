### Goal
Create a module in `/src/screamsheet` to fetch and normalize news entries from 8 sources (7 RSS, 1 HTML):
- HTML with `BeautifulSoup` for https://www.whitehouse.gov/briefing-room/ (special selectors, dynamic fallback for post containers/headlines/dates)
- RSS with `feedparser` (Reuters, AP, BBC, NYT, Politico, NPR, Washington Post)

### Requirements
- Modular: one function or class per source (all in `/src/screamsheet`)
- Common output: dicts with [title, link, published date, summary/description, source name]
- Filter entries with `published >= now() - 48h`
- Unit test (mock small RSS/HTML blobs)
- Minimal deps; only use those in requirements.txt or request addition
- Robust error handling/logging

### Acceptance Criteria
- Module lives in `/src/screamsheet`, can be imported by the pipeline
- All 8 sources process into a common format ready for scoring/dedup
- Handles malformed/missing data gracefully

_Parent: #epic-news-pipeline-trump-v-world_
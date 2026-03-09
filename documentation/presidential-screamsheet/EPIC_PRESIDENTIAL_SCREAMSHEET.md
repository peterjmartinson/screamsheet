## Overview
Implement an automated daily pipeline in `/src/screamsheet` that fetches, parses, scores, deduplicates, and outputs news stories from 8 key political/world news sources (7 RSS, 1 HTML for the White House). The ultimate goal is a printable 'Trump v. World' screamsheet, curated from top recent headlines.

#### Sub-issues (to be created):
1. Fetch & normalize news entries from all sources (with HTML parsing for White House)
2. Scoring, filtering (last 48h), and deduplication by keyword/title/link
3. Output pipeline: review list, select top 4, and render printable PDF

#### Acceptance Criteria
- All code implemented in `/src/screamsheet` (treat all other `/src/*` as legacy/dead)
- Each sub-issue deliverable merges into the new pipeline
- Modular code structure for easy maintenance/extension
- Logging, storage, and error handling per spec

#### Context
Only `/src/screamsheet` is active. Examples/specs provided in previous issues/messages are for context only. This issue tracks all implementation work.

---
This parent issue tracks all work for news aggregation, curation, and the 'Trump v. World' printable screamsheet pipeline.
### Goal
Provide the final pipeline step in `/src/screamsheet` to:
- Select/review top-scored news entries (manual or CLI-assisted curation)
- Generate a printable 'Trump v. World' screamsheet PDF, leveraging existing ReportLab code style
- Optionally include LLM-based summary/analysis if API key is present

### Requirements
- All code in `/src/screamsheet`
- Input: batch JSON or SQLite from earlier processing
- Output: PDF with top 4 stories, headlines, summaries, byline/source, and render date
- Follow established PDF format for printout (one page)
- Error/log gracefully if feed is empty or LLM fails

### Acceptance Criteria
- Generates a PDF with all expected elements, ready for print
- Usable as a CLI step or scheduled task

_Parent: #epic-news-pipeline-trump-v-world_
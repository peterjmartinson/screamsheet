# Recreate team lookup DB and sync scripts from current screamsheet.db 
## Problem
After running the latest branch, my local `screamsheet.db` already contains team tables for all four sports (NHL, MLB, NBA, NFL), and the data appears fully populated. Rather than merging the whole branch or cherry-picking, I want to generate a fresh, clean set of scripts and modules for:
- team lookup table schema
- team sync scripts (one per sport)
- lookup helpers (e.g. lookup by full name or abbreviation)
- relevant tests

## Goal
Use Copilot (or another local LLM) to examine the schemas and contents of my existing local `screamsheet.db`, then generate the code described above in `screamsheet/db/`, matching the actual DB as source of truth.

---

## Exact Prompt to Copilot

> I have a SQLite database at `~/database/screamsheet.db` that is already populated with team tables for all four sports (NHL, MLB, NBA, NFL). I want to create the Python scripts in `src/screamsheet/db/` that:
> 
> 1. Define SQLAlchemy ORM models for the current schema of each team table found in the DB (one model per sport, matching table and column names exactly as in the DB).
> 2. Implement upsert helpers for each table, ensuring idempotent insertion based on the unique team ID (e.g. `team_id`).
> 3. Provide lookup helpers to search by canonical team name, abbreviation, or numeric ID, returning full row dicts.
> 4. Create a sync script for each sport (e.g. `mlb_teams_sync.py`, etc.) that pulls from the relevant public sports API and upserts into the proper table, matching columns and datatypes as found in the DB.
> 5. Add a generic test that (a) creates an in-memory SQLite DB using these models, (b) populates it with a sample team, (c) exercises each lookup and upsert helper, and (d) verifies all results match expectations.
> 
> To start, connect with a SQLite DB explorer (or `sqlite3`) and for each team table, output:
> - Table name
> - Full `CREATE TABLE` statement
> - A few representative rows (SELECT * LIMIT 2)
> 
> Then, generate each script one-by-one, verifying that schema/column types in your code exactly match the DB. Do not fall back on previous repo code; treat the DB as ground truth.

---

## Acceptance Criteria
- All generated Python code matches the schema and contents of the current local DB
- Upsert is idempotent (no duplicates on repeated runs)
- Lookups by full name, abbreviation, or ID work as expected
- Test suite passes on the new helpers

---

**This issue is the canonical prompt and results checkpoint. Paste all generated scripts and test results as a comment or PR linked here.**

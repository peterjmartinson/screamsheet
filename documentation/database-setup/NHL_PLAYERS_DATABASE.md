Issue #51
Goal

Provide a local SQLite cache of NHL player records to minimize API calls and speed up the screamsheet. Author a script that performs a full update/insert of player records (run weekly via cron) and falls back to API on cache-miss.
Environment/paths

Linux DB path: ~/database/nhl_players.db
Windows DB path: C:\database\nhl_players.db
High-level components

SQLite table: players with columns [id|player_id|player_last_name|player_first_name|position|team|update_date|raw_json]
A script to perform a full sync (upsert) of the players table from the canonical NHL API or source.
A helper lookup function used by the NHL screamsheet that: a. Looks up by player_id first. b. If not found, attempts a name-based search (case-insensitive) within the cache. c. On cache-miss, calls the external API, inserts/updates the row, and returns the data.
A weekly cron job on Linux to run the full update script.
Step-by-step work items for Copilot to implement

Schema & DB setup a. Create or initialize the SQLite players DB at the specified path. b. Create the players table with the listed columns and appropriate indexes (by player_id and last name).
Full update/insert script a. Implement a full-sync script that fetches the authoritative player roster dataset from the chosen API and upserts all player rows into SQLite (updating team and position as needed). b. Ensure the script writes update_date (ISO8601) when it refreshes a row. c. Keep raw API JSON in raw_json for debugging.
Lookup helper for screamsheet a. Provide an API function for the screamsheet that tries player_id lookup, then last-name fallback, then API fallback and upsert. b. Handle name collisions (return multiple candidates) and document how selection is decided.
Cron & Windows notes a. Provide a cron example that runs the full update once per week on Linux. b. Document how to run the same update manually on Windows (scheduled task or manual run).
Initialization script a. Provide an init script that creates the DB file, creates the players table and indexes, creates directories, and optionally performs the first full sync (configurable).
Acceptance criteria / Done when
The SQLite DB exists at the Linux and Windows paths with the players schema.
The full-sync script can upsert all players and set update_date.
The lookup function returns local data and falls back to the API on cache miss.
Cron example included and verified manually.
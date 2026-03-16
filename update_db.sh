#!/usr/bin/env bash
# update_db.sh — Sync NHL teams and players into the local SQLite cache.
#
# Usage (manual):
#   bash /home/peter/Code/screamsheet/update_db.sh
#
# Cron (every Monday at 3 am):
#   0 3 * * 1 /home/peter/Code/screamsheet/update_db.sh
#
# Log output:
#   ./logfiles/update_db_log_YYYYMMDD.txt
#   Messages are also echoed to stdout so cron mailers capture them.
#
# Exit codes:
#   0 — sync completed successfully
#   1 — one or more sync steps failed

# Make sure cron jobs can find uv and other user tools
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Resolve script dir so the script works from any working directory
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# Directories and dated log file
mkdir -p ./logfiles
DB_DIR="${SCRIPT_DIR}/src/screamsheet/db"
mkdir -p "$DB_DIR"
DB_PATH="${DB_DIR}/nhl.db"
DATE=$(date +%Y%m%d)
LOG_FILE="./logfiles/update_db_log_${DATE}.txt"

# ---------------------------------------------------------------------------
# Helper: log <message>
#   Prints a timestamped message to stdout AND appends it to the logfile.
# ---------------------------------------------------------------------------
log() {
    local MSG="[$(date +%T)] $*"
    echo "$MSG"
    echo "$MSG" >> "$LOG_FILE"
}

log "--- Update DB Started: $(date) ---"
log "DB path: ${DB_PATH}"

# ---------------------------------------------------------------------------
# Run the team and player syncs.
# PIPESTATUS[0] captures the Python process exit code, not tee's.
# ---------------------------------------------------------------------------
log "Running: uv run db_update --db ${DB_PATH}"
uv run db_update --db "$DB_PATH" 2>&1 | tee -a "$LOG_FILE"
RC=${PIPESTATUS[0]}

if [[ $RC -ne 0 ]]; then
    log "ERROR: update_db failed (exit ${RC})."
else
    log "OK: update_db completed successfully."
fi

log "--- Update DB Finished: $(date) ---"
exit $RC

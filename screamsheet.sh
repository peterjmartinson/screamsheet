#!/bin/bash

# 1. Get the directory where THIS script actually lives.
#    This resolves the symlink so we are always working inside the release folder.
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# 2. Setup directories and logging
mkdir -p ./Files ./logfiles
DATE=$(date +%Y%m%d)
LOG_FILE="./logfiles/screamsheet_log_${DATE}.txt"

echo "--- Execution Started: $(date) ---" >> "$LOG_FILE"

# ---------------------------------------------------------------------------
# Helper: print_sheet <label> <pdf_path>
#   Sends a file to the printer duplex; skips with a warning if missing.
# ---------------------------------------------------------------------------
print_sheet() {
    local LABEL="$1"
    local PDF="$2"
    echo "[$(date +%T)] Printing ${LABEL}..." >> "$LOG_FILE"
    if [[ ! -f "$PDF" ]]; then
        echo "[$(date +%T)] WARNING: ${LABEL} PDF not found, skipping print: ${PDF}" >> "$LOG_FILE"
        return
    fi
    lp -o sides=two-sided-long-edge "$PDF" >> "$LOG_FILE" 2>&1
    local RC=$?
    if [[ $RC -ne 0 ]]; then
        echo "[$(date +%T)] ERROR: ${LABEL} print failed (exit ${RC})." >> "$LOG_FILE"
    else
        echo "[$(date +%T)] OK: ${LABEL} sent to printer." >> "$LOG_FILE"
    fi
}

# ---------------------------------------------------------------------------
# 3. Generate screamsheets by running the module from the src directory.
#    __main__.py produces:
#      ../Files/MLB_gamescores_YYYYMMDD.pdf
#      ../Files/MLB_trade_rumors_YYYYMMDD.pdf
# ---------------------------------------------------------------------------
echo "[$(date +%T)] Generating screamsheets..." >> "$LOG_FILE"
uv run python -m screamsheet >> "$LOG_FILE" 2>&1
RC=$?

if [[ $RC -ne 0 ]]; then
    echo "[$(date +%T)] ERROR: screamsheet generation failed (exit ${RC})." >> "$LOG_FILE"
else
    echo "[$(date +%T)] OK: screamsheets generated successfully." >> "$LOG_FILE"
fi

echo "[$(date +%T)] Generation phase complete. Starting print jobs..." >> "$LOG_FILE"

# ---------------------------------------------------------------------------
# 4. Print the two MLB PDFs duplex (long-edge binding).
# ---------------------------------------------------------------------------
print_sheet "MLB Game Scores"  "./Files/MLB_gamescores_${DATE}.pdf"
print_sheet "MLB Trade Rumors" "./Files/MLB_trade_rumors_${DATE}.pdf"

echo "--- Execution Finished: $(date) ---" >> "$LOG_FILE"

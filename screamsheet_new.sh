#!/bin/bash

# 1. Get the directory where THIS script actually lives.
#    This resolves the symlink so we are always working inside the release folder.
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# 2. Setup directories and logging
mkdir -p ./Files ./logfiles
DATE=$(date +%Y%m%d)
LOG_FILE="./logging/screamsheet_new_log_${DATE}.txt"

echo "--- Execution Started: $(date) ---" >> "$LOG_FILE"

# ---------------------------------------------------------------------------
# Helper: generate_sheet <label> <python_heredoc_file>
#   Runs a Python snippet; logs PASS or FAIL but always continues.
# ---------------------------------------------------------------------------
generate_sheet() {
    local LABEL="$1"
    local PYFILE="$2"
    echo "[$(date +%T)] Generating ${LABEL}..." >> "$LOG_FILE"
    PYTHONPATH=src uv run python "$PYFILE" >> "$LOG_FILE" 2>&1
    local RC=$?
    if [[ $RC -ne 0 ]]; then
        echo "[$(date +%T)] ERROR: ${LABEL} generation failed (exit ${RC})." >> "$LOG_FILE"
    else
        echo "[$(date +%T)] OK: ${LABEL} generated successfully." >> "$LOG_FILE"
    fi
}

# ---------------------------------------------------------------------------
# Helper: print_sheet <label> <pdf_path>
#   Sends a file to the printer; skips with a logged warning if file is
#   missing; logs PASS or FAIL but always continues.
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
# 3. Generate each screamsheet independently via temporary Python scripts.
#    Using temp files avoids heredoc variable-expansion issues and keeps
#    each run fully isolated.
# ---------------------------------------------------------------------------

# --- MLB Screamsheet (Phillies, team_id=143) ---
MLB_PY=$(mktemp /tmp/screamsheet_mlb_XXXXXX.py)
cat > "$MLB_PY" <<PYEOF
from screamsheet import ScreamsheetFactory
sheet = ScreamsheetFactory.create_mlb_screamsheet(
    output_filename='Files/MLB_Scores_${DATE}.pdf',
    team_id=143,
    team_name='Philadelphia Phillies'
)
sheet.generate()
print("MLB screamsheet generated: Files/MLB_Scores_${DATE}.pdf")
PYEOF
generate_sheet "MLB" "$MLB_PY"
rm -f "$MLB_PY"

# --- NHL Screamsheet (Flyers, team_id=4) ---
NHL_PY=$(mktemp /tmp/screamsheet_nhl_XXXXXX.py)
cat > "$NHL_PY" <<PYEOF
from screamsheet import ScreamsheetFactory
sheet = ScreamsheetFactory.create_nhl_screamsheet(
    output_filename='Files/NHL_Scores_${DATE}.pdf',
    team_id=4,
    team_name='Philadelphia Flyers'
)
sheet.generate()
print("NHL screamsheet generated: Files/NHL_Scores_${DATE}.pdf")
PYEOF
generate_sheet "NHL" "$NHL_PY"
rm -f "$NHL_PY"

# --- NBA Screamsheet ---
NBA_PY=$(mktemp /tmp/screamsheet_nba_XXXXXX.py)
cat > "$NBA_PY" <<PYEOF
from screamsheet import ScreamsheetFactory
sheet = ScreamsheetFactory.create_nba_screamsheet(
    output_filename='Files/NBA_Scores_${DATE}.pdf'
)
sheet.generate()
print("NBA screamsheet generated: Files/NBA_Scores_${DATE}.pdf")
PYEOF
generate_sheet "NBA" "$NBA_PY"
rm -f "$NBA_PY"

# --- MLB Trade Rumors News Screamsheet ---
NEWS_PY=$(mktemp /tmp/screamsheet_news_XXXXXX.py)
cat > "$NEWS_PY" <<PYEOF
from screamsheet import ScreamsheetFactory
sheet = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
    output_filename='Files/MLB_Trade_Rumors_${DATE}.pdf',
    max_articles=4,
    include_weather=True
)
sheet.generate()
print("MLB Trade Rumors screamsheet generated: Files/MLB_Trade_Rumors_${DATE}.pdf")
PYEOF
generate_sheet "MLB Trade Rumors" "$NEWS_PY"
rm -f "$NEWS_PY"

echo "[$(date +%T)] Generation phase complete. Starting print jobs..." >> "$LOG_FILE"

# ---------------------------------------------------------------------------
# 4. Print each PDF independently (duplex, long-edge binding).
# ---------------------------------------------------------------------------
print_sheet "MLB"              "./Files/MLB_Scores_${DATE}.pdf"
print_sheet "NHL"              "./Files/NHL_Scores_${DATE}.pdf"
print_sheet "NBA"              "./Files/NBA_Scores_${DATE}.pdf"
print_sheet "MLB Trade Rumors" "./Files/MLB_Trade_Rumors_${DATE}.pdf"

echo "--- Execution Finished: $(date) ---" >> "$LOG_FILE"

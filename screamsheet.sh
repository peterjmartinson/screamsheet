#!/bin/bash

# Make sure cron jobs can find uv and other user tools
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

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
# 3. Generate screamsheets by running the module from the src directory.
#    __main__.py produces PDFs in Files/ and copies each to output.directory
#    (configured in config.yaml).
# ---------------------------------------------------------------------------
echo "[$(date +%T)] Generating screamsheets..." >> "$LOG_FILE"
uv run python -m screamsheet >> "$LOG_FILE" 2>&1
RC=$?

if [[ $RC -ne 0 ]]; then
    echo "[$(date +%T)] ERROR: screamsheet generation failed (exit ${RC})." >> "$LOG_FILE"
else
    echo "[$(date +%T)] OK: screamsheets generated and copied to output directory." >> "$LOG_FILE"
fi

echo "--- Execution Finished: $(date) ---" >> "$LOG_FILE"

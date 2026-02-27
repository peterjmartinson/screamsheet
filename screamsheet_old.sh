#!/bin/bash

# 1. Get the directory where THIS script actually lives
# This resolves the symlink so we are working inside the release folder
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# 2. Setup logging
mkdir -p ./Files ./logfiles
LOG_FILE="./logfiles/screamsheet_log_$(date +%Y%m%d).txt"

echo "--- Execution Started: $(date) ---" >> "$LOG_FILE"

# 3. Use the UV-managed environment (.venv) instead of 'env'
# This points to the environment uv sync just built
./.venv/bin/python ./src/screamsheet.py >> "$LOG_FILE" 2>&1

# 4. Printing (using relative paths to ensure it finds the files we just made)
# Note: I removed the backslashes from the date command; 
# they are usually only needed inside a crontab string.
lp -o sides=two-sided-long-edge "./Files/NFL_Scores_$(date +%Y%m%d).pdf" >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge "./Files/NHL_Scores_$(date +%Y%m%d).pdf" >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge "./Files/NBA_Scores_$(date +%Y%m%d).pdf" >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge "./Files/MLB_News_$(date +%Y%m%d).pdf" >> "$LOG_FILE" 2>&1

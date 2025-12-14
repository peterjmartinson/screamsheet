#!/bin/bash
mkdir -p /home/peter/Code/screamsheet_live/Files /home/peter/Code/screamsheet_live/logfiles
LOG_FILE="/home/peter/Code/screamsheet_live/logfiles/screamsheet_log_$(date +\%Y\%m\%d).txt"
/home/peter/Code/screamsheet_live/env/bin/python /home/peter/Code/screamsheet_live/src/screamsheet.py >> "$LOG_FILE" 2>&1
# lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/MLB_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet_live/Files/NFL_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet_live/Files/NHL_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet_live/Files/NBA_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet_live/Files/MLB_News_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1

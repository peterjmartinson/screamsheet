#!/bin/bash
LOG_FILE="/home/peter/Code/screamsheet/logfiles/screamsheet_log_$(date +\%Y\%m\%d).txt"
/home/peter/Code/screamsheet/env/bin/python /home/peter/Code/screamsheet/src/screamsheet.py >> "$LOG_FILE" 2>&1
# lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/MLB_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/NFL_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/NHL_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/NBA_Scores_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1
lp -o sides=two-sided-long-edge /home/peter/Code/screamsheet/Files/MLB_News_$(date +\%Y\%m\%d).pdf >> "$LOG_FILE" 2>&1

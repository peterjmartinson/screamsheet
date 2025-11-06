import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams
from datetime import date, timedelta

# --- 1. Setup: Date and Team Name Mapping ---
today = date.today()
yesterday = today - timedelta(days=1)
date_string = yesterday.strftime('%m/%d/%Y')

print(f"Fetching NBA scores for: {date_string}")

# Create the tricode (abbreviation) to full name mapping
nba_teams = teams.get_teams()
tricode_to_name = {
    team['abbreviation']: team['full_name'] 
    for team in nba_teams
}

# --- 2. Retrieve Yesterday's NBA Data ---
gamefinder = leaguegamefinder.LeagueGameFinder(
    date_from_nullable=date_string,
    date_to_nullable=date_string
)
# The data frame has two rows per game (one for each team)
raw_games_df = gamefinder.get_data_frames()[0]

# --- 3. Process and Format the Data ---
games = []

if not raw_games_df.empty:
    # Key columns needed for processing
    df = raw_games_df[['GAME_ID', 'GAME_DATE', 'MATCHUP', 'TEAM_ABBREVIATION', 'WL', 'PTS']]
    
    # Identify unique games based on GAME_ID
    unique_game_ids = df['GAME_ID'].unique()
    
    for game_id in unique_game_ids:
        # Get the two rows corresponding to this single game
        game_data = df[df['GAME_ID'] == game_id].reset_index(drop=True)
        
        # Ensure we have exactly two teams (safety check)
        if len(game_data) != 2:
            print(f"Skipping incomplete game data for GAME_ID: {game_id}")
            continue
            
        # Determine the home and away teams using the MATCHUP format
        # NBA Matchups are always 'AWAY_TEAM @ HOME_TEAM'
        matchup_str = game_data.iloc[0]['MATCHUP']
        
        if '@' in matchup_str:
            # The 'home' team is the one whose abbreviation appears AFTER the '@'
            away_tri, home_tri = matchup_str.split(' @ ')
        else:
            # Handle cases where the home team is first (e.g., if MATCHUP only shows one team's perspective)
            # This is less common, but ensures robust parsing. We'll use the WL column logic below.
            continue 

        # Extract data for both teams in the game
        team_1 = game_data.iloc[0]
        team_2 = game_data.iloc[1]
        
        # Identify which row is Home and which is Away
        if team_1['TEAM_ABBREVIATION'] == home_tri:
            home_team_data = team_1
            away_team_data = team_2
        elif team_2['TEAM_ABBREVIATION'] == home_tri:
            home_team_data = team_2
            away_team_data = team_1
        else:
            # This handles unexpected Matchup formats or data inconsistencies
            print(f"Could not reliably determine home/away for GAME_ID: {game_id}")
            continue

        # Build the dictionary in the exact format you requested
        game_info = {
            # Format the date nicely
            "gameDate": home_team_data['GAME_DATE'],
            
            # Use the tricode_to_name mapping to get the full team names
            "away_team": tricode_to_name.get(away_team_data['TEAM_ABBREVIATION'], away_team_data['TEAM_ABBREVIATION']),
            "home_team": tricode_to_name.get(home_team_data['TEAM_ABBREVIATION'], home_team_data['TEAM_ABBREVIATION']),
            
            "away_score": int(away_team_data['PTS']),
            "home_score": int(home_team_data['PTS']),
            
            # Use 'Final' for the status, as this data is only for completed games
            "status": "Final"
        }
        games.append(game_info)

# --- 4. Display the Final Result ---
if games:
    print("\n--- Formatted NBA Game Data (List of Dictionaries) ---")
    for game in games:
        print(game)
else:
    print("\nNo games were successfully processed into the target format.")
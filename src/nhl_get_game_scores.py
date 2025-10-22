import requests
from datetime import datetime, timedelta

def get_yesterdays_nhl_scores() -> list:
    """
    Fetches NHL scores for the previous day and structures them 
    into a list of dictionaries, mirroring the requested MLB format.
    """
    # 1. Determine Yesterday's Date in YYYY-MM-DD format
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')
    
    # Unofficial NHL API endpoint for a specific date's schedule/scores
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    
    # Initialize the list to store the results
    nhl_scores_list = []

    print(f"Fetching NHL scores for: {date_str} from {url}")

    try:
        # 2. Make the API Request
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        
        # 3. Process the JSON data
        # Navigate to the games list. Assumes 'gameWeek' has at least one entry.
        games_for_the_day = data.get('gameWeek', [{}])[0].get('games', [])

        for game in games_for_the_day:
            game_state = game['gameState'] # e.g., 'FINAL', 'OFF', 'LIVE', 'PRE'
            
            # Use 'OFF' (Official/Completed) or 'FINAL' for finished games, and 'LIVE' for in-progress games
            if game_state in ['FINAL', 'OFF', 'LIVE']:
                
                # Extract team names and scores
                # The API uses abbreviations (abbrev) and a full name (placeName) 
                # We'll use the full team name for better readability, similar to your MLB example.
                away_full_name = game['awayTeam']['placeName']['default']
                home_full_name = game['homeTeam']['placeName']['default']
                
                game_info = {
                    # NHL API uses 'startTimeUTC' for the date/time string
                    "gameDate": game.get('startTimeUTC'),
                    "away_team": away_full_name,
                    "home_team": home_full_name,
                    "away_score": game['awayTeam']['score'],
                    "home_score": game['homeTeam']['score'],
                    "status": game_state
                }
                nhl_scores_list.append(game_info)
            # Future games (PRE, FUT) are skipped to focus on scores

        return nhl_scores_list

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from NHL API: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []


if __name__ == "__main__":
    scores_list = get_yesterdays_nhl_scores()
    
    if scores_list:
        print("\n--- Yesterday's NHL Scores (List of Dicts) ---")
        for game in scores_list:
            print(f"  {game}")
    else:
        print("\nNo game scores found for yesterday, or an error occurred.")

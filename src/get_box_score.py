import requests
from datetime import datetime, timedelta

def get_last_game_boxscore(team_id: int):
    """
    Fetches the box score data for a team's last completed game.

    Args:
        team_id: The MLB team ID (e.g., Phillies is 143).

    Returns:
        A dictionary with parsed box score data, or None if not found.
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
    
    try:
        # Step 1: Find the game ID for yesterday's game
        params = {'sportId': 1, 'teamId': team_id, 'date': yesterday}
        schedule_response = requests.get(schedule_url, params=params)
        schedule_response.raise_for_status()
        schedule_data = schedule_response.json()
        
        game_pk = None
        if 'dates' in schedule_data and schedule_data['dates']:
            for game in schedule_data['dates'][0]['games']:
                # Ensure the game is completed
                if game['status']['statusCode'] == 'F':
                    if game['teams']['away']['team']['id'] == team_id or game['teams']['home']['team']['id'] == team_id:
                        game_pk = game['gamePk']
                        break
        
        if not game_pk:
            print(f"No completed game found for team ID {team_id} on {yesterday}.")
            return None
        
        # Step 2: Fetch the detailed box score using the game ID
        boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        boxscore_response = requests.get(boxscore_url)
        boxscore_response.raise_for_status()
        boxscore_data = boxscore_response.json()

        return boxscore_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_boxscore(boxscore_data, team_id: int):
    """
    Parses a box score dictionary to extract player stats for a specific team.

    Args:
        boxscore_data: The JSON response from the boxscore API.
        team_id: The ID of the team to parse stats for.

    Returns:
        A dictionary with hitting and pitching stats.
    """
    if not boxscore_data:
        return {'batting_stats': [], 'pitching_stats': []}

    home_team_id = boxscore_data['teams']['home']['team']['id']
    away_team_id = boxscore_data['teams']['away']['team']['id']
    
    target_team = 'home' if home_team_id == team_id else 'away'
    
    batting_stats = []
    pitching_stats = []

    players = boxscore_data['teams'][target_team]['players']
    
    # Parse hitting stats
    for player_id, player_data in players.items():
        if player_data['stats'].get('batting'):
            stats = player_data['stats']['batting']
            batting_stats.append({
                'name': player_data['person']['fullName'],
                'AB': stats.get('atBats', 0),
                'R': stats.get('runs', 0),
                'H': stats.get('hits', 0),
                'HR': stats.get('homeRuns', 0),
                'RBI': stats.get('rbi', 0),
                'BB': stats.get('baseOnBalls', 0),
                'SO': stats.get('strikeOuts', 0)
            })

    # Parse pitching stats
    for player_id, player_data in players.items():
        if player_data['stats'].get('pitching'):
            stats = player_data['stats']['pitching']
            pitching_stats.append({
                'name': player_data['person']['fullName'],
                'IP': stats.get('inningsPitched', '0.0'),
                'H': stats.get('hits', 0),
                'R': stats.get('runs', 0),
                'ER': stats.get('earnedRuns', 0),
                'BB': stats.get('baseOnBalls', 0),
                'SO': stats.get('strikeOuts', 0)
            })

    return {'batting_stats': batting_stats, 'pitching_stats': pitching_stats}

if __name__ == '__main__':

    phillies = 143
    box_score = get_last_game_boxscore(phillies)
    parsed_score = parse_boxscore(box_score, phillies)
    print(parsed_score)

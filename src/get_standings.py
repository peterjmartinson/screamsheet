import requests
import pandas as pd

# Get current season (MLB typically runs April-October)
from datetime import datetime
season = datetime.now().year

# API endpoint for both AL (103) and NL (104)
base_url = f"https://statsapi.mlb.com"
url = f"{base_url}/api/v1/standings?season={season}&leagueId=103,104"

def get_division(record):
    url = base_url + record.get("division", {}).get("link", {})
    response = requests.get(url)
    data = response.json()
    division = data["divisions"][0].get("name")
    return division

response = requests.get(url)
response.raise_for_status()  # Raises an error if the request failed

data = response.json()

team_list = []
for record in data.get("records", []):
    division = get_division(record)
    for team in record.get("teamRecords", []):
        name = team.get("team", {}).get("name")
        wins = team["leagueRecord"].get("wins")
        losses = team["leagueRecord"].get("losses")
        ties = team["leagueRecord"].get("ties")
        pct = team["leagueRecord"].get("pct")
        rank = team.get("divisionRank")
        team_obj = {
            "division": division,
            "team": name,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "pct": pct,
            "divisionRank": rank
        }
        team_list.append(team_obj)

standings = pd.DataFrame(team_list)

# Sort by division (ascending) and then wins (descending)
df_sorted = standings.sort_values(by=['division', 'divisionRank'], ascending=[True, True])

# Now, print the results. You can group by division and iterate through each group.
for division_name, group in df_sorted.groupby('division'):
    print(f"\n### {division_name}\n")
    print(group[['team', 'wins', 'losses', 'ties', 'pct']].to_string(index=False))





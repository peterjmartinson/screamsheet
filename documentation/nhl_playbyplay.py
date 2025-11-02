
pbp = pbp_res.json()

pbp["gameState"] == "OFF"
pbp["periodDescriptor"]["number"] >= 3 # says whether went into overtime
awayTeam = pbp["awayTeam"]
    awayTeam["id"] = away_team_id
    awayTeam["commonName"]["default"] == "Maple Leafs"
    awayTeam["placeName"]["default"] == "Toronto"
    awayTeam["score"] == 3
    awayTeam["sog"] = 36 # shots on goal

    homeTeam["id"] = home_team_id
    homeTeam["commonName"]["default"] == "Blue Jackets"
    homeTeam["placeName"]["default"] == "Columbus"
    homeTeam["score"] == 6
    homeTeam["sog"] = 24 # shots on goal
plays = pbp["plays"] # list of plays

for p in plays:
    p["typeDescKey"] == "faceoff" # type of event
    p["periodDescriptor"]["number"] == 1 # which period we in
    p["timeRemaining"] == "20:00" # minutes left
    details = p["details"]
    interesting_events = [
        'goal',
        'hit',
        'penalty',
        'shot-on-goal',
        'takeaway'
    ]
    
    {
      "eventId": 71,
      "periodDescriptor": {
        "number": 1,
        "periodType": "REG",
        "maxRegulationPeriods": 3
      },
      "timeInPeriod": "01:35",
      "timeRemaining": "18:25",
      "situationCode": "1551",
      "homeTeamDefendingSide": "right",
      "typeCode": 506,
      "typeDescKey": "shot-on-goal",
      "sortOrder": 25,
      "details": {
        "xCoord": 58,
        "yCoord": -28,
        "zoneCode": "O",
        "shotType": "wrist",
        "shootingPlayerId": 8484258,
        "goalieInNetId": 8482761,
        "eventOwnerTeamId": 21,
        "awaySOG": 1,
        "homeSOG": 0
      }
    },

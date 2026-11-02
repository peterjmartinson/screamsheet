# Specification: International Soccer Screamsheet (Issue #115)

## Target Audience & Editorial Vision
A double-sided daily print publication (8.5" x 11") tailored for an 11-year-old reader who idolizes Cristiano Ronaldo, passionately tracks Al-Nassr, and follows marquee European and international football (UEFA Champions League, Premier League, La Liga, and International tournaments).

---

## 1. Data Sourcing & Endpoint Mapping (API-Football v3)

### 1.1 API-Sports Free-Tier Budget Management
* **Budget**: 100 requests / day (free tier on `https://v3.football.api-sports.io/`).
* **Strategy**: Minimize daily requests to **4–6 calls per morning** using targeted queries, persistent SQLite caching, and bulk date filtering.

```
Daily Morning Pipeline:
  Step 1: Check yesterday's fixtures for target leagues   (1-2 requests)
  Step 2: Fetch MOTD Lineups, Statistics, & Events       (3 requests)
  Step 3: Fetch Standings if cache expired (24h TTL)     (0-2 requests)
  Total: 4 to 6 requests / day (Leaves >90 calls for buffer/dev)
```

### 1.2 Target League & Team IDs

| Competition / Team | API-Football ID | Type | Notes |
| :--- | :--- | :--- | :--- |
| **Saudi Pro League** | `league=307` | League | Al-Nassr domestic fixtures |
| **UEFA Champions League** | `league=2` | Cup | Primary European marquee stage |
| **Premier League** | `league=39` | League | Top English fixtures |
| **La Liga** | `league=140` | League | Spanish marquee fixtures (Real Madrid, Barca) |
| **AFC Champions League Elite** | `league=17` | Cup | Al-Nassr continental fixtures |
| **King's Cup (Saudi)** | `league=308` | Cup | Domestic cup fixtures for Al-Nassr |
| **UEFA Nations League** | `league=5` | International | Portugal fixtures |
| **European Championship Qualifiers** | `league=32` / `league=3` | International | Portugal fixtures |
| **FIFA World Cup Qualifiers** | `league=32` | International | Portugal fixtures |
| **Al-Nassr FC** | `team=1005` | Club | Primary affinity club |
| **Portugal National Team** | `team=27` | Country | Primary affinity national team |
| **Cristiano Ronaldo** | `player=874` | Player | Primary athlete spotlight |

### 1.3 Exact Endpoint Signatures

#### A. Yesterday's Target Fixtures (1 Request)
```http
GET https://v3.football.api-sports.io/fixtures?date={YYYY-MM-DD}&timezone=America/New_York
Headers:
  x-apisports-key: <API_KEY>
```
*Filter client-side for matches belonging to target leagues (IDs `307, 2, 39, 140, 17, 308, 5, 32, 10`) or matches featuring `team=1005` (Al-Nassr) or `team=27` (Portugal).*

#### B. Deep-Dive Match of the Day (3 Requests)
```http
GET https://v3.football.api-sports.io/fixtures/lineups?fixture={fixture_id}
GET https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}
GET https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}
```

#### C. Standings (Cached with 24-Hour TTL)
```http
GET https://v3.football.api-sports.io/standings?league=307&season={season_year}
GET https://v3.football.api-sports.io/standings?league=39&season={season_year}
```

### 1.4 Resilient Caching & Off-Day Fallback Strategy
1. **Fixture Immutability**: Historical matches never change once `status.short == "FT" | "AET" | "PEN"`. Cache fixture details, lineups, statistics, and events permanently in `screamsheet.db` under `soccer_fixtures`.
2. **Standings TTL**: Standings responses are cached with a 24-hour expiration timestamp.
3. **Hiatus / Matchless Day Strategy**:
   * If zero competitive matches occurred yesterday across all target leagues:
     * **Lookback Buffer**: Check the previous 48–72 hours for an unfeatured Al-Nassr or Portugal match.
     * **Standby Mode**: If no recent matches exist, activate the **CR7 Career Tracker & Upcoming Fixtures** fallback payload (no extra API calls required if player season stats are cached).

---

## 2. Payload Schema & Transformation Contract

```json
{
  "meta": {
    "date": "2026-11-01",
    "display_date": "Sunday, November 1, 2026",
    "edition_title": "International Football Screamsheet",
    "subscriber_name": "Leo",
    "has_live_matches": true
  },
  "scores_section": [
    {
      "league_id": 307,
      "league_name": "Saudi Pro League",
      "league_country": "Saudi Arabia",
      "matches": [
        {
          "fixture_id": 1204851,
          "home_team": "Al-Nassr",
          "away_team": "Al-Hilal",
          "home_score": 3,
          "away_score": 1,
          "status": "FT",
          "is_derby": true,
          "aggregate": null,
          "penalties": null,
          "goal_timeline": [
            { "minute": 14, "extra": null, "team": "home", "player": "C. Ronaldo", "is_penalty": false, "is_own_goal": false },
            { "minute": 42, "extra": null, "team": "away", "player": "A. Mitrović", "is_penalty": false, "is_own_goal": false },
            { "minute": 78, "extra": null, "team": "home", "player": "C. Ronaldo", "is_penalty": true, "is_own_goal": false },
            { "minute": 90, "extra": 3, "team": "home", "player": "Talísca", "is_penalty": false, "is_own_goal": false }
          ]
        }
      ]
    }
  ],
  "standings_section": [
    {
      "league_id": 307,
      "league_name": "Saudi Pro League",
      "rows": [
        { "rank": 1, "team_name": "Al-Hilal", "mp": 10, "w": 9, "d": 1, "l": 0, "gd": "+21", "pts": 28, "form": "WWWDW", "is_affinity": false },
        { "rank": 2, "team_name": "Al-Nassr", "mp": 10, "w": 8, "d": 2, "l": 0, "gd": "+19", "pts": 26, "form": "WWWWW", "is_affinity": true },
        { "rank": 3, "team_name": "Al-Ittihad", "mp": 10, "w": 8, "d": 0, "l": 2, "gd": "+14", "pts": 24, "form": "LWWWW", "is_affinity": false },
        { "rank": 4, "team_name": "Al-Shabab", "mp": 10, "w": 7, "d": 0, "l": 3, "gd": "+8", "pts": 21, "form": "WLWLW", "is_affinity": false },
        { "rank": 5, "team_name": "Al-Qadsiah", "mp": 10, "w": 6, "d": 1, "l": 3, "gd": "+5", "pts": 19, "form": "DWLWW", "is_affinity": false }
      ]
    },
    {
      "league_id": 39,
      "league_name": "Premier League",
      "rows": [
        { "rank": 1, "team_name": "Liverpool", "mp": 10, "w": 8, "d": 1, "l": 1, "gd": "+11", "pts": 25, "form": "WDWWW", "is_affinity": false },
        { "rank": 2, "team_name": "Manchester City", "mp": 10, "w": 7, "d": 2, "l": 1, "gd": "+10", "pts": 23, "form": "LWWWD", "is_affinity": false },
        { "rank": 3, "team_name": "Arsenal", "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+6", "pts": 18, "form": "LDWDL", "is_affinity": false },
        { "rank": 4, "team_name": "Chelsea", "mp": 10, "w": 5, "d": 3, "l": 2, "gd": "+8", "pts": 18, "form": "DWLDW", "is_affinity": false }
      ]
    }
  ],
  "featured_match": {
    "fixture_id": 1204851,
    "competition": "Saudi Pro League • Matchday 10",
    "venue": "Al-Awwal Park, Riyadh",
    "attendance": "24,800",
    "home_team": { "name": "Al-Nassr", "formation": "4-2-3-1", "score": 3 },
    "away_team": { "name": "Al-Hilal", "formation": "4-3-3", "score": 1 },
    "status_detail": "Full Time",
    "ronaldo_spotlight": {
      "featured": true,
      "minutes": 90,
      "goals": 2,
      "assists": 0,
      "shots_on_target": "4/5",
      "rating": "8.8",
      "career_goals_total": 916
    },
    "editorial_summary": "Cristiano Ronaldo delivered a masterclass in the Riyadh Derby, netting a stunning first-half volley before sealing victory with a clinical 78th-minute penalty. Al-Nassr snapped Al-Hilal's unbeaten streak with relentless high pressing and dominant midfield control.",
    "starting_xi": {
      "home": [
        { "number": 24, "name": "Bento", "pos": "G", "rating": "7.2", "is_captain": false },
        { "number": 2, "name": "S. Al-Ghannam", "pos": "D", "rating": "6.8", "is_captain": false },
        { "number": 3, "name": "M. Simakan", "pos": "D", "rating": "7.4", "is_captain": false },
        { "number": 27, "name": "A. Laporte", "pos": "D", "rating": "7.5", "is_captain": false },
        { "number": 83, "name": "S. Najdi", "pos": "D", "rating": "6.9", "is_captain": false },
        { "number": 17, "name": "A. Al-Khaibari", "pos": "M", "rating": "7.1", "is_captain": false },
        { "number": 25, "name": "Otávio", "pos": "M", "rating": "7.6", "is_captain": false },
        { "number": 94, "name": "Talísca", "pos": "F", "rating": "8.1", "is_captain": false },
        { "number": 20, "name": "Á. Brozović", "pos": "M", "rating": "7.7", "is_captain": false },
        { "number": 10, "name": "S. Mané", "pos": "F", "rating": "7.3", "is_captain": false },
        { "number": 7, "name": "C. Ronaldo", "pos": "F", "rating": "8.8", "is_captain": true }
      ],
      "away": [
        { "number": 37, "name": "Y. Bono", "pos": "G", "rating": "6.5", "is_captain": false },
        { "number": 20, "name": "J. Cancelo", "pos": "D", "rating": "7.0", "is_captain": false },
        { "number": 3, "name": "K. Koulibaly", "pos": "D", "rating": "6.2", "is_captain": false },
        { "number": 5, "name": "Ali Al-Bulaihi", "pos": "D", "rating": "5.9", "is_captain": false },
        { "number": 6, "name": "Renan Lodi", "pos": "D", "rating": "6.4", "is_captain": false },
        { "number": 8, "name": "R. Neves", "pos": "M", "rating": "7.1", "is_captain": false },
        { "number": 22, "name": "S. Milinković-Savić", "pos": "M", "rating": "6.9", "is_captain": false },
        { "number": 29, "name": "Salem Al-Dawsari", "pos": "F", "rating": "6.7", "is_captain": true },
        { "number": 77, "name": "Malcom", "pos": "F", "rating": "6.5", "is_captain": false },
        { "number": 9, "name": "A. Mitrović", "pos": "F", "rating": "7.3", "is_captain": false },
        { "number": 11, "name": "Marcos Leonardo", "pos": "F", "rating": "6.3", "is_captain": false }
      ]
    },
    "bench_subs": [
      { "minute": 68, "team": "away", "in": "Nasser Al-Dawsari", "out": "Renan Lodi" },
      { "minute": 82, "team": "home", "in": "A. Ghareeb", "out": "S. Mané" }
    ],
    "key_events": [
      { "minute": "14'", "type": "GOAL", "team": "home", "player": "C. Ronaldo", "detail": "Volley into top right corner" },
      { "minute": "31'", "type": "YELLOW", "team": "away", "player": "Ali Al-Bulaihi", "detail": "Tactical foul" },
      { "minute": "42'", "type": "GOAL", "team": "away", "player": "A. Mitrović", "detail": "Header from corner" },
      { "minute": "78'", "type": "GOAL", "team": "home", "player": "C. Ronaldo (P)", "detail": "Bottom left penalty" },
      { "minute": "90+3'", "type": "GOAL", "team": "home", "player": "Talísca", "detail": "Breakaway counter" }
    ],
    "team_metrics": [
      { "label": "Possession", "home": "48%", "away": "52%" },
      { "label": "Expected Goals (xG)", "home": "2.41", "away": "1.18" },
      { "label": "Total Shots (On Target)", "home": "16 (8)", "away": "11 (4)" },
      { "label": "Corner Kicks", "home": "6", "away": "5" },
      { "label": "Fouls Committed", "home": "12", "away": "15" },
      { "label": "Yellow / Red Cards", "home": "1 / 0", "away": "3 / 0" },
      { "label": "Goalkeeper Saves", "home": "3", "away": "5" }
    ]
  }
}
```

---

## 3. Deterministic Editorial & Ranking Algorithms

```python
"""soccer_ranking.py — MOTD selection and hiatus fallback routing."""
from typing import Any, Dict, List, Optional

AL_NASSR_TEAM_ID = 1005
PORTUGAL_TEAM_ID = 27

MARQUEE_CLUBS = {
    541: "Real Madrid",
    529: "Barcelona",
    50: "Manchester City",
    40: "Liverpool",
    42: "Arsenal",
    49: "Chelsea",
    33: "Manchester United",
    157: "Bayern Munich",
    85: "Paris Saint-Germain",
    505: "Inter Milan",
    496: "Juventus",
}

LEAGUE_TIER_POINTS = {
    2: 100,    # UEFA Champions League
    17: 85,    # AFC Champions League Elite
    39: 75,    # Premier League
    140: 65,   # La Liga
    307: 60,   # Saudi Pro League
    5: 70,     # UEFA Nations League
    32: 70,    # World Cup Qualifiers
    308: 50,   # King's Cup
}


def score_fixture_for_motd(fixture: Dict[str, Any]) -> float:
    """Calculate an excitement score for an 11-year-old reader."""
    home_id = fixture.get("teams", {}).get("home", {}).get("id")
    away_id = fixture.get("teams", {}).get("away", {}).get("id")

    # 1. Hard Affinity Locks
    if AL_NASSR_TEAM_ID in (home_id, away_id):
        return 10000.0  # Automatic lock
    if PORTUGAL_TEAM_ID in (home_id, away_id):
        return 8000.0   # Secondary automatic lock

    league_id = fixture.get("league", {}).get("id")
    score = float(LEAGUE_TIER_POINTS.get(league_id, 30))

    # 2. Marquee Club Multiplier
    marquee_count = sum(1 for tid in (home_id, away_id) if tid in MARQUEE_CLUBS)
    score += marquee_count * 25.0
    if marquee_count == 2:
        score += 20.0  # Derby / heavyweight clash bonus

    # 3. Goal Volume & High-Scoring Thrills
    goals_home = fixture.get("goals", {}).get("home") or 0
    goals_away = fixture.get("goals", {}).get("away") or 0
    total_goals = goals_home + goals_away
    score += total_goals * 8.0

    # 4. Competitive Margin & Drama
    goal_diff = abs(goals_home - goals_away)
    if goal_diff == 0 and total_goals > 0:
        score += 25.0  # High-scoring draw (e.g. 2-2, 3-3)
    elif goal_diff == 1:
        score += 20.0  # 1-goal nail-biter

    status_short = fixture.get("fixture", {}).get("status", {}).get("short", "")
    if status_short in ("AET", "PEN"):
        score += 35.0  # Knockout extra time or penalties

    return score


def select_match_of_the_day(completed_fixtures: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the highest-ranking fixture from yesterday."""
    if not completed_fixtures:
        return None
    return max(completed_fixtures, key=score_fixture_for_motd)
```

### 3.1 Fallback Content Rules (Zero Matches Yesterday)
When `completed_fixtures` is empty:
1. **Lookback Scan**: The system queries the prior 48 hours for any Al-Nassr or Portugal match not yet published.
2. **Hiatus Replacement Module**: If no match is found, the Back Page transitions from Match Deep-Dive to:
   * **The Cristiano Ronaldo Milestone Watch**: Lifetime goals tally (counting to 1,000 goals), goals per club breakdown (Sporting, Man Utd, Real Madrid, Juventus, Al-Nassr, Portugal).
   * **Upcoming Matchday Preview**: Al-Nassr's next scheduled fixture, venue, and broadcast info.
   * **European Golden Shoe Standings**: Top 5 scorers across major world leagues.

---

## 4. Print Layout & Typography Specification (8.5" x 11")

### Page Dimensions & Grid Setup
- **Page Size**: Standard Letter (8.5" x 11.0" / 612pt x 792pt).
- **Margins**: Top/Bottom: 24pt (0.33"), Left/Right: 24pt (0.33").
- **Printable Area**: 564pt width x 744pt height.
- **Color Palette**:
  * Primary Accent: Dark Navy (`#0A192F` or `#1E293B`)
  * Affinity Gold (Al-Nassr): Vibrant Gold/Amber (`#EAB308` / `#F59E0B`)
  * Table Header Fill: Light Cool Gray (`#F1F5F9`)
  * Border Stroke: 0.5pt subtle gray (`#CBD5E1`)

---

### Front Page ASCII Wireframe: Scores & Standings

```
+-------------------------------------------------------------------------+
| [LOGO]              INTERNATIONAL FOOTBALL SCREAMSHEET                  |
|                        Sunday, November 1, 2026                         |
+-------------------------------------------------------------------------+
|  YESTERDAY'S MATCH SCORES                                               |
|  +-- SAUDI PRO LEAGUE ------------------------------------------------+ |
|  | Al-Nassr               3   FINAL  | Al-Ittihad            2  FINAL | |
|  | @ Al-Hilal             1          | @ Al-Shabab           0        | |
|  |   [Ronaldo 14', 78'(P), Talisca]  |   [Benzema 34', 68']           | |
|  +-- UEFA CHAMPIONS LEAGUE -------------------------------------------+ |
|  | Real Madrid            3   FINAL  | Bayern Munich         2  FINAL | |
|  | @ Dortmund             2          | @ Barcelona           4        | |
|  |   [Vinicius 62', 86', Mbappe 71'] |   [Raphinha 36', 56', Lewa]    | |
|  +-- PREMIER LEAGUE --------------------------------------------------+ |
|  | Manchester City        2   FINAL  | Liverpool             2  FINAL | |
|  | @ Bournemouth          1          | @ Arsenal             2        | |
+-------------------------------------------------------------------------+
|  LEAGUE STANDINGS                                                       |
|  +-- SAUDI PRO LEAGUE --------------+ +-- PREMIER LEAGUE ---------------+ |
|  | #  Club          MP  GD Pts Form | | #  Club          MP  GD Pts Form| |
|  | 1  Al-Hilal      10 +21  28 WWWD | | 1  Liverpool     10 +11  25 WDWW| |
|  | 2* Al-Nassr      10 +19  26 WWWW | | 2  Man City      10 +10  23 LWWW| |
|  | 3  Al-Ittihad    10 +14  24 LWWW | | 3  Arsenal       10  +6  18 LDWD| |
|  | 4  Al-Shabab     10  +8  21 WLWL | | 4  Chelsea       10  +8  18 DWLD| |
|  | 5  Al-Qadsiah    10  +5  19 DWLW | | 5  Nottm Forest  10  +4  19 WWDW| |
|  +----------------------------------+ +---------------------------------+ |
|  FOOTER: Screamsheet v2.1 • api-sports.io • DISTRACTEDFORTUNE.COM       |
+-------------------------------------------------------------------------+
```

---

### Back Page ASCII Wireframe: Match of the Day Deep Dive

```
+-------------------------------------------------------------------------+
| MATCH OF THE DAY: RIYADH DERBY                                          |
| Saudi Pro League • Matchday 10 • Al-Awwal Park (Att: 24,800)            |
+-------------------------------------------------------------------------+
|                       AL-NASSR  3  -  1  AL-HILAL                       |
|          Scorers: Ronaldo 14', 78'(P), Talisca 90+3' | Mitrovic 42'     |
+-------------------------------------------------------------------------+
| [CR7 SPOTLIGHT] Rating: 8.8 ★ | 2 Goals | 5 Shots | Career Total: 916   |
+-------------------------------------------------------------------------+
| THE MATCH IN 60 SECONDS:                                                |
| Cristiano Ronaldo electrified the home crowd with an opening volley     |
| and a late penalty to claim derby bragging rights over Al-Hilal.        |
+------------------------------------+------------------------------------+
| STARTING LINEUPS & RATINGS         | MATCH STATS & EVENT TIMELINE       |
|                                    |                                    |
| AL-NASSR (4-2-3-1)                 | STATISTIC        NASSR    HILAL    |
| 24 Bento (GK)                7.2   | Possession         48%      52%    |
| 2  S. Al-Ghannam (RB)        6.8   | Expected Goals    2.41     1.18    |
| 27 A. Laporte (CB)           7.5   | Shots (On Target) 16(8)    11(4)   |
| 20 A. Brozovic (CM)          7.7   | Corner Kicks         6        5    |
| 94 Talisca (AM)              8.1   | Fouls Committed     12       15    |
| 10 S. Mane (LW)              7.3   | Cards (Y/R)        1/0      3/0    |
| 7* C. Ronaldo (ST, C)        8.8 ★ | Goalkeeper Saves     3        5    |
|                                    |                                    |
| AL-HILAL (4-3-3)                   | TIMELINE HIGHLIGHTS                |
| 37 Y. Bono (GK)              6.5   | 14'  [GOAL] Ronaldo (Volley)       |
| 3  K. Koulibaly (CB)         6.2   | 31'  [CARD] Al-Bulaihi (Yellow)    |
| 8  R. Neves (CM)             7.1   | 42'  [GOAL] Mitrovic (Header)      |
| 29 S. Al-Dawsari (LW, C)     6.7   | 78'  [GOAL] Ronaldo (Penalty)      |
| 9  A. Mitrovic (ST)          7.3   | 90+3'[GOAL] Talisca (Counter)      |
+------------------------------------+------------------------------------+
| FOOTER: Screamsheet v2.1 • Produced for Leo                             |
+-------------------------------------------------------------------------+
```

---

## 5. Edge-Case Print Formatting Rules

1. **Extra Time (AET) & Penalty Shootouts (PEN)**:
   * Score header renders as: `Real Madrid 2 - 2 Man City (AET, 4-3 PK)`.
   * Timeline displays extra-time minutes with `ET` prefix (e.g., `104' ET`).
   * Penalty shootout shootout list renders in condensed notation: `PK: Real [O O O X O] - City [O X O O X]`.
2. **Red Cards**:
   * Highlighted with high-contrast badge: `[RED 74']` and bold player name to catch the young reader's eye.
3. **VAR Disallowed Goals**:
   * Rendered with strike-through or prefix: `<s>45' Goal - Mbappe</s> (VAR: Offside)`.
4. **Missing Expected Goals (xG)**:
   * In non-Tier-1 leagues where Opta/xG data is not provided by the API, omit the row or render a clean dash (`—`) rather than `None` or `0.0`.
5. **Two-Legged Ties (Aggregate Scores)**:
   * When `aggregate` is present (e.g. Champions League knockouts), append `(Agg: 4-3)`.

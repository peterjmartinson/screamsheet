# Custom Screamsheet Instruction Manual

This guide explains how to compose custom, multi-page screamsheets in your subscriber YAML files (`screamsheet-subscribers/subscribers/<name>.yaml`) or programmatically via `ScreamsheetOrder`.

---

## 1. Quick Start

Any entry under `sheets:` in a subscriber YAML file that includes a `components:` list is automatically recognized as a **Custom Screamsheet**.

- **Custom Sheet Key**: You can name the key under `sheets:` anything you want (e.g., `daily_standings`, `philly_mashup`, `hot_stove_digest`). The generated PDF is named `<sheet_key>_<YYYYMMDD>.pdf`.
- **Mix and Match**: You can freely combine pre-established template sheets (`presidential: true`, `mlb: ...`) and custom `components:` sheets in the same subscriber YAML file.
- **Shorthand vs. Configured Components**: Each item in `components:` can be either a dictionary (`- type: mlb_standings`) with options or a plain string shorthand (`- mlb_standings`) when using default options.

```yaml
name: Peter Martinson
email: peter.j.martinson@gmail.com
destination: print

location:
  name: "Bryn Mawr, PA"
  lat: 40.02
  lon: -75.34

sheets:
  # Standard pre-built template sheet:
  presidential: true

  # Custom component-based screamsheet:
  philly_fall_mashup:
    screamsheet_title: "The Broad Street Mashup"
    subtitle: "Weather, Birds, Puck & Hot Stove"
    components:
      - type: weather
      - type: nfl_tv_schedule
        teams: ["Philadelphia Eagles", "Green Bay Packers"]
      - type: nhl_standings
      - type: nba_standings
      - type: nfl_standings
      - type: mlb_trade_rumors_news
        teams: ["Philadelphia Phillies", "Milwaukee Brewers", "San Diego Padres"]
        max_articles: 4
```

---

## 2. Sheet-Level Options

When defining a custom sheet block under `sheets:`, the following top-level keys are supported:

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `components` | `list` | *(Required)* | Ordered list of components to render on the screamsheet. |
| `screamsheet_title` | `str` | `"Screamsheet"` | Main masthead title printed at the top of Page 1. |
| `subtitle` | `str` | `None` | Optional italicized subtitle line displayed directly below `screamsheet_title` (above the date). |
| `enabled` | `bool` | `true` | Set `enabled: false` to temporarily skip generating this custom sheet without deleting its YAML configuration. |
| `location` / `weather` | `dict` | Subscriber's `location:` | Optional `{ name, lat, lon }` block overriding the subscriber's default location for all weather/sky components on this sheet. |

---

## 3. Page Layout & Automatic Overflow Rules

`CustomScreamsheet` packs components onto pages in the **exact order** you list them under `components:`, applying the following layout rules automatically:

1. **Front Page vs. Back/Subsequent Pages**:
   - **Page 1 (Front Page)** reserves space at the top for the masthead (`screamsheet_title`, optional `subtitle`, and date).
   - **Standings Limit**: Page 1 allows **at most 1** standings table (`max_on_front_page = 1`). Compact components (`weather`, `*_game_scores`, `nfl_tv_schedule`, or the first 2 articles of a news component) can share Page 1 with that single standings table if vertical space permits.
   - **Page 2+ (Back Page and beyond)** can hold **up to 2** standings tables per page (`max_per_page = 2`).
2. **Single-Column ("Next Available Column") Flowing**:
   - Components with `columns: 1`—including `sky_horoscope` (alias: `horoscope`), `sky_highlights` (alias: `sky_summary`), and 1-article news units—occupy a single half-page column (`265pt` wide) and automatically fill the next available column slot (**Left Column** → **Right Column**) on the current page:
     - Ordering two `sky_horoscope` components in a row places Person 1 in the Left Column and Person 2 in the Right Column.
     - Ordering one `sky_horoscope` followed by `sky_highlights` places the horoscope in the Left Column and the Sky Tonight summary in the Right Column.
     - Ordering one `sky_horoscope` followed by a multi-article news component (e.g., `presidential_news` with `max_articles: 3`) automatically places the horoscope in the Left Column, splits **Article 1** into the open Right Column beside it, and flows **Articles 2 & 3** onto the next page's Left & Right columns.
     - When `sky_highlights` is unpaired on a row (for example, placed directly beneath `zodiac_wheel`), it automatically expands to span the full width of the page.
3. **News Article 2-Column Overflow & Deduplication**:
   - News components default to **`max_articles: 4`** if not specified.
   - When starting on a fresh row, articles flow across 2 columns per page:
     - **Article 1** → Current page, left half
     - **Article 2** → Current page, right half
     - **Article 3** → Next page, left half
     - **Article 4** → Next page, right half (and so on for larger `max_articles`).
   - **Story Deduplication**: Every custom screamsheet tracks all stories across the entire sheet (`seen_story_keys` by URL/ID and normalized headline). If you place `mlb_trade_rumors_news` followed by `mlb_news`, no story will ever be duplicated across components or pages.
4. **Full-Page Components**:
   - Box scores (`*_box_score`), `briefing_back`, and `home_run_derby` require an entire page to themselves (`full_page_only = true`). They automatically start on a new page if the current page is non-empty, and any component after them starts on the following page.
5. **Empty Component Suppression**:
   - If a component has no data for the day (for example, `mlb_game_scores` on an off-day or `nhl_box_score` when none of the specified `teams` played yesterday), it is cleanly omitted without leaving blank pages.

---

## 4. Common Component Options

Every item in `components:` accepts:

```yaml
- type: <component_type>      # Required: registered component key (see Section 5)
  title: "Custom Heading"     # Optional: overrides the component's default section header
  columns: 1                  # Optional: 1 (single-column half-page slot) or 2 (full-width)
  teams: [...]                # Optional: list of team names, nicknames, abbreviations, or {id, name} dicts
  max_articles: 4             # Optional (News components): number of articles to include (default: 4)
  mad_fan: false              # Optional (Box Score components): enraged hometown-fan recap on a loss
  location:                   # Optional (Weather / Sky components): per-component location override
    name: "Wildwood, NJ"
    lat: 38.99
    lon: -74.82
```

> **Note on `teams:`**: You can specify teams using full names (`"Philadelphia Phillies"`), nicknames (`"Phillies"`, `"Flyers"`, `"76ers"`, `"Eagles"`), or abbreviations (`"PHI"`, `"GB"`). Team aliases are resolved automatically via the `screamsheet` team database.

---

## 5. Complete Component Reference (`type:`)

### A. League Standings Components
Renders full division/conference standings tables.
- **Layout Rule**: Max **1** standings table on Page 1; up to **2** standings tables per page on Page 2+.

| `type` | Default `title` | Extra Options | Description |
| :--- | :--- | :--- | :--- |
| `mlb_standings` | `"MLB Standings"` | `title` | AL & NL East/Central/West standings tables. |
| `nhl_standings` | `"NHL Standings"` | `title` | Eastern & Western Conference division standings. |
| `nba_standings` | `"NBA Standings"` | `title` | Eastern & Western Conference standings. |
| `nfl_standings` | `"NFL Standings"` | `title` | AFC & NFC Conference standings. |
| `worldcup_standings` | `"Group Standings"` | `title` | FIFA World Cup 4-column group stage tables. |

---

### B. Game Scores Components
Renders yesterday's final scores (and/or upcoming matchups) in a compact multi-column grid, highlighting your `teams:` first.

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `mlb_game_scores` | `"Game Scores"` | `teams`, `title`, `upcoming_games: false` | MLB final scores (or today's matchups if `upcoming_games: true`). |
| `nhl_game_scores` | `"Game Scores"` | `teams`, `title`, `upcoming_games: false` | NHL final scores. |
| `nba_game_scores` | `"Game Scores"` | `teams`, `title`, `upcoming_games: false` | NBA final scores. |
| `nfl_game_scores` | `"Game Scores"` | `teams`, `title`, `upcoming_games: false` | NFL final scores. |
| `worldcup_game_scores` | `"Match Results"` | `teams`, `title` | FIFA World Cup match scores. |
| `mlb_all_star_game_scores` | `"MLB All-Star Game Score"` | `title` | MLB All-Star Game linescore banner. |

---

### C. Box Score & Game Summary Components
Renders a two-column full-page recap: LLM-generated **Game Summary** on the left half and the full **Box Score** tables on the right half for the highest-priority team in `teams:` that played yesterday.
- **Layout Rule**: `full_page_only = true` (occupies an entire page). If none of the teams in `teams:` played yesterday, the component is skipped automatically.

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `mlb_box_score` | `"Game Summary"` | `teams` *(required)*, `mad_fan`, `title` | MLB batting/pitching box score + LLM game recap. |
| `nhl_box_score` | `"Game Summary"` | `teams` *(required)*, `mad_fan`, `title` | NHL skaters/goalies box score + LLM game recap. |
| `nba_box_score` | `"Game Summary"` | `teams` *(required)*, `mad_fan`, `title` | NBA player stats box score + LLM game recap. |
| `nfl_box_score` | `"Game Summary"` | `teams` *(required)*, `mad_fan`, `title` | NFL team/player stats box score + LLM game recap. |
| `worldcup_box_score` | `"Match Summary"` | `teams`, `fixture_id`, `title` | FIFA World Cup match summary + box score. |
| `mlb_all_star_box_score` | `"Box Score"` | `title` | MLB All-Star Game full box score. |
| `mlb_all_star_game_summary` | `"Game Story"` | `title` | Standalone MLB All-Star Game summary. |

---

### D. TV Schedule & Other Sports Components

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `nfl_tv_schedule` | `"Upcoming NFL Broadcasts"` | `teams`, `title` | Compact 2-column table of upcoming NFL TV broadcast times & networks (prioritizing `teams`). |
| `nfl_injuries` | `"Key Injuries"` | `teams`, `title` | Injury report table for the specified NFL `teams`. |
| `home_run_derby` | `"Home Run Derby"` | `game_pk`, `title`, `page_slot: "front"` | MLB Home Run Derby round-by-round bracket (`"front"` or `"back"`). |

---

### E. News & Language Components
Fetches, scores, deduplicates, and summarizes news articles via LLM.
- **Layout Rule**: Flows 2 articles per page (left column → right column → next page left column → next page right column). Defaults to `max_articles: 4`.

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `presidential_news` | `"Top Stories"` | `max_articles` (default `4`), `title` | Top political/White House news across 7 RSS feeds + White House briefings. |
| `mlb_trade_rumors_news` *(alias: `mlb_trade_rumors`)* | `"MLB Trade Rumors"` | `teams`, `max_articles` (default `4`), `title` | MLB Trade Rumors stories prioritizing `teams`. |
| `mlb_news` | `"MLB News"` | `teams`, `max_articles` (default `4`), `title` | Official MLB.com RSS news prioritizing `teams`. |
| `nhl_news` | `"NHL News"` | `teams`, `max_articles` (default `4`), `title` | Official NHL.com RSS news prioritizing `teams`. |
| `nfl_news` | `"NFL News"` | `teams`, `max_articles` (default `4`), `title` | NFL news stories prioritizing `teams`. |
| `french_mlb_articles` | `"Nouvelles du Baseball"` | `teams`, `title` | Two-column French MLB articles rewritten at CEFR A2 (left) and B2/C1 (right). |
| `french_mlb_lexicon` | `"Lexique & Expressions"` | `teams`, `title` | French-English baseball vocabulary & idiomatic phrases table. |

---

### F. Weather & Sky Tonight Components
Uses the subscriber's top-level `location:` automatically unless overridden on the sheet or component.

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `weather` | `"Weather Forecast"` | `location`, `show_description: true`, `title` | 5-day weather forecast table with icons, highs/lows, and conditions (`show_description: false` for compact banner). |
| `zodiac_wheel` | `""` | `location`, `title` | Full-width vector ecliptic zodiac wheel with planet positions and 9-planet symbol glossary. |
| `sky_highlights` *(or `sky_summary`)* | `"Sky Highlights"` | `location`, `title`, `columns` | Independent naked-eye sky observing summary. Pairs into the next available column (`columns: 1`) when placed next to a horoscope or news story, or spans full width beneath `zodiac_wheel`. |
| `sky_horoscope` *(or `horoscope`)* | `"Horoscope"` | `name`, `birth_date`, `birth_time`, `birth_location`, `horoscope_style` (`"kepler"` or `"playbook"`), `extra_instructions`, `people`, `location`, `title` | Independent 1-column natal/transit horoscope reading. Each ordered horoscope fills the next available column (Left → Right), so it can pair with a second `sky_horoscope`, `sky_highlights`, or a news article. |

#### Single-Column Flowing for Sky Tonight, Horoscopes & News
`sky_horoscope`, `sky_highlights`, and news stories automatically flow into the next available half-page column (`Left Column` → `Right Column`):
- **Horoscope + Sky Tonight Summary (2 columns on the same page)**:
```yaml
- type: sky_horoscope
  name: "Peter"
  birth_date: "1978-02-26"
  birth_time: "01:20"
  birth_location: "Wauwatosa, WI"
  horoscope_style: "playbook"
- type: sky_highlights
```
- **Two Separate Horoscopes (fills Left & Right columns)**:
```yaml
- type: sky_horoscope
  name: "Peter"
  birth_date: "1978-02-26"
  birth_time: "01:20"
  birth_location: "Wauwatosa, WI"
  horoscope_style: "playbook"
- type: sky_horoscope
  name: "Anna"
  birth_date: "1985-05-03"
  birth_time: "13:26"
  birth_location: "New York, NY"
  horoscope_style: "playbook"
```
- **Horoscope + News**: If you order one `sky_horoscope` followed by a news component (e.g., `presidential_news` with `max_articles: 3`), your horoscope fills the Left Column, Story 1 fills the Right Column beside it, and Stories 2 & 3 flow onto the next page's Left & Right columns.

---

### G. Morning Briefing & Comic Components

| `type` | Default `title` | Supported Options | Description |
| :--- | :--- | :--- | :--- |
| `xkcd` | `"XKCD"` | `title` | Daily XKCD comic strip with title and alt-text caption. |
| `agenda` | `"Agenda"` | `api_url`, `payload`, `upcoming_days: 1`, `title` | Two-column daily calendar events, commute leave-by times, and tasks. |
| `email_news` | `"Morning News Briefing"` | `gmail_label`, `max_emails: 8`, `lookback_hours: 24`, `latest_per_sender: true`, `title` | LLM summaries of newsletter emails from a Gmail label. |
| `important_emails` | `"Important Notices & Updates"` | `important_senders` *(list of emails/domains)*, `max_emails: 6`, `title` | LLM summaries of recent emails from priority senders/domains. |
| `briefing_back` | `"Morning News & Important Notices"` | `include_email_news: true`, `gmail_label: "Morning Briefing"`, `important_senders: [...]`, `max_left_news: 5`, `title` | Full-page 2-column composite back page combining `email_news` (left column, overflowing to right) and `important_emails` (right column). |

#### How URLs, API Keys & Secrets Work for Morning Briefing Components
1. **Automatic `.env` Variable Expansion in Subscriber YAML**:
   When `screamsheet-subscribers` loads your subscriber YAML (`subscribers/peter.yaml`), it loads `~/.config/screamsheet/.env` and runs `os.path.expandvars()` on the entire YAML file before parsing.
   Any `${VAR_NAME}` placeholder in your YAML (such as `${CALENDAR_URL_PERSONAL}`, `${TRELLO_API_KEY}`, `${GOOGLE_MAPS_API_KEY}`) is automatically replaced with the value from `~/.config/screamsheet/.env`.
2. **Gmail Credentials (`email_news`, `important_emails`, `briefing_back`)**:
   `GmailNewsProvider` automatically reads `GMAIL_USERNAME` and `GMAIL_APP_PASSWORD` from your environment / `~/.config/screamsheet/.env` (or `.env` in the repo root) — you do **not** need to put your Gmail password in the YAML file.
3. **Full Custom Morning Briefing Example**:
```yaml
  custom_morning_briefing:
    screamsheet_title: "Peter's Screamsheet"
    subtitle: "Morning Briefing"
    components:
      - type: weather
        show_description: false
      - type: agenda
        api_url: "https://random-task-rouge.vercel.app/api/agenda"
        upcoming_days: 1
        payload:
          default_start_location: "1041 Reese Ave., Bryn Mawr, PA 19010"
          calendars:
            ical_urls:
              - name: "Personal"
                url: ${CALENDAR_URL_PERSONAL}
              - name: "Family"
                url: ${CALENDAR_URL_FAMILY}
          google_calendar:
            client_id: ${GOOGLE_CALENDAR_CLIENT_ID}
            client_secret: ${GOOGLE_CALENDAR_CLIENT_SECRET}
            refresh_token: ${GOOGLE_CALENDAR_REFRESH_TOKEN}
            calendar_ids:
              - ${GOOGLE_CALENDAR_ID_MLCA}
          trello:
            api_key: ${TRELLO_API_KEY}
            token: ${TRELLO_TOKEN}
            boards:
              - name: "Homework"
                board_id: ${TRELLO_BOARD_ID_HOMEWORK}
                lists:
                  - id: ${TRELLO_LIST_ID_ISAAC}
                    name: "Isaac"
                    assignee: "Isaac"
                    max_tasks: 15
                  - id: ${TRELLO_LIST_ID_ASHER}
                    name: "Asher"
                    assignee: "Asher"
                    max_tasks: 15
            include_past_due: true
          maps:
            enabled: true
            api_key: ${GOOGLE_MAPS_API_KEY}
      - type: xkcd
      - type: briefing_back
        gmail_label: "Morning Briefing"
        important_senders:
          - "annashavin@gmail.com"
          - "mainlineclassical.org"
          - "michelemrice@gmail.com"
          - "vscottzelov@lowermerion.org"
          - "asenn@theredeemer.org"
```

---

## 6. Sample Custom Sheet Recipes

### Recipe 1: Two-Page All-Sports Scoreboard & Standings
Page 1 has MLB scores + MLB standings; Page 2 has NHL standings + NBA standings.
```yaml
  daily_scoreboard:
    screamsheet_title: "Daily Pro Sports Standings"
    components:
      - type: mlb_game_scores
        teams: ["Philadelphia Phillies", "San Diego Padres"]
      - type: mlb_standings
      - type: nhl_standings
      - type: nba_standings
```

### Recipe 2: Multi-Source Baseball Digest (Deduplicated)
Combines `mlb_trade_rumors_news` and `mlb_news` with automatic cross-component story deduplication and a Phillies box score if they played yesterday.
```yaml
  baseball_digest:
    screamsheet_title: "Hot Stove & Diamond Digest"
    components:
      - type: weather
        show_description: false
      - type: mlb_game_scores
        teams: ["Philadelphia Phillies", "Milwaukee Brewers"]
      - type: mlb_trade_rumors_news
        teams: ["Philadelphia Phillies", "Milwaukee Brewers"]
        max_articles: 2
      - type: mlb_news
        teams: ["Philadelphia Phillies", "Milwaukee Brewers"]
        max_articles: 2
      - type: mlb_box_score
        teams: ["Philadelphia Phillies"]
        mad_fan: true
```

### Recipe 3: NFL Sunday / Monday Sheet
```yaml
  nfl_gameday:
    screamsheet_title: "Sunday Gridiron Report"
    components:
      - type: nfl_game_scores
        teams: ["Philadelphia Eagles", "Green Bay Packers"]
      - type: nfl_tv_schedule
        teams: ["Philadelphia Eagles", "Green Bay Packers"]
      - type: nfl_standings
      - type: nfl_injuries
        teams: ["Philadelphia Eagles", "Green Bay Packers"]
      - type: nfl_news
        teams: ["Philadelphia Eagles", "Green Bay Packers"]
        max_articles: 4
```

### Recipe 4: Custom Sky Tonight, Horoscope & News Mashup
Page 1 renders the full-width `zodiac_wheel`; Page 2 pairs your personal `sky_horoscope` in the Left Column with `sky_highlights` (or Article 1 of `presidential_news`) in the Right Column.
```yaml
  sky_and_news:
    screamsheet_title: "Tonight's Sky & Digest"
    components:
      - type: zodiac_wheel
      - type: sky_horoscope
        name: "Peter"
        birth_date: "1978-02-26"
        birth_time: "01:20"
        birth_location: "Wauwatosa, WI"
        horoscope_style: "playbook"
      - type: sky_highlights
      - type: presidential_news
        max_articles: 2
```

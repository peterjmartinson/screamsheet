# Screamsheet

> *One page of news, printed fresh every morning.*

---

## Why

My son became obsessed with baseball scores — but every way to check them involved a screen. Once he was on a screen, getting him off was a battle. My wife and I call it "screen withdrawal," and it's real.

I wanted him to follow the Phillies without hunting for the remote. Then I remembered something from the cyberpunk role-playing games of my youth: the **Screamsheet** — a futuristic fax machine that prints the day's headlines for a buck, you read it, and toss it away.

So I built one.

Every morning at 6 AM, a cron job runs on our basement Linux box, pulls the latest scores and news from the internet, formats it into a tidy one-page PDF, and sends it to the printer. My son comes downstairs, picks it up, and reads it over breakfast — no screen required.

> *"Dad, the Brewers are last in their division."*
> 
> He was poking at my Wisconsin heritage. The Brewers may be losing, but Team Parents had won.

Since then it's grown to cover NHL and NFL scores, MLB trade rumors, political news, and even a nightly star chart with horoscopes. The goal in every case is the same: **use AI and automation to make technology invisible** — replace the infinite scroll with a single printed page.

I wrote about the whole story [on my blog](https://peterjmartinson.com) if you want the full origin.

---

## What

Screamsheet is a Python system that generates **print-ready one-page PDFs** — called *screamsheets* — and sends them to a printer automatically every morning via cron.

Each screamsheet is a self-contained PDF covering one topic: sports scores, sports news, political headlines, or whatever you wire up. The current set includes:

| Sheet | Output file | What's on it |
|---|---|---|
| MLB game scores | `Files/MLB_gamescores_YYYYMMDD.pdf` | Scores, standings, favourite team box score + AI narrative |
| MLB Trade Rumors | `Files/MLB_trade_rumors_YYYYMMDD.pdf` | Top 4 articles from MLB Trade Rumors, prioritised by favourite teams |
| MLB News | `Files/MLB_NEWS_YYYYMMDD.pdf` | Top 4 articles from MLB.com RSS feeds, prioritised by favourite teams |
| NHL game scores | `Files/NHL_gamescores_YYYYMMDD.pdf` | Scores, standings, favourite team box score |
| NBA game scores | `Files/NBA_gamescores_YYYYMMDD.pdf` | Scores, standings, favourite team box score |
| NFL game scores | `Files/NFL_gamescores_YYYYMMDD.pdf` | Scores, standings |
| Presidential | `Files/presidential_screamsheet_YYYYMMDD.pdf` | Top 4 political stories from 7 RSS feeds + WhiteHouse.gov |
| Sky Tonight | `Files/SKY_YYYYMMDD.pdf` | Tonight's sky highlights + horoscopes |

### Favourite teams & fallback

Each sports scores sheet features a box score and narrative for one team. Configure your preferred teams in priority order in `config.yaml`:

```yaml
mlb:
  favorite_teams:
    - id: 143
      name: "Philadelphia Phillies"
    - id: 147
      name: "New York Yankees"
```

The sheet checks teams in order. If none of your favourites played on a given day, it automatically selects a random completed game instead — so the featured section is never blank.

MLB news sheets (`MLB_trade_rumors`, `MLB_NEWS`) use short team names to prioritise articles. Configure them under `mlb.news_names`:

```yaml
mlb:
  news_names:
    - "Phillies"
    - "Yankees"
```

If no matching articles are found for any listed team, remaining slots are filled from the general MLB feed. If `news_names` is empty or omitted, all slots come from the general feed.

Run them all at once:

```bash
uv run screamsheet
```

---

## How It Works

The system is built around four concepts:

```
DataProvider  →  fetches raw data (API, RSS, scrape, package)
Section       →  one content block on the page (scores table, standings, article list…)
Screamsheet   →  orchestrates sections → renders → outputs a PDF
Factory       →  the single public entry point for creating any screamsheet
```

```
src/screamsheet/
├── base/           # Abstract base classes: BaseScreamsheet, DataProvider, Section
├── sports/         # MLBScreamsheet, NHLScreamsheet, NFLScreamsheet, NBAScreamsheet
├── news/           # NewsScreamsheet base + concrete news sheets
├── providers/      # One provider per data source (MLB Stats API, NHL API, RSS feeds…)
├── renderers/      # ReportLab helpers: game_scores, standings, box_score, news_articles…
├── db/             # SQLite cache for reference data (NHL teams, players)
├── factory.py      # ScreamsheetFactory — only public surface for instantiation
└── __main__.py     # Entry point: calls factory for each sheet, sends to printer
```

PDFs land in `Files/` named `{TYPE}_{YYYYMMDD}.pdf`.

---

## How to Make Your Own

The intended workflow for forking this repo is:

1. **Fork & clone** the repo onto your machine.
2. **Point your AI assistant at this README and `src/screamsheet/README.md`** — the architecture docs are written to be readable by an LLM. Ask it to scaffold a new screamsheet for whatever you care about.
3. **Wire it up to cron** to print (or email, or drop to a folder) every morning.

Here's the pattern your AI will follow:

### Step 1 — Create a Data Provider

```python
# src/screamsheet/providers/mls_provider.py
from ..base import DataProvider

class MLSDataProvider(DataProvider):
    def get_game_scores(self, date):
        ...  # call your API / scrape / whatever

    def get_standings(self):
        ...
```

### Step 2 — Create the Screamsheet class

```python
# src/screamsheet/sports/mls.py
from .base_sports import SportsScreamsheet
from ..providers.mls_provider import MLSDataProvider

class MLSScreamsheet(SportsScreamsheet):
    def __init__(self, output_filename, team_id=None, team_name=None, date=None):
        super().__init__("MLS", output_filename, team_id, team_name, date)

    def create_provider(self):
        return MLSDataProvider()
```

### Step 3 — Register it in the Factory

```python
# src/screamsheet/factory.py
@staticmethod
def create_mls_screamsheet(output_filename, team_id=None, team_name=None, date=None):
    return MLSScreamsheet(output_filename=output_filename, team_id=team_id,
                          team_name=team_name, date=date)
```

### Step 4 — Add it to `__main__.py` and run

```bash
uv run screamsheet
```

That's it. Your AI can handle steps 1–3 autonomously once it's read the architecture docs. Your job is to tell it what data source to use and what you want on the page.

---

## Setup

**Requirements**: Python 3.10+, [`uv`](https://docs.astral.sh/uv/), a printer (optional but the whole point).

```bash
git clone https://github.com/peterjmartinson/screamsheet.git
cd screamsheet
uv sync
```

### Cron — generate every morning at 6 AM

```cron
0 6 * * * cd /path/to/screamsheet && uv run screamsheet
```

Add with `crontab -e`.

### Output directory

After generating each PDF, screamsheet copies it to a configurable drop folder. An external tool (e.g. `dispatch`, a print daemon, or a network share watcher) monitors that folder to handle delivery.

Set the folder in `config.yaml`:

```yaml
output:
  directory: /home/peter/PRINT
```

You can also override it for a single run on the command line:

```bash
uv run screamsheet --output-dir /tmp/today
```

The `--output-dir` flag takes precedence over `config.yaml`. If `output.directory` is empty and no `--output-dir` is given, PDFs are generated into `Files/` as usual but not copied anywhere.

#### CI / deploy setup

`config.yaml.example` contains placeholders that the deploy workflow substitutes using **GitHub repository variables** (Settings → Secrets and variables → Actions → **Variables** tab):

| Variable | Description | Example |
|---|---|---|
| `PRINT_DIR` | Output directory on the server for generated PDFs | `/home/peter/Print` |
| `PERSON1_NAME` | Display name for person 1's horoscope column | `Peter` |
| `PERSON1_SUN_SIGN` | Sun sign for person 1 | `Gemini` |
| `PERSON1_MOON_SIGN` | Moon sign for person 1 | `Scorpio` |
| `PERSON1_ASCENDANT` | Ascendant (rising) sign for person 1 | `Sagittarius` |
| `PERSON2_NAME` | Display name for person 2's horoscope column | `Jane` |
| `PERSON2_SUN_SIGN` | Sun sign for person 2 | `Pisces` |
| `PERSON2_MOON_SIGN` | Moon sign for person 2 | `Taurus` |
| `PERSON2_ASCENDANT` | Ascendant (rising) sign for person 2 | `Cancer` |

Valid zodiac sign values are: `Aries`, `Taurus`, `Gemini`, `Cancer`, `Leo`, `Virgo`, `Libra`, `Scorpio`, `Sagittarius`, `Capricorn`, `Aquarius`, `Pisces`.

Use **Variables**, not **Secrets**, for these values. These sign/name values are not sensitive, and Variables are easier to view and manage.

After setting/updating variables, trigger deploy from the Actions tab:

1. Open **Deploy Scream Sheet**
2. Click **Run workflow**

No path is hardcoded in the workflow YAML.

### DB cache — NHL teams & players (refresh weekly)

```bash
uv run db_update
```

Cron entry for weekly sync (Monday 3 AM):

```cron
0 3 * * 1 cd /path/to/screamsheet && uv run db_update
```

---

## Architecture Reference

For a full breakdown of every module, base class, renderer, and extension pattern, see [`src/screamsheet/README.md`](src/screamsheet/README.md).

That document is intentionally written to be consumed by an LLM — if you're using Copilot, Cursor, or another AI assistant to extend the system, point it there first.

---

## Questions & Contributions

Drop a note in [Issues](https://github.com/peterjmartinson/screamsheet/issues) if you have questions about setup or ideas for new sheets. Pull requests welcome!

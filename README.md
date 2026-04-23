# screamsheet
One page news, suitable for printout in the morning!

## Available Screamsheets

| Sheet | Output file | Description |
|---|---|---|
| MLB game scores | `Files/MLB_gamescores_YYYYMMDD.pdf` | Scores, standings, and box score for the Philadelphia Phillies |
| MLB Trade Rumors | `Files/MLB_trade_rumors_YYYYMMDD.pdf` | Top 4 articles from [MLB Trade Rumors](https://www.mlbtraderumors.com/), prioritising Phillies, Padres, Yankees |
| **MLB News** | `Files/MLB_NEWS_YYYYMMDD.pdf` | Top 4 articles from MLB.com team RSS feeds (Phillies → Padres → Yankees priority; configurable) |
| NHL game scores | `Files/NHL_gamescores_YYYYMMDD.pdf` | Scores, standings, and box score for the Philadelphia Flyers |
| Presidential | `Files/presidential_screamsheet_YYYYMMDD.pdf` | Top 4 political news stories from 7 RSS feeds + White House |

### Customising MLB News team priority

Open [src/screamsheet/__main__.py](src/screamsheet/__main__.py) and edit the `favorite_teams` list for the `"MLB News"` entry, or call the factory directly:

```python
ScreamsheetFactory.create_mlb_news_screamsheet(
    output_filename="Files/MLB_NEWS_20260319.pdf",
    favorite_teams=["Dodgers", "Phillies"],   # your preferred order
)
```

Any team listed in `MLBNewsRssProvider.TEAM_FEEDS` is supported.  To add a new team, add its name and MLB.com RSS URL to that dictionary in [src/screamsheet/providers/mlb_news_rss_provider.py](src/screamsheet/providers/mlb_news_rss_provider.py).

## Running the system

```bash
uv run screamsheet        # generate all sheets and send to printer
```

---

## DB Update — NHL Teams & Players Cache

The local SQLite cache (`src/screamsheet/db/nhl.db`) stores NHL team and player
reference data so that live lookups during generation are fast and resilient to
transient API failures.  The cache is populated / refreshed by `update_db.sh`.

### Manual run

```bash
# From any working directory:
bash /home/peter/Code/screamsheet/update_db.sh
```

Or use the `uv` entry point directly (no shell script):

```bash
cd /home/peter/Code/screamsheet
uv run db_update                                    # use default DB path
uv run db_update --db src/screamsheet/db/nhl.db    # explicit path
```

### Cron — weekly sync (every Monday at 3 am)

```cron
0 3 * * 1 /home/peter/Code/screamsheet/update_db.sh
```

Add with `crontab -e`.  Verify with `crontab -l`.

### Log output

Each run appends to a dated file:

```
logfiles/update_db_log_YYYYMMDD.txt
```

Messages are also echoed to stdout so cron mailers and systemd journal capture them.

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Both teams and players synced with non-zero row counts |
| `1`  | A sync raised an exception or returned zero rows (network failure) |

### `pyproject.toml` — entry point (no changes needed)

The `db_update` CLI command is already wired in `[project.scripts]`:

```toml
[project.scripts]
db_update = "screamsheet.db.db_update:main"
```

---

## Sky Tonight — Horoscope Pipeline (Issue #66)

The Sky Tonight screamsheet uses **two separate astronomy libraries** for different purposes:

| Concern | Library | Provider |
|---|---|---|
| Zodiac wheel visual, constellation visibility, sky highlights | Skyfield (DE421) | `SkyDataProvider` |
| Horoscope planet positions, planetary aspects, moon phase | Swiss Ephemeris (Moshier) | `AstroDataProvider` |

### `AstroDataProvider`

Located at `src/screamsheet/providers/astro_provider.py`.  Uses [`pyswisseph`](https://pypi.org/project/pyswisseph/) with the Moshier built-in ephemeris — **no data file downloads required**.

Key methods:

| Method | Returns | Description |
|---|---|---|
| `get_planet_longitudes(date)` | `List[Dict]` | Tropical ecliptic longitude for 9 planets (Sun–Neptune) anchored to the vernal equinox |
| `get_aspects(date)` | `List[Dict]` | All major aspects (conjunction, sextile, square, trine, opposition) with standard orbs |
| `get_moon_phase(date)` | `str` | Phase name derived from Sun–Moon elongation |
| `get_horoscope_data(date)` | `Dict` | Combined dict with `planets`, `aspects`, `moon_phase` |

### Planetary aspects

Five major aspects are computed for all pairs of the 9 modern planets:

| Aspect | Angle | Orb |
|---|---|---|
| Conjunction | 0° | ±8° |
| Sextile | 60° | ±6° |
| Square | 90° | ±8° |
| Trine | 120° | ±8° |
| Opposition | 180° | ±8° |

The aspects list is passed to the horoscope LLM prompt via the `{aspects}` template variable.

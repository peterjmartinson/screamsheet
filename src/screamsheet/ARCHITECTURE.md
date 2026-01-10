# Screamsheet Architecture Summary

## Quick Reference

### Directory Structure
```
src/screamsheet/
├── __init__.py
├── __main__.py              # Main entry point with examples
├── README.md                # Comprehensive documentation
├── factory.py               # ScreamsheetFactory for easy creation
│
├── base/                    # Core abstractions
│   ├── __init__.py
│   ├── screamsheet.py      # BaseScreamsheet
│   ├── section.py          # Section
│   └── data_provider.py    # DataProvider
│
├── sports/                  # Sports implementations
│   ├── __init__.py
│   ├── base_sports.py      # SportsScreamsheet
│   ├── mlb.py              # MLBScreamsheet
│   ├── nhl.py              # NHLScreamsheet
│   ├── nfl.py              # NFLScreamsheet
│   └── nba.py              # NBAScreamsheet
│
├── news/                    # News implementations
│   ├── __init__.py
│   ├── base_news.py        # NewsScreamsheet
│   └── mlb_trade_rumors.py # MLBTradeRumorsScreamsheet
│
├── providers/               # Data fetching
│   ├── __init__.py
│   ├── mlb_provider.py
│   ├── nhl_provider.py
│   ├── nfl_provider.py
│   ├── nba_provider.py
│   └── mlb_trade_rumors_provider.py
│
└── renderers/               # PDF rendering
    ├── __init__.py
    ├── game_scores.py
    ├── standings.py
    ├── box_score.py
    ├── game_summary.py
    ├── weather.py
    └── news_articles.py
```

## Quick Start

```python
from screamsheet import ScreamsheetFactory

# Sports screamsheet
sheet = ScreamsheetFactory.create_mlb_screamsheet(
    output_filename='phillies.pdf',
    team_id=ScreamsheetFactory.MLB_PHILLIES,
    team_name='Philadelphia Phillies'
)
sheet.generate()

# News screamsheet
news = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
    output_filename='news.pdf',
    favorite_teams=['Phillies', 'Padres']
)
news.generate()
```

## Adding New Sport (e.g., MLS)

### Step 1: Create Provider
```python
# providers/mls_provider.py
class MLSDataProvider(DataProvider):
    def get_game_scores(self, date): ...
    def get_standings(self): ...
```

### Step 2: Create Screamsheet
```python
# sports/mls.py
class MLSScreamsheet(SportsScreamsheet):
    def __init__(self, ...):
        super().__init__(sport_name="MLS", ...)
    
    def create_provider(self):
        return MLSDataProvider()
```

### Step 3: Add to Factory (optional)
```python
# factory.py
@staticmethod
def create_mls_screamsheet(...):
    return MLSScreamsheet(...)
```

### Step 4: Use It!
```python
sheet = ScreamsheetFactory.create_mls_screamsheet(
    output_filename='union.pdf',
    team_id=123,
    team_name='Philadelphia Union'
)
sheet.generate()
```

## Key Classes

### BaseScreamsheet
- Abstract base for all screamsheets
- Handles PDF generation
- Orchestrates sections

### SportsScreamsheet
- Base for sports screamsheets
- Standard sections: scores, standings, box score, summary
- Subclass per sport: MLB, NHL, NFL, NBA

### NewsScreamsheet
- Base for news screamsheets
- Standard sections: weather, articles
- Subclass per source: MLBTradeRumors, etc.

### DataProvider
- Interface for data fetching
- Abstracts API/package/scraping details
- One provider per data source

### Section
- Represents a screamsheet section
- Fetches data and renders to PDF
- Modular and reusable

## Current Status

### Fully Implemented (4 sections)
- ✓ MLB: scores, standings, box score, summary
- ✓ NHL: scores, standings, box score, summary

### Partially Implemented (2 sections)
- ⚠ NFL: scores, standings only (organized by week)
- ⚠ NBA: scores, standings only

### News
- ✓ MLB Trade Rumors: weather + articles

## Benefits

1. **Modular**: Each piece is independent
2. **Extensible**: Easy to add sports/news sources
3. **Reusable**: Share code via inheritance
4. **Maintainable**: Clear structure
5. **Testable**: Components can be tested in isolation
6. **Flexible**: Mix and match sections

## Example Use Cases

### Daily Sports Brief
Generate all sports in one script:
```python
for sport in ['mlb', 'nhl', 'nfl', 'nba']:
    factory_method = getattr(ScreamsheetFactory, f'create_{sport}_screamsheet')
    sheet = factory_method(output_filename=f'{sport}_daily.pdf')
    sheet.generate()
```

### Custom Multi-Team Report
```python
teams = [
    (MLB_PHILLIES, 'Philadelphia Phillies'),
    (MLB_YANKEES, 'New York Yankees'),
]

for team_id, team_name in teams:
    sheet = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename=f'mlb_{team_name.lower().replace(" ", "_")}.pdf',
        team_id=team_id,
        team_name=team_name
    )
    sheet.generate()
```

### Historical Analysis
```python
from datetime import datetime, timedelta

for days_ago in range(7):
    date = datetime.now() - timedelta(days=days_ago)
    sheet = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename=f'mlb_{date.strftime("%Y%m%d")}.pdf',
        team_id=MLB_PHILLIES,
        team_name='Philadelphia Phillies',
        date=date
    )
    sheet.generate()
```

## Migration Path

1. **Phase 1**: Test new system alongside old code
2. **Phase 2**: Update scripts to use factory
3. **Phase 3**: Verify outputs match
4. **Phase 4**: Remove old code

Old code location: `src/*.py` (individual screamsheet files)
New code location: `src/screamsheet/` (modular architecture)

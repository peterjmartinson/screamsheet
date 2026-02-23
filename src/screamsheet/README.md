# Screamsheet Modular Architecture

A modular, extensible system for generating sports and news "screamsheets" - single-page PDF reports with scores, standings, and summaries.

## Overview

The screamsheet system is now organized into a clean, modular architecture that makes it easy to:
- Add new sports (like MLS, college sports, etc.)
- Add new news sources (like ESPN, The Athletic, etc.)
- Customize sections and layouts
- Share common functionality across different screamsheet types

## Architecture

### Core Components

```
src/screamsheet/
├── base/                      # Base classes and interfaces
│   ├── screamsheet.py        # BaseScreamsheet class
│   ├── section.py            # Section interface
│   └── data_provider.py      # DataProvider interface
├── sports/                    # Sports screamsheet implementations
│   ├── base_sports.py        # SportsScreamsheet base class
│   ├── mlb.py                # MLB implementation
│   ├── nhl.py                # NHL implementation
│   ├── nfl.py                # NFL implementation
│   └── nba.py                # NBA implementation
├── news/                      # News screamsheet implementations
│   ├── base_news.py          # NewsScreamsheet base class
│   └── mlb_trade_rumors.py   # MLB Trade Rumors implementation
├── providers/                 # Data providers for fetching data
│   ├── mlb_provider.py       # MLB Stats API
│   ├── nhl_provider.py       # NHL API
│   ├── nfl_provider.py       # ESPN API (NFL)
│   ├── nba_provider.py       # nba_api package
│   └── mlb_trade_rumors_provider.py  # RSS feed
├── renderers/                 # Section renderers for PDF generation
│   ├── game_scores.py        # Game scores section
│   ├── standings.py          # Standings section
│   ├── box_score.py          # Box score section
│   ├── game_summary.py       # Game summary section
│   ├── weather.py            # Weather section
│   └── news_articles.py      # News articles section
├── factory.py                 # Factory for creating screamsheets
└── __main__.py               # Main entry point with examples
```

## Key Design Patterns

### 1. Separation of Concerns

Each component has a single responsibility:
- **Data Providers**: Fetch data from external sources (APIs, packages, web scraping)
- **Sections**: Define what data to display and how to render it
- **Screamsheets**: Orchestrate sections and generate PDFs
- **Renderers**: Handle PDF layout and formatting

### 2. Inheritance Hierarchy

```
BaseScreamsheet
├── SportsScreamsheet
│   ├── MLBScreamsheet
│   ├── NHLScreamsheet
│   ├── NFLScreamsheet
│   └── NBAScreamsheet
└── NewsScreamsheet
    └── MLBTradeRumorsScreamsheet
```

### 3. Composition over Configuration

Screamsheets are composed of sections. To create a custom screamsheet, simply compose different sections:

```python
class CustomScreamsheet(SportsScreamsheet):
    def build_sections(self):
        return [
            GameScoresSection(...),
            StandingsSection(...),
            CustomSection(...),
        ]
```

## Usage Examples

### Basic Usage with Factory

```python
from screamsheet import ScreamsheetFactory

# Generate MLB screamsheet
sheet = ScreamsheetFactory.create_mlb_screamsheet(
    output_filename='phillies.pdf',
    team_id=ScreamsheetFactory.MLB_PHILLIES,
    team_name='Philadelphia Phillies'
)
sheet.generate()

# Generate NHL screamsheet
sheet = ScreamsheetFactory.create_nhl_screamsheet(
    output_filename='flyers.pdf',
    team_id=ScreamsheetFactory.NHL_FLYERS,
    team_name='Philadelphia Flyers'
)
sheet.generate()

# Generate news screamsheet
sheet = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
    output_filename='news.pdf',
    favorite_teams=['Phillies', 'Padres']
)
sheet.generate()
```

### Direct Instantiation

```python
from screamsheet.sports import MLBScreamsheet
from datetime import datetime

sheet = MLBScreamsheet(
    output_filename='custom_mlb.pdf',
    team_id=143,
    team_name='Philadelphia Phillies',
    date=datetime(2026, 1, 8)
)
sheet.generate()
```

## Adding New Sports

To add a new sport (e.g., MLS), follow these steps:

### 1. Create a Data Provider

```python
# src/screamsheet/providers/mls_provider.py
from ..base import DataProvider

class MLSDataProvider(DataProvider):
    def get_game_scores(self, date):
        # Fetch MLS game scores from API
        pass
    
    def get_standings(self):
        # Fetch MLS standings
        pass
```

### 2. Create the Screamsheet Class

```python
# src/screamsheet/sports/mls.py
from .base_sports import SportsScreamsheet
from ..providers.mls_provider import MLSDataProvider

class MLSScreamsheet(SportsScreamsheet):
    def __init__(self, output_filename, team_id=None, team_name=None, date=None):
        super().__init__(
            sport_name="MLS",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    def create_provider(self):
        return MLSDataProvider()
```

### 3. Add to Factory (Optional)

```python
# src/screamsheet/factory.py
@staticmethod
def create_mls_screamsheet(output_filename, team_id=None, team_name=None, date=None):
    return MLSScreamsheet(
        output_filename=output_filename,
        team_id=team_id,
        team_name=team_name,
        date=date
    )
```

### 4. Use It

```python
from screamsheet import ScreamsheetFactory

sheet = ScreamsheetFactory.create_mls_screamsheet(
    output_filename='union.pdf',
    team_id=123,
    team_name='Philadelphia Union'
)
sheet.generate()
```

## Adding New News Sources

To add a new news source (e.g., ESPN), follow similar steps:

### 1. Create a Data Provider

```python
# src/screamsheet/providers/espn_provider.py
class ESPNProvider:
    def get_articles(self):
        # Fetch and filter ESPN articles
        pass
```

### 2. Create the Screamsheet Class

```python
# src/screamsheet/news/espn.py
from .base_news import NewsScreamsheet
from ..renderers import WeatherSection, NewsArticlesSection

class ESPNScreamsheet(NewsScreamsheet):
    def __init__(self, output_filename, **kwargs):
        super().__init__(
            news_source="ESPN",
            output_filename=output_filename,
            **kwargs
        )
        self.provider = ESPNProvider()
    
    def build_sections(self):
        return [
            WeatherSection(...),
            NewsArticlesSection(...),
        ]
```

## Custom Sections

You can create custom sections for specific needs:

```python
from screamsheet.base import Section
from reportlab.platypus import Paragraph

class CustomSection(Section):
    def fetch_data(self):
        # Fetch your custom data
        self.data = get_my_custom_data()
    
    def render(self):
        # Render using ReportLab flowables
        return [
            Paragraph(self.title, self.styles['h3']),
            # ... more rendering logic
        ]
```

## Sports Section Structure

All sports screamsheets follow this common structure:

1. **Game Scores**: Yesterday's game results
2. **League Standings**: Current standings
3. **Box Score**: Detailed stats for a specific team (if configured)
4. **Game Summary**: LLM-generated narrative summary (if configured)

Currently, full implementation (all 4 sections) exists for:
- MLB ✓
- NHL ✓

Partial implementation (scores + standings only) exists for:
- NFL (organized by week, not date)
- NBA

## News Section Structure

News screamsheets typically have:

1. **Weather Report** (optional)
2. **News Articles** (number varies)

## Data Sources

The system supports multiple data source types:
- **REST APIs**: MLB Stats API, NHL API, ESPN API
- **Python Packages**: nba_api
- **RSS Feeds**: MLB Trade Rumors
- **Web Scraping**: (Can be added as needed)

## Future Enhancements

Potential additions:
- MLS screamsheet
- College sports (football, basketball)
- More news sources (ESPN, The Athletic, etc.)
- Customizable layouts
- Email delivery
- Automated scheduling
- Web interface

## Benefits of This Architecture

1. **Modularity**: Each component is independent and testable
2. **Extensibility**: Easy to add new sports or news sources
3. **Reusability**: Common functionality is shared via base classes
4. **Maintainability**: Clear structure makes code easy to understand and modify
5. **Flexibility**: Mix and match sections to create custom screamsheets
6. **Separation of Concerns**: Data fetching, rendering, and orchestration are separate

## Migration from Old Code

The old code still exists in `src/` with files like:
- `mlb_screamsheet.py`
- `nhl_screamsheet.py`
- `nfl_screamsheet.py`
- `nba_screamsheet.py`
- `get_mlb_news.py`

The new modular code is in `src/screamsheet/` and provides the same functionality with better organization.

To migrate:
1. Update your scripts to use `ScreamsheetFactory`
2. Replace direct imports with factory methods
3. Test thoroughly
4. Remove old code once confident

## Contributing

When adding new features:
1. Follow the existing patterns
2. Create data providers for new data sources
3. Implement sections for new content types
4. Add factory methods for convenience
5. Document your additions

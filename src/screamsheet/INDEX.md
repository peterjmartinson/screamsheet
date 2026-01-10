# Screamsheet System - Documentation Index

Welcome to the refactored screamsheet system! This directory contains a modular, extensible architecture for generating sports and news screamsheets.

## 📚 Documentation Files

### Getting Started
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Start here! Overview of what was done and why
- **[README.md](README.md)** - Comprehensive guide with examples and tutorials
- **[example_usage.py](../example_usage.py)** - Interactive examples you can run

### Architecture & Design
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Quick reference for architecture patterns
- **[ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt)** - Visual diagrams of system structure

### Code Organization
```
screamsheet/
├── base/           # Core abstractions (BaseScreamsheet, Section, DataProvider)
├── sports/         # Sports implementations (MLB, NHL, NFL, NBA)
├── news/           # News implementations (MLBTradeRumors)
├── providers/      # Data fetching from APIs/packages/feeds
├── renderers/      # PDF rendering for different section types
├── factory.py      # ScreamsheetFactory for easy creation
└── __main__.py     # Main entry point with examples
```

## 🚀 Quick Start

### 1. Import the factory
```python
from screamsheet import ScreamsheetFactory
```

### 2. Create a screamsheet
```python
# Sports screamsheet
sheet = ScreamsheetFactory.create_mlb_screamsheet(
    output_filename='phillies.pdf',
    team_id=ScreamsheetFactory.MLB_PHILLIES,
    team_name='Philadelphia Phillies'
)

# News screamsheet
news = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
    output_filename='news.pdf',
    favorite_teams=['Phillies', 'Padres']
)
```

### 3. Generate PDF
```python
sheet.generate()
news.generate()
```

## 📖 Documentation Guide

### For First-Time Users
1. Read [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) - understand what changed
2. Read [README.md](README.md) - learn how to use the system
3. Run [example_usage.py](../example_usage.py) - see it in action

### For Developers Adding Features
1. Review [ARCHITECTURE.md](ARCHITECTURE.md) - understand design patterns
2. Review [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) - visualize structure
3. Follow examples in [README.md](README.md) - see how to extend

### For Maintainers
1. Check [ARCHITECTURE.md](ARCHITECTURE.md) - understand design decisions
2. Review code in `base/` - understand core abstractions
3. Review implementations in `sports/` and `news/` - see patterns

## 🎯 Common Tasks

### Generate a screamsheet
```bash
cd src
python -c "from screamsheet import ScreamsheetFactory; \
    sheet = ScreamsheetFactory.create_mlb_screamsheet('output.pdf'); \
    sheet.generate()"
```

### Run interactive example
```bash
cd src
python example_usage.py
```

### Add a new sport (e.g., MLS)
See **"Adding New Sports"** section in [README.md](README.md)

### Add a new news source (e.g., ESPN)
See **"Adding New News Sources"** section in [README.md](README.md)

## 🏗️ System Components

### Base Classes (in `base/`)
- `BaseScreamsheet` - Abstract base for all screamsheets
- `Section` - Interface for screamsheet sections
- `DataProvider` - Interface for data fetching

### Sports Screamsheets (in `sports/`)
- `SportsScreamsheet` - Base for all sports
- `MLBScreamsheet` - Major League Baseball
- `NHLScreamsheet` - National Hockey League
- `NFLScreamsheet` - National Football League
- `NBAScreamsheet` - National Basketball Association

### News Screamsheets (in `news/`)
- `NewsScreamsheet` - Base for all news
- `MLBTradeRumorsScreamsheet` - MLB Trade Rumors RSS feed

### Data Providers (in `providers/`)
- `MLBDataProvider` - MLB Stats API
- `NHLDataProvider` - NHL API
- `NFLDataProvider` - ESPN API
- `NBADataProvider` - nba_api package
- `MLBTradeRumorsProvider` - RSS feed parser

### Renderers (in `renderers/`)
- `GameScoresSection` - Renders game scores
- `StandingsSection` - Renders league standings
- `BoxScoreSection` - Renders detailed box scores
- `GameSummarySection` - Renders game summaries
- `WeatherSection` - Renders weather reports
- `NewsArticlesSection` - Renders news articles

## 📊 Current Status

### Fully Implemented ✅
- **MLB**: All 4 sections (scores, standings, box score, summary)
- **NHL**: All 4 sections (scores, standings, box score, summary)
- **MLB Trade Rumors**: Weather + articles

### Partially Implemented ⚠️
- **NFL**: 2 sections (scores by week, standings)
- **NBA**: 2 sections (scores, standings)

## 🎓 Learning Path

### Beginner
1. Run example_usage.py
2. Create a simple screamsheet using the factory
3. Customize team IDs and output filenames

### Intermediate
1. Understand the class hierarchy
2. Create a custom section
3. Modify section rendering

### Advanced
1. Add a new sport
2. Add a new news source
3. Create custom data providers

## 🔗 Related Files

### Old Implementation (still in src/)
- `mlb_screamsheet.py` - Original MLB implementation
- `nhl_screamsheet.py` - Original NHL implementation
- `nfl_screamsheet.py` - Original NFL implementation
- `nba_screamsheet.py` - Original NBA implementation
- `get_mlb_news.py` - Original news implementation
- `screamsheet.py` - Original wrapper script

### Helper Modules
- `get_box_score.py` - MLB box score fetching
- `get_box_score_nhl.py` - NHL box score fetching
- `get_game_summary.py` - LLM-based game summaries
- `get_llm_summary.py` - LLM-based news summaries
- `print_weather.py` - Weather report generation
- `utilities.py` - Various utility functions

## 💡 Tips

- Use `ScreamsheetFactory` for convenience
- Extend `SportsScreamsheet` for new sports
- Extend `NewsScreamsheet` for new news sources
- Create custom `Section` subclasses for new content types
- Data providers abstract away API/package differences
- Renderers handle PDF generation complexity

## 🐛 Troubleshooting

### Import errors
Make sure you're in the `src/` directory or have it in your PYTHONPATH.

### Missing data
Check that APIs are accessible and your API keys are configured (if needed).

### PDF generation issues
Ensure ReportLab is installed: `pip install reportlab`

## 📝 Contributing

When adding new features:
1. Follow existing patterns (see ARCHITECTURE.md)
2. Create providers for new data sources
3. Implement sections for new content
4. Add factory methods for convenience
5. Update documentation

## 🎉 Summary

The screamsheet system is now:
- **Modular**: Each piece is independent
- **Extensible**: Easy to add sports and news sources
- **Maintainable**: Clear structure and documentation
- **Testable**: Components can be tested in isolation
- **Documented**: Comprehensive docs and examples

Enjoy your new modular screamsheet system! 🏆

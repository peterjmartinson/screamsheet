"""
Main entry point for the screamsheet system.

Usage:
    uv run python -m screamsheet            # run all screamsheets
    uv run python -m screamsheet --single   # pick one interactively and run it
"""
import argparse
from datetime import datetime, timedelta
from .factory import ScreamsheetFactory
from .config import load_config
from .sports import MLBScreamsheet, NHLScreamsheet, NFLScreamsheet, NBAScreamsheet
from .news import MLBTradeRumorsScreamsheet, MLBNewsScreamsheet
from .political import PresidentialScreamsheet
from .sky.sky_tonight import SkyTonightScreamsheet

__all__ = [
    'ScreamsheetFactory',
    'MLBScreamsheet',
    'NHLScreamsheet',
    'NFLScreamsheet',
    'NBAScreamsheet',
    'MLBTradeRumorsScreamsheet',
    'MLBNewsScreamsheet',
    'PresidentialScreamsheet',
    'SkyTonightScreamsheet',
]


def _build_sheets(today_str: str) -> list:
    """Return the ordered list of (label, callable) pairs for every active screamsheet."""
    today = datetime.strptime(today_str, "%Y%m%d")
    game_date = today - timedelta(days=1)

    cfg = load_config()
    mlb_teams = [(t.id, t.name) for t in cfg.mlb.favorite_teams]
    nhl_teams = [(t.id, t.name) for t in cfg.nhl.favorite_teams]
    mlb_news_names = cfg.mlb.news_names

    return [        (
            "MLB  — " + (cfg.mlb.favorite_teams[0].name if cfg.mlb.favorite_teams else ""),
            lambda: ScreamsheetFactory.create_mlb_screamsheet(
                output_filename=f'Files/MLB_gamescores_{today_str}.pdf',
                favorite_teams=mlb_teams,
                date=game_date,
                display_date=today,
            ),
        ),
        (
            "MLB Trade Rumors",
            lambda: ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
                output_filename=f'Files/MLB_trade_rumors_{today_str}.pdf',
                favorite_teams=mlb_news_names,
                max_articles=4,
                include_weather=True,
                weather_lat=cfg.weather.mlb_news.lat,
                weather_lon=cfg.weather.mlb_news.lon,
                weather_location_name=cfg.weather.mlb_news.location_name,
                date=today,
            ),
        ),
        (
            "MLB News",
            lambda: ScreamsheetFactory.create_mlb_news_screamsheet(
                output_filename=f'Files/MLB_NEWS_{today_str}.pdf',
                favorite_teams=mlb_news_names,
                include_weather=True,
                weather_lat=cfg.weather.mlb_news.lat,
                weather_lon=cfg.weather.mlb_news.lon,
                weather_location_name=cfg.weather.mlb_news.location_name,
                date=today,
            ),
        ),
        (
            "NHL  — " + (cfg.nhl.favorite_teams[0].name if cfg.nhl.favorite_teams else ""),
            lambda: ScreamsheetFactory.create_nhl_screamsheet(
                output_filename=f'Files/NHL_gamescores_{today_str}.pdf',
                favorite_teams=nhl_teams,
                date=game_date,
                display_date=today,
            ),
        ),
        (
            "Presidential",
            lambda: ScreamsheetFactory.create_presidential_screamsheet(
                output_filename=f'Files/presidential_screamsheet_{today_str}.pdf',
                max_articles=4,
                weather_lat=cfg.weather.presidential.lat,
                weather_lon=cfg.weather.presidential.lon,
                weather_location_name=cfg.weather.presidential.location_name,
                date=today,
            ),
        ),
        (
            "Sky Tonight — " + cfg.sky.location_name,
            lambda: ScreamsheetFactory.create_sky_tonight_screamsheet(
                output_filename=f'Files/SKY_{today_str}.pdf',
                lat=cfg.sky.lat,
                lon=cfg.sky.lon,
                location_name=cfg.sky.location_name,
                date=today,
            ),
        ),
    ]


def _run_sheet(label: str, factory_fn) -> None:
    sheet = factory_fn()
    sheet.generate()
    print(f"Generated: {label}")


def _pick_and_run(sheets: list) -> None:
    """Present an interactive menu, prompt for a selection, and run that one sheet."""
    print("\nAvailable screamsheets:")
    for i, (label, _) in enumerate(sheets, start=1):
        print(f"  {i}. {label}")
    print()

    while True:
        raw = input(f"Select a screamsheet [1-{len(sheets)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(sheets):
            choice = int(raw) - 1
            break
        print(f"  Please enter a number between 1 and {len(sheets)}.")

    label, factory_fn = sheets[choice]
    print()
    _run_sheet(label, factory_fn)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m screamsheet",
        description="Generate screamsheet PDFs.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Interactively select and run a single screamsheet.",
    )
    args = parser.parse_args()

    today_str = datetime.now().strftime("%Y%m%d")
    sheets = _build_sheets(today_str)

    if args.single:
        _pick_and_run(sheets)
    else:
        for label, factory_fn in sheets:
            _run_sheet(label, factory_fn)


if __name__ == "__main__":
    main()

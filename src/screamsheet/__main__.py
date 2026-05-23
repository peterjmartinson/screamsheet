"""
Main entry point for the screamsheet system.

Usage:
    uv run screamsheet                         # run all (yesterday's games)
    uv run screamsheet --single                # pick one interactively
    uv run screamsheet --date 20260503         # treat May 3 as today (fetches May 2 games)
    uv run screamsheet --single --date 20260503
"""
import argparse
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from .config import load_config
from .factory import ScreamsheetFactory
from .order import (
    MLBNewsOrderOptions,
    MLBOrderOptions,
    MLBTradeRumorsOrderOptions,
    NBAOrderOptions,
    NHLOrderOptions,
    OutputOrderOptions,
    PersonOptions,
    PresidentialOrderOptions,
    ScreamsheetOrder,
    SkyOrderOptions,
    TeamEntry,
    WeatherLocationOptions,
)
from .runner import run_order
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




def _copy_to_output_dir(pdf_path: str, output_dir: str) -> None:
    """Copy a generated PDF into the configured output directory."""
    if not output_dir:
        return

    source = Path(pdf_path)
    if not source.exists():
        logging.getLogger(__name__).warning("Generated PDF not found for copy: %s", pdf_path)
        return

    destination_dir = Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    if source.resolve() == destination.resolve():
        return

    shutil.copy2(source, destination)


def _build_sheets(today_str: str) -> tuple[list, str]:
    """Return the ordered list of (label, callable) pairs for every active screamsheet."""
    today = datetime.strptime(today_str, "%Y%m%d")
    game_date = today - timedelta(days=1)

    cfg = load_config()
    mlb_teams = [(t.id, t.name) for t in cfg.mlb.favorite_teams]
    nhl_teams = [(t.id, t.name) for t in cfg.nhl.favorite_teams]
    nba_teams = [(t.id, t.name) for t in cfg.nba.favorite_teams]
    mlb_news_names = cfg.mlb.news_names

    output_dir = cfg.output.directory

    return [
        (
            "MLB  — " + (cfg.mlb.favorite_teams[0].name if cfg.mlb.favorite_teams else ""),
            lambda: ScreamsheetFactory.create_mlb_screamsheet(
                output_filename=f'Files/MLB_scores_{today_str}.pdf',
                favorite_teams=mlb_teams,
                date=game_date,
                display_date=today,
            ),
        ),
        (
            "MLB Trade Rumors",
            lambda: ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
                output_filename=f'Files/MLB_news_trade_rumors_{today_str}.pdf',
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
                output_filename=f'Files/MLB_news_{today_str}.pdf',
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
                output_filename=f'Files/NHL_scores_{today_str}.pdf',
                favorite_teams=nhl_teams,
                date=game_date,
                display_date=today,
            ),
        ),
        (
            "NBA  — " + (cfg.nba.favorite_teams[0].name if cfg.nba.favorite_teams else ""),
            lambda: ScreamsheetFactory.create_nba_screamsheet(
                output_filename=f'Files/NBA_scores_{today_str}.pdf',
                favorite_teams=nba_teams,
                date=game_date,
                display_date=today,
            ),
        ),
        (
            "Presidential",
            lambda: ScreamsheetFactory.create_presidential_screamsheet(
                output_filename=f'Files/Presidential_news_{today_str}.pdf',
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
                output_filename=f'Files/Sky_tonight_{today_str}.pdf',
                lat=cfg.sky.lat,
                lon=cfg.sky.lon,
                location_name=cfg.sky.location_name,
                date=today,
                people=cfg.sky.people,
            ),
        ),
    ], output_dir


def _run_sheet(label: str, factory_fn, output_dir: str) -> None:
    _log = logging.getLogger(__name__)
    sheet = factory_fn()
    pdf_path = sheet.generate()
    _log.info("Generated: %s", pdf_path)
    if output_dir:
        dest = str(Path(output_dir) / Path(pdf_path).name)
        _copy_to_output_dir(pdf_path, output_dir)
        _log.info("Copied to: %s", dest)


def _build_order_from_config(today: datetime) -> ScreamsheetOrder:
    """Translate the on-disk config.yaml into a ScreamsheetOrder.

    Produces an order that mirrors the full set of sheets currently generated
    by the CLI, preserving existing behaviour exactly.
    """
    cfg = load_config()
    weather_mlb = WeatherLocationOptions(
        lat=cfg.weather.mlb_news.lat,
        lon=cfg.weather.mlb_news.lon,
        location_name=cfg.weather.mlb_news.location_name,
    )
    weather_presidential = WeatherLocationOptions(
        lat=cfg.weather.presidential.lat,
        lon=cfg.weather.presidential.lon,
        location_name=cfg.weather.presidential.location_name,
    )
    return ScreamsheetOrder(
        output=OutputOrderOptions(directory=cfg.output.directory),
        nhl=NHLOrderOptions(
            favorite_teams=[TeamEntry(id=t.id, name=t.name) for t in cfg.nhl.favorite_teams]
        ),
        mlb=MLBOrderOptions(
            favorite_teams=[TeamEntry(id=t.id, name=t.name) for t in cfg.mlb.favorite_teams],
            news_names=cfg.mlb.news_names,
        ),
        nba=NBAOrderOptions(
            favorite_teams=[TeamEntry(id=t.id, name=t.name) for t in cfg.nba.favorite_teams]
        ),
        mlb_news=MLBNewsOrderOptions(
            news_names=cfg.mlb.news_names,
            weather=weather_mlb,
        ),
        mlb_trade_rumors=MLBTradeRumorsOrderOptions(
            news_names=cfg.mlb.news_names,
            weather=weather_mlb,
        ),
        presidential=PresidentialOrderOptions(weather=weather_presidential),
        sky=SkyOrderOptions(
            lat=cfg.sky.lat,
            lon=cfg.sky.lon,
            location_name=cfg.sky.location_name,
            people=[
                PersonOptions(
                    name=p.name,
                    birth_date=p.birth_date,
                    birth_time=p.birth_time,
                    birth_location=p.birth_location,
                    sun_sign=p.sun_sign,
                    moon_sign=p.moon_sign,
                    ascendant=p.ascendant,
                )
                for p in cfg.sky.people
            ],
        ),
    )


def _pick_and_run(sheets: list, output_dir: str) -> None:
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
    _run_sheet(label, factory_fn, output_dir)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-40s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        prog="python -m screamsheet",
        description="Generate screamsheet PDFs.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Interactively select and run a single screamsheet.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help=(
            "Copy generated PDFs to this directory after generation. "
            "Overrides output.directory from config.yaml."
        ),
    )
    parser.add_argument(
        "--date",
        metavar="YYYYMMDD",
        help=(
            "Treat this date as 'today' (game data fetched for the day before). "
            "Example: --date 20260503 fetches games from May 2 and stamps files with 20260503."
        ),
    )
    args = parser.parse_args()

    if args.date:
        try:
            today_str = datetime.strptime(args.date, "%Y%m%d").strftime("%Y%m%d")
        except ValueError:
            parser.error(f"--date must be in YYYYMMDD format, got: {args.date}")
    else:
        today_str = datetime.now().strftime("%Y%m%d")

    today = datetime.strptime(today_str, "%Y%m%d")

    # Apply database path from config before any DB access.
    # os.environ.setdefault leaves an already-exported SCREAMSHEET_DB untouched.
    import os
    try:
        _db_cfg = load_config()
        if _db_cfg.database.path:
            os.environ.setdefault("SCREAMSHEET_DB", _db_cfg.database.path)
    except FileNotFoundError:
        pass  # config.yaml missing — env var / platform default will be used

    if args.single:
        sheets, output_dir = _build_sheets(today_str)
        if args.output_dir:
            output_dir = args.output_dir
        _pick_and_run(sheets, output_dir)
    else:
        order = _build_order_from_config(today)
        if args.output_dir:
            order.output = OutputOrderOptions(directory=args.output_dir)
        run_order(order, today=today)


if __name__ == "__main__":
    main()

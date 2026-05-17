"""run_order() — the single engine entry point for screamsheet generation.

External callers (CLI, orchestration layers) construct a ScreamsheetOrder and
call run_order().  The registry maps each order field name to a handler
function; adding a new sheet type requires only a new field on ScreamsheetOrder
and one new entry in _REGISTRY — this function never needs to change.
"""
from __future__ import annotations

import dataclasses
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .factory import ScreamsheetFactory
from .order import (
    MLBNewsOrderOptions,
    MLBOrderOptions,
    MLBTradeRumorsOrderOptions,
    NBAOrderOptions,
    NFLOrderOptions,
    NHLOrderOptions,
    PresidentialOrderOptions,
    ScreamsheetOrder,
    SkyOrderOptions,
)

logger = logging.getLogger(__name__)

# Fields on ScreamsheetOrder that control execution but are not sheet keys.
_SKIP_FIELDS: frozenset[str] = frozenset({"output"})


def _copy_to_output_dir(src: str, output_dir: str) -> None:
    """Copy a generated PDF to the configured output directory.

    No-ops silently when output_dir is empty.  Logs a warning if src is missing.
    """
    if not output_dir:
        return
    src_path = Path(src)
    if not src_path.exists():
        logger.warning("Output copy skipped — file not found: %s", src)
        return
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest / src_path.name)


# ---------------------------------------------------------------------------
# Per-sheet handlers
# Each handler signature: (options, today, today_str) -> pdf_path
# ---------------------------------------------------------------------------

def _run_nhl(options: NHLOrderOptions, today: datetime, today_str: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nhl_screamsheet(
        output_filename=f"Files/NHL_gamescores_{today_str}.pdf",
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_mlb(options: MLBOrderOptions, today: datetime, today_str: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename=f"Files/MLB_gamescores_{today_str}.pdf",
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_nba(options: NBAOrderOptions, today: datetime, today_str: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nba_screamsheet(
        output_filename=f"Files/NBA_gamescores_{today_str}.pdf",
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_nfl(options: NFLOrderOptions, today: datetime, today_str: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nfl_screamsheet(
        output_filename=f"Files/NFL_gamescores_{today_str}.pdf",
        favorite_teams=teams,
        date=game_date,
    )
    return sheet.generate()


def _run_mlb_news(options: MLBNewsOrderOptions, today: datetime, today_str: str) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": f"Files/MLB_NEWS_{today_str}.pdf",
        "favorite_teams": options.news_names or None,
        "date": today,
    }
    if options.weather:
        kwargs.update(
            include_weather=True,
            weather_lat=options.weather.lat,
            weather_lon=options.weather.lon,
            weather_location_name=options.weather.location_name,
        )
    sheet = ScreamsheetFactory.create_mlb_news_screamsheet(**kwargs)
    return sheet.generate()


def _run_mlb_trade_rumors(
    options: MLBTradeRumorsOrderOptions, today: datetime, today_str: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": f"Files/MLB_trade_rumors_{today_str}.pdf",
        "favorite_teams": options.news_names or None,
        "date": today,
    }
    if options.weather:
        kwargs.update(
            include_weather=True,
            weather_lat=options.weather.lat,
            weather_lon=options.weather.lon,
            weather_location_name=options.weather.location_name,
        )
    sheet = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(**kwargs)
    return sheet.generate()


def _run_presidential(
    options: PresidentialOrderOptions, today: datetime, today_str: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": f"Files/presidential_screamsheet_{today_str}.pdf",
        "date": today,
    }
    if options.weather:
        kwargs.update(
            include_weather=True,
            weather_lat=options.weather.lat,
            weather_lon=options.weather.lon,
            weather_location_name=options.weather.location_name,
        )
    sheet = ScreamsheetFactory.create_presidential_screamsheet(**kwargs)
    return sheet.generate()


def _run_sky(options: SkyOrderOptions, today: datetime, today_str: str) -> str:
    sheet = ScreamsheetFactory.create_sky_tonight_screamsheet(
        output_filename=f"Files/SKY_{today_str}.pdf",
        lat=options.lat,
        lon=options.lon,
        location_name=options.location_name,
        date=today,
        people=options.people,
    )
    return sheet.generate()


# ---------------------------------------------------------------------------
# Registry — maps ScreamsheetOrder field names to their handler functions.
# To add a new sheet: add a field to ScreamsheetOrder, write a handler above,
# and add one entry here.  run_order() never needs to change.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[..., str]] = {
    "nhl":              _run_nhl,
    "mlb":              _run_mlb,
    "nba":              _run_nba,
    "nfl":              _run_nfl,
    "mlb_news":         _run_mlb_news,
    "mlb_trade_rumors": _run_mlb_trade_rumors,
    "presidential":     _run_presidential,
    "sky":              _run_sky,
}


def run_order(order: ScreamsheetOrder, today: datetime | None = None) -> str:
    """Generate all sheets specified in *order*.

    Args:
        order: Describes which sheets to produce and their options.
               Fields set to ``None`` are skipped.
        today: Treat this datetime as "today".  Defaults to ``datetime.now()``.
               Each handler derives the game date as yesterday relative to *today*.

    Returns:
        ``"success"`` when all requested sheets complete without raising.
    """
    if today is None:
        today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    output_dir = order.output.directory if order.output else ""

    for f in dataclasses.fields(order):
        if f.name in _SKIP_FIELDS:
            continue
        options = getattr(order, f.name)
        if options is None:
            continue
        if f.name not in _REGISTRY:
            logger.warning(
                "ScreamsheetOrder field '%s' is set but has no registry entry — sheet skipped",
                f.name,
            )
            continue
        pdf_path = _REGISTRY[f.name](options, today, today_str)
        logger.info("Generated: %s", pdf_path)
        if output_dir:
            dest = str(Path(output_dir) / Path(pdf_path).name)
            _copy_to_output_dir(pdf_path, output_dir)
            logger.info("Copied to: %s", dest)

    return "success"

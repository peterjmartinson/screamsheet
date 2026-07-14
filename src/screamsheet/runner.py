"""run_order() — the single engine entry point for screamsheet generation.

External callers (CLI, orchestration layers) construct a ScreamsheetOrder and
call run_order().  The registry maps each order field name to a handler
function; adding a new sheet type requires only a new field on ScreamsheetOrder
and one new entry in _REGISTRY — this function never needs to change.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .factory import ScreamsheetFactory
from .order import (
    FrenchMLBNewsOrderOptions,
    HomeRunDerbyOrderOptions,
    MLBNewsOrderOptions,
    MLBOrderOptions,
    MLBTradeRumorsOrderOptions,
    NBAOrderOptions,
    NFLOrderOptions,
    NHLOrderOptions,
    NHLNewsOrderOptions,
    PresidentialOrderOptions,
    ScreamsheetOrder,
    ScreamsheetResult,
    SkyOrderOptions,
    WorldCupOrderOptions,
)

logger = logging.getLogger(__name__)

# Fields on ScreamsheetOrder that control execution but are not sheet keys.
_SKIP_FIELDS: frozenset[str] = frozenset({"output"})


def _output_path(output_dir: str, basename: str) -> str:
    """Return the full path for a generated PDF.

    Writes directly into *output_dir* when set; falls back to Files/ for
    backward-compatible standalone use.
    """
    if output_dir:
        return str(Path(output_dir) / basename)
    return f"Files/{basename}"


def _options_summary_entry(field_name: str, options: Any) -> list[str]:
    """Extract a human-readable summary list from a sheet options object."""
    if field_name in ("nhl", "mlb", "nba", "nfl"):
        return [t.name for t in getattr(options, "favorite_teams", [])]
    if field_name in ("nhl_news", "mlb_news", "mlb_trade_rumors", "presidential"):
        weather = getattr(options, "weather", None)
        return [weather.location_name] if weather else []
    return []


# ---------------------------------------------------------------------------
# Per-sheet handlers
# Each handler signature: (options, today, today_str, output_dir) -> pdf_path
# ---------------------------------------------------------------------------

def _run_nhl(options: NHLOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nhl_screamsheet(
        output_filename=_output_path(output_dir, f"NHL_gamescores_{today_str}.pdf"),
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_mlb(options: MLBOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename=_output_path(output_dir, f"MLB_gamescores_{today_str}.pdf"),
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_nba(options: NBAOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nba_screamsheet(
        output_filename=_output_path(output_dir, f"NBA_gamescores_{today_str}.pdf"),
        favorite_teams=teams,
        date=game_date,
        display_date=today,
    )
    return sheet.generate()


def _run_nfl(options: NFLOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nfl_screamsheet(
        output_filename=_output_path(output_dir, f"NFL_gamescores_{today_str}.pdf"),
        favorite_teams=teams,
        date=game_date,
    )
    return sheet.generate()


def _run_mlb_news(
    options: MLBNewsOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"MLB_NEWS_{today_str}.pdf"),
        "favorite_teams": options.news_names,
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


def _run_nhl_news(
    options: NHLNewsOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"NHL_NEWS_{today_str}.pdf"),
        "favorite_teams": options.news_names,
        "date": today,
    }
    if options.weather:
        kwargs.update(
            include_weather=True,
            weather_lat=options.weather.lat,
            weather_lon=options.weather.lon,
            weather_location_name=options.weather.location_name,
        )
    sheet = ScreamsheetFactory.create_nhl_news_screamsheet(**kwargs)
    return sheet.generate()


def _run_mlb_trade_rumors(
    options: MLBTradeRumorsOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"MLB_trade_rumors_{today_str}.pdf"),
        "favorite_teams": options.news_names,
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


def _run_french_mlb_news(
    options: FrenchMLBNewsOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    sheet = ScreamsheetFactory.create_french_mlb_news_screamsheet(
        output_filename=_output_path(output_dir, f"french_mlb_news_{today_str}.pdf"),
        favorite_teams=options.news_names,
        date=today,
    )
    return sheet.generate()


def _run_presidential(
    options: PresidentialOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"presidential_screamsheet_{today_str}.pdf"),
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


def _run_sky(options: SkyOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    sheet = ScreamsheetFactory.create_sky_tonight_screamsheet(
        output_filename=_output_path(output_dir, f"SKY_{today_str}.pdf"),
        lat=options.lat,
        lon=options.lon,
        location_name=options.location_name,
        date=today,
        people=options.people,
    )
    return sheet.generate()


def _run_worldcup(
    options: WorldCupOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    game_date = today - timedelta(days=1)
    sheet = ScreamsheetFactory.create_worldcup_screamsheet(
        output_filename=_output_path(output_dir, f"WORLD_CUP_{today_str}.pdf"),
        date=game_date,
    )
    return sheet.generate()


def _run_home_run_derby(
    options: HomeRunDerbyOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    sheet = ScreamsheetFactory.create_home_run_derby_screamsheet(
        output_filename=_output_path(output_dir, f"Home_Run_Derby_{today_str}.pdf"),
        date=today,
        game_pk=options.game_pk,
    )
    return sheet.generate()


# ---------------------------------------------------------------------------
# Registry — maps ScreamsheetOrder field names to their handler functions.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[..., str]] = {
    "nhl":              _run_nhl,
    "nhl_news":         _run_nhl_news,
    "mlb":              _run_mlb,
    "nba":              _run_nba,
    "nfl":              _run_nfl,
    "mlb_news":         _run_mlb_news,
    "mlb_trade_rumors": _run_mlb_trade_rumors,
    "french_mlb_news":  _run_french_mlb_news,
    "presidential":     _run_presidential,
    "sky":              _run_sky,
    "worldcup":         _run_worldcup,
    "home_run_derby":   _run_home_run_derby,
}


def run_order(
    order: ScreamsheetOrder,
    today: datetime | None = None,
    subscriber_name: str = "",
) -> ScreamsheetResult:
    """Generate all sheets specified in *order*.

    Args:
        order: Describes which sheets to produce and their options.
               Fields set to ``None`` are skipped.
        today: Treat this datetime as "today".  Defaults to ``datetime.now()``.
        subscriber_name: Label embedded in the returned result for reporting.

    Returns:
        A ``ScreamsheetResult`` describing what was generated and any errors.
        Per-sheet exceptions are caught; the sheet is added to errors and the
        loop continues.
    """
    if today is None:
        today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    output_dir = order.output.directory if order.output else ""

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    result = ScreamsheetResult(subscriber_name=subscriber_name)

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
        try:
            pdf_path = _REGISTRY[f.name](options, today, today_str, output_dir)
            logger.info("Generated: %s", pdf_path)
            result.sheets_generated.append(Path(pdf_path).name)
            result.options_summary[f.name] = _options_summary_entry(f.name, options)
        except Exception as exc:
            logger.error("Sheet '%s' failed: %s", f.name, exc)
            result.errors.append(f"{f.name}: {exc}")

    return result


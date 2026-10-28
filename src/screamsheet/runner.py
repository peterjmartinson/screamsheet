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

from .components import ComponentRegistry
from .factory import ScreamsheetFactory
from .order import (
    BriefingOrderOptions,
    ComponentSpec,
    CustomSheetOrderOptions,
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
    TeamEntry,
    WeatherLocationOptions,
    WorldCupOrderOptions,
)

logger = logging.getLogger(__name__)

# Fields on ScreamsheetOrder that control execution or are handled outside _REGISTRY.
_SKIP_FIELDS: frozenset[str] = frozenset({"output", "custom_sheets"})


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
    if field_name in ("nhl_news", "mlb_news", "mlb_trade_rumors", "french_mlb_news", "presidential"):
        weather = getattr(options, "weather", None)
        if weather:
            return [weather.location_name]
        return getattr(options, "news_names", [])
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
        mad_fan=options.mad_fan,
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
        mad_fan=options.mad_fan,
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
        mad_fan=options.mad_fan,
    )
    return sheet.generate()


def _run_nfl(options: NFLOrderOptions, today: datetime, today_str: str, output_dir: str) -> str:
    game_date = today - timedelta(days=1)
    teams = [(t.id, t.name) for t in options.favorite_teams]
    sheet = ScreamsheetFactory.create_nfl_screamsheet(
        output_filename=_output_path(output_dir, f"NFL_gamescores_{today_str}.pdf"),
        favorite_teams=teams,
        date=game_date,
        display_date=today,
        mad_fan=options.mad_fan,
    )
    return sheet.generate()


def _run_mlb_news(
    options: MLBNewsOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"MLB_NEWS_{today_str}.pdf"),
        "favorite_teams": options.news_names,
        "date": today,
        "mode": getattr(options, "mode", "multi"),
        "primary_source": getattr(options, "primary_source", "MLB.com"),
        "primary_source_bonus": getattr(options, "primary_source_bonus", 25),
        "extra_feeds": getattr(options, "extra_feeds", None) or None,
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
        "mode": getattr(options, "mode", "multi"),
        "primary_source": getattr(options, "primary_source", "NHL.com"),
        "primary_source_bonus": getattr(options, "primary_source_bonus", 25),
        "extra_feeds": getattr(options, "extra_feeds", None) or None,
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
        "mode": getattr(options, "mode", "single"),
        "primary_source": getattr(options, "primary_source", "MLB Trade Rumors"),
        "primary_source_bonus": getattr(options, "primary_source_bonus", 0),
        "extra_feeds": getattr(options, "extra_feeds", None) or None,
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
        horoscope_style=options.horoscope_style,
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


def _run_briefing(
    options: BriefingOrderOptions, today: datetime, today_str: str, output_dir: str
) -> str:
    kwargs: dict[str, Any] = {
        "output_filename": _output_path(output_dir, f"BRIEFING_{today_str}.pdf"),
        "subscriber_name": options.subscriber_name,
        "payload": options.payload,
        "upcoming_days": options.upcoming_days,
        "include_xkcd": options.include_xkcd,
        "include_email_news": options.include_email_news,
        "gmail_label": options.gmail_label,
        "important_senders": options.important_senders,
        "latest_email_per_sender": options.latest_email_per_sender,
        "date": today,
    }
    if options.api_url:
        kwargs["api_url"] = options.api_url
    if options.weather:
        kwargs.update(
            include_weather=True,
            weather_lat=options.weather.lat,
            weather_lon=options.weather.lon,
            weather_location_name=options.weather.location_name,
        )
    sheet = ScreamsheetFactory.create_briefing_screamsheet(**kwargs)
    return sheet.generate()


_NEWS_COMPONENT_TYPES: frozenset[str] = frozenset(
    {
        "mlb_news",
        "nhl_news",
        "nfl_news",
        "mlb_trade_rumors",
        "mlb_trade_rumors_news",
        "french_mlb_articles",
        "french_mlb_lexicon",
        "presidential_news",
    }
)


def _resolve_sport_team_tuples(sport: str, raw_teams: list[Any]) -> list[tuple[int, str]]:
    """Resolve a heterogeneous list of team entries/names into (team_id, team_name) tuples."""
    resolved: list[tuple[int, str]] = []
    for idx, item in enumerate(raw_teams, start=1):
        if isinstance(item, TeamEntry):
            resolved.append((item.id, item.name))
        elif isinstance(item, tuple) and len(item) == 2:
            resolved.append((int(item[0]), str(item[1])))
        elif isinstance(item, dict) and "id" in item and "name" in item:
            resolved.append((int(item["id"]), str(item["name"])))
        else:
            name_str = item.get("name") if isinstance(item, dict) else str(item)
            if not name_str:
                continue
            match = None
            if sport in ("mlb", "nhl", "nba", "nfl"):
                try:
                    from .db import sport_resolve_team

                    match = sport_resolve_team(sport, name_str)  # type: ignore[arg-type]
                except Exception:
                    match = None
            if match:
                resolved.append((int(match["team_id"]), str(match["full_name"])))
            else:
                resolved.append((idx, str(name_str)))
    return resolved


def _resolve_news_team_names(raw_teams: list[Any]) -> list[str]:
    """Extract team display names for news filtering."""
    names: list[str] = []
    for item in raw_teams:
        if isinstance(item, TeamEntry):
            names.append(item.name)
        elif isinstance(item, tuple) and len(item) == 2:
            names.append(str(item[1]))
        elif isinstance(item, dict) and "name" in item:
            names.append(str(item["name"]))
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _build_component_from_spec(
    spec: ComponentSpec,
    today: datetime,
    sheet_weather: WeatherLocationOptions | None = None,
) -> Any:
    """Instantiate a registered ScreamsheetComponent from a ComponentSpec."""
    comp_type = spec.type.strip().lower()
    kwargs: dict[str, Any] = dict(spec.options or {})

    if spec.title is not None:
        kwargs["title"] = spec.title

    sport = ""
    for prefix in ("mlb", "nhl", "nba", "nfl", "worldcup"):
        if comp_type.startswith(f"{prefix}_"):
            sport = prefix
            break

    if comp_type in _NEWS_COMPONENT_TYPES:
        kwargs.setdefault("date", today)
        if comp_type != "french_mlb_lexicon":
            kwargs.setdefault("max_articles", spec.max_articles)
        team_names = _resolve_news_team_names(spec.teams)
        if team_names:
            kwargs.setdefault("favorite_teams", team_names)
    elif comp_type == "weather" or comp_type in (
        "zodiac_wheel",
        "sky_highlights",
        "sky_summary",
        "sky_tonight_summary",
        "sky_horoscope",
        "horoscope",
    ):
        kwargs.setdefault("date", today)
        w = spec.weather or sheet_weather
        if w is not None:
            kwargs.setdefault("lat", w.lat)
            kwargs.setdefault("lon", w.lon)
            kwargs.setdefault("location_name", w.location_name)
    elif sport:
        if "game_scores" in comp_type or "box_score" in comp_type:
            kwargs.setdefault("date", today - timedelta(days=1))
        else:
            kwargs.setdefault("date", today)
        if "box_score" in comp_type:
            kwargs.setdefault("mad_fan", spec.mad_fan)
        if spec.teams:
            kwargs.setdefault(
                "favorite_teams",
                _resolve_sport_team_tuples(sport, spec.teams),
            )
    else:
        kwargs.setdefault("date", today)
        if comp_type == "briefing_back":
            kwargs.setdefault("include_email_news", True)

    return ComponentRegistry.create(comp_type, **kwargs)


def _run_custom_sheet(
    options: CustomSheetOrderOptions,
    today: datetime,
    today_str: str,
    output_dir: str,
) -> str:
    """Build and generate a CustomScreamsheet from CustomSheetOrderOptions."""
    safe_key = "".join(
        ch if (ch.isalnum() or ch in ("_", "-")) else "_"
        for ch in (options.sheet_key or "custom")
    ).strip("_") or "custom"
    components = [
        _build_component_from_spec(spec, today=today, sheet_weather=options.weather)
        for spec in options.components
    ]
    sheet = ScreamsheetFactory.create_custom_screamsheet(
        output_filename=_output_path(output_dir, f"{safe_key}_{today_str}.pdf"),
        components=components,
        screamsheet_title=options.screamsheet_title,
        subtitle=options.subtitle,
        date=today,
        display_date=today,
    )
    return sheet.generate()


# ---------------------------------------------------------------------------
# Registry — maps ScreamsheetOrder field names to their handler functions.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[..., str]] = {
    "briefing":         _run_briefing,
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

    if subscriber_name:
        logger.info("\nGenerating screamsheets for subscriber %s", subscriber_name)

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

    for custom_opts in order.custom_sheets or []:
        key = custom_opts.sheet_key or "custom"
        try:
            pdf_path = _run_custom_sheet(custom_opts, today, today_str, output_dir)
            logger.info("Generated custom sheet '%s': %s", key, pdf_path)
            result.sheets_generated.append(Path(pdf_path).name)
            result.options_summary[key] = [spec.type for spec in custom_opts.components]
        except Exception as exc:
            logger.error("Custom sheet '%s' failed: %s", key, exc)
            result.errors.append(f"{key}: {exc}")

    return result


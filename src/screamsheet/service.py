"""Subscriber service entry point for screamsheet.

This module is the interface between ``screamsheet-dispatch`` and the
generator.  It accepts a path to a subscriber YAML config file, produces
one PDF per sheet type in the config, and returns a ``list[GenerationResult]``.

Entry point: ``uv run screamsheet-service --config <path> --output-dir <dir>``

The ``generate_for_subscriber`` function is the primary callable.  It is
designed to be called by ``screamsheet-dispatch`` via subprocess — the entry
point ``main()`` serialises the result list to JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import yaml

from .config import MLBConfig, ScreamsheetConfig, SportConfig, TeamEntry, load_config
from .factory import ScreamsheetFactory
from .result import GenerationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_subscriber_config(config_path: str) -> dict:
    """Load and return the raw subscriber YAML as a dict.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file is not valid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Subscriber config not found: {config_path}")
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in subscriber config {config_path}: {exc}") from exc
    return data or {}


def _sheet_types_from_config(raw: dict) -> List[str]:
    """Return the ordered list of sheet type keys present in the config."""
    # Sports sections always present when the key exists with team data
    types: List[str] = []
    for sport in ("nhl", "mlb", "nba", "nfl"):
        section = raw.get(sport, {})
        if section and section.get("favorite_teams"):
            types.append(sport)
    # News section
    news = raw.get("news", {})
    for news_type in news.get("types", []):
        types.append(news_type)
    return types


def _generate_sheet(
    sheet_type: str,
    raw_config: dict,
    output_dir: str,
    today_str: str,
) -> GenerationResult:
    """Generate a single sheet and return a ``GenerationResult``.

    This is a thin wrapper around the existing factory so that tests can
    patch it cleanly.

    Raises:
        Any exception raised by the underlying sheet generator.
    """
    output_path = str(Path(output_dir) / f"{sheet_type}_{today_str}.pdf")
    today = datetime.strptime(today_str, "%Y%m%d")
    game_date = today - timedelta(days=1)

    section = raw_config.get(sheet_type, {})
    teams_raw = section.get("favorite_teams", [])

    if sheet_type == "nhl":
        # Resolve name → id via DB; fall back to None if DB not populated yet.
        favorite_teams = _resolve_team_ids("nhl", teams_raw)
        sheet = ScreamsheetFactory.create_nhl_screamsheet(
            output_filename=output_path,
            favorite_teams=favorite_teams,
            date=game_date,
            display_date=today,
        )

    elif sheet_type == "mlb":
        favorite_teams = _resolve_team_ids("mlb", teams_raw)
        news_names = section.get("news_names", [])
        sheet = ScreamsheetFactory.create_mlb_screamsheet(
            output_filename=output_path,
            favorite_teams=favorite_teams,
            date=game_date,
            display_date=today,
        )

    elif sheet_type == "nba":
        favorite_teams = _resolve_team_ids("nba", teams_raw)
        sheet = ScreamsheetFactory.create_nba_screamsheet(
            output_filename=output_path,
            favorite_teams=favorite_teams,
            date=game_date,
            display_date=today,
        )

    elif sheet_type == "nfl":
        favorite_teams = _resolve_team_ids("nfl", teams_raw)
        sheet = ScreamsheetFactory.create_nfl_screamsheet(
            output_filename=output_path,
            favorite_teams=favorite_teams,
            date=game_date,
            display_date=today,
        )

    else:
        raise ValueError(f"Unknown sheet type: {sheet_type!r}")

    sheet.generate()
    return GenerationResult(pdf_path=output_path, sheet_type=sheet_type)


def _resolve_team_ids(
    sport: str,
    teams_raw: list,
) -> list:
    """Resolve canonical team names to (id, name) tuples via the local DB.

    If the DB is not populated (e.g. first run before ``db_update``), the
    ``id`` will be ``None`` and the generator will receive ``(None, name)``.
    The individual sport providers are responsible for handling a ``None``
    id gracefully.
    """
    from .db.team_lookup import lookup_team_id_by_name  # local import to keep startup fast
    result = []
    for t in teams_raw:
        name = t.get("name", "")
        team_id = lookup_team_id_by_name(sport, name)
        result.append((team_id, name))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_for_subscriber(
    config_path: str,
    output_dir: str,
    today_str: str | None = None,
) -> List[GenerationResult]:
    """Generate all sheets for a subscriber and return structured results.

    Args:
        config_path: Path to the subscriber YAML config file.
        output_dir:  Directory where PDFs are written.  Created if absent.
        today_str:   Override today's date as ``YYYYMMDD`` (for testing /
                     backfills).  Defaults to the current date.

    Returns:
        One ``GenerationResult`` per sheet type in the config.  A sheet that
        fails to generate is represented as a ``GenerationResult`` with
        ``layout_clean=False``, ``pdf_path=""``, and the error message in
        ``issues``.
    """
    if today_str is None:
        today_str = datetime.now().strftime("%Y%m%d")

    raw = _load_subscriber_config(config_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    sheet_types = _sheet_types_from_config(raw)
    results: List[GenerationResult] = []

    for sheet_type in sheet_types:
        try:
            result = _generate_sheet(sheet_type, raw, output_dir, today_str)
        except Exception as exc:  # noqa: BLE001
            logger.error("Sheet %r failed for config %s: %s", sheet_type, config_path, exc)
            result = GenerationResult(
                pdf_path="",
                sheet_type=sheet_type,
                issues=[f"{type(exc).__name__}: {exc}"],
            )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for ``uv run screamsheet-service``."""
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(
        prog="screamsheet-service",
        description="Generate screamsheet PDFs for a subscriber config.",
    )
    parser.add_argument("--config", required=True, help="Path to subscriber YAML config.")
    parser.add_argument("--output-dir", required=True, help="Directory to write PDFs into.")
    parser.add_argument("--date", metavar="YYYYMMDD", help="Override today's date.")
    args = parser.parse_args()

    results = generate_for_subscriber(
        config_path=args.config,
        output_dir=args.output_dir,
        today_str=args.date,
    )

    # Output JSON only — dispatch parses this.
    print(json.dumps([
        {
            "pdf_path":     r.pdf_path,
            "sheet_type":   r.sheet_type,
            "layout_clean": r.layout_clean,
            "issues":       r.issues,
        }
        for r in results
    ]))

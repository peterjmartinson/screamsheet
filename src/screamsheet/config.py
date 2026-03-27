"""User preference configuration for the screamsheet system.

Reads config.yaml from the project root and exposes typed dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

# Project root is three levels above this file:
#   src/screamsheet/config.py  →  src/screamsheet/  →  src/  →  project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


@dataclass
class TeamEntry:
    """A single team with its provider ID and display name."""
    id: int
    name: str


@dataclass
class SportConfig:
    """Configuration for a single sport."""
    favorite_teams: List[TeamEntry] = field(default_factory=list)


@dataclass
class MLBConfig(SportConfig):
    """MLB-specific configuration, which adds short news-filter names."""
    news_names: List[str] = field(default_factory=list)


@dataclass
class ScreamsheetConfig:
    """Top-level config object, one SportConfig per sport."""
    nhl: SportConfig = field(default_factory=SportConfig)
    mlb: MLBConfig = field(default_factory=MLBConfig)
    nba: SportConfig = field(default_factory=SportConfig)
    nfl: SportConfig = field(default_factory=SportConfig)


def _parse_sport(raw: dict) -> SportConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    return SportConfig(favorite_teams=teams)


def _parse_mlb(raw: dict) -> MLBConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    news_names = raw.get("news_names", [])
    return MLBConfig(favorite_teams=teams, news_names=news_names)


def load_config(path: Path = _CONFIG_PATH) -> ScreamsheetConfig:
    """Load and parse config.yaml.

    Args:
        path: Path to the YAML config file. Defaults to <project_root>/config.yaml.

    Returns:
        Fully populated ScreamsheetConfig.

    Raises:
        FileNotFoundError: If the config file does not exist, with a hint to
            copy config.yaml.example.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.yaml.example to config.yaml and fill in your teams."
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    return ScreamsheetConfig(
        nhl=_parse_sport(raw.get("nhl", {})),
        mlb=_parse_mlb(raw.get("mlb", {})),
        nba=_parse_sport(raw.get("nba", {})),
        nfl=_parse_sport(raw.get("nfl", {})),
    )

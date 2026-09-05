"""User preference configuration for the screamsheet system.

Reads config.yaml from the project root and exposes typed dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

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
    mad_fan: bool = False


@dataclass
class MLBConfig(SportConfig):
    """MLB-specific configuration, which adds short news-filter names."""
    news_names: List[str] = field(default_factory=list)


@dataclass
class NHLConfig(SportConfig):
    """NHL-specific configuration, which adds short news-filter names."""
    news_names: List[str] = field(default_factory=list)


@dataclass
class WorldCupConfig(SportConfig):
    """WorldCup-specific configuration, which adds short news-filter names."""
    news_names: List[str] = field(default_factory=list)


@dataclass
class FrenchMLBConfig:
    """French MLB news-filter names."""
    news_names: List[str] = field(default_factory=list)


@dataclass
class WeatherLocationConfig:
    """Lat/lon and display name for a weather location."""
    lat: float
    lon: float
    location_name: str


@dataclass
class WeatherConfig:
    """Weather location config for each screamsheet type."""
    presidential: WeatherLocationConfig = field(
        default_factory=lambda: WeatherLocationConfig(38.8951, -77.0364, "Washington, DC")
    )
    mlb_news: WeatherLocationConfig = field(
        default_factory=lambda: WeatherLocationConfig(40.02, -75.34, "Bryn Mawr, PA")
    )
    nhl_news: WeatherLocationConfig = field(
        default_factory=lambda: WeatherLocationConfig(40.02, -75.34, "Bryn Mawr, PA")
    )
    briefing: WeatherLocationConfig = field(
        default_factory=lambda: WeatherLocationConfig(40.02, -75.34, "Bryn Mawr, PA")
    )


@dataclass
class BriefingConfig:
    """Configuration for Morning Briefing screamsheet."""
    api_url: str = ""
    subscriber_name: str = ""
    payload: dict = field(default_factory=dict)
    upcoming_days: int = 1
    include_xkcd: bool = True
    weather: WeatherLocationConfig = field(
        default_factory=lambda: WeatherLocationConfig(40.02, -75.34, "Bryn Mawr, PA")
    )


@dataclass
class PersonConfig:
    """Birth details for a horoscope reading."""
    name: str
    birth_date: str = ""          # YYYY-MM-DD
    birth_time: str = ""          # HH:MM (24-hour)
    birth_location: str = ""
    sun_sign: str = ""
    moon_sign: str = ""
    ascendant: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    horoscope_style: Optional[str] = None   # "kepler" | "playbook" | None (defaults to sky.horoscope_style)
    extra_instructions: Optional[Union[str, List[str]]] = None   # Custom prompt instructions for this person


@dataclass
class SkyConfig:
    """Location config for the sky tonight screamsheet."""
    lat: float = 40.0
    lon: float = -75.0
    location_name: str = "My Location"
    people: List[PersonConfig] = field(default_factory=list)
    horoscope_style: str = "kepler"         # Default horoscope style for the sheet: "kepler" | "playbook"


@dataclass
class OutputConfig:
    """Output directory configuration for generated PDF files."""
    directory: str = ""


@dataclass
class DbConfig:
    """Database path configuration.

    Leave ``path`` empty to use the platform default (~/database/screamsheet.db).
    Set it to override, e.g. for a non-standard deployment location.
    The SCREAMSHEET_DB environment variable takes precedence over this setting.
    """
    path: str = ""


@dataclass
class ScreamsheetConfig:
    """Top-level config object, one SportConfig per sport."""
    nhl: NHLConfig = field(default_factory=NHLConfig)
    mlb: MLBConfig = field(default_factory=MLBConfig)
    worldcup: WorldCupConfig = field(default_factory=WorldCupConfig)
    french_mlb: FrenchMLBConfig = field(default_factory=FrenchMLBConfig)
    nba: SportConfig = field(default_factory=SportConfig)
    nfl: SportConfig = field(default_factory=SportConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    sky: SkyConfig = field(default_factory=SkyConfig)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    branding: str = ""
    output: OutputConfig = field(default_factory=OutputConfig)
    database: DbConfig = field(default_factory=DbConfig)


def _parse_output(raw: dict) -> OutputConfig:
    return OutputConfig(
        directory=str(raw.get("directory", "")),
    )


def _parse_db(raw: dict) -> DbConfig:
    return DbConfig(path=str(raw.get("path", "")))


def _parse_sport(raw: dict) -> SportConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    mad_fan = bool(raw.get("mad_fan", False))
    return SportConfig(favorite_teams=teams, mad_fan=mad_fan)


def _parse_mlb(raw: dict) -> MLBConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    news_names = raw.get("news_names", [])
    mad_fan = bool(raw.get("mad_fan", False))
    return MLBConfig(favorite_teams=teams, news_names=news_names, mad_fan=mad_fan)


def _parse_worldcup(raw: dict) -> WorldCupConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    mad_fan = bool(raw.get("mad_fan", False))
    return WorldCupConfig(favorite_teams=teams, mad_fan=mad_fan)


def _parse_nhl(raw: dict) -> NHLConfig:
    teams = [TeamEntry(id=t["id"], name=t["name"]) for t in raw.get("favorite_teams", [])]
    news_names = raw.get("news_names", [])
    mad_fan = bool(raw.get("mad_fan", False))
    return NHLConfig(favorite_teams=teams, news_names=news_names, mad_fan=mad_fan)


def _parse_french_mlb(raw: dict) -> FrenchMLBConfig:
    news_names = raw.get("news_names", [])
    return FrenchMLBConfig(news_names=news_names)


def _parse_weather_location(
    raw: dict,
    default_lat: float,
    default_lon: float,
    default_name: str,
) -> WeatherLocationConfig:
    return WeatherLocationConfig(
        lat=float(raw.get("lat", default_lat)),
        lon=float(raw.get("lon", default_lon)),
        location_name=str(raw.get("location_name", default_name)),
    )


def _parse_weather(raw: dict) -> WeatherConfig:
    return WeatherConfig(
        presidential=_parse_weather_location(
            raw.get("presidential", {}), 38.8951, -77.0364, "Washington, DC"
        ),
        mlb_news=_parse_weather_location(
            raw.get("mlb_news", {}), 40.02, -75.34, "Bryn Mawr, PA"
        ),
        nhl_news=_parse_weather_location(
            raw.get("nhl_news", {}), 40.02, -75.34, "Bryn Mawr, PA"
        ),
        briefing=_parse_weather_location(
            raw.get("briefing", {}), 40.02, -75.34, "Bryn Mawr, PA"
        ),
    )


def _parse_person(raw: dict) -> PersonConfig:
    lat_val = raw.get("lat")
    lon_val = raw.get("lon")
    raw_style = raw.get("horoscope_style")
    horoscope_style = str(raw_style) if raw_style is not None else None
    raw_extra = raw.get("extra_instructions")
    extra_instructions: Optional[Union[str, List[str]]] = None
    if isinstance(raw_extra, list):
        extra_instructions = [str(x) for x in raw_extra]
    elif raw_extra is not None:
        extra_instructions = str(raw_extra)
    return PersonConfig(
        name=str(raw.get("name", "Unknown")),
        birth_date=str(raw.get("birth_date", "")),
        birth_time=str(raw.get("birth_time", "")),
        birth_location=str(raw.get("birth_location", "")),
        sun_sign=str(raw.get("sun_sign", "")),
        moon_sign=str(raw.get("moon_sign", "")),
        ascendant=str(raw.get("ascendant", "")),
        lat=float(lat_val) if lat_val is not None else None,
        lon=float(lon_val) if lon_val is not None else None,
        horoscope_style=horoscope_style,
        extra_instructions=extra_instructions,
    )


def _parse_sky(raw: dict) -> SkyConfig:
    sheet_style = str(raw.get("horoscope_style", "kepler"))
    people = [_parse_person(p) for p in raw.get("people", [])]
    return SkyConfig(
        lat=float(raw.get("lat", 40.0)),
        lon=float(raw.get("lon", -75.0)),
        location_name=str(raw.get("location_name", "My Location")),
        people=people,
        horoscope_style=sheet_style,
    )


def _parse_briefing(raw: dict, weather_cfg: WeatherConfig) -> BriefingConfig:
    api_url = str(raw.get("api_url", ""))
    subscriber_name = str(raw.get("subscriber_name", raw.get("name", "")))
    payload = raw.get("payload", {})
    upcoming_days = int(raw.get("upcoming_days", 1))
    include_xkcd = bool(raw.get("include_xkcd", True))
    weather_raw = raw.get("weather", {})
    if weather_raw:
        weather_loc = _parse_weather_location(weather_raw, 40.02, -75.34, "Bryn Mawr, PA")
    else:
        weather_loc = weather_cfg.briefing
    return BriefingConfig(
        api_url=api_url,
        subscriber_name=subscriber_name,
        payload=payload,
        upcoming_days=upcoming_days,
        include_xkcd=include_xkcd,
        weather=weather_loc,
    )


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

    weather = _parse_weather(raw.get("weather", {}))
    return ScreamsheetConfig(
        nhl=_parse_nhl(raw.get("nhl", {})),
        mlb=_parse_mlb(raw.get("mlb", {})),
        french_mlb=_parse_french_mlb(raw.get("french_mlb", {})),
        nba=_parse_sport(raw.get("nba", {})),
        nfl=_parse_sport(raw.get("nfl", {})),
        worldcup=_parse_worldcup(raw.get("worldcup", {})),
        weather=weather,
        sky=_parse_sky(raw.get("sky") or raw.get("sky_tonight") or {}),
        briefing=_parse_briefing(raw.get("briefing") or raw.get("morning_briefing") or {}, weather),
        branding=str(raw.get("branding", "")),
        output=_parse_output(raw.get("output", {})),
        database=_parse_db(raw.get("database", {})),
    )

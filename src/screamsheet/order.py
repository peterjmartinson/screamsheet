"""ScreamsheetOrder contract — the public input model for the screamsheet engine.

Each field on ScreamsheetOrder maps to one sheet type.  A field set to ``None``
means "do not generate that sheet".  The presence of a non-None value is
sufficient to trigger generation.

Callers (including the CLI and external orchestration layers) construct a
ScreamsheetOrder and pass it to ``runner.run_order()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class OrderValidationError(ValueError):
    """Raised when a ScreamsheetOrder or any of its nested options are invalid."""


@dataclass
class TeamEntry:
    """A single team with its provider ID and display name."""

    id: int
    name: str

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise OrderValidationError(
                f"TeamEntry.id must be a positive integer, got {self.id!r}"
            )
        if not self.name:
            raise OrderValidationError("TeamEntry.name must not be empty")


@dataclass
class WeatherLocationOptions:
    """Lat/lon and display name for a weather location."""

    lat: float
    lon: float
    location_name: str


@dataclass
class PersonOptions:
    """Birth details for a horoscope reading (used by the Sky Tonight sheet)."""

    name: str
    birth_date: str = ""       # YYYY-MM-DD
    birth_time: str = ""       # HH:MM (24-hour)
    birth_location: str = ""
    sun_sign: str = ""
    moon_sign: str = ""
    ascendant: str = ""
    lat: float | None = None
    lon: float | None = None
    horoscope_style: str | None = None   # "kepler" | "playbook" | None (defaults to sky.horoscope_style)
    extra_instructions: str | list[str] | None = None


@dataclass
class NHLOrderOptions:
    """Options for the NHL sports / standings sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    mad_fan: bool = False


@dataclass
class MLBOrderOptions:
    """Options for the MLB sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    news_names: list[str] = field(default_factory=list)
    mad_fan: bool = False


@dataclass
class NBAOrderOptions:
    """Options for the NBA sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    mad_fan: bool = False


@dataclass
class NFLOrderOptions:
    """Options for the NFL sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    mad_fan: bool = False


@dataclass
class MLBNewsOrderOptions:
    """Options for the MLB News sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None
    mode: str = "multi"
    primary_source: str = "MLB.com"
    primary_source_bonus: int = 25
    extra_feeds: dict[str, str] | None = None


@dataclass
class NHLNewsOrderOptions:
    """Options for the NHL News sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None
    mode: str = "multi"
    primary_source: str = "NHL.com"
    primary_source_bonus: int = 25
    extra_feeds: dict[str, str] | None = None


@dataclass
class FrenchMLBNewsOrderOptions:
    """Options for the French MLB News sheet."""

    news_names: list[str] = field(default_factory=list)


@dataclass
class MLBTradeRumorsOrderOptions:
    """Options for the MLB Trade Rumors sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None
    mode: str = "single"
    primary_source: str = "MLB Trade Rumors"
    primary_source_bonus: int = 0
    extra_feeds: dict[str, str] | None = None


@dataclass
class PresidentialOrderOptions:
    """Options for the Presidential sheet."""

    weather: WeatherLocationOptions | None = None


@dataclass
class SkyOrderOptions:
    """Options for the Sky Tonight sheet."""

    lat: float = 40.0
    lon: float = -75.0
    location_name: str = "My Location"
    people: list[PersonOptions] = field(default_factory=list)
    horoscope_style: str = "kepler"


@dataclass
class WorldCupOrderOptions:
    """Options for the FIFA World Cup sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    mad_fan: bool = False


@dataclass
class HomeRunDerbyOrderOptions:
    """Options for the MLB Home Run Derby sheet."""

    game_pk: int | None = None


@dataclass
class BriefingOrderOptions:
    """Options for the Morning Briefing sheet."""

    subscriber_name: str = ""
    payload: dict = field(default_factory=dict)
    api_url: str = ""
    weather: WeatherLocationOptions | None = None
    upcoming_days: int = 1
    include_xkcd: bool = True
    include_email_news: bool = True
    gmail_label: str = "Morning Briefing"
    important_senders: list[str] = field(default_factory=list)
    latest_email_per_sender: bool = True


@dataclass
class OutputOrderOptions:
    """Destination directory for generated PDFs."""

    directory: str = ""


@dataclass
class ComponentSpec:
    """Specification for a single component in a custom component-based screamsheet."""

    type: str
    title: str | None = None
    teams: list[Any] = field(default_factory=list)
    max_articles: int = 4
    mad_fan: bool = False
    weather: WeatherLocationOptions | None = None
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.type or not str(self.type).strip():
            raise OrderValidationError("ComponentSpec.type must not be empty")
        if self.max_articles is not None and self.max_articles < 1:
            raise OrderValidationError(
                f"ComponentSpec.max_articles must be >= 1, got {self.max_articles!r}"
            )


@dataclass
class CustomSheetOrderOptions:
    """Options for a custom component-based screamsheet defined in subscriber YAML."""

    sheet_key: str = "custom"
    screamsheet_title: str = "Screamsheet"
    subtitle: str | None = None
    components: list[ComponentSpec] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None

    def __post_init__(self) -> None:
        if not self.sheet_key or not str(self.sheet_key).strip():
            raise OrderValidationError("CustomSheetOrderOptions.sheet_key must not be empty")
        if not self.screamsheet_title or not str(self.screamsheet_title).strip():
            self.screamsheet_title = "Screamsheet"


@dataclass
class ScreamsheetOrder:
    """Complete input contract for the screamsheet engine.

    Set a field to a non-None options object to include that sheet.
    Leave a field as ``None`` to skip it entirely.
    """

    output: OutputOrderOptions | None = None
    # --- active batch sheets (generated in this order) ---
    briefing: BriefingOrderOptions | None = None
    mlb: MLBOrderOptions | None = None
    mlb_news: MLBNewsOrderOptions | None = None
    french_mlb_news: FrenchMLBNewsOrderOptions | None = None
    nhl_news: NHLNewsOrderOptions | None = None
    presidential: PresidentialOrderOptions | None = None
    sky: SkyOrderOptions | None = None
    # --- inactive / on-demand sheets (set to None in batch, available via --single) ---
    worldcup: WorldCupOrderOptions | None = None
    nhl: NHLOrderOptions | None = None
    nba: NBAOrderOptions | None = None
    nfl: NFLOrderOptions | None = None
    mlb_trade_rumors: MLBTradeRumorsOrderOptions | None = None
    home_run_derby: HomeRunDerbyOrderOptions | None = None
    # --- custom component-based screamsheets ---
    custom_sheets: list[CustomSheetOrderOptions] = field(default_factory=list)


@dataclass
class ScreamsheetResult:
    """Return value of runner.run_order()."""

    subscriber_name: str
    sheets_generated: list[str] = field(default_factory=list)
    options_summary: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


_RESERVED_COMPONENT_KEYS: frozenset[str] = frozenset(
    {
        "type",
        "title",
        "teams",
        "favorite_teams",
        "max_articles",
        "mad_fan",
        "weather",
        "location",
        "options",
    }
)


def build_custom_sheet_options_from_dict(
    sheet_key: str,
    raw: dict[str, Any],
    default_weather: WeatherLocationOptions | None = None,
) -> CustomSheetOrderOptions:
    """Parse a custom screamsheet YAML dictionary (containing ``components:``) into ``CustomSheetOrderOptions``."""
    screamsheet_title = str(raw.get("screamsheet_title") or raw.get("title") or "Screamsheet")
    subtitle = str(raw["subtitle"]) if raw.get("subtitle") is not None else None

    sheet_weather = default_weather
    loc_raw = raw.get("weather") or raw.get("location")
    if isinstance(loc_raw, dict) and "lat" in loc_raw and "lon" in loc_raw:
        sheet_weather = WeatherLocationOptions(
            lat=float(loc_raw["lat"]),
            lon=float(loc_raw["lon"]),
            location_name=str(
                loc_raw.get("name")
                or loc_raw.get("location_name")
                or (default_weather.location_name if default_weather else "My Location")
            ),
        )

    specs: list[ComponentSpec] = []
    for item in raw.get("components", []) or []:
        if isinstance(item, str):
            specs.append(ComponentSpec(type=item.strip(), weather=sheet_weather))
            continue
        if not isinstance(item, dict) or not item.get("type"):
            continue
        comp_type = str(item["type"]).strip()
        comp_title = str(item["title"]) if item.get("title") is not None else None
        raw_teams = item.get("teams", item.get("favorite_teams", [])) or []
        if isinstance(raw_teams, str):
            raw_teams = [raw_teams]
        max_articles = int(item.get("max_articles", 4))
        mad_fan = bool(item.get("mad_fan", False))

        comp_weather = sheet_weather
        comp_loc = item.get("weather") or item.get("location")
        if isinstance(comp_loc, dict) and "lat" in comp_loc and "lon" in comp_loc:
            comp_weather = WeatherLocationOptions(
                lat=float(comp_loc["lat"]),
                lon=float(comp_loc["lon"]),
                location_name=str(
                    comp_loc.get("name")
                    or comp_loc.get("location_name")
                    or (sheet_weather.location_name if sheet_weather else "My Location")
                ),
            )

        extra_options: dict[str, Any] = dict(item.get("options") or {})
        for k, v in item.items():
            if k not in _RESERVED_COMPONENT_KEYS:
                extra_options[k] = v

        specs.append(
            ComponentSpec(
                type=comp_type,
                title=comp_title,
                teams=list(raw_teams),
                max_articles=max_articles,
                mad_fan=mad_fan,
                weather=comp_weather,
                options=extra_options,
            )
        )

    return CustomSheetOrderOptions(
        sheet_key=sheet_key,
        screamsheet_title=screamsheet_title,
        subtitle=subtitle,
        components=specs,
        weather=sheet_weather,
    )

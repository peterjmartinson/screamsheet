"""ScreamsheetOrder contract — the public input model for the screamsheet engine.

Each field on ScreamsheetOrder maps to one sheet type.  A field set to ``None``
means "do not generate that sheet".  The presence of a non-None value is
sufficient to trigger generation.

Callers (including the CLI and external orchestration layers) construct a
ScreamsheetOrder and pass it to ``runner.run_order()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class NHLOrderOptions:
    """Options for the NHL sports / standings sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)


@dataclass
class MLBOrderOptions:
    """Options for the MLB sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)
    news_names: list[str] = field(default_factory=list)


@dataclass
class NBAOrderOptions:
    """Options for the NBA sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)


@dataclass
class NFLOrderOptions:
    """Options for the NFL sports sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)


@dataclass
class MLBNewsOrderOptions:
    """Options for the MLB News sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None


@dataclass
class NHLNewsOrderOptions:
    """Options for the NHL News sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None


@dataclass
class FrenchMLBNewsOrderOptions:
    """Options for the French MLB News sheet."""

    news_names: list[str] = field(default_factory=list)


@dataclass
class MLBTradeRumorsOrderOptions:
    """Options for the MLB Trade Rumors sheet."""

    news_names: list[str] = field(default_factory=list)
    weather: WeatherLocationOptions | None = None


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


@dataclass
class WorldCupOrderOptions:
    """Options for the FIFA World Cup sheet."""

    favorite_teams: list[TeamEntry] = field(default_factory=list)


@dataclass
class OutputOrderOptions:
    """Destination directory for generated PDFs."""

    directory: str = ""


@dataclass
class ScreamsheetOrder:
    """Complete input contract for the screamsheet engine.

    Set a field to a non-None options object to include that sheet.
    Leave a field as ``None`` to skip it entirely.
    """

    output: OutputOrderOptions | None = None
    # --- active batch sheets (generated in this order) ---
    mlb: MLBOrderOptions | None = None
    mlb_news: MLBNewsOrderOptions | None = None
    nhl_news: NHLNewsOrderOptions | None = None
    presidential: PresidentialOrderOptions | None = None
    sky: SkyOrderOptions | None = None
    worldcup: WorldCupOrderOptions | None = None
    # --- inactive / on-demand sheets (set to None in batch, available via --single) ---
    nhl: NHLOrderOptions | None = None
    nba: NBAOrderOptions | None = None
    nfl: NFLOrderOptions | None = None
    mlb_trade_rumors: MLBTradeRumorsOrderOptions | None = None
    french_mlb_news: FrenchMLBNewsOrderOptions | None = None


@dataclass
class ScreamsheetResult:
    """Return value of runner.run_order()."""

    subscriber_name: str
    sheets_generated: list[str] = field(default_factory=list)
    options_summary: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

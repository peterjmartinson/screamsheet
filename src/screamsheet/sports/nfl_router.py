"""NFL day-of-week strategy router.

Determines the operational focus of the screamsheet based on the day of the week:
- Monday: RECAP (Scoreboard + Featured Game Summary + Drive Chart)
- Tuesday: STANDINGS_AND_INJURIES (Standings + Team Injuries)
- Wednesday: FILM_ROOM (Season Metrics + Scheme Focus)
- Thursday: TNF_SCOUTING (TNF Scoreboard + Upcoming Opponent Stats)
- Friday: KEYS_TO_VICTORY (Final Practice Injury Designations)
- Saturday: WEEKEND_PREP (Weather Forecast + TV Schedule / Game Slate)
- Sunday: GAMEDAY_CARD (Pre-game Depth Chart + Head-to-Head)
"""
from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional


class NFLDayStrategy(str, Enum):
    RECAP = "RECAP"
    STANDINGS_AND_INJURIES = "STANDINGS_AND_INJURIES"
    FILM_ROOM = "FILM_ROOM"
    TNF_SCOUTING = "TNF_SCOUTING"
    KEYS_TO_VICTORY = "KEYS_TO_VICTORY"
    WEEKEND_PREP = "WEEKEND_PREP"
    GAMEDAY_CARD = "GAMEDAY_CARD"


DAY_TO_STRATEGY_MAP = {
    0: NFLDayStrategy.RECAP,                   # Monday
    1: NFLDayStrategy.STANDINGS_AND_INJURIES,  # Tuesday
    2: NFLDayStrategy.FILM_ROOM,               # Wednesday
    3: NFLDayStrategy.TNF_SCOUTING,            # Thursday
    4: NFLDayStrategy.KEYS_TO_VICTORY,         # Friday
    5: NFLDayStrategy.WEEKEND_PREP,            # Saturday
    6: NFLDayStrategy.GAMEDAY_CARD,            # Sunday
}

STRATEGY_CONFIG = {
    NFLDayStrategy.RECAP: {
        "description": "Monday recap featuring final scores, featured game summary, and drive chart.",
        "prompt_template_key": "nfl_recap",
        "data_loaders": ["scores", "game_summary"],
    },
    NFLDayStrategy.STANDINGS_AND_INJURIES: {
        "description": "Tuesday division standings, playoff bubble check, and injury reports.",
        "prompt_template_key": "nfl_standings_injuries",
        "data_loaders": ["standings", "injuries"],
    },
    NFLDayStrategy.FILM_ROOM: {
        "description": "Wednesday scheme, film room analysis, and advanced season metrics.",
        "prompt_template_key": "nfl_film_room",
        "data_loaders": ["standings", "team_stats"],
    },
    NFLDayStrategy.TNF_SCOUTING: {
        "description": "Thursday night preview and opponent scouting.",
        "prompt_template_key": "nfl_tnf_scouting",
        "data_loaders": ["scores", "standings"],
    },
    NFLDayStrategy.KEYS_TO_VICTORY: {
        "description": "Friday game prep, injury designations, and 3 keys to victory.",
        "prompt_template_key": "nfl_keys_to_victory",
        "data_loaders": ["injuries", "standings"],
    },
    NFLDayStrategy.WEEKEND_PREP: {
        "description": "Saturday weekend schedule, game slate, and weather forecasts.",
        "prompt_template_key": "nfl_weekend_prep",
        "data_loaders": ["scores", "weather"],
    },
    NFLDayStrategy.GAMEDAY_CARD: {
        "description": "Sunday gameday card, head-to-head stats, and matchup preview.",
        "prompt_template_key": "nfl_gameday_card",
        "data_loaders": ["scores", "standings", "injuries"],
    },
}


class ScreamSheetRouter:
    """Strategy router for NFL screamsheet."""

    def __init__(self, override_date: Optional[datetime] = None):
        self.override_date = override_date

    def get_strategy(self, date: Optional[datetime] = None) -> NFLDayStrategy:
        """Resolve the day strategy for the given date (or override/today)."""
        target_date = date or self.override_date or datetime.today()
        weekday = target_date.weekday()
        return DAY_TO_STRATEGY_MAP[weekday]

    def get_strategy_info(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Return strategy name, description, required data loaders, and prompt template key."""
        strategy = self.get_strategy(date)
        config = STRATEGY_CONFIG[strategy]
        return {
            "strategy": strategy,
            "strategy_name": strategy.value,
            "description": config["description"],
            "prompt_template_key": config["prompt_template_key"],
            "data_loaders": config["data_loaders"],
        }

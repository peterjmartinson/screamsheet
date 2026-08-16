"""Tests for NFL router."""
from datetime import datetime
import pytest
from screamsheet.sports.nfl_router import (
    NFLDayStrategy,
    ScreamSheetRouter,
    DAY_TO_STRATEGY_MAP,
)


@pytest.mark.parametrize(
    "dt,expected_strategy",
    [
        (datetime(2024, 9, 9), NFLDayStrategy.RECAP),                  # Monday
        (datetime(2024, 9, 10), NFLDayStrategy.STANDINGS_AND_INJURIES), # Tuesday
        (datetime(2024, 9, 11), NFLDayStrategy.FILM_ROOM),              # Wednesday
        (datetime(2024, 9, 12), NFLDayStrategy.TNF_SCOUTING),           # Thursday
        (datetime(2024, 9, 13), NFLDayStrategy.KEYS_TO_VICTORY),        # Friday
        (datetime(2024, 9, 14), NFLDayStrategy.WEEKEND_PREP),           # Saturday
        (datetime(2024, 9, 15), NFLDayStrategy.GAMEDAY_CARD),           # Sunday
    ]
)
def test_router_day_mapping(dt, expected_strategy):
    router = ScreamSheetRouter()
    strategy = router.get_strategy(dt)
    assert strategy == expected_strategy

    info = router.get_strategy_info(dt)
    assert info["strategy"] == expected_strategy
    assert "prompt_template_key" in info
    assert len(info["data_loaders"]) > 0


def test_router_override_date():
    router = ScreamSheetRouter(override_date=datetime(2024, 9, 9))
    assert router.get_strategy() == NFLDayStrategy.RECAP

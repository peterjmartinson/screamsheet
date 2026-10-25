"""Zodiac wheel renderer — backward-compatible wrapper around ZodiacWheelComponent."""
from __future__ import annotations

from ..components.sky.zodiac_wheel import (
    ZodiacWheelComponent,
    _INNER_R,
    _INVISIBLE_FILL,
    _INVISIBLE_TEXT,
    _OUTER_R,
    _PLANET_RADII,
    _PLANET_SYMBOLS,
    _RIM_R,
    _UNICODE_FONT,
    _VISIBLE_FILL,
    _VISIBLE_TEXT,
    _WHEEL_SIZE,
    _ZODIAC_FULL,
    _ZODIAC_SHORT,
)

ZodiacWheelSection = ZodiacWheelComponent

__all__ = [
    "ZodiacWheelComponent",
    "ZodiacWheelSection",
    "_INNER_R",
    "_INVISIBLE_FILL",
    "_INVISIBLE_TEXT",
    "_OUTER_R",
    "_PLANET_RADII",
    "_PLANET_SYMBOLS",
    "_RIM_R",
    "_UNICODE_FONT",
    "_VISIBLE_FILL",
    "_VISIBLE_TEXT",
    "_WHEEL_SIZE",
    "_ZODIAC_FULL",
    "_ZODIAC_SHORT",
]

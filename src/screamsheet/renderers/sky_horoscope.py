"""Sky horoscope renderer — backward-compatible wrapper around SkyHoroscopeComponent."""
from __future__ import annotations

from ..components.sky.sky_horoscope import (
    SkyHoroscopeComponent,
    _enlarge_astro_glyphs,
)
from ..llm.summarizers import HoroscopeSummarizer

SkyHoroscopeSection = SkyHoroscopeComponent

__all__ = [
    "HoroscopeSummarizer",
    "SkyHoroscopeComponent",
    "SkyHoroscopeSection",
    "_enlarge_astro_glyphs",
]

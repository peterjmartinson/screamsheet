"""Sky highlights renderer — backward-compatible wrapper around SkyHighlightsComponent."""
from __future__ import annotations

from ..components.sky.sky_highlights import SkyHighlightsComponent
from ..llm.summarizers import SkyNightSummarizer

SkyHighlightsSection = SkyHighlightsComponent

__all__ = [
    "SkyHighlightsComponent",
    "SkyHighlightsSection",
    "SkyNightSummarizer",
]

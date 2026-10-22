"""XKCD comic strip renderer — backward-compatible wrapper around XKCDComponent."""
from __future__ import annotations

from ..components.briefing.xkcd import XKCDComponent

XKCDSection = XKCDComponent

__all__ = [
    "XKCDComponent",
    "XKCDSection",
]

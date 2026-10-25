"""World Cup group standings renderer (backward-compatible alias for WorldCupStandingsComponent)."""
from __future__ import annotations

from ..components.standings.worldcup import WorldCupStandingsComponent

WorldCupStandingsSection = WorldCupStandingsComponent

__all__ = ["WorldCupStandingsSection", "WorldCupStandingsComponent"]

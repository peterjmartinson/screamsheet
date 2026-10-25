"""World Cup back-page box score renderer (backward-compatible alias)."""
from ..components.box_score import WorldCupBoxScoreComponent, _card_symbol

WorldCupBoxScoreSection = WorldCupBoxScoreComponent

__all__ = ["WorldCupBoxScoreSection", "WorldCupBoxScoreComponent", "_card_symbol"]

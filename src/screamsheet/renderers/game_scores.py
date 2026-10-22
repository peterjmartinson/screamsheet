"""Game scores section renderer (backward-compatible wrapper over GameScoresComponent)."""
from ..components.game_scores import GameScoresComponent, _determine_series_badge

GameScoresSection = GameScoresComponent

__all__ = ["GameScoresSection", "GameScoresComponent", "_determine_series_badge"]

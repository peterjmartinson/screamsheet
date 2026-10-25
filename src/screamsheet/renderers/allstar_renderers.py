"""All-Star Game screamsheet renderers (backward-compatible aliases)."""
from ..components.box_score import MLBAllStarBoxScoreComponent, MLBAllStarGameSummaryComponent
from ..components.game_scores import MLBAllStarGameScoresComponent

AllStarGameScoresSection = MLBAllStarGameScoresComponent
AllStarGameSummarySection = MLBAllStarGameSummaryComponent
AllStarSideBySideBoxScoreSection = MLBAllStarBoxScoreComponent

__all__ = [
    "AllStarGameScoresSection",
    "AllStarGameSummarySection",
    "AllStarSideBySideBoxScoreSection",
    "MLBAllStarGameScoresComponent",
    "MLBAllStarGameSummaryComponent",
    "MLBAllStarBoxScoreComponent",
]

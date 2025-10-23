from dataclasses import dataclass

@dataclass
class GameScore:
    """The standardized container for a single game score."""
    gameDate: str
    away_team: str
    home_team: str
    away_score: int
    home_score: int
    status: str

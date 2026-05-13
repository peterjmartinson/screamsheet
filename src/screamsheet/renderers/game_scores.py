"""Game scores section renderer."""
from datetime import datetime
from typing import List, Any, Optional, Dict, Tuple
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from ..base import Section, DataProvider


def _determine_series_badge(
    away_abbrev: str,
    home_abbrev: str,
    away_score: int,
    home_score: int,
    series_status: Dict[str, Any],
) -> Tuple[str, str]:
    """Return (badge_row, badge_text) for a playoff game.

    badge_row is "away" or "home".
    badge_text is one of "(leads X-Y)", "(won X-Y)", or "(tied X-X)".
    """
    top_abbrev = series_status["top_seed_abbrev"]
    top_wins = series_status["top_seed_wins"]
    bottom_abbrev = series_status["bottom_seed_abbrev"]
    bottom_wins = series_status["bottom_seed_wins"]
    needed = series_status["needed_to_win"]

    # Determine series winner/leader
    if top_wins == needed:
        leader_abbrev = top_abbrev
        badge_text = f"(won {top_wins}-{bottom_wins})"
    elif bottom_wins == needed:
        leader_abbrev = bottom_abbrev
        badge_text = f"(won {bottom_wins}-{top_wins})"
    elif top_wins > bottom_wins:
        leader_abbrev = top_abbrev
        badge_text = f"(leads {top_wins}-{bottom_wins})"
    elif bottom_wins > top_wins:
        leader_abbrev = bottom_abbrev
        badge_text = f"(leads {bottom_wins}-{top_wins})"
    else:
        # Tied — badge goes on game winner's row
        leader_abbrev = away_abbrev if away_score > home_score else home_abbrev
        badge_text = f"(tied {top_wins}-{bottom_wins})"

    badge_row = "away" if leader_abbrev == away_abbrev else "home"
    return badge_row, badge_text


class GameScoresSection(Section):
    """
    Section for displaying game scores.
    
    Shows all game scores from a specific date in a multi-column layout.
    """
    
    def __init__(self, title: str, provider: DataProvider, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.styles = getSampleStyleSheet()
        
        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )

        self.score_style = ParagraphStyle(
            name="ScoreCell",
            fontName='Helvetica',
            fontSize=10,
            alignment=TA_RIGHT,
            leading=12,
        )
    
    def fetch_data(self):
        """Fetch game scores from the provider."""
        self.data = self.provider.get_game_scores(self.date)
    
    def render(self) -> List[Any]:
        """Render the game scores section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Section title suppressed (document top-level title used instead)
        
        # Organize games into three columns
        scores_left: List[Any] = []
        scores_center: List[Any] = []
        scores_right: List[Any] = []
        
        for i, game in enumerate(self.data):
            if game.get("away_score") is not None and game.get("home_score") is not None:
                series_status: Optional[Dict[str, Any]] = game.get("series_status")

                if series_status:
                    badge_row, badge_text = _determine_series_badge(
                        away_abbrev=game.get("away_abbrev", ""),
                        home_abbrev=game.get("home_abbrev", ""),
                        away_score=game["away_score"],
                        home_score=game["home_score"],
                        series_status=series_status,
                    )
                    away_score_cell: Any = Paragraph(
                        f'{game["away_score"]} {badge_text}'
                        if badge_row == "away"
                        else str(game["away_score"]),
                        self.score_style,
                    )
                    home_score_cell: Any = Paragraph(
                        f'{game["home_score"]} {badge_text}'
                        if badge_row == "home"
                        else str(game["home_score"]),
                        self.score_style,
                    )
                    col_widths = [70, 90]
                else:
                    away_score_cell = str(game["away_score"])
                    home_score_cell = str(game["home_score"])
                    col_widths = [80, 50]

                table_data = [
                    [game['away_team'], away_score_cell],
                    [f"@{game['home_team']}", home_score_cell],
                ]
                table_style = TableStyle([
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('LEFTPADDING', (0, 0), (0, -1), 0),
                    ('RIGHTPADDING', (0, 0), (0, -1), 0),
                ])
                game_table = Table(table_data, colWidths=col_widths)
                game_table.setStyle(table_style)
                
                if i % 3 == 0:
                    scores_left.append(game_table)
                    scores_left.append(Spacer(1, 10))
                elif i % 3 == 1:
                    scores_center.append(game_table)
                    scores_center.append(Spacer(1, 10))
                else:
                    scores_right.append(game_table)
                    scores_right.append(Spacer(1, 10))
        
        # Create three-column layout
        # Use available width (letter size minus margins)
        available_width = 540  # 8.5" * 72 - 72 (margins)
        col_width = available_width / 3
        
        scores_table = Table(
            [[scores_left, scores_center, scores_right]],
            colWidths=[col_width, col_width, col_width],
            hAlign='LEFT'
        )
        
        elements.append(scores_table)
        
        return elements

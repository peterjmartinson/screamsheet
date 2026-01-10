"""Box score section renderer."""
from datetime import datetime
from typing import List, Any
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from ..base import Section, DataProvider


class BoxScoreSection(Section):
    """
    Section for displaying box scores.
    
    Shows detailed statistics from a specific game.
    Currently only fully implemented for MLB and NHL.
    """
    
    def __init__(self, title: str, provider: DataProvider, team_id: int, date: datetime):
        super().__init__(title)
        self.provider = provider
        self.team_id = team_id
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
    
    def fetch_data(self):
        """Fetch box score from the provider."""
        self.data = self.provider.get_box_score(self.team_id, self.date)
    
    def render(self) -> List[Any]:
        """Render the box score section."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            return []
        
        elements = []
        
        # Add section title
        elements.append(Paragraph(self.title, self.subtitle_style))
        elements.append(Spacer(1, 12))
        
        # Render based on data structure
        if isinstance(self.data, dict):
            if 'batting_stats' in self.data:
                # MLB box score
                elements.extend(self._render_mlb_boxscore(self.data))
            elif 'home_skaters' in self.data:
                # NHL box score
                elements.extend(self._render_nhl_boxscore(self.data))
        
        return elements
    
    def _render_mlb_boxscore(self, boxscore_stats: dict) -> List[Any]:
        """Render MLB box score with batting and pitching stats."""
        elements = []
        
        # Batting table
        batting_stats = boxscore_stats.get('batting_stats', [])
        if batting_stats:
            hitting_header = ["Batter", "AB", "R", "H", "HR", "RBI", "BB", "SO"]
            hitting_data = [hitting_header]
            
            for player in batting_stats:
                row = [
                    player['name'],
                    str(player.get('AB', 0)),
                    str(player.get('R', 0)),
                    str(player.get('H', 0)),
                    str(player.get('HR', 0)),
                    str(player.get('RBI', 0)),
                    str(player.get('BB', 0)),
                    str(player.get('SO', 0))
                ]
                hitting_data.append(row)
            
            hitting_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ])
            
            hitting_table = Table(hitting_data, colWidths=[120, 30, 30, 30, 30, 30, 30, 30])
            hitting_table.setStyle(hitting_style)
            elements.append(hitting_table)
            elements.append(Spacer(1, 12))
        
        # Pitching table
        pitching_stats = boxscore_stats.get('pitching_stats', [])
        if pitching_stats:
            pitching_header = ["Pitcher", "IP", "H", "R", "ER", "BB", "SO", "HR"]
            pitching_data = [pitching_header]
            
            for player in pitching_stats:
                row = [
                    player['name'],
                    str(player.get('IP', 0)),
                    str(player.get('H', 0)),
                    str(player.get('R', 0)),
                    str(player.get('ER', 0)),
                    str(player.get('BB', 0)),
                    str(player.get('SO', 0)),
                    str(player.get('HR', 0))
                ]
                pitching_data.append(row)
            
            pitching_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ])
            
            pitching_table = Table(pitching_data, colWidths=[120, 30, 30, 30, 30, 30, 30, 30])
            pitching_table.setStyle(pitching_style)
            elements.append(pitching_table)
        
        return elements
    
    def _render_nhl_boxscore(self, boxscore_stats: dict) -> List[Any]:
        """Render NHL box score with skater and goalie stats."""
        elements = []
        
        # Home skaters
        home_skaters = boxscore_stats.get('home_skaters', [])
        if home_skaters:
            elements.append(Paragraph("<b>Home Skaters</b>", self.styles['h4']))
            skater_header = ["Player", "G", "A", "PTS", "+/-", "PIM", "SOG"]
            skater_data = [skater_header]
            
            for player in home_skaters:
                row = [
                    player.get('name', ''),
                    str(player.get('goals', 0)),
                    str(player.get('assists', 0)),
                    str(player.get('points', 0)),
                    str(player.get('plusMinus', 0)),
                    str(player.get('pim', 0)),
                    str(player.get('shots', 0))
                ]
                skater_data.append(row)
            
            skater_style = TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ])
            
            skater_table = Table(skater_data, colWidths=[120, 20, 20, 30, 30, 30, 30])
            skater_table.setStyle(skater_style)
            elements.append(skater_table)
            elements.append(Spacer(1, 12))
        
        return elements

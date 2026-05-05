"""Box score section renderer."""
import logging
from datetime import datetime
from typing import List, Any, Optional
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph, PageBreak
from reportlab.platypus.flowables import KeepInFrame
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from ..base import Section, DataProvider

logger = logging.getLogger(__name__)


class BoxScoreSection(Section):
    """
    Section for displaying box scores with game summary.
    
    Shows game summary on the left and box score on the right in a two-column layout.
    Currently only fully implemented for MLB and NHL.
    """
    
    def __init__(self, title: str, provider: DataProvider, team_id: int, date: datetime,
                 is_primary_favorite: bool = False):
        super().__init__(title)
        self.provider = provider
        self.team_id = team_id
        self.date = date
        self.is_primary_favorite = is_primary_favorite
        self.styles = getSampleStyleSheet()
        
        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        self.summary_style = ParagraphStyle(
            name="SummaryText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT
        )
        
        self.legend_style = ParagraphStyle(
            name="LegendText",
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            spaceAfter=2,
            alignment=TA_LEFT
        )
    
    def fetch_data(self):
        """Fetch box score from the provider."""
        logger.info("Fetching box score for team_id=%s date=%s", self.team_id, self.date.strftime("%Y-%m-%d"))
        self.data = self.provider.get_box_score(self.team_id, self.date)
        if self.data is None:
            logger.warning("get_box_score returned None for team_id=%s date=%s — back page may be blank", self.team_id, self.date.strftime("%Y-%m-%d"))
    
    def render(self) -> List[Any]:
        """Render the box score section with two-column layout."""
        if not self.data:
            self.fetch_data()
        
        if not self.data:
            logger.warning("No box score data for team_id=%s — returning empty render", self.team_id)
            return []
        
        elements: List[Any] = [PageBreak()]
        
        # Get game summary from provider
        game_summary = self.provider.get_game_summary(
            self.team_id, self.date, is_primary_favorite=self.is_primary_favorite
        )
        
        # Build left column (game summary)
        left_column = []
        if game_summary:
            left_column.append(Paragraph(game_summary, self.summary_style))
        else:
            left_column.append(Paragraph("[No game summary available]", self.summary_style))
        
        # Build right column (box score)
        right_column = []
        
        # Render based on data structure
        if isinstance(self.data, dict):
            if 'batting_stats' in self.data:
                # MLB box score
                right_column.extend(self._render_mlb_boxscore(self.data))
            elif 'skater_table' in self.data:
                # NHL box score (already rendered tables)
                right_column.extend(self._render_nhl_boxscore_tables(self.data))
            elif 'home_skaters' in self.data:
                # NHL box score (raw data - legacy format)
                right_column.extend(self._render_nhl_boxscore(self.data))
            elif 'player_stats' in self.data:
                # NBA box score
                right_column.extend(self._render_nba_boxscore(self.data))
        
        # Wrap the summary in KeepInFrame so it never exceeds the page frame
        # height (708pt on 'Later' pages with letter/36pt-margin layout).
        # mode='truncate' clips quietly rather than raising a LayoutError.
        summary_frame = KeepInFrame(
            maxWidth=0, maxHeight=680,
            content=left_column, mode='truncate'
        )

        # Create two-column layout
        two_column_table = Table(
            [[summary_frame, right_column]],
            colWidths=['50%', '50%'],
            rowHeights=[None]
        )
        
        two_column_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 12),
            ('LEFTPADDING', (1, 0), (1, 0), 0),
        ]))
        
        elements.append(two_column_table)
        
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
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ])
            
            hitting_table = Table(hitting_data, colWidths=[100, 24, 24, 24, 24, 24, 24, 24])
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
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ])
            
            pitching_table = Table(pitching_data, colWidths=[100, 24, 24, 24, 24, 24, 24, 24])
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
    
    def _render_nhl_boxscore_tables(self, boxscore_data: dict) -> List[Any]:
        """Render NHL box score with already-rendered Table objects and legend."""
        elements = []
        
        # Add skater table if it exists
        skater_table = boxscore_data.get('skater_table')
        if skater_table:
            elements.append(skater_table)
            elements.append(Spacer(1, 6))
        
        # Add goalie table if it exists
        goalie_table = boxscore_data.get('goalie_table')
        if goalie_table:
            elements.append(goalie_table)
            elements.append(Spacer(1, 8))
        
        # Add legend
        legend_items = [
            "G = Goals",
            "A = Assists",
            "P = Points",
            "SOG = Shots on Goal",
            "PIM = Penalty Minutes",
            "SA = Shots Against",
            "SV = Saves",
            "SV% = Save Percentage"
        ]
        
        for item in legend_items:
            elements.append(Paragraph(item, self.legend_style))
        
        return elements

    def _render_nba_boxscore(self, boxscore_data: dict) -> List[Any]:
        """Render NBA box score with per-player stats and an acronym legend."""
        elements: List[Any] = []

        player_stats = boxscore_data.get("player_stats", [])
        if not player_stats:
            return elements

        # Drop the first name, keep everything else ("Wendell Carter Jr." → "Carter Jr.")
        def _short_name(full: str) -> str:
            parts = full.split()
            return " ".join(parts[1:]) if len(parts) > 1 else full

        header = ["Player", "MIN", "FG", "3P", "FT", "REB", "AST", "PTS"]
        table_data = [header]
        for p in player_stats:
            table_data.append([
                _short_name(p.get("name", "")),
                p.get("MIN", ""),
                p.get("FG", ""),
                p.get("3P", ""),
                p.get("FT", ""),
                str(p.get("REB", 0)),
                str(p.get("AST", 0)),
                str(p.get("PTS", 0)),
            ])

        table_style = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])

        # Column widths: last name ~65pt, FG wider (e.g. "9-18"), counters narrow
        # Total = 65+28+34+28+28+22+22+22 = 249pt — fits in a 270pt half-page column
        col_widths = [65, 28, 34, 28, 28, 22, 22, 22]
        nba_table = Table(table_data, colWidths=col_widths)
        nba_table.setStyle(table_style)
        elements.append(nba_table)
        elements.append(Spacer(1, 8))

        legend_items = [
            "MIN = Minutes",
            "FG = Field Goals (Made-Attempted)",
            "3P = Three-Pointers (Made-Attempted)",
            "FT = Free Throws (Made-Attempted)",
            "REB = Rebounds",
            "AST = Assists",
            "PTS = Points",
        ]
        for item in legend_items:
            elements.append(Paragraph(item, self.legend_style))

        return elements

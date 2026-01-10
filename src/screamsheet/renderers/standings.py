"""Standings section renderer."""
from typing import List, Any
from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
import pandas as pd

from ..base import Section, DataProvider


class StandingsSection(Section):
    """
    Section for displaying league standings.
    
    Displays standings in a formatted table. Format varies by sport.
    """
    
    def __init__(self, title: str, provider: DataProvider):
        super().__init__(title)
        self.provider = provider
        self.styles = getSampleStyleSheet()
        
        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles['h3'],
            fontName='Helvetica-Bold',
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        self.centered_style = ParagraphStyle(
            name="CenteredText",
            alignment=TA_CENTER
        )
    
    def fetch_data(self):
        """Fetch standings from the provider."""
        self.data = self.provider.get_standings()
    
    def render(self) -> List[Any]:
        """Render the standings section."""
        if self.data is None:
            self.fetch_data()
        
        if self.data is None or (isinstance(self.data, pd.DataFrame) and self.data.empty):
            return []
        
        elements = []
        
        # Add section title
        elements.append(Paragraph(self.title, self.subtitle_style))
        elements.append(Spacer(1, 12))
        
        # Detect sport type and render accordingly
        if 'division' in self.data.columns:
            # MLB-style standings
            elements.append(self._render_mlb_standings(self.data))
        elif 'conference' in self.data.columns and 'GP' in self.data.columns:
            # NHL-style standings
            elements.append(self._render_nhl_standings(self.data))
        elif 'conference' in self.data.columns and 'winPercent' in self.data.columns:
            # NFL-style standings
            elements.append(self._render_nfl_standings(self.data))
        elif 'conference' in self.data.columns:
            # NBA-style standings
            elements.append(self._render_nba_standings(self.data))
        else:
            # Generic standings
            elements.append(self._render_generic_standings(self.data))
        
        return elements
    
    def _render_mlb_standings(self, standings_df: pd.DataFrame) -> Table:
        """Render MLB standings in AL/NL format."""
        al_divisions = standings_df[standings_df['division'].str.contains('American League')]
        nl_divisions = standings_df[standings_df['division'].str.contains('National League')]
        divisions_order = ['East', 'Central', 'West']
        
        grid_data = [
            ['', Paragraph("<b>American League</b>", self.centered_style),
             Paragraph("<b>National League</b>", self.centered_style)],
        ]
        
        for geography in divisions_order:
            row_list = [Paragraph(f"<b>{geography}</b>", self.centered_style)]
            al_group = al_divisions[al_divisions['division'].str.contains(geography)]
            nl_group = nl_divisions[nl_divisions['division'].str.contains(geography)]
            
            for group in [al_group, nl_group]:
                if not group.empty:
                    header = ["Team", "W", "L", "%"]
                    table_data = [header] + group[['team', 'wins', 'losses', 'pct']].values.tolist()
                    table_style = TableStyle([
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ])
                    standings_table = Table(table_data, colWidths=[150, 30, 30, 30])
                    standings_table.setStyle(table_style)
                    row_list.append(standings_table)
                else:
                    row_list.append('')
            grid_data.append(row_list)
        
        master_table_style = TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
        ])
        final_standings_table = Table(grid_data, colWidths=[60, 250, 250])
        final_standings_table.setStyle(master_table_style)
        
        return final_standings_table
    
    def _render_nhl_standings(self, standings_df: pd.DataFrame) -> Table:
        """Render NHL standings by conference and division."""
        eastern_conf = standings_df[standings_df['conference'] == 'Eastern']
        western_conf = standings_df[standings_df['conference'] == 'Western']
        
        grid_data = [
            [Paragraph("<b>EASTERN CONFERENCE</b>", self.centered_style),
             Paragraph("<b>WESTERN CONFERENCE</b>", self.centered_style)],
        ]
        
        division_layout = [
            {'east': 'Atlantic', 'west': 'Central'},
            {'east': 'Metropolitan', 'west': 'Pacific'},
        ]
        
        INNER_COL_WIDTHS = [130, 20, 20, 25, 25]
        
        for row_info in division_layout:
            east_div_name = row_info['east']
            west_div_name = row_info['west']
            
            row_list = []
            
            for conf_data, div_name in [(eastern_conf, east_div_name), (western_conf, west_div_name)]:
                group = conf_data[conf_data['division'] == div_name]
                
                if not group.empty:
                    INNER_HEADER = [f"{div_name} Division", "W", "L", "OTL", "P"]
                    table_data = [INNER_HEADER] + group[['team', 'W', 'L', 'OTL', 'P']].values.tolist()
                    
                    table_style = TableStyle([
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ])
                    
                    inner_table = Table(table_data, colWidths=INNER_COL_WIDTHS)
                    inner_table.setStyle(table_style)
                    row_list.append(inner_table)
                else:
                    row_list.append('')
            
            grid_data.append(row_list)
        
        master_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ])
        
        final_table = Table(grid_data, colWidths=[270, 270])
        final_table.setStyle(master_style)
        
        return final_table
    
    def _render_nfl_standings(self, standings_df: pd.DataFrame) -> Table:
        """Render NFL standings by conference."""
        afc = standings_df[standings_df['conference'] == 'AFC']
        nfc = standings_df[standings_df['conference'] == 'NFC']
        
        grid_data = [
            [Paragraph("<b>AFC</b>", self.centered_style),
             Paragraph("<b>NFC</b>", self.centered_style)],
        ]
        
        row_list = []
        for conf_data in [afc, nfc]:
            if not conf_data.empty:
                header = ["Team", "W", "L", "T", "%"]
                table_data = [header] + conf_data[['team', 'wins', 'losses', 'ties', 'winPercent']].values.tolist()
                
                table_style = TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ])
                standings_table = Table(table_data, colWidths=[150, 25, 25, 25, 40])
                standings_table.setStyle(table_style)
                row_list.append(standings_table)
            else:
                row_list.append('')
        
        grid_data.append(row_list)
        
        master_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ])
        
        final_table = Table(grid_data, colWidths=[270, 270])
        final_table.setStyle(master_style)
        
        return final_table
    
    def _render_nba_standings(self, standings_df: pd.DataFrame) -> Table:
        """Render NBA standings by conference."""
        eastern = standings_df[standings_df['conference'] == 'Eastern']
        western = standings_df[standings_df['conference'] == 'Western']
        
        grid_data = [
            [Paragraph("<b>Eastern Conference</b>", self.centered_style),
             Paragraph("<b>Western Conference</b>", self.centered_style)],
        ]
        
        row_list = []
        for conf_data in [eastern, western]:
            if not conf_data.empty:
                header = ["Team", "W", "L", "%"]
                table_data = [header] + conf_data[['team', 'wins', 'losses', 'pct']].values.tolist()
                
                table_style = TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ])
                standings_table = Table(table_data, colWidths=[150, 30, 30, 40])
                standings_table.setStyle(table_style)
                row_list.append(standings_table)
            else:
                row_list.append('')
        
        grid_data.append(row_list)
        
        master_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ])
        
        final_table = Table(grid_data, colWidths=[270, 270])
        final_table.setStyle(master_style)
        
        return final_table
    
    def _render_generic_standings(self, standings_df: pd.DataFrame) -> Table:
        """Render generic standings table."""
        # Create a simple table from the dataframe
        header = list(standings_df.columns)
        table_data = [header] + standings_df.values.tolist()
        
        table_style = TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ])
        
        standings_table = Table(table_data)
        standings_table.setStyle(table_style)
        
        return standings_table

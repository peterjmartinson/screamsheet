"""Home Run Derby section renderer for ReportLab PDF generation."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..providers.mlb_provider import MLBDataProvider


class HomeRunDerbySection(Section):
    """Section renderer for displaying MLB Home Run Derby bracket & Statcast data in a PDF screamsheet."""

    def __init__(
        self,
        title: str,
        provider: MLBDataProvider,
        date: datetime,
        game_pk: Optional[int] = None,
    ):
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.game_pk = game_pk
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="DerbySubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=8,
            alignment=TA_CENTER,
        )
        self.normal_center = ParagraphStyle(
            name="DerbyCenter",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            alignment=TA_CENTER,
        )
        self.bold_center = ParagraphStyle(
            name="DerbyBoldCenter",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            alignment=TA_CENTER,
        )
        self.champ_style = ParagraphStyle(
            name="DerbyChamp",
            parent=self.styles["h2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.HexColor("#1b4d3e"),
            spaceAfter=6,
            alignment=TA_CENTER,
        )

    def fetch_data(self) -> None:
        """Fetch Derby summary data from the MLBDataProvider."""
        self.data = self.provider.get_home_run_derby_summary(date=self.date, game_pk=self.game_pk)

    def has_content(self) -> bool:
        """Always return True so that Derby section renders either full bracket or informative fallback message."""
        if self.data is None:
            self.fetch_data()
        return True

    def render(self) -> List[Any]:
        """Render the Derby section into ReportLab flowable elements for PDF."""
        if self.data is None:
            self.fetch_data()

        if not self.data or not isinstance(self.data, dict):
            return [Paragraph("No Home Run Derby data available for this date.", self.normal_center)]

        elements: List[Any] = []
        bracket = self.data.get("bracket", {})
        statcast = self.data.get("statcast", {})

        # Champion & Runner-Up Header Table
        champion = bracket.get("champion")
        runner_up = bracket.get("runner_up")
        if champion and runner_up:
            champ_text = f"CHAMPION: {champion.get('player', 'TBD')} ({champion.get('hits', 0)} HR)"
            runner_text = f"Runner-Up: {runner_up.get('player', 'TBD')} ({runner_up.get('hits', 0)} HR)"
            elements.append(Paragraph(champ_text, self.champ_style))
            elements.append(Paragraph(runner_text, self.bold_center))
            elements.append(Spacer(1, 12))

        # Statcast Highlights Box
        longest = statcast.get("longest_hr", {})
        hardest = statcast.get("hardest_hit", {})
        if longest or hardest:
            elements.append(Paragraph("Statcast Highlights", self.subtitle_style))
            stat_data = [
                ["Metric", "Value", "Player"],
                [
                    "Longest Home Run",
                    f"{longest.get('distance', 0)} ft",
                    str(longest.get("player", "N/A")),
                ],
                [
                    "Hardest Hit Ball",
                    f"{hardest.get('exit_velocity', 0.0)} mph",
                    str(hardest.get("player", "N/A")),
                ],
            ]
            stat_table = Table(stat_data, colWidths=[150, 100, 200])
            stat_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                    ]
                )
            )
            elements.append(stat_table)
            elements.append(Spacer(1, 16))

        # Round-by-Round Bracket Table
        rounds = bracket.get("rounds", [])
        if rounds:
            elements.append(Paragraph("Round-by-Round Matchups", self.subtitle_style))
            bracket_data = [["Round", "Matchup", "Score", "Winner"]]
            row_idx = 1
            table_styles = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4d3e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]

            for rnd in rounds:
                round_name = rnd.get("round_name", "")
                matchups = rnd.get("matchups", [])
                start_row = row_idx
                for m in matchups:
                    top_p = m.get("top_seed", {}).get("player", "TBD")
                    top_h = m.get("top_seed", {}).get("hits", 0)
                    bot_p = m.get("bottom_seed", {}).get("player", "TBD")
                    bot_h = m.get("bottom_seed", {}).get("hits", 0)
                    winner = m.get("winner", "TBD")

                    matchup_p = Paragraph(f"{top_p}<br/><b>vs</b><br/>{bot_p}", self.normal_center)
                    score_p = Paragraph(f"<b>{top_h} - {bot_h}</b>", self.normal_center)
                    winner_p = Paragraph(f"<b>{winner}</b>", self.bold_center)
                    round_p = Paragraph(f"<b>{round_name}</b>", self.bold_center)

                    bracket_data.append([round_p, matchup_p, score_p, winner_p])
                    row_idx += 1

                if start_row < row_idx - 1:
                    table_styles.append(("SPAN", (0, start_row), (0, row_idx - 1)))
                    table_styles.append(("VALIGN", (0, start_row), (0, row_idx - 1), "MIDDLE"))

            for r in range(1, len(bracket_data)):
                bg = colors.white if r % 2 != 0 else colors.HexColor("#f8f9fa")
                table_styles.append(("BACKGROUND", (0, r), (-1, r), bg))

            bracket_table = Table(bracket_data, colWidths=[110, 150, 80, 140])
            bracket_table.setStyle(TableStyle(table_styles))
            elements.append(bracket_table)

        if not elements:
            elements.append(
                Paragraph(
                    f"No Home Run Derby statistics or bracket results were found for {self.date.strftime('%B %d, %Y')}.",
                    self.normal_center,
                )
            )

        return elements

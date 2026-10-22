"""Base BoxScoreComponent and GameSummaryComponent implementations."""
from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import KeepInFrame

from ...base import DataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry

logger = logging.getLogger(__name__)


class BoxScoreComponent(ScreamsheetComponent):
    """Component for displaying game summary (left) + box score (right) in a two-column layout."""

    layout_spec = ComponentLayoutSpec(
        weight=1.0,
        full_page_only=True,
        max_on_front_page=None,
        max_per_page=1,
        component_family="box_score",
    )

    def __init__(
        self,
        title: str = "Box Score",
        provider: Optional[DataProvider] = None,
        team_id: Optional[int] = None,
        date: Optional[datetime] = None,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        team_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            team_id=team_id,
            date=date,
            is_primary_favorite=is_primary_favorite,
            mad_fan=mad_fan,
            favorite_teams=favorite_teams,
            team_name=team_name,
            **kwargs,
        )
        self.team_id: int = team_id or 0
        self.team_name: Optional[str] = team_name
        self.favorite_teams: List[Tuple[int, str]] = list(favorite_teams) if favorite_teams else []
        self.is_primary_favorite = is_primary_favorite
        self.mad_fan = mad_fan
        self.page_slot = "back"
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

        self.summary_style = ParagraphStyle(
            name="SummaryText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=5,
            alignment=TA_LEFT,
        )

        self.summary_header_style = ParagraphStyle(
            name="SummaryHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceAfter=3,
            alignment=TA_LEFT,
        )

        self.summary_takeaway_style = ParagraphStyle(
            name="SummaryTakeaway",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            spaceAfter=3,
            alignment=TA_LEFT,
        )

        self.legend_style = ParagraphStyle(
            name="LegendText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            spaceAfter=2,
            alignment=TA_LEFT,
        )

    def _resolve_featured_team(self) -> Optional[Tuple[int, str]]:
        """Resolve which team's game to feature when team_id is not explicitly provided."""
        if self.team_id:
            return (self.team_id, self.team_name or "")
        if self.provider is None:
            return None

        for tid, tname in self.favorite_teams:
            if self.provider.has_game(tid, self.date):
                if self.favorite_teams and (tid, tname) == self.favorite_teams[0]:
                    self.is_primary_favorite = True
                return (tid, tname)

        all_teams = self.provider.get_all_teams_for_date(self.date)
        if all_teams:
            chosen = random.choice(all_teams)
            return chosen
        return None

    def _format_summary_flowables(self, text: Optional[str]) -> List[Any]:
        """Format multi-paragraph LLM summary with clear section breaks, bolding, and no distracting bullets."""
        import re

        flowables: List[Any] = []
        if not text or not str(text).strip():
            flowables.append(Paragraph("[No game summary available]", self.summary_style))
            return flowables

        def _clean_markdown_text(s: str) -> str:
            s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
            s = s.replace("**", "")
            return s.strip()

        def _strip_bullet_prefix(s: str) -> str:
            return re.sub(r"^(\s*([•\-\*]|\d+[\.\)])\s*)", "", s).strip()

        normalized = str(text).replace("\r\n", "\n").strip()

        takeaway_match = re.search(
            r"(?:\n|^|(?<=[.!?])\s+)(?:#{1,4}\s*)?(\*{0,2}(?:3\s+)?Key\s+Takeaways:?\*{0,2})\s*:?\s*",
            normalized,
            re.IGNORECASE,
        )

        if takeaway_match:
            recap_part = normalized[: takeaway_match.start()].strip()
            takeaways_part = normalized[takeaway_match.end() :].strip()

            if recap_part:
                recap_blocks = [b.strip() for b in recap_part.split("\n\n") if b.strip()]
                if len(recap_blocks) == 1 and "\n" in recap_blocks[0]:
                    recap_blocks = [l.strip() for l in recap_blocks[0].split("\n") if l.strip()]
                for block in recap_blocks:
                    p_text = " ".join(block.split())
                    p_text = _clean_markdown_text(p_text)
                    if p_text:
                        flowables.append(Paragraph(p_text, self.summary_style))
                        flowables.append(Spacer(1, 3))

            raw_header = takeaway_match.group(1).strip("*# ")
            header_title = raw_header if raw_header.endswith(":") else f"{raw_header}:"
            flowables.append(Paragraph(f"<b>{header_title}</b>", self.summary_header_style))
            flowables.append(Spacer(1, 2))

            pattern = r"(?:^|\n|(?<=[.!?])\s+)(?:[•\-\*]|\d+[\.\)])?\s*(<b>[^<]+:?</b>:?|\*\*[^*]+:?\*\*:?|[A-Z][A-Za-z0-9\s\'\-]{1,35}:)"
            splits = re.split(pattern, takeaways_part)
            takeaway_items = []
            i = 1 if len(splits) > 1 and not splits[0].strip() else 0
            while i < len(splits):
                tok = splits[i].strip()
                if (
                    i + 1 < len(splits)
                    and re.match(r"^(?:<b>|\*\*|[A-Z])", tok)
                    and tok.endswith((":", "</b>", "</b>:", "**", "**:"))
                ):
                    content = splits[i + 1].strip()
                    takeaway_items.append(f"{tok} {content}")
                    i += 2
                else:
                    if tok:
                        takeaway_items.append(tok)
                    i += 1

            if not takeaway_items:
                takeaway_items = [l.strip() for l in takeaways_part.split("\n") if l.strip()]

            for item in takeaway_items:
                item = _clean_markdown_text(item)
                item = _strip_bullet_prefix(item)
                item = " ".join(item.split())
                item = re.sub(r"^<b>([^<:]+)</b>:\s*", r"<b>\1:</b> ", item)
                item = re.sub(r"^\[([^\]:]+)\]:?\s*", r"<b>\1:</b> ", item)
                m = re.match(r"^([A-Za-z0-9\s\'\-]+:)\s*(.*)", item)
                if m and not item.startswith("<b>"):
                    item = f"<b>{m.group(1)}</b> {m.group(2)}"
                if item:
                    flowables.append(Paragraph(item, self.summary_takeaway_style))
                    flowables.append(Spacer(1, 2))
        else:
            raw_blocks = [b.strip() for b in normalized.split("\n\n") if b.strip()]
            if len(raw_blocks) == 1 and "\n" in raw_blocks[0]:
                raw_blocks = [l.strip() for l in raw_blocks[0].split("\n") if l.strip()]

            for block in raw_blocks:
                lines = [line.strip() for line in block.split("\n") if line.strip()]
                is_takeaway_block = any(
                    l.startswith(("-", "*", "•"))
                    or (len(l) > 2 and l[0].isdigit() and l[1:3] in (". ", ") "))
                    for l in lines
                )

                if is_takeaway_block:
                    for line in lines:
                        if line.startswith(("###", "##")):
                            h_text = _clean_markdown_text(line.lstrip("# "))
                            flowables.append(Paragraph(f"<b>{h_text}</b>", self.summary_header_style))
                        elif line.lower().startswith(("key takeaways", "3 key takeaways")):
                            h_text = _clean_markdown_text(line)
                            flowables.append(Paragraph(f"<b>{h_text}</b>", self.summary_header_style))
                        else:
                            clean_item = _clean_markdown_text(line)
                            clean_item = _strip_bullet_prefix(clean_item)
                            if clean_item:
                                flowables.append(Paragraph(clean_item, self.summary_takeaway_style))
                    flowables.append(Spacer(1, 4))
                elif len(lines) == 1 and (
                    lines[0].startswith(("###", "##"))
                    or lines[0].lower().startswith(("key takeaways", "3 key takeaways"))
                ):
                    h_text = _clean_markdown_text(lines[0].lstrip("# "))
                    flowables.append(Paragraph(f"<b>{h_text}</b>", self.summary_header_style))
                else:
                    p_text = " ".join(lines)
                    p_text = _clean_markdown_text(p_text)
                    flowables.append(Paragraph(p_text, self.summary_style))

        return flowables

    def fetch_data(self) -> None:
        """Fetch box score from the provider."""
        if self.provider is None:
            self.data = None
            return
        if not self.team_id:
            resolved = self._resolve_featured_team()
            if resolved:
                self.team_id, self.team_name = resolved
                if self.title == "Box Score" and self.team_name:
                    self.title = f"{self.team_name} Box Score"
            else:
                self.data = None
                return

        logger.info("Fetching box score for team_id=%s date=%s", self.team_id, self.date.strftime("%Y-%m-%d"))
        self.data = self.provider.get_box_score(self.team_id, self.date)
        if self.data is None:
            logger.warning(
                "get_box_score returned None for team_id=%s date=%s — back page may be blank",
                self.team_id,
                self.date.strftime("%Y-%m-%d"),
            )

    def render(self) -> List[Any]:
        """Render the box score section with two-column layout."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            logger.warning("No box score data for team_id=%s — returning empty render", self.team_id)
            return []

        elements: List[Any] = []

        # Get game summary from provider
        game_summary = self.provider.get_game_summary(
            self.team_id, self.date, is_primary_favorite=self.is_primary_favorite, mad_fan=self.mad_fan
        )

        # Build left column (game summary) with clean section breaks
        left_column = self._format_summary_flowables(game_summary)

        # Build right column (box score)
        right_column = []

        if isinstance(self.data, dict):
            if "batting_stats" in self.data:
                right_column.extend(self._render_mlb_boxscore(self.data))
            elif "skater_table" in self.data:
                right_column.extend(self._render_nhl_boxscore_tables(self.data))
            elif "home_skaters" in self.data:
                right_column.extend(self._render_nhl_boxscore(self.data))
            elif "player_stats" in self.data:
                right_column.extend(self._render_nba_boxscore(self.data))
            elif "away_linescores" in self.data and "team_stats" in self.data:
                right_column.extend(self._render_nfl_boxscore(self.data))

        summary_frame = KeepInFrame(
            maxWidth=0,
            maxHeight=680,
            content=left_column,
            mode="truncate",
        )

        two_column_table = Table(
            [[summary_frame, right_column]],
            colWidths=["50%", "50%"],
            rowHeights=[None],
        )

        two_column_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 12),
                    ("LEFTPADDING", (1, 0), (1, 0), 0),
                ]
            )
        )

        elements.append(two_column_table)

        return elements

    def render_markdown(self) -> str:
        """Render game summary and box score sequentially in single-column Markdown."""
        if not self.data:
            self.fetch_data()

        if not self.data:
            return ""

        lines = []

        game_summary = self.provider.get_game_summary(
            self.team_id, self.date, is_primary_favorite=self.is_primary_favorite, mad_fan=self.mad_fan
        )
        if game_summary:
            lines.append("### Game Summary\n\n" + game_summary.strip() + "\n")

        lines.append("### Box Score\n")
        if isinstance(self.data, dict):
            if "batting_stats" in self.data and self.data["batting_stats"]:
                lines.append("#### Batting")
                lines.append("| Batter | AB | R | H | HR | RBI | BB | SO |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
                for p in self.data["batting_stats"]:
                    lines.append(
                        f"| {p.get('name')} | {p.get('AB', 0)} | {p.get('R', 0)} | {p.get('H', 0)} | {p.get('HR', 0)} | {p.get('RBI', 0)} | {p.get('BB', 0)} | {p.get('SO', 0)} |"
                    )
                lines.append("")
            if "pitching_stats" in self.data and self.data["pitching_stats"]:
                lines.append("#### Pitching")
                lines.append("| Pitcher | IP | H | R | ER | BB | SO | HR | ERA |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
                for p in self.data["pitching_stats"]:
                    lines.append(
                        f"| {p.get('name')} | {p.get('IP', 0)} | {p.get('H', 0)} | {p.get('R', 0)} | {p.get('ER', 0)} | {p.get('BB', 0)} | {p.get('SO', 0)} | {p.get('HR', 0)} | {p.get('ERA', '0.00')} |"
                    )
                lines.append("")
            if "player_stats" in self.data and self.data["player_stats"]:
                lines.append("| Player | PTS | REB | AST | STL | BLK |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
                for p in self.data["player_stats"]:
                    lines.append(
                        f"| {p.get('name')} | {p.get('PTS', 0)} | {p.get('REB', 0)} | {p.get('AST', 0)} | {p.get('STL', 0)} | {p.get('BLK', 0)} |"
                    )
                lines.append("")
            if "skaters" in self.data and self.data["skaters"]:
                lines.append("| Skater | G | A | PTS | +/- | SOG |")
                lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
                for p in self.data["skaters"]:
                    lines.append(
                        f"| {p.get('name')} | {p.get('G', 0)} | {p.get('A', 0)} | {p.get('PTS', 0)} | {p.get('+/-', 0)} | {p.get('SOG', 0)} |"
                    )
                lines.append("")
            if "away_linescores" in self.data and "team_stats" in self.data:
                lines.append("#### Linescore")
                qlabels = self.data.get("quarter_labels", ["1", "2", "3", "4"])
                lines.append(f"| Team | {' | '.join(qlabels)} | T |")
                lines.append(f"| :--- | {' | '.join([':---:'] * len(qlabels))} | :---: |")
                away_ls = [str(x) for x in self.data.get("away_linescores", [])]
                lines.append(
                    f"| {self.data.get('away_team')} | {' | '.join(away_ls[:len(qlabels)])} | {self.data.get('away_score')} |"
                )
                home_ls = [str(x) for x in self.data.get("home_linescores", [])]
                lines.append(
                    f"| {self.data.get('home_team')} | {' | '.join(home_ls[:len(qlabels)])} | {self.data.get('home_score')} |"
                )
                lines.append("")
                if self.data.get("team_stats"):
                    lines.append("#### Team Comparison")
                    a_abb = self.data.get("away_abbrev", "AWAY")
                    h_abb = self.data.get("home_abbrev", "HOME")
                    lines.append(f"| Stat | {a_abb} | {h_abb} |")
                    lines.append("| :--- | :---: | :---: |")
                    for s in self.data.get("team_stats", []):
                        lines.append(f"| {s.get('stat')} | {s.get('away')} | {s.get('home')} |")
                    lines.append("")
                if self.data.get("top_performers"):
                    lines.append("#### Top Performers")
                    lines.append("| Leader | Player | Stats |")
                    lines.append("| :--- | :--- | :--- |")
                    for p in self.data.get("top_performers", [])[:6]:
                        lines.append(f"| {p.get('category')} | {p.get('player')} | {p.get('stat')} |")
                    lines.append("")

        return "\n".join(lines)

    def _render_mlb_boxscore(self, boxscore_stats: dict) -> List[Any]:
        """Render MLB box score with batting and pitching stats."""
        elements = []

        batting_stats = boxscore_stats.get("batting_stats", [])
        if batting_stats:
            hitting_header = ["Batter", "AB", "R", "H", "HR", "RBI", "BB", "SO"]
            hitting_data = [hitting_header]

            for player in batting_stats:
                row = [
                    player["name"],
                    str(player.get("AB", 0)),
                    str(player.get("R", 0)),
                    str(player.get("H", 0)),
                    str(player.get("HR", 0)),
                    str(player.get("RBI", 0)),
                    str(player.get("BB", 0)),
                    str(player.get("SO", 0)),
                ]
                hitting_data.append(row)

            hitting_style = TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )

            hitting_table = Table(hitting_data, colWidths=[100, 24, 24, 24, 24, 24, 24, 24])
            hitting_table.setStyle(hitting_style)
            elements.append(hitting_table)
            elements.append(Spacer(1, 12))

        pitching_stats = boxscore_stats.get("pitching_stats", [])
        if pitching_stats:
            pitching_header = ["Pitcher", "IP", "H", "R", "ER", "BB", "SO", "HR"]
            pitching_data = [pitching_header]

            for player in pitching_stats:
                row = [
                    player["name"],
                    str(player.get("IP", 0)),
                    str(player.get("H", 0)),
                    str(player.get("R", 0)),
                    str(player.get("ER", 0)),
                    str(player.get("BB", 0)),
                    str(player.get("SO", 0)),
                    str(player.get("HR", 0)),
                ]
                pitching_data.append(row)

            pitching_style = TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )

            pitching_table = Table(pitching_data, colWidths=[100, 24, 24, 24, 24, 24, 24, 24])
            pitching_table.setStyle(pitching_style)
            elements.append(pitching_table)

        return elements

    def _render_nhl_boxscore(self, boxscore_stats: dict) -> List[Any]:
        """Render NHL box score with skater and goalie stats."""
        elements = []

        home_skaters = boxscore_stats.get("home_skaters", [])
        if home_skaters:
            elements.append(Paragraph("<b>Home Skaters</b>", self.styles["h4"]))
            skater_header = ["Player", "G", "A", "PTS", "+/-", "PIM", "SOG"]
            skater_data = [skater_header]

            for player in home_skaters:
                row = [
                    player.get("name", ""),
                    str(player.get("goals", 0)),
                    str(player.get("assists", 0)),
                    str(player.get("points", 0)),
                    str(player.get("plusMinus", 0)),
                    str(player.get("pim", 0)),
                    str(player.get("shots", 0)),
                ]
                skater_data.append(row)

            skater_style = TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ]
            )

            skater_table = Table(skater_data, colWidths=[120, 20, 20, 30, 30, 30, 30])
            skater_table.setStyle(skater_style)
            elements.append(skater_table)
            elements.append(Spacer(1, 12))

        return elements

    def _render_nhl_boxscore_tables(self, boxscore_data: dict) -> List[Any]:
        """Render NHL box score with already-rendered Table objects and legend."""
        elements = []

        skater_table = boxscore_data.get("skater_table")
        if skater_table:
            elements.append(skater_table)
            elements.append(Spacer(1, 6))

        goalie_table = boxscore_data.get("goalie_table")
        if goalie_table:
            elements.append(goalie_table)
            elements.append(Spacer(1, 8))

        legend_items = [
            "G = Goals",
            "A = Assists",
            "P = Points",
            "SOG = Shots on Goal",
            "PIM = Penalty Minutes",
            "SA = Shots Against",
            "SV = Saves",
            "SV% = Save Percentage",
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

        def _short_name(full: str) -> str:
            parts = full.split()
            return " ".join(parts[1:]) if len(parts) > 1 else full

        header = ["Player", "MIN", "FG", "3P", "FT", "REB", "AST", "PTS"]
        table_data = [header]
        for p in player_stats:
            table_data.append(
                [
                    _short_name(p.get("name", "")),
                    p.get("MIN", ""),
                    p.get("FG", ""),
                    p.get("3P", ""),
                    p.get("FT", ""),
                    str(p.get("REB", 0)),
                    str(p.get("AST", 0)),
                    str(p.get("PTS", 0)),
                ]
            )

        table_style = TableStyle(
            [
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
            ]
        )

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

    def _render_nfl_boxscore(self, boxscore_data: dict) -> List[Any]:
        """Render NFL box score with linescore, team comparison, and top performers."""
        elements: List[Any] = []

        table_style = TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )

        quarter_labels = boxscore_data.get("quarter_labels", ["1", "2", "3", "4"])
        header = ["Team"] + list(quarter_labels) + ["T"]
        num_q = len(quarter_labels)
        num_num_cols = num_q + 1
        num_width = 22 if num_num_cols > 5 else 25
        team_width = 268 - (num_num_cols * num_width)
        col_widths_linescore = [team_width] + [num_width] * num_num_cols

        away_team = boxscore_data.get("away_team", "Away")
        away_ls = [str(x) for x in boxscore_data.get("away_linescores", [])]
        while len(away_ls) < num_q:
            away_ls.append("0")
        away_score = str(boxscore_data.get("away_score", "0"))
        away_row = [away_team] + away_ls[:num_q] + [away_score]

        home_team = boxscore_data.get("home_team", "Home")
        home_ls = [str(x) for x in boxscore_data.get("home_linescores", [])]
        while len(home_ls) < num_q:
            home_ls.append("0")
        home_score = str(boxscore_data.get("home_score", "0"))
        home_row = [home_team] + home_ls[:num_q] + [home_score]

        linescore_table = Table([header, away_row, home_row], colWidths=col_widths_linescore)
        linescore_table.setStyle(table_style)
        elements.append(linescore_table)
        elements.append(Spacer(1, 8))

        team_stats = boxscore_data.get("team_stats", [])
        if team_stats:
            away_abbrev = boxscore_data.get("away_abbrev", "AWAY")
            home_abbrev = boxscore_data.get("home_abbrev", "HOME")
            stats_header = ["Team Stats", away_abbrev, home_abbrev]
            stats_data = [stats_header]
            for s in team_stats:
                stats_data.append([s.get("stat", ""), str(s.get("away", "-")), str(s.get("home", "-"))])
            stats_table = Table(stats_data, colWidths=[140, 64, 64])
            stats_table.setStyle(table_style)
            elements.append(stats_table)
            elements.append(Spacer(1, 8))

        top_performers = boxscore_data.get("top_performers", [])
        if top_performers:
            perf_header = ["Leader", "Player", "Stats"]
            perf_data = [perf_header]
            for p in top_performers[:6]:
                perf_data.append([p.get("category", ""), p.get("player", ""), p.get("stat", "")])
            perf_table = Table(perf_data, colWidths=[54, 104, 110])
            perf_table.setStyle(table_style)
            elements.append(perf_table)
            elements.append(Spacer(1, 8))

        legend_items = [
            "PASS = Passing",
            "RUSH = Rushing",
            "REC = Receiving",
            "YDS = Yards",
            "TD = Touchdowns",
            "CAR = Carries",
            "INT = Interceptions",
        ]
        for item in legend_items:
            elements.append(Paragraph(item, self.legend_style))

        return elements


class GameSummaryComponent(ScreamsheetComponent):
    """Standalone game summary component."""

    layout_spec = ComponentLayoutSpec(
        weight=0.65,
        full_page_only=False,
        max_on_front_page=None,
        max_per_page=None,
        component_family="game_summary",
    )

    def __init__(
        self,
        title: str = "Game Summary",
        provider: Optional[DataProvider] = None,
        team_id: int = 0,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            team_id=team_id,
            date=date,
            **kwargs,
        )
        self.team_id = team_id
        self.page_slot = "back"
        self.styles = getSampleStyleSheet()

        self.subtitle_style = ParagraphStyle(
            name="SectionSubtitle",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
        )

        self.summary_text_style = ParagraphStyle(
            name="SummaryText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
        )

    def fetch_data(self) -> None:
        """Fetch game summary from the provider."""
        if self.provider is None:
            self.data = None
            return
        self.data = self.provider.get_game_summary(self.team_id, self.date)

    def render(self) -> List[Any]:
        """Render the game summary section."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return []

        elements = []
        paragraphs = [p for p in str(self.data).split("\n\n") if p.strip()]
        for p in paragraphs:
            elements.append(Paragraph(p, self.summary_text_style))
            elements.append(Spacer(1, 6))

        return elements

    def render_markdown(self) -> str:
        """Render the game summary in Markdown format."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return ""

        return f"### {self.title}\n\n{self.data}"

"""World Cup back-page box score renderer.

Layout (two-column):
  Left  – LLM / event-narrative game summary from the provider
  Right – Per-player table for both teams
           Columns: Player | MP | G | A | S/SOT | C
           Goalkeepers: Player | MP | G | A | Saves | C
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import KeepInFrame

from ..base import DataProvider, Section

logger = logging.getLogger(__name__)


def _card_symbol(yellow: int, red: int) -> str:
    if yellow and red:
        return "YR"
    if red:
        return "R"
    if yellow:
        return "Y"
    return "-"


class WorldCupBoxScoreSection(Section):
    """Back-page box score for the World Cup featured fixture."""

    def __init__(
        self,
        title: str,
        provider: DataProvider,
        fixture_id: int,
        date: datetime,
        is_primary_favorite: bool = False,
    ) -> None:
        super().__init__(title)
        self.provider = provider
        self.fixture_id = fixture_id
        self.date = date
        self.is_primary_favorite = is_primary_favorite
        self.page_slot = "back"

        styles = getSampleStyleSheet()
        self.summary_style = ParagraphStyle(
            "WCSummary",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        self.team_header_style = ParagraphStyle(
            "WCTeamHeader",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=10,
            spaceAfter=4,
            alignment=TA_LEFT,
        )
        self.legend_style = ParagraphStyle(
            "WCLegend",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            spaceAfter=2,
            alignment=TA_LEFT,
        )

    # ------------------------------------------------------------------

    def fetch_data(self) -> None:
        self.players: List[Dict[str, Any]] = self.provider.get_fixture_lineups(self.fixture_id)
        self.events: List[Dict[str, Any]] = self.provider.get_fixture_events(self.fixture_id)
        self.stats: Dict[str, Dict[str, Any]] = self.provider.get_fixture_statistics(self.fixture_id)
        # Fetch penalty-shootout detail when available (WorldCup26Provider only)
        _get_penalty = getattr(self.provider, "get_penalty_detail", None)
        self.penalty_detail: Optional[Dict[str, Any]] = (
            _get_penalty(self.fixture_id) if callable(_get_penalty) else None
        )
        # Set self.data so the base Section.has_content() returns True.
        # The actual content is stored in self.players/events/stats above.
        self.data = {"fetched": True}

    def render(self) -> List[Any]:
        if not hasattr(self, "players"):
            self.fetch_data()

        # ---- left column: narrative summary ----
        summary_text: Optional[str] = self.provider.get_game_summary(
            self.fixture_id, self.date, is_primary_favorite=self.is_primary_favorite
        )
        left_column: List[Any] = []
        for line in (summary_text or "[No summary available]").split("\n"):
            left_column.append(Paragraph(line or " ", self.summary_style))

        # ---- right column: box score tables ----
        right_column: List[Any] = self._render_player_tables()

        summary_frame = KeepInFrame(
            maxWidth=0, maxHeight=680, content=left_column, mode="truncate"
        )

        two_col = Table(
            [[summary_frame, right_column]],
            colWidths=["50%", "50%"],
        )
        two_col.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 12),
                    ("LEFTPADDING", (1, 0), (1, 0), 0),
                ]
            )
        )
        return [two_col]

    # ------------------------------------------------------------------

    def _render_player_tables(self) -> List[Any]:
        players = getattr(self, "players", [])
        if not players:
            # Fall back to a goals-event table when lineup data is unavailable
            fallback: List[Any] = self._render_goals_table(getattr(self, "events", []))
            penalty_detail = getattr(self, "penalty_detail", None)
            if penalty_detail is not None:
                fallback.append(Spacer(1, 8))
                fallback.extend(self._render_penalty_shootout_table(penalty_detail))
            return fallback

        # Group players by team
        teams: Dict[str, List[Dict[str, Any]]] = {}
        for p in players:
            teams.setdefault(p.get("team_name") or "Unknown", []).append(p)

        elements: List[Any] = []
        for team_name, roster in teams.items():
            elements.append(Paragraph(team_name, self.team_header_style))
            outfield = [p for p in roster if p.get("position") != "G"]
            goalies = [p for p in roster if p.get("position") == "G"]

            if outfield:
                elements.append(self._build_outfield_table(outfield))
                elements.append(Spacer(1, 4))
            if goalies:
                elements.append(self._build_goalie_table(goalies))
                elements.append(Spacer(1, 6))

        # Legend
        for item in [
            "MP=Minutes Played  G=Goals  A=Assists",
            "S/SOT=Shots/Shots on Target  C=Cards (Y=Yellow, R=Red, YR=Both)",
        ]:
            elements.append(Paragraph(item, self.legend_style))

        return elements

    def _render_goals_table(self, events: List[Dict[str, Any]]) -> List[Any]:
        """Render a simple goals-event table when no lineup data is available."""
        if not events:
            return [Paragraph("No goal events recorded.", self.summary_style)]
        header = ["Min", "Scorer", "Team"]
        rows: List[List[str]] = [header]
        for ev in events:
            elapsed = ev.get("time", {}).get("elapsed", "?")
            player = (ev.get("player") or {}).get("name") or ""
            team = (ev.get("team") or {}).get("name") or ""
            suffix = " (p)" if ev.get("detail") else ""
            rows.append([f"{elapsed}'", f"{player}{suffix}", team])
        t = self._styled_table(rows, col_widths=[30, 120, 90])
        return [Paragraph("Goals", self.team_header_style), t]

    def _render_penalty_shootout_table(self, detail: Dict[str, Any]) -> List[Any]:
        """Render a penalty-shootout summary table."""
        home = detail.get("home_team", "")
        away = detail.get("away_team", "")
        h_pen = detail.get("home_penalty_score", "")
        a_pen = detail.get("away_penalty_score", "")

        elements: List[Any] = [
            Paragraph(
                f"Penalty Shootout — {home} {h_pen}  ·  {a_pen} {away}",
                self.team_header_style,
            )
        ]

        rows: List[List[str]] = [["Team", "Scored", "Missed"]]
        h_scored = ", ".join(detail.get("home_scorers", [])) or "—"
        h_missed = ", ".join(detail.get("home_misses", [])) or "—"
        a_scored = ", ".join(detail.get("away_scorers", [])) or "—"
        a_missed = ", ".join(detail.get("away_misses", [])) or "—"
        rows.append([home, h_scored, h_missed])
        rows.append([away, a_scored, a_missed])

        elements.append(self._styled_table(rows, col_widths=[60, 110, 70]))
        return elements

    def _build_outfield_table(self, players: List[Dict[str, Any]]) -> Table:
        header = ["Player", "MP", "G", "A", "S/SOT", "C"]
        rows: List[List[str]] = [header]
        for p in players:
            shots = f"{p.get('shots_total', 0)}/{p.get('shots_on_target', 0)}"
            rows.append(
                [
                    p.get("player_name") or "",
                    str(p.get("minutes") or "-"),
                    str(p.get("goals", 0)),
                    str(p.get("assists", 0)),
                    shots,
                    _card_symbol(p.get("yellow_cards", 0), p.get("red_cards", 0)),
                ]
            )
        return self._styled_table(rows, col_widths=[90, 22, 18, 18, 36, 18])

    def _build_goalie_table(self, goalies: List[Dict[str, Any]]) -> Table:
        header = ["GK", "MP", "G", "A", "SV", "C"]
        rows: List[List[str]] = [header]
        for p in goalies:
            rows.append(
                [
                    p.get("player_name") or "",
                    str(p.get("minutes") or "-"),
                    str(p.get("goals", 0)),
                    str(p.get("assists", 0)),
                    str(p.get("saves", 0)),
                    _card_symbol(p.get("yellow_cards", 0), p.get("red_cards", 0)),
                ]
            )
        return self._styled_table(rows, col_widths=[90, 22, 18, 18, 22, 18])

    @staticmethod
    def _styled_table(rows: List[List[str]], col_widths: List[int]) -> Table:
        t = Table(rows, colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
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
        )
        return t

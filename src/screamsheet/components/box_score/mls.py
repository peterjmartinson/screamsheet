"""MLS Box Score component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...base import DataProvider
from ...providers.mls_provider import MLSDataProvider
from ..registry import ComponentRegistry
from .base import BoxScoreComponent


@ComponentRegistry.register("mls_box_score")
class MLSBoxScoreComponent(BoxScoreComponent):
    """Back-page Match of the Day or Featured Team deep dive for Major League Soccer."""

    component_type = "mls_box_score"

    def __init__(
        self,
        title: str = "MLS Box Score",
        provider: Optional[DataProvider] = None,
        team_id: Optional[int] = None,
        date: Optional[datetime] = None,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        team_name: Optional[str] = None,
        event_id: Optional[str] = None,
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
        self.event_id: Optional[str] = event_id
        self.page_slot = "back"

        styles = getSampleStyleSheet()
        self.match_title_style = ParagraphStyle(
            "MLSMatchTitle",
            parent=styles["h2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
        )
        self.match_subtitle_style = ParagraphStyle(
            "MLSMatchSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        self.narrative_style = ParagraphStyle(
            "MLSNarrative",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=5,
        )
        self.section_h_style = ParagraphStyle(
            "MLSSectionHeader",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceBefore=3,
            spaceAfter=3,
        )
        self.table_cell_style = ParagraphStyle(
            "MLSTableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.black,
        )

    def create_default_provider(self) -> DataProvider:
        return MLSDataProvider()

    def fetch_data(self) -> None:
        if self.provider is None:
            self.provider = self.create_default_provider()

        # 1. Resolve event_id from team_id or favorite teams
        if not self.event_id or str(self.event_id) in ("0", "None"):
            self.event_id = None
            if self.team_id and self.team_id != 0:
                self.event_id = getattr(self.provider, "get_game_id", lambda tid, d: None)(self.team_id, self.date)

            if not self.event_id and self.favorite_teams:
                scores = getattr(self.provider, "get_game_scores", lambda d: [])(self.date)
                for fav_id, fav_name in self.favorite_teams:
                    for g in scores:
                        if g.get("home_id") == fav_id or g.get("away_id") == fav_id:
                            self.event_id = str(g.get("game_id"))
                            self.team_name = fav_name
                            break
                    if self.event_id:
                        break

            # 2. Fall back to Match of the Day if no favorite team played
            if not self.event_id:
                motd = getattr(self.provider, "get_match_of_the_day", lambda d: None)(self.date)
                if motd and motd.get("game_id"):
                    self.event_id = str(motd["game_id"])
                else:
                    self.data = {"has_match": False}
                    return

        box = getattr(self.provider, "get_box_score", lambda eid, d: None)(self.event_id, self.date)
        summary = getattr(self.provider, "get_game_summary", lambda eid, d, **kw: "")(
            self.event_id,
            self.date,
            is_primary_favorite=self.is_primary_favorite,
            mad_fan=self.mad_fan,
        )

        self.data = {
            "has_match": True,
            "box": box,
            "summary": summary,
        }

    def render(self) -> List[Any]:
        if not self.data:
            self.fetch_data()

        if not self.data or not self.data.get("has_match") or not self.data.get("box"):
            return [
                Paragraph("<b>No MLS matches were played yesterday.</b>", self.match_title_style),
                Paragraph("The league is currently on a matchday break.", self.match_subtitle_style),
            ]

        box = self.data["box"]
        summary = self.data.get("summary", "")

        home = box.get("home_team", {})
        away = box.get("away_team", {})
        h_name = home.get("name", "Home")
        a_name = away.get("name", "Away")
        h_score = str(home.get("score", 0))
        a_score = str(away.get("score", 0))
        venue_info = box.get("venue", "MLS Stadium")

        elements: List[Any] = []

        # 1. Match Header
        header_text = f"<b>{h_name}  {h_score}  –  {a_score}  {a_name}</b>"
        elements.append(Paragraph(header_text, self.match_title_style))
        elements.append(Paragraph(f"Major League Soccer  •  {venue_info}", self.match_subtitle_style))
        elements.append(Spacer(1, 4))

        # 2. Left Column: Recap Narrative
        left_col: List[Any] = []
        left_col.append(Paragraph("<b>MATCH RECAP</b>", self.section_h_style))
        for para in summary.strip().split("\n\n"):
            clean_p = para.strip().replace("\n", " ")
            if clean_p:
                left_col.append(Paragraph(clean_p, self.narrative_style))

        # 3. Right Column: Match Stats & Events
        right_col: List[Any] = []

        # A. Key Events / Scoring Summary
        key_events = box.get("key_events", [])
        if key_events:
            right_col.append(Paragraph("<b>KEY MATCH EVENTS</b>", self.section_h_style))
            ev_rows = []
            for ev in key_events[:6]:
                minute = ev.get("minute", "—")
                desc = ev.get("text", "")
                ev_rows.append([minute, Paragraph(desc, self.table_cell_style)])

            ev_table = Table(ev_rows, colWidths=[28, 222])
            ev_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            right_col.append(ev_table)
            right_col.append(Spacer(1, 6))

        # B. Team Match Statistics Comparison Table
        team_metrics = box.get("team_metrics", [])
        if team_metrics:
            right_col.append(Paragraph("<b>MATCH STATISTICS</b>", self.section_h_style))
            stat_rows = [
                [
                    Paragraph(f"<b>{h_name[:15]}</b>", self.table_cell_style),
                    Paragraph("<b>Metric</b>", self.table_cell_style),
                    Paragraph(f"<b>{a_name[:15]}</b>", self.table_cell_style),
                ]
            ]
            for m in team_metrics:
                stat_rows.append([str(m.get("home", "")), str(m.get("label", "")), str(m.get("away", ""))])

            st_table = Table(stat_rows, colWidths=[75, 100, 75])
            st_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            right_col.append(st_table)
            right_col.append(Spacer(1, 6))

        # C. Starting Lineups
        starters = box.get("starters", {})
        h_starters = starters.get("home", [])
        a_starters = starters.get("away", [])
        if h_starters and a_starters:
            right_col.append(Paragraph("<b>STARTING XI</b>", self.section_h_style))
            lineup_rows = [
                [
                    Paragraph(f"<b>{h_name[:14]}</b>", self.table_cell_style),
                    Paragraph(f"<b>{a_name[:14]}</b>", self.table_cell_style),
                ]
            ]
            max_len = max(len(h_starters), len(a_starters))
            for i in range(min(max_len, 11)):
                hp = h_starters[i] if i < len(h_starters) else {}
                ap = a_starters[i] if i < len(a_starters) else {}

                h_str = f"#{hp.get('number', '')} {hp.get('name', '')} ({hp.get('pos', '')})" if hp else ""
                a_str = f"#{ap.get('number', '')} {ap.get('name', '')} ({ap.get('pos', '')})" if ap else ""

                lineup_rows.append([h_str, a_str])

            lineup_table = Table(lineup_rows, colWidths=[125, 125])
            lineup_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]
                )
            )
            right_col.append(lineup_table)

        # 4. Master Two-Column Table
        two_col = Table(
            [[left_col, right_col]],
            colWidths=[265, 265],
        )
        two_col.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, -1), 8),
                    ("LEFTPADDING", (1, 0), (1, -1), 8),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(two_col)
        return elements

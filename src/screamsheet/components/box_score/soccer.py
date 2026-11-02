"""International soccer box score / Match of the Day deep dive component."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import KeepInFrame

from ...base import DataProvider
from ...providers.soccer_provider import SoccerDataProvider
from ..registry import ComponentRegistry
from .base import BoxScoreComponent

logger = logging.getLogger(__name__)


@ComponentRegistry.register("soccer_box_score")
class SoccerBoxScoreComponent(BoxScoreComponent):
    """Back-page Match of the Day deep dive for international soccer."""

    component_type = "soccer_box_score"

    def __init__(
        self,
        title: str = "Match of the Day",
        provider: Optional[DataProvider] = None,
        fixture_id: Optional[int] = None,
        date: Optional[datetime] = None,
        is_primary_favorite: bool = False,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            is_primary_favorite=is_primary_favorite,
            fixture_id=fixture_id,
            **kwargs,
        )
        self.fixture_id: int = fixture_id or 0
        self.favorite_teams = favorite_teams
        self.page_slot = "back"

        styles = getSampleStyleSheet()
        self.match_title_style = ParagraphStyle(
            "SoccerMatchTitle",
            parent=styles["h2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=2,
        )
        self.match_subtitle_style = ParagraphStyle(
            "SoccerMatchSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.dimgrey,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        self.spotlight_style = ParagraphStyle(
            "SoccerSpotlight",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#713F12"),
        )
        self.narrative_style = ParagraphStyle(
            "SoccerNarrative",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
        self.section_h_style = ParagraphStyle(
            "SoccerSectionHeader",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=9,
            alignment=TA_LEFT,
            spaceBefore=2,
            spaceAfter=3,
        )

    def create_default_provider(self) -> DataProvider:
        return SoccerDataProvider()

    def fetch_data(self) -> None:
        if self.provider is None:
            self.data = None
            return

        if not self.fixture_id:
            # Check favorite_teams if specified
            if self.favorite_teams:
                scores = getattr(self.provider, "get_game_scores", lambda d: [])(self.date)
                completed = [
                    s for s in scores
                    if s.get("status_short") in getattr(self.provider, "COMPLETED_STATUSES", {"FT", "AET", "PEN"})
                ]
                for fav_id, _ in self.favorite_teams:
                    for g in completed:
                        if g.get("home_id") == fav_id or g.get("away_id") == fav_id:
                            self.fixture_id = int(g["fixture_id"])
                            break
                    if self.fixture_id:
                        break

            if not self.fixture_id:
                motd = getattr(self.provider, "get_match_of_the_day", lambda d: None)(self.date)
                if motd and motd.get("fixture_id"):
                    self.fixture_id = int(motd["fixture_id"])
                else:
                    self.data = {"has_match": False}
                    return

        box = getattr(self.provider, "get_box_score", lambda fid, d: None)(self.fixture_id, self.date)
        summary = getattr(self.provider, "get_game_summary", lambda fid, d: "")(self.fixture_id, self.date)
        self.data = {
            "has_match": True,
            "box": box,
            "summary": summary,
        }

    def render(self) -> List[Any]:
        if not self.data:
            self.fetch_data()

        if not self.data:
            return []

        elements: List[Any] = []

        if not self.data.get("has_match") or not self.data.get("box"):
            return self._render_offday_fallback()

        box = self.data["box"]
        summary = self.data.get("summary", "")

        home = box.get("home_team", {})
        away = box.get("away_team", {})
        h_name = home.get("name", "Home")
        a_name = away.get("name", "Away")
        h_score = str(home.get("score", 0))
        a_score = str(away.get("score", 0))

        # 1. Match Header
        comp_info = box.get("competition", "International Match")
        venue_info = box.get("venue", "")
        header_text = f"<b>{h_name}  {h_score}  –  {a_score}  {a_name}</b>"
        elements.append(Paragraph(header_text, self.match_title_style))
        elements.append(Paragraph(f"{comp_info}  •  {venue_info}", self.match_subtitle_style))

        # 2. CR7 Spotlight Banner
        spotlight = box.get("ronaldo_spotlight")
        if spotlight and spotlight.get("featured"):
            rating = spotlight.get("rating", "8.5")
            goals = spotlight.get("goals", 0)
            total = spotlight.get("career_total", 916)
            spot_table = Table(
                [[
                    Paragraph(
                        f"★ <b>CR7 SPOTLIGHT:</b> Rating: <b>{rating}</b>  |  Goals: <b>{goals}</b>  |  Career Goals: <b>{total}</b>",
                        self.spotlight_style,
                    )
                ]],
                colWidths=[530],
            )
            spot_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF9C3")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#EAB308")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            elements.append(spot_table)
            elements.append(Spacer(1, 6))

        # 3. Two-Column Layout (Left: Lineups, Right: Summary, Stats, Timeline)
        left_col: List[Any] = []
        right_col: List[Any] = []

        # Left Column: Starting Formations & Lineups
        left_col.append(Paragraph("<b>STARTING LINEUPS & RATINGS</b>", self.section_h_style))
        xi = box.get("starting_xi", {})
        for team_label, team_dict, roster in [
            (f"{h_name} ({home.get('formation', '4-3-3')})", home, xi.get("home", [])),
            (f"{a_name} ({away.get('formation', '4-3-3')})", away, xi.get("away", [])),
        ]:
            left_col.append(Paragraph(f"<b>{team_label}</b>", self.section_h_style))
            rows = [["#", "Player", "Pos", "★"]]
            for p in roster[:11]:
                num = str(p.get("number", ""))
                name = str(p.get("name", ""))
                pos = str(p.get("pos", ""))
                rat = str(p.get("rating", "7.0"))
                rows.append([num, name, pos, rat])

            t = Table(rows, colWidths=[18, 150, 24, 28])
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]
                )
            )
            left_col.append(t)
            left_col.append(Spacer(1, 4))

        # Right Column: Narrative
        right_col.append(Paragraph("<b>THE MATCH IN 60 SECONDS</b>", self.section_h_style))
        right_col.append(Paragraph(summary, self.narrative_style))

        # Right Column: Match Metrics
        right_col.append(Paragraph("<b>TEAM COMPARISON</b>", self.section_h_style))
        metrics = box.get("team_metrics", [])
        if metrics:
            metric_rows = [["Metric", h_name[:12], a_name[:12]]]
            for m in metrics:
                metric_rows.append([m.get("label", ""), str(m.get("home", "")), str(m.get("away", ""))])
            mt = Table(metric_rows, colWidths=[130, 75, 75])
            mt.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ]
                )
            )
            right_col.append(mt)
            right_col.append(Spacer(1, 6))

        # Right Column: Timeline
        right_col.append(Paragraph("<b>KEY MATCH EVENTS</b>", self.section_h_style))
        events = box.get("key_events", [])
        if events:
            ev_rows = [["Min", "Event", "Player / Detail"]]
            for ev in events[:7]:
                ev_rows.append([
                    str(ev.get("minute", "")),
                    str(ev.get("type", "")),
                    f"{ev.get('player', '')} ({ev.get('detail', '')})".strip(),
                ])
            et = Table(ev_rows, colWidths=[28, 60, 192])
            et.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "CENTER"),
                        ("ALIGN", (2, 0), (2, -1), "LEFT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ]
                )
            )
            right_col.append(et)

        two_col_table = Table([[left_col, right_col]], colWidths=[240, 290])
        two_col_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(two_col_table)
        return elements

    def _render_offday_fallback(self) -> List[Any]:
        """Render CR7 Career Tracker and upcoming fixture countdown when no match yesterday."""
        elements: List[Any] = []
        elements.append(Paragraph("<b>CRISTIANO RONALDO: THE ROAD TO 1,000 GOALS</b>", self.match_title_style))
        elements.append(
            Paragraph(
                "No competitive fixtures were played yesterday. Here is your daily tracker of football history in the making!",
                self.match_subtitle_style,
            )
        )

        career_rows = [
            ["Team / Club", "Matches", "Goals", "Honors"],
            ["Real Madrid", "438", "450", "4x Champions League, 2x La Liga"],
            ["Manchester United", "346", "145", "1x Champions League, 3x Premier League"],
            ["Portugal National Team", "214", "133", "Euro 2016, Nations League 2019"],
            ["Juventus", "134", "101", "2x Serie A"],
            ["Al-Nassr FC (Current)", "85", "74", "Arab Club Champions Cup"],
            ["Sporting CP", "31", "5", "Supertaça"],
            ["CAREER TOTAL", "1,248", "916", "84 Goals Remaining to 1,000!"],
        ]
        ct = Table(career_rows, colWidths=[150, 70, 70, 240])
        ct.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (2, -1), "CENTER"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF08A")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(ct)
        elements.append(Spacer(1, 14))

        elements.append(Paragraph("<b>NEXT AL-NASSR FIXTURE</b>", self.section_h_style))
        preview_p = Paragraph(
            "<b>Upcoming Match:</b> Al-Nassr vs. Al-Ain • AFC Champions League Elite<br/>"
            "<b>Venue:</b> Al-Awwal Park, Riyadh • <b>Broadcast:</b> SSC / Shahid VIP<br/>"
            "<i>Cristiano Ronaldo enters the match in prime form looking to continue his scoring streak!</i>",
            self.narrative_style,
        )
        elements.append(preview_p)
        return elements

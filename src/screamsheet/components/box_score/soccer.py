"""International soccer box score / Match of the Day deep dive component."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import KeepInFrame

from ...base import DataProvider
from ...providers.soccer_provider import (
    AL_NASSR_TEAM_ID,
    SoccerDataProvider,
    resolve_player_list,
    resolve_team_list,
)
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
        favorite_teams: Optional[List[Any]] = None,
        favorite_players: Optional[List[Any]] = None,
        players: Optional[List[Any]] = None,
        leagues: Optional[List[Any]] = None,
        standings: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._init_favorite_teams = favorite_teams
        self._init_players = favorite_players if favorite_players is not None else players
        self._init_leagues = leagues
        self._init_standings = standings
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            is_primary_favorite=is_primary_favorite,
            fixture_id=fixture_id,
            **kwargs,
        )
        self.fixture_id: int = fixture_id or 0
        self.favorite_teams = (
            resolve_team_list(favorite_teams)
            if favorite_teams is not None
            else getattr(self.provider, "favorite_teams", None)
        )
        if self._init_players is not None:
            self.favorite_players = resolve_player_list(self._init_players)
        else:
            self.favorite_players = getattr(self.provider, "favorite_players", [])
        self.page_slot = "back"

        styles = getSampleStyleSheet()
        self.match_title_style = ParagraphStyle(
            "SoccerMatchTitle",
            parent=styles["h2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
        )
        self.match_subtitle_style = ParagraphStyle(
            "SoccerMatchSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        self.spotlight_style = ParagraphStyle(
            "SoccerSpotlight",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            alignment=TA_CENTER,
            textColor=colors.black,
        )
        self.narrative_style = ParagraphStyle(
            "SoccerNarrative",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
        self.section_h_style = ParagraphStyle(
            "SoccerSectionHeader",
            parent=styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceBefore=3,
            spaceAfter=3,
        )
        self.lineup_header_style = ParagraphStyle(
            "SoccerLineupHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=2,
        )
        self.legend_style = ParagraphStyle(
            "SoccerMatchLegend",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.black,
            alignment=TA_LEFT,
        )

    def create_default_provider(self) -> DataProvider:
        return SoccerDataProvider(
            favorite_teams=self._init_favorite_teams,
            favorite_players=self._init_players,
            leagues=self._init_leagues,
            standings=self._init_standings,
        )

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

        # 2. Player / MVP Spotlight Banner (Grayscale, no gray background fill)
        spotlight = box.get("player_spotlight") or box.get("ronaldo_spotlight")
        if spotlight and spotlight.get("featured"):
            label = spotlight.get("label", "CR7 SPOTLIGHT")
            p_name = spotlight.get("player_name", "")
            rating = spotlight.get("rating", "8.5")
            goals = spotlight.get("goals", 0)
            total = spotlight.get("career_total")
            note = spotlight.get("milestone_note", "(Road to 1,000)" if total == 916 else "")
            if label == "MAN OF THE MATCH" and p_name:
                banner_str = (
                    f"★ <b>{label}:</b> {p_name} {note}  |  Rating: <b>{rating}</b>  |  Goals: <b>{goals}</b>"
                )
            elif total is not None:
                banner_str = (
                    f"★ <b>{label}:</b> Rating: <b>{rating}</b>  |  Goals: <b>{goals}</b>  |  Career Goals: <b>{total}</b> {note}".strip()
                )
            else:
                banner_str = (
                    f"★ <b>{label}:</b> Rating: <b>{rating}</b>  |  Goals: <b>{goals}</b> {note}".strip()
                )
            spot_table = Table(
                [[Paragraph(banner_str, self.spotlight_style)]],
                colWidths=[530],
            )
            spot_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            elements.append(spot_table)
            elements.append(Spacer(1, 4))

        # 3. Two-Column Layout (Left: Summary, Right: Lineups, Stats, Timeline, Legend)
        left_col: List[Any] = []
        right_col: List[Any] = []

        # Left Column: In-Depth Narrative (200-300 words)
        left_col.append(Paragraph("<b>GAME RECAP</b>", self.section_h_style))
        for para in summary.strip().split("\n\n"):
            clean_p = para.strip().replace("\n", " ")
            if clean_p:
                left_col.append(Paragraph(clean_p, self.narrative_style))

        # Right Column: Side-by-Side Starting Formations & Lineups
        right_col.append(Paragraph("<b>STARTING FORMATIONS & RATINGS</b>", self.section_h_style))
        xi = box.get("starting_xi", {})

        home_label = Paragraph(f"<b>{h_name[:14]}</b> <i>({home.get('formation', '4-3-3')})</i>", self.lineup_header_style)
        home_rows = [["#", "Player", "P", "★"]]
        for p in xi.get("home", [])[:11]:
            home_rows.append([
                str(p.get("number", "")),
                str(p.get("name", ""))[:13],
                str(p.get("pos", ""))[:1],
                str(p.get("rating", "7.0")),
            ])
        ht = Table(home_rows, colWidths=[14, 76, 16, 22])
        ht.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        away_label = Paragraph(f"<b>{a_name[:14]}</b> <i>({away.get('formation', '4-3-3')})</i>", self.lineup_header_style)
        away_rows = [["#", "Player", "P", "★"]]
        for p in xi.get("away", [])[:11]:
            away_rows.append([
                str(p.get("number", "")),
                str(p.get("name", ""))[:13],
                str(p.get("pos", ""))[:1],
                str(p.get("rating", "7.0")),
            ])
        at = Table(away_rows, colWidths=[14, 76, 16, 22])
        at.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        lineups_master = Table(
            [[[home_label, ht], [away_label, at]]],
            colWidths=[130, 130],
        )
        lineups_master.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        right_col.append(lineups_master)
        right_col.append(Spacer(1, 4))

        # Right Column: Match Metrics
        right_col.append(Paragraph("<b>TEAM COMPARISON</b>", self.section_h_style))
        metrics = box.get("team_metrics", [])
        if metrics:
            metric_rows = [["Metric", h_name[:12], a_name[:12]]]
            for m in metrics:
                metric_rows.append([m.get("label", ""), str(m.get("home", "")), str(m.get("away", ""))])
            mt = Table(metric_rows, colWidths=[120, 70, 70])
            mt.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]
                )
            )
            right_col.append(mt)
            right_col.append(Spacer(1, 4))

        # Right Column: Timeline
        right_col.append(Paragraph("<b>KEY MATCH EVENTS</b>", self.section_h_style))
        events = box.get("key_events", [])
        if events:
            ev_rows = [["Min", "Event", "Player / Detail"]]
            for ev in events[:6]:
                ev_rows.append([
                    str(ev.get("minute", "")),
                    str(ev.get("type", "")),
                    f"{ev.get('player', '')} ({ev.get('detail', '')})".strip(),
                ])
            et = Table(ev_rows, colWidths=[26, 44, 190])
            et.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "CENTER"),
                        ("ALIGN", (2, 0), (2, -1), "LEFT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]
                )
            )
            right_col.append(et)

        # Match Stats & Rules Legend placed below the tables in right column
        legend_lines = [
            "<b>MATCH STATS & SOCCER DEFINITIONS:</b>",
            "• <b>xG (Expected Goals):</b> Probability of scoring from a chance based on distance and angle.",
            "• <b>Rating (★):</b> Match performance on a 1.0–10.0 scale (6.0 average, 8.0+ outstanding).",
            "• <b>Positions:</b> G = Goalkeeper, D = Defender, M = Midfielder, F = Forward.",
            "• <b>Status:</b> FT = Full Time (90m), AET = Extra Time (120m), PEN = Penalty Shootout.",
        ]
        legend_html = "<br/>".join(legend_lines)
        legend_t = Table([[Paragraph(legend_html, self.legend_style)]], colWidths=[258])
        legend_t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        right_col.append(Spacer(1, 6))
        right_col.append(legend_t)

        two_col_table = Table([[left_col, right_col]], colWidths=[265, 265])
        two_col_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(two_col_table)
        return elements

    def _render_offday_fallback(self) -> List[Any]:
        """Render Player/Golden Boot Tracker and upcoming fixture countdown when no match yesterday."""
        elements: List[Any] = []

        # Determine primary player (if configured) and primary team
        primary_player = self.favorite_players[0] if self.favorite_players else None
        primary_team = (
            self.favorite_teams[0]
            if self.favorite_teams
            else (AL_NASSR_TEAM_ID, "Al-Nassr")
        )
        p_team_id, p_team_name = primary_team

        headline_title = "CRISTIANO RONALDO: THE ROAD TO 1,000 GOALS"
        career_rows: List[List[str]] = [
            ["Team / Club", "Matches", "Goals", "Honors"],
            ["Real Madrid", "438", "450", "4x Champions League, 2x La Liga"],
            ["Manchester United", "346", "145", "1x Champions League, 3x Premier League"],
            ["Portugal National Team", "214", "133", "Euro 2016, Nations League 2019"],
            ["Juventus", "134", "101", "2x Serie A"],
            ["Al-Nassr FC (Current)", "85", "74", "Arab Club Champions Cup"],
            ["Sporting CP", "31", "5", "Supertaça"],
            ["CAREER TOTAL", "1,248", "916", "84 Goals Remaining to 1,000!"],
        ]

        if primary_player:
            if primary_player.get("stats_json"):
                try:
                    parsed = json.loads(primary_player["stats_json"])
                    headline_title = parsed.get("headline_title", f"{primary_player['full_name'].upper()}: CAREER TRACKER")
                    if parsed.get("rows"):
                        career_rows = [["Team / Club", "Matches", "Goals", "Honors"]] + parsed["rows"]
                except Exception:
                    headline_title = f"{primary_player['full_name'].upper()}: CAREER & SEASON TRACKER"
            else:
                headline_title = f"{primary_player['full_name'].upper()}: PLAYER SPOTLIGHT TRACKER"
                club_str = primary_player.get("current_team_name") or p_team_name
                nat_str = primary_player.get("nationality") or "National Team"
                career_rows = [
                    ["Team / Competition", "Role", "Status", "Notes"],
                    [club_str, primary_player.get("position", "Attacker"), "Active", "Primary Club"],
                    [nat_str, primary_player.get("position", "Attacker"), "Active", "International Duty"],
                ]
        elif self._init_players is not None and len(self.favorite_players) == 0:
            # Subscriber explicitly configured no favorite players -> show Golden Boot / Club Tracker
            headline_title = f"{p_team_name.upper()} & GOLDEN BOOT TRACKER"
            career_rows = [
                ["Player", "Club", "Goals", "Competition"],
                ["Erling Haaland", "Manchester City", "14", "Premier League"],
                ["Mohamed Salah", "Liverpool", "11", "Premier League"],
                ["Bukayo Saka", "Arsenal", "9", "Premier League"],
                ["Cole Palmer", "Chelsea", "9", "Premier League"],
                ["Victor Osimhen", "Galatasaray", "10", "European Leagues"],
            ]

        elements.append(Paragraph(f"<b>{headline_title}</b>", self.match_title_style))
        elements.append(
            Paragraph(
                "No competitive fixtures were played yesterday. Here is your daily tracker of football history in the making!",
                self.match_subtitle_style,
            )
        )

        ct = Table(career_rows, colWidths=[150, 70, 70, 240])
        ct.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (2, -1), "CENTER"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(ct)
        elements.append(Spacer(1, 10))

        upcoming_list = getattr(
            self.provider,
            "get_upcoming_fixtures",
            lambda tid, tname="": [{
                "matchup": f"{tname or 'Al-Nassr'} vs. Al-Ain",
                "competition": "AFC Champions League Elite",
                "venue": "Al-Awwal Park, Riyadh",
                "date": "Upcoming",
            }],
        )(p_team_id, p_team_name)
        next_fx = upcoming_list[0] if upcoming_list else {
            "matchup": f"{p_team_name} vs. Opponent",
            "competition": "League Fixture",
            "venue": "Home Stadium",
            "date": "Upcoming",
        }
        star_name = primary_player["full_name"] if primary_player else p_team_name

        elements.append(Paragraph(f"<b>NEXT {p_team_name.upper()} FIXTURE</b>", self.section_h_style))
        preview_p = Paragraph(
            f"<b>Upcoming Match:</b> {next_fx['matchup']} • {next_fx['competition']}<br/>"
            f"<b>Venue:</b> {next_fx['venue']} • <b>Date:</b> {next_fx.get('date', 'Upcoming')}<br/>"
            f"<i>{star_name} enters the match in prime form looking to continue their momentum!</i>",
            self.narrative_style,
        )
        elements.append(preview_p)
        elements.append(Spacer(1, 8))

        # Offday Terminology Legend (definitions formatted as a clean list)
        legend_lines = [
            "<b>SOCCER STATS & RULES DEFINITIONS:</b>",
            "• <b>xG (Expected Goals):</b> Probability of scoring from a chance based on shot distance and angle.",
            "• <b>Rating (★):</b> Match performance rating from 1.0 to 10.0 (6.0 average, 8.0+ outstanding).",
            "• <b>Positions:</b> G = Goalkeeper, D = Defender, M = Midfielder, F = Forward.",
            "• <b>Status:</b> FT = Full Time (90m), AET = Extra Time (120m), PEN = Penalty Shootout.",
        ]
        legend_html = "<br/>".join(legend_lines)
        legend_t = Table([[Paragraph(legend_html, self.legend_style)]], colWidths=[530])
        legend_t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(legend_t)
        return elements

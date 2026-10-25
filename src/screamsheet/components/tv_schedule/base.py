"""Extensible base TVScheduleComponent for sport broadcast schedules."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

from ...base import DataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent


class TVScheduleComponent(ScreamsheetComponent):
    """Base component for displaying upcoming broadcast TV schedules.

    Designed for extensibility so future sports (MLB, NHL, NBA, CFB, etc.) can
    subclass `TVScheduleComponent` and override `create_default_provider()` or
    `fetch_schedule_entries(target_date)`.
    """

    layout_spec = ComponentLayoutSpec(
        weight=0.25,
        full_page_only=False,
        max_on_front_page=None,
        max_per_page=None,
        component_family="tv_schedule",
    )

    def __init__(
        self,
        title: str = "Today's Broadcasts",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        schedule_items: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            schedule_items=schedule_items,
            **kwargs,
        )
        self.display_date = display_date
        self.favorite_teams: List[Tuple[int, str]] = list(favorite_teams) if favorite_teams else []
        self.schedule_items: Optional[List[str]] = list(schedule_items) if schedule_items is not None else None
        self.styles = getSampleStyleSheet()
        self.heading_style = ParagraphStyle(
            name="TVScheduleHeading",
            parent=self.styles["h4"],
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceAfter=6,
        )

    def _get_target_schedule_date(self) -> datetime:
        """Return the publication/target date for broadcast schedule lookup."""
        if self.display_date is not None:
            return self.display_date
        return self.date + timedelta(days=1)

    def fetch_schedule_entries(self, target_date: datetime) -> List[Dict[str, Any]]:
        """Fetch raw schedule dicts from the provider for `target_date`."""
        if self.provider is not None and hasattr(self.provider, "get_day_schedule"):
            return self.provider.get_day_schedule(target_date)
        return []

    def _format_schedule_lines(self, raw_games: List[Dict[str, Any]]) -> List[str]:
        """Format raw schedule entries into display strings, bolding favorite teams."""
        fav_names = [t[1].lower() for t in self.favorite_teams] if self.favorite_teams else []
        lines: List[str] = []
        for g in raw_games:
            line = g.get("schedule_line", "")
            if not line:
                away = g.get("away_team", "")
                home = g.get("home_team", "")
                time_et = g.get("time_et", "")
                b_str = g.get("broadcast", "")
                line = f"{away} @ {home}: {time_et} ({b_str})" if b_str else f"{away} @ {home}: {time_et}"
            away_lower = str(g.get("away_team", "")).lower()
            home_lower = str(g.get("home_team", "")).lower()
            is_fav = any(f in away_lower or f in home_lower for f in fav_names)
            if is_fav and not line.startswith("<b>"):
                line = f"<b>{line}</b>"
            lines.append(line)
        return lines

    def fetch_data(self) -> None:
        """Fetch and format broadcast schedule lines."""
        if self.schedule_items is not None:
            self.data = list(self.schedule_items)
            return
        target_date = self._get_target_schedule_date()
        raw_games = self.fetch_schedule_entries(target_date)
        self.data = self._format_schedule_lines(raw_games)
        if self.title == "Today's Broadcasts" and len(self.data) == 1:
            self.title = "Tonight's Broadcast"

    def render(self) -> List[Any]:
        """Render the TV broadcast schedule into ReportLab flowables."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return []

        elements: List[Any] = [
            Paragraph(f"<b>{self.title}</b>", self.heading_style),
        ]
        item_font_size = 8.5 if len(self.data) > 6 else 9.5
        item_leading = 11 if len(self.data) > 6 else 13
        item_style = ParagraphStyle(
            name="ScheduleItemText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=item_font_size,
            leading=item_leading,
            spaceAfter=2,
        )
        for item in self.data:
            elements.append(Paragraph(item, item_style))
        elements.append(Spacer(1, 8))
        return elements

    def render_markdown(self) -> str:
        """Render the TV broadcast schedule in Markdown."""
        if self.data is None:
            self.fetch_data()

        if not self.data:
            return ""

        sched_lines = [f"### {self.title}\n"]
        for item in self.data:
            clean_item = item.replace("<b>", "**").replace("</b>", "**")
            sched_lines.append(f"- {clean_item}")
        return "\n".join(sched_lines)

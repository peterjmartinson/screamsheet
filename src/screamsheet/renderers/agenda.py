"""Two-column Agenda section renderer for the Morning Briefing screamsheet."""
import logging
import re
import zoneinfo
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..providers.agenda_provider import AgendaProvider

logger = logging.getLogger(__name__)
EASTERN_TZ = zoneinfo.ZoneInfo("America/New_York")
UTC_TZ = zoneinfo.ZoneInfo("UTC")


def convert_time_to_eastern_and_duration(time_str: str) -> str:
    """
    Convert a UTC time range string from the API (e.g. '01:30 PM - 02:00 PM' or 'All Day')
    into Eastern timezone with duration, e.g. '9:30 AM (30 min)'.
    """
    if not time_str or time_str.strip().lower() == "all day":
        return "All Day"

    m = re.match(
        r"(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)",
        time_str,
        re.IGNORECASE,
    )
    if not m:
        return time_str

    h1, m1, p1, h2, m2, p2 = m.groups()
    h1, m1, h2, m2 = int(h1), int(m1), int(h2), int(m2)
    if p1.upper() == "PM" and h1 != 12:
        h1 += 12
    if p1.upper() == "AM" and h1 == 12:
        h1 = 0
    if p2.upper() == "PM" and h2 != 12:
        h2 += 12
    if p2.upper() == "AM" and h2 == 12:
        h2 = 0

    # Assume UTC baseline
    dt_utc1 = datetime(2026, 1, 1, h1, m1, tzinfo=UTC_TZ)
    dt_utc2 = datetime(2026, 1, 1, h2, m2, tzinfo=UTC_TZ)

    dt_est1 = dt_utc1.astimezone(EASTERN_TZ)
    dt_est2 = dt_utc2.astimezone(EASTERN_TZ)

    duration_mins = int((dt_utc2 - dt_utc1).total_seconds() / 60)
    if duration_mins < 0:
        duration_mins += 24 * 60

    if duration_mins == 0:
        dur_str = ""
    elif duration_mins % 60 == 0:
        hrs = duration_mins // 60
        dur_str = f" ({hrs} hr)" if hrs == 1 else f" ({hrs} hrs)"
    else:
        if duration_mins < 60:
            dur_str = f" ({duration_mins} min)"
        else:
            hrs = duration_mins // 60
            mins = duration_mins % 60
            dur_str = f" ({hrs} hr {mins} min)"

    est_hour = dt_est1.strftime("%I").lstrip("0")
    start_fmt = f"{est_hour}:{dt_est1.strftime('%M %p')}"
    return f"{start_fmt}{dur_str}"


class TwoColumnAgendaSection(Section):
    """
    Renders a two-column briefing section:
    If upcoming_days == 1:
        Left Column: Today's Agenda + Tomorrow's Agenda
        Right Column: Tasks & Projects (grouped by Board/List)
    If upcoming_days > 1:
        Left Column: Today's Agenda (Events + Tasks)
        Right Column: Next N Days (Chronological Multi-Day Schedule)
    """

    def __init__(
        self,
        date: datetime,
        multi_day_data: Optional[List[Dict[str, Any]]] = None,
        provider: Optional[AgendaProvider] = None,
        title: str = "Agenda",
        upcoming_days: int = 1,
    ):
        super().__init__(title)
        self.date = date
        self.provider = provider
        self.multi_day_data: List[Dict[str, Any]] = multi_day_data or []
        self.upcoming_days = max(1, upcoming_days)
        self._setup_styles()

    def _setup_styles(self):
        base = getSampleStyleSheet()
        self._col_h1 = ParagraphStyle(
            "ColH1",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            spaceBefore=0,
            spaceAfter=2,
            textColor=colors.HexColor("#111111"),
        )
        self._sub_hdr = ParagraphStyle(
            "ColSubHdr",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12.5,
            spaceBefore=5,
            spaceAfter=2,
            textColor=colors.HexColor("#222222"),
        )
        self._day_hdr = ParagraphStyle(
            "DayHdr",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12.5,
            spaceBefore=4.5,
            spaceAfter=1.5,
            textColor=colors.HexColor("#222222"),
        )
        self._item_style = ParagraphStyle(
            "ColItem",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#222222"),
        )
        self._accessory_style = ParagraphStyle(
            "ColAccessory",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#555555"),
        )
        self._empty_style = ParagraphStyle(
            "ColEmpty",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=11.5,
            textColor=colors.HexColor("#777777"),
        )

    def fetch_data(self):
        if not self.multi_day_data and self.provider:
            # For 1 upcoming day (Tomorrow), we need 2 days total (Today + Tomorrow).
            # For N upcoming days, we need 1 + N days total.
            num_days_to_fetch = 1 + self.upcoming_days
            self.multi_day_data = self.provider.get_multi_day_agenda(self.date, num_days=num_days_to_fetch)

    def has_content(self) -> bool:
        return True

    def _render_events_block(self, events: List[Dict[str, Any]]) -> List[Any]:
        flowables: List[Any] = []
        if not events:
            flowables.append(Paragraph("<i>No scheduled events</i>", self._empty_style))
        else:
            for ev in events:
                time_raw = ev.get("time", "")
                converted_time = convert_time_to_eastern_and_duration(time_raw)
                title = ev.get("title", "")
                accessory = ev.get("accessory", "")

                line_text = f"<b>{converted_time}</b> - {title}"
                flowables.append(Paragraph(line_text, self._item_style))

                if accessory:
                    acc_clean = accessory.replace("\n", " &bull; ")
                    flowables.append(Paragraph(f"<i>{acc_clean}</i>", self._accessory_style))
                flowables.append(Spacer(1, 1.5))
        return flowables

    def _render_tasks_block(self, sections: List[Dict[str, Any]]) -> List[Any]:
        flowables: List[Any] = []
        for sec in sections:
            tasks = sec.get("tasks", [])
            if not tasks:
                continue
            sec_title = sec.get("title", "Tasks")

            # Group tasks by assignee preserving order of appearance
            grouped_tasks: Dict[str, List[Dict[str, Any]]] = {}
            for task in tasks:
                assignee = (task.get("assignee") or "").strip()
                if assignee not in grouped_tasks:
                    grouped_tasks[assignee] = []
                grouped_tasks[assignee].append(task)

            for assignee, t_list in grouped_tasks.items():
                if assignee:
                    hdr_title = f"{sec_title} &mdash; {assignee}"
                else:
                    hdr_title = sec_title

                flowables.append(Paragraph(f"<b>{hdr_title}</b>", self._sub_hdr))
                flowables.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#888888"), spaceAfter=2))

                for task in t_list:
                    t_title = task.get("title", "")
                    due = task.get("due", "")
                    accessory = task.get("accessory", "")

                    task_line = t_title
                    if due:
                        task_line += f" <font color='#555555'><i>(Due: {due})</i></font>"
                    if accessory:
                        task_line += f" <font color='#8b0000'><b>({accessory})</b></font>"

                    flowables.append(Paragraph(task_line, self._item_style))
                    flowables.append(Spacer(1, 1))

                flowables.append(Spacer(1, 3))
        return flowables

    def _build_left_column_flowables(self, today_data: Dict[str, Any], tomorrow_data: Optional[Dict[str, Any]] = None) -> List[Any]:
        flowables: List[Any] = []
        flowables.append(Paragraph("<b>TODAY'S AGENDA</b>", self._col_h1))
        flowables.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#222222"), spaceAfter=3))

        events = today_data.get("agenda", [])
        flowables.extend(self._render_events_block(events))

        if self.upcoming_days == 1:
            # Show Tomorrow in left column right below Today
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph("<b>TOMORROW'S AGENDA</b>", self._col_h1))
            flowables.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#222222"), spaceAfter=3))
            tomorrow_events = (tomorrow_data or {}).get("agenda", [])
            flowables.extend(self._render_events_block(tomorrow_events))
        else:
            # Multi-day mode: Tasks go in left column under Today
            flowables.append(Spacer(1, 4))
            sections = today_data.get("sections", [])
            flowables.extend(self._render_tasks_block(sections))

        return flowables

    def _build_right_column_flowables(self, upcoming_days_data: List[Dict[str, Any]], today_data: Optional[Dict[str, Any]] = None) -> List[Any]:
        flowables: List[Any] = []

        if self.upcoming_days == 1:
            # Tomorrow-only mode: Right column is dedicated to Board / List sections directly
            sections = (today_data or {}).get("sections", [])
            if not sections or not any(s.get("tasks") for s in sections):
                flowables.append(Paragraph("<i>No active tasks</i>", self._empty_style))
            else:
                flowables.extend(self._render_tasks_block(sections))
        else:
            # Multi-day mode: Right column is Next N Days
            title = f"NEXT {len(upcoming_days_data)} DAYS" if len(upcoming_days_data) != 5 else "NEXT 5 DAYS"
            flowables.append(Paragraph(f"<b>{title}</b>", self._col_h1))
            flowables.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#222222"), spaceAfter=3))

            for day_dict in upcoming_days_data:
                d_str = day_dict.get("date", "")
                try:
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                    day_name = d_obj.strftime("%A")
                    date_fmt = d_obj.strftime("%m/%d")
                    heading_str = f"{day_name}, {date_fmt}"
                except Exception:
                    heading_str = d_str

                flowables.append(Paragraph(f"<b>{heading_str}</b>", self._day_hdr))

                events = day_dict.get("agenda", [])
                if not events:
                    flowables.append(Paragraph("<i>No scheduled events</i>", self._empty_style))
                else:
                    for ev in events:
                        time_raw = ev.get("time", "")
                        converted_time = convert_time_to_eastern_and_duration(time_raw)
                        title = ev.get("title", "")
                        accessory = ev.get("accessory", "")

                        if accessory:
                            acc_short = accessory.split("\n")[0]
                            acc_part = f" <font color='#555555'>({acc_short})</font>"
                        else:
                            acc_part = ""

                        line_text = f"<b>{converted_time}</b> - {title}{acc_part}"
                        flowables.append(Paragraph(line_text, self._item_style))
                        flowables.append(Spacer(1, 1))

                flowables.append(Spacer(1, 3))

        return flowables

    def render(self) -> List[Any]:
        if not self.multi_day_data and self.provider:
            self.fetch_data()

        today_data = self.multi_day_data[0] if self.multi_day_data else {}
        tomorrow_data = self.multi_day_data[1] if len(self.multi_day_data) > 1 else {}
        upcoming_data = self.multi_day_data[1:] if len(self.multi_day_data) > 1 else []

        left_flowables = self._build_left_column_flowables(today_data, tomorrow_data=tomorrow_data)
        right_flowables = self._build_right_column_flowables(upcoming_data, today_data=today_data)

        # 2-column table layout: page width is 612, margin 36 on each side -> 540 pt usable width
        # Left col: 260 pt, Gap: 20 pt, Right col: 260 pt
        col_table = Table([[left_flowables, "", right_flowables]], colWidths=[260, 20, 260])
        col_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [col_table]

    def render_markdown(self) -> str:
        if not self.multi_day_data and self.provider:
            self.fetch_data()

        today_data = self.multi_day_data[0] if self.multi_day_data else {}
        lines = []
        lines.append("## TODAY'S AGENDA\n")
        events = today_data.get("agenda", [])
        if not events:
            lines.append("_No scheduled events_\n")
        else:
            for ev in events:
                time_raw = ev.get("time", "")
                c_time = convert_time_to_eastern_and_duration(time_raw)
                title = ev.get("title", "")
                accessory = ev.get("accessory", "")
                lines.append(f"{c_time} - {title}")
                if accessory:
                    acc_clean = accessory.replace("\n", " • ")
                    lines.append(f"_{acc_clean}_")
            lines.append("")

        if self.upcoming_days == 1:
            tomorrow_data = self.multi_day_data[1] if len(self.multi_day_data) > 1 else {}
            lines.append("## TOMORROW'S AGENDA\n")
            t_evs = tomorrow_data.get("agenda", [])
            if not t_evs:
                lines.append("_No scheduled events_\n")
            else:
                for ev in t_evs:
                    time_raw = ev.get("time", "")
                    c_time = convert_time_to_eastern_and_duration(time_raw)
                    title = ev.get("title", "")
                    accessory = ev.get("accessory", "")
                    lines.append(f"{c_time} - {title}")
                    if accessory:
                        acc_clean = accessory.replace("\n", " • ")
                        lines.append(f"_{acc_clean}_")
                lines.append("")

            lines.append("---\n")
            for sec in today_data.get("sections", []):
                sec_title = sec.get("title", "Tasks")
                grouped_tasks: Dict[str, List[Dict[str, Any]]] = {}
                for task in sec.get("tasks", []):
                    assignee = (task.get("assignee") or "").strip()
                    if assignee not in grouped_tasks:
                        grouped_tasks[assignee] = []
                    grouped_tasks[assignee].append(task)

                for assignee, t_list in grouped_tasks.items():
                    sub_title = f"{sec_title} — {assignee}" if assignee else sec_title
                    lines.append(f"### {sub_title}\n")
                    for task in t_list:
                        t_title = task.get("title", "")
                        lines.append(f"{t_title}")
                    lines.append("")
        else:
            for sec in today_data.get("sections", []):
                sec_title = sec.get("title", "Tasks")
                grouped_tasks: Dict[str, List[Dict[str, Any]]] = {}
                for task in sec.get("tasks", []):
                    assignee = (task.get("assignee") or "").strip()
                    if assignee not in grouped_tasks:
                        grouped_tasks[assignee] = []
                    grouped_tasks[assignee].append(task)

                for assignee, t_list in grouped_tasks.items():
                    sub_title = f"{sec_title} — {assignee}" if assignee else sec_title
                    lines.append(f"### {sub_title}\n")
                    for task in t_list:
                        t_title = task.get("title", "")
                        lines.append(f"{t_title}")
                    lines.append("")

            lines.append("---\n")
            upcoming_data = self.multi_day_data[1:] if len(self.multi_day_data) > 1 else []
            lines.append(f"## NEXT {len(upcoming_data)} DAYS\n")
            for day_dict in upcoming_data:
                d_str = day_dict.get("date", "")
                try:
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                    heading_str = f"{d_obj.strftime('%A')}, {d_obj.strftime('%m/%d')}"
                except Exception:
                    heading_str = d_str

                lines.append(f"### {heading_str}\n")
                evs = day_dict.get("agenda", [])
                if not evs:
                    lines.append("_No scheduled events_\n")
                else:
                    for ev in evs:
                        time_raw = ev.get("time", "")
                        c_time = convert_time_to_eastern_and_duration(time_raw)
                        title = ev.get("title", "")
                        accessory = ev.get("accessory", "")
                        acc_str = f" ({accessory.replace(chr(10), ' ')})" if accessory else ""
                        lines.append(f"{c_time} - {title}{acc_str}")
                    lines.append("")

        return "\n".join(lines)

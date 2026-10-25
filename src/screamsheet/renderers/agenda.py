"""Two-column Agenda renderer — backward-compatible wrapper around AgendaComponent."""
from __future__ import annotations

from ..components.briefing.agenda import (
    AgendaComponent,
    classify_task_due_status,
    convert_accessory_to_eastern,
    convert_time_to_eastern_and_duration,
    extract_task_label,
    format_due_date,
    group_and_sort_tasks_by_due,
    parse_due_date,
    sort_agenda_events,
)

TwoColumnAgendaSection = AgendaComponent

__all__ = [
    "AgendaComponent",
    "TwoColumnAgendaSection",
    "classify_task_due_status",
    "convert_accessory_to_eastern",
    "convert_time_to_eastern_and_duration",
    "extract_task_label",
    "format_due_date",
    "group_and_sort_tasks_by_due",
    "parse_due_date",
    "sort_agenda_events",
]

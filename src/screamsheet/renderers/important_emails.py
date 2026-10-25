"""Important emails renderer — backward-compatible wrapper around ImportantEmailsComponent."""
from __future__ import annotations

from ..components.briefing.important_emails import ImportantEmailsComponent
from ..llm.summary import EmailImportantSummarizer

ImportantEmailsSection = ImportantEmailsComponent

__all__ = [
    "EmailImportantSummarizer",
    "ImportantEmailsComponent",
    "ImportantEmailsSection",
]

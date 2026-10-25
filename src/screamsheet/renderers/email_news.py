"""Email news renderer — backward-compatible wrapper around EmailNewsComponent."""
from __future__ import annotations

from ..components.briefing.email_news import EmailNewsComponent
from ..llm.summary import EmailNewsSummarizer

EmailNewsSection = EmailNewsComponent

__all__ = [
    "EmailNewsComponent",
    "EmailNewsSection",
    "EmailNewsSummarizer",
]

"""Structured result returned by every screamsheet generation call.

Both the personal-use entry point and the subscriber service entry point
return ``GenerationResult`` objects so that callers can inspect layout
quality and error details without parsing the PDF.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class GenerationResult:
    """The outcome of generating a single screamsheet PDF.

    Attributes:
        pdf_path:     Absolute path to the written PDF file.
        sheet_type:   Short identifier for the sheet type, e.g. ``"nhl"``,
                      ``"mlb"``, ``"presidential"``.
        issues:       Human-readable descriptions of any layout or data
                      problems encountered.  Empty list when clean.
        layout_clean: ``True`` if the output is exactly two pages with no
                      warnings.  Derived from ``issues`` — do not set
                      directly.
    """

    pdf_path: str
    sheet_type: str
    issues: List[str] = field(default_factory=list)

    @property
    def layout_clean(self) -> bool:
        """Return True if no issues were recorded."""
        return len(self.issues) == 0

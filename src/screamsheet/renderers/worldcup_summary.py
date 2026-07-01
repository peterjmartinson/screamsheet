"""Helpers for World Cup LLM payload generation."""
from __future__ import annotations

import json
from typing import Any, Dict, List


def minify_summary_payload(events: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
    """Return a compact JSON string from events + stats for LLM consumption."""
    return json.dumps({"events": events, "stats": stats}, separators=(",", ":"))

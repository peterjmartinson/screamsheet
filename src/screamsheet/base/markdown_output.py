"""Markdown output and 7-day TTL cache management for screamsheets."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("screamsheet.markdown")

DEFAULT_MARKDOWN_DIR = Path("markdown_output")


def get_markdown_dir() -> Path:
    """Return the resolved Path for the markdown_output directory."""
    md_dir = DEFAULT_MARKDOWN_DIR
    md_dir.mkdir(parents=True, exist_ok=True)
    return md_dir


def resolve_markdown_path(pdf_path: str, md_dir: Optional[Path] = None) -> Path:
    """Derive the corresponding .md file path from a PDF output filename.

    Example:
        'Files/MLB_scores_20260819.pdf' -> 'markdown_output/MLB_scores_20260819.md'
    """
    target_dir = md_dir or get_markdown_dir()
    stem = Path(pdf_path).stem
    return target_dir / f"{stem}.md"


def is_markdown_cached(file_path: Path, ttl_days: int = 7) -> bool:
    """Check if a generated markdown file exists and is within the 7-day TTL."""
    if not file_path.exists() or not file_path.is_file():
        return False
    try:
        mtime = file_path.stat().st_mtime
        age_seconds = time.time() - mtime
        return age_seconds < (ttl_days * 86400)
    except Exception:
        return False


def purge_expired_markdown(md_dir: Optional[Path] = None, ttl_days: int = 7) -> int:
    """Delete markdown files in markdown_output that are older than ttl_days.

    Returns:
        Number of purged markdown files.
    """
    target_dir = md_dir or DEFAULT_MARKDOWN_DIR
    if not target_dir.exists():
        return 0

    now = time.time()
    ttl_seconds = ttl_days * 86400
    purged = 0

    for item in target_dir.glob("*.md"):
        try:
            mtime = item.stat().st_mtime
            if (now - mtime) >= ttl_seconds:
                item.unlink(missing_ok=True)
                purged += 1
                logger.debug("Purged expired markdown: %s", item.name)
        except Exception as exc:
            logger.warning("Failed to check/purge markdown file %s: %s", item, exc)

    logger.info("Purged %d expired markdown files from %s", purged, target_dir)
    return purged

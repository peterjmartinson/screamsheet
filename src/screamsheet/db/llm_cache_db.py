"""SQLite storage and management for cached LLM responses."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger("screamsheet.llm.cache")


class _LLMCache(_Base):
    __tablename__ = "llm_cache"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    cache_key      = Column(String(64), nullable=False, unique=True, index=True)
    topic_slug     = Column(String(200), nullable=False)
    summarizer     = Column(String(60), nullable=False)
    llm_provider   = Column(String(20), nullable=False)
    model_name     = Column(String(60), nullable=False)
    prompt_preview = Column(String(1000))
    response_text  = Column(String, nullable=False)
    word_count     = Column(Integer, default=0)
    created_at     = Column(String(30), nullable=False)
    expires_at     = Column(String(30), nullable=False, index=True)


def _get_engine(db_path: Optional[Path] = None):
    """Return a SQLAlchemy engine, ensuring llm_cache table exists."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_cache_db(db_path: Optional[Path] = None):
    """Create the llm_cache table if it does not exist."""
    return _get_engine(db_path)


def get_cached_response(
    cache_key: str,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Retrieve non-expired cached LLM response for *cache_key*.

    Returns:
        The cached response string, or None if not found or expired.
    """
    engine = _get_engine(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        row = (
            session.query(_LLMCache)
            .filter(_LLMCache.cache_key == cache_key)
            .first()
        )
        if row:
            if row.expires_at > now_iso:
                logger.debug("Cache hit for key %s (topic: %s)", cache_key[:8], row.topic_slug)
                return row.response_text
            else:
                logger.debug("Cache expired for key %s (topic: %s)", cache_key[:8], row.topic_slug)
                session.delete(row)
                session.commit()
    return None


def save_cached_response(
    cache_key: str,
    topic_slug: str,
    summarizer: str,
    llm_provider: str,
    model_name: str,
    prompt_preview: str,
    response_text: str,
    ttl_days: int = 7,
    db_path: Optional[Path] = None,
) -> None:
    """Store an LLM response in the cache with a defined TTL.

    Args:
        cache_key:      Deterministic SHA-256 hash.
        topic_slug:     Human-readable topic slug.
        summarizer:     Name of summarizer class.
        llm_provider:   Provider label (e.g. "gemini", "grok").
        model_name:     Model identifier string.
        prompt_preview: Truncated prompt string.
        response_text:  Full generated response string.
        ttl_days:       Expiration in days (default: 7).
        db_path:        Optional database path.
    """
    engine = _get_engine(db_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    expires_iso = (now + timedelta(days=ttl_days)).isoformat()
    word_count = len(response_text.split())

    with Session(engine) as session:
        # Delete existing entry if any
        session.execute(
            text("DELETE FROM llm_cache WHERE cache_key = :k"), {"k": cache_key}
        )
        session.add(
            _LLMCache(
                cache_key=cache_key,
                topic_slug=topic_slug[:200],
                summarizer=summarizer[:60],
                llm_provider=llm_provider[:20],
                model_name=model_name[:60],
                prompt_preview=(prompt_preview or "")[:1000],
                response_text=response_text,
                word_count=word_count,
                created_at=now_iso,
                expires_at=expires_iso,
            )
        )
        session.commit()
    logger.debug("Cached LLM response for %s (%d words, TTL=%dd)", topic_slug, word_count, ttl_days)


def purge_expired_cache(db_path: Optional[Path] = None) -> int:
    """Delete all expired entries from llm_cache.

    Returns:
        Number of purged rows.
    """
    engine = _get_engine(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        result = session.execute(
            text("DELETE FROM llm_cache WHERE expires_at <= :now"), {"now": now_iso}
        )
        count = result.rowcount
        session.commit()
    logger.info("Purged %d expired LLM cache entries", count)
    return count


def clear_cache(
    db_path: Optional[Path] = None,
    topic_filter: Optional[str] = None,
) -> int:
    """Delete all cached entries, optionally filtered by topic substring.

    Returns:
        Number of deleted rows.
    """
    engine = _get_engine(db_path)
    with Session(engine) as session:
        if topic_filter:
            result = session.execute(
                text("DELETE FROM llm_cache WHERE topic_slug LIKE :f"),
                {"f": f"%{topic_filter}%"},
            )
        else:
            result = session.execute(text("DELETE FROM llm_cache"))
        count = result.rowcount
        session.commit()
    logger.info("Cleared %d LLM cache entries", count)
    return count


def get_cache_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return summary statistics for the LLM cache."""
    engine = _get_engine(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        total = session.query(_LLMCache).count()
        active = session.query(_LLMCache).filter(_LLMCache.expires_at > now_iso).count()
        expired = total - active
        word_sum = (
            session.query(text("SUM(word_count) FROM llm_cache WHERE expires_at > :now"))
            .params(now=now_iso)
            .scalar()
            or 0
        )
    return {
        "total_entries": total,
        "active_entries": active,
        "expired_entries": expired,
        "active_cached_words": int(word_sum),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect and manage Screamsheet LLM cache.")
    parser.add_argument("--stats", action="store_true", help="Display cache statistics")
    parser.add_argument("--purge", action="store_true", help="Purge expired entries")
    parser.add_argument("--clear", action="store_true", help="Clear all entries")
    args = parser.parse_args()

    if args.purge:
        count = purge_expired_cache()
        print(f"Purged {count} expired cache entries.")
    elif args.clear:
        count = clear_cache()
        print(f"Cleared {count} cache entries.")
    else:
        stats = get_cache_stats()
        print(f"LLM Cache Stats (Database: {get_db_path()}):")
        print(f"  Active entries: {stats['active_entries']}")
        print(f"  Expired entries: {stats['expired_entries']}")
        print(f"  Total cached words: {stats['active_cached_words']}")

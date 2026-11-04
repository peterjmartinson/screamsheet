"""SQLite cache for slow-moving or large weather/teleconnection payloads.

Stores JSON-serialized datasets in the shared screamsheet SQLite database with:
  - fresh TTL (within which cached data is returned without a network request)
  - stale fallback TTL (within which cached data can be returned with ``stale=True``
    if the remote source is unreachable)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import Column, String, Text, create_engine, text
from sqlalchemy.orm import Session

from ._nhl_db_shared import _Base, get_db_path

logger = logging.getLogger("screamsheet.weather_patterns.cache")


class _WeatherDataCache(_Base):
    __tablename__ = "weather_data_cache"
    cache_key     = Column(String(120), primary_key=True)
    source_url    = Column(String(500), nullable=False)
    payload_json  = Column(Text, nullable=False)
    fetched_at    = Column(String(40), nullable=False)
    fresh_until   = Column(String(40), nullable=False)
    stale_until   = Column(String(40), nullable=False)


@dataclass
class CachedFetchResult:
    """Result returned by :func:`fetch_with_cache` / :func:`weather_cache_fetch`."""
    data: Any
    fetched_at: str
    from_cache: bool = False
    is_stale: bool = False
    age_hours: float = 0.0
    error: Optional[str] = None

    @property
    def payload(self) -> Any:
        return self.data

    @property
    def retrieved_at(self) -> str:
        return self.fetched_at


def _get_engine(db_path: Optional[Path] = None):
    """Return a SQLAlchemy engine, ensuring weather_data_cache table exists."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    _Base.metadata.create_all(engine)
    return engine


def init_weather_cache_db(db_path: Optional[Path] = None):
    """Ensure the weather_data_cache table exists."""
    return _get_engine(db_path)


def get_weather_cache(
    cache_key: str,
    allow_stale: bool = False,
    db_path: Optional[Path] = None,
) -> Optional[CachedFetchResult]:
    """Retrieve a cached weather dataset by key.

    Args:
        cache_key:   Unique identifier for the dataset.
        allow_stale: If True, returns entries past ``fresh_until`` (up to ``stale_until``)
                     with ``is_stale=True``.
        db_path:     Optional SQLite DB path override.

    Returns:
        :class:`CachedFetchResult` if a valid entry exists, else ``None``.
    """
    try:
        engine = _get_engine(db_path)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with Session(engine) as session:
            row = (
                session.query(_WeatherDataCache)
                .filter(_WeatherDataCache.cache_key == cache_key)
                .first()
            )
            if not row:
                return None

            try:
                fetched_dt = datetime.fromisoformat(row.fetched_at)
                if fetched_dt.tzinfo is None:
                    fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
                age_hours = max(0.0, (now - fetched_dt).total_seconds() / 3600.0)
            except Exception:
                age_hours = 0.0

            if row.fresh_until > now_iso:
                payload = json.loads(row.payload_json)
                return CachedFetchResult(
                    data=payload,
                    fetched_at=row.fetched_at,
                    from_cache=True,
                    is_stale=False,
                    age_hours=round(age_hours, 2),
                )

            if allow_stale and row.stale_until > now_iso:
                payload = json.loads(row.payload_json)
                logger.warning(
                    "Using STALE cached weather data for '%s' (age=%.1fh, fetched=%s)",
                    cache_key,
                    age_hours,
                    row.fetched_at,
                )
                return CachedFetchResult(
                    data=payload,
                    fetched_at=row.fetched_at,
                    from_cache=True,
                    is_stale=True,
                    age_hours=round(age_hours, 2),
                )
    except Exception as exc:
        logger.debug("Weather cache lookup failed for %s: %s", cache_key, exc)
    return None


def save_weather_cache(
    cache_key: str,
    source_url: str,
    data: Any,
    fresh_hours: float = 12.0,
    max_stale_hours: float = 168.0,
    db_path: Optional[Path] = None,
) -> str:
    """Save a JSON-serializable dataset into ``weather_data_cache``.

    Returns:
        ISO-8601 UTC timestamp of when the entry was saved.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    fresh_iso = (now + timedelta(hours=fresh_hours)).isoformat()
    stale_iso = (now + timedelta(hours=max(fresh_hours, max_stale_hours))).isoformat()

    try:
        payload_json = json.dumps(data, default=str)
        engine = _get_engine(db_path)
        with Session(engine) as session:
            session.execute(
                text("DELETE FROM weather_data_cache WHERE cache_key = :k"),
                {"k": cache_key},
            )
            session.add(
                _WeatherDataCache(
                    cache_key=cache_key[:120],
                    source_url=source_url[:500],
                    payload_json=payload_json,
                    fetched_at=now_iso,
                    fresh_until=fresh_iso,
                    stale_until=stale_iso,
                )
            )
            session.commit()
    except Exception as exc:
        logger.warning("Failed to save weather cache for %s: %s", cache_key, exc)
    return now_iso


def fetch_with_cache(
    cache_key: str,
    source_url: str,
    fetcher: Callable[[], Any],
    fresh_hours: float = 12.0,
    max_stale_hours: float = 168.0,
    use_cache: bool = True,
    refresh_cache: bool = False,
    db_path: Optional[Path] = None,
) -> CachedFetchResult:
    """Execute ``fetcher()`` with SQLite cache-first and stale-on-error fallback.

    1. If ``use_cache`` and not ``refresh_cache``, checks for a fresh cached entry.
    2. Otherwise calls ``fetcher()``. If ``fetcher()`` returns non-None data, saves to cache.
    3. If ``fetcher()`` raises an exception or returns None, falls back to stale cache
       (up to ``max_stale_hours``) and marks ``is_stale=True``.
    """
    if use_cache and not refresh_cache:
        hit = get_weather_cache(cache_key, allow_stale=False, db_path=db_path)
        if hit is not None:
            return hit

    error_msg: Optional[str] = None
    try:
        fresh_data = fetcher()
        if fresh_data is not None:
            now_iso = datetime.now(timezone.utc).isoformat()
            if use_cache:
                now_iso = save_weather_cache(
                    cache_key=cache_key,
                    source_url=source_url,
                    data=fresh_data,
                    fresh_hours=fresh_hours,
                    max_stale_hours=max_stale_hours,
                    db_path=db_path,
                )
            return CachedFetchResult(
                data=fresh_data,
                fetched_at=now_iso,
                from_cache=False,
                is_stale=False,
                age_hours=0.0,
            )
        error_msg = f"Empty response from {source_url}"
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("Live fetch failed for %s (%s): %s", cache_key, source_url, exc)

    if use_cache:
        stale_hit = get_weather_cache(cache_key, allow_stale=True, db_path=db_path)
        if stale_hit is not None:
            stale_hit.error = error_msg
            return stale_hit

    return CachedFetchResult(
        data=None,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        from_cache=False,
        is_stale=False,
        age_hours=0.0,
        error=error_msg or "Unavailable",
    )


def weather_cache_fetch(
    cache_key: str,
    fetcher: Callable[[], Any],
    source_name: str = "",
    source_url: str = "",
    fresh_ttl_seconds: Optional[float] = None,
    stale_ttl_seconds: Optional[float] = None,
    fresh_hours: float = 12.0,
    max_stale_hours: float = 168.0,
    use_cache: bool = True,
    refresh: bool = False,
    refresh_cache: bool = False,
    db_path: Optional[Path] = None,
) -> CachedFetchResult:
    """Convenience wrapper accepting either seconds or hours TTLs."""
    fh = (fresh_ttl_seconds / 3600.0) if fresh_ttl_seconds is not None else fresh_hours
    sh = (stale_ttl_seconds / 3600.0) if stale_ttl_seconds is not None else max_stale_hours
    return fetch_with_cache(
        cache_key=cache_key,
        source_url=source_url or source_name or cache_key,
        fetcher=fetcher,
        fresh_hours=fh,
        max_stale_hours=sh,
        use_cache=use_cache,
        refresh_cache=refresh or refresh_cache,
        db_path=db_path,
    )


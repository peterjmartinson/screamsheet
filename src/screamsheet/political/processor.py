"""Political news scoring, deduplication, and storage pipeline.

This module is Step 2 of the presidential screamsheet pipeline.  It
consumes normalized entry dicts produced by
:mod:`screamsheet.providers.political_news_provider` (Step 1) and
outputs filtered, scored, and deduplicated candidates ready for the
render step.

Entry dict shape (input and output)::

    {
        'title':     str,
        'link':      str,
        'published': datetime,   # UTC-aware
        'summary':   str,
        'source':    str,
        'score':     int,        # added by this module
    }

Stand-alone usage::

    python -m screamsheet.political.processor

"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword weights  — single place for tuning
# ---------------------------------------------------------------------------

# Multi-word phrases MUST appear before their component single words so the
# scanning loop can give them priority without double-counting.
KEYWORD_WEIGHTS: Dict[str, int] = {
    # Core presidential / White House
    "white house":       8,
    "executive order":   7,
    "trump":            10,
    "president":         5,
    # Domestic policy hot-buttons
    "tariff":            6,
    "tariffs":           6,
    "doge":              6,
    "immigration":       5,
    "border":            4,
    "inflation":         4,
    "federal reserve":   5,
    "congress":          4,
    "senate":            4,
    "house of representatives": 4,
    # Key international actors
    "xi jinping":        7,
    "xi":                5,
    "putin":             5,
    "zelensky":          5,
    "netanyahu":         5,
    "modi":              4,
    "macron":            4,
    "kim jong":          6,
    # Geopolitical topics
    "ukraine":           5,
    "russia":            4,
    "china":             4,
    "nato":              5,
    "israel":            4,
    "gaza":              4,
    "taiwan":            5,
    "north korea":       6,
    # Trade / foreign policy
    "diplomacy":         5,
    "sanctions":         5,
    "trade war":         6,
    "trade deal":        5,
    # Key Washington institutions
    "supreme court":     5,
    "department of justice": 5,
    "doj":               4,
    "fbi":               4,
    "cia":               4,
    "pentagon":          4,
    # Elon Musk / tech power
    "musk":              5,
    "elon":              4,
    "spacex":            3,
    "tesla":             3,
}


# ---------------------------------------------------------------------------
# NewsScorer
# ---------------------------------------------------------------------------

class NewsScorer:
    """Score news entries by keyword relevance.

    Weights are defined at module level in :data:`KEYWORD_WEIGHTS` so they
    can be tuned in one place without touching the class.
    """

    def score(self, entry: Dict) -> int:
        """Return a relevance score for *entry*.

        The title and summary are concatenated, lower-cased, and scanned
        once for every keyword.  Multi-word phrases are checked before their
        component single words to avoid double-counting (the ordering in
        :data:`KEYWORD_WEIGHTS` ensures this).

        Returns 0 for entries with missing/empty title and summary.
        """
        text = " ".join([
            (entry.get("title") or ""),
            (entry.get("summary") or ""),
        ]).lower()

        if not text.strip():
            return 0

        total = 0
        already_matched: List[str] = []

        for keyword, weight in KEYWORD_WEIGHTS.items():
            # Skip single-word keyword if a phrase containing it already matched
            if " " not in keyword:
                if any(keyword in phrase for phrase in already_matched):
                    continue
            if keyword in text:
                total += weight
                already_matched.append(keyword)

        return total


# ---------------------------------------------------------------------------
# NewsDeduplicator
# ---------------------------------------------------------------------------

class NewsDeduplicator:
    """Remove duplicate entries from a list of scored news dicts.

    Two-pass strategy:

    1. **Exact URL**: normalise each link (strip scheme, ``www.``, query
       string, fragment, trailing ``/``) and keep the first-seen entry per
       normalised URL.
    2. **Fuzzy title**: compare remaining titles pairwise with
       :class:`difflib.SequenceMatcher`.  When the ratio exceeds *threshold*
       (default 0.80) the entry with the lower ``score`` is dropped; ties
       keep the earlier entry (stable ordering is preserved throughout).

    No third-party libraries are required — ``difflib`` is stdlib.
    """

    def __init__(self, fuzzy_threshold: float = 0.80):
        self.fuzzy_threshold = fuzzy_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate(self, entries: List[Dict]) -> List[Dict]:
        """Return a deduplicated copy of *entries* (original list unchanged)."""
        after_url = self._dedup_by_url(entries)
        return self._dedup_by_title(after_url)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalize_url(self, link: str) -> str:
        """Return a canonical URL string for deduplication comparison."""
        if not link:
            return ""
        try:
            parsed = urlparse(link.strip())
            host = (parsed.netloc or "").lower().removeprefix("www.")
            path = parsed.path.rstrip("/")
            return urlunparse(("", host, path, "", "", ""))
        except Exception:  # noqa: BLE001
            return link.strip().lower()

    def _dedup_by_url(self, entries: List[Dict]) -> List[Dict]:
        seen: set = set()
        result = []
        for entry in entries:
            norm = self._normalize_url(entry.get("link") or "")
            if norm and norm in seen:
                logger.debug("NewsDeduplicator: URL dup dropped: %s", entry.get("title"))
                continue
            if norm:
                seen.add(norm)
            result.append(entry)
        return result

    def _dedup_by_title(self, entries: List[Dict]) -> List[Dict]:
        """Remove near-duplicate titles, keeping the higher-scored entry."""
        # Work with indices so we can mark entries for removal
        keep = [True] * len(entries)

        for i in range(len(entries)):
            if not keep[i]:
                continue
            title_i = (entries[i].get("title") or "").lower()
            for j in range(i + 1, len(entries)):
                if not keep[j]:
                    continue
                title_j = (entries[j].get("title") or "").lower()
                ratio = SequenceMatcher(None, title_i, title_j).ratio()
                if ratio >= self.fuzzy_threshold:
                    score_i = entries[i].get("score", 0)
                    score_j = entries[j].get("score", 0)
                    if score_j > score_i:
                        # j is better; drop i and stop comparing i
                        logger.debug(
                            "NewsDeduplicator: title dup — keeping '%s' over '%s' (scores %d vs %d)",
                            entries[j].get("title"), entries[i].get("title"),
                            score_j, score_i,
                        )
                        keep[i] = False
                        break
                    else:
                        logger.debug(
                            "NewsDeduplicator: title dup — keeping '%s' over '%s' (scores %d vs %d)",
                            entries[i].get("title"), entries[j].get("title"),
                            score_i, score_j,
                        )
                        keep[j] = False

        return [entry for entry, ok in zip(entries, keep) if ok]


# ---------------------------------------------------------------------------
# PoliticalNewsProcessor
# ---------------------------------------------------------------------------

class PoliticalNewsProcessor:
    """Orchestrate the filter → score → sort → deduplicate → store pipeline.

    Typical usage::

        from screamsheet.providers.political_news_provider import (
            PoliticalRSSProvider, WhiteHouseProvider,
        )
        from screamsheet.political import PoliticalNewsProcessor

        entries = PoliticalRSSProvider().get_articles()
        entries += WhiteHouseProvider().get_articles()

        processor = PoliticalNewsProcessor()
        candidates = processor.process(entries)
        processor.save_to_json(candidates, "logfiles/political_candidates.json")
    """

    def __init__(
        self,
        hours: int = 48,
        fuzzy_threshold: float = 0.80,
    ):
        self.hours = hours
        self._scorer = NewsScorer()
        self._deduplicator = NewsDeduplicator(fuzzy_threshold=fuzzy_threshold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, entries: List[Dict]) -> List[Dict]:
        """Filter, score, sort, and deduplicate *entries*.

        Steps:
        1. Re-apply time filter (defensive; providers already filter, but
           entries may originate from cache or other sources).
        2. Score each entry and attach a ``score`` key.
        3. Sort descending by score.
        4. Deduplicate (URL exact-match, then fuzzy title).

        Args:
            entries: Normalized entry dicts from the fetch step.

        Returns:
            Processed list with a ``score`` key added to each entry.
        """
        recent = [e for e in entries if self._within_window(e.get("published"))]
        logger.info("PoliticalNewsProcessor: %d entries after time filter", len(recent))

        scored = []
        for entry in recent:
            e = dict(entry)
            e["score"] = self._scorer.score(e)
            scored.append(e)

        scored.sort(key=lambda e: e["score"], reverse=True)

        result = self._deduplicator.deduplicate(scored)
        logger.info("PoliticalNewsProcessor: %d entries after dedup", len(result))
        return result

    def save_to_json(self, entries: List[Dict], path: str) -> None:
        """Serialize *entries* to a JSON file at *path*.

        ``datetime`` objects are converted to ISO-8601 strings.  The parent
        directory is created if it does not exist.
        """
        def _serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, default=_serializer, indent=2, ensure_ascii=False)
        logger.info("PoliticalNewsProcessor: wrote %d entries to %s", len(entries), out_path)

    def save_to_sqlite(self, entries: List[Dict], path: str) -> None:
        """Upsert *entries* into a SQLite database at *path*.

        Table ``political_news`` is created if it does not exist.  The
        ``link`` column is used as the natural key; rows are replaced on
        conflict so scores and fetched_at timestamps stay current.

        Requires SQLAlchemy (already in the project dependencies).
        """
        from sqlalchemy import (
            Column, DateTime, Integer, String, Text, create_engine, text,
        )
        from sqlalchemy.orm import DeclarativeBase, Session

        class _Base(DeclarativeBase):
            pass

        class _PoliticalNews(_Base):
            __tablename__ = "political_news"
            id        = Column(Integer, primary_key=True, autoincrement=True)
            title     = Column(String(500), nullable=False)
            link      = Column(String(1000), unique=True, nullable=False)
            published = Column(DateTime(timezone=True))
            summary   = Column(Text, default="")
            source    = Column(String(200), default="")
            score     = Column(Integer, default=0)
            fetched_at = Column(DateTime(timezone=True))

        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        _Base.metadata.create_all(engine)

        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            for entry in entries:
                link = (entry.get("link") or "").strip()
                if not link:
                    logger.warning("PoliticalNewsProcessor: skipping entry without link: %s", entry.get("title"))
                    continue
                # Upsert: delete existing row then insert (SQLite-compatible)
                session.execute(text("DELETE FROM political_news WHERE link = :link"), {"link": link})
                session.add(_PoliticalNews(
                    title      = (entry.get("title") or "")[:500],
                    link       = link[:1000],
                    published  = entry.get("published"),
                    summary    = (entry.get("summary") or ""),
                    source     = (entry.get("source") or "")[:200],
                    score      = entry.get("score", 0),
                    fetched_at = now,
                ))
            session.commit()
        logger.info("PoliticalNewsProcessor: upserted %d rows into %s", len(entries), db_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _within_window(self, dt: Optional[datetime]) -> bool:
        """Return True if *dt* is within the configured hour window."""
        if dt is None:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=self.hours)


# ---------------------------------------------------------------------------
# Stand-alone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Make sure the package is importable when run directly
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from screamsheet.providers.political_news_provider import (
        PoliticalRSSProvider,
        WhiteHouseProvider,
    )

    rss_entries  = PoliticalRSSProvider().get_articles()
    wh_entries   = WhiteHouseProvider().get_articles()
    all_entries  = rss_entries + wh_entries

    processor    = PoliticalNewsProcessor()
    candidates   = processor.process(all_entries)

    timestamp    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path     = Path("logfiles") / f"political_candidates_{timestamp}.json"
    processor.save_to_json(candidates, str(out_path))

    print(f"\nTop 10 candidates (of {len(candidates)} total):")
    print("-" * 60)
    for entry in candidates[:10]:
        print(f"  [{entry['score']:>3}] {entry['source']}: {entry['title'][:70]}")

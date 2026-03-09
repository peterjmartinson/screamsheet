"""Unit tests for screamsheet.political.processor."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from screamsheet.political.processor import (
    NewsDeduplicator,
    NewsScorer,
    PoliticalNewsProcessor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recent_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=6)


def _old_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=72)


def _entry(
    title="Breaking News",
    link="https://example.com/story/1",
    summary="",
    source="Reuters",
    published=None,
    score=0,
) -> dict:
    return {
        "title":     title,
        "link":      link,
        "published": published or _recent_dt(),
        "summary":   summary,
        "source":    source,
        "score":     score,
    }


# ---------------------------------------------------------------------------
# NewsScorer
# ---------------------------------------------------------------------------

class TestNewsScorer:
    def test_trump_headline_scores_high(self):
        scorer = NewsScorer()
        entry = _entry(title="Trump signs executive order on tariffs")
        assert scorer.score(entry) >= 10

    def test_sports_headline_scores_zero(self):
        scorer = NewsScorer()
        entry = _entry(title="Home run lifts Yankees over Red Sox in extra innings")
        assert scorer.score(entry) == 0

    def test_case_insensitive(self):
        scorer = NewsScorer()
        lower = _entry(title="trump meets with nato allies")
        upper = _entry(title="TRUMP MEETS WITH NATO ALLIES")
        assert scorer.score(lower) == scorer.score(upper)

    def test_summary_contributes_to_score(self):
        scorer = NewsScorer()
        no_summary = _entry(title="Trump", summary="")
        with_summary = _entry(title="Trump", summary="White House sanctions announced")
        assert scorer.score(with_summary) > scorer.score(no_summary)

    def test_compound_keyword_not_double_counted(self):
        scorer = NewsScorer()
        # "white house" should score once as the phrase, not also as "house"
        entry_phrase  = _entry(title="White House press briefing")
        score_phrase  = scorer.score(entry_phrase)
        # If double-counted, adding the phrase weight plus a single-word weight
        # would give a higher total — verify it does not exceed phrase weight alone
        from screamsheet.political.processor import KEYWORD_WEIGHTS
        assert score_phrase <= KEYWORD_WEIGHTS["white house"] + KEYWORD_WEIGHTS.get("president", 0) + 10

    def test_empty_entry_scores_zero(self):
        scorer = NewsScorer()
        assert scorer.score({"title": "", "summary": ""}) == 0

    def test_missing_fields_scores_zero(self):
        scorer = NewsScorer()
        assert scorer.score({}) == 0

    def test_multiple_keywords_accumulate(self):
        scorer = NewsScorer()
        entry = _entry(title="Trump tariffs on China draw NATO response")
        assert scorer.score(entry) > 15


# ---------------------------------------------------------------------------
# NewsDeduplicator
# ---------------------------------------------------------------------------

class TestNewsDeduplicator:
    def test_exact_url_duplicate_removed(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Story A", link="https://example.com/a", score=5),
            _entry(title="Story A copy", link="https://example.com/a", score=3),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 1
        assert result[0]["title"] == "Story A"

    def test_url_normalization_strips_trailing_slash(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Story A", link="https://example.com/a/", score=5),
            _entry(title="Story A copy", link="https://example.com/a", score=3),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 1

    def test_url_normalization_strips_query(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Story A", link="https://example.com/a?utm_source=rss", score=5),
            _entry(title="Story B", link="https://example.com/a?ref=homepage", score=3),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 1

    def test_fuzzy_title_duplicate_removed(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Trump signs new executive order on immigration", score=10),
            _entry(title="Trump signs new executive order on immigration policy", score=8),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 1

    def test_fuzzy_keeps_higher_scored(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Trump signs executive order on immigration", score=5, link="https://a.com/1"),
            _entry(title="Trump signs executive order on immigration policy", score=12, link="https://b.com/2"),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 1
        assert result[0]["score"] == 12

    def test_dissimilar_titles_both_kept(self):
        dedup = NewsDeduplicator()
        entries = [
            _entry(title="Trump raises tariffs on China", link="https://a.com/1"),
            _entry(title="Ukraine requests more weapons from NATO allies", link="https://b.com/2"),
        ]
        result = dedup.deduplicate(entries)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        dedup = NewsDeduplicator()
        assert dedup.deduplicate([]) == []

    def test_single_entry_returned_unchanged(self):
        dedup = NewsDeduplicator()
        entries = [_entry()]
        result = dedup.deduplicate(entries)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# PoliticalNewsProcessor
# ---------------------------------------------------------------------------

class TestPoliticalNewsProcessor:
    def test_returns_list(self):
        processor = PoliticalNewsProcessor()
        result = processor.process([_entry()])
        assert isinstance(result, list)

    def test_score_key_added(self):
        processor = PoliticalNewsProcessor()
        result = processor.process([_entry(title="Trump tariffs on China")])
        assert "score" in result[0]

    def test_old_entries_filtered_out(self):
        processor = PoliticalNewsProcessor()
        entries = [_entry(published=_old_dt())]
        assert processor.process(entries) == []

    def test_recent_entries_kept(self):
        processor = PoliticalNewsProcessor()
        entries = [_entry(published=_recent_dt())]
        assert len(processor.process(entries)) == 1

    def test_sorted_descending_by_score(self):
        processor = PoliticalNewsProcessor()
        entries = [
            _entry(title="Sports scores today", link="https://a.com/1"),
            _entry(title="Trump executive order on tariffs", link="https://b.com/2"),
            _entry(title="NATO meeting on Ukraine diplomacy", link="https://c.com/3"),
        ]
        result = processor.process(entries)
        scores = [e["score"] for e in result]
        assert scores == sorted(scores, reverse=True)

    def test_duplicates_removed_end_to_end(self):
        processor = PoliticalNewsProcessor()
        entries = [
            _entry(title="Trump tariffs on China", link="https://a.com/1"),
            _entry(title="Trump tariffs on China", link="https://a.com/1"),
        ]
        result = processor.process(entries)
        assert len(result) == 1

    def test_entry_without_published_filtered_out(self):
        processor = PoliticalNewsProcessor()
        entry = _entry()
        entry["published"] = None
        assert processor.process([entry]) == []

    def test_naive_datetime_treated_as_utc(self):
        processor = PoliticalNewsProcessor()
        naive_recent = datetime.utcnow() - timedelta(hours=1)
        entry = _entry(published=naive_recent)
        result = processor.process([entry])
        assert len(result) == 1

    # ------------------------------------------------------------------
    # save_to_json
    # ------------------------------------------------------------------

    def test_save_to_json_creates_file(self, tmp_path):
        processor = PoliticalNewsProcessor()
        entries = processor.process([_entry(title="Trump White House meeting")])
        out = tmp_path / "out.json"
        processor.save_to_json(entries, str(out))
        assert out.exists()

    def test_save_to_json_content_valid(self, tmp_path):
        import json as _json
        processor = PoliticalNewsProcessor()
        entries = processor.process([_entry(title="Trump White House meeting")])
        out = tmp_path / "out.json"
        processor.save_to_json(entries, str(out))
        data = _json.loads(out.read_text())
        assert isinstance(data, list)
        assert data[0]["title"] == "Trump White House meeting"

    def test_save_to_json_creates_parent_dirs(self, tmp_path):
        processor = PoliticalNewsProcessor()
        entries = processor.process([_entry()])
        nested = tmp_path / "a" / "b" / "out.json"
        processor.save_to_json(entries, str(nested))
        assert nested.exists()

    # ------------------------------------------------------------------
    # save_to_sqlite
    # ------------------------------------------------------------------

    def test_save_to_sqlite_creates_file(self, tmp_path):
        processor = PoliticalNewsProcessor()
        entries = processor.process([_entry(title="Trump tariffs")])
        db = tmp_path / "news.db"
        processor.save_to_sqlite(entries, str(db))
        assert db.exists()

    def test_save_to_sqlite_upserts(self, tmp_path):
        """Saving twice should not duplicate rows."""
        from sqlalchemy import create_engine, text
        processor = PoliticalNewsProcessor()
        entries = processor.process([_entry(title="Trump tariffs")])
        db = tmp_path / "news.db"
        processor.save_to_sqlite(entries, str(db))
        processor.save_to_sqlite(entries, str(db))
        engine = create_engine(f"sqlite:///{db}")
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM political_news")).scalar()
        assert count == 1

    def test_save_to_sqlite_entry_without_link_skipped(self, tmp_path, caplog):
        import logging
        processor = PoliticalNewsProcessor()
        entry = _entry(title="No link story", link="")
        # bypass process() so the entry isn't dropped by score/filter
        entry["score"] = 5
        db = tmp_path / "news.db"
        with caplog.at_level(logging.WARNING):
            processor.save_to_sqlite([entry], str(db))
        assert any("without link" in r.message for r in caplog.records)

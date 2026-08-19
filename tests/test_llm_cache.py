"""Unit tests for SQLite-backed LLM response caching and TTL management."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.runnables import RunnableLambda

from screamsheet.db.llm_cache_db import (
    clear_cache,
    get_cache_stats,
    get_cached_response,
    init_cache_db,
    purge_expired_cache,
    save_cached_response,
)
from screamsheet.llm.base import BaseGameSummaryGenerator
from screamsheet.llm.config import LLMConfig


@pytest.fixture
def test_db(tmp_path):
    path = tmp_path / "test_llm_cache.db"
    init_cache_db(path)
    return path


# ---------------------------------------------------------------------------
# Database layer tests
# ---------------------------------------------------------------------------

class TestLLMCacheDB:
    def test_init_creates_table(self, test_db):
        import sqlalchemy as sa

        engine = init_cache_db(test_db)
        tables = sa.inspect(engine).get_table_names()
        assert "llm_cache" in tables

    def test_save_and_retrieve_response(self, test_db):
        save_cached_response(
            cache_key="key123",
            topic_slug="20260819_mlb_BOS_at_MIL",
            summarizer="MLBGameSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="Sample prompt...",
            response_text="The Brewers defeated the Red Sox in a thrilling game.",
            ttl_days=7,
            db_path=test_db,
        )
        res = get_cached_response("key123", db_path=test_db)
        assert res == "The Brewers defeated the Red Sox in a thrilling game."

    def test_missing_key_returns_none(self, test_db):
        res = get_cached_response("nonexistent", db_path=test_db)
        assert res is None

    def test_expired_entry_returns_none(self, test_db):
        save_cached_response(
            cache_key="expkey",
            topic_slug="expired_topic",
            summarizer="NewsSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="Prompt",
            response_text="Old news",
            ttl_days=-1,  # Expired yesterday
            db_path=test_db,
        )
        res = get_cached_response("expkey", db_path=test_db)
        assert res is None

    def test_purge_expired_cache(self, test_db):
        # 1 active, 2 expired
        save_cached_response(
            cache_key="act1",
            topic_slug="active_1",
            summarizer="NewsSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Active text",
            ttl_days=7,
            db_path=test_db,
        )
        save_cached_response(
            cache_key="exp1",
            topic_slug="expired_1",
            summarizer="NewsSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Exp 1",
            ttl_days=-2,
            db_path=test_db,
        )
        save_cached_response(
            cache_key="exp2",
            topic_slug="expired_2",
            summarizer="NewsSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Exp 2",
            ttl_days=-1,
            db_path=test_db,
        )
        purged = purge_expired_cache(test_db)
        assert purged == 2
        assert get_cached_response("act1", db_path=test_db) == "Active text"

    def test_clear_cache(self, test_db):
        save_cached_response(
            cache_key="k1",
            topic_slug="mlb_topic",
            summarizer="MLBGameSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Text 1",
            db_path=test_db,
        )
        save_cached_response(
            cache_key="k2",
            topic_slug="nhl_topic",
            summarizer="NHLGameSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Text 2",
            db_path=test_db,
        )
        # Filtered clear
        clear_cache(test_db, topic_filter="mlb")
        assert get_cached_response("k1", db_path=test_db) is None
        assert get_cached_response("k2", db_path=test_db) == "Text 2"

        # Full clear
        clear_cache(test_db)
        assert get_cached_response("k2", db_path=test_db) is None

    def test_get_cache_stats(self, test_db):
        save_cached_response(
            cache_key="k1",
            topic_slug="t1",
            summarizer="MLBGameSummarizer",
            llm_provider="gemini",
            model_name="gemini-2.5-flash",
            prompt_preview="",
            response_text="Five words in this response",
            ttl_days=7,
            db_path=test_db,
        )
        stats = get_cache_stats(test_db)
        assert stats["total_entries"] == 1
        assert stats["active_entries"] == 1
        assert stats["active_cached_words"] == 5


# ---------------------------------------------------------------------------
# BaseGameSummaryGenerator caching integration tests
# ---------------------------------------------------------------------------

class DummySummarizer(BaseGameSummaryGenerator):
    def _build_llm_prompt(self, data):
        return f"Summarize game between {data.get('away_team')} and {data.get('home_team')}"


class DummyFanRantSummarizer(BaseGameSummaryGenerator):
    def _build_llm_prompt(self, data):
        return f"Angry fan rant for {data.get('losing_team')}"


class TestLLMGeneratorCaching:
    def test_caching_deduplicates_llm_calls(self, test_db, monkeypatch):
        monkeypatch.setenv("SCREAMSHEET_DB", str(test_db))
        summarizer = DummySummarizer(config=LLMConfig(gemini_model="test-model"))

        call_count = 0

        def fake_llm_func(prompt_val):
            nonlocal call_count
            call_count += 1
            return "Brewers win 5-4 on a walk-off homer."

        fake_runnable = RunnableLambda(fake_llm_func)
        summarizer.llm_gemini = fake_runnable

        data = {
            "date": "2026-08-19",
            "away_team": "Boston Red Sox",
            "home_team": "Milwaukee Brewers",
            "score": "4-5",
        }

        # Subscriber 1 generates summary -> LLM called
        res1 = summarizer.generate_summary("gemini", data=data)
        assert res1 == "Brewers win 5-4 on a walk-off homer."
        assert call_count == 1

        # Subscriber 2 requests the same summary -> Cache HIT, no second LLM call!
        res2 = summarizer.generate_summary("gemini", data=data)
        assert res2 == "Brewers win 5-4 on a walk-off homer."
        assert call_count == 1  # call count did NOT increase!

    def test_no_cache_flag_bypasses_cache(self, test_db, monkeypatch):
        monkeypatch.setenv("SCREAMSHEET_DB", str(test_db))
        summarizer = DummySummarizer(config=LLMConfig(gemini_model="test-model"))

        call_count = 0

        def fake_llm_func(prompt_val):
            nonlocal call_count
            call_count += 1
            return f"Call {call_count}"

        summarizer.llm_gemini = RunnableLambda(fake_llm_func)

        data = {"date": "2026-08-19", "away_team": "BOS", "home_team": "MIL"}

        res1 = summarizer.generate_summary("gemini", data=data, use_cache=False)
        assert res1 == "Call 1"
        assert call_count == 1

        # With use_cache=False, second call still invokes LLM
        res2 = summarizer.generate_summary("gemini", data=data, use_cache=False)
        assert res2 == "Call 2"
        assert call_count == 2

    def test_refresh_cache_flag_overwrites_cache(self, test_db, monkeypatch):
        monkeypatch.setenv("SCREAMSHEET_DB", str(test_db))
        summarizer = DummySummarizer(config=LLMConfig(gemini_model="test-model"))

        call_count = 0

        def fake_llm_func(prompt_val):
            nonlocal call_count
            call_count += 1
            return f"Generated {call_count}"

        summarizer.llm_gemini = RunnableLambda(fake_llm_func)

        data = {"date": "2026-08-19", "away_team": "BOS", "home_team": "MIL"}

        res1 = summarizer.generate_summary("gemini", data=data)
        assert res1 == "Generated 1"
        assert call_count == 1

        # With refresh_cache=True, LLM is called and cache is refreshed
        res2 = summarizer.generate_summary("gemini", data=data, refresh_cache=True)
        assert res2 == "Generated 2"
        assert call_count == 2

        # Subsequent regular call gets the refreshed value from cache without calling LLM
        res3 = summarizer.generate_summary("gemini", data=data)
        assert res3 == "Generated 2"
        assert call_count == 2

    def test_different_summarizers_do_not_collide(self, test_db, monkeypatch):
        monkeypatch.setenv("SCREAMSHEET_DB", str(test_db))
        neutral_summarizer = DummySummarizer(config=LLMConfig(gemini_model="test-model"))
        rant_summarizer = DummyFanRantSummarizer(config=LLMConfig(gemini_model="test-model"))

        neutral_summarizer.llm_gemini = RunnableLambda(lambda x: "Neutral game summary")
        rant_summarizer.llm_gemini = RunnableLambda(lambda x: "Angry fan rant")

        data = {
            "date": "2026-08-19",
            "away_team": "Boston Red Sox",
            "home_team": "Milwaukee Brewers",
            "losing_team": "Boston Red Sox",
        }

        res1 = neutral_summarizer.generate_summary("gemini", data=data)
        assert res1 == "Neutral game summary"

        res2 = rant_summarizer.generate_summary("gemini", data=data)
        assert res2 == "Angry fan rant"

        # Check that both cached distinctly
        stats = get_cache_stats(test_db)
        assert stats["active_entries"] == 2

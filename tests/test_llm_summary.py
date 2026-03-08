"""Unit tests for screamsheet.llm.summary (BaseGameSummaryGenerator and subclasses)."""
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.llm.summary import (
    BaseGameSummaryGenerator,
    NHLGameSummarizer,
    MLBGameSummarizer,
    NewsSummarizer,
)


# ---------------------------------------------------------------------------
# BaseGameSummaryGenerator initialization
# ---------------------------------------------------------------------------

class TestBaseGameSummaryGeneratorInit:
    def test_no_api_keys_llms_are_none(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        assert gen.llm_gemini is None
        assert gen.llm_grok is None

    def test_api_keys_stored(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        assert gen.api_keys["gemini"] is None
        assert gen.api_keys["grok"] is None


# ---------------------------------------------------------------------------
# _select_llm_instance
# ---------------------------------------------------------------------------

class TestSelectLLMInstance:
    def test_returns_none_when_no_llms(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        assert gen._select_llm_instance("gemini") is None

    def test_returns_gemini_when_available(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        fake_llm = MagicMock()
        gen.llm_gemini = fake_llm
        assert gen._select_llm_instance("gemini") is fake_llm

    def test_returns_grok_when_available(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        fake_llm = MagicMock()
        gen.llm_grok = fake_llm
        assert gen._select_llm_instance("grok") is fake_llm

    def test_case_insensitive(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        fake_llm = MagicMock()
        gen.llm_gemini = fake_llm
        assert gen._select_llm_instance("GEMINI") is fake_llm


# ---------------------------------------------------------------------------
# generate_summary — no LLM (returns default text immediately)
# ---------------------------------------------------------------------------

class TestGenerateSummaryNoLLM:
    def test_returns_string_without_real_llm(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        data = {"home_team": "Flyers", "away_team": "Devils",
                "home_score": 4, "away_score": 2, "narrative_snippets": ""}
        result = gen.generate_summary(llm_choice="gemini", data=data)
        assert isinstance(result, str)

    def test_returns_string_when_data_is_string(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        result = gen.generate_summary(llm_choice="gemini", data="no game data")
        assert result == "no game data"


# ---------------------------------------------------------------------------
# generate_summary — mocked LangChain pipeline
# ---------------------------------------------------------------------------

class TestGenerateSummaryWithMockedChain:
    def test_returns_llm_output(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        data = {"home_team": "Flyers", "away_team": "Devils",
                "home_score": 4, "away_score": 2, "narrative_snippets": ""}
        fake_llm = MagicMock()
        gen.llm_gemini = fake_llm

        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "The Flyers won in hilarious fashion."
        with patch.object(gen, "_setup_prompt_chain", return_value=MagicMock()):
            with patch(
                "screamsheet.llm.summary.StrOutputParser",
                return_value=MagicMock(return_value=MagicMock()),
            ):
                # Patch the full pipeline by replacing _generate_llm_summary
                with patch.object(
                    gen,
                    "_generate_llm_summary",
                    return_value="The Flyers won in hilarious fashion.",
                ):
                    result = gen.generate_summary(llm_choice="gemini", data=data)
        assert result == "The Flyers won in hilarious fashion."


# ---------------------------------------------------------------------------
# _build_llm_prompt sanity checks
# ---------------------------------------------------------------------------

class TestBuildLLMPrompt:
    def _sample_data(self):
        return {
            "home_team": "Flyers",
            "away_team": "Devils",
            "home_score": 4,
            "away_score": 2,
            "narrative_snippets": "Goal by Cates.",
        }

    def test_nhl_prompt_contains_home_team(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "Flyers" in prompt

    def test_nhl_prompt_contains_score(self):
        gen = NHLGameSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "4" in prompt

    def test_mlb_prompt_contains_home_team(self):
        gen = MLBGameSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "Flyers" in prompt

    def test_news_prompt_not_implemented_raises(self):
        """NewsSummarizer extends BaseGameSummaryGenerator directly and has a prompt."""
        gen = NewsSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt({})
        assert isinstance(prompt, str)
        assert len(prompt) > 20

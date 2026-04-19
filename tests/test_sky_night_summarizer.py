"""Unit tests for SkyNightSummarizer."""
from unittest.mock import patch

from screamsheet.llm.summarizers import SkyNightSummarizer


class TestSkyNightSummarizerInit:
    def test_instantiable_without_api_keys(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        assert gen.llm_gemini is None
        assert gen.llm_grok is None


class TestSkyNightSummarizerPrompt:
    def _sample_data(self) -> dict:
        return {
            "planets": "Venus in Taurus, Mars in Gemini, Jupiter in Gemini",
            "moon_phase": "Waxing Crescent (35% illuminated)",
            "highlights": "Venus is in Taurus.\nMars is in Gemini.",
            "location": "Bryn Mawr, PA",
            "date": "April 18, 2026",
        }

    def test_returns_string_without_real_llm(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        result = gen.generate_summary(llm_choice="gemini", data=self._sample_data())
        assert isinstance(result, str)

    def test_prompt_contains_planet_data(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "Venus in Taurus" in prompt

    def test_prompt_contains_moon_phase(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "Waxing Crescent" in prompt

    def test_prompt_contains_location(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "Bryn Mawr" in prompt

    def test_prompt_contains_date(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        prompt = gen._build_llm_prompt(self._sample_data())
        assert "April 18, 2026" in prompt

    def test_generate_returns_mocked_summary(self):
        gen = SkyNightSummarizer(gemini_api_key=None, grok_api_key=None)
        with patch.object(
            gen, "_generate_llm_summary", return_value="Venus dazzles tonight!"
        ):
            result = gen.generate_summary(llm_choice="gemini", data=self._sample_data())
        assert result == "Venus dazzles tonight!"

"""LLM model/API configuration for screamsheet summarizers.

All model names, endpoint URLs, sampling temperatures, and other
provider-level knobs live here so they can be version-controlled and
swapped without touching prompt or business logic.

Usage::

    from screamsheet.llm.config import DEFAULT_LLM_CONFIG, LLMConfig

    # Use defaults everywhere
    summarizer = NHLGameSummarizer(config=DEFAULT_LLM_CONFIG)

    # Override for a one-off experiment
    experimental = LLMConfig(gemini_model="gemini-2.0-pro", gemini_temperature=0.7)
    summarizer = NHLGameSummarizer(config=experimental)
"""
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """All tuneable LLM settings in one version-controlled place."""

    # --- Gemini (Google) -----------------------------------------------
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.3

    # --- Grok (xAI, OpenAI-compatible endpoint) -----------------------
    grok_model: str = "grok-4-fast"
    grok_base_url: str = "https://api.x.ai/v1"
    grok_temperature: float = 0.3
    grok_extra_headers: dict = field(default_factory=lambda: {"x-search-mode": "auto"})

    # --- Fallback / debug ---------------------------------------------
    # Returned when no LLM key is configured (keeps tests and dry-runs clean)
    default_text: str = "howdy, folks.  test text here"


# Module-level singleton — import this in all production code paths.
DEFAULT_LLM_CONFIG = LLMConfig()

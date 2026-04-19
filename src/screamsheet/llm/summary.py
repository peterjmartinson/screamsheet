"""Re-export shim — preserved for backward-compatible import paths.

All implementation has moved to:
    llm/config.py       — LLMConfig dataclass
    llm/base.py         — BaseGameSummaryGenerator
    llm/summarizers.py  — NHLGameSummarizer, MLBGameSummarizer, NewsSummarizer
    llm/prompts/*.txt   — versioned prompt templates

Existing callers such as::

    from ..llm.summary import NHLGameSummarizer

continue to work unchanged.
"""
# isort: skip_file
from .config import LLMConfig, DEFAULT_LLM_CONFIG  # noqa: F401
from .base import BaseGameSummaryGenerator, ExtractedInfo, PromptChainInput  # noqa: F401
from .summarizers import NHLGameSummarizer, MLBGameSummarizer, NewsSummarizer, SkyNightSummarizer  # noqa: F401

__all__ = [
    "LLMConfig",
    "DEFAULT_LLM_CONFIG",
    "BaseGameSummaryGenerator",
    "ExtractedInfo",
    "PromptChainInput",
    "NHLGameSummarizer",
    "MLBGameSummarizer",
    "NewsSummarizer",
]

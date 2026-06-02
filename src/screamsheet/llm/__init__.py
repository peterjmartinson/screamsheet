"""LLM summarization package for screamsheet.

Public API — prefer importing from here rather than from sub-modules::

    from screamsheet.llm import NHLGameSummarizer, LLMConfig
"""
from .config import LLMConfig, DEFAULT_LLM_CONFIG
from .base import BaseGameSummaryGenerator, ExtractedInfo, PromptChainInput
from .summarizers import (
    NHLGameSummarizer,
    MLBGameSummarizer,
    NewsSummarizer,
    PoliticalNewsSummarizer,
    SkyNightSummarizer,
    NBAGameSummarizer,
    NBAFanRantSummarizer,
    FrenchMLBA2Summarizer,
    FrenchMLBB2C1Summarizer,
    FrenchMLBLexiconSummarizer,
)

__all__ = [
    "LLMConfig",
    "DEFAULT_LLM_CONFIG",
    "BaseGameSummaryGenerator",
    "ExtractedInfo",
    "PromptChainInput",
    "NHLGameSummarizer",
    "MLBGameSummarizer",
    "NewsSummarizer",
    "PoliticalNewsSummarizer",
    "SkyNightSummarizer",
    "NBAGameSummarizer",
    "NBAFanRantSummarizer",
    "FrenchMLBA2Summarizer",
    "FrenchMLBB2C1Summarizer",
    "FrenchMLBLexiconSummarizer",
]

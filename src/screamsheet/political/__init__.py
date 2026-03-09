"""Political news processing pipeline (scoring, deduplication, storage)."""
from .processor import NewsScorer, NewsDeduplicator, PoliticalNewsProcessor

__all__ = [
    "NewsScorer",
    "NewsDeduplicator",
    "PoliticalNewsProcessor",
]

"""Political news pipeline: scoring, deduplication, storage, and PDF render."""
from .processor import NewsScorer, NewsDeduplicator, PoliticalNewsProcessor
from .renderer import PresidentialSection
from .screamsheet import PresidentialScreamsheet

__all__ = [
    "NewsScorer",
    "NewsDeduplicator",
    "PoliticalNewsProcessor",
    "PresidentialSection",
    "PresidentialScreamsheet",
]

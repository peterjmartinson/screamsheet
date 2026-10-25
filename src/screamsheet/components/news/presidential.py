"""Presidential / Political News component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ...base import DataProvider
from ...llm.summarizers import PoliticalNewsSummarizer
from ...providers.political_news_provider import PoliticalNewsProvider
from ..registry import ComponentRegistry
from .base import NewsStoryComponent


@ComponentRegistry.register("presidential_news")
class PresidentialNewsComponent(NewsStoryComponent):
    """Self-contained Presidential / Political News component."""

    component_type = "presidential_news"

    def __init__(
        self,
        title: str = "Top Political Stories",
        provider: Optional[DataProvider] = None,
        max_articles: int = 4,
        start_index: int = 0,
        summarizer_class: Any = PoliticalNewsSummarizer,
        date: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        self._initial_max_articles = max_articles if max_articles is not None else 4
        super().__init__(
            title=title,
            provider=provider,
            max_articles=self._initial_max_articles,
            start_index=start_index,
            summarizer_class=summarizer_class,
            date=date,
            **kwargs,
        )

    def create_default_provider(self) -> DataProvider:
        return PoliticalNewsProvider(max_articles=max(self._initial_max_articles, 8))

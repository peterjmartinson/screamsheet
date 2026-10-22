"""Base abstractions for self-contained screamsheet components."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional

from ..base.section import Section


@dataclass(frozen=True)
class ComponentLayoutSpec:
    """Layout metadata describing how a component fits and stacks on a page.

    Attributes:
        weight: Approximate fraction of a full page's vertical height occupied by
            this component (e.g., 0.18 for weather/TV schedule, 0.25 for game scores,
            0.48 for standings, 1.0 for box score).
        component_family: Logical family name used for per-page family limits
            (e.g., "standings", "game_scores", "box_score", "news", "weather", "tv_schedule").
        max_on_front_page: Optional cap on how many components of this
            ``component_family`` may appear on Page 1 (e.g., 1 for standings).
        max_per_page: Optional cap on how many components of this
            ``component_family`` may appear on Page 2+ (e.g., 2 for standings).
        full_page_only: True if this component requires an entire page to itself
            (or all remaining space on an empty page).
        renders_own_header: True if the component draws its own section banner/title
            inside ``render()``.
        preferred_top_divider: True if a horizontal divider or extra spacing should
            precede this component when stacked below another component on the same page.
    """

    weight: float = 0.45
    component_family: str = "generic"
    max_on_front_page: Optional[int] = None
    max_per_page: Optional[int] = None
    full_page_only: bool = False
    renders_own_header: bool = False
    preferred_top_divider: bool = False

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"ComponentLayoutSpec.weight must be > 0, got {self.weight}")
        if self.max_on_front_page is not None and self.max_on_front_page < 0:
            raise ValueError(
                f"ComponentLayoutSpec.max_on_front_page must be >= 0, got {self.max_on_front_page}"
            )
        if self.max_per_page is not None and self.max_per_page < 1:
            raise ValueError(
                f"ComponentLayoutSpec.max_per_page must be >= 1, got {self.max_per_page}"
            )


class ScreamsheetComponent(Section, ABC):
    """Abstract base class for all self-contained screamsheet components.

    Inherits from :class:`~screamsheet.base.section.Section` so components can be
    used directly inside any existing :class:`~screamsheet.base.screamsheet.BaseScreamsheet`
    during and after the migration.
    """

    component_key: str = ""
    component_type: str = ""
    DEFAULT_LAYOUT_SPEC: ComponentLayoutSpec = ComponentLayoutSpec()
    layout_spec: ComponentLayoutSpec = DEFAULT_LAYOUT_SPEC

    def __init__(
        self,
        title: str = "",
        provider: Optional[Any] = None,
        date: Optional[datetime] = None,
        page_slot: str = "front",
        layout_spec: Optional[ComponentLayoutSpec] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(title)
        self.page_slot = page_slot
        cls_spec = getattr(self.__class__, "layout_spec", None)
        if cls_spec is None or cls_spec == ScreamsheetComponent.DEFAULT_LAYOUT_SPEC:
            cls_spec = getattr(self.__class__, "DEFAULT_LAYOUT_SPEC", ScreamsheetComponent.DEFAULT_LAYOUT_SPEC)
        self.layout_spec: ComponentLayoutSpec = layout_spec or cls_spec
        self.date: datetime = date if date is not None else (datetime.now() - timedelta(days=1))
        self.provider: Optional[Any] = (
            provider
            if provider is not None
            else (self.create_default_provider() or self._create_provider())
        )
        self.extra_config = kwargs

    def create_default_provider(self) -> Optional[Any]:
        """Instantiate the default data provider when none is passed explicitly."""
        return None

    def _create_provider(self) -> Optional[Any]:
        """Backward-compatible hook for instantiating the default data provider."""
        return None

    @abstractmethod
    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        """Render the component into ReportLab flowables.

        Args:
            styles: Optional ReportLab style sheet override.
            max_width: Optional maximum printable width in points (default 540pt).

        Returns:
            List of ReportLab flowable objects.
        """
        pass

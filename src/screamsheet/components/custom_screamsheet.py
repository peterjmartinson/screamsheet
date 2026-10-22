"""CustomScreamsheet composer for building multi-page screamsheets from arbitrary components."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import HRFlowable, Paragraph, Spacer

from ..base.screamsheet import BaseScreamsheet
from ..base.section import Section
from .base import ComponentLayoutSpec, ScreamsheetComponent

logger = logging.getLogger(__name__)


class CustomScreamsheet(BaseScreamsheet):
    """Composes an ordered list of :class:`ScreamsheetComponent` instances across 1..N pages.

    Layout rules:
      - Preserves the exact component order specified by the caller / subscriber YAML.
      - Page 1 (front page) reserves vertical budget for the masthead
        (``FRONT_PAGE_CAPACITY = 0.85``) and enforces ``layout_spec.max_on_front_page``
        per ``component_family`` (for ``"standings"``, at most **1** standings chart on Page 1).
      - Page 2+ (back and subsequent pages) have ``SUBSEQUENT_PAGE_CAPACITY = 1.0``
        and enforce ``layout_spec.max_per_page`` per ``component_family``
        (for ``"standings"``, up to **2** standings charts per page).
      - Maintains ``self.seen_story_keys`` across the entire screamsheet so news
        components never duplicate stories within the same screamsheet.
    """

    FRONT_PAGE_CAPACITY: float = 0.85
    SUBSEQUENT_PAGE_CAPACITY: float = 1.0

    def __init__(
        self,
        output_filename: str,
        components: Optional[List[ScreamsheetComponent]] = None,
        screamsheet_title: str = "Screamsheet",
        subtitle: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            output_filename=output_filename,
            date=date,
            display_date=display_date if display_date is not None else (date or datetime.now()),
        )
        self.components: List[ScreamsheetComponent] = list(components or [])
        self.screamsheet_title: str = screamsheet_title or "Screamsheet"
        self.subtitle_text: Optional[str] = subtitle
        self.seen_story_keys: Set[str] = set()
        self.packed_pages: List[List[ScreamsheetComponent]] = []

        self.component_header_style = ParagraphStyle(
            name="CustomComponentHeader",
            parent=self.styles["h3"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=4,
            spaceAfter=6,
            alignment=TA_CENTER,
        )

    def get_title(self) -> str:
        return self.screamsheet_title or "Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        return self.subtitle_text

    def build_sections(self) -> List[Section]:
        return list(self.components)

    @classmethod
    def _can_fit_on_page(
        cls,
        spec: ComponentLayoutSpec,
        page_index: int,
        current_weight: float,
        family_counts: Dict[str, int],
        page_is_empty: bool,
    ) -> bool:
        """Return True if a component with ``spec`` can be added to ``page_index``."""
        family = spec.component_family or "generic"
        count_in_family = family_counts.get(family, 0)

        if page_index == 0 and spec.max_on_front_page is not None:
            if count_in_family >= spec.max_on_front_page:
                return False

        if page_index >= 1 and spec.max_per_page is not None:
            if count_in_family >= spec.max_per_page:
                return False

        if spec.max_per_page is not None and count_in_family >= spec.max_per_page:
            return False

        if spec.full_page_only and not page_is_empty:
            return False

        capacity = (
            cls.FRONT_PAGE_CAPACITY if page_index == 0 else cls.SUBSEQUENT_PAGE_CAPACITY
        )
        if not page_is_empty and (current_weight + spec.weight > capacity + 1e-6):
            return False

        return True

    def _expand_components_for_packing(self) -> List[ScreamsheetComponent]:
        """Bind sheet-level deduplication state and expand any multi-chunk components."""
        expanded: List[ScreamsheetComponent] = []
        for comp in self.components:
            if hasattr(comp, "bind_screamsheet_context"):
                comp.bind_screamsheet_context(seen_story_keys=self.seen_story_keys)
            if not comp.has_content():
                continue
            if hasattr(comp, "expand_page_units"):
                units = comp.expand_page_units()
                expanded.extend(u for u in units if u.has_content())
            else:
                expanded.append(comp)
        return expanded

    def pack_components_into_pages(self) -> List[List[ScreamsheetComponent]]:
        """Pack active components into pages while strictly preserving YAML order."""
        units = self._expand_components_for_packing()
        if not units:
            self.packed_pages = []
            return []

        pages: List[List[ScreamsheetComponent]] = [[]]
        page_weights: List[float] = [0.0]
        page_families: List[Dict[str, int]] = [{}]

        for comp in units:
            spec = comp.layout_spec
            cur_idx = len(pages) - 1

            while not self._can_fit_on_page(
                spec=spec,
                page_index=cur_idx,
                current_weight=page_weights[cur_idx],
                family_counts=page_families[cur_idx],
                page_is_empty=(len(pages[cur_idx]) == 0),
            ):
                # If the current page is empty and only failed because of a front-page
                # restriction (e.g., max_on_front_page == 0), advance to the next page;
                # if we're already on page >= 1 and the page is empty, force-place it
                # so we never loop infinitely.
                if len(pages[cur_idx]) == 0 and cur_idx >= 1:
                    break
                pages.append([])
                page_weights.append(0.0)
                page_families.append({})
                cur_idx = len(pages) - 1

            pages[cur_idx].append(comp)
            page_weights[cur_idx] += spec.weight
            fam = spec.component_family or "generic"
            page_families[cur_idx][fam] = page_families[cur_idx].get(fam, 0) + 1

        # Remove any empty leading/trailing page buckets if created
        non_empty = [p for p in pages if p]
        self.packed_pages = non_empty
        return non_empty

    def _render_component_with_chrome(
        self,
        comp: ScreamsheetComponent,
        is_first_on_page: bool,
    ) -> List[Any]:
        """Render a single component along with inter-component dividers and title header."""
        flowables: List[Any] = []
        import inspect

        sig = inspect.signature(comp.render)
        if "styles" in sig.parameters:
            comp_elements = comp.render(styles=self.styles, max_width=540)
        else:
            comp_elements = comp.render()
        if not comp_elements:
            return []

        if not is_first_on_page:
            flowables.append(Spacer(1, 10))
            if comp.layout_spec.preferred_top_divider:
                flowables.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.6,
                        color=colors.HexColor("#cccccc"),
                        spaceBefore=2,
                        spaceAfter=6,
                    )
                )

        if comp.title and not comp.layout_spec.renders_own_header:
            flowables.append(Paragraph(f"<b>{comp.title}</b>", self.component_header_style))

        flowables.extend(comp_elements)
        return flowables

    def generate(self) -> str:
        """Pack components into pages, render the multi-page PDF, and write Markdown."""
        logger.info("Building CustomScreamsheet '%s'", self.get_title())
        self.sections = self.build_sections()
        pages_of_components = self.pack_components_into_pages()

        rendered_pages: List[List[Any]] = []

        # Masthead flowables for Page 1
        masthead: List[Any] = [
            Paragraph(self.get_title(), self.title_style),
        ]
        subtitle = self.get_subtitle()
        if subtitle:
            masthead.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        masthead.append(Paragraph(self.get_date_string(), self.subtitle_style))
        masthead.append(Spacer(1, 12))

        if not pages_of_components:
            rendered_pages.append(masthead)
        else:
            for page_idx, comp_list in enumerate(pages_of_components):
                page_flowables: List[Any] = []
                if page_idx == 0:
                    page_flowables.extend(masthead)
                for comp_idx, comp in enumerate(comp_list):
                    page_flowables.extend(
                        self._render_component_with_chrome(
                            comp, is_first_on_page=(comp_idx == 0)
                        )
                    )
                rendered_pages.append(page_flowables)

        pdf_path = self._build_multi_page_pdf(rendered_pages)

        try:
            self.generate_markdown()
        except Exception as exc:
            logger.warning(
                "Failed to generate secondary markdown output for %s: %s",
                self.get_title(),
                exc,
            )

        return pdf_path

"""CustomScreamsheet composer for building multi-page screamsheets from arbitrary components."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Set

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

from ..base.errors import EmptyScreamsheetError
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

    FRONT_PAGE_CAPACITY: float = 0.92
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
        page_has_full_page_only: bool = False,
    ) -> bool:
        """Return True if a component with ``spec`` can be added to ``page_index``."""
        if page_has_full_page_only:
            return False

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

    @classmethod
    def _can_fit_in_open_right_column(
        cls,
        open_left_comp: ScreamsheetComponent,
        right_spec: ComponentLayoutSpec,
        page_index: int,
        current_weight: float,
        family_counts: Dict[str, int],
        page_has_full_page_only: bool = False,
    ) -> bool:
        """Return True if a single-column component can pair into the open right column on ``page_index``."""
        if page_has_full_page_only or right_spec.columns != 1 or right_spec.full_page_only:
            return False

        family = right_spec.component_family or "generic"
        count_in_family = family_counts.get(family, 0)

        if page_index == 0 and right_spec.max_on_front_page is not None:
            if count_in_family >= right_spec.max_on_front_page:
                return False

        if page_index >= 1 and right_spec.max_per_page is not None:
            if count_in_family >= right_spec.max_per_page:
                return False

        if right_spec.max_per_page is not None and count_in_family >= right_spec.max_per_page:
            return False

        capacity = (
            cls.FRONT_PAGE_CAPACITY if page_index == 0 else cls.SUBSEQUENT_PAGE_CAPACITY
        )
        left_w = open_left_comp.layout_spec.weight
        new_row_w = max(left_w, right_spec.weight)
        new_page_w = (current_weight - left_w) + new_row_w
        if new_page_w > capacity + 1e-6:
            return False

        return True

    def pack_components_into_pages(self) -> List[List[ScreamsheetComponent]]:
        """Pack active components into pages while strictly preserving YAML order."""
        from .news.base import _NewsPageUnitComponent

        units = self._expand_components_for_packing()
        if not units:
            self.packed_pages = []
            return []

        pages: List[List[ScreamsheetComponent]] = [[]]
        page_weights: List[float] = [0.0]
        page_families: List[Dict[str, int]] = [{}]
        open_left_comp: Optional[ScreamsheetComponent] = None

        queue: Deque[ScreamsheetComponent] = deque(units)

        while queue:
            cur_idx = len(pages) - 1
            has_full_only = any(
                existing.layout_spec.full_page_only for existing in pages[cur_idx]
            )

            # If there is an open left column on the current page and the next unit is
            # a 2-article news chunk, split off its first article to fill the open right
            # column if a 1-article news column fits alongside open_left_comp.
            if (
                open_left_comp is not None
                and isinstance(queue[0], _NewsPageUnitComponent)
                and len(queue[0].data) >= 2
            ):
                probe_spec = ComponentLayoutSpec(
                    weight=0.35,
                    columns=1,
                    component_family="news",
                    max_on_front_page=2,
                    max_per_page=2,
                    renders_own_header=False,
                    preferred_top_divider=True,
                )
                if self._can_fit_in_open_right_column(
                    open_left_comp=open_left_comp,
                    right_spec=probe_spec,
                    page_index=cur_idx,
                    current_weight=page_weights[cur_idx],
                    family_counts=page_families[cur_idx],
                    page_has_full_page_only=has_full_only,
                ):
                    first_news_unit: _NewsPageUnitComponent = queue.popleft()  # type: ignore[assignment]
                    parent_news = first_news_unit.parent
                    all_articles = list(first_news_unit.data)
                    sched_items = list(first_news_unit.schedule_items)
                    sched_title = first_news_unit.schedule_title
                    first_title = first_news_unit.title

                    while queue and isinstance(queue[0], _NewsPageUnitComponent) and queue[0].parent is parent_news:
                        nxt_unit: _NewsPageUnitComponent = queue.popleft()  # type: ignore[assignment]
                        all_articles.extend(nxt_unit.data)
                        if nxt_unit.schedule_items:
                            sched_items = list(nxt_unit.schedule_items)

                    single_unit = _NewsPageUnitComponent(
                        parent=parent_news,
                        articles_chunk=[all_articles[0]],
                        schedule_items=sched_items if len(all_articles) == 1 else None,
                        schedule_title=sched_title,
                        title=first_title,
                    )
                    remaining = all_articles[1:]
                    rechunked: List[_NewsPageUnitComponent] = []
                    for r_idx in range(0, len(remaining), 2):
                        r_chunk = remaining[r_idx : r_idx + 2]
                        is_last = r_idx + 2 >= len(remaining)
                        cont_title = (
                            f"{parent_news.title} (Cont.)" if parent_news.title else ""
                        )
                        rechunked.append(
                            _NewsPageUnitComponent(
                                parent=parent_news,
                                articles_chunk=r_chunk,
                                schedule_items=sched_items if is_last else None,
                                schedule_title=sched_title,
                                title=cont_title,
                            )
                        )
                    for rc in reversed(rechunked):
                        queue.appendleft(rc)
                    queue.appendleft(single_unit)

            comp = queue.popleft()
            spec = comp.layout_spec

            # Try pairing into the open right column on the current page
            if open_left_comp is not None and spec.columns == 1:
                if self._can_fit_in_open_right_column(
                    open_left_comp=open_left_comp,
                    right_spec=spec,
                    page_index=cur_idx,
                    current_weight=page_weights[cur_idx],
                    family_counts=page_families[cur_idx],
                    page_has_full_page_only=has_full_only,
                ):
                    left_w = open_left_comp.layout_spec.weight
                    page_weights[cur_idx] = (
                        page_weights[cur_idx] - left_w + max(left_w, spec.weight)
                    )
                    pages[cur_idx].append(comp)
                    fam = spec.component_family or "generic"
                    page_families[cur_idx][fam] = page_families[cur_idx].get(fam, 0) + 1
                    open_left_comp = None
                    continue

            # Otherwise, close any open single-column row and start a new row
            open_left_comp = None

            while not self._can_fit_on_page(
                spec=spec,
                page_index=cur_idx,
                current_weight=page_weights[cur_idx],
                family_counts=page_families[cur_idx],
                page_is_empty=(len(pages[cur_idx]) == 0),
                page_has_full_page_only=any(
                    existing.layout_spec.full_page_only for existing in pages[cur_idx]
                ),
            ):
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
            open_left_comp = comp if spec.columns == 1 else None

        # Remove any empty leading/trailing page buckets if created
        non_empty = [p for p in pages if p]
        self.packed_pages = non_empty
        return non_empty

    def _render_single_column_cell(self, comp: ScreamsheetComponent) -> List[Any]:
        """Render a single-column component (max_width=265) along with its header for a 2-column table cell."""
        import inspect

        cell_flowables: List[Any] = []
        sig = inspect.signature(comp.render)
        if "styles" in sig.parameters:
            comp_elements = comp.render(styles=self.styles, max_width=265)
        else:
            comp_elements = comp.render()
        if not comp_elements:
            return [Paragraph("", self.styles["Normal"])]

        if comp.title and not comp.layout_spec.renders_own_header:
            cell_flowables.append(Paragraph(f"<b>{comp.title}</b>", self.component_header_style))
        cell_flowables.extend(comp_elements)
        return cell_flowables

    def _build_two_column_row_table(
        self,
        left_flowables: List[Any],
        right_flowables: List[Any],
        show_divider: bool = True,
    ) -> Table:
        """Build a 2-column side-by-side ReportLab Table for single-column components."""
        col_w = 265.0
        gutter = 10.0
        style_cmds: List[Any] = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, -1), gutter),
            ("LEFTPADDING", (1, 0), (1, -1), gutter),
            ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ]
        if show_divider:
            style_cmds.append(("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#CCCCCC")))

        table = Table(
            [[left_flowables, right_flowables]],
            colWidths=[col_w, col_w],
            spaceBefore=0,
            spaceAfter=0,
        )
        table.setStyle(TableStyle(style_cmds))
        return table

    def _render_page_components(self, comp_list: List[ScreamsheetComponent]) -> List[Any]:
        """Render a page's components, pairing adjacent single-column components into 2-column rows."""
        page_flowables: List[Any] = []
        idx = 0
        row_idx = 0

        while idx < len(comp_list):
            comp = comp_list[idx]
            is_first_row = row_idx == 0

            if comp.layout_spec.columns == 1:
                if idx + 1 < len(comp_list) and comp_list[idx + 1].layout_spec.columns == 1:
                    right_comp = comp_list[idx + 1]
                    left_cell = self._render_single_column_cell(comp)
                    right_cell = self._render_single_column_cell(right_comp)

                    if not is_first_row:
                        page_flowables.append(Spacer(1, 10))
                        if (
                            comp.layout_spec.preferred_top_divider
                            or right_comp.layout_spec.preferred_top_divider
                        ):
                            page_flowables.append(
                                HRFlowable(
                                    width="100%",
                                    thickness=0.6,
                                    color=colors.HexColor("#cccccc"),
                                    spaceBefore=2,
                                    spaceAfter=6,
                                )
                            )
                    page_flowables.append(
                        self._build_two_column_row_table(left_cell, right_cell, show_divider=True)
                    )
                    idx += 2
                    row_idx += 1
                    continue

                # Unpaired single-column component
                if comp.layout_spec.expand_when_unpaired:
                    page_flowables.extend(
                        self._render_component_with_chrome(comp, is_first_on_page=is_first_row)
                    )
                else:
                    left_cell = self._render_single_column_cell(comp)
                    right_cell = [Paragraph("", self.styles["Normal"])]
                    if not is_first_row:
                        page_flowables.append(Spacer(1, 10))
                        if comp.layout_spec.preferred_top_divider:
                            page_flowables.append(
                                HRFlowable(
                                    width="100%",
                                    thickness=0.6,
                                    color=colors.HexColor("#cccccc"),
                                    spaceBefore=2,
                                    spaceAfter=6,
                                )
                            )
                    page_flowables.append(
                        self._build_two_column_row_table(left_cell, right_cell, show_divider=True)
                    )
                idx += 1
                row_idx += 1
                continue

            page_flowables.extend(
                self._render_component_with_chrome(comp, is_first_on_page=is_first_row)
            )
            idx += 1
            row_idx += 1

        return page_flowables

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

    def has_content(self) -> bool:
        """Check if any components in this screamsheet have content."""
        if not self.components:
            return False
        return any(comp.has_content() for comp in self.components)

    def generate(self) -> str:
        """Pack components into pages, render the multi-page PDF, and write Markdown."""
        logger.info("Building CustomScreamsheet '%s'", self.get_title())
        self.sections = self.build_sections()
        pages_of_components = (
            self.packed_pages if self.packed_pages else self.pack_components_into_pages()
        )

        if not pages_of_components:
            raise EmptyScreamsheetError(
                f"Screamsheet '{self.get_title()}' has no content to display (all components were empty or unavailable)"
            )

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

        total_content_elements = 0
        for page_idx, comp_list in enumerate(pages_of_components):
            page_flowables: List[Any] = []
            if page_idx == 0:
                page_flowables.extend(masthead)
            content_elements = self._render_page_components(comp_list)
            total_content_elements += len(content_elements)
            page_flowables.extend(content_elements)
            rendered_pages.append(page_flowables)

        if total_content_elements == 0:
            raise EmptyScreamsheetError(
                f"Screamsheet '{self.get_title()}' has no content to display (all components were empty or unavailable)"
            )

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

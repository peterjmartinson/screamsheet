"""Unit tests for Stage 1 foundation: ScreamsheetComponent, ComponentLayoutSpec, ComponentRegistry, and provider hierarchy."""
from datetime import datetime
from typing import Any, List, Optional

import pytest
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from screamsheet.base import (
    BaseScreamsheet,
    DataProvider,
    NewsDataProvider,
    Section,
    SportsDataProvider,
)
from screamsheet.components import (
    ComponentLayoutSpec,
    ComponentRegistry,
    ScreamsheetComponent,
)
from screamsheet.providers.mlb_provider import MLBDataProvider
from screamsheet.providers.nhl_provider import NHLDataProvider
from screamsheet.providers.nba_provider import NBADataProvider
from screamsheet.providers.nfl_provider import NFLDataProvider
from screamsheet.providers.worldcup26_provider import WorldCup26Provider
from screamsheet.providers.mlb_news_rss_provider import MLBNewsRssProvider
from screamsheet.providers.nhl_news_rss_provider import NHLNewsRssProvider
from screamsheet.providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider
from screamsheet.providers.nfl_news_provider import NFLNewsProvider
from screamsheet.providers.political_news_provider import (
    PoliticalNewsProvider,
    PoliticalRSSProvider,
    WhiteHouseProvider,
)
from screamsheet.providers.french_mlb_scraper_provider import FrenchMLBScraperProvider


# ---------------------------------------------------------------------------
# ComponentLayoutSpec tests
# ---------------------------------------------------------------------------

class TestComponentLayoutSpec:
    def test_defaults(self):
        spec = ComponentLayoutSpec()
        assert spec.weight == 0.45
        assert spec.component_family == "generic"
        assert spec.max_on_front_page is None
        assert spec.max_per_page is None
        assert spec.renders_own_header is False
        assert spec.preferred_top_divider is False

    def test_standings_layout_spec_limits(self):
        spec = ComponentLayoutSpec(
            weight=0.48,
            component_family="standings",
            max_on_front_page=1,
            max_per_page=2,
        )
        assert spec.weight == 0.48
        assert spec.component_family == "standings"
        assert spec.max_on_front_page == 1
        assert spec.max_per_page == 2

    def test_invalid_weight_raises(self):
        with pytest.raises(ValueError, match="weight"):
            ComponentLayoutSpec(weight=0)

    def test_invalid_max_on_front_page_raises(self):
        with pytest.raises(ValueError, match="max_on_front_page"):
            ComponentLayoutSpec(max_on_front_page=-1)

    def test_invalid_max_per_page_raises(self):
        with pytest.raises(ValueError, match="max_per_page"):
            ComponentLayoutSpec(max_per_page=0)


# ---------------------------------------------------------------------------
# ScreamsheetComponent tests
# ---------------------------------------------------------------------------

class _DummyComponent(ScreamsheetComponent):
    component_key = "dummy_test_component"
    DEFAULT_LAYOUT_SPEC = ComponentLayoutSpec(weight=0.25, component_family="dummy")

    def __init__(self, title: str = "Dummy", text: str = "Hello Component", **kwargs: Any):
        super().__init__(title=title, **kwargs)
        self.text = text

    def fetch_data(self) -> None:
        self.data = self.text

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()
        style_sheet = styles or getSampleStyleSheet()
        return [Paragraph(str(self.data), style_sheet["Normal"])]


class TestScreamsheetComponent:
    def test_is_section_subclass(self):
        comp = _DummyComponent()
        assert isinstance(comp, Section)
        assert isinstance(comp, ScreamsheetComponent)

    def test_default_layout_spec_applied(self):
        comp = _DummyComponent()
        assert comp.layout_spec.weight == 0.25
        assert comp.layout_spec.component_family == "dummy"
        assert comp.page_slot == "front"

    def test_custom_layout_spec_override(self):
        override = ComponentLayoutSpec(weight=0.80, component_family="custom")
        comp = _DummyComponent(page_slot="back", layout_spec=override)
        assert comp.page_slot == "back"
        assert comp.layout_spec == override

    def test_render_without_args_compatible_with_base_screamsheet(self, tmp_path):
        comp = _DummyComponent(text="Compatible with BaseScreamsheet")
        flowables = comp.render()
        assert len(flowables) == 1
        assert comp.has_content() is True
        assert comp.render_markdown() == "Compatible with BaseScreamsheet"

        class _TestSheet(BaseScreamsheet):
            def get_title(self) -> str:
                return "Component Test Sheet"

            def build_sections(self) -> List[Section]:
                return [comp]

        pdf_file = tmp_path / "comp_test.pdf"
        sheet = _TestSheet(output_filename=str(pdf_file), date=datetime(2026, 10, 21))
        out = sheet.generate()
        assert pdf_file.exists()
        assert out == str(pdf_file)


# ---------------------------------------------------------------------------
# ComponentRegistry tests
# ---------------------------------------------------------------------------

class TestComponentRegistry:
    def setup_method(self):
        self._saved = dict(ComponentRegistry._registry)

    def teardown_method(self):
        ComponentRegistry._registry.clear()
        ComponentRegistry._registry.update(self._saved)

    def test_register_with_explicit_key_and_create(self):
        @ComponentRegistry.register("custom_dummy")
        class _RegisteredComp(_DummyComponent):
            pass

        assert ComponentRegistry.is_registered("custom_dummy")
        assert ComponentRegistry.is_registered("  CUSTOM_DUMMY ")
        assert ComponentRegistry.get("custom_dummy") is _RegisteredComp
        assert "custom_dummy" in ComponentRegistry.list_keys()

        instance = ComponentRegistry.create("custom_dummy", title="Created", text="Body")
        assert isinstance(instance, _RegisteredComp)
        assert instance.title == "Created"
        assert instance.text == "Body"

    def test_register_without_args_uses_component_key_attr(self):
        @ComponentRegistry.register
        class _AutoKeyComp(_DummyComponent):
            component_key = "auto_key_dummy"

        assert ComponentRegistry.get("auto_key_dummy") is _AutoKeyComp

    def test_unknown_key_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown screamsheet component type"):
            ComponentRegistry.get("nonexistent_component_xyz")

    def test_empty_key_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty"):
            ComponentRegistry.register_component("   ", _DummyComponent)

    def test_non_component_class_raises_type_error(self):
        class _NotAComponent:
            pass

        with pytest.raises(TypeError, match="ScreamsheetComponent"):
            ComponentRegistry.register_component("bad", _NotAComponent)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Provider Hierarchy tests
# ---------------------------------------------------------------------------

class TestProviderHierarchy:
    def test_sports_providers_inherit_from_sports_data_provider(self):
        for cls in (
            MLBDataProvider,
            NHLDataProvider,
            NBADataProvider,
            NFLDataProvider,
            WorldCup26Provider,
        ):
            assert issubclass(cls, SportsDataProvider)
            assert issubclass(cls, DataProvider)

    def test_news_providers_inherit_from_news_data_provider(self):
        for cls in (
            MLBNewsRssProvider,
            NHLNewsRssProvider,
            MLBTradeRumorsProvider,
            NFLNewsProvider,
            PoliticalRSSProvider,
            WhiteHouseProvider,
            PoliticalNewsProvider,
            FrenchMLBScraperProvider,
        ):
            assert issubclass(cls, NewsDataProvider)
            assert issubclass(cls, DataProvider)

    def test_sports_data_provider_requires_abstract_methods(self):
        class _IncompleteSportsProvider(SportsDataProvider):
            pass

        with pytest.raises(TypeError):
            _IncompleteSportsProvider()  # type: ignore[abstract]

    def test_news_data_provider_requires_get_articles(self):
        class _IncompleteNewsProvider(NewsDataProvider):
            pass

        with pytest.raises(TypeError):
            _IncompleteNewsProvider()  # type: ignore[abstract]

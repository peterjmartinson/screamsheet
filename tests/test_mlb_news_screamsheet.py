"""Unit tests for screamsheet.news.mlb_news (MLBNewsScreamsheet)."""
import pytest

from screamsheet.news.mlb_news import MLBNewsScreamsheet
from screamsheet.renderers.news_articles import NewsArticlesSection
from screamsheet.renderers.weather import WeatherSection


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


class TestMLBNewsScreamsheeetTitle:
    def test_get_title_returns_mlb_news(self) -> None:
        s = MLBNewsScreamsheet("out.pdf")
        assert s.get_title() == "MLB News"


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------


class TestMLBNewsScreamsheeetDefaults:
    def test_default_favorite_teams(self) -> None:
        s = MLBNewsScreamsheet("out.pdf")
        assert s.favorite_teams == ["Phillies", "Padres", "Yankees"]

    def test_output_filename_stored(self) -> None:
        s = MLBNewsScreamsheet("myfile.pdf")
        assert s.output_filename == "myfile.pdf"


# ---------------------------------------------------------------------------
# Custom configuration
# ---------------------------------------------------------------------------


class TestMLBNewsScreamsheeetCustomTeams:
    def test_custom_favorite_teams_passed_to_provider(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", favorite_teams=["Dodgers"])
        assert s.provider.favorite_teams == ["Dodgers"]


# ---------------------------------------------------------------------------
# build_sections — weather
# ---------------------------------------------------------------------------


class TestMLBNewsScreamsheeetWeatherSection:
    def test_includes_weather_when_enabled(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=True)
        sections = s.build_sections()
        assert any(isinstance(sec, WeatherSection) for sec in sections)

    def test_excludes_weather_when_disabled(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        sections = s.build_sections()
        assert not any(isinstance(sec, WeatherSection) for sec in sections)


# ---------------------------------------------------------------------------
# build_sections — news article sections
# ---------------------------------------------------------------------------


class TestMLBNewsScreamsheeetNewsSections:
    def test_build_sections_contains_two_news_sections(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        news_sections = [
            sec for sec in s.build_sections() if isinstance(sec, NewsArticlesSection)
        ]
        assert len(news_sections) == 2

    def test_first_news_section_start_index_is_zero(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        news_sections = [
            sec for sec in s.build_sections() if isinstance(sec, NewsArticlesSection)
        ]
        assert news_sections[0].start_index == 0

    def test_second_news_section_start_index_is_two(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        news_sections = [
            sec for sec in s.build_sections() if isinstance(sec, NewsArticlesSection)
        ]
        assert news_sections[1].start_index == 2

    def test_first_news_section_max_articles_is_two(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        news_sections = [
            sec for sec in s.build_sections() if isinstance(sec, NewsArticlesSection)
        ]
        assert news_sections[0].max_articles == 2

    def test_second_news_section_max_articles_is_two(self) -> None:
        s = MLBNewsScreamsheet("out.pdf", include_weather=False)
        news_sections = [
            sec for sec in s.build_sections() if isinstance(sec, NewsArticlesSection)
        ]
        assert news_sections[1].max_articles == 2

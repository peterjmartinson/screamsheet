"""Tests for FrenchMLBScraperProvider — team priority routing and random fallback."""
from unittest.mock import patch, MagicMock

from screamsheet.providers.french_mlb_scraper_provider import FrenchMLBScraperProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


RDS_HTML = """<html><body>
  <article>
    <h2><a href="/baseball/mlb/phillies">Phillies acquièrent un lanceur</a></h2>
    <p>Les Phillies ont acquis un lanceur droitier.</p>
  </article>
  <article>
    <h2><a href="/baseball/mlb/blue-jays">Blue Jays remportent la victoire</a></h2>
    <p>Les Blue Jays ont gagné leur dernier match.</p>
  </article>
  <article>
    <h2><a href="/baseball/mlb/mets">Les Mets visent les séries</a></h2>
    <p>Les Mets de New York restent en bonne posture.</p>
  </article>
</body></html>"""

TVA_HTML = """<html><body>
  <article>
    <h2><a href="/baseball/mlb/dodgers">Victoire des Dodgers</a></h2>
    <p>Les Dodgers ont battu les Giants hier soir.</p>
  </article>
  <article>
    <h2><a href="/baseball/mlb/yankees">Yankees et Padres en discussion</a></h2>
    <p>Des pourparlers seraient en cours entre les Yankees et les Padres.</p>
  </article>
</body></html>"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_default_favorite_teams_is_empty():
    provider = FrenchMLBScraperProvider()
    assert provider.favorite_teams == []


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_returns_exactly_two_articles(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response(TVA_HTML)]
    provider = FrenchMLBScraperProvider()
    articles = provider.get_articles()
    assert len(articles) == 2


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_team_match_in_title_is_prioritised(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response(TVA_HTML)]
    provider = FrenchMLBScraperProvider(favorite_teams=["Phillies"])
    articles = provider.get_articles()
    assert "Phillies" in articles[0]["title"]


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_no_team_match_still_returns_two_articles(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response(TVA_HTML)]
    provider = FrenchMLBScraperProvider(favorite_teams=["Expos"])
    articles = provider.get_articles()
    assert len(articles) == 2


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_empty_favorite_teams_returns_two_articles(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response(TVA_HTML)]
    provider = FrenchMLBScraperProvider(favorite_teams=[])
    articles = provider.get_articles()
    assert len(articles) == 2


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_article_has_required_keys(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response(TVA_HTML)]
    provider = FrenchMLBScraperProvider()
    articles = provider.get_articles()
    for article in articles:
        assert "title" in article
        assert "body" in article
        assert "source" in article
        assert "url" in article


@patch("screamsheet.providers.french_mlb_scraper_provider.requests.get")
def test_failed_source_does_not_crash(mock_get):
    mock_get.side_effect = [_make_response(RDS_HTML), _make_response("", status_code=500)]
    provider = FrenchMLBScraperProvider()
    articles = provider.get_articles()
    # RDS has 3 articles, so we should still get 2 from it alone
    assert len(articles) == 2

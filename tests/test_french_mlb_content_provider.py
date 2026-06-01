"""Tests for FrenchMLBContentProvider — LLM lane routing and lexicon parsing."""
import json
from unittest.mock import MagicMock, patch

from screamsheet.providers.french_mlb_content_provider import (
    FrenchMLBContent,
    FrenchMLBContentProvider,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ARTICLE_1 = {
    "title": "Phillies acquièrent un lanceur",
    "body": "Les Phillies ont acquis un lanceur droitier.",
    "source": "RDS",
    "url": "/article-1",
}
ARTICLE_2 = {
    "title": "Blue Jays remportent la victoire",
    "body": "Les Blue Jays ont gagné leur dernier match.",
    "source": "TVA Sports",
    "url": "/article-2",
}

VALID_LEXICON_JSON = json.dumps(
    {
        "vocabulary": [
            {
                "french_lemma": "acquérir",
                "part_of_speech": "verbe",
                "english_translation": "to acquire",
            }
        ],
        "idiomatic_phrases": [
            {
                "french_phrase": "retirer sur des prises",
                "literal_translation": "to retire on strikes",
                "contextual_meaning": "to strike out a batter",
            }
        ],
    }
)


# ---------------------------------------------------------------------------
# Helper: build fully-mocked summarizer classes
# ---------------------------------------------------------------------------

def _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls, lexicon_json=VALID_LEXICON_JSON):
    mock_a2 = MagicMock()
    mock_a2.generate_summary.return_value = "Texte A2."
    mock_b2 = MagicMock()
    mock_b2.generate_summary.return_value = "Texte B2."
    mock_lex = MagicMock()
    mock_lex.generate_summary.return_value = lexicon_json
    mock_a2_cls.return_value = mock_a2
    mock_b2_cls.return_value = mock_b2
    mock_lex_cls.return_value = mock_lex
    return mock_a2, mock_b2, mock_lex


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_lane_a_receives_article_1(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    mock_a2, _, _ = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    mock_a2.generate_summary.assert_called_once_with("grok", ARTICLE_1)


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_lane_b_receives_article_2(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _, mock_b2, _ = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    mock_b2.generate_summary.assert_called_once_with("grok", ARTICLE_2)


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_lexicon_lane_receives_both_articles(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _, _, mock_lex = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    call_data = mock_lex.generate_summary.call_args[0][1]
    assert call_data["article_1_title"] == ARTICLE_1["title"]
    assert call_data["article_2_title"] == ARTICLE_2["title"]


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_valid_lexicon_json_is_parsed(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    result = FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    assert len(result.lexicon["vocabulary"]) == 1
    assert result.lexicon["vocabulary"][0]["french_lemma"] == "acquérir"
    assert len(result.lexicon["idiomatic_phrases"]) == 1


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_invalid_lexicon_json_returns_empty_structure(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _mock_summarizer_classes(
        mock_lex_cls, mock_b2_cls, mock_a2_cls, lexicon_json="this is not json"
    )
    result = FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    assert result.lexicon == {"vocabulary": [], "idiomatic_phrases": []}

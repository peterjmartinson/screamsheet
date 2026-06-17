"""Tests for FrenchMLBContentProvider — LLM lane routing and lexicon parsing."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from screamsheet.providers.french_mlb_content_provider import (
    FrenchMLBContent,
    FrenchMLBContentProvider,
)

_LEXICON_PROMPT = (
    Path(__file__).parent.parent
    / "src" / "screamsheet" / "llm" / "prompts" / "french_mlb_lexicon.txt"
).read_text(encoding="utf-8")

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
def test_lexicon_lane_receives_generated_a2_text(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _, _, mock_lex = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    call_data = mock_lex.generate_summary.call_args[0][1]
    assert call_data["a2_text"] == "Texte A2."


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_lexicon_lane_receives_generated_b2c1_text(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _, _, mock_lex = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    call_data = mock_lex.generate_summary.call_args[0][1]
    assert call_data["b2c1_text"] == "Texte B2."


@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBA2Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBB2C1Summarizer")
@patch("screamsheet.providers.french_mlb_content_provider.FrenchMLBLexiconSummarizer")
def test_lexicon_lane_does_not_receive_raw_source_articles(mock_lex_cls, mock_b2_cls, mock_a2_cls):
    _, _, mock_lex = _mock_summarizer_classes(mock_lex_cls, mock_b2_cls, mock_a2_cls)
    FrenchMLBContentProvider(grok_api_key="test").generate([ARTICLE_1, ARTICLE_2])
    call_data = mock_lex.generate_summary.call_args[0][1]
    assert "article_1_body" not in call_data
    assert "article_2_body" not in call_data


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


# ---------------------------------------------------------------------------
# Prompt-content tests (DoD criteria 3–5)
# ---------------------------------------------------------------------------

def test_lexicon_prompt_references_a2_and_b2c1_keys():
    assert "a2_text" in _LEXICON_PROMPT
    assert "b2c1_text" in _LEXICON_PROMPT


def test_lexicon_prompt_restricts_extraction_to_provided_text():
    prompt_lower = _LEXICON_PROMPT.lower()
    assert "only" in prompt_lower


def test_lexicon_prompt_instructs_weighting():
    assert "2/3" in _LEXICON_PROMPT or "two-thirds" in _LEXICON_PROMPT.lower()

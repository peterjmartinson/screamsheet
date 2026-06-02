"""French MLB LLM content generation provider."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..llm import FrenchMLBA2Summarizer, FrenchMLBB2C1Summarizer, FrenchMLBLexiconSummarizer
from ..llm.config import DEFAULT_LLM_CONFIG, LLMConfig


@dataclass
class FrenchMLBContent:
    """Structured output from the three LLM generation lanes."""

    lane_a: str       # CEFR A2 rewrite of article 1
    lane_b: str       # CEFR B2/C1 rewrite of article 2
    lexicon: Dict     # Parsed JSON: {"vocabulary": [...], "idiomatic_phrases": [...]}


class FrenchMLBContentProvider:
    """
    Generates LLM-powered French article rewrites and a vocabulary lexicon.

    Uses the existing Grok-backed summarizer infrastructure to run three
    concurrent generation tasks:

    - **Lane A**: CEFR A2 rewrite of article 1 via :class:`FrenchMLBA2Summarizer`
    - **Lane B**: CEFR B2/C1 rewrite of article 2 via :class:`FrenchMLBB2C1Summarizer`
    - **Lane C**: JSON lexicon extracted from both articles via
      :class:`FrenchMLBLexiconSummarizer`

    Args:
        grok_api_key: xAI API key.  Defaults to the ``GROK_API_KEY`` env var.
        config:       LLM configuration.  Defaults to ``DEFAULT_LLM_CONFIG``.
    """

    def __init__(
        self,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        self._grok_api_key = grok_api_key or os.getenv("GROK_API_KEY")
        self._config = config

    def generate(self, articles: List[Dict[str, str]]) -> FrenchMLBContent:
        """
        Run all three LLM lanes against the two input articles.

        Args:
            articles: List of exactly two article dicts, each with keys
                      ``title``, ``body``, ``source``, ``url``.

        Returns:
            :class:`FrenchMLBContent` with ``lane_a``, ``lane_b``, and
            ``lexicon`` populated.  Never raises; invalid lexicon JSON
            produces an empty ``{"vocabulary": [], "idiomatic_phrases": []}``
            structure instead.
        """
        article_1 = articles[0] if len(articles) > 0 else {"title": "", "body": ""}
        article_2 = articles[1] if len(articles) > 1 else {"title": "", "body": ""}

        a2_sum = FrenchMLBA2Summarizer(
            grok_api_key=self._grok_api_key, config=self._config
        )
        b2_sum = FrenchMLBB2C1Summarizer(
            grok_api_key=self._grok_api_key, config=self._config
        )
        lex_sum = FrenchMLBLexiconSummarizer(
            grok_api_key=self._grok_api_key, config=self._config
        )

        lexicon_data: Dict[str, str] = {
            "article_1_title": article_1.get("title", ""),
            "article_1_body": article_1.get("body", ""),
            "article_2_title": article_2.get("title", ""),
            "article_2_body": article_2.get("body", ""),
        }

        with ThreadPoolExecutor(max_workers=3) as executor:
            f_a = executor.submit(a2_sum.generate_summary, "grok", article_1)
            f_b = executor.submit(b2_sum.generate_summary, "grok", article_2)
            f_lex = executor.submit(lex_sum.generate_summary, "grok", lexicon_data)
            lane_a: str = f_a.result()
            lane_b: str = f_b.result()
            lexicon_raw: str = f_lex.result()

        return FrenchMLBContent(
            lane_a=lane_a,
            lane_b=lane_b,
            lexicon=self._parse_lexicon(lexicon_raw),
        )

    def _parse_lexicon(self, raw: str) -> Dict:
        """Parse lexicon JSON, returning an empty structure on any failure."""
        try:
            data = json.loads(raw)
            return {
                "vocabulary": data.get("vocabulary", []),
                "idiomatic_phrases": data.get("idiomatic_phrases", []),
            }
        except (json.JSONDecodeError, AttributeError, TypeError):
            return {"vocabulary": [], "idiomatic_phrases": []}

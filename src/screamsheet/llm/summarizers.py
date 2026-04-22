"""Concrete LLM summarizer classes.

Each summarizer targets a specific input source (NHL games, MLB games, news
articles).  The :class:`FilePromptMixin` handles loading versioned prompt
templates from ``llm/prompts/``; concrete classes just declare ``_PROMPT_FILE``
and the expected ``ExtractedInfo`` key contract in their docstring.

Adding a new input source
-------------------------
1. Drop a ``your_source.txt`` prompt file  in ``llm/prompts/`` using
   ``{key}`` placeholders that match the dict you'll pass as ``data``.
2. Add a class here that inherits ``FilePromptMixin, BaseGameSummaryGenerator``
   and sets ``_PROMPT_FILE = Path("your_source.txt")``.
3. Wire it where needed (provider's ``get_game_summary`` or a renderer's
   ``fetch_data``), passing the matching ``ExtractedInfo`` dict.
"""
from pathlib import Path
from typing import Optional

from .base import BaseGameSummaryGenerator, ExtractedInfo
from .config import LLMConfig, DEFAULT_LLM_CONFIG

# Absolute path to the prompts directory next to this file
_PROMPTS_DIR = Path(__file__).parent / "prompts"


class FilePromptMixin:
    """
    Mixin that loads ``_build_llm_prompt`` from a versioned ``.txt`` file.

    The prompt file lives at ``llm/prompts/<_PROMPT_FILE>``.  Any ``{key}``
    placeholders in the file are filled via ``str.format_map(data)``.
    Keys that are absent from *data* are left as literals so the prompt
    doesn't crash on partially-populated inputs.
    """

    _PROMPT_FILE: Path  # must be set by concrete class

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        template = (_PROMPTS_DIR / self._PROMPT_FILE).read_text(encoding="utf-8")
        try:
            return template.format_map(data)
        except KeyError:
            # Fallback: return the raw template (missing keys stay as {key})
            return template


# ---------------------------------------------------------------------------
# Concrete summarizers
# ---------------------------------------------------------------------------

class NHLGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a humorous NHL game recap for a young audience.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str  — full team name
    - ``away_team``          str  — full team name
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — space-joined play descriptions
    """

    _PROMPT_FILE = Path("nhl_game.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )


class MLBGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an over-the-top MLB game recap for a stat-savvy young fan.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — space-joined play descriptions
    """

    _PROMPT_FILE = Path("mlb_game.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )


class NewsSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a lively news-article summary.

    The ``news.txt`` prompt contains no ``{key}`` placeholders; *data* is
    serialised to JSON and embedded in the LangChain template by
    :meth:`~screamsheet.llm.base.BaseGameSummaryGenerator._setup_prompt_chain`
    as ``{game_data}``, so any dict shape is accepted.

    Typical ``data`` shapes
    -----------------------
    - News article: ``{'title': str, 'summary': str, 'link': str, ...}``
    - Ad-hoc:       ``{'summary': str}``  (e.g., Players Tribune title gen)
    """

    _PROMPT_FILE = Path("news.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )


class PoliticalNewsSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a lively summary of a political news article.

    Uses ``political_news.txt`` so the prompt can carry extra political
    context instructions (party attribution, administration sourcing, etc.)
    without affecting the generic ``NewsSummarizer`` used by MLB/FanGraphs.

    Typical ``data`` shape
    ----------------------
    - ``{'title': str, 'summary': str, 'link': str, 'source': str, ...}``
    """

    _PROMPT_FILE = Path("political_news.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )


class SkyNightSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a sky-tonight narrative bullet list.

    Persona: an enthusiastic naked-eye amateur astronomer who also finds
    astrology playfully fun.  Never recommends telescopes.

    Expected ``data`` keys
    ----------------------
    - ``planets``    str  — formatted planet/zodiac summary line
    - ``moon_phase`` str  — e.g. "Waxing Crescent (35% illuminated)"
    - ``highlights`` str  — newline-separated highlight sentences
    - ``location``   str  — observer location name
    - ``date``       str  — display date string
    """

    _PROMPT_FILE = Path("sky_tonight.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )


class HoroscopeSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a personalized ~200-word horoscope reading for one person.

    Expected ``data`` keys
    ----------------------
    - ``name``           str  — person's name
    - ``birth_date``     str  — YYYY-MM-DD
    - ``birth_time``     str  — HH:MM (24-hour)
    - ``birth_location`` str  — city/state of birth
    - ``planets``        str  — formatted planet/zodiac summary line
    - ``moon_phase``     str  — e.g. "Waxing Crescent"
    - ``date``           str  — display date string
    - ``location``       str  — observer location name
    """

    _PROMPT_FILE = Path("sky_horoscope.txt")

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )

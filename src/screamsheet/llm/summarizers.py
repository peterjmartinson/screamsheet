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
import logging
import random
from pathlib import Path
from typing import Optional

from .base import BaseGameSummaryGenerator, ExtractedInfo
from .config import LLMConfig, DEFAULT_LLM_CONFIG

logger = logging.getLogger(__name__)

# Absolute path to the prompts directory next to this file
_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Randomized Fan Rant opening hook angles
# ---------------------------------------------------------------------------

MLB_RANT_ANGLES = [
    "Focus your opening on the starting pitcher or bullpen meltdown and the specific pitches that gave up runs.",
    "Focus your opening on the decisive offensive failure: stranded runners in scoring position, key double plays, or empty at-bats.",
    "Focus your opening with biting sarcasm about false hope from earlier innings or a misleading stat that masked the disaster.",
    "Open in media res with the opponent's game-winning hit or home run that sealed the defeat.",
    "Focus your opening on questionable managerial decisions, bullpen substitutions, or late-game execution errors.",
]

NHL_RANT_ANGLES = [
    "Focus your opening on the goaltending performance and soft or surrendered goals.",
    "Focus your opening on special teams failures: wasted power plays, shorthanded concessions, or undisciplined penalties.",
    "Focus your opening on a devastating third-period breakdown or late defensive collapse.",
    "Open in media res with the opponent's dagger goal that put the game out of reach.",
    "Focus your opening with biting sarcasm about a blown lead or failing to match the opponent's physical intensity.",
]

NBA_RANT_ANGLES = [
    "Focus your opening on a devastating 4th quarter collapse or opponent scoring run.",
    "Focus your opening on poor shooting, missed free throws, and wasted possessions in crunch time.",
    "Focus your opening on star players failing to step up or costly turnovers down the stretch.",
    "Open in media res with the opponent's dagger three-pointer or backbreaking run.",
    "Focus your opening on defensive lapses and easy transition points given away.",
]


class SafeDict(dict):
    """Dict subclass that leaves missing keys as literal '{key}' placeholders during str.format_map."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


class FilePromptMixin:
    """
    Mixin that loads ``_build_llm_prompt`` from a versioned ``.txt`` file.

    The prompt file lives at ``llm/prompts/<_PROMPT_FILE>``. Any ``{key}``
    placeholders in the file are filled via ``str.format_map(data)``.
    Keys that are absent from *data* are left as literals so the prompt
    doesn't crash on partially-populated inputs.

    If ``extra_instructions`` is provided in *data* (as a string or list of strings),
    it is cleanly appended to the rendered prompt instructions.
    """

    _PROMPT_FILE: Path  # must be set by concrete class

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        template = (_PROMPTS_DIR / self._PROMPT_FILE).read_text(encoding="utf-8")
        prompt = template.format_map(SafeDict(data))

        extra = data.get("extra_instructions")
        if extra:
            if isinstance(extra, list):
                extra_lines = "\n".join(f"- {item.strip()}" for item in extra if str(item).strip())
                if extra_lines:
                    prompt = f"{prompt.rstrip()}\n\nAdditional instructions:\n{extra_lines}\n"
            elif isinstance(extra, str) and extra.strip():
                prompt = f"{prompt.rstrip()}\n\nAdditional instructions:\n- {extra.strip()}\n"

        return prompt


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


class NHLFanRantSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an angry hometown-fan game recap when the primary favorite NHL team loses.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — period-tagged play-by-play
    - ``losing_team``        str  — full name of the featured team that lost
    - ``rant_angle``         str  — optional opening hook instruction
    """

    _PROMPT_FILE = Path("nhl_game_fan_rant.txt")

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

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        prompt_data = dict(data)
        if not prompt_data.get("rant_angle"):
            prompt_data["rant_angle"] = random.choice(NHL_RANT_ANGLES)
        return super()._build_llm_prompt(prompt_data)


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


class MLBFanRantSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an angry hometown-fan game recap when the primary favorite team loses.

    Uses the same game-data structure as ``MLBGameSummarizer`` but adds
    ``losing_team`` so the prompt can address the fan base directly.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — space-joined play descriptions
    - ``losing_team``        str  — full name of the featured team that lost
    - ``rant_angle``         str  — optional opening hook instruction
    """

    _PROMPT_FILE = Path("mlb_game_fan_rant.txt")

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

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        prompt_data = dict(data)
        if not prompt_data.get("rant_angle"):
            prompt_data["rant_angle"] = random.choice(MLB_RANT_ANGLES)
        return super()._build_llm_prompt(prompt_data)


class MLBAllStarGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an expanded ~500-word recap for the MLB All-Star Game from an NL beat writer perspective.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — space-joined play descriptions
    """

    _PROMPT_FILE = Path("mlb_allstar_game.txt")

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


HOROSCOPE_PROMPT_KEPLER = Path("sky_horoscope_kepler.txt")
HOROSCOPE_PROMPT_PLAYBOOK = Path("sky_horoscope_playbook.txt")


class HoroscopeSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a personalized ~200-word horoscope reading for one person.

    Supports different prompt styles:
    - ``"kepler"`` (default): Strategic advisor modelled after Johannes Kepler.
    - ``"playbook"``: Daily playbook with green light / caution / move and aspect breakdown.

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

    _PROMPT_FILE = HOROSCOPE_PROMPT_KEPLER

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
        style: str = "kepler",
    ) -> None:
        BaseGameSummaryGenerator.__init__(
            self,
            gemini_api_key=gemini_api_key,
            grok_api_key=grok_api_key,
            config=config,
        )
        self.style = style.lower().strip() if style else "kepler"
        if self.style == "playbook":
            self._PROMPT_FILE = HOROSCOPE_PROMPT_PLAYBOOK
        else:
            self._PROMPT_FILE = HOROSCOPE_PROMPT_KEPLER
        logger.debug("HoroscopeSummarizer initialized with style='%s' (prompt_file='%s')", self.style, self._PROMPT_FILE)



class NBAGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an Athletic/ESPN-style NBA game recap.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — quarter-tagged play descriptions
    """

    _PROMPT_FILE = Path("nba_game.txt")

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


class NBAFanRantSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an angry hometown-fan NBA recap when the primary favorite team loses.

    Expected ``data`` keys
    ----------------------
    - ``home_team``          str
    - ``away_team``          str
    - ``home_score``         int
    - ``away_score``         int
    - ``narrative_snippets`` str  — quarter-tagged play descriptions
    - ``losing_team``        str  — full name of the featured team that lost
    - ``rant_angle``         str  — optional opening hook instruction
    """

    _PROMPT_FILE = Path("nba_game_fan_rant.txt")

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

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        prompt_data = dict(data)
        if not prompt_data.get("rant_angle"):
            prompt_data["rant_angle"] = random.choice(NBA_RANT_ANGLES)
        return super()._build_llm_prompt(prompt_data)


# ---------------------------------------------------------------------------
# French MLB summarizers (Issue 90)
# ---------------------------------------------------------------------------


class FrenchMLBA2Summarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Rewrites an MLB news article in CEFR A2 French for young readers.

    Expected ``data`` keys
    ----------------------
    - ``title`` str — article headline
    - ``body``  str — article body text
    """

    _PROMPT_FILE = Path("french_mlb_a2.txt")

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


class FrenchMLBB2C1Summarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Rewrites an MLB news article in CEFR B2/C1 French for advanced readers.

    Expected ``data`` keys
    ----------------------
    - ``title`` str — article headline
    - ``body``  str — article body text
    """

    _PROMPT_FILE = Path("french_mlb_b2c1.txt")

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


class FrenchMLBLexiconSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Extracts a JSON vocabulary/idiom lexicon from two generated French MLB articles.

    Expected ``data`` keys
    ----------------------
    - ``a2_text``    str  — generated CEFR A2 French article (Lane A output)
    - ``b2c1_text``  str  — generated CEFR B2/C1 French article (Lane B output)

    Output is a JSON string matching the schema defined in
    ``llm/prompts/french_mlb_lexicon.txt``.
    """

    _PROMPT_FILE = Path("french_mlb_lexicon.txt")

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


class WorldCupGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a newspaper-style FIFA World Cup match recap.

    Expected ``data`` keys
    ----------------------
    - ``home_team``       str  — full team name
    - ``away_team``       str  — full team name
    - ``home_score``      str  — goals scored in regulation/AET
    - ``away_score``      str
    - ``status_label``    str  — e.g. " (on penalties)" or ""
    - ``round_label``     str  — e.g. "Round of 32", "Group Stage"
    - ``goals_timeline``  str  — formatted goal-event lines
    - ``penalty_section`` str  — penalty shootout detail or ""
    """

    _PROMPT_FILE = Path("worldcup_game.txt")

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


class NFLGameSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates an NFL game recap and drive breakdown.

    Expected ``data`` keys
    ----------------------
    - ``home_team``       str
    - ``away_team``       str
    - ``home_score``      int
    - ``away_score``      int
    - ``scoring_drives``  str
    - ``team_totals``     str
    - ``top_performers``  str
    """

    _PROMPT_FILE = Path("nfl_game.txt")

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


class EmailNewsSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a 2-3 sentence summary of an email newsletter or news alert.

    Expected ``data`` keys
    ----------------------
    - ``sender``  str — sender display name or publication source
    - ``subject`` str — subject line of the email
    - ``body``    str — extracted body text
    """

    _PROMPT_FILE = Path("email_news.txt")

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


class EmailImportantSummarizer(FilePromptMixin, BaseGameSummaryGenerator):
    """
    Generates a 1-2 sentence actionable summary of important personal/school emails.

    Expected ``data`` keys
    ----------------------
    - ``sender``  str — sender display name or address
    - ``subject`` str — subject line of the email
    - ``body``    str — extracted body text
    """

    _PROMPT_FILE = Path("email_important.txt")

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


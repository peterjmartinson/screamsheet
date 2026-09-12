"""Base LLM summarizer: LangChain chain wiring, SQLite response caching, and shared generation logic.

Concrete summarizers live in llm/summarizers.py; they subclass this and
implement only ``_build_llm_prompt(data)``.

Callers that previously imported from ``llm.summary`` continue to work
unchanged — ``llm/summary.py`` re-exports everything from here.
"""
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    Runnable,
    RunnableLambda,
    RunnablePassthrough,
)

from .config import LLMConfig, DEFAULT_LLM_CONFIG

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("screamsheet.llm")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Public type aliases (re-exported so callers don't need a new import path)
# ---------------------------------------------------------------------------

ExtractedInfo = Dict[str, Any]
PromptChainInput = Dict[str, Any]


class BaseGameSummaryGenerator:
    """
    Base class for LLM-powered summarizers with built-in SQLite caching.

    Handles LLM initialisation, LangChain pipeline assembly, response caching,
    logging, and error recovery. Concrete subclasses implement ``_build_llm_prompt(data)``
    and declare an optional ``_PROMPT_FILE`` class attribute pointing to a
    versioned ``.txt`` template relative to ``llm/prompts/``.

    Args:
        gemini_api_key: Google Gemini API key (``None`` disables Gemini).
        grok_api_key:   xAI Grok API key     (``None`` disables Grok).
        config:         :class:`~screamsheet.llm.config.LLMConfig` instance.
                        Defaults to :data:`~screamsheet.llm.config.DEFAULT_LLM_CONFIG`.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        config: LLMConfig = DEFAULT_LLM_CONFIG,
    ) -> None:
        self.config = config
        self.api_keys: Dict[str, Optional[str]] = {
            "gemini": gemini_api_key,
            "grok": grok_api_key,
        }
        self.llm_gemini = self._initialize_gemini(gemini_api_key)
        self.llm_grok = self._initialize_grok(grok_api_key)
        self._cwd = Path.cwd()

    # ------------------------------------------------------------------
    # LLM initialisation
    # ------------------------------------------------------------------

    def _initialize_gemini(
        self, api_key: Optional[str]
    ) -> Optional[ChatGoogleGenerativeAI]:
        if not api_key:
            return None
        return ChatGoogleGenerativeAI(
            model=self.config.gemini_model,
            temperature=self.config.gemini_temperature,
            google_api_key=api_key,
        )

    def _initialize_grok(self, api_key: Optional[str]) -> Optional[ChatOpenAI]:
        if not api_key:
            return None
        return ChatOpenAI(
            model=self.config.grok_model,
            temperature=self.config.grok_temperature,
            openai_api_key=api_key,
            base_url=self.config.grok_base_url,
            model_kwargs={"extra_headers": self.config.grok_extra_headers},
        )

    # ------------------------------------------------------------------
    # LLM selection
    # ------------------------------------------------------------------

    def _select_llm_instance(self, llm_choice: str) -> Union[Runnable, None]:
        """Return the initialised LLM corresponding to *llm_choice*."""
        llm_choice = llm_choice.lower()
        if llm_choice == "gemini" and self.llm_gemini:
            logger.debug("Using GEMINI for generation")
            return self.llm_gemini
        elif llm_choice == "grok" and self.llm_grok:
            logger.debug("Using GROK for generation")
            return self.llm_grok

        logger.warning("No LLM available for generation (requested: %s)", llm_choice)
        return None

    # ------------------------------------------------------------------
    # LangChain pipeline
    # ------------------------------------------------------------------

    def _setup_prompt_chain(self) -> Runnable:
        """Build a reusable LangChain prompt-assembly chain."""
        input_prep_chain = RunnablePassthrough.assign(
            game_data=RunnableLambda(lambda x: json.dumps(x["data"], indent=2, default=str)),
            prompt_text=RunnableLambda(lambda x: self._build_llm_prompt(x["data"])),
        )
        template = PromptTemplate.from_template(
            "Here is the input data:\n\n{game_data}\n\nInstruction: {prompt_text}"
        )
        return input_prep_chain | template

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        """Return the prompt string for *data*. Subclasses must override."""
        raise NotImplementedError("Subclass must implement '_build_llm_prompt'")

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------

    def _derive_topic_slug(self, data: Union[ExtractedInfo, str]) -> str:
        """Derive a human-readable topic slug from input data."""
        summarizer_name = self.__class__.__name__
        if isinstance(data, str):
            clean_str = re.sub(r"[^\w\s-]", "", data)[:40].strip().replace(" ", "_")
            return f"{summarizer_name}_{clean_str}"

        if not isinstance(data, dict):
            return summarizer_name

        date_str = str(data.get("date", "")).replace("-", "")

        # Game summaries: away at home
        if "home_team" in data and "away_team" in data:
            home = re.sub(r"[^\w-]", "", str(data["home_team"])).replace(" ", "_")
            away = re.sub(r"[^\w-]", "", str(data["away_team"])).replace(" ", "_")
            rant = "_rant" if "losing_team" in data else ""
            prefix = f"{date_str}_" if date_str else ""
            return f"{prefix}{summarizer_name}_{away}_at_{home}{rant}"

        # News articles
        if "title" in data:
            title_clean = re.sub(r"[^\w\s-]", "", str(data["title"]))[:40].strip().replace(" ", "_")
            prefix = f"{date_str}_" if date_str else ""
            return f"{prefix}{summarizer_name}_{title_clean}"

        # Email news
        if "subject" in data:
            subj_clean = re.sub(r"[^\w\s-]", "", str(data["subject"]))[:40].strip().replace(" ", "_")
            prefix = f"{date_str}_" if date_str else ""
            return f"{prefix}{summarizer_name}_{subj_clean}"

        # Horoscope / sky
        if "name" in data:
            name_clean = re.sub(r"[^\w-]", "", str(data["name"])).replace(" ", "_")
            prefix = f"{date_str}_" if date_str else ""
            return f"{prefix}{summarizer_name}_{name_clean}"

        return f"{summarizer_name}_{list(data.keys())[:2]}"

    def _compute_cache_key(
        self,
        data: ExtractedInfo,
        prompt_text: str,
        llm_choice: str,
        model_name: str,
    ) -> str:
        """Compute deterministic SHA-256 cache key."""
        try:
            data_json = json.dumps(data, sort_keys=True, default=str)
        except Exception:
            data_json = str(data)

        payload = f"{self.__class__.__name__}|{prompt_text}|{data_json}|{llm_choice.lower()}|{model_name}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate_llm_summary(
        self,
        data: Union[ExtractedInfo, str],
        llm_choice: str,
        use_cache: Optional[bool] = None,
        refresh_cache: Optional[bool] = None,
        cache_ttl_days: Optional[int] = None,
    ) -> str:
        """Run the generation pipeline (with SQLite caching) and return summary string."""
        if isinstance(data, str):
            return data

        should_use_cache = self.config.use_cache if use_cache is None else use_cache
        should_refresh_cache = self.config.refresh_cache if refresh_cache is None else refresh_cache
        ttl_days = self.config.cache_ttl_days if cache_ttl_days is None else cache_ttl_days

        llm_choice_clean = (llm_choice or "gemini").lower()
        model_name = (
            self.config.grok_model
            if llm_choice_clean == "grok"
            else self.config.gemini_model
        )

        prompt_text = ""
        try:
            prompt_text = self._build_llm_prompt(data)
        except Exception:
            pass

        cache_key = self._compute_cache_key(data, prompt_text, llm_choice_clean, model_name)
        topic_slug = self._derive_topic_slug(data)

        # 1. Check cache if caching is active and not refreshing
        if should_use_cache and not should_refresh_cache:
            try:
                from ..db import llm_cache_get

                cached_response = llm_cache_get(cache_key)
                if cached_response is not None:
                    word_count = len(cached_response.split())
                    logger.info(
                        "LLM cache HIT for %s (%d words, key=%s)",
                        topic_slug,
                        word_count,
                        cache_key[:8],
                    )
                    return cached_response
            except Exception as exc:
                logger.debug("Cache lookup failed: %s", exc)

        # 2. Invoke LLM on cache miss or cache refresh
        try:
            llm_instance: Runnable = self._select_llm_instance(llm_choice_clean)
            if not llm_instance:
                return self.config.default_text

            full_pipeline = (
                self._setup_prompt_chain() | llm_instance | StrOutputParser()
            )

            chain_input: PromptChainInput = {"data": data, "llm_choice": llm_choice_clean}

            summary: str = full_pipeline.invoke(chain_input)
            word_count = len(summary.split())
            logger.info("LLM summary generated: %d words (via %s)", word_count, llm_choice_clean)

            # 3. Save generated response to cache
            if should_use_cache and summary and summary != self.config.default_text:
                try:
                    from ..db import llm_cache_save

                    llm_cache_save(
                        cache_key=cache_key,
                        topic_slug=topic_slug,
                        summarizer=self.__class__.__name__,
                        llm_provider=llm_choice_clean,
                        model_name=model_name,
                        prompt_preview=prompt_text[:500],
                        response_text=summary,
                        ttl_days=ttl_days,
                    )
                    logger.info("LLM response cached for %s (key=%s)", topic_slug, cache_key[:8])
                except Exception as exc:
                    logger.warning("Failed to save LLM cache for %s: %s", topic_slug, exc)

            return summary

        except ValueError as ve:
            logger.error("LLM configuration error: %s", ve)
            return "Summary generation failed due to configuration issue."
        except Exception as exc:
            logger.error("LLM summary generation failed: %s", exc)
            return "Summary generation failed."

    def generate_summary(
        self,
        llm_choice: Union[str, ExtractedInfo] = "gemini",
        data: Union[ExtractedInfo, str] = {"data": "dummy"},
        use_cache: Optional[bool] = None,
        refresh_cache: Optional[bool] = None,
        cache_ttl_days: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Public entry point: generate and return the summary string."""
        if isinstance(llm_choice, dict):
            data = llm_choice
            llm_choice = kwargs.get("llm_choice_override", "gemini")

        return self._generate_llm_summary(
            data,
            llm_choice,
            use_cache=use_cache,
            refresh_cache=refresh_cache,
            cache_ttl_days=cache_ttl_days,
        )

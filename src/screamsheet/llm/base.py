"""Base LLM summarizer: LangChain chain wiring and shared generation logic.

Concrete summarizers live in llm/summarizers.py; they subclass this and
implement only ``_build_llm_prompt(data)``.

Callers that previously imported from ``llm.summary`` continue to work
unchanged — ``llm/summary.py`` re-exports everything from here.
"""
import json
import logging
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
    Base class for LLM-powered summarizers.

    Handles LLM initialisation, LangChain pipeline assembly, logging, and
    error recovery.  Concrete subclasses implement ``_build_llm_prompt(data)``
    and declare an optional ``_PROMPT_FILE`` class attribute pointing to a
    versioned ``.txt`` template relative to ``llm/prompts/``.

    Args:
        gemini_api_key: Google Gemini API key (``None`` disables Gemini).
        grok_api_key:   xAI Grok API key     (``None`` disables Grok).
        config:         :class:`~screamsheet.llm.config.LLMConfig` instance.
                        Defaults to :data:`~screamsheet.llm.config.DEFAULT_LLM_CONFIG`.

    Wiring a new input source
    -------------------------
    1. Subclass ``BaseGameSummaryGenerator`` in ``llm/summarizers.py``.
    2. Add a prompt file under ``llm/prompts/`` with ``{key}`` placeholders
       matching your ``ExtractedInfo`` dict keys.
    3. Set ``_PROMPT_FILE = Path("your_prompt.txt")`` on the subclass.
    4. ``_build_llm_prompt(data)`` is handled automatically by
       :class:`~screamsheet.llm.summarizers.FilePromptMixin` if you inherit it;
       otherwise override the method directly.
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
            print("--- Using GEMINI for generation ---")
            return self.llm_gemini
        elif llm_choice == "grok" and self.llm_grok:
            print("--- Using GROK for generation ---")
            return self.llm_grok

        print("--- No LLM available for generation ---")
        return None

    # ------------------------------------------------------------------
    # LangChain pipeline
    # ------------------------------------------------------------------

    def _setup_prompt_chain(self) -> Runnable:
        """Build a reusable LangChain prompt-assembly chain."""
        input_prep_chain = RunnablePassthrough.assign(
            game_data=RunnableLambda(lambda x: json.dumps(x["data"], indent=2)),
            prompt_text=RunnableLambda(lambda x: self._build_llm_prompt(x["data"])),
        )
        template = PromptTemplate.from_template(
            "Here is the input data:\n\n{game_data}\n\nInstruction: {prompt_text}"
        )
        return input_prep_chain | template

    def _build_llm_prompt(self, data: ExtractedInfo) -> str:
        """Return the prompt string for *data*.  Subclasses must override."""
        raise NotImplementedError("Subclass must implement '_build_llm_prompt'")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate_llm_summary(
        self, data: Union[ExtractedInfo, str], llm_choice: str
    ) -> str:
        """Run the full generation pipeline and return the summary string."""
        if isinstance(data, str):
            return data

        try:
            llm_instance: Runnable = self._select_llm_instance(llm_choice)

            full_pipeline = (
                self._setup_prompt_chain() | llm_instance | StrOutputParser()
            )

            chain_input: PromptChainInput = {"data": data, "llm_choice": llm_choice}

            # Log a prompt preview before invoking (best-effort)
            try:
                prompt_builder = self._setup_prompt_chain()
                try:
                    prompt_preview = prompt_builder.invoke(chain_input)
                    if hasattr(prompt_preview, "to_string"):
                        prompt_preview = prompt_preview.to_string()
                    else:
                        prompt_preview = str(prompt_preview)
                    logger.info(
                        "LLM prompt preview (trimmed 4000 chars):\n%s",
                        prompt_preview[:4000],
                    )
                    logger.debug("Full LLM prompt length: %d", len(prompt_preview))
                except Exception as exc:
                    logger.warning("Could not render LLM prompt preview: %s", exc)
            except Exception:
                pass

            if not llm_choice:
                return self.config.default_text

            summary: str = full_pipeline.invoke(chain_input)
            return summary

        except ValueError as ve:
            print(f"Configuration Error: {ve}")
            return "Summary generation failed due to configuration issue."
        except Exception as exc:
            print(f"Error generating summary with LLM: {exc}")
            return "Summary generation failed."

    def generate_summary(
        self,
        llm_choice: str = "gemini",
        data: Union[ExtractedInfo, str] = {"data": "dummy"},
        **kwargs,
    ) -> str:
        """Public entry point: generate and return the summary string."""
        return self._generate_llm_summary(data, llm_choice)

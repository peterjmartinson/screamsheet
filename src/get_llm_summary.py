import os
import json
from typing import Optional, Dict, Union, Any, List
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import logging

# Configure a module-level logger for LLM prompt/debug output
logger = logging.getLogger('screamsheet.llm')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- LANGCHAIN IMPORTS ---
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough, RunnableParallel
# -------------------------

# Define the common type for extracted game info
ExtractedInfo = Dict[str, Union[str, int, float, List[Any]]]
# Define the input type for the prompt chain
PromptChainInput = Dict[str, Union[str, ExtractedInfo]]


class BaseGameSummaryGenerator:
    """
    Base class for generating summaries.
    """

    _DEFAULT_TEXT: str = 'howdy, folks.  test text here'
    _DEFAULT_MODEL: str = 'gemini-2.5-flash'
    _GROK_MODEL: str = 'grok-4-fast'
    _GROK_BASE_URL: str = "https://api.x.ai/v1"

    def __init__(self,
                 gemini_api_key: Optional[str] = None,
                 grok_api_key: Optional[str] = None) -> None:
        """Initializes the generator with API keys for multiple LLMs."""
        
        self.api_keys: Dict[str, Optional[str]] = {
            'gemini': gemini_api_key,
            'grok': grok_api_key
        }
        self.llm_gemini = self._initialize_gemini(gemini_api_key)
        self.llm_grok = self._initialize_grok(grok_api_key)
        self._cwd = Path.cwd()

    def _initialize_gemini(self, api_key: Optional[str]) -> Optional[ChatGoogleGenerativeAI]:
        """Initializes the Gemini LLM object."""
        if not api_key:
            return None
        return ChatGoogleGenerativeAI(
            model=self._DEFAULT_MODEL,
            temperature=0.3,
            google_api_key=api_key
        )

    def _initialize_grok(self, api_key: Optional[str]) -> Optional[ChatOpenAI]:
        """Initializes the Grok (via OpenAI-compatible API) LLM object."""
        if not api_key:
            return None
        # Use ChatOpenAI for Grok since it uses an OpenAI-compatible endpoint
        return ChatOpenAI(
            model=self._GROK_MODEL,
            temperature=0.3,
            openai_api_key=api_key,
            base_url=self._GROK_BASE_URL,
            model_kwargs={"extra_headers": {"x-search-mode": "auto"}}
        )

    # The selection happens outside of the main chain definition.
    def _select_llm_instance(self, llm_choice: str) -> Union[Runnable, None]:
        """Dynamically selects the correct LLM instance."""
        llm_choice = llm_choice.lower()
        if llm_choice == 'gemini' and self.llm_gemini:
            print("--- Using GEMINI for generation ---")
            return self.llm_gemini
        elif llm_choice == 'grok' and self.llm_grok:
            print("--- Using GROK for generation ---")
            return self.llm_grok
        
        print("--- No LLM available for generation ---")
        return None

    def _setup_prompt_chain(self) -> Runnable:
        """
        Defines a simple, reusable LangChain composition for **prompt building and parsing**.
        This uses explicit composition (`.and_then()`) instead of the pipe operator (`|`).
        """
        # 1. Initial Input Preparation (The map step)
        # We use RunnablePassthrough.assign to build the keys the template expects
        input_prep_chain = RunnablePassthrough.assign(
            game_data=RunnableLambda(
                lambda x: json.dumps(x['data'], indent=2)
            ),
            prompt_text=RunnableLambda(
                # We need the full `self` instance here, so we wrap the call
                lambda x: self._build_llm_prompt(x['data'])
            )
        )

        # 2. Prompt Template (This step takes the prepared inputs and renders the string)
        template = PromptTemplate.from_template(
            "Here is the raw data for a sports game:\n\n{game_data}\n\nNow, follow this instruction to summarize it: {prompt_text}"
        )

        # 3. Composition: Combine the preparation and the template
        # The output of input_prep_chain (a dict) is passed into the template (which expects a dict)
        final_prompt_builder = input_prep_chain | template

        return final_prompt_builder
    
    # --- ABSTRACT METHODS (Must be implemented by subclasses) ---
    def _build_llm_prompt(self, data: Union[ExtractedInfo, str]) -> str:
        """
        Constructs the LLM prompt instruction (e.g., "Write a 3-paragraph summary...").
        """
        raise NotImplementedError("Subclass must implement abstract method '_build_llm_prompt'")
    # -----------------------------------------------------------

    def _generate_llm_summary(self, data: Union[ExtractedInfo, str], llm_choice: str) -> str:
        """
        Executes the entire generation process using the chosen LLM.
        This method uses a simple imperative structure.
        """
        if isinstance(data, str):
            # If extraction failed, return the error message string
            return data

        try:
            # IMPERATIVE STEP 1: Get the required LLM instance
            llm_instance: Runnable = self._select_llm_instance(llm_choice)
            
            # IMPERATIVE STEP 2: Define the full pipeline (Prompt -> LLM -> Parser)
            # This is the simplest, most readable composition structure.
            full_pipeline = (
                self._setup_prompt_chain()
                | llm_instance
                | StrOutputParser()
            )

            # IMPERATIVE STEP 3: Structure the input for the prompt chain
            chain_input: PromptChainInput = {
                "data": data,
                "llm_choice": llm_choice
            }
                
            # IMPERATIVE STEP 4: Render a preview of the prompt for logging
            try:
                prompt_builder = self._setup_prompt_chain()
                try:
                    prompt_preview = prompt_builder.invoke(chain_input)
                    # LangChain returns a PromptValue object; convert to string
                    if hasattr(prompt_preview, 'to_string'):
                        prompt_preview = prompt_preview.to_string()
                    else:
                        prompt_preview = str(prompt_preview)
                    # Log a trimmed preview so logs don't explode; full prompt available at DEBUG
                    logger.info("LLM prompt preview (trimmed 4000 chars):\n%s", prompt_preview[:4000])
                    logger.debug("Full LLM prompt length: %d", len(prompt_preview))
                except Exception as e:
                    logger.warning("Could not render LLM prompt preview: %s", e)
            except Exception:
                # If building the preview fails, continue to invocation path
                pass

            # If no LLM is available, just return dummy text
            if not llm_choice:
                return self._DEFAULT_TEXT

            # IMPERATIVE STEP 5: Invoke the full pipeline
            summary: str = full_pipeline.invoke(chain_input)
            return summary
            
        except ValueError as ve:
            print(f"Configuration Error: {ve}")
            return "Summary generation failed due to configuration issue."
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."

    def generate_summary(
        self,
        llm_choice: str = 'gemini',
        data: Union[ExtractedInfo, str] = {'data': 'dummy'},
        **kwargs
    ) -> str:
        """
        Public method to generate the full game summary.
        """
        llm_summary = self._generate_llm_summary(data, llm_choice)
        return llm_summary

class NewsSummarizer(BaseGameSummaryGenerator):

    def _build_llm_prompt(self, data: Union[ExtractedInfo, str]) -> str:
        """
        Constructs the LLM prompt instruction (e.g., "Write a 3-paragraph summary...").
        """
        prompt = """
        You are a professional journalist. Write a tight, lively summary of the
        included news topic. Start clean, but get more wild towards the end.
        Hit the big story, toss in a couple key highlights, and dig up the
        freshest dirt with real sources.

        These are the requirements
        - Break summary up into logical paragraphs of one to three sentences, but limit word count to 300.
        - Use plain text, no markdown or formatting marks.
        - Use humor where you can.
        - Use real words, no "'em", "youse", "snaggin'", or any other words designed to look like they sound.
        """
        return prompt

class NHLGameSummarizer(BaseGameSummaryGenerator):

    def _build_llm_prompt(self, data: Union[ExtractedInfo, str]) -> str:
        """
        Constructs the LLM prompt instruction (e.g., "Write a 3-paragraph summary...").
        """
        prompt = f"""
            You are a hilarious sports journalist writing a game recap for a clever
            10-year-old hockey fan who loves the sport and wants to laugh while
            learning about what happened. Your reader knows what goals, penalties,
            and power plays are - don't waste words on basics.

            TONE: Funny, witty, and slightly snarky. Use vivid descriptions and
            playful language. Roast bad plays gently (e.g., "that pass had all
            the accuracy of a water balloon thrown backwards"). Celebrate awesome
            moments with enthusiasm (e.g., "that snipe was absolutely FILTHY").
            Include clever wordplay or jokes where appropriate. Make your young
            reader chuckle - be edgy and cheeky but keep it clean (no swear words).

            The entire summary must be 300 words or less in a single continuous
            paragraph of plain text (no markdown, bolding, italics, or special
            formatting). Make it entertaining above all else - this should feel
            like reading a funny story, not a boring news report.

            You must define exactly one obscure or technical hockey term by following
            it with an asterisk (e.g., term*). Choose something interesting like
            'zone exit', 'board battle', 'forechecking pressure', 'odd-man rush',
            'high slot', 'cycle', 'cross-ice pass', or similar tactical/positional
            concepts. Avoid defining basic terms like 'goal', 'penalty', 'hit',
            'shot', 'save', or 'takeaway'. The definition should appear on a
            separate line at the end, prefixed by an asterisk with a brief but
            insightful explanation that a 10-year-old would understand and find
            interesting (e.g., *A zone exit is when...).

            Game details to include:
            Home Team: {data['home_team']}
            Away Team: {data['away_team']}
            Final Score: {data['home_team']} {data['home_score']} to {data['away_team']} {data['away_score']}

            Narrative snippets (for context, include highlights from each period in order): {data['narrative_snippets']}

            Write the funny, entertaining recap now. Make that kid giggle!
        """
        return prompt

# --- Main Execution ---
if __name__ == "__main__":
    # NOTE: Set your actual API keys here for real LLM calls.
    # For this example, we will treat the LLM objects as if they exist
    # (i.e., we are relying on the LLM client objects being set up,
    # even if they won't make a real API call without a key).
    
    # Passing None for keys allows the initialization to proceed without failure,
    # but the select method will raise a ValueError if it expects an LLM to be available.
    story = {
        'title': 'Unanimous for 4th time, Ohtani owns 2nd-most MVPs in MLB history',
        'summary': "By definition, it doesn't get much more valuable than what Shohei Ohtani brings to the table, impacting the game at the plate and on the mound -- and doing both at an elite level. And for the third year in a row, the Dodgers' two-way superstar has some hardware to show for it.  Ohtani was unanimously named the National League MVP on Thursday night, as voted by the Baseball Writers' Association of America and announced on MLB Network. He beat out runner-up Kyle Schwarber of the Phillies and third-place finisher Juan Soto of the Mets for the fourth MVP Award of his Major League career, and his second in as many seasons as a Dodger."
    }
    generator = NewsSummarizer(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "MOCK_GEMINI_KEY"),
        grok_api_key=os.getenv("GROK_API_KEY", "MOCK_GROK_KEY")
    )

    print("\n" + "="*50)
    print("DEMO 1: Using the 'gemini' choice")
    print("="*50)
    
    # Since we are using mock keys, this will likely raise a configuration error 
    # if LangChain tries to validate the key immediately, but it demonstrates 
    # the correct composition logic.
    try:
        summary_gemini = generator.generate_summary(llm_choice='gemini', story=story)
        print("\n--- Summary Result (Gemini Chain) ---")
        print(summary_gemini)
    except Exception as e:
        print(f"\n[Execution Mocked] Successfully composed chain, but invocation failed: {e}")

    print("\n" + "="*50)
    print("DEMO 2: Using the 'grok' choice")
    print("="*50)

    try:
        summary_grok = generator.generate_summary(llm_choice='grok', story=story)
        print("\n--- Summary Result (Grok Chain) ---")
        print(summary_grok)
    except Exception as e:
        print(f"\n[Execution Mocked] Successfully composed chain, but invocation failed: {e}")


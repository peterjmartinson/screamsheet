import os
import json
from typing import Optional, Dict, Union, Any, List, Callable
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

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
    Base class for generating summaries. Refactored to use a simpler, 
    imperative composition structure instead of complex LCEL pipes.
    """

    _DEFAULT_TEXT: str = 'howdy, folks.  test text here'
    _DEFAULT_MODEL: str = 'gemini-2.5-flash'
    _GROK_MODEL: str = 'grok-4'
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
        if not api_key: return None
        return ChatGoogleGenerativeAI(
            model=self._DEFAULT_MODEL,
            temperature=0.3,
            google_api_key=api_key
        )

    def _initialize_grok(self, api_key: Optional[str]) -> Optional[ChatOpenAI]:
        """Initializes the Grok (via OpenAI-compatible API) LLM object."""
        if not api_key: return None
        # Use ChatOpenAI for Grok since it uses an OpenAI-compatible endpoint
        return ChatOpenAI(
            model=self._GROK_MODEL,
            temperature=0.3,
            openai_api_key=api_key,
            base_url=self._GROK_BASE_URL,
            model_kwargs={"extra_headers": {"x-search-mode": "auto"}}
        )

    # Note: This method now returns the LLM *instance*, not a Runnable.
    # The selection happens outside of the main chain definition.
    def _select_llm_instance(self, llm_choice: str) -> Runnable:
        """Dynamically selects the correct LLM instance."""
        llm_choice = llm_choice.lower()
        if llm_choice == 'gemini' and self.llm_gemini:
            print("--- Using GEMINI for generation ---")
            return self.llm_gemini
        elif llm_choice == 'grok' and self.llm_grok:
            print("--- Using GROK for generation ---")
            return self.llm_grok
        
        raise ValueError(f"LLM choice '{llm_choice}' is invalid or API key is missing.")

    # --- REFACTORED CHAIN COMPOSITION ---

    def _setup_prompt_chain(self) -> Runnable:
        """
        Defines a simple, reusable LangChain composition for **prompt building and parsing**.
        This uses explicit composition (`.and_then()`) instead of the pipe operator (`|`).
        """
        # 1. Initial Input Preparation (The map step)
        # We use RunnablePassthrough.assign to build the keys the template expects
        input_prep_chain = RunnablePassthrough.assign(
            game_data=RunnableLambda(
                lambda x: json.dumps(x['extracted_info'], indent=2)
            ),
            prompt_text=RunnableLambda(
                # We need the full `self` instance here, so we wrap the call
                lambda x: self._build_llm_prompt(x['extracted_info'])
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
    
    # ------------------------------------


    # --- ABSTRACT METHODS (Must be implemented by subclasses) ---
    def _fetch_raw_game_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetches raw game data from the league API. Args depend on the league."""
        raise NotImplementedError("Subclass must implement abstract method '_fetch_raw_game_data'")

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Parses raw data and extracts essential game details for the LLM."""
        raise NotImplementedError("Subclass must implement abstract method '_extract_key_info'")

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """
        Constructs the LLM prompt instruction (e.g., "Write a 3-paragraph summary...").
        """
        raise NotImplementedError("Subclass must implement abstract method '_build_llm_prompt'")
    # -----------------------------------------------------------


    def _generate_llm_summary(self, extracted_info: Union[ExtractedInfo, str], llm_choice: str) -> str:
        """
        Executes the entire generation process using the chosen LLM.
        This method uses a simple imperative structure.
        """
        if isinstance(extracted_info, str):
            # If extraction failed, return the error message string
            return extracted_info

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
                "extracted_info": extracted_info,
                # Note: 'llm_choice' is not needed by the chain anymore, but useful for tracing
                "llm_choice": llm_choice 
            }
                
            # IMPERATIVE STEP 4: Invoke the full pipeline
            summary: str = full_pipeline.invoke(chain_input)
            return summary
            
        except ValueError as ve:
            print(f"Configuration Error: {ve}")
            return "Summary generation failed due to configuration issue."
        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            return "Summary generation failed."


    def generate_summary(self, llm_choice: str = 'gemini', **kwargs) -> str:
        """
        Public method to generate the full game summary.
        """
        raw_data: Optional[Dict[str, Any]] = self._fetch_raw_game_data(**kwargs)
        extracted_info: Union[ExtractedInfo, str] = self._extract_key_info(raw_data)
        llm_summary = self._generate_llm_summary(extracted_info, llm_choice)
        return llm_summary

class NewsSummarizer(BaseGameSummaryGenerator):

    def _fetch_raw_game_data(self, story: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Fetches raw game data from the league API. Args depend on the league.
        Assumes story = {'title': 'text', 'summary': 'text'}
        """
        return story

    def _extract_key_info(self, raw_data: Optional[Dict[str, Any]]) -> Union[ExtractedInfo, str]:
        """Parses raw data and extracts essential game details for the LLM."""
        return raw_data

    def _build_llm_prompt(self, extracted_info: ExtractedInfo) -> str:
        """
        Constructs the LLM prompt instruction (e.g., "Write a 3-paragraph summary...").
        """
        prompt = """
        You are a pro journalist who grew up in Philly. Write a tight, lively
        summary of the news topic below. Hit the big story, toss in a couple
        key highlights, and dig up the freshest dirt on X with real sources.

        These are the rules
        - Keep it around 300 words.
        - Use plain text, no markdown or formatting marks.
        - Use exactly one swear word, but make it count.
        - Slip in one or two quick funnies.
        - Use real words, no "'em", "youse", "snaggin'", or any other words designed to look like they sound.
        - Let a little raw emotion out, but don’t drown the facts.
        """
        return prompt

    def generate_summary(self, llm_choice: str = 'gemini', **kwargs) -> str:
        """
        Public method to generate the full game summary.
        """
        raw_data: Optional[Dict[str, Any]] = self._fetch_raw_game_data(**kwargs)
        extracted_info: Union[ExtractedInfo, str] = self._extract_key_info(raw_data)
        llm_summary = self._generate_llm_summary(extracted_info, llm_choice)
        return llm_summary


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


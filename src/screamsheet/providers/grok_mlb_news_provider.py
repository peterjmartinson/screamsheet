"""Grok-generated MLB news provider.

Instead of scraping an RSS feed, this provider asks Grok to search for
recent MLB stories directly, compose a full journalist-style article for
each one, and return them ready for the renderer.  No second summarization
pass is needed.
"""
import os
from datetime import datetime
from typing import List, Dict, Optional

from ..base import DataProvider


_GROK_MODEL = 'grok-3-fast'
_GROK_BASE_URL = 'https://api.x.ai/v1'

_SYSTEM_PROMPT = (
    "You are a sharp, witty sports journalist covering Major League Baseball. "
    "You have access to live news search. When asked for a story you will search "
    "recent news (past 24 hours) and write a complete article. "
    "Do NOT cite X (Twitter) or any social media post as your primary source — "
    "cite the original outlet, official team statement, or wire service instead."
)

_STORY_PROMPT_TEMPLATE = """\
Find and write a significant MLB news story from the past 24 hours.
{team_instruction}
{exclusion_instruction}

Format your response EXACTLY like this (two-line header, then body):
TITLE: <headline, 8 words or fewer>

BODY:
<full article, ~250-300 words, plain text, no markdown, no bullet points>

Requirements for the article body:
- Break into logical paragraphs of 1-3 sentences each.
- Start factual and clean, get livelier toward the end.
- Use humor where appropriate.
- Use real words — no slang contractions like "'em", "snaggin'", etc.
- Do NOT cite X, Twitter, or any social media as your primary source.
- Do NOT repeat any of the excluded headlines listed above.
"""


class GrokMLBNewsProvider(DataProvider):
    """
    Data provider that uses Grok (with live search) to generate MLB news articles.

    Each call to get_articles() makes `max_articles` sequential Grok requests,
    passing previously generated headlines as exclusions so stories don't repeat.

    Args:
        favorite_teams: Teams to feature first (first story biased toward
                        favorite_teams[0]).  Defaults to Phillies, Padres, Yankees.
        max_articles:   Number of articles to generate (default 4).
        grok_api_key:   xAI API key.  Falls back to GROK_API_KEY env var.
    """

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        grok_api_key: Optional[str] = None,
        **config,
    ):
        super().__init__(**config)
        self.favorite_teams = favorite_teams or ['Phillies', 'Padres', 'Yankees']
        self.max_articles = max_articles
        self._api_key = grok_api_key or os.getenv('GROK_API_KEY')
        self._client = self._init_client()
        self._articles_cache: Optional[List[Dict]] = None  # populated on first call

    # ------------------------------------------------------------------
    # DataProvider stubs
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self):
        return None

    # ------------------------------------------------------------------
    # Main public method
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """
        Generate `max_articles` unique MLB news articles via Grok.

        Returns a list of dicts compatible with the standard article shape:
            {'slot': 'Section N', 'entry': {title, summary, link, id, pub_date}}
        """
        if not self._client:
            print('GrokMLBNewsProvider: No Grok API key — cannot generate articles.')
            return []

        # Return cached results so shared provider instances don't re-query Grok
        if self._articles_cache is not None:
            return self._articles_cache

        today_str = datetime.now().strftime('%B %d, %Y')
        used_headlines: List[str] = []
        articles: List[Dict] = []

        for i in range(self.max_articles):
            # First story: try to feature the top favorite team
            if i == 0 and self.favorite_teams:
                team_instruction = (
                    f"Prefer a story that involves the {self.favorite_teams[0]} "
                    "if there is a significant one; otherwise pick the biggest MLB story."
                )
            else:
                team_instruction = "Pick the most significant or interesting MLB story available."

            if used_headlines:
                exclusion_lines = '\n'.join(f'  - {h}' for h in used_headlines)
                exclusion_instruction = (
                    f"Do NOT write about any of these already-covered stories:\n{exclusion_lines}"
                )
            else:
                exclusion_instruction = ''

            prompt = _STORY_PROMPT_TEMPLATE.format(
                team_instruction=team_instruction,
                exclusion_instruction=exclusion_instruction,
            ).strip()

            title, body = self._call_grok(prompt)
            if not title:
                print(f'GrokMLBNewsProvider: Empty response for article {i + 1}, skipping.')
                continue

            used_headlines.append(title)
            articles.append({
                'slot': f'Section {i + 1}',
                'entry': {
                    'id':               f'grok-mlb-{i + 1}-{datetime.now().timestamp()}',
                    'title':            title,
                    'summary':          body,
                    'link':             '',
                    'pub_date':         today_str,
                    'published_parsed': None,
                },
            })

        self._articles_cache = articles
        return articles

    def _init_client(self):
        """Build a ChatOpenAI-compatible Grok client, or return None."""
        if not self._api_key:
            return None
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=_GROK_MODEL,
                temperature=0.5,
                openai_api_key=self._api_key,
                base_url=_GROK_BASE_URL,
                model_kwargs={'extra_headers': {'x-search-mode': 'auto'}},
            )
        except Exception as e:
            print(f'GrokMLBNewsProvider: Failed to initialise Grok client: {e}')
            return None

    def _call_grok(self, user_prompt: str):
        """
        Call Grok with the system + user prompt.  Returns (title, body) tuple.
        Returns ('', '') on any failure.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        from langchain_core.output_parsers import StrOutputParser

        try:
            messages = [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            response: str = (self._client | StrOutputParser()).invoke(messages)
            return self._parse_response(response)
        except Exception as e:
            print(f'GrokMLBNewsProvider: Grok call failed: {e}')
            return '', ''

    @staticmethod
    def _parse_response(response: str):
        """
        Parse the structured TITLE / BODY response from Grok.
        Returns (title, body) strings.
        """
        title = ''
        body = ''
        lines = response.strip().splitlines()

        for i, line in enumerate(lines):
            if line.upper().startswith('TITLE:'):
                title = line[len('TITLE:'):].strip()
            elif line.upper().startswith('BODY:'):
                # Everything after the BODY: line
                body = '\n'.join(lines[i + 1:]).strip()
                break

        # Fallback: if no markers found, treat first line as title, rest as body
        if not title and lines:
            title = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()

        return title, body

    # ------------------------------------------------------------------
    # Required by NewsArticlesSection (sanitize_articles stub)
    # ------------------------------------------------------------------

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """Articles are already clean — pass through unchanged."""
        return articles

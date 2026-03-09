"""Presidential Screamsheet: assembles the full political news PDF."""
from datetime import datetime
from typing import List, Optional

from ..base import Section
from ..news.base_news import NewsScreamsheet
from ..renderers import NewsArticlesSection
from ..providers.political_news_provider import PoliticalNewsProvider


class PresidentialScreamsheet(NewsScreamsheet):
    """
    Assembles a one-page 'Presidential Screamsheet' PDF.

    Fetches political news from 7 RSS feeds and the White House briefing
    room, scores and deduplicates stories, optionally summarizes via LLM,
    and renders the top four to a printable PDF.

    Usage::

        from screamsheet.political import PresidentialScreamsheet

        sheet = PresidentialScreamsheet(output_filename="Files/presidential.pdf")
        sheet.generate()

    Or via the factory::

        from screamsheet import ScreamsheetFactory
        sheet = ScreamsheetFactory.create_presidential_screamsheet("Files/presidential.pdf")
        sheet.generate()
    """

    def __init__(
        self,
        output_filename: str,
        max_articles: int = 4,
        date: Optional[datetime] = None,
    ):
        super().__init__(
            news_source="Presidential Screamsheet",
            output_filename=output_filename,
            include_weather=False,
            date=date,
        )
        self.max_articles = max_articles
        self.provider = PoliticalNewsProvider(max_articles=self.max_articles)

    def get_title(self) -> str:
        return "Presidential Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        return None

    def build_sections(self) -> List[Section]:
        return [
            NewsArticlesSection(
                title="Top Stories",
                provider=self.provider,
                max_articles=2,
                start_index=0,
            ),
            NewsArticlesSection(
                title="More Stories",
                provider=self.provider,
                max_articles=2,
                start_index=2,
            ),
        ]


# ---------------------------------------------------------------------------
# Stand-alone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    from pathlib import Path

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    today_str = datetime.now().strftime("%Y%m%d")
    out = Path("Files") / f"presidential_screamsheet_{today_str}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    sheet = PresidentialScreamsheet(output_filename=str(out))
    generated = sheet.generate()
    print(f"Generated: {generated}")

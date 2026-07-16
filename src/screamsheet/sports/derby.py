"""MLB Home Run Derby screamsheet implementation for PDF generation."""
from datetime import datetime
from typing import List, Optional

from ..base import BaseScreamsheet, Section
from ..providers.mlb_provider import MLBDataProvider
from ..renderers.derby_section import HomeRunDerbySection


class HomeRunDerbyScreamsheet(BaseScreamsheet):
    """Specialized PDF Screamsheet for the MLB Home Run Derby exhibition event."""

    def __init__(
        self,
        output_filename: str,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        game_pk: Optional[int] = None,
    ):
        """Initialize the Home Run Derby PDF screamsheet."""
        super().__init__(output_filename=output_filename, date=date, display_date=display_date)
        self.provider = MLBDataProvider()
        self.game_pk = game_pk

    def get_title(self) -> str:
        """Return the main header title."""
        return "MLB Home Run Derby"

    def get_subtitle(self) -> Optional[str]:
        """Return the subtitle line shown in the PDF header."""
        return "Screamsheet Special Edition"

    def build_sections(self) -> List[Section]:
        """Build and return all sections to be rendered into the PDF."""
        return [
            HomeRunDerbySection(
                title="Home Run Derby Results",
                provider=self.provider,
                date=self.date,
                game_pk=self.game_pk,
            )
        ]

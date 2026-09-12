"""Unified news scoring engine for political and sports screamsheets."""
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Core political keyword weights
POLITICAL_KEYWORD_WEIGHTS: Dict[str, int] = {
    # Core presidential / White House
    "white house": 8,
    "executive order": 7,
    "trump": 10,
    "president": 6,
    # Domestic policy hot-buttons
    "tariff": 6,
    "tariffs": 6,
    "immigration": 5,
    "border": 4,
    "inflation": 4,
    "federal reserve": 5,
    "congress": 4,
    "senate": 4,
    "house of representatives": 4,
    # Key international actors
    "xi jinping": 7,
    "xi": 5,
    "putin": 5,
    "zelensky": 5,
    "netanyahu": 5,
    "modi": 4,
    "macron": 4,
    "kim jong": 6,
    # Geopolitical topics
    "ukraine": 5,
    "russia": 4,
    "china": 4,
    "nato": 5,
    "israel": 4,
    "gaza": 4,
    "taiwan": 5,
    "north korea": 6,
    # Trade / foreign policy
    "diplomacy": 5,
    "sanctions": 5,
    "trade war": 6,
    "trade deal": 5,
    # Key Washington institutions
    "supreme court": 5,
    "department of justice": 5,
    "doj": 4,
    "fbi": 4,
    "cia": 4,
    "pentagon": 4,
    # Tech power / government efficiency
    "musk": 5,
    "elon": 4,
    "spacex": 3,
    "tesla": 3,
}


class BaseNewsScorer:
    """Base news scoring class with shared substance-gating and quality metrics."""

    def calculate_substance_multiplier(self, text: str) -> float:
        """Calculate quality multiplier based on text richness/word count.

        - Empty text: 0.0
        - Under 30 words: 0.4
        - 120 words or more: 1.0
        - Between 30 and 120 words: linear scale from 0.4 to 1.0
        """
        words = len(text.split())
        if words == 0:
            return 0.0
        if words < 30:
            return 0.4
        if words >= 120:
            return 1.0
        return round(0.4 + 0.6 * ((words - 30) / 90.0), 3)

    def has_substantial_text(self, text: str, min_words: int = 40) -> bool:
        """Return True if text meets or exceeds minimum word count."""
        return len(text.split()) >= min_words

    def score(self, entry: Dict[str, Any]) -> int:
        """Score an individual article entry. Subclasses must implement."""
        raise NotImplementedError


class PoliticalNewsScorer(BaseNewsScorer):
    """Score political news entries with keyword weights and White House substance-gating."""

    def __init__(
        self,
        keyword_weights: Optional[Dict[str, int]] = None,
        white_house_bonus: int = 25,
        min_white_house_words: int = 60,
    ) -> None:
        self.keyword_weights = keyword_weights or POLITICAL_KEYWORD_WEIGHTS
        self.white_house_bonus = white_house_bonus
        self.min_white_house_words = min_white_house_words

    def score(self, entry: Dict[str, Any]) -> int:
        """Return a relevance score for a political news entry.

        Applies:
        1. Keyword weighting over combined title and summary.
        2. White House authority bonus ONLY if substantial text is present.
        3. Substance scaling multiplier so hollow teasers are deranked.
        """
        title = (entry.get("title") or "").strip()
        summary = (entry.get("summary") or "").strip()
        combined = f"{title} {summary}".lower()

        if not combined.strip():
            return 0

        raw_score = 0
        already_matched: List[str] = []

        for keyword, weight in self.keyword_weights.items():
            if " " not in keyword:
                if any(keyword in phrase for phrase in already_matched):
                    continue
            if keyword in combined:
                raw_score += weight
                already_matched.append(keyword)

        # White House authority bonus: heavily weight official briefings/statements
        # ONLY if substantial text is available.
        source = entry.get("source") or ""
        link = entry.get("link") or ""
        is_wh = source == "White House" or "whitehouse.gov" in link

        wh_bonus = 0
        if is_wh:
            if self.has_substantial_text(summary, min_words=self.min_white_house_words):
                wh_bonus = self.white_house_bonus
            else:
                logger.debug(
                    "White House entry '%s' lacks substantial text (%d words); authority bonus skipped.",
                    title,
                    len(summary.split()),
                )

        # Substance scaling
        multiplier = self.calculate_substance_multiplier(summary)
        # Apply multiplier to raw keyword score, then add White House bonus
        total = int(round(raw_score * multiplier)) + wh_bonus

        # If it matched high-priority keywords but had short summary, ensure a non-zero floor
        if raw_score > 0 and total == 0:
            total = 1

        return total


class SportsNewsScorer(BaseNewsScorer):
    """Score sports news entries prioritizing favorite teams and penalizing junk."""

    def __init__(
        self,
        sport: str = "mlb",
        favorite_teams: Optional[List[str]] = None,
        junk_keywords: Optional[List[str]] = None,
    ) -> None:
        self.sport = sport.lower()
        self.favorite_teams = favorite_teams or []
        self.junk_keywords = [k.lower() for k in (junk_keywords or [])]

    def _get_team_match_patterns(self, team_name: str) -> Set[str]:
        patterns: Set[str] = {team_name.strip().lower()}
        try:
            from ..db import sport_get_team_aliases, sport_resolve_team

            resolved = sport_resolve_team(self.sport, team_name)
            if resolved:
                for alias in sport_get_team_aliases(self.sport, resolved["team_id"]):
                    patterns.add(alias.lower())
                if resolved.get("full_name"):
                    patterns.add(resolved["full_name"].lower())
                if resolved.get("abbrev"):
                    patterns.add(resolved["abbrev"].lower())
        except Exception:
            pass

        parts = team_name.strip().split()
        if len(parts) > 1:
            patterns.add(parts[-1].lower())  # Mascot / Nickname
            patterns.add(" ".join(parts[:-1]).lower())  # City

        return {p for p in patterns if len(p) > 1}

    def _matches_team(self, text: str, team_name: str) -> bool:
        patterns = self._get_team_match_patterns(team_name)
        text_lower = text.lower()
        for pat in patterns:
            regex = r"(?:\b|\A)" + re.escape(pat) + r"(?:\b|\Z)"
            if re.search(regex, text_lower):
                return True
        return False

    def score(self, entry: Dict[str, Any]) -> int:
        title = (entry.get("title") or "").strip()
        summary = (entry.get("summary") or "").strip()
        combined = f"{title} {summary}".lower()

        # Check junk
        for junk in self.junk_keywords:
            if junk in combined:
                return 0

        # Base score for any clean news
        score = 10

        # Tiered favorite team bonuses:
        # Tier 1 (1st team): +35
        # Tier 2 (2nd team): +20
        # Tier 3 (3rd+ teams): +10
        for idx, team in enumerate(self.favorite_teams):
            if self._matches_team(combined, team):
                if idx == 0:
                    score += 35
                elif idx == 1:
                    score += 20
                else:
                    score += 10
                break  # Don't double count multiple favorite matches on same team

        multiplier = self.calculate_substance_multiplier(summary)
        return int(round(score * multiplier))


class ClusterScorer:
    """Score grouped topic clusters based on anchor article and multi-source corroboration."""

    def __init__(
        self,
        multi_source_bonus_2: int = 15,
        multi_source_bonus_3_plus: int = 30,
        min_cluster_words: int = 80,
    ) -> None:
        self.multi_source_bonus_2 = multi_source_bonus_2
        self.multi_source_bonus_3_plus = multi_source_bonus_3_plus
        self.min_cluster_words = min_cluster_words

    def score_cluster(
        self,
        articles: List[Dict[str, Any]],
        anchor_score: Optional[int] = None,
    ) -> float:
        """Calculate score for a cluster of articles."""
        if not articles:
            return 0.0

        if anchor_score is None:
            anchor_score = max(a.get("score", 0) for a in articles)

        sources = {a.get("source") for a in articles if a.get("source")}
        num_sources = len(sources)

        # Multi-source bonus
        if num_sources >= 3:
            ms_bonus = self.multi_source_bonus_3_plus
        elif num_sources == 2:
            ms_bonus = self.multi_source_bonus_2
        else:
            ms_bonus = 0

        # Total information depth
        combined_text = " ".join(
            f"{a.get('title', '')} {a.get('summary', '')}" for a in articles
        )
        total_words = len(combined_text.split())

        substance_bonus = 0
        if total_words < self.min_cluster_words:
            # Thin cluster penalty
            penalty_factor = 0.5
        elif total_words >= 200:
            substance_bonus = 5
            penalty_factor = 1.0
        else:
            penalty_factor = 1.0

        final_score = (anchor_score + ms_bonus + substance_bonus) * penalty_factor
        return round(final_score, 1)

"""XKCD comic data provider.

Fetches latest comic on release days (MWF) and random unseen comics on off days.
Tracks all retrieved comics in screamsheet.db.
"""
from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional
import requests

from ..db.xkcd_db import get_seen_comic_nums, is_comic_seen, record_comic

logger = logging.getLogger("screamsheet.xkcd.provider")

XKCD_LATEST_ENDPOINT = "https://xkcd.com/info.0.json"
XKCD_BY_NUM_ENDPOINT = "https://xkcd.com/{num}/info.0.json"
DEFAULT_USER_AGENT = "screamsheet/1.0 (https://github.com/peterjmartinson/screamsheet)"


class XKCDProvider:
    """Provider for fetching XKCD comic metadata with deduplication and random fallback."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        timeout: int = 15,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}

    def fetch_latest_comic_metadata(self) -> Optional[Dict[str, Any]]:
        """Fetch the current newest comic metadata from xkcd.com."""
        try:
            resp = requests.get(XKCD_LATEST_ENDPOINT, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch latest XKCD comic from %s: %s", XKCD_LATEST_ENDPOINT, e)
            return None

    def fetch_comic_by_num(self, num: int) -> Optional[Dict[str, Any]]:
        """Fetch comic metadata for a specific issue number."""
        if num == 404:
            return None
        url = XKCD_BY_NUM_ENDPOINT.format(num=num)
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch XKCD comic #%d from %s: %s", num, url, e)
            return None

    def get_comic(self) -> Optional[Dict[str, Any]]:
        """
        Get the comic for today's screamsheet.

        - If the latest live comic is new (unseen), records and returns it.
        - If the latest live comic was already seen (e.g. off-days: Tue, Thu, weekends),
          picks a random unseen comic from 1 to latest_num (excluding 404), records and returns it.
        """
        latest_data = self.fetch_latest_comic_metadata()
        if not latest_data or "num" not in latest_data:
            logger.warning("Could not obtain latest XKCD comic metadata.")
            return None

        latest_num = int(latest_data["num"])

        # Check if latest release is unseen
        if not is_comic_seen(latest_num, db_path=self.db_path):
            logger.info("New XKCD comic detected: #%d (%s)", latest_num, latest_data.get("title"))
            record_comic(latest_data, is_latest=True, db_path=self.db_path)
            return latest_data

        # Off-day or already seen latest comic: find an unseen random comic
        seen_nums = get_seen_comic_nums(db_path=self.db_path)
        all_candidates = set(range(1, latest_num + 1)) - {404}
        unseen_candidates = list(all_candidates - seen_nums)

        if unseen_candidates:
            selected_num = random.choice(unseen_candidates)
            logger.info("Off-day or latest already seen; selected random unseen XKCD comic #%d", selected_num)
            comic_data = self.fetch_comic_by_num(selected_num)
            if comic_data:
                record_comic(comic_data, is_latest=False, db_path=self.db_path)
                return comic_data

        # Fallback if all have been seen or random fetch failed: pick any random comic
        fallback_pool = [n for n in range(1, latest_num + 1) if n != 404]
        fallback_num = random.choice(fallback_pool) if fallback_pool else latest_num
        fallback_data = self.fetch_comic_by_num(fallback_num)
        return fallback_data or latest_data

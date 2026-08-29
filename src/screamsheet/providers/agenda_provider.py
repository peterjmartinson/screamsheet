"""Agenda data provider communicating with the random-task REST API."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests

from ..briefing.constants import DEFAULT_AGENDA_ENDPOINT

logger = logging.getLogger(__name__)


class AgendaProvider:
    """
    Fetches daily agenda events and tasks from the random-task REST API.
    """

    def __init__(
        self,
        payload: Optional[Dict[str, Any]] = None,
        api_url: str = DEFAULT_AGENDA_ENDPOINT,
        timeout: int = 20,
    ):
        self.payload = payload or {}
        self.api_url = api_url.rstrip("/") if api_url else DEFAULT_AGENDA_ENDPOINT
        self.timeout = timeout

    def get_day_agenda(self, date: datetime) -> Dict[str, Any]:
        """Fetch agenda for a specific single date."""
        date_str = date.strftime("%Y-%m-%d")
        url = f"{self.api_url}?date={date_str}"
        try:
            resp = requests.post(
                url,
                json=self.payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch agenda for %s from %s: %s", date_str, url, e)
            return {"date": date_str, "agenda": [], "sections": []}

    def get_multi_day_agenda(self, start_date: datetime, num_days: int = 6) -> List[Dict[str, Any]]:
        """
        Fetch agendas for start_date and the following (num_days - 1) days.
        Returns a list of agenda data dicts ordered chronologically.
        """
        results = []
        for offset in range(num_days):
            target = start_date + timedelta(days=offset)
            data = self.get_day_agenda(target)
            results.append(data)
        return results

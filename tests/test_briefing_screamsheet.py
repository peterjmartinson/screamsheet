import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from screamsheet.factory import ScreamsheetFactory
from screamsheet.briefing import MorningBriefingScreamsheet
from screamsheet.providers.agenda_provider import AgendaProvider
from screamsheet.order import BriefingOrderOptions, ScreamsheetOrder, OutputOrderOptions
from screamsheet.runner import run_order


MOCK_AGENDA_DATA = {
    "date": "2026-08-28",
    "metadata": {"total_events": 1, "total_tasks": 1},
    "agenda": [
        {
            "id": "1",
            "type": "event",
            "title": "Morning Standup",
            "time": "09:00 AM - 09:30 AM",
            "accessory": "Room 101",
        }
    ],
    "sections": [
        {
            "title": "Work",
            "tasks": [
                {
                    "id": "t1",
                    "title": "Review PR",
                    "priority": "high",
                    "assignee": "Peter",
                }
            ],
        }
    ],
}


def test_agenda_provider_mock():
    provider = AgendaProvider(payload={}, api_url="https://fake.url")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_AGENDA_DATA
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        day_data = provider.get_day_agenda(datetime(2026, 8, 28))
        assert day_data["date"] == "2026-08-28"
        assert len(day_data["agenda"]) == 1

        multi = provider.get_multi_day_agenda(datetime(2026, 8, 28), num_days=2)
        assert len(multi) == 2


def test_briefing_screamsheet_creation(tmp_path):
    out_pdf = str(tmp_path / "briefing.pdf")
    sheet = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf,
        subscriber_name="Peter",
        payload={},
        include_weather=False,
        date=datetime(2026, 8, 28),
    )
    assert isinstance(sheet, MorningBriefingScreamsheet)
    assert sheet.get_title() == "Screamsheet"
    assert sheet.get_subtitle() == "Peter's Morning Briefing"


def test_briefing_screamsheet_generate(tmp_path):
    out_pdf = str(tmp_path / "test_briefing.pdf")
    sheet = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf,
        payload={},
        include_weather=False,
        date=datetime(2026, 8, 28),
    )

    with patch.object(AgendaProvider, "get_day_agenda", return_value=MOCK_AGENDA_DATA):
        pdf_path = sheet.generate()
        assert pdf_path == out_pdf


def test_runner_briefing_order(tmp_path):
    order = ScreamsheetOrder(
        output=OutputOrderOptions(directory=str(tmp_path)),
        briefing=BriefingOrderOptions(
            payload={},
            api_url="https://test.url",
            upcoming_days=1,
        ),
    )
    with patch.object(AgendaProvider, "get_day_agenda", return_value=MOCK_AGENDA_DATA), \
         patch("screamsheet.briefing.morning_briefing.WeatherSection.render", return_value=[]):
        res = run_order(order, today=datetime(2026, 8, 28))
        assert not res.errors
        assert any("BRIEFING" in name for name in res.sheets_generated)


def test_briefing_upcoming_days_modes(tmp_path):
    # Test upcoming_days = 1 (Today + Tomorrow mode)
    sheet_1 = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=str(tmp_path / "briefing_1.pdf"),
        payload={},
        include_weather=False,
        upcoming_days=1,
        date=datetime(2026, 8, 28),
    )
    with patch.object(AgendaProvider, "get_day_agenda", return_value=MOCK_AGENDA_DATA):
        pdf_1 = sheet_1.generate()
        assert pdf_1

    # Test upcoming_days = 5 (Next 5 Days mode)
    sheet_5 = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=str(tmp_path / "briefing_5.pdf"),
        payload={},
        include_weather=False,
        upcoming_days=5,
        date=datetime(2026, 8, 28),
    )
    with patch.object(AgendaProvider, "get_day_agenda", return_value=MOCK_AGENDA_DATA):
        pdf_5 = sheet_5.generate()
        assert pdf_5


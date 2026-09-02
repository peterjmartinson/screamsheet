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
    assert sheet.get_title() == "Peter's Screamsheet"
    assert sheet.get_subtitle() == "Morning Briefing"


def test_briefing_xkcd_toggle(tmp_path):
    out_pdf_with = str(tmp_path / "briefing_with_xkcd.pdf")
    sheet_with = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf_with,
        include_weather=False,
        include_xkcd=True,
        date=datetime(2026, 8, 28),
    )
    sections_with = sheet_with.build_sections()
    assert any(s.title == "XKCD" for s in sections_with)

    out_pdf_without = str(tmp_path / "briefing_no_xkcd.pdf")
    sheet_without = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf_without,
        include_weather=False,
        include_xkcd=False,
        date=datetime(2026, 8, 28),
    )
    sections_without = sheet_without.build_sections()
    assert not any(s.title == "XKCD" for s in sections_without)


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


def test_convert_time_to_eastern_and_duration():
    from screamsheet.renderers.agenda import convert_time_to_eastern_and_duration

    # Summer date (EDT is UTC-4): 01:30 PM UTC -> 9:30 AM EDT
    summer_dt = datetime(2026, 9, 1)
    res_summer = convert_time_to_eastern_and_duration("01:30 PM - 02:00 PM", ref_date=summer_dt)
    assert res_summer == "9:30 AM (30 min)"

    # Winter date (EST is UTC-5): 01:30 PM UTC -> 8:30 AM EST
    winter_dt = datetime(2026, 1, 15)
    res_winter = convert_time_to_eastern_and_duration("01:30 PM - 02:00 PM", ref_date=winter_dt)
    assert res_winter == "8:30 AM (30 min)"

    # All day event
    assert convert_time_to_eastern_and_duration("All Day", ref_date=summer_dt) == "All Day"


def test_sort_agenda_events():
    from screamsheet.renderers.agenda import sort_agenda_events

    ref_date = datetime(2026, 9, 1)
    events = [
        {"title": "Sophia Avery Schwane's birthday", "time": "02:00 AM - 03:00 AM"},  # 10:00 PM EDT
        {"title": "Work stand up", "time": "01:30 PM - 02:00 PM"},                   # 9:30 AM EDT
        {"title": "Buy two LEGO Advent calendars", "time": "01:00 PM - 02:00 PM"},   # 9:00 AM EDT
        {"title": "All Day Event B", "time": "All Day"},                              # Top / 00:00
        {"title": "All Day Event A", "time": "All Day"},                              # Top / 00:00
        {"title": "Apple Store visit", "time": "01:00 PM - 02:00 PM"},               # 9:00 AM EDT (ties with LEGO)
    ]

    sorted_evs = sort_agenda_events(events, ref_date=ref_date)
    titles = [e["title"] for e in sorted_evs]

    assert titles == [
        "All Day Event A",
        "All Day Event B",
        "Apple Store visit",
        "Buy two LEGO Advent calendars",
        "Work stand up",
        "Sophia Avery Schwane's birthday",
    ]


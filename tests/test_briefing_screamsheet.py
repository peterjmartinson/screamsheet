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
        include_email_news=False,
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
            include_email_news=False,
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
        include_email_news=False,
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
        include_email_news=False,
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


def test_format_due_date():
    from datetime import date as dt_date
    from screamsheet.renderers.agenda import format_due_date

    assert format_due_date("2026-09-15T16:00:00.000Z") == "2026-09-15"
    assert format_due_date("2026-09-15T12:00:00Z") == "2026-09-15"
    assert format_due_date("2026-09-15") == "2026-09-15"
    assert format_due_date(datetime(2026, 9, 15, 12, 0)) == "2026-09-15"
    assert format_due_date(dt_date(2026, 9, 15)) == "2026-09-15"
    assert format_due_date("") == ""
    assert format_due_date(None) == ""
    assert format_due_date("Not a date") == "Not a date"


def test_agenda_task_due_date_formatting():
    from screamsheet.renderers.agenda import TwoColumnAgendaSection

    test_data = [
        {
            "date": "2026-08-28",
            "agenda": [],
            "sections": [
                {
                    "title": "Homework",
                    "tasks": [
                        {
                            "id": "t1",
                            "title": "Math Problem Set",
                            "due": "2026-09-15T16:00:00.000Z",
                            "assignee": "Student",
                        }
                    ],
                }
            ],
        }
    ]

    section = TwoColumnAgendaSection(
        date=datetime(2026, 8, 28),
        multi_day_data=test_data,
        upcoming_days=1,
    )
    # Check PDF flowables
    tasks_flowables = section._render_tasks_block(test_data[0]["sections"])
    rendered_text = " ".join(getattr(f, "text", "") for f in tasks_flowables)
    assert "(Due: 2026-09-15)" in rendered_text
    assert "2026-09-15T16:00:00.000Z" not in rendered_text

    # Check Markdown
    md = section.render_markdown()
    assert "(Due: 2026-09-15)" in md
    assert "2026-09-15T16:00:00.000Z" not in md


def test_gmail_provider_sender_parsing():
    from screamsheet.providers.gmail_provider import _parse_sender

    assert _parse_sender("Not Even Wrong <donotreply@wordpress.com>") == ("Not Even Wrong", "donotreply@wordpress.com")
    assert _parse_sender("Punchbowl News <newsletters@punchbowl.news>") == ("Punchbowl News", "newsletters@punchbowl.news")
    assert _parse_sender("editor@politico.com") == ("Politico", "editor@politico.com")
    assert _parse_sender("") == ("", "")


def test_gmail_provider_fetch_mock():
    import email.message
    from datetime import timezone
    from screamsheet.providers.gmail_provider import GmailNewsProvider

    provider = GmailNewsProvider(username="test@gmail.com", app_password="secret_password", label="Morning Briefing")

    msg = email.message.EmailMessage()
    msg["Subject"] = "Daily Political Briefing"
    msg["From"] = "Punchbowl News <news@punchbowl.news>"
    msg["Date"] = "Fri, 28 Aug 2026 10:00:00 -0400"
    msg.set_content("Congress passes new infrastructure measure today.")

    with patch("imaplib.IMAP4_SSL") as mock_imap_cls:
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.select.return_value = ("OK", [b"1"])
        mock_imap.uid.side_effect = [
            ("OK", [b"101"]),
            ("OK", [(b"101 (RFC822 {100})", msg.as_bytes())]),
        ]

        emails = provider.fetch_emails(since=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc), lookback_hours=24)
        assert len(emails) == 1
        assert emails[0]["sender"] == "Punchbowl News"
        assert emails[0]["subject"] == "Daily Political Briefing"
        assert "Congress passes new infrastructure" in emails[0]["body"]


def test_email_news_summarizer():
    from screamsheet.llm.summary import EmailNewsSummarizer

    summarizer = EmailNewsSummarizer()
    prompt = summarizer._build_llm_prompt({
        "sender": "Not Even Wrong",
        "subject": "String Theory Update",
        "body": "A new paper tests quantum gravity predictions.",
    })
    assert "Not Even Wrong" in prompt
    assert "String Theory Update" in prompt
    assert "A new paper tests quantum gravity" in prompt


def test_email_news_section_render():
    from screamsheet.renderers.email_news import EmailNewsSection

    mock_provider = MagicMock()
    mock_provider.fetch_emails.return_value = [
        {
            "id": "1",
            "sender": "Not Even Wrong",
            "subject": "Quantum Gravity",
            "date": datetime(2026, 8, 28, 9, 0),
            "body": "Full body text of the article about quantum gravity.",
        }
    ]

    mock_summarizer_cls = MagicMock()
    mock_summarizer_inst = MagicMock()
    mock_summarizer_inst.generate_summary.return_value = (
        "Scientists observed a new quantum resonance. The implications could reshape modern physics in the next decade."
    )
    mock_summarizer_cls.return_value = mock_summarizer_inst

    sec = EmailNewsSection(
        provider=mock_provider,
        date=datetime(2026, 8, 28),
        summarizer_class=mock_summarizer_cls,
    )
    assert sec.page_slot == "back"
    assert sec.has_content() is True

    flowables = sec.render()
    assert len(flowables) > 0
    rendered_text = " ".join(getattr(f, "text", "") for f in flowables)
    assert "Not Even Wrong" in rendered_text
    assert "Quantum Gravity" in rendered_text
    assert "Scientists observed a new quantum resonance" in rendered_text

    md = sec.render_markdown()
    assert "Not Even Wrong" in md
    assert "Scientists observed a new quantum resonance" in md


def test_briefing_two_page_with_email_news(tmp_path):
    import re
    from pathlib import Path

    out_pdf = str(tmp_path / "briefing_two_page.pdf")

    mock_email_provider = MagicMock()
    mock_email_provider.fetch_emails.return_value = [
        {
            "id": "1",
            "sender": "Punchbowl News",
            "subject": "Morning Punch",
            "date": datetime(2026, 8, 28, 7, 30),
            "body": "Big policy developments overnight.",
        }
    ]

    mock_summarizer_inst = MagicMock()
    mock_summarizer_inst.generate_summary.return_value = (
        "Major policy moves were announced in Washington this morning. Key leaders reached a tentative budget compromise."
    )

    sheet = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf,
        subscriber_name="Peter",
        payload={},
        include_weather=False,
        include_email_news=True,
        email_provider=mock_email_provider,
        date=datetime(2026, 8, 28),
    )

    with patch.object(AgendaProvider, "get_day_agenda", return_value=MOCK_AGENDA_DATA), \
         patch("screamsheet.renderers.email_news.EmailNewsSummarizer", return_value=mock_summarizer_inst):
        pdf_path = sheet.generate()
        assert pdf_path == out_pdf
        assert Path(pdf_path).exists()

        # Verify page count is 2 (Page 1: Agenda + XKCD, Page 2: Email news)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        num_pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
        assert num_pages == 2


def test_matches_important_sender():
    from screamsheet.providers.gmail_provider import _matches_important_sender

    targets = ["annashavin@gmail.com", "mainlineclassical.org"]

    # Exact email match in header
    assert _matches_important_sender("Anna <annashavin@gmail.com>", targets) is True
    assert _matches_important_sender("ANNASHAVIN@GMAIL.COM", targets) is True
    assert _matches_important_sender("annashavin@gmail.com", targets) is True

    # Domain match
    assert _matches_important_sender("Principal <admin@mainlineclassical.org>", targets) is True
    assert _matches_important_sender("<teacher@sub.mainlineclassical.org>", targets) is True

    # Non-match
    assert _matches_important_sender("Stranger <stranger@example.com>", targets) is False
    assert _matches_important_sender("evil@notmainlineclassical.org", targets) is False
    assert _matches_important_sender("someone@gmail.com", targets) is False


def test_important_emails_section_render():
    from screamsheet.renderers.important_emails import ImportantEmailsSection

    mock_provider = MagicMock()
    mock_provider.fetch_important_emails.return_value = [
        {
            "id": "1",
            "sender": "Headmaster <office@mainlineclassical.org>",
            "subject": "School Closure Tomorrow",
            "date": datetime(2026, 8, 28, 8, 0),
            "body": "School will be closed tomorrow due to weather.",
        }
    ]

    mock_summarizer_cls = MagicMock()
    mock_summarizer_inst = MagicMock()
    mock_summarizer_inst.generate_summary.return_value = (
        "School is closed tomorrow due to weather. Check portal for assignments."
    )
    mock_summarizer_cls.return_value = mock_summarizer_inst

    sec = ImportantEmailsSection(
        provider=mock_provider,
        date=datetime(2026, 8, 28),
        senders=["mainlineclassical.org"],
        summarizer_class=mock_summarizer_cls,
    )
    assert sec.page_slot == "back"
    assert sec.has_content() is True

    flowables = sec.render()
    assert len(flowables) > 0
    rendered_text = " ".join(getattr(f, "text", "") for f in flowables)
    assert "Headmaster" in rendered_text
    assert "School Closure Tomorrow" in rendered_text
    assert "School is closed tomorrow" in rendered_text

    md = sec.render_markdown()
    assert "Headmaster" in md
    assert "School Closure Tomorrow" in md
    assert "School is closed tomorrow" in md


def test_briefing_with_important_emails_and_news(tmp_path):
    out_pdf = str(tmp_path / "briefing_important.pdf")

    mock_email_provider = MagicMock()
    mock_email_provider.fetch_important_emails.return_value = [
        {
            "id": "1",
            "sender": "Anna <annashavin@gmail.com>",
            "subject": "Pickup schedule",
            "date": datetime(2026, 8, 28, 8, 0),
            "body": "Please pick up the kids at 3pm.",
        }
    ]
    mock_email_provider.fetch_emails.return_value = [
        {
            "id": "2",
            "sender": "Punchbowl News",
            "subject": "Punchbowl AM",
            "date": datetime(2026, 8, 28, 7, 0),
            "body": "Congress returns today.",
        }
    ]

    sheet = ScreamsheetFactory.create_briefing_screamsheet(
        output_filename=out_pdf,
        subscriber_name="Peter",
        payload={},
        include_weather=False,
        include_email_news=True,
        important_senders=["annashavin@gmail.com"],
        email_provider=mock_email_provider,
        date=datetime(2026, 8, 28),
    )

    sections = sheet.build_sections()
    from screamsheet.renderers.briefing_back import TwoColumnBriefingBackSection
    back_sections = [s for s in sections if isinstance(s, TwoColumnBriefingBackSection)]
    assert len(back_sections) == 1
    back_sec = back_sections[0]
    assert back_sec.page_slot == "back"
    assert back_sec.news_section is not None
    assert back_sec.important_section is not None


def test_two_column_briefing_back_section_render_and_overflow():
    from screamsheet.renderers.briefing_back import TwoColumnBriefingBackSection
    from screamsheet.renderers.email_news import EmailNewsSection
    from screamsheet.renderers.important_emails import ImportantEmailsSection

    mock_news_provider = MagicMock()
    # 7 news items (more than max_left_news=5)
    mock_news_provider.fetch_emails.return_value = [
        {
            "id": f"news-{i}",
            "sender": f"News Source {i}",
            "subject": f"Headlines {i}",
            "date": datetime(2026, 8, 28, 7, i),
            "body": f"Details for headline {i}",
        }
        for i in range(1, 8)
    ]

    mock_important_provider = MagicMock()
    mock_important_provider.fetch_important_emails.return_value = [
        {
            "id": "imp-1",
            "sender": "School Office",
            "subject": "Parent Teacher Conference",
            "date": datetime(2026, 8, 28, 8, 0),
            "body": "Conferences will take place on Friday.",
        }
    ]

    mock_news_sum = MagicMock()
    mock_news_sum.generate_summary.side_effect = lambda data=None, **kw: f"Summary of {data.get('subject') if data else 'news'}"
    mock_imp_sum = MagicMock()
    mock_imp_sum.generate_summary.side_effect = lambda data=None, **kw: f"Notice: {data.get('subject') if data else 'notice'}"

    news_sec = EmailNewsSection(provider=mock_news_provider, date=datetime(2026, 8, 28), summarizer_class=lambda: mock_news_sum)
    important_sec = ImportantEmailsSection(important_senders=["office@school.org"], provider=mock_important_provider, date=datetime(2026, 8, 28), summarizer_class=lambda: mock_imp_sum)

    back_sec = TwoColumnBriefingBackSection(
        news_section=news_sec,
        important_section=important_sec,
        max_left_news=5,
    )
    assert back_sec.has_content() is True
    flowables = back_sec.render()
    assert len(flowables) == 1

    table = flowables[0]
    # table._cellvalues is [[left_flowables, "", right_flowables]]
    left_cells = table._cellvalues[0][0]
    right_cells = table._cellvalues[0][2]

    # Left column has first 5 news items
    left_text = " ".join(getattr(f, "text", "") for f in left_cells)
    assert "News Source 1" in left_text
    assert "News Source 5" in left_text
    assert "News Source 6" not in left_text

    # Right column has overflow news items (6 and 7) continuing OVER the important email
    right_text = " ".join(getattr(f, "text", "") for f in right_cells)
    assert "MORNING NEWS BRIEFING (CONT.)" in right_text
    assert "News Source 6" in right_text
    assert "News Source 7" in right_text
    assert "School Office" in right_text
    assert "Parent Teacher Conference" in right_text

    # Verify order in right column: overflow news comes BEFORE important emails
    idx_overflow = right_text.index("News Source 6")
    idx_important = right_text.index("School Office")
    assert idx_overflow < idx_important

    # Verify markdown output contains both sections
    md = back_sec.render_markdown()
    assert "News Source 1" in md
    assert "School Office" in md


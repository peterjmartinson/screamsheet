import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from screamsheet.providers.xkcd_provider import XKCDProvider
from screamsheet.renderers.xkcd import XKCDSection
from screamsheet.db.xkcd_db import init_xkcd_db, get_seen_comic_nums


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_screamsheet.db"
    init_xkcd_db(db_file)
    return db_file


MOCK_LATEST_COMIC = {
    "num": 2980,
    "title": "Latest Comic",
    "safe_title": "Latest Comic",
    "img": "https://imgs.xkcd.com/comics/latest.png",
    "alt": "Latest alt punchline",
    "year": "2026",
    "month": "9",
    "day": "1",
}

MOCK_RANDOM_COMIC = {
    "num": 1234,
    "title": "Random Past Comic",
    "safe_title": "Random Past Comic",
    "img": "https://imgs.xkcd.com/comics/random.png",
    "alt": "Random alt punchline",
    "year": "2013",
    "month": "5",
    "day": "10",
}


def test_provider_new_release_mwf(test_db: Path):
    provider = XKCDProvider(db_path=test_db)

    with patch.object(provider, "fetch_latest_comic_metadata", return_value=MOCK_LATEST_COMIC):
        comic = provider.get_comic()
        assert comic is not None
        assert comic["num"] == 2980
        assert get_seen_comic_nums(db_path=test_db) == {2980}


def test_provider_off_day_random_selection(test_db: Path):
    provider = XKCDProvider(db_path=test_db)

    # First fetch records latest 2980
    with patch.object(provider, "fetch_latest_comic_metadata", return_value=MOCK_LATEST_COMIC):
        provider.get_comic()
        assert 2980 in get_seen_comic_nums(db_path=test_db)

    # Second fetch on off-day detects 2980 already seen and selects random comic
    with patch.object(provider, "fetch_latest_comic_metadata", return_value=MOCK_LATEST_COMIC), \
         patch.object(provider, "fetch_comic_by_num", return_value=MOCK_RANDOM_COMIC) as mock_by_num:
        comic = provider.get_comic()
        assert comic is not None
        assert comic["num"] == 1234
        assert mock_by_num.called
        # Check that 404 is never called
        called_nums = [call.args[0] for call in mock_by_num.call_args_list]
        assert 404 not in called_nums
        assert get_seen_comic_nums(db_path=test_db) == {1234, 2980}


def test_xkcd_section_render():
    section = XKCDSection(comic_data=MOCK_LATEST_COMIC)
    assert section.has_content()

    md = section.render_markdown()
    assert "## XKCD #2980: Latest Comic" in md
    assert "https://imgs.xkcd.com/comics/latest.png" in md
    assert "Latest alt punchline" in md

    with patch.object(section, "_download_and_scale_image", return_value=None):
        flowables = section.render()
        assert len(flowables) >= 2  # Title, line, alt text

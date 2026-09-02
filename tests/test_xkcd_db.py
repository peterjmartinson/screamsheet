import pytest
from pathlib import Path

from screamsheet.db.xkcd_db import (
    init_xkcd_db,
    is_comic_seen,
    get_seen_comic_nums,
    get_comic,
    record_comic,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_screamsheet.db"
    init_xkcd_db(db_file)
    return db_file


def test_xkcd_db_operations(test_db: Path):
    assert not is_comic_seen(2980, db_path=test_db)
    assert get_seen_comic_nums(db_path=test_db) == set()

    comic_data = {
        "num": 2980,
        "title": "Test Comic",
        "safe_title": "Test Comic",
        "img": "https://imgs.xkcd.com/comics/test.png",
        "alt": "This is test alt text",
        "year": "2026",
        "month": "9",
        "day": "1",
    }

    record_comic(comic_data, is_latest=True, db_path=test_db)

    assert is_comic_seen(2980, db_path=test_db)
    assert get_seen_comic_nums(db_path=test_db) == {2980}

    saved = get_comic(2980, db_path=test_db)
    assert saved is not None
    assert saved["num"] == 2980
    assert saved["title"] == "Test Comic"
    assert saved["alt"] == "This is test alt text"
    assert saved["is_latest"] is True

    # Record again without error (idempotent)
    record_comic(comic_data, is_latest=True, db_path=test_db)
    assert len(get_seen_comic_nums(db_path=test_db)) == 1

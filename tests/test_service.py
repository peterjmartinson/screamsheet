"""Unit tests for screamsheet.service — generate_for_subscriber()."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from screamsheet.service import generate_for_subscriber
from screamsheet.result import GenerationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, data: dict) -> Path:
    cfg = tmp_path / "subscriber.yaml"
    cfg.write_text(yaml.dump(data), encoding="utf-8")
    return cfg


MINIMAL_NHL_CONFIG = {
    "guid": "abc-123",
    "name": "Test Subscriber",
    "email": "test@example.com",
    "nhl": {
        "favorite_teams": [{"name": "Philadelphia Flyers"}],
    },
}

MINIMAL_MLB_CONFIG = {
    "guid": "abc-456",
    "name": "Test Subscriber",
    "email": "test@example.com",
    "mlb": {
        "favorite_teams": [{"name": "Philadelphia Phillies"}],
        "news_names": ["Phillies"],
    },
}

MULTI_SPORT_CONFIG = {
    "guid": "abc-789",
    "name": "Test Subscriber",
    "email": "test@example.com",
    "nhl": {"favorite_teams": [{"name": "Philadelphia Flyers"}]},
    "mlb": {"favorite_teams": [{"name": "Philadelphia Phillies"}], "news_names": ["Phillies"]},
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestGenerateForSubscriberConfigLoading:
    def test_missing_config_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "no_such_file.yaml"
        with pytest.raises(FileNotFoundError):
            generate_for_subscriber(str(missing), str(tmp_path))

    def test_invalid_yaml_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(":: not valid yaml ::", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid YAML"):
            generate_for_subscriber(str(bad), str(tmp_path))


# ---------------------------------------------------------------------------
# One result per sheet type
# ---------------------------------------------------------------------------

class TestGenerateForSubscriberResults:
    def test_nhl_config_produces_one_result(self, tmp_path):
        cfg = _write_config(tmp_path, MINIMAL_NHL_CONFIG)
        out = tmp_path / "out"
        out.mkdir()
        with patch("screamsheet.service._generate_sheet") as mock_gen:
            mock_gen.return_value = GenerationResult(
                pdf_path=str(out / "nhl_20260506.pdf"),
                sheet_type="nhl",
            )
            results = generate_for_subscriber(str(cfg), str(out))
        assert len(results) == 1
        assert results[0].sheet_type == "nhl"

    def test_multi_sport_config_produces_one_result_per_sport(self, tmp_path):
        cfg = _write_config(tmp_path, MULTI_SPORT_CONFIG)
        out = tmp_path / "out"
        out.mkdir()
        with patch("screamsheet.service._generate_sheet") as mock_gen:
            mock_gen.side_effect = lambda sheet_type, *a, **kw: GenerationResult(
                pdf_path=str(out / f"{sheet_type}_20260506.pdf"),
                sheet_type=sheet_type,
            )
            results = generate_for_subscriber(str(cfg), str(out))
        sheet_types = {r.sheet_type for r in results}
        assert "nhl" in sheet_types
        assert "mlb" in sheet_types
        assert len(results) == 2

    def test_returns_list_of_generation_results(self, tmp_path):
        cfg = _write_config(tmp_path, MINIMAL_NHL_CONFIG)
        out = tmp_path / "out"
        out.mkdir()
        with patch("screamsheet.service._generate_sheet") as mock_gen:
            mock_gen.return_value = GenerationResult(
                pdf_path=str(out / "nhl_20260506.pdf"),
                sheet_type="nhl",
            )
            results = generate_for_subscriber(str(cfg), str(out))
        assert all(isinstance(r, GenerationResult) for r in results)


# ---------------------------------------------------------------------------
# Failure isolation — one sheet crashing doesn't abort others
# ---------------------------------------------------------------------------

class TestGenerateForSubscriberIsolation:
    def test_sheet_exception_recorded_as_issue_not_raised(self, tmp_path):
        cfg = _write_config(tmp_path, MULTI_SPORT_CONFIG)
        out = tmp_path / "out"
        out.mkdir()

        def _mock_gen(sheet_type, *a, **kw):
            if sheet_type == "nhl":
                raise RuntimeError("API unavailable")
            return GenerationResult(
                pdf_path=str(out / f"{sheet_type}_20260506.pdf"),
                sheet_type=sheet_type,
            )

        with patch("screamsheet.service._generate_sheet", side_effect=_mock_gen):
            results = generate_for_subscriber(str(cfg), str(out))

        assert len(results) == 2
        nhl_result = next(r for r in results if r.sheet_type == "nhl")
        assert not nhl_result.layout_clean
        assert any("API unavailable" in issue for issue in nhl_result.issues)

    def test_failed_sheet_has_empty_pdf_path(self, tmp_path):
        cfg = _write_config(tmp_path, MINIMAL_NHL_CONFIG)
        out = tmp_path / "out"
        out.mkdir()
        with patch("screamsheet.service._generate_sheet", side_effect=RuntimeError("boom")):
            results = generate_for_subscriber(str(cfg), str(out))
        assert results[0].pdf_path == ""

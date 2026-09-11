"""Unit tests for screamsheet.__main__ copy-to-output-dir logic."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.__main__ import _copy_to_output_dir, _run_sheet


class TestCopyToOutputDir:
    def test_copy_pdf_to_output_directory(self, tmp_path):
        src = tmp_path / "test.pdf"
        src.write_bytes(b"%PDF")
        dest_dir = tmp_path / "output"

        _copy_to_output_dir(str(src), str(dest_dir))

        assert (dest_dir / "test.pdf").exists()

    def test_output_directory_created_if_missing(self, tmp_path):
        src = tmp_path / "test.pdf"
        src.write_bytes(b"%PDF")
        dest_dir = tmp_path / "new" / "nested" / "dir"

        _copy_to_output_dir(str(src), str(dest_dir))

        assert dest_dir.is_dir()

    def test_copy_skips_if_pdf_missing(self, tmp_path, caplog):
        import logging
        dest_dir = tmp_path / "output"
        with caplog.at_level(logging.WARNING):
            _copy_to_output_dir("/nonexistent/file.pdf", str(dest_dir))

        assert any("nonexistent" in r.message for r in caplog.records)

    def test_copy_is_noop_when_output_dir_empty(self, tmp_path):
        src = tmp_path / "test.pdf"
        src.write_bytes(b"%PDF")

        # Must not raise and must not copy anywhere
        _copy_to_output_dir(str(src), "")

    def test_copy_noop_when_source_in_output_dir(self, tmp_path):
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()
        src = dest_dir / "test.pdf"
        src.write_bytes(b"%PDF")

        with patch("screamsheet.__main__.shutil.copy2") as copy2:
            _copy_to_output_dir(str(src), str(dest_dir))

        copy2.assert_not_called()
        assert src.read_bytes() == b"%PDF"


class TestRunSheet:
    def test_run_sheet_copies_to_output_dir(self, tmp_path):
        src = tmp_path / "sheet.pdf"
        src.write_bytes(b"%PDF")
        dest_dir = tmp_path / "output"

        mock_sheet = MagicMock()
        mock_sheet.generate.return_value = str(src)

        _run_sheet("Test Sheet", lambda: mock_sheet, str(dest_dir))

        assert (dest_dir / "sheet.pdf").exists()

    def test_run_sheet_noop_when_output_dir_empty(self, tmp_path):
        src = tmp_path / "sheet.pdf"
        src.write_bytes(b"%PDF")

        mock_sheet = MagicMock()
        mock_sheet.generate.return_value = str(src)

        # Must not raise
        _run_sheet("Test Sheet", lambda: mock_sheet, "")

    def test_cli_output_dir_overrides_config(self, tmp_path):
        src = tmp_path / "sheet.pdf"
        src.write_bytes(b"%PDF")
        config_dir = tmp_path / "from_config"
        cli_dir = tmp_path / "from_cli"

        mock_sheet = MagicMock()
        mock_sheet.generate.return_value = str(src)

        # Simulate: CLI override wins — caller passes cli_dir, not config_dir
        _run_sheet("Test Sheet", lambda: mock_sheet, str(cli_dir))

        assert (cli_dir / "sheet.pdf").exists()
        assert not (config_dir / "sheet.pdf").exists()


class TestBuildOrderFromConfig:
    @pytest.fixture(autouse=True)
    def mock_config(self, monkeypatch):
        from screamsheet.config import load_config
        example_path = Path(__file__).parents[1] / "config.yaml.example"
        monkeypatch.setattr("screamsheet.__main__.load_config", lambda: load_config(example_path))

    def test_worldcup_not_in_batch_order(self):
        from datetime import datetime
        from screamsheet.__main__ import _build_order_from_config

        order = _build_order_from_config(datetime(2026, 7, 29))
        assert order.worldcup is None

    def test_french_mlb_news_in_batch_order(self):
        from datetime import datetime
        from screamsheet.__main__ import _build_order_from_config

        order = _build_order_from_config(datetime(2026, 7, 29))
        assert order.french_mlb_news is not None
        assert isinstance(order.french_mlb_news.news_names, list)


class TestBuildSheets:
    @pytest.fixture(autouse=True)
    def mock_config(self, monkeypatch):
        from screamsheet.config import load_config
        example_path = Path(__file__).parents[1] / "config.yaml.example"
        monkeypatch.setattr("screamsheet.__main__.load_config", lambda: load_config(example_path))

    def test_nfl_in_build_sheets(self):
        from screamsheet.__main__ import _build_sheets

        sheets, _ = _build_sheets("20260909")
        labels = [label for label, _ in sheets]
        assert any("NFL" in label for label in labels)


class TestMainMissingConfig:
    def test_main_exits_gracefully_when_config_missing(self, monkeypatch, capsys):
        from screamsheet.__main__ import main
        monkeypatch.setattr("screamsheet.__main__.load_config", MagicMock(side_effect=FileNotFoundError("Config file not found")))
        monkeypatch.setattr("sys.argv", ["screamsheet"])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "config.yaml" in captured.out or "config.yaml" in captured.err


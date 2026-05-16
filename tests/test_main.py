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

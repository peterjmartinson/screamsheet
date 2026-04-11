"""Unit tests for screamsheet.__main__ — output copy logic."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.__main__ import _copy_to_output, _run_sheet


# ---------------------------------------------------------------------------
# _copy_to_output
# ---------------------------------------------------------------------------

class TestCopyToOutput:
    def test_copies_file_to_output_dir(self, tmp_path):
        pdf = tmp_path / "NHL_gamescores_20260411.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out_dir = tmp_path / "PRINT"
        out_dir.mkdir()

        _copy_to_output(str(pdf), str(out_dir))

        assert (out_dir / pdf.name).exists()

    def test_no_copy_when_output_dir_equals_files(self, tmp_path):
        pdf = tmp_path / "NHL_gamescores_20260411.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with patch("screamsheet.__main__.shutil.copy2") as mock_copy:
            _copy_to_output(str(pdf), "Files/")

        mock_copy.assert_not_called()

    def test_raises_when_output_dir_missing(self, tmp_path):
        pdf = tmp_path / "NHL_gamescores_20260411.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        missing_dir = str(tmp_path / "nonexistent")

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            _copy_to_output(str(pdf), missing_dir)


# ---------------------------------------------------------------------------
# _run_sheet
# ---------------------------------------------------------------------------

class TestRunSheet:
    def test_run_sheet_copies_to_output_dir(self, tmp_path, capsys):
        pdf = tmp_path / "test_sheet.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out_dir = tmp_path / "PRINT"
        out_dir.mkdir()

        sheet = MagicMock()
        sheet.generate.return_value = str(pdf)

        _run_sheet("Test Sheet", lambda: sheet, output_dir=str(out_dir))

        assert (out_dir / pdf.name).exists()

    def test_run_sheet_prints_label(self, tmp_path, capsys):
        pdf = tmp_path / "test_sheet.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        sheet = MagicMock()
        sheet.generate.return_value = str(pdf)

        _run_sheet("My Label", lambda: sheet)

        captured = capsys.readouterr()
        assert "My Label" in captured.out

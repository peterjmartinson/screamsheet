"""Unit tests for screamsheet.result.GenerationResult."""
from screamsheet.result import GenerationResult


class TestGenerationResultDefaults:
    def test_layout_clean_true_when_no_issues(self):
        r = GenerationResult(pdf_path="/tmp/nhl_20260506.pdf", sheet_type="nhl")
        assert r.layout_clean is True

    def test_issues_empty_by_default(self):
        r = GenerationResult(pdf_path="/tmp/nhl_20260506.pdf", sheet_type="nhl")
        assert r.issues == []


class TestGenerationResultWithIssues:
    def test_layout_clean_false_when_issues_provided(self):
        r = GenerationResult(
            pdf_path="/tmp/nhl_20260506.pdf",
            sheet_type="nhl",
            issues=["standings overflowed to page 3"],
        )
        assert r.layout_clean is False

    def test_issues_list_preserved(self):
        issues = ["standings overflowed", "column width at floor"]
        r = GenerationResult(
            pdf_path="/tmp/nhl_20260506.pdf",
            sheet_type="nhl",
            issues=issues,
        )
        assert r.issues == issues

    def test_multiple_issues_all_stored(self):
        r = GenerationResult(
            pdf_path="/tmp/mlb_20260506.pdf",
            sheet_type="mlb",
            issues=["issue one", "issue two", "issue three"],
        )
        assert len(r.issues) == 3


class TestGenerationResultFields:
    def test_pdf_path_stored(self):
        r = GenerationResult(pdf_path="/tmp/nhl_20260506.pdf", sheet_type="nhl")
        assert r.pdf_path == "/tmp/nhl_20260506.pdf"

    def test_sheet_type_stored(self):
        r = GenerationResult(pdf_path="/tmp/mlb_20260506.pdf", sheet_type="mlb")
        assert r.sheet_type == "mlb"

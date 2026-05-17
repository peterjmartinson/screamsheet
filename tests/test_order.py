"""Unit tests for the ScreamsheetOrder contract and run_order() dispatcher."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.order import (
    NHLOrderOptions,
    MLBOrderOptions,
    OutputOrderOptions,
    ScreamsheetOrder,
    TeamEntry,
    OrderValidationError,
)
from screamsheet.runner import run_order


_TODAY = datetime(2026, 5, 16)


class TestTeamEntryValidation:
    def test_valid_team_entry_constructs_successfully(self) -> None:
        entry = TeamEntry(id=4, name="Philadelphia Flyers")
        assert entry.id == 4
        assert entry.name == "Philadelphia Flyers"

    def test_zero_id_raises_order_validation_error(self) -> None:
        with pytest.raises(OrderValidationError):
            TeamEntry(id=0, name="Bad Team")

    def test_negative_id_raises_order_validation_error(self) -> None:
        with pytest.raises(OrderValidationError):
            TeamEntry(id=-1, name="Bad Team")

    def test_empty_name_raises_order_validation_error(self) -> None:
        with pytest.raises(OrderValidationError):
            TeamEntry(id=4, name="")


class TestRunOrder:
    def test_empty_order_returns_success(self) -> None:
        order = ScreamsheetOrder()
        assert run_order(order, today=_TODAY) == "success"

    def test_nhl_only_order_calls_only_nhl_handler(self) -> None:
        order = ScreamsheetOrder(
            nhl=NHLOrderOptions(favorite_teams=[TeamEntry(id=4, name="Flyers")])
        )
        mock_nhl = MagicMock(return_value="/tmp/nhl.pdf")
        mock_mlb = MagicMock(return_value="/tmp/mlb.pdf")
        with patch("screamsheet.runner._REGISTRY", {"nhl": mock_nhl, "mlb": mock_mlb}):
            result = run_order(order, today=_TODAY)
        assert result == "success"
        mock_nhl.assert_called_once()
        mock_mlb.assert_not_called()

    def test_no_sheet_keys_produces_zero_handler_calls(self) -> None:
        order = ScreamsheetOrder(output=OutputOrderOptions(directory="/tmp"))
        mock_handler = MagicMock(return_value="/tmp/sheet.pdf")
        with patch("screamsheet.runner._REGISTRY", {"nhl": mock_handler}):
            result = run_order(order, today=_TODAY)
        assert result == "success"
        mock_handler.assert_not_called()

    def test_unregistered_field_logs_warning_and_does_not_raise(self, caplog) -> None:
        import logging

        order = ScreamsheetOrder(
            nhl=NHLOrderOptions(favorite_teams=[TeamEntry(id=4, name="Flyers")])
        )
        with patch("screamsheet.runner._REGISTRY", {}):
            with caplog.at_level(logging.WARNING, logger="screamsheet.runner"):
                result = run_order(order, today=_TODAY)
        assert result == "success"
        assert any("nhl" in r.message for r in caplog.records)

    def test_output_field_is_never_dispatched_as_sheet(self) -> None:
        order = ScreamsheetOrder(output=OutputOrderOptions(directory="/tmp/out"))
        mock_handler = MagicMock(return_value="/tmp/sheet.pdf")
        with patch("screamsheet.runner._REGISTRY", {"output": mock_handler}):
            run_order(order, today=_TODAY)
        mock_handler.assert_not_called()

    def test_today_defaults_to_now_when_not_provided(self) -> None:
        order = ScreamsheetOrder()
        assert run_order(order) == "success"

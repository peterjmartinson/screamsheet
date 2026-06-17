"""Unit tests for the ScreamsheetOrder contract and run_order() dispatcher."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from screamsheet.order import (
    NHLOrderOptions,
    NHLNewsOrderOptions,
    MLBOrderOptions,
    OutputOrderOptions,
    PersonOptions,
    ScreamsheetOrder,
    ScreamsheetResult,
    TeamEntry,
    OrderValidationError,
    WeatherLocationOptions,
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
    def test_empty_order_returns_clean_result(self) -> None:
        order = ScreamsheetOrder()
        result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        assert result.errors == []
        assert result.sheets_generated == []

    def test_nhl_only_order_calls_only_nhl_handler(self) -> None:
        order = ScreamsheetOrder(
            nhl=NHLOrderOptions(favorite_teams=[TeamEntry(id=4, name="Flyers")])
        )
        mock_nhl = MagicMock(return_value="/tmp/nhl.pdf")
        mock_mlb = MagicMock(return_value="/tmp/mlb.pdf")
        with patch("screamsheet.runner._REGISTRY", {"nhl": mock_nhl, "mlb": mock_mlb}):
            result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        mock_nhl.assert_called_once()
        mock_mlb.assert_not_called()

    def test_nhl_news_only_order_calls_only_nhl_news_handler(self) -> None:
        order = ScreamsheetOrder(
            nhl_news=NHLNewsOrderOptions(
                news_names=["Flyers"],
                weather=WeatherLocationOptions(40.0, -75.0, "Bryn Mawr, PA"),
            )
        )
        mock_nhl_news = MagicMock(return_value="/tmp/nhl_news.pdf")
        mock_nhl = MagicMock(return_value="/tmp/nhl.pdf")
        with patch("screamsheet.runner._REGISTRY", {"nhl_news": mock_nhl_news, "nhl": mock_nhl}):
            result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        mock_nhl_news.assert_called_once()
        mock_nhl.assert_not_called()

    def test_no_sheet_keys_produces_zero_handler_calls(self) -> None:
        order = ScreamsheetOrder(output=OutputOrderOptions(directory="/tmp"))
        mock_handler = MagicMock(return_value="/tmp/sheet.pdf")
        with patch("screamsheet.runner._REGISTRY", {"nhl": mock_handler}):
            result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        mock_handler.assert_not_called()

    def test_unregistered_field_logs_warning_and_does_not_raise(self, caplog) -> None:
        import logging

        order = ScreamsheetOrder(
            nhl=NHLOrderOptions(favorite_teams=[TeamEntry(id=4, name="Flyers")])
        )
        with patch("screamsheet.runner._REGISTRY", {}):
            with caplog.at_level(logging.WARNING, logger="screamsheet.runner"):
                result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        assert any("nhl" in r.message for r in caplog.records)

    def test_output_field_is_never_dispatched_as_sheet(self) -> None:
        order = ScreamsheetOrder(output=OutputOrderOptions(directory="/tmp/out"))
        mock_handler = MagicMock(return_value="/tmp/sheet.pdf")
        with patch("screamsheet.runner._REGISTRY", {"output": mock_handler}):
            run_order(order, today=_TODAY)
        mock_handler.assert_not_called()

    def test_today_defaults_to_now_when_not_provided(self) -> None:
        order = ScreamsheetOrder()
        result = run_order(order)
        assert isinstance(result, ScreamsheetResult)

    def test_sheet_exception_is_captured_in_errors_not_raised(self) -> None:
        order = ScreamsheetOrder(
            nhl=NHLOrderOptions(favorite_teams=[TeamEntry(id=4, name="Flyers")])
        )
        mock_nhl = MagicMock(side_effect=RuntimeError("network timeout"))
        with patch("screamsheet.runner._REGISTRY", {"nhl": mock_nhl}):
            result = run_order(order, today=_TODAY)
        assert isinstance(result, ScreamsheetResult)
        assert any("network timeout" in e for e in result.errors)
        assert result.sheets_generated == []

    def test_subscriber_name_appears_in_result(self) -> None:
        order = ScreamsheetOrder()
        result = run_order(order, today=_TODAY, subscriber_name="Peter Martinson")
        assert result.subscriber_name == "Peter Martinson"


class TestPersonOptions:
    def test_birth_fields_default_to_empty_strings(self) -> None:
        person = PersonOptions(name="Alice")
        assert person.birth_date == ""
        assert person.birth_time == ""
        assert person.birth_location == ""
        assert person.sun_sign == ""
        assert person.moon_sign == ""
        assert person.ascendant == ""

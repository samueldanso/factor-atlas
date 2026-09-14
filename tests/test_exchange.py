"""Tests for the exchange state module — all bgc calls are mocked."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from factor_atlas.exchange import (
    classify_order_status,
    query_exchange_state,
    query_order_status,
)

# Realistic bgc account_overview response
_ACCOUNT_OVERVIEW_RESPONSE = json.dumps(
    {
        "data": {
            "accountId": "123456",
            "coin": [
                {
                    "coin": "USDT",
                    "available": "48523.12",
                    "frozen": "1200.00",
                    "equity": "49723.12",
                }
            ],
        }
    }
)

# Realistic bgc position info response
_POSITION_RESPONSE = json.dumps(
    {
        "data": [
            {
                "symbol": "AAPLUSDT",
                "holdSide": "long",
                "total": "2",
                "openPriceAvg": "330.33",
                "unrealizedPL": "-12.50",
            },
            {
                "symbol": "METAUSDT",
                "holdSide": "short",
                "total": "1",
                "openPriceAvg": "641.76",
                "unrealizedPL": "8.20",
            },
        ]
    }
)

# Realistic bgc order open response
_OPEN_ORDERS_RESPONSE = json.dumps({"data": {"orderList": []}})

# Realistic bgc order detail response
_ORDER_DETAIL_FILLED = json.dumps(
    {
        "data": {
            "orderId": "1483216288468062208",
            "symbol": "AAPLUSDT",
            "side": "buy",
            "price": "330.33",
            "size": "2",
            "status": "filled",
        }
    }
)

_ORDER_DETAIL_REJECTED = json.dumps(
    {
        "data": {
            "orderId": "999",
            "symbol": "AAPLUSDT",
            "side": "buy",
            "price": "330.33",
            "size": "2",
            "status": "cancelled",
        }
    }
)


def _mock_subprocess_run(responses: dict[str, str]):
    """Return a mock that maps bgc action keywords to canned responses."""

    def _side_effect(cmd, **_kwargs):
        cmd_str = " ".join(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        r = Result()

        for keyword, response in responses.items():
            if keyword in cmd_str:
                r.stdout = response
                return r

        r.returncode = 1
        r.stderr = "unknown command"
        return r

    return _side_effect


class TestQueryExchangeState:
    def test_parses_balance_and_positions(self) -> None:
        responses = {
            "account_overview": _ACCOUNT_OVERVIEW_RESPONSE,
            "position": _POSITION_RESPONSE,
            "order": _OPEN_ORDERS_RESPONSE,
        }
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run(responses),
        ):
            state = query_exchange_state()

        assert state.balance == Decimal("48523.12")
        assert len(state.positions) == 2
        assert state.positions[0].symbol == "AAPLUSDT"
        assert state.positions[0].side == "long"
        assert state.positions[0].size == Decimal(2)
        assert state.positions[0].entry_price == Decimal("330.33")
        assert len(state.pending_orders) == 0
        assert state.queried_at is not None

    def test_raises_on_account_overview_failure(self) -> None:
        def _fail(cmd, **_kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "auth failed"

            return Result()

        with (
            patch("factor_atlas.exchange.subprocess.run", side_effect=_fail),
            pytest.raises(RuntimeError, match="account_overview failed"),
        ):
            query_exchange_state()

    def test_empty_positions_returns_empty_list(self) -> None:
        responses = {
            "account_overview": _ACCOUNT_OVERVIEW_RESPONSE,
            "position": json.dumps({"data": []}),
            "order": _OPEN_ORDERS_RESPONSE,
        }
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run(responses),
        ):
            state = query_exchange_state()
        assert state.positions == []
        assert state.balance == Decimal("48523.12")


class TestQueryOrderStatus:
    def test_filled_order(self) -> None:
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run({"order": _ORDER_DETAIL_FILLED}),
        ):
            order = query_order_status("1483216288468062208")
        assert order.status == "filled"
        assert order.order_id == "1483216288468062208"

    def test_cancelled_order(self) -> None:
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run({"order": _ORDER_DETAIL_REJECTED}),
        ):
            order = query_order_status("999")
        assert order.status == "cancelled"

    def test_network_failure_propagates_oserror(self) -> None:
        def _fail(cmd, **_kwargs):
            raise OSError("Network unreachable")

        with (
            patch("factor_atlas.exchange.subprocess.run", side_effect=_fail),
            pytest.raises(OSError),
        ):
            query_order_status("123")

    def test_invalid_order_id_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid order_id"):
            query_order_status("--malicious-flag")

    def test_order_id_with_leading_dash_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid order_id"):
            query_order_status("-1234")

    def test_order_id_too_long_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid order_id"):
            query_order_status("1" * 33)


class TestClassifyOrderStatus:
    def test_filled(self) -> None:
        assert classify_order_status("filled") == "verified_filled"

    def test_filled_uppercase(self) -> None:
        assert classify_order_status("FILLED") == "verified_filled"

    def test_cancelled(self) -> None:
        assert classify_order_status("cancelled") == "verified_cancelled"

    def test_canceled_alternate_spelling(self) -> None:
        assert classify_order_status("canceled") == "verified_cancelled"

    def test_rejected(self) -> None:
        assert classify_order_status("rejected") == "verified_rejected"

    def test_failed_maps_to_rejected(self) -> None:
        assert classify_order_status("failed") == "verified_rejected"

    def test_partial_fill(self) -> None:
        assert classify_order_status("partial_fill") == "verified_partial"

    def test_partially_filled(self) -> None:
        assert classify_order_status("partially_filled") == "verified_partial"

    def test_partial(self) -> None:
        assert classify_order_status("partial") == "verified_partial"

    def test_unknown_returns_unverified(self) -> None:
        assert classify_order_status("unknown_thing") == "unverified"

    def test_empty_string_returns_unverified(self) -> None:
        assert classify_order_status("") == "unverified"

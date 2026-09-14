"""Tests for adapters: Bitget Demo (mocked HTTP) and instrument normalization."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx
import pytest

from factor_atlas.adapters.bitget_demo import BitgetDemoAdapter
from factor_atlas.adapters.normalize import research_to_execution

# ---------------------------------------------------------------------------
# Instrument normalization
# ---------------------------------------------------------------------------


class TestResearchToExecution:
    """Normalize rToken research instruments to stock perp execution instruments."""

    def test_raaplusdt(self) -> None:
        assert research_to_execution("RAAPLUSDT") == "AAPLUSDT"

    def test_rnvdausdt(self) -> None:
        assert research_to_execution("RNVDAUSDT") == "NVDAUSDT"

    def test_rtslausdt(self) -> None:
        assert research_to_execution("RTSLAUSDT") == "TSLAUSDT"

    def test_rmetausdt(self) -> None:
        assert research_to_execution("RMETAUSDT") == "METAUSDT"

    def test_execution_passthrough_aaplusdt(self) -> None:
        assert research_to_execution("AAPLUSDT") == "AAPLUSDT"

    def test_execution_passthrough_nvdausdt(self) -> None:
        assert research_to_execution("NVDAUSDT") == "NVDAUSDT"

    def test_unknown_passthrough(self) -> None:
        assert research_to_execution("BTCUSDT") == "BTCUSDT"


# ---------------------------------------------------------------------------
# BitgetDemoAdapter — credential validation
# ---------------------------------------------------------------------------


class TestBitgetDemoAdapterCredentials:
    """Adapter refuses missing credentials with ValueError."""

    def test_empty_api_key(self) -> None:
        with pytest.raises(ValueError, match="credentials required"):
            BitgetDemoAdapter("", "secret", "pass")

    def test_empty_secret(self) -> None:
        with pytest.raises(ValueError, match="credentials required"):
            BitgetDemoAdapter("key", "", "pass")

    def test_empty_passphrase(self) -> None:
        with pytest.raises(ValueError, match="credentials required"):
            BitgetDemoAdapter("key", "secret", "")

    def test_valid_credentials(self) -> None:
        adapter = BitgetDemoAdapter("key", "secret", "pass")
        assert adapter is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "https://api.bitget.com"


def _mock_client(handler: Any) -> httpx.AsyncClient:
    """Build a mock async client with base_url matching the adapter's."""
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=_BASE,
    )


def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# BitgetDemoAdapter — mocked HTTP tests
# ---------------------------------------------------------------------------


class TestBitgetDemoAdapterMockedHTTP:
    """Adapter HTTP methods with mocked transport (no real API calls)."""

    @pytest.fixture()
    def adapter(self) -> BitgetDemoAdapter:
        return BitgetDemoAdapter("test-key", "test-secret", "test-pass")

    def test_get_market_snapshot_success(self, adapter: BitgetDemoAdapter) -> None:
        """Mocked ticker response returns data dict."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"code": "00000", "data": [{"lastPr": "238.50"}]},
            )

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.get_market_snapshot("AAPLUSDT")
            assert result["code"] == "00000"
            await adapter.close()

        _run(_test())

    def test_get_market_snapshot_http_error(self, adapter: BitgetDemoAdapter) -> None:
        """HTTP error returns error dict instead of crashing."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"code": "40003", "msg": "Forbidden"},
            )

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.get_market_snapshot("AAPLUSDT")
            assert result["error"] is True
            assert result["status_code"] == 403
            await adapter.close()

        _run(_test())

    def test_place_paper_order_success(self, adapter: BitgetDemoAdapter) -> None:
        """Mocked order placement returns data dict."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"code": "00000", "data": {"orderId": "12345"}},
            )

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.place_paper_order(
                instrument="AAPLUSDT",
                side="buy",
                quantity=Decimal(10),
                price=Decimal("238.50"),
            )
            assert result["code"] == "00000"
            assert result["data"]["orderId"] == "12345"
            await adapter.close()

        _run(_test())

    def test_place_paper_order_http_error(self, adapter: BitgetDemoAdapter) -> None:
        """Order placement HTTP error returns error dict."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                500,
                json={"code": "50000", "msg": "Internal error"},
            )

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.place_paper_order(
                instrument="AAPLUSDT",
                side="buy",
                quantity=Decimal(10),
                price=Decimal("238.50"),
            )
            assert result["error"] is True
            assert result["status_code"] == 500
            await adapter.close()

        _run(_test())

    def test_get_account_balance_success(self, adapter: BitgetDemoAdapter) -> None:
        """Mocked account balance returns data dict."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "data": [{"marginCoin": "USDT", "available": "100000"}],
                },
            )

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.get_account_balance()
            assert result["code"] == "00000"
            await adapter.close()

        _run(_test())

    def test_simulated_trading_header(self, adapter: BitgetDemoAdapter) -> None:
        """Requests include X-SIMULATED-TRADING: 1 header."""
        captured_headers: dict[str, str] = {}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"code": "00000", "data": []})

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            await adapter.get_market_snapshot("AAPLUSDT")
            await adapter.close()

        _run(_test())
        assert captured_headers.get("x-simulated-trading") == "1"

    def test_request_error_handled(self, adapter: BitgetDemoAdapter) -> None:
        """Connection errors return error dict instead of crashing."""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        adapter._client = _mock_client(mock_handler)

        async def _test() -> None:
            result = await adapter.get_market_snapshot("AAPLUSDT")
            assert result["error"] is True
            assert result["status_code"] == 0
            await adapter.close()

        _run(_test())

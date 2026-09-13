"""Adapter for Bitget Demo USDT-FUTURES stock perpetuals.

Uses httpx for REST calls to Bitget's Demo API.
All calls use paper-trading mode.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from base64 import b64encode
from decimal import Decimal
from typing import Any

import httpx

from factor_atlas.config import CATEGORY

# Bitget Demo API base URL
_DEMO_BASE_URL = "https://api.bitget.com"


class BitgetDemoAdapter:
    """Adapter for Bitget Demo USDT-FUTURES stock perpetuals.

    Uses httpx for REST calls to Bitget's Demo API.
    All calls use paper-trading mode.
    """

    def __init__(self, api_key: str, secret_key: str, passphrase: str) -> None:
        if not api_key or not secret_key or not passphrase:
            msg = (
                "Bitget Demo credentials required: "
                "BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE"
            )
            raise ValueError(msg)
        self._api_key = api_key
        self._secret_key = secret_key
        self._passphrase = passphrase
        self._client = httpx.AsyncClient(
            base_url=_DEMO_BASE_URL,
            timeout=30.0,
        )

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Create HMAC-SHA256 signature for Bitget API."""
        message = timestamp + method.upper() + path + body
        mac = hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return b64encode(mac.digest()).decode("utf-8")

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Build authenticated request headers."""
        timestamp = str(int(time.time() * 1000))
        sign = self._sign(timestamp, method, path, body)
        return {
            "ACCESS-KEY": self._api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type": "application/json",
            "X-SIMULATED-TRADING": "1",  # Demo/paper-trading flag
        }

    async def get_market_snapshot(self, instrument: str) -> dict[str, Any]:
        """Fetch latest ticker for a USDT-FUTURES instrument.

        Returns the raw API response dict or an error dict.
        """
        path = f"/api/v2/mix/market/ticker?productType={CATEGORY}&symbol={instrument}"
        headers = self._headers("GET", path)
        try:
            resp = await self._client.get(path, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except httpx.HTTPStatusError as e:
            return {
                "error": True,
                "status_code": e.response.status_code,
                "detail": str(e),
            }
        except httpx.RequestError as e:
            return {"error": True, "status_code": 0, "detail": str(e)}

    async def place_paper_order(
        self,
        instrument: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> dict[str, Any]:
        """Place a paper order on Bitget Demo. Returns order response dict."""
        path = "/api/v2/mix/order/place-order"
        body_dict = {
            "symbol": instrument,
            "productType": CATEGORY,
            "marginMode": "crossed",
            "marginCoin": "USDT",
            "side": side,
            "orderType": "limit",
            "price": str(price),
            "size": str(quantity),
            "tradeSide": "open",
        }
        import json

        body = json.dumps(body_dict)
        headers = self._headers("POST", path, body)
        try:
            resp = await self._client.post(path, content=body, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except httpx.HTTPStatusError as e:
            return {
                "error": True,
                "status_code": e.response.status_code,
                "detail": str(e),
            }
        except httpx.RequestError as e:
            return {"error": True, "status_code": 0, "detail": str(e)}

    async def get_account_balance(self) -> dict[str, Any]:
        """Get Demo account USDT balance.

        Returns the raw API response dict or an error dict.
        """
        path = f"/api/v2/mix/account/accounts?productType={CATEGORY}"
        headers = self._headers("GET", path)
        try:
            resp = await self._client.get(path, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except httpx.HTTPStatusError as e:
            return {
                "error": True,
                "status_code": e.response.status_code,
                "detail": str(e),
            }
        except httpx.RequestError as e:
            return {"error": True, "status_code": 0, "detail": str(e)}

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


__all__ = [
    "BitgetDemoAdapter",
]

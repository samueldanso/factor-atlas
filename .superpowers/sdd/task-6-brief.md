### Task 6: Separate research prices from execution prices

**Files:**
- Modify: `src/factor_atlas/runner.py` (`_build_demo_data`, `_process_demo_exits`, `run_paper_session`)

**Interfaces:**
- Consumes: `_fetch_candles_bgc` (existing), `RESEARCH_TO_EXECUTION` mapping from `factor_atlas.config`
- Produces: `_fetch_perp_prices(instruments: list[str]) -> dict[str, Decimal]` — fetches latest USDT-FUTURES prices for perp instruments. Demo exits use perp prices, not SPOT research prices.

- [ ] **Step 1: Write test for perp price fetching**

```python
# Add to tests/test_runner.py
class TestPerpPriceFetching:
    def test_fetch_perp_prices_returns_decimals(self) -> None:
        from unittest.mock import patch
        import json

        candle_resp = json.dumps(
            {
                "data": [
                    [
                        1694649600000,
                        "330.00",
                        "335.00",
                        "328.00",
                        "332.50",
                        "1000",
                        "332500",
                    ]
                ]
            }
        )

        def _mock_run(cmd, **_kw):
            class R:
                returncode = 0
                stdout = candle_resp
                stderr = ""

            return R()

        with patch("factor_atlas.runner.subprocess.run", side_effect=_mock_run):
            from factor_atlas.runner import _fetch_perp_prices

            prices = _fetch_perp_prices(["AAPLUSDT"])

        from decimal import Decimal

        assert prices["AAPLUSDT"] == Decimal("332.50")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runner.py::TestPerpPriceFetching -v`
Expected: FAIL with `ImportError: cannot import name '_fetch_perp_prices'`

- [ ] **Step 3: Add _fetch_perp_prices and wire it in**

Add to `src/factor_atlas/runner.py` after `_build_demo_data`:

```python
def _fetch_perp_prices(instruments: list[str]) -> dict[str, Decimal]:
    """Fetch the latest USDT-FUTURES close price for each perp instrument."""
    prices: dict[str, Decimal] = {}
    for symbol in instruments:
        cmd = [
            "bgc",
            "market",
            "--action",
            "candles",
            "--category",
            "USDT-FUTURES",
            "--symbol",
            symbol,
            "--interval",
            "1D",
            "--limit",
            "1",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode != 0:
            continue
        raw = json.loads(result.stdout)
        candles = raw.get("data", [])
        if candles:
            prices[symbol] = Decimal(str(candles[-1][4]))
    return prices
```

Update `_process_demo_exits` to accept a `perp_prices: dict[str, Decimal]` parameter instead of using SPOT OHLCV data for exit evaluation:

```python
def _process_demo_exits(
    broker_state: BrokerState,
    perp_prices: dict[str, Decimal],
    risk_config: RiskConfig,
    config_hash: str,
    paper_log_f: Any,
) -> None:
    now = datetime.now(tz=UTC)
    to_close: list[str] = []

    for instrument, pos in broker_state.open_positions.items():
        exec_sym = RESEARCH_TO_EXECUTION.get(instrument, instrument)
        current_price = perp_prices.get(exec_sym)
        if current_price is None:
            continue
        # ... rest of exit logic unchanged but uses exec_sym price ...
```

Update the call site in `run_paper_session` to fetch perp prices and pass them.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/factor_atlas/runner.py tests/test_runner.py
git commit -m "fix(runner): use perp prices for exit evaluation, not SPOT research prices"
```

---

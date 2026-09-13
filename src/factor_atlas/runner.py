"""Competition-period paper-trading runner for FactorAtlas."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from factor_atlas.adapters.normalize import research_to_execution
from factor_atlas.audit import AuditLogger
from factor_atlas.broker import BrokerState, ClosedTrade, OpenPosition
from factor_atlas.config import (
    CATEGORY,
    EXECUTION_INSTRUMENTS,
    FACTOR_VOCABULARY,
    RESEARCH_INSTRUMENTS,
    RESEARCH_TO_EXECUTION,
)
from factor_atlas.contracts import MarketSnapshot
from factor_atlas.fixtures import ACCEPTED_SNAPSHOT, RAAPLUSDT_OHLCV, REJECTED_SNAPSHOT
from factor_atlas.llm import (
    BedrockProvider,
    FixtureLLMProvider,
    LLMDecisionProvider,
    LLMProposer,
)
from factor_atlas.metrics import compute_metrics, make_closed_trade
from factor_atlas.orchestrator import CycleResult, run_cycles
from factor_atlas.risk import RiskConfig

SOFTWARE_VERSION = "0.1.0"

_DEFAULT_OUTPUT_DIR = Path("artifacts/paper-trading")


# ---------------------------------------------------------------------------
# Config hash
# ---------------------------------------------------------------------------


def compute_config_hash(risk_config: RiskConfig) -> str:
    """Compute a deterministic hash from risk config, factors, and instruments."""
    risk_dict: dict[str, Any] = {
        "max_data_age_hours": risk_config.max_data_age_hours,
        "max_notional": str(risk_config.max_notional),
        "max_concurrent_positions": risk_config.max_concurrent_positions,
        "max_exposure": str(risk_config.max_exposure),
        "cooldown_seconds": risk_config.cooldown_seconds,
        "daily_loss_limit": str(risk_config.daily_loss_limit),
        "max_concentration_per_instrument": risk_config.max_concentration_per_instrument,
        "max_quantity": str(risk_config.max_quantity),
    }
    config_data = json.dumps(
        {
            "risk": risk_dict,
            "factors": sorted(FACTOR_VOCABULARY),
            "research_instruments": sorted(RESEARCH_INSTRUMENTS),
            "execution_instruments": sorted(EXECUTION_INSTRUMENTS),
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(config_data.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Git commit hash
# ---------------------------------------------------------------------------


def get_git_commit() -> str:
    """Get the short git commit hash, or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


# ---------------------------------------------------------------------------
# Paper log record builder
# ---------------------------------------------------------------------------


def _build_paper_record(
    cycle_result: CycleResult,
    config_hash: str,
) -> dict[str, Any]:
    """Build a paper log record dict from a CycleResult."""
    order = cycle_result.order
    decision = cycle_result.decision

    # Determine execution instrument (normalize rToken -> perp)
    raw_instrument = cycle_result.snapshot.instrument
    exec_instrument = research_to_execution(raw_instrument)

    # Find hypothesis and validation info
    hypothesis_id = ""
    factor_name = ""
    validation_sharpe: float | None = None
    rationale = ""

    if decision is not None:
        hypothesis_id = decision.hypothesis_id
        rationale = decision.rationale
        # Find matching hypothesis
        for hyp, val in cycle_result.validated:
            if hyp.hypothesis_id == decision.hypothesis_id:
                factor_name = hyp.factor_name
                validation_sharpe = val.metrics.sharpe_ratio.value
                break

    # Build gate results list
    gate_results_list: list[dict[str, Any]] = []
    if cycle_result.gate_results is not None:
        gate_results_list = [
            {
                "gate_name": g.gate_name,
                "passed": g.passed,
                "reason": g.reason,
            }
            for g in cycle_result.gate_results
        ]

    if order is not None:
        return {
            "record_type": "open",
            "order_id": order.order_id,
            "decision_id": order.decision_id,
            "event_id": order.event_id,
            "timestamp": order.timestamp.isoformat(),
            "instrument": exec_instrument,
            "category": CATEGORY,
            "side": order.side,
            "price": str(order.price),
            "quantity": str(order.quantity),
            "notional": str(order.notional),
            "pre_balance": str(order.pre_balance),
            "post_balance": str(order.post_balance),
            "fees": str(order.fees),
            "slippage": str(order.slippage),
            "status": order.status,
            "fill_price": str(order.fill_price) if order.fill_price else None,
            "rejection_reason": order.rejection_reason,
            "cycle_id": cycle_result.cycle_id,
            "hypothesis_id": hypothesis_id,
            "factor_name": factor_name,
            "risk_gate_results": gate_results_list,
            "validation_sharpe": validation_sharpe,
            "rationale": rationale,
            "software_version": SOFTWARE_VERSION,
            "config_hash": config_hash,
        }

    # No order (no_candidate / no_hypothesis)
    return {
        "record_type": "open",
        "order_id": None,
        "decision_id": decision.decision_id if decision else None,
        "event_id": None,
        "timestamp": cycle_result.snapshot.timestamp.isoformat(),
        "instrument": exec_instrument,
        "category": CATEGORY,
        "side": decision.side if decision else None,
        "price": str(cycle_result.snapshot.close),
        "quantity": "0",
        "notional": "0",
        "pre_balance": None,
        "post_balance": None,
        "fees": "0",
        "slippage": "0",
        "status": cycle_result.status,
        "fill_price": None,
        "rejection_reason": cycle_result.status,
        "cycle_id": cycle_result.cycle_id,
        "hypothesis_id": hypothesis_id,
        "factor_name": factor_name,
        "risk_gate_results": gate_results_list,
        "validation_sharpe": validation_sharpe,
        "rationale": rationale,
        "software_version": SOFTWARE_VERSION,
        "config_hash": config_hash,
    }


# ---------------------------------------------------------------------------
# Fixture mode data builder
# ---------------------------------------------------------------------------


def _build_fixture_data() -> tuple[
    list[Any],
    dict[str, pd.DataFrame],
]:
    """Build snapshots and OHLCV data from fixtures.

    Snapshot timestamps are set to now so the data_freshness gate passes
    in deterministic demo runs. OHLCV prices are unchanged fixture data.

    Returns (snapshots, ohlcv_dict).
    """
    from datetime import timedelta

    now = datetime.now(tz=UTC)
    n_bars = len(RAAPLUSDT_OHLCV)

    # Build OHLCV DataFrame with monotonically increasing timestamps ending at
    # now. bar[n-1] = now, bar[n-2] = now-1h, ..., bar[0] = now-(n-1)h.
    # Unique timestamps prevent leakage detection false positives.
    records = []
    for i, bar in enumerate(RAAPLUSDT_OHLCV):
        ts = now - timedelta(hours=(n_bars - 1 - i))
        records.append(
            {
                "timestamp": ts,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
        )
    df = pd.DataFrame(records)
    ohlcv_data: dict[str, pd.DataFrame] = {"RAAPLUSDT": df}

    # Freshen snapshot timestamps to match the last bar (data_freshness gate
    # checks snapshot.timestamp, which must be within 24h of now).
    accepted = ACCEPTED_SNAPSHOT.model_copy(update={"timestamp": now})
    rejected = REJECTED_SNAPSHOT.model_copy(
        update={"timestamp": now - timedelta(minutes=1)}
    )
    snapshots = [accepted, rejected]

    return snapshots, ohlcv_data


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------


def _build_manifest(
    run_id: str,
    mode: str,
    start_time: datetime,
    end_time: datetime,
    results: list[CycleResult],
    config_hash: str,
    commit: str,
    closed_trades: list[ClosedTrade] | None = None,
) -> dict[str, Any]:
    """Build the run manifest dict."""
    accepted = sum(1 for r in results if r.status == "accepted")
    rejected = sum(1 for r in results if r.status != "accepted")
    research_insts = sorted({r.snapshot.instrument for r in results})
    exec_insts = sorted({research_to_execution(i) for i in research_insts})

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "start_timestamp": start_time.isoformat(),
        "end_timestamp": end_time.isoformat(),
        "timezone": "UTC",
        "mode": mode,
        "instruments": research_insts,
        "execution_instruments": exec_insts,
        "cycles_completed": len(results),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "code_commit": commit,
        "config_hash": config_hash,
        "software_version": SOFTWARE_VERSION,
        "performance_metrics": compute_metrics(closed_trades or []),
    }
    return manifest


# ---------------------------------------------------------------------------
# bgc-based market data fetcher (demo mode)
# ---------------------------------------------------------------------------


def _fetch_candles_bgc(
    symbol: str, interval: str = "1D", limit: int = 90
) -> pd.DataFrame:
    """Fetch OHLCV candles for a SPOT rToken symbol via bgc CLI.

    Returns a DataFrame with columns: timestamp, open, high, low, close, volume.
    Raises RuntimeError if bgc fails or returns no data.
    """
    cmd = [
        "bgc",
        "market",
        "--action",
        "candles",
        "--category",
        "SPOT",
        "--symbol",
        symbol,
        "--interval",
        interval,
        "--limit",
        str(limit),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"bgc candles failed for {symbol}: {result.stderr.strip()}")

    raw = json.loads(result.stdout)
    candles = raw.get("data", [])
    if not candles:
        raise RuntimeError(f"bgc returned empty candles for {symbol}")

    records = []
    for c in candles:
        # Format: [ts_ms, open, high, low, close, base_vol, quote_vol]
        records.append(
            {
                "timestamp": datetime.fromtimestamp(int(c[0]) / 1000, tz=UTC),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            }
        )
    return pd.DataFrame(records)


def _place_order_bgc(
    exec_symbol: str,
    side: str,
    price: Decimal,
    qty: Decimal,
) -> dict[str, Any]:
    """Place a paper order on Bitget Demo via bgc CLI.

    Returns parsed JSON response. Raises RuntimeError on failure.
    Always uses --paper-trading, posSide long, timeInForce gtc.
    """
    pos_side = "long" if side == "buy" else "short"
    cmd = [
        "bgc",
        "--paper-trading",
        "order",
        "--action",
        "place",
        "--category",
        "USDT-FUTURES",
        "--symbol",
        exec_symbol,
        "--side",
        side,
        "--orderType",
        "limit",
        "--price",
        str(price),
        "--qty",
        str(qty),
        "--timeInForce",
        "gtc",
        "--posSide",
        pos_side,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"bgc order failed for {exec_symbol}: {result.stderr.strip()}"
        )
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def _build_demo_data(
    instruments: list[str],
) -> tuple[
    list[MarketSnapshot],
    dict[str, pd.DataFrame],
]:
    """Fetch live rToken SPOT candles via bgc for all research instruments.

    Returns (snapshots, ohlcv_dict) where each snapshot is the latest bar
    and ohlcv_dict has DataFrames keyed by research symbol.
    """
    snapshots: list[MarketSnapshot] = []
    ohlcv_data: dict[str, pd.DataFrame] = {}

    for symbol in instruments:
        try:
            df = _fetch_candles_bgc(symbol, interval="1D", limit=90)
        except RuntimeError as e:
            print(f"  Warning: {e} — skipping {symbol}", file=sys.stderr)
            continue

        if df.empty:
            continue

        ohlcv_data[symbol] = df
        last = df.iloc[-1]
        snap = MarketSnapshot(
            timestamp=last["timestamp"],
            snapshot_id=f"demo-{symbol}-{int(last['timestamp'].timestamp())}",
            instrument=symbol,
            category="SPOT",
            open=Decimal(str(last["open"])),
            high=Decimal(str(last["high"])),
            low=Decimal(str(last["low"])),
            close=Decimal(str(last["close"])),
            volume=Decimal(str(last["volume"])),
            source="bitget-demo",
        )
        snapshots.append(snap)

    return snapshots, ohlcv_data


# ---------------------------------------------------------------------------
# Position state persistence (cross-run tracking for demo mode)
# ---------------------------------------------------------------------------

_POSITIONS_STATE_FILE = _DEFAULT_OUTPUT_DIR / "positions_state.json"


def _load_positions_state(
    broker_state: BrokerState,
    state_path: Path,
) -> None:
    """Load persisted open positions and closed trades into broker_state."""
    if not state_path.exists():
        return
    try:
        raw = json.loads(state_path.read_text())
        for d in raw.get("open_positions", []):
            pos = OpenPosition.from_dict(d)
            broker_state.open_positions[pos.instrument] = pos
        for d in raw.get("closed_trades", []):
            broker_state.closed_trades.append(ClosedTrade.from_dict(d))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass  # corrupt state → start fresh


def _save_positions_state(
    broker_state: BrokerState,
    state_path: Path,
) -> None:
    """Persist open positions and closed trades for the next run."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "open_positions": [p.to_dict() for p in broker_state.open_positions.values()],
                "closed_trades": [t.to_dict() for t in broker_state.closed_trades],
                "last_updated": datetime.now(tz=UTC).isoformat(),
            },
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# Position registration (after a cycle fills an entry order)
# ---------------------------------------------------------------------------


def _register_open_positions(
    results: list[CycleResult],
    broker_state: BrokerState,
) -> None:
    """Add accepted, filled cycles to broker_state.open_positions."""
    for result in results:
        if result.status != "accepted" or result.order is None:
            continue
        if result.order.status != "filled" or result.decision is None:
            continue
        d = result.decision
        factor_name = ""
        for hyp, _ in result.validated:
            if hyp.hypothesis_id == d.hypothesis_id:
                factor_name = hyp.factor_name
                break
        pos = OpenPosition(
            instrument=d.instrument,
            side=d.side,
            entry_price=d.price,
            quantity=d.quantity,
            entry_time=d.timestamp,
            hypothesis_id=d.hypothesis_id,
            factor_name=factor_name,
            cycle_id=result.cycle_id,
        )
        broker_state.open_positions[d.instrument] = pos


# ---------------------------------------------------------------------------
# Exit evaluation
# ---------------------------------------------------------------------------


def _should_exit(
    pos: OpenPosition,
    current_price: Decimal,
    now: datetime,
    risk_config: RiskConfig,
) -> tuple[bool, str]:
    """Return (should_exit, reason) for an open position."""
    cost = pos.entry_price
    if cost == 0:
        return False, ""
    if pos.side == "buy":
        unrealized_pct = float((current_price - pos.entry_price) / cost)
    else:
        unrealized_pct = float((pos.entry_price - current_price) / cost)

    if unrealized_pct <= -risk_config.stop_loss_pct:
        return True, f"stop_loss ({unrealized_pct:.2%})"
    if unrealized_pct >= risk_config.take_profit_pct:
        return True, f"take_profit ({unrealized_pct:.2%})"
    hold_h = (now - pos.entry_time).total_seconds() / 3600
    if hold_h >= risk_config.max_hold_hours:
        return True, f"max_hold ({hold_h:.1f}h)"
    return False, ""


def _build_close_record(
    closed_trade: ClosedTrade,
    config_hash: str,
    bgc_close_order_id: str | None = None,
) -> dict[str, Any]:
    """Build a paper_log close record for a ClosedTrade."""
    exec_instrument = research_to_execution(closed_trade.instrument)
    close_side = "sell" if closed_trade.side == "buy" else "buy"
    record: dict[str, Any] = {
        "record_type": "close",
        "order_id": None,
        "decision_id": None,
        "event_id": None,
        "timestamp": closed_trade.exit_time.isoformat(),
        "instrument": exec_instrument,
        "category": CATEGORY,
        "side": close_side,
        "price": str(closed_trade.exit_price),
        "quantity": str(closed_trade.quantity),
        "notional": str(closed_trade.exit_price * closed_trade.quantity),
        "pre_balance": None,
        "post_balance": None,
        "fees": "0",
        "slippage": "0",
        "status": "closed",
        "fill_price": str(closed_trade.exit_price),
        "rejection_reason": None,
        "cycle_id": "",
        "hypothesis_id": "",
        "factor_name": closed_trade.factor_name,
        "risk_gate_results": [],
        "validation_sharpe": None,
        "rationale": f"exit: pnl={closed_trade.pnl} ({closed_trade.pnl_pct:.2%}), "
        f"hold={closed_trade.hold_duration_hours:.1f}h",
        "entry_price": str(closed_trade.entry_price),
        "exit_price": str(closed_trade.exit_price),
        "pnl": str(closed_trade.pnl),
        "pnl_pct": closed_trade.pnl_pct,
        "won": closed_trade.won,
        "hold_duration_hours": closed_trade.hold_duration_hours,
        "software_version": SOFTWARE_VERSION,
        "config_hash": config_hash,
    }
    if bgc_close_order_id:
        record["bgc_order_id"] = bgc_close_order_id
    return record


# ---------------------------------------------------------------------------
# Demo mode exit processor
# ---------------------------------------------------------------------------


def _process_demo_exits(
    broker_state: BrokerState,
    ohlcv_data: dict[str, pd.DataFrame],
    risk_config: RiskConfig,
    config_hash: str,
    paper_log_f: Any,
) -> None:
    """Check open positions for exit conditions and close them via bgc."""
    now = datetime.now(tz=UTC)
    to_close: list[str] = []

    for instrument, pos in broker_state.open_positions.items():
        df = ohlcv_data.get(instrument)
        if df is None or df.empty:
            continue
        current_price = Decimal(str(df.iloc[-1]["close"]))
        should_exit, reason = _should_exit(pos, current_price, now, risk_config)
        if should_exit:
            to_close.append(instrument)
            closed = make_closed_trade(pos, current_price, now)
            broker_state.closed_trades.append(closed)
            broker_state.daily_pnl += closed.pnl

            exec_sym = RESEARCH_TO_EXECUTION.get(instrument, instrument)
            close_side = "sell" if pos.side == "buy" else "buy"
            bgc_close_id: str | None = None
            try:
                resp = _place_order_bgc(exec_sym, close_side, current_price, pos.quantity)
                bgc_close_id = (
                    str(resp.get("data", {}).get("orderId") or resp.get("orderId") or "")
                    or None
                )
                print(f"  Exit {instrument} ({reason}): orderId={bgc_close_id}")
            except (RuntimeError, json.JSONDecodeError) as e:
                print(f"  Exit order failed for {instrument}: {e}", file=sys.stderr)

            close_record = _build_close_record(closed, config_hash, bgc_close_id)
            paper_log_f.write(json.dumps(close_record) + "\n")

    for instrument in to_close:
        del broker_state.open_positions[instrument]


# ---------------------------------------------------------------------------
# Fixture mode synthetic exit (in-memory only, no bgc, for metrics in tests)
# ---------------------------------------------------------------------------


def _process_fixture_exits(
    broker_state: BrokerState,
) -> None:
    """Synthetically close all open positions at ±2% from entry (no I/O)."""
    now = datetime.now(tz=UTC)
    for pos in list(broker_state.open_positions.values()):
        if pos.side == "buy":
            exit_price = pos.entry_price * Decimal("1.02")
        else:
            exit_price = pos.entry_price * Decimal("0.98")
        closed = make_closed_trade(pos, exit_price, now)
        broker_state.closed_trades.append(closed)
        broker_state.daily_pnl += closed.pnl
    broker_state.open_positions.clear()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_paper_session(
    mode: str = "fixture",
    cycles: int = 2,
    output_dir: Path | None = None,
) -> Path:
    """Run a paper-trading session and write results.

    Returns the path to the run output directory.
    """
    if mode not in ("fixture", "demo"):
        msg = f"Unknown mode '{mode}'. Must be 'fixture' or 'demo'."
        raise ValueError(msg)

    # Setup output
    run_id = str(uuid4())
    base_dir = output_dir or _DEFAULT_OUTPUT_DIR
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Config
    risk_config = RiskConfig()
    config_hash = compute_config_hash(risk_config)
    commit = get_git_commit()
    start_time = datetime.now(tz=UTC)

    # Audit logger
    audit_path = run_dir / "audit_log.jsonl"
    audit_logger = AuditLogger(output_path=audit_path)

    state_path = (output_dir or _DEFAULT_OUTPUT_DIR) / "positions_state.json"

    if mode == "demo":
        print("Demo mode: fetching live rToken SPOT candles via bgc...")
        research_syms = sorted(RESEARCH_INSTRUMENTS)
        snapshots_all, ohlcv_data = _build_demo_data(research_syms)
        if not snapshots_all:
            msg = "Demo mode: no candle data returned for any instrument. Check bgc."
            raise RuntimeError(msg)
    else:
        snapshots_all, ohlcv_data = _build_fixture_data()

    snapshots = snapshots_all[:cycles]

    broker_state = BrokerState()

    if mode == "demo":
        _load_positions_state(broker_state, state_path)

    if mode == "demo":
        try:
            llm_provider = BedrockProvider()
            print(f"  LLM: {llm_provider.model_name} (AWS Bedrock)")
        except (ImportError, RuntimeError, OSError) as e:
            print(
                f"  Warning: BedrockProvider init failed ({e}). "
                "Falling back to FixtureLLMProvider.",
                file=sys.stderr,
            )
            llm_provider = FixtureLLMProvider()  # type: ignore[assignment]
    else:
        llm_provider = FixtureLLMProvider()  # type: ignore[assignment]

    proposer = LLMProposer(llm_provider)
    decision_provider = LLMDecisionProvider(llm_provider)

    # Write paper log — open file here so exit processor can append close records
    paper_log_path = run_dir / "paper_log.jsonl"

    with paper_log_path.open("a") as paper_log_f:
        # Demo: process exits from prior runs before opening new positions
        if mode == "demo" and broker_state.open_positions:
            _process_demo_exits(
                broker_state, ohlcv_data, risk_config, config_hash, paper_log_f
            )

        results = run_cycles(
            snapshots=snapshots,
            ohlcv_data=ohlcv_data,
            proposer=proposer,
            decision_provider=decision_provider,
            broker_state=broker_state,
            risk_config=risk_config,
            audit_logger=audit_logger,
        )

        end_time = datetime.now(tz=UTC)

        # Register newly opened positions
        _register_open_positions(results, broker_state)

        # Demo: place bgc entry orders for accepted cycles
        bgc_order_ids: dict[str, str] = {}
        if mode == "demo":
            for result in results:
                if result.status == "accepted" and result.decision is not None:
                    d = result.decision
                    exec_sym = RESEARCH_TO_EXECUTION.get(d.instrument, d.instrument)
                    try:
                        resp = _place_order_bgc(
                            exec_symbol=exec_sym,
                            side=d.side,
                            price=d.price,
                            qty=d.quantity,
                        )
                        order_id = (
                            resp.get("data", {}).get("orderId")
                            or resp.get("orderId")
                            or "unknown"
                        )
                        bgc_order_ids[result.cycle_id] = str(order_id)
                        print(f"  Entry {exec_sym} {d.side} → orderId={order_id}")
                    except (RuntimeError, json.JSONDecodeError) as e:
                        print(f"  Entry order failed for {exec_sym}: {e}", file=sys.stderr)
                        bgc_order_ids[result.cycle_id] = f"error:{e}"

        # Fixture: close positions synthetically for metrics (in-memory only)
        if mode == "fixture":
            _process_fixture_exits(broker_state)

        # Write open-cycle records
        for result in results:
            record = _build_paper_record(result, config_hash)
            if mode == "demo" and result.cycle_id in bgc_order_ids:
                record["bgc_order_id"] = bgc_order_ids[result.cycle_id]
            paper_log_f.write(json.dumps(record) + "\n")

    # Persist position state for next demo run
    if mode == "demo":
        _save_positions_state(broker_state, state_path)

    # Write manifest with real performance metrics
    manifest = _build_manifest(
        run_id=run_id,
        mode=mode,
        start_time=start_time,
        end_time=end_time,
        results=results,
        config_hash=config_hash,
        commit=commit,
        closed_trades=broker_state.closed_trades,
    )
    manifest_path = run_dir / "manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    perf = manifest["performance_metrics"]
    print(f"Paper run complete: {run_dir}")
    print(f"  Cycles: {len(results)}")
    print(f"  Accepted: {manifest['accepted_count']}")
    print(f"  Rejected: {manifest['rejected_count']}")
    print(
        f"  Performance: trades={perf['total_trades']}, "
        f"win_rate={perf['win_rate']}, sharpe={perf['sharpe_ratio']}, "
        f"max_dd={perf['max_drawdown']}"
    )
    print(f"  Paper log: {paper_log_path}")
    print(f"  Audit log: {audit_path}")
    print(f"  Manifest: {manifest_path}")

    return run_dir


# ---------------------------------------------------------------------------
# Dry-run validation
# ---------------------------------------------------------------------------


def validate_config() -> None:
    """Validate configuration and exit. Used by --dry-run."""
    risk_config = RiskConfig()
    config_hash = compute_config_hash(risk_config)
    commit = get_git_commit()

    print("FactorAtlas configuration valid.")
    print(f"  Software version: {SOFTWARE_VERSION}")
    print(f"  Config hash: {config_hash}")
    print(f"  Git commit: {commit}")
    print(f"  Research instruments: {sorted(RESEARCH_INSTRUMENTS)}")
    print(f"  Execution instruments: {sorted(EXECUTION_INSTRUMENTS)}")
    print(f"  Factor vocabulary: {sorted(FACTOR_VOCABULARY)}")
    print(
        f"  Risk config: max_notional={risk_config.max_notional}, "
        f"max_positions={risk_config.max_concurrent_positions}, "
        f"daily_loss_limit={risk_config.daily_loss_limit}"
    )


__all__ = [
    "SOFTWARE_VERSION",
    "compute_config_hash",
    "get_git_commit",
    "run_paper_session",
    "validate_config",
]

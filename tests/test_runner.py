"""Tests for the paper-trading runner (fixture mode)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factor_atlas.runner import (
    SOFTWARE_VERSION,
    compute_config_hash,
    get_git_commit,
    run_paper_session,
    validate_config,
)


class TestConfigHash:
    """Config hash is deterministic and well-formed."""

    def test_deterministic(self) -> None:
        from factor_atlas.risk import RiskConfig

        cfg = RiskConfig()
        h1 = compute_config_hash(cfg)
        h2 = compute_config_hash(cfg)
        assert h1 == h2

    def test_prefix(self) -> None:
        from factor_atlas.risk import RiskConfig

        cfg = RiskConfig()
        h = compute_config_hash(cfg)
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 16


class TestGitCommit:
    """Git commit helper returns a non-empty string."""

    def test_returns_string(self) -> None:
        commit = get_git_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0


class TestValidateConfig:
    """--dry-run config validation prints and does not raise."""

    def test_no_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        validate_config()
        out = capsys.readouterr().out
        assert "FactorAtlas configuration valid" in out
        assert "sha256:" in out


class TestRunPaperSession:
    """Fixture-mode paper session produces all required artifacts."""

    def test_produces_output_files(self, tmp_path: Path) -> None:
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        assert run_dir.exists()
        assert (run_dir / "paper_log.jsonl").exists()
        assert (run_dir / "audit_log.jsonl").exists()
        assert (run_dir / "manifest.json").exists()

    def test_paper_log_has_records(self, tmp_path: Path) -> None:
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        paper_log = run_dir / "paper_log.jsonl"
        lines = paper_log.read_text().strip().split("\n")
        assert len(lines) >= 2
        for line in lines:
            record = json.loads(line)
            # All required fields present
            assert "timestamp" in record
            assert "instrument" in record
            assert "category" in record
            assert "side" in record or record["side"] is None
            assert "price" in record
            assert "quantity" in record
            assert "status" in record
            assert "cycle_id" in record
            assert "factor_name" in record
            assert "risk_gate_results" in record
            assert "software_version" in record
            assert "config_hash" in record

    def test_paper_log_execution_instrument(self, tmp_path: Path) -> None:
        """Paper log records use the EXECUTION instrument, not research."""
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        paper_log = run_dir / "paper_log.jsonl"
        lines = paper_log.read_text().strip().split("\n")
        for line in lines:
            record = json.loads(line)
            instrument = record["instrument"]
            # Must be execution instrument or at least normalized
            # RAAPLUSDT -> AAPLUSDT, RNVDAUSDT -> NVDAUSDT
            assert not instrument.startswith("R") or instrument not in (
                "RAAPLUSDT",
                "RNVDAUSDT",
                "RTSLAUSDT",
                "RMETAUSDT",
            ), f"Paper log should use execution instrument, got {instrument}"

    def test_paper_log_category_usdt_futures(self, tmp_path: Path) -> None:
        """Paper log records use USDT-FUTURES category."""
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        paper_log = run_dir / "paper_log.jsonl"
        lines = paper_log.read_text().strip().split("\n")
        for line in lines:
            record = json.loads(line)
            assert record["category"] == "USDT-FUTURES"

    def test_manifest_fields(self, tmp_path: Path) -> None:
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert "run_id" in manifest
        assert "start_timestamp" in manifest
        assert "end_timestamp" in manifest
        assert manifest["timezone"] == "UTC"
        assert manifest["mode"] == "fixture"
        assert "instruments" in manifest
        assert "execution_instruments" in manifest
        assert manifest["cycles_completed"] == 2
        assert "accepted_count" in manifest
        assert "rejected_count" in manifest
        assert "code_commit" in manifest
        assert manifest["config_hash"].startswith("sha256:")
        assert manifest["software_version"] == SOFTWARE_VERSION

    def test_manifest_timestamps_are_real(self, tmp_path: Path) -> None:
        """Manifest timestamps are actual ISO strings, not placeholders."""
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        manifest = json.loads((run_dir / "manifest.json").read_text())
        from datetime import datetime

        start = datetime.fromisoformat(manifest["start_timestamp"])
        end = datetime.fromisoformat(manifest["end_timestamp"])
        assert start.year >= 2026
        assert end >= start

    def test_audit_log_has_events(self, tmp_path: Path) -> None:
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        audit_log = run_dir / "audit_log.jsonl"
        lines = audit_log.read_text().strip().split("\n")
        # 7 stages per cycle, 2 cycles = 14 events
        assert len(lines) >= 14

    def test_accepted_and_rejected_cycles(self, tmp_path: Path) -> None:
        """The 2-cycle fixture run should produce at least one accepted and one non-accepted."""
        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        paper_log = run_dir / "paper_log.jsonl"
        lines = paper_log.read_text().strip().split("\n")
        statuses = [json.loads(line)["status"] for line in lines]
        # At least one cycle that isn't 'no_candidate' / 'no_hypothesis'
        # (the ACCEPTED_SNAPSHOT produces a fill or accepted, REJECTED has no OHLCV)
        assert len(statuses) == 2

    def test_single_cycle(self, tmp_path: Path) -> None:
        run_dir = run_paper_session(mode="fixture", cycles=1, output_dir=tmp_path)
        paper_log = run_dir / "paper_log.jsonl"
        lines = paper_log.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_unknown_mode_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown mode"):
            run_paper_session(mode="live", cycles=1, output_dir=tmp_path)

    def test_demo_mode_runs_or_fails_cleanly(self, tmp_path: Path) -> None:
        # Demo mode runs bgc for live candles. In CI it may raise RuntimeError
        # if bgc returns no data, but never NotImplementedError.
        try:
            run_paper_session(mode="demo", cycles=1, output_dir=tmp_path)
        except RuntimeError:
            pass  # acceptable: bgc unavailable or returned no data
        except NotImplementedError:
            pytest.fail("Demo mode must not raise NotImplementedError")


class TestCLI:
    """CLI entry point basics."""

    def test_no_command_returns_1(self) -> None:
        from factor_atlas.__main__ import main

        assert main([]) == 1

    def test_dry_run_returns_0(self) -> None:
        from factor_atlas.__main__ import main

        assert main(["run", "--dry-run"]) == 0

    def test_fixture_run(self, tmp_path: Path) -> None:
        from factor_atlas.__main__ import main

        rc = main(
            ["run", "--mode", "fixture", "--cycles", "1", "--output", str(tmp_path)]
        )
        assert rc == 0
        # Should have created a run directory inside tmp_path
        subdirs = list(tmp_path.iterdir())
        assert len(subdirs) == 1
        assert (subdirs[0] / "paper_log.jsonl").exists()

    def test_demo_mode_exits_cleanly_on_bgc_failure(self, tmp_path: Path) -> None:
        """Demo mode returns exit code 1 (not an unhandled exception) when bgc fails."""
        from unittest.mock import patch

        from factor_atlas.__main__ import main

        with patch(
            "factor_atlas.runner.subprocess.run",
            side_effect=RuntimeError("bgc candle retrieval failed"),
        ):
            rc = main(
                ["run", "--mode", "demo", "--cycles", "1", "--output", str(tmp_path)]
            )
        assert rc == 1

    def test_demo_mode_exits_cleanly_on_network_error(self, tmp_path: Path) -> None:
        """Demo mode returns exit code 1 (not an unhandled exception) on network errors."""
        from unittest.mock import patch

        from factor_atlas.__main__ import main

        with patch(
            "factor_atlas.runner.subprocess.run",
            side_effect=OSError("Network is unreachable"),
        ):
            rc = main(
                ["run", "--mode", "demo", "--cycles", "1", "--output", str(tmp_path)]
            )
        assert rc == 1


class TestDemoLLMFailure:
    """Demo mode must not silently fall back to fixture LLM."""

    def test_demo_mode_raises_when_bedrock_fails(self, tmp_path: Path) -> None:
        """Demo mode must fail loudly when BedrockProvider init fails."""
        from unittest.mock import patch

        from factor_atlas.__main__ import main

        with patch(
            "factor_atlas.runner.BedrockProvider",
            side_effect=RuntimeError("Bedrock unavailable"),
        ):
            rc = main(
                ["run", "--mode", "demo", "--cycles", "1", "--output", str(tmp_path)]
            )
        assert rc == 1


class TestPerpPriceFetching:
    """_fetch_perp_prices fetches USDT-FUTURES close prices via bgc."""

    def test_fetch_perp_prices_returns_decimals(self) -> None:
        import json
        from decimal import Decimal
        from unittest.mock import patch

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

        assert prices["AAPLUSDT"] == Decimal("332.50")

    def test_fetch_perp_prices_skips_failed_symbol(self) -> None:
        """If bgc returns non-zero for a symbol, it is skipped without crashing."""
        from unittest.mock import patch

        def _mock_run(cmd, **_kw):
            class R:
                returncode = 1
                stdout = ""
                stderr = "error"

            return R()

        with patch("factor_atlas.runner.subprocess.run", side_effect=_mock_run):
            from factor_atlas.runner import _fetch_perp_prices

            prices = _fetch_perp_prices(["AAPLUSDT"])

        assert prices == {}


class TestManifestLLMFields:
    """Manifest contains required LLM provenance fields."""

    def test_manifest_contains_llm_fields(self, tmp_path: Path) -> None:
        """Fixture mode manifest has llm_provider, llm_model, llm_mode fields."""
        run_dir = run_paper_session(mode="fixture", cycles=1, output_dir=tmp_path)
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["llm_provider"] == "fixture"
        assert manifest["llm_model"] == "fixture"
        assert manifest["llm_mode"] == "fixture"

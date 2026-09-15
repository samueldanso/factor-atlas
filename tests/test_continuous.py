"""Tests for continuous runner mode."""

from __future__ import annotations

from unittest.mock import patch

from factor_atlas.runner import run_continuous


def test_continuous_single_round(tmp_path) -> None:
    """Continuous mode with max_rounds=1 runs exactly one session."""
    with patch("factor_atlas.runner.run_paper_session") as mock_run:
        mock_run.return_value = tmp_path / "fake-run"
        run_continuous(
            mode="fixture",
            cycles=2,
            interval=60,
            output_dir=tmp_path,
            max_rounds=1,
        )
        assert mock_run.call_count == 1

"""Factor Atlas CLI — ``uv run python -m factor_atlas <command>``"""

from __future__ import annotations

import argparse
import sys

# Load .env before anything else so BITGET_* and AWS_* are available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factor_atlas",
        description="FactorAtlas — agentic factor discovery for tokenized stock markets.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_parser = sub.add_parser(
        "run",
        help="Run the full autonomous paper-trading loop.",
    )
    run_parser.add_argument(
        "--mode",
        choices=["fixture", "demo"],
        default="fixture",
        help="Run mode: 'fixture' (deterministic, no creds) or 'demo' (Bitget Demo). Default: fixture.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and exit without executing.",
    )
    run_parser.add_argument(
        "--cycles",
        type=int,
        default=2,
        help="Number of cycles to run. Default: 2.",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for paper logs. Default: artifacts/paper-trading/",
    )

    # --- status ---
    sub.add_parser(
        "status", help="Show open positions, closed trade metrics, and session count."
    )

    # --- history ---
    sub.add_parser("history", help="List all paper-trading sessions with key stats.")

    # --- explain ---
    explain_parser = sub.add_parser(
        "explain", help="Detailed breakdown of a single session's decisions."
    )
    explain_parser.add_argument("run_id", help="Run ID to explain.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        from pathlib import Path

        from factor_atlas.runner import run_paper_session, validate_config

        if args.dry_run:
            validate_config()
            return 0

        output_dir = Path(args.output) if args.output else None
        try:
            run_paper_session(
                mode=args.mode,
                cycles=args.cycles,
                output_dir=output_dir,
            )
        except (NotImplementedError, RuntimeError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.command == "status":
        from pathlib import Path

        from factor_atlas.cli_commands import cmd_status

        print(cmd_status(Path("artifacts/paper-trading")))
        return 0

    if args.command == "history":
        from pathlib import Path

        from factor_atlas.cli_commands import cmd_history

        print(cmd_history(Path("artifacts/paper-trading")))
        return 0

    if args.command == "explain":
        from pathlib import Path

        from factor_atlas.cli_commands import cmd_explain

        print(cmd_explain(args.run_id, Path("artifacts/paper-trading")))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

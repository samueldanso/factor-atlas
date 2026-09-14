"""One-time script to archive stale runs and restructure artifacts/paper-trading/.

Stale = fixture mode OR demo mode with zero Bitget orderIds.
Real = demo mode with at least one orderId in paper_log.jsonl.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ARTIFACTS_DIR = Path("artifacts/paper-trading")
ARCHIVE_DIR = Path("artifacts/archive")

STALE_RUN_IDS = [
    "a8fcc980-4aa0-4452-840c-cbe6b6b59b89",
    "50fb2b14-b925-4999-96f2-e9be7643abad",
    "bbc51c19-8934-460b-a261-4f81ab9ae7bc",
    "199ac5d2-b42c-494f-a481-f735cbaca21c",
    "1b35e00a-f4f6-43eb-b2b9-4075a1267d38",
    "0a0fc56b-a92a-4eec-95b4-4ac1113a33db",
    "88eaf22f-1329-45a8-9542-8c55dc5e7431",
    "41ea91ca-3121-4375-886c-8281231a2cf6",
    "919104fc-fd1c-44af-adec-0526fe107424",
]


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved = 0
    for run_id in STALE_RUN_IDS:
        src = ARTIFACTS_DIR / run_id
        if src.exists():
            dst = ARCHIVE_DIR / run_id
            shutil.move(str(src), str(dst))
            print(f"  Archived: {run_id}")
            moved += 1
        else:
            print(f"  Not found: {run_id}")

    print(f"\nArchived {moved} stale runs to {ARCHIVE_DIR}/")

    # Create logs/ directory for the evidence logger
    logs_dir = ARTIFACTS_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    print(f"Created {logs_dir}/")

    # Move remaining UUID runs to runs/ subdirectory
    runs_dir = ARTIFACTS_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)
    for item in sorted(ARTIFACTS_DIR.iterdir()):
        if item.is_dir() and item.name not in ("logs", "runs") and len(item.name) == 36:
            dst = runs_dir / item.name
            shutil.move(str(item), str(dst))
            print(f"  Moved to runs/: {item.name}")

    print("Done. Restructured artifacts/paper-trading/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rebuild the epstein_derived.db sidecar from the immutable corpora, in order.

The sidecar is fully regenerable — this is the canonical, reproducible pipeline.
Run order matters: the evidence registry must exist before the temporal/financial
builders link evidence_item_id by canonical_ref. Person resolution is independent.

    uv run python scripts/build_derived.py            # incremental (idempotent builders)
    uv run python scripts/build_derived.py --reset     # delete sidecar first, clean rebuild

Each step shells out to its builder so a failure is isolated and visible.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DERIVED_DB = PROJECT_ROOT / "datasets" / "epstein_derived.db"

STEPS = [
    ("evidence registry", ["tools/build_evidence_registry.py"]),
    ("temporal events", ["tools/build_temporal_events.py"]),
    ("financial model", ["tools/build_financials.py"]),
    ("person resolution: build", ["tools/person_resolution.py", "build"]),
    ("person resolution: reconcile", ["tools/person_resolution.py", "reconcile", "--no-dry-run"]),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true",
                    help="delete the sidecar DB (and -wal/-shm) before building")
    args = ap.parse_args()

    if args.reset:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(DERIVED_DB) + suffix)
            if p.exists():
                p.unlink()
                print(f"removed {p.name}")

    for name, cmd in STEPS:
        print(f"\n{'='*60}\n▶ {name}\n{'='*60}", flush=True)
        t0 = time.monotonic()
        result = subprocess.run(["uv", "run", "python", *cmd], cwd=PROJECT_ROOT)
        dt = time.monotonic() - t0
        if result.returncode != 0:
            print(f"\n✗ step '{name}' failed (exit {result.returncode}) after {dt:.0f}s", file=sys.stderr)
            sys.exit(result.returncode)
        print(f"✓ {name} ({dt:.0f}s)", flush=True)

    print(f"\n{'='*60}\n✓ sidecar rebuilt\n{'='*60}")
    subprocess.run(["uv", "run", "python", "tools/epstein_derived.py", "stats"], cwd=PROJECT_ROOT)


if __name__ == "__main__":
    main()

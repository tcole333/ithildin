#!/usr/bin/env python3
"""Small helper to load repo-local .env values into process env."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env_file(env_path: Path | None = None) -> None:
    """Load key=value pairs from .env without overriding existing env vars."""
    path = env_path or (PROJECT_ROOT / ".env")
    if not path.exists():
        return

    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

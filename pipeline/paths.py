"""Explicit roots for isolated export and publication builds."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = Path(os.environ.get("ITHILDIN_CONTENT_DIR", ROOT / "content")).resolve()
PUBLIC_CONTENT_DIR = Path(os.environ.get("ITHILDIN_PUBLIC_CONTENT_DIR", ROOT / "web/public/content")).resolve()
DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH") or os.environ.get("INVESTIGATION_DB_PATH") or ROOT / "investigation.db").resolve()

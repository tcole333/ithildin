"""Shared OpenCorporates credential and error diagnostics.

Keep API tokens out of exception text: ``requests`` includes the complete
request URL in several transport errors, including its ``api_token`` query
parameter.
"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

API_KEY_ENV = "OPENCORPORATES_API_KEY"
ACCOUNT_STATUS_COMMAND = (
    "uv run python tools/query_opencorporates.py account-status"
)


def get_api_key() -> str:
    """Return the configured API key or fail with setup guidance."""
    key = os.getenv(API_KEY_ENV, "").strip()
    if key:
        return key

    print(f"ERROR: {API_KEY_ENV} is not set.", file=sys.stderr)
    print(
        "Set it in the active shell or project .env, then verify it with:",
        file=sys.stderr,
    )
    print(f"  {ACCOUNT_STATUS_COMMAND}", file=sys.stderr)
    raise SystemExit(1)


def exit_for_http_error(status_code: int) -> NoReturn:
    """Report an actionable API failure without exposing response secrets."""
    if status_code == 401:
        print(
            f"ERROR: OpenCorporates rejected {API_KEY_ENV} (HTTP 401).",
            file=sys.stderr,
        )
        print(
            "Replace or remove the stale token in the active environment/.env; "
            "do not repeat searches until credential verification succeeds.",
            file=sys.stderr,
        )
        print(f"Verify with: {ACCOUNT_STATUS_COMMAND}", file=sys.stderr)
    elif status_code == 403:
        print(
            "ERROR: OpenCorporates denied this endpoint (HTTP 403); "
            "the configured account may not include access to it.",
            file=sys.stderr,
        )
        print(f"Check the account first with: {ACCOUNT_STATUS_COMMAND}", file=sys.stderr)
    elif status_code == 429:
        print(
            "ERROR: OpenCorporates rate or account quota exceeded (HTTP 429).",
            file=sys.stderr,
        )
        print(f"Check current usage with: {ACCOUNT_STATUS_COMMAND}", file=sys.stderr)
    else:
        print(
            f"ERROR: OpenCorporates request failed (HTTP {status_code}).",
            file=sys.stderr,
        )
    raise SystemExit(1)


def exit_for_transport_error(error: BaseException) -> NoReturn:
    """Report a transport failure without rendering its token-bearing URL."""
    print(
        "ERROR: OpenCorporates request failed before a response was received "
        f"({type(error).__name__}).",
        file=sys.stderr,
    )
    print(
        "Check DNS/network connectivity and retry; request URLs and credentials "
        "are intentionally redacted.",
        file=sys.stderr,
    )
    raise SystemExit(1)

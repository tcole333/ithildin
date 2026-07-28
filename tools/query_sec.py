#!/usr/bin/env python3
"""Compatibility entry point for SEC EDGAR queries.

Use ``query_sec_enforcement.py`` for SEC enforcement releases.
"""

try:
    from tools.query_edgar import main
except ImportError:
    from query_edgar import main


if __name__ == "__main__":
    main()

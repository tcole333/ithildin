#!/usr/bin/env python3
"""Probe USASpending bulk_download/awards endpoint shape with a tiny 1-day request."""
import json
import urllib.request

BASE = "https://api.usaspending.gov/api/v2"

payload = {
    "filters": {
        "prime_award_types": ["A", "B", "C", "D"],
        "agencies": [
            {"type": "awarding", "tier": "toptier", "name": "Department of Homeland Security"}
        ],
        "date_type": "action_date",
        "date_range": {"start_date": "2025-02-03", "end_date": "2025-02-04"},
    },
    "file_format": "csv",
}

req = urllib.request.Request(
    f"{BASE}/bulk_download/awards/",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "User-Agent": "osint-research-census/0.1"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
        print("HTTP", resp.status)
        print(json.dumps(body, indent=2)[:3000])
except urllib.error.HTTPError as e:
    print("HTTPError", e.code)
    print(e.read().decode()[:3000])

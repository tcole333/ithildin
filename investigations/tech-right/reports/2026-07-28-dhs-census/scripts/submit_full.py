#!/usr/bin/env python3
"""Submit the full-window DHS bulk download as two <=1yr jobs and save job info."""
import json
import sys
import time
import urllib.request

BASE = "https://api.usaspending.gov/api/v2"

WINDOWS = [
    ("2025-01-20", "2026-01-19"),
    ("2026-01-20", "2026-07-28"),
]

AWARD_TYPES = [
    "A", "B", "C", "D",
    "IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E",
]


def submit(start, end):
    payload = {
        "filters": {
            "prime_award_types": AWARD_TYPES,
            "agencies": [
                {"type": "awarding", "tier": "toptier", "name": "Department of Homeland Security"}
            ],
            "date_type": "action_date",
            "date_range": {"start_date": start, "end_date": end},
        },
        "file_format": "csv",
    }
    req = urllib.request.Request(
        f"{BASE}/bulk_download/awards/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "osint-research-census/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


jobs = []
for start, end in WINDOWS:
    try:
        body = submit(start, end)
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, "for", start, end)
        print(e.read().decode()[:2000])
        sys.exit(1)
    jobs.append({"start": start, "end": end, **body})
    print(f"submitted {start}..{end}: {body['file_name']}")
    time.sleep(2)

with open("/tmp/osint-GWLtvuxV/work-census/full_jobs.json", "w") as f:
    json.dump(jobs, f, indent=2)

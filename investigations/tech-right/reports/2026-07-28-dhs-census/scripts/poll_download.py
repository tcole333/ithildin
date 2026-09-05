#!/usr/bin/env python3
"""Poll the two bulk download jobs; download + extract when finished. Resumable via state.json."""
import json
import os
import subprocess
import sys
import time
import urllib.request

WORK = "/tmp/osint-GWLtvuxV/work-census"
STATE = os.path.join(WORK, "state.json")


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"jobs": {}}


def save_state(state):
    with open(STATE + ".tmp", "w") as f:
        json.dump(state, f, indent=2)
    os.replace(STATE + ".tmp", STATE)


def check_status(file_name):
    url = f"https://api.usaspending.gov/api/v2/download/status?file_name={file_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "osint-research-census/0.1"})
    backoff = 5
    for _ in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            code = getattr(e, "code", None)
            if code and code < 500 and code != 429:
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)
    raise RuntimeError(f"status polling failed for {file_name}")


def main():
    with open(os.path.join(WORK, "full_jobs.json")) as f:
        jobs = json.load(f)
    state = load_state()

    deadline = time.time() + 45 * 60
    pending = {j["file_name"]: j for j in jobs}
    for fn in list(pending):
        if state["jobs"].get(fn, {}).get("extracted"):
            print(f"already extracted: {fn}")
            del pending[fn]

    while pending and time.time() < deadline:
        for fn, job in list(pending.items()):
            st = check_status(fn)
            rec = state["jobs"].setdefault(fn, {"window": [job["start"], job["end"]]})
            rec["last_status"] = {k: st.get(k) for k in ("status", "total_rows", "total_size", "seconds_elapsed", "message")}
            save_state(state)
            print(f"{fn}: {st['status']} rows={st.get('total_rows')} size_kb={st.get('total_size')}")
            if st["status"] == "finished":
                zpath = os.path.join(WORK, fn)
                if not rec.get("downloaded"):
                    print(f"downloading {fn} ...")
                    subprocess.run(
                        ["curl", "-sL", "--retry", "3", "--retry-delay", "10", "-o", zpath, st["file_url"]],
                        check=True,
                    )
                    rec["downloaded"] = True
                    rec["zip_bytes"] = os.path.getsize(zpath)
                    save_state(state)
                exdir = os.path.join(WORK, "raw", fn.replace(".zip", ""))
                os.makedirs(exdir, exist_ok=True)
                subprocess.run(["unzip", "-o", "-q", "-d", exdir, zpath], check=True)
                rec["extracted"] = True
                rec["extract_dir"] = exdir
                rec["csv_files"] = sorted(os.listdir(exdir))
                save_state(state)
                print(f"extracted to {exdir}: {rec['csv_files']}")
                del pending[fn]
            elif st["status"] == "failed":
                print(f"JOB FAILED: {fn}: {st.get('message')}")
                del pending[fn]
        if pending:
            time.sleep(30)

    if pending:
        print(f"TIMEOUT waiting on: {list(pending)}")
        sys.exit(2)
    print("all jobs done")


if __name__ == "__main__":
    main()

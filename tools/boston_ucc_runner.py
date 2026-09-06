#!/usr/bin/env python3
"""Run a Boston holder queue serially through the existing verified UCC tool.

Bounded batches reuse one isolated visible Chrome through serial JSONL requests.
Raw HTML and structured results are saved before checkpointing queue progress. Stops on the first error;
never retries access challenges. Filing histories and attachments are separate.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.boston_license_review import coverage, load, load_events, merge_events, save, validate_event, validate_queue
    from tools.lead_tracker import check_searched, log_search
    from tools.query_massachusetts_ucc import BrowserSession, PortalError, SOURCE_NAME, recover_transport
    from tools.search_log_util import canonical_search_key
except ImportError:
    from boston_license_review import coverage, load, load_events, merge_events, save, validate_event, validate_queue
    from lead_tracker import check_searched, log_search
    from query_massachusetts_ucc import BrowserSession, PortalError, SOURCE_NAME, recover_transport
    from search_log_util import canonical_search_key


def search_key(payload: dict) -> str:
    return canonical_search_key(payload["command"], payload["query"], **{
        key: value for key, value in payload.items() if key not in {"command", "query"}
    })


def needs_name_review(holder: dict) -> bool:
    return bool(holder.get("query_input_requires_review") or holder.get("name_mode_review_reasons"))


def sync_event_log(events_path: Path, checkpoint_path: Path, logger=None) -> dict:
    """Log saved source results once per event checkpoint; makes no network call."""
    logger = logger or log_search
    checkpoint = load(checkpoint_path) if checkpoint_path.exists() else {"logged_event_hashes": []}
    done = set(checkpoint["logged_event_hashes"])
    logged = skipped = 0
    for event in load_events(events_path):
        if event.get("state") not in {"complete", "partial"}:
            skipped += 1
            continue
        validate_event(event, {event.get("holder_id")})
        reported, returned = event.get("reported_count"), event.get("returned_count")
        if type(reported) is not int or type(returned) is not int or not 0 <= returned <= reported:
            raise ValueError("Only saved result events with valid counts can enter search_log")
        identity = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        if identity in done:
            continue
        payload = {**event["query"], "lapsed": event["scope"] == "lapsed"}
        logger(search_key(payload), SOURCE_NAME, returned)
        done.add(identity)
        logged += 1
        save(checkpoint_path, {"events_file": str(events_path.resolve()),
                               "updated_at": datetime.now(timezone.utc).isoformat(),
                               "logged_event_hashes": sorted(done)})
    return {"new_events_logged": logged, "total_checkpointed_events": len(done), "nonresult_events_skipped": skipped}


def result_event(holder: dict, scope: str, payload: dict, result: dict, source: Path) -> dict:
    if result.get("query") != payload or result.get("scope") != scope:
        raise ValueError("Saved result query/scope differs from the queued request")
    reported, returned = result.get("reported_count"), result.get("returned")
    rows = result.get("results")
    if (type(reported) is not int or type(returned) is not int or not isinstance(rows, list)
            or returned != len(rows) or returned < 0 or reported < returned
            or result.get("truncated") != (returned < reported)):
        raise ValueError("Result count/rows/truncation fields are inconsistent")
    return {
        "holder_id": holder["holder_id"], "scope": scope,
        "state": "partial" if result["truncated"] else "complete", "query": payload,
        "reported_count": reported, "returned_count": returned, "truncated": result["truncated"],
        "source_file": str(source.resolve()), "source_file_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_url": result["source_url"], "retrieved_at": result["retrieved_at"],
        "capture_method": ("query_massachusetts_ucc structured parser output; complete source HTML checkpoint retained"
                           if result.get("transport_capture") else
                           "query_massachusetts_ucc structured parser output; page hashes/URLs retained, HTML not saved"),
        "review": {"history_state": "not_started", "attachments_state": "not_started",
                   "original_filing_numbers": sorted({row["original_filing_number"] for row in rows if row.get("original_filing_number")}),
                   "name_match_state": "pending_review" if rows else "no_rows_for_this_query"},
    }


class BrowserPool:
    """Recycle an owned browser only at the configured bounded batch boundary."""

    def __init__(self, batch_size):
        if type(batch_size) is not int or not 1 <= batch_size <= 50:
            raise ValueError("batch_size must be 1–50")
        self.batch_size = batch_size
        self.session = None
        self.sessions_started = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.session:
            self.session.close()

    def execute(self, payload, raw_path):
        if self.session and self.session.requests >= self.batch_size:
            self.session.close()
            self.session = None
        if self.session is None:
            self.session = BrowserSession(self.batch_size)
            self.sessions_started += 1
        return self.session.execute(payload, raw_path)


def append_event(path, event):
    # Logically append-only, but atomically replace to avoid an unreadable final
    # JSONL line after interruption. The runner lock serializes these updates.
    previous = path.read_bytes() if path.exists() else b""
    if previous and not previous.endswith(b"\n"):
        raise ValueError("Event journal lacks its final newline; preserve and review it before resuming")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(previous)
            stream.write(json.dumps(event, ensure_ascii=False).encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def run(queue_path: Path, output_dir: Path, scope: str, max_queries: int | None = None,
        spacing: float = 1.0, stop_file: Path | None = None, executor=None, searched=None,
        batch_size: int = 20, events_path: Path | None = None) -> dict:
    if scope not in {"current", "lapsed"}:
        raise ValueError("scope must be current or lapsed")
    searched = searched or check_searched
    output_dir.mkdir(parents=True, exist_ok=True)
    queue = load(queue_path)
    validate_queue(queue)
    network_calls = cached_results = processed = 0
    deferred = []
    last_finish = 0.0
    started = datetime.now(timezone.utc).isoformat()
    outcome = "pending_exhausted"
    result_dir = output_dir / "results"
    result_dir.mkdir(exist_ok=True)
    checkpoint = output_dir / "progress.json"
    stop_file = stop_file or output_dir / "STOP"
    lock_path = queue_path.with_suffix(queue_path.suffix + ".lock")
    with BrowserPool(batch_size) as pool, lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another runner holds this queue lock") from error
        # Reload after taking the exclusive runner lock.
        queue = load(queue_path)
        events_path = events_path or queue_path.parent / "ucc-cua" / "events.jsonl"
        if events_path.exists():
            queue = merge_events(queue, load_events(events_path))
        own_events = output_dir / "events.jsonl"
        if own_events.exists():
            queue = merge_events(queue, load_events(own_events))
        for holder in queue["holders"]:
            if needs_name_review(holder) and holder["searches"][scope]["state"] == "pending":
                holder["name_mode_review_state"] = "needs_review"
                deferred.append({"holder_id": holder["holder_id"], "state": "needs_review",
                                 "reasons": holder.get("name_mode_review_reasons", []),
                                 "query": holder["query_proposal"], "scope": scope})
        save(queue_path, queue)
        for holder in queue["holders"]:
            if holder["searches"][scope]["state"] != "pending":
                continue
            if needs_name_review(holder):
                continue
            if stop_file.exists():
                outcome = "stop_file"
                break
            payload = {**holder["query_proposal"], "lapsed": scope == "lapsed"}
            key = search_key(payload)
            source = result_dir / (hashlib.sha256(key.encode()).hexdigest() + ".json")
            raw_source = output_dir / "raw" / source.name
            prior_log = None
            try:
                prior_log = searched(key, SOURCE_NAME)
                if source.exists():
                    result = load(source)
                    cached_results += 1
                elif raw_source.exists():
                    result = recover_transport(raw_source, payload)
                    save(source, result)
                    cached_results += 1
                else:
                    if max_queries is not None and network_calls >= max_queries:
                        outcome = "query_limit"
                        break
                    remaining = max(1.0, spacing) - (time.monotonic() - last_finish)
                    if remaining > 0:
                        time.sleep(remaining)
                    if stop_file.exists():
                        outcome = "stop_file"
                        break
                    network_calls += 1
                    result = executor(payload) if executor else pool.execute(payload, raw_source)
                    last_finish = time.monotonic()
                    save(source, result)
                event = result_event(holder, scope, payload, result, source)
                event["canonical_search_key"] = key
                event["prior_search_log_present"] = prior_log is not None
                # A search log row alone never certifies completeness or replaces evidence.
                event["prior_search_log_result_count"] = prior_log.get("result_count") if prior_log else None
            except (PortalError, ValueError, OSError) as error:
                error_file = output_dir / f"{holder['holder_id']}-{scope}-error.json"
                failure = {
                    "holder_id": holder["holder_id"], "scope": scope, "state": "blocked",
                    "query": payload, "error": str(error), "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "source_file": str(error_file.resolve()), "capture_method": "runner error; no completed source result",
                    "canonical_search_key": key, "prior_search_log_present": prior_log is not None,
                }
                save(error_file, failure)
                queue = merge_events(queue, [failure])
                save(queue_path, queue)
                outcome = "stopped_on_error"
                print(json.dumps({"event": outcome, "holder_id": holder["holder_id"], "query": payload["query"], "error": str(error)}), flush=True)
                break
            append_event(own_events, event)
            queue = merge_events(queue, [event])
            save(queue_path, queue)
            processed += 1
            progress = {"started_at": started, "scope": scope, "processed_this_run": processed,
                        "network_calls": network_calls, "cached_results": cached_results,
                        "last_holder_id": holder["holder_id"], "coverage": coverage(queue)}
            save(checkpoint, progress)
            if processed % 10 == 0 or max_queries is not None:
                print(json.dumps({"event": "progress", "processed": processed, "network_calls": network_calls,
                                  "last_holder_id": holder["holder_id"], "search_states": progress["coverage"]["search_states"]}), flush=True)
        if outcome == "pending_exhausted" and deferred:
            outcome = "organization_queue_exhausted_with_name_review"
        final = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "scope": scope,
                 "outcome": outcome, "processed_this_run": processed, "network_calls": network_calls,
                 "cached_results": cached_results, "browser_sessions_started": pool.sessions_started,
                 "deferred_name_reviews": len(deferred), "coverage": coverage(queue)}
        save(output_dir / "needs-review.json", deferred)
        save(checkpoint, final)
        return final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--scope", choices=("current", "lapsed"))
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--batch-size", type=int, default=20, help="Requests per isolated Chrome session, 1–50 (default 20)")
    parser.add_argument("--events", type=Path, help="Import saved CUA events before selecting work; defaults to queue parent/ucc-cua/events.jsonl")
    parser.add_argument("--spacing", type=float, default=1.0)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--sync-events", type=Path, help="Only synchronize saved events into search_log; no browser/network")
    parser.add_argument("--log-checkpoint", type=Path)
    args = parser.parse_args(argv)
    if args.sync_events:
        if not args.log_checkpoint:
            parser.error("--sync-events requires --log-checkpoint")
        try:
            print(json.dumps(sync_event_log(args.sync_events, args.log_checkpoint), indent=2))
            return 0
        except (ValueError, OSError) as error:
            parser.exit(1, f"ERROR: {error}\n")
    if not args.queue or not args.output_dir or not args.scope:
        parser.error("Runner requires --queue, --output-dir and --scope")
    if args.max_queries is not None and args.max_queries < 1:
        parser.error("--max-queries must be positive")
    if args.spacing < 1:
        parser.error("--spacing must be at least one second")
    if not 1 <= args.batch_size <= 50:
        parser.error("--batch-size must be 1–50")
    try:
        result = run(args.queue, args.output_dir, args.scope, args.max_queries, args.spacing, args.stop_file,
                     batch_size=args.batch_size, events_path=args.events)
    except (ValueError, OSError) as error:
        parser.exit(1, f"ERROR: {error}\n")
    print(json.dumps(result, indent=2))
    return 1 if result["outcome"] == "stopped_on_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

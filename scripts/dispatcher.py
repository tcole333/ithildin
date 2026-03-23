#!/usr/bin/env python3
"""
Investigation-aware pipeline dispatcher — launches headless Claude Code instances
to process investigation queues (triage, pursue-lead, build-infra, auto-leads).

This is the primary dispatcher for investigation work. It reads lead priorities,
triage scheduler fields (depth_tier, recommended_skill), and analysis cooldowns
to decide WHAT to run. Uses the dispatch_runs table to track execution.

See also: queue_dispatcher.py (generic job queue worker manager) and
queue_system/ (job queue infrastructure with heartbeat tracking). Those systems
use separate tables (job_queue, agent_instances) and operate independently.

Usage:
    uv run python scripts/dispatcher.py run          # One-shot: check queues, launch needed agents
    uv run python scripts/dispatcher.py daemon        # Loop: poll every N seconds
    uv run python scripts/dispatcher.py status        # Show running/recent dispatch_runs
    uv run python scripts/dispatcher.py stop [--all]  # Kill running instances
"""

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "investigation.db"
CONFIG_PATH = Path(__file__).resolve().parent / "dispatch_config.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

SKILL_PATHS = {
    "triage": SKILLS_DIR / "triage-leads" / "SKILL.md",
    "pursue_lead": SKILLS_DIR / "pursue-lead" / "SKILL.md",
    "deep_investigate": SKILLS_DIR / "deep-investigate" / "SKILL.md",
    "build_infra": SKILLS_DIR / "build-infra" / "SKILL.md",
    "analyze_network": SKILLS_DIR / "analyze-network" / "SKILL.md",
    "generate_hunches": SKILLS_DIR / "generate-hunches" / "SKILL.md",
    "timeline_analysis": SKILLS_DIR / "timeline-analysis" / "SKILL.md",
    "systemic_analysis": SKILLS_DIR / "systemic-analysis" / "SKILL.md",
}

PROMPTS = {
    "triage": (
        "Process the next batch of pending_triage leads. Claim up to 20, "
        "deduplicate against existing leads, adjust priorities, and promote to open. "
        "Dead-end duplicates. Report results."
    ),
    "pursue_lead": "Claim and investigate lead #{target}. Follow the pursue-lead methodology. "
        "Use --output /tmp/... on all searches. Record findings with full provenance. "
        "Complete the lead when done.",
    "deep_investigate": "Run a deep investigation on {target}. Follow the deep-investigate methodology. "
        "Use --output /tmp/... on all searches. Record findings with full provenance.",
    "build_infra": "Claim infra request #{target} and build it. Probe the endpoint first, "
        "confirm it works, then write the tool. Test against known targets. "
        "Update CLAUDE.md and TOOL_REFERENCE.md. Complete the request.",
    "auto_leads": "Run: uv run python tools/auto_leads.py run\nReport the results.",
    "analyze_network": "Run the /analyze-network skill. Analyze the investigation graph for structural patterns, "
        "centrality, bridges, clusters, cross-thread actors, and coverage gaps. "
        "Record findings, tag clusters, generate hypotheses, create leads for gaps.",
    "generate_hunches": "Run the /generate-hunches skill. Scan findings and entity data for emerging themes "
        "and recurring patterns that cross unexpected boundaries. "
        "Generate hypotheses with testable search plans. Quality over quantity.",
    "timeline_analysis": "Run the /timeline-analysis skill. Analyze temporal patterns in findings — "
        "activity clusters, pre-event spikes, silence periods, coordinated action windows. "
        "Cross-reference with event timeline.",
    "systemic_analysis": "Run the /systemic-analysis skill. Analyze the largest investigation thread's actors "
        "as a system — shared boards, co-investments, common counsel, jurisdiction clustering. "
        "Focus on non-subject connections between actors.",
}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def ensure_dispatch_table(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS dispatch_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            target TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed','timeout')),
            session_id TEXT,
            prompt_hash TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            exit_code INTEGER,
            cost_usd REAL,
            findings_added INTEGER,
            leads_created INTEGER,
            output_file TEXT,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_runs(status);
        CREATE INDEX IF NOT EXISTS idx_dispatch_type ON dispatch_runs(run_type);
        CREATE INDEX IF NOT EXISTS idx_dispatch_started ON dispatch_runs(started_at);
    """)


# ── Queue depth queries ──────────────────────────────────────────────

def is_system_paused(db):
    """Check system_state for pause flag (safe if table missing)."""
    try:
        row = db.execute("SELECT value FROM system_state WHERE key='paused'").fetchone()
        return row and row["value"] == "true"
    except sqlite3.OperationalError:
        return False


def get_queue_depths(db):
    """Get current queue depths from investigation.db."""
    depths = {}

    row = db.execute("SELECT COUNT(*) as n FROM leads WHERE status='pending_triage'").fetchone()
    depths["pending_triage"] = row["n"]

    row = db.execute("SELECT COUNT(*) as n FROM leads WHERE status='open'").fetchone()
    depths["open_leads"] = row["n"]

    row = db.execute(
        "SELECT COUNT(*) as n FROM leads WHERE status='open' AND priority IN ('critical','high')"
    ).fetchone()
    depths["high_critical_open"] = row["n"]

    # Depth tier distribution (from triage scheduler)
    try:
        for tier_row in db.execute(
            "SELECT COALESCE(depth_tier, 'untiered') as tier, COUNT(*) as n "
            "FROM leads WHERE status='open' GROUP BY tier"
        ).fetchall():
            depths[f"tier_{tier_row['tier']}"] = tier_row["n"]
    except Exception:
        pass

    row = db.execute(
        "SELECT COUNT(*) as n FROM infra_requests WHERE status IN ('open','evaluating')"
    ).fetchone()
    depths["infra_open"] = row["n"]

    # Count leads completed since last auto_leads run
    last_auto = db.execute(
        "SELECT MAX(started_at) as t FROM dispatch_runs WHERE run_type='auto_leads' AND status='completed'"
    ).fetchone()
    since = last_auto["t"] if last_auto and last_auto["t"] else "1970-01-01"
    row = db.execute(
        "SELECT COUNT(*) as n FROM leads WHERE status='completed' AND completed_at > ?", (since,)
    ).fetchone()
    depths["completions_since_last_auto"] = row["n"]

    # Analysis queue depths — new findings since each skill's last run
    analysis_skills = ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]
    findings_total = db.execute("SELECT COUNT(*) as n FROM findings").fetchone()["n"]
    connections_total = db.execute("SELECT COUNT(*) as n FROM connections").fetchone()["n"]

    for skill in analysis_skills:
        try:
            last = db.execute(
                "SELECT findings_at_start, completed_at FROM analysis_runs "
                "WHERE skill_name = ? AND status = 'completed' ORDER BY completed_at DESC LIMIT 1",
                (skill.replace("_", "-"),)
            ).fetchone()
            if last:
                depths[f"{skill}_new_findings"] = findings_total - (last["findings_at_start"] or 0)
                depths[f"{skill}_last_run"] = last["completed_at"]
            else:
                depths[f"{skill}_new_findings"] = findings_total
                depths[f"{skill}_last_run"] = None
        except Exception:
            depths[f"{skill}_new_findings"] = findings_total
            depths[f"{skill}_last_run"] = None

    return depths


def get_running_instances(db):
    return [dict(r) for r in db.execute(
        "SELECT * FROM dispatch_runs WHERE status='running' ORDER BY started_at"
    ).fetchall()]


def any_running(db, run_type):
    row = db.execute(
        "SELECT COUNT(*) as n FROM dispatch_runs WHERE status='running' AND run_type=?",
        (run_type,)
    ).fetchone()
    return row["n"] > 0


def count_running(db, run_type):
    row = db.execute(
        "SELECT COUNT(*) as n FROM dispatch_runs WHERE status='running' AND run_type=?",
        (run_type,)
    ).fetchone()
    return row["n"]


def get_next_lead_id(db, for_skill=None):
    """Get highest-priority open lead not already being dispatched.

    Args:
        for_skill: If set, prefer leads whose recommended_skill matches.
                   Falls back to any high/critical lead if no match found.
    """
    running_targets = [
        r["target"] for r in db.execute(
            "SELECT target FROM dispatch_runs WHERE status='running' AND run_type IN ('pursue_lead','deep_investigate')"
        ).fetchall()
    ]
    placeholders = ",".join("?" for _ in running_targets) if running_targets else "''"

    # Try recommended_skill match first (from triage scheduler)
    # Use shared policy constants for skill name resolution
    if for_skill:
        try:
            from tools.triage_policy import SKILL_RECOMMENDATION
            valid_skills = set(SKILL_RECOMMENDATION.values())
        except ImportError:
            valid_skills = set()
        skill_map = {"pursue_lead": "/pursue-lead", "deep_investigate": "/deep-investigate"}
        skill_value = skill_map.get(for_skill, for_skill)
        query = f"""
            SELECT id FROM leads
            WHERE status = 'open' AND recommended_skill = ?
            AND CAST(id AS TEXT) NOT IN ({placeholders})
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                              WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                created_at ASC
            LIMIT 1
        """
        row = db.execute(query, [skill_value] + running_targets).fetchone()
        if row:
            return str(row["id"])

    # Fallback: any high/critical open lead
    query = f"""
        SELECT id FROM leads
        WHERE status = 'open' AND priority IN ('critical','high')
        AND CAST(id AS TEXT) NOT IN ({placeholders})
        ORDER BY
            CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 END,
            created_at ASC
        LIMIT 1
    """
    row = db.execute(query, running_targets).fetchone()
    return str(row["id"]) if row else None


def get_next_infra_id(db):
    """Get next open infra request not already being dispatched."""
    running_targets = [
        r["target"] for r in db.execute(
            "SELECT target FROM dispatch_runs WHERE status='running' AND run_type='build_infra'"
        ).fetchall()
    ]
    placeholders = ",".join("?" for _ in running_targets) if running_targets else "''"

    query = f"""
        SELECT id FROM infra_requests
        WHERE status IN ('open','evaluating')
        AND CAST(id AS TEXT) NOT IN ({placeholders})
        ORDER BY
            CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
            created_at ASC
        LIMIT 1
    """
    row = db.execute(query, running_targets).fetchone()
    return str(row["id"]) if row else None


# ── Process management ────────────────────────────────────────────────

def process_alive(pid):
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def reap_completed(db, config):
    """Check running instances, finalize any that have exited."""
    timeout = config.get("timeout_seconds", 1800)
    running = get_running_instances(db)

    for run in running:
        pid = run["pid"]
        started = datetime.fromisoformat(run["started_at"])
        elapsed = (utcnow() - started).total_seconds()

        if not process_alive(pid):
            finalize_run(db, run)
        elif elapsed > timeout:
            # Kill timed-out process
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                if process_alive(pid):
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            db.execute(
                "UPDATE dispatch_runs SET status='timeout', completed_at=CURRENT_TIMESTAMP, "
                "error='Exceeded timeout of {}s' WHERE id=?".format(timeout),
                (run["id"],)
            )
            db.commit()
            print(f"  [timeout] #{run['id']} {run['run_type']} (PID {pid}, {elapsed:.0f}s)")


def finalize_run(db, run):
    """Parse output and update dispatch_runs for a completed process."""
    output_file = run.get("output_file")
    exit_code = None
    cost = None
    session_id = None
    error_msg = None
    findings_added = None
    leads_created = None

    # Try to parse JSON output
    if output_file and Path(output_file).exists():
        try:
            raw = Path(output_file).read_text()
            if raw.strip():
                data = json.loads(raw)
                cost = data.get("total_cost_usd") or data.get("cost_usd") or data.get("costUSD")
                session_id = data.get("session_id") or data.get("sessionId")
                exit_code = 0
                # Try to extract stats from result text
                result = data.get("result", "")
                if isinstance(result, str):
                    if "findings" in result.lower():
                        # Try to parse "N findings" from output
                        import re
                        m = re.search(r"(\d+)\s+finding", result)
                        if m:
                            findings_added = int(m.group(1))
                    if "lead" in result.lower():
                        import re
                        m = re.search(r"(\d+)\s+lead", result)
                        if m:
                            leads_created = int(m.group(1))
        except (json.JSONDecodeError, KeyError):
            exit_code = 1
            error_msg = "Failed to parse JSON output"
    else:
        exit_code = 1
        error_msg = "No output file found"

    status = "completed" if exit_code == 0 else "failed"

    db.execute(
        """UPDATE dispatch_runs SET
            status=?, completed_at=CURRENT_TIMESTAMP, exit_code=?,
            cost_usd=?, session_id=?, findings_added=?, leads_created=?, error=?
        WHERE id=?""",
        (status, exit_code, cost, session_id, findings_added, leads_created, error_msg, run["id"])
    )
    db.commit()
    print(f"  [{status}] #{run['id']} {run['run_type']} target={run.get('target', 'batch')}"
          f" cost=${cost or 0:.2f}")


def build_prompt(run_type, target):
    template = PROMPTS[run_type]
    if "{target}" in template:
        return template.format(target=target)
    return template


def prompt_hash(run_type, target):
    key = f"{run_type}:{target or 'batch'}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def launch_agent(db, config, run_type, target):
    """Launch a headless Claude Code instance."""
    skill_path = SKILL_PATHS.get(run_type)
    prompt = build_prompt(run_type, target)
    phash = prompt_hash(run_type, target)

    # Check for duplicate running prompt
    row = db.execute(
        "SELECT id FROM dispatch_runs WHERE prompt_hash=? AND status='running'", (phash,)
    ).fetchone()
    if row:
        print(f"  [skip] {run_type} target={target} already running (#{row['id']})")
        return False

    ts = utcnow().strftime("%Y%m%d-%H%M%S")
    output_file = f"/tmp/dispatch-{run_type}-{target or 'batch'}-{ts}.json"

    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--allowedTools", config.get("allowed_tools", "Bash,Read,Write,Edit,Glob,Grep,Task,WebFetch,WebSearch"),
        "--no-session-persistence",
    ]

    # Add skill content as system prompt (not for auto_leads — simple command)
    if skill_path and skill_path.exists():
        skill_content = skill_path.read_text()
        cmd.extend(["--append-system-prompt", skill_content])

    # Model
    model = config.get("model")
    if model:
        cmd.extend(["--model", model])

    # Unset CLAUDECODE env var so nested claude works
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    out_fh = open(output_file, "w")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=out_fh,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
    except FileNotFoundError:
        out_fh.close()
        print(f"  [error] 'claude' not found in PATH")
        return False

    db.execute(
        """INSERT INTO dispatch_runs (run_type, target, pid, status, prompt_hash, output_file)
           VALUES (?, ?, ?, 'running', ?, ?)""",
        (run_type, target, proc.pid, phash, output_file)
    )
    db.commit()
    print(f"  [launch] {run_type} target={target or 'batch'} PID={proc.pid} → {output_file}")
    return True


# ── Dispatch cycle ────────────────────────────────────────────────────

def check_daily_budget(db, config):
    """Check if daily budget has been exceeded."""
    limit = config.get("daily_budget_usd", 50.0)
    today = utcnow().strftime("%Y-%m-%d")
    row = db.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) as total FROM dispatch_runs WHERE started_at >= ?",
        (today,)
    ).fetchone()
    spent = row["total"]
    return spent, limit, spent < limit


def dispatch_cycle(config, dry_run=False):
    """One dispatch cycle: reap, check queues, launch agents."""
    db = get_db()
    ensure_dispatch_table(db)

    # Reap completed processes
    reap_completed(db, config)

    # Respect global pause
    if is_system_paused(db):
        print("  [paused] system_state.paused=true — no launches")
        db.close()
        return

    # Get queue depths
    queues = get_queue_depths(db)
    running = get_running_instances(db)
    total_running = len(running)
    max_concurrent = config.get("max_concurrent", 3)

    if total_running >= max_concurrent:
        print(f"  [full] {total_running}/{max_concurrent} slots occupied — no launches")
        db.close()
        return

    slots_available = max_concurrent - total_running
    launches = []
    triggers = config.get("triggers", {})

    # Rule 1: Triage (low cost, high value, batch)
    trig = triggers.get("triage", {})
    if queues["pending_triage"] >= trig.get("min_pending", 1) and not any_running(db, "triage"):
        launches.append(("triage", None))

    # Rule 2: Infra requests (unblocks leads)
    trig = triggers.get("build_infra", {})
    if queues["infra_open"] >= trig.get("min_open", 1) and not any_running(db, "build_infra"):
        next_infra = get_next_infra_id(db)
        if next_infra:
            launches.append(("build_infra", next_infra))

    # Rule 3: High-priority leads (core research)
    # Use triage scheduler's recommended_skill when available
    trig = triggers.get("pursue_lead", {})
    max_research = config.get("max_research_agents", 2)
    research_running = count_running(db, "pursue_lead") + count_running(db, "deep_investigate")
    if queues["high_critical_open"] >= trig.get("min_high_critical", 1) and research_running < max_research:
        # Check for deep_dive leads first (triage recommended /deep-investigate)
        deep_lead = get_next_lead_id(db, for_skill="deep_investigate")
        if deep_lead and not any_running(db, "deep_investigate"):
            launches.append(("deep_investigate", deep_lead))
        else:
            next_lead = get_next_lead_id(db, for_skill="pursue_lead") or get_next_lead_id(db)
            if next_lead:
                launches.append(("pursue_lead", next_lead))
        # Fill remaining research slots with pursue_lead
        while research_running + sum(1 for t, _ in launches if t in ("pursue_lead", "deep_investigate")) < max_research:
            another = get_next_lead_id(db)
            used = {t for _, t in launches}
            if another and another not in used:
                launches.append(("pursue_lead", another))
            else:
                break

    # Rule 4: Auto-leads after completions
    trig = triggers.get("auto_leads", {})
    if (queues["completions_since_last_auto"] >= trig.get("completions_since_last", 10)
            and not any_running(db, "auto_leads")):
        launches.append(("auto_leads", None))

    # Rule 5: Analysis skills (lower priority than data gathering)
    max_analysis = config.get("max_analysis_agents", 1)
    analysis_running = sum(
        count_running(db, s) for s in
        ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]
    )
    if analysis_running < max_analysis:
        # Check each analysis skill by priority order
        for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]:
            trig = triggers.get(skill, {})
            min_new = trig.get("new_findings_since_last", 50)
            cooldown_hours = trig.get("cooldown_hours", 48)

            new_findings = queues.get(f"{skill}_new_findings", 0)
            last_run = queues.get(f"{skill}_last_run")

            # Check cooldown
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    hours_since = (utcnow() - last_dt).total_seconds() / 3600
                    if hours_since < cooldown_hours:
                        continue
                except (ValueError, TypeError):
                    pass

            if new_findings >= min_new and not any_running(db, skill):
                launches.append((skill, None))
                break  # Only one analysis agent at a time

    # Cap to available slots
    launches = launches[:slots_available]

    if not launches:
        print("  [idle] No launches needed")
    elif dry_run:
        for run_type, target in launches:
            print(f"  [dry-run] Would launch {run_type} target={target or 'batch'}")
    else:
        for run_type, target in launches:
            launch_agent(db, config, run_type, target)

    db.close()


# ── Subcommands ───────────────────────────────────────────────────────

def cmd_run(args):
    config = load_config()
    ts = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Dispatcher one-shot ({ts})")
    dispatch_cycle(config, dry_run=args.dry_run)


def cmd_daemon(args):
    config = load_config()
    interval = args.interval or config.get("poll_interval_seconds", 300)
    print(f"Dispatcher daemon started (poll every {interval}s, Ctrl-C to stop)")

    try:
        while True:
            ts = utcnow().strftime("%H:%M:%S")
            print(f"\n[{ts}] Dispatch cycle")
            try:
                dispatch_cycle(config)
            except Exception as e:
                print(f"  [error] {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def cmd_status(args):
    db = get_db()
    ensure_dispatch_table(db)
    paused = is_system_paused(db)

    # Running
    running = get_running_instances(db)
    config = load_config()
    max_c = config.get("max_concurrent", 3)

    print(f"Dispatcher Status ({utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
    print(f"Paused: {'yes' if paused else 'no'}")
    print("=" * 55)

    if running:
        print(f"\nRUNNING ({len(running)}/{max_c} max):")
        for r in running:
            started = datetime.fromisoformat(r["started_at"])
            elapsed = utcnow() - started
            mins = int(elapsed.total_seconds() / 60)
            alive = "alive" if process_alive(r["pid"]) else "DEAD"
            print(f"  #{r['id']:>3} {r['run_type']:<18} target={r['target'] or 'batch':<10} "
                  f"PID {r['pid']}  {mins}m ago  [{alive}]")
    else:
        print(f"\nRUNNING (0/{max_c} max): none")

    # Recent (24h)
    cutoff = (utcnow() - timedelta(hours=24)).isoformat()
    recent = db.execute(
        "SELECT * FROM dispatch_runs WHERE status != 'running' AND started_at > ? "
        "ORDER BY started_at DESC LIMIT 20", (cutoff,)
    ).fetchall()

    if recent:
        print(f"\nRECENT (24h):")
        for r in recent:
            findings = f"{r['findings_added'] or '?'} findings" if r["run_type"] != "triage" else ""
            leads = f"{r['leads_created'] or '?'} leads" if r["leads_created"] else ""
            started = datetime.fromisoformat(r["started_at"])
            ended = datetime.fromisoformat(r["completed_at"]) if r["completed_at"] else utcnow()
            duration = int((ended - started).total_seconds() / 60)
            status_icon = {"completed": "ok", "failed": "FAIL", "timeout": "TIME"}.get(r["status"], r["status"])
            print(f"  #{r['id']:>3} {r['run_type']:<18} [{status_icon}]  "
                  f"{duration}m  {findings}  {leads}")
            if r["error"]:
                print(f"       error: {r['error'][:80]}")
    else:
        print("\nRECENT (24h): none")

    # Queue depths
    queues = get_queue_depths(db)
    print(f"\nQUEUES:")
    print(f"  {queues['pending_triage']:>5} pending_triage")
    print(f"  {queues['infra_open']:>5} infra open")
    print(f"  {queues['open_leads']:>5} open leads ({queues['high_critical_open']} high/critical)")
    print(f"  {queues['completions_since_last_auto']:>5} completions since last auto_leads")

    # Analysis status
    print(f"\nANALYSIS:")
    for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]:
        new_f = queues.get(f"{skill}_new_findings", "?")
        last = queues.get(f"{skill}_last_run", "never")
        if last and last != "never":
            last = last[:16]  # trim seconds
        trigger = config.get("triggers", {}).get(skill, {})
        threshold = trigger.get("new_findings_since_last", "?")
        cooldown = trigger.get("cooldown_hours", "?")
        ready = "READY" if isinstance(new_f, int) and isinstance(threshold, int) and new_f >= threshold else "wait"
        print(f"  {skill:<22} +{new_f} findings (threshold={threshold}, cooldown={cooldown}h) "
              f"last={last}  [{ready}]")

    db.close()


def cmd_launch(args):
    """Manually launch a specific agent type with a target."""
    config = load_config()
    db = get_db()
    ensure_dispatch_table(db)

    run_type = args.type
    target = args.target

    if run_type not in PROMPTS:
        print(f"  [error] Unknown type '{run_type}'. Valid: {', '.join(PROMPTS.keys())}")
        db.close()
        return

    print(f"Manual launch: {run_type} target={target or 'batch'}")
    launch_agent(db, config, run_type, target)
    db.close()


def cmd_stop(args):
    db = get_db()
    ensure_dispatch_table(db)
    running = get_running_instances(db)

    if not running:
        print("No running instances to stop.")
        db.close()
        return

    for r in running:
        if args.run_id and str(r["id"]) != str(args.run_id):
            continue
        pid = r["pid"]
        if process_alive(pid):
            print(f"  Stopping #{r['id']} {r['run_type']} PID {pid}...")
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            if process_alive(pid):
                os.kill(pid, signal.SIGKILL)
                print(f"    Force-killed PID {pid}")
        db.execute(
            "UPDATE dispatch_runs SET status='failed', completed_at=CURRENT_TIMESTAMP, "
            "error='Manually stopped' WHERE id=?",
            (r["id"],)
        )
        db.commit()
        print(f"    Marked #{r['id']} as failed")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Dispatch headless Claude Code agents")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="One-shot: check queues, launch needed agents")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would launch without launching")

    p_daemon = sub.add_parser("daemon", help="Loop: poll and launch on schedule")
    p_daemon.add_argument("--interval", type=int, help="Override poll interval (seconds)")

    p_status = sub.add_parser("status", help="Show running/recent dispatch_runs")

    p_launch = sub.add_parser("launch", help="Manually launch a specific agent")
    p_launch.add_argument("type", choices=list(PROMPTS.keys()), help="Agent type to launch")
    p_launch.add_argument("target", nargs="?", help="Target ID (lead #, infra #, or person name)")

    p_stop = sub.add_parser("stop", help="Stop running instances")
    p_stop.add_argument("run_id", nargs="?", help="Specific dispatch_run ID to stop (default: all)")

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "launch":
        cmd_launch(args)
    elif args.command == "stop":
        cmd_stop(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

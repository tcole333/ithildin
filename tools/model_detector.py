#!/usr/bin/env python3
"""Detect which analytical models apply to a given finding or text.

Uses detection markers from each model definition to suggest applicable models.
Intended for use by agent workers to auto-tag findings with model references.

Usage:
    python tools/model_detector.py detect --finding-id 1234
    python tools/model_detector.py detect --text "Epstein introduced Black to..."
    python tools/model_detector.py list
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import get_db
except ImportError:
    from lead_tracker import get_db

MODELS_DIR = Path(__file__).parent.parent / "site" / "content" / "models"

# Detection rules: keyword clusters that indicate a model may apply.
# Each rule is a list of keyword groups — matching ANY group triggers the model,
# but confidence increases with more groups matched.
DETECTION_RULES: dict[str, list[list[str]]] = {
    "manufactured-dependency": [
        ["introduc", "problem", "help"],
        ["rescue", "leverage", "compound"],
        ["advisory fee", "consulting fee", "unspecified service"],
        ["nardello", "hush", "extort"],
        ["restructur", "complicat", "tax liabilit"],
        ["created the", "engineered", "manufactured"],
    ],
    "bridge-tax": [
        ["intermediary", "introduc", "connect"],
        ["betweenness", "centrality", "structural hole"],
        ["bridge", "broker", "gatekeeper"],
        ["advisory fee", "unspecified", "information asymmetr"],
        ["multiple group", "cross-thread", "competing parties"],
    ],
    "private-order": [
        ["revolving door", "former official", "former partner"],
        ["dpa", "deferred prosecution", "non-prosecution"],
        ["board member", "advisory committee", "foundation board"],
        ["reciprocal", "invitation only", "exclusive"],
        ["institutional capture", "regulatory capture"],
        ["career path", "government to private", "private to government"],
    ],
    "narrative-shield": [
        ["journalist", "reporter", "media", "press"],
        ["pr firm", "reputation", "public image", "rehabilitation"],
        ["wolff", "thomas jr", "landon thomas"],
        ["triangulat", "information control", "narrative"],
        ["philanthropy", "science dinner", "edge foundation"],
        ["name-drop", "disinformation", "strategic gap"],
    ],
    "jurisdictional-arbitrage": [
        ["usvi", "virgin islands", "delaware", "new mexico"],
        ["multi-jurisdict", "offshore", "shell company"],
        ["trust company", "holding company", "operating entity"],
        ["opacity", "beneficial ownership", "nominee"],
        ["formation date", "dissolution", "legal event"],
        ["tax advantage", "privacy", "regulatory gap"],
    ],
    "parallel-financial-system": [
        ["intelligence", "cia", "mossad", "isi"],
        ["bcci", "iran-contra", "air america", "nugan hand"],
        ["covert", "off-the-books", "parallel"],
        ["maxwell", "barak", "carbyne"],
        ["fincen", "suspicious activity", "sar"],
        ["shared infrastructure", "shared plumbing"],
    ],
    "enabler-gradient": [
        ["compliance", "override", "flag raised"],
        ["willful blind", "knew or should have known"],
        ["relationship manager", "rm 82289", "banker"],
        ["registered agent", "nominee director", "unwitting"],
        ["professional obligation", "due diligence"],
        ["architect", "knowing participant", "captured"],
    ],
    "complexity-as-credential": [
        ["complexity", "layers", "no business purpose"],
        ["signal", "sophisticat", "exclusive", "mystique"],
        ["claim", "billionaire", "limited client"],
        ["ponzi", "madoff", "credential"],
        ["entity with no employee", "no operation"],
        ["advisory", "unspecified", "what was he paid for"],
    ],
}


def load_model_titles() -> dict[str, str]:
    """Load model ID→title mapping from index."""
    index_path = MODELS_DIR / "_index.json"
    if not index_path.exists():
        return {}
    index = json.loads(index_path.read_text())
    return {m["id"]: m["title"] for m in index}


def detect_models(text: str) -> list[dict]:
    """Detect which models apply to the given text.

    Returns list of {model_id, title, confidence, reasons} sorted by confidence desc.
    """
    text_lower = text.lower()
    titles = load_model_titles()
    results = []

    for model_id, rule_groups in DETECTION_RULES.items():
        matched_groups = []
        for group in rule_groups:
            if any(kw in text_lower for kw in group):
                matched_groups.append(group)

        if not matched_groups:
            continue

        match_ratio = len(matched_groups) / len(rule_groups)
        if match_ratio >= 0.5:
            confidence = "high"
        elif match_ratio >= 0.3:
            confidence = "medium"
        else:
            confidence = "low"

        reasons = []
        for group in matched_groups:
            matched_kw = [kw for kw in group if kw in text_lower]
            reasons.append(f"matched: {', '.join(matched_kw[:2])}")

        results.append({
            "model_id": model_id,
            "title": titles.get(model_id, model_id),
            "confidence": confidence,
            "match_ratio": round(match_ratio, 2),
            "matched_groups": len(matched_groups),
            "total_groups": len(rule_groups),
            "reasons": reasons,
        })

    results.sort(key=lambda r: r["match_ratio"], reverse=True)
    return results


def get_finding_text(finding_id: int) -> str | None:
    """Fetch finding summary + detail text from investigation.db."""
    db = get_db()
    row = db.execute(
        "SELECT summary, detail, target_name FROM findings WHERE id = ?",
        (finding_id,)
    ).fetchone()
    db.close()
    if not row:
        return None
    parts = [row["summary"] or ""]
    if row["detail"]:
        parts.append(row["detail"])
    if row["target_name"]:
        parts.append(f"Target: {row['target_name']}")
    return " ".join(parts)


def cmd_detect(args):
    if args.finding_id:
        text = get_finding_text(args.finding_id)
        if not text:
            print(f"Finding {args.finding_id} not found")
            sys.exit(1)
        print(f"Finding #{args.finding_id}: {text[:120]}...")
    elif args.text:
        text = args.text
    else:
        print("Provide --finding-id or --text")
        sys.exit(1)

    results = detect_models(text)

    if not results:
        print("No models detected")
        return

    output = []
    for r in results:
        output.append({
            "model_id": r["model_id"],
            "title": r["title"],
            "confidence": r["confidence"],
            "match_ratio": r["match_ratio"],
            "reasons": r["reasons"],
        })
        if not hasattr(args, "output") or not args.output:
            conf_label = {"high": "HIGH", "medium": "MED", "low": "LOW"}[r["confidence"]]
            print(f"  [{conf_label}] {r['title']} ({r['matched_groups']}/{r['total_groups']} groups)")
            for reason in r["reasons"][:3]:
                print(f"        {reason}")

    if hasattr(args, "output") and args.output:
        write_output(output, args)


def cmd_list(args):
    titles = load_model_titles()
    output = []
    for model_id, title in sorted(titles.items()):
        rule_count = len(DETECTION_RULES.get(model_id, []))
        entry = {"id": model_id, "title": title, "rule_groups": rule_count}
        output.append(entry)
        if not hasattr(args, "output") or not args.output:
            print(f"  {model_id:30s} {title} ({rule_count} detection groups)")

    if hasattr(args, "output") and args.output:
        write_output(output, args)


def main():
    parser = argparse.ArgumentParser(description="Analytical model detector")
    sub = parser.add_subparsers(dest="command")

    p_detect = sub.add_parser("detect", help="Detect applicable models")
    p_detect.add_argument("--finding-id", type=int)
    p_detect.add_argument("--text", type=str)
    add_output_args(p_detect)

    p_list = sub.add_parser("list", help="List all models and detection rules")
    add_output_args(p_list)

    args = parser.parse_args()
    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

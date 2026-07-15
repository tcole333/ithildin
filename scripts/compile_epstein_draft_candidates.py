#!/usr/bin/env python3
"""Compile a review-only catalog of possible Epstein-authored draft artifacts.

The compiler reads the immutable Kabasshouse corpus and writes CSV/JSONL/Markdown
review artifacts.  It does not touch investigation profiles, findings, leads, or
the derived sidecar.  Candidate status is deliberately broader than a factual
finding: a self-addressed message is a working-copy signal, not proof that the
text was never transmitted elsewhere or that allegations inside it are true.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import quopri
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "datasets/kabasshouse_epstein.db"
DEFAULT_OUTPUT = ROOT / "reports/epstein-draft-candidates"
SCAN_DATASETS = (
    "DataSet8",
    "DataSet9",
    "DataSet10",
    "DataSet11",
    "HouseOversightEstate",
)

EPSTEIN_ADDRESSES = {
    "jeevacation@gmail.com",
    "jeeproject@yahoo.com",
    "jeffreyepsteinorg@gmail.com",
    "jeffreyepeinorg@gmail.com",  # recurring source spelling
    "jeffreyeipsteinorg@gmail.com",  # recurring source spelling
    "jeffrey.epstein@centurytel.net",
    "lsje_llc@outlook.com",
    "zorroranch@aol.com",
    "epstein@wanadoo.fr",
}

HEADER_RE = re.compile(
    r"^\s*(from|sender|to|cc|bcc|sent|date|subject)\s*:\s*(.*)$", re.I
)
QUOTE_DELIMITERS = (
    re.compile(r"^\s*-{2,}\s*original message\s*-{2,}\s*$", re.I),
    re.compile(r"^\s*-{2,}\s*forwarded message\s*-{2,}\s*$", re.I),
    re.compile(r"^\s*begin forwarded message\s*:?[ ]*$", re.I),
    re.compile(r"^\s*on .{0,180} wrote\s*:?[ ]*$", re.I),
    re.compile(r"^\s*_{5,}\s*$"),
)
FOOTER_PATTERNS = (
    re.compile(r"\bplease note\b", re.I),
    re.compile(r"\bthe information contained in this communication is\b", re.I),
    re.compile(r"\bunauthorized use, disclosure or copying\b", re.I),
    re.compile(r"<\?xml\s+version=", re.I),
    re.compile(r"\bdate-last-viewed\b", re.I),
)
AUTO_SUBJECT_RE = re.compile(r"^(alert\b|photo from\b)", re.I)
ATTACHMENT_ONLY_RE = re.compile(
    r"^(?:attachments?\s*:?)?\s*(?:(?:img|dsc)[-_ ]?\d+\.(?:jpe?g|png|gif)\s*[;,]?\s*)+$",
    re.I,
)
FORMAL_SALUTATION_RE = re.compile(
    r"^(?:dear\s+[a-z][a-z .'-]{0,80}|to whom it may concern|members of the\b)",
    re.I,
)
DRAFT_RE = re.compile(
    r"\b(?:draft|drafted|drafting|rough draft|proposed (?:text|language|letter)|"
    r"wording below|language below|letter below|use this(?: language)?|send this)\b",
    re.I,
)
HANDOFF_RE = re.compile(
    r"\b(?:please send|send (?:it|this|the letter)|use (?:this|the following)|"
    r"put this (?:in|on)|under your name|for (?:his|her|your) signature|"
    r"sign and send|forward this|send from|review and send)\b",
    re.I,
)
THIRD_PARTY_VOICE_PATTERNS = (
    re.compile(r"\bi have decided to resign\b", re.I),
    re.compile(r"\bi hereby resign\b", re.I),
    re.compile(r"\bin my role as (?:his|her|the) right hand\b", re.I),
    re.compile(r"\bas i am a medical doctor\b", re.I),
    re.compile(r"\bmy (?:application|admission) to\b", re.I),
    re.compile(r"\bmy future employer\b", re.I),
    re.compile(r"\bletter of recommendation\b", re.I),
)
DOCUMENTATION_PATTERNS = (
    re.compile(r"\bi am not sending this email\b", re.I),
    re.compile(r"\bonly document(?:ing|ation)\b", re.I),
    re.compile(r"\byou should keep this email\b", re.I),
    re.compile(r"\bfor the record\b", re.I),
)
PRESSURE_PATTERNS = (
    re.compile(r"\bconfidentiality agreement\b", re.I),
    re.compile(r"\b(?:protect|maintain|damage|public perception of) (?:my |your |the )?reputation\b", re.I),
    re.compile(r"\b(?:make|go|send|release) (?:it |this |the emails? )?public\b", re.I),
    re.compile(r"\bdelete the emails?\b", re.I),
    re.compile(r"\bseverance\b", re.I),
    re.compile(r"\bsettlement\b", re.I),
    re.compile(r"\bbar complaint\b", re.I),
    re.compile(r"\bexecutive committee\b", re.I),
    re.compile(r"\bcover[ -]?up\b", re.I),
    re.compile(r"\bexpos(?:e|ing|ure)\b", re.I),
    re.compile(r"\b(?:unless|if i do not|if you do not).{0,100}\b(?:file|send|tell|publish|release|public)\b", re.I),
    re.compile(r"\bcompensation\b", re.I),
    re.compile(r"\bwrongly acquiesced\b", re.I),
    re.compile(r"\bpotentially over the line into the illegal\b", re.I),
)
PUBLIC_STATEMENT_PATTERNS = (
    re.compile(r"\bthe press\b", re.I),
    re.compile(r"\bpublic statement\b", re.I),
    re.compile(r"\bpaid a heavy price\b", re.I),
    re.compile(r"\bwholly inappropriate behavior\b", re.I),
    re.compile(r"\bnewspapers?\b", re.I),
)
ACCEPTED_DISPLAY_NAMES = {
    "",
    "j",
    "j ee",
    "jee",
    "jee jee",
    "jeff",
    "jeffrey",
    "jeffrey e",
    "jeffrey epstein",
    "jeffreyepstein",
    "jeevacation",
    "jeevacation jeevacation",
    "lsj",
    "story",
}


@dataclass
class ParsedEmail:
    headers: dict[str, str]
    body: str
    header_text: str


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def decode_text(value: str) -> str:
    """Best-effort cleanup for quoted-printable corpus text."""
    if not value:
        return ""
    try:
        decoded = quopri.decodestring(value).decode("utf-8", errors="replace")
    except (ValueError, UnicodeError):
        decoded = value
    decoded = html.unescape(decoded).replace("\r\n", "\n").replace("\r", "\n")
    return decoded.replace("\ufffd", " ")


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def plausible_header_continuation(key: str, line: str) -> bool:
    if not line or len(line) > 320:
        return False
    if key in {"sent", "date", "subject"}:
        return True
    if "@" in line or any(mark in line for mark in "<>[];"):
        return True
    words = re.findall(r"[A-Za-z][A-Za-z.'-]*", line)
    return 0 < len(words) <= 12 and not re.search(r"[.!?]\s*$", line)


def parse_email(text: str) -> ParsedEmail:
    decoded = decode_text(text)
    lines = decoded.splitlines()
    first_header = None
    for index, line in enumerate(lines[:40]):
        if HEADER_RE.match(compact(line)):
            first_header = index
            break
    if first_header is None:
        return ParsedEmail({}, clean_body(decoded), "")

    headers: dict[str, str] = {}
    header_lines: list[str] = []
    pending: str | None = None
    body_start = first_header
    matched_headers = 0
    for index in range(first_header, min(len(lines), first_header + 45)):
        line = compact(lines[index])
        match = HEADER_RE.match(line)
        if match:
            key = match.group(1).lower()
            key = "from" if key == "sender" else key
            value = match.group(2).strip()
            header_lines.append(lines[index])
            matched_headers += 1
            if key not in headers:
                headers[key] = value
            pending = key if not value else None
            body_start = index + 1
            continue
        if pending and plausible_header_continuation(pending, line):
            headers[pending] = line
            header_lines.append(lines[index])
            pending = None
            body_start = index + 1
            continue
        if not line:
            header_lines.append(lines[index])
            body_start = index + 1
            continue
        if matched_headers >= 2:
            body_start = index
            break
        if index - first_header > 12:
            body_start = index
            break

    body = clean_body("\n".join(lines[body_start:]))
    return ParsedEmail(headers, body, "\n".join(header_lines))


def clean_body(value: str) -> str:
    lines = decode_text(value).splitlines()
    kept: list[str] = []
    for line in lines:
        if kept and any(pattern.match(line) for pattern in QUOTE_DELIMITERS):
            break
        if kept and re.match(r"^\s*>+", line):
            break
        kept.append(line)
    body = "\n".join(kept)
    cut = len(body)
    for pattern in FOOTER_PATTERNS:
        match = pattern.search(body)
        if match:
            cut = min(cut, match.start())
    body = body[:cut]
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"(?:^|\n)\s*(?:EFTA(?:_R1)?[_ ]?\d+|HOUSE OVERSIGHT \d+)\s*(?=\n|$)", "\n", body, flags=re.I)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def normalize_identity(value: str) -> str:
    value = decode_text(value).lower().replace("®", "@").replace("©", "@")
    value = value.replace("[at]", "@").replace("(at)", "@")
    return compact(value)


def is_epstein_identity(value: str) -> bool:
    normalized = normalize_identity(value).replace(" ", "")
    if "jeffreyepstein" in normalized or "jeffrey.e.epstein" in normalized:
        return True
    return any(address.replace(" ", "") in normalized for address in EPSTEIN_ADDRESSES)


def sender_display_conflict(value: str) -> bool:
    normalized = normalize_identity(value)
    if not any(address in normalized.replace(" ", "") for address in EPSTEIN_ADDRESSES):
        return False
    display = re.split(r"[<\[]|\bmailto\s*:", normalized, maxsplit=1)[0]
    display = re.sub(r"[^a-z0-9 ]", " ", display)
    display = compact(display)
    return display not in ACCEPTED_DISPLAY_NAMES and not display.startswith("jeff")


def has_other_recipients(value: str) -> bool:
    if not is_epstein_identity(value):
        return bool(compact(value))
    normalized = normalize_identity(value)
    for address in EPSTEIN_ADDRESSES:
        normalized = normalized.replace(address, " ")
    normalized = re.sub(r"\b(?:jeffrey|jeff|jefrey|j|jee|e|epstein|mailto|gmail|com|yahoo)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9@]+", "", normalized)
    return len(normalized) > 3


def explicit_draft_ui(text: str) -> bool:
    lowered = text.lower()
    draft_lines = len(re.findall(r"(?m)^\s*draft\s*$", lowered))
    return draft_lines >= 2 and all(token in lowered for token in ("unread", "starred", "unstarred"))


def draft_mailbox(text: str) -> bool:
    lowered = text.lower()
    position = lowered.find("original-mailbox")
    if position < 0:
        return False
    return "/drafts" in lowered[position : position + 500]


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", value.lower())


def normalized_body(value: str) -> str:
    return " ".join(words(value))


def simhash(value: str) -> int:
    tokens = words(value)
    if not tokens:
        return 0
    shingles = [" ".join(tokens[index : index + 4]) for index in range(max(1, len(tokens) - 3))]
    vector = [0] * 64
    for shingle in shingles:
        digest = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += 1 if digest & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(vector):
        if weight >= 0:
            result |= 1 << bit
    return result


def signal_names(body: str, subject: str) -> tuple[list[str], int]:
    signals: list[str] = []
    stripped = body.lstrip()
    if FORMAL_SALUTATION_RE.match(stripped):
        signals.append("formal_salutation")
    if DRAFT_RE.search(body) or DRAFT_RE.search(subject):
        signals.append("explicit_draft_language")
    if HANDOFF_RE.search(body):
        signals.append("handoff_language")
    if any(pattern.search(body) for pattern in THIRD_PARTY_VOICE_PATTERNS):
        signals.append("third_party_voice")
    if any(pattern.search(body) for pattern in DOCUMENTATION_PATTERNS):
        signals.append("documentation_language")
    pressure_count = sum(bool(pattern.search(body)) for pattern in PRESSURE_PATTERNS)
    if pressure_count:
        signals.append("pressure_language")
    if any(pattern.search(body) for pattern in PUBLIC_STATEMENT_PATTERNS):
        signals.append("public_statement_language")
    return signals, pressure_count


def is_automatic(subject: str, body: str) -> bool:
    if AUTO_SUBJECT_RE.match(subject):
        return True
    compact_body = compact(body)
    # The attachment-only grammar is intentionally tiny.  Bounding it avoids
    # catastrophic backtracking on long OCR strings that begin with thousands
    # of attachment-looking tokens but contain prose near the end.
    if len(compact_body) <= 500 and ATTACHMENT_ONLY_RE.fullmatch(compact_body):
        return True
    if len(words(compact_body)) <= 5 and re.search(r"\b(?:img|dsc)[-_ ]?\d+\.(?:jpe?g|png|gif)\b", compact_body, re.I):
        return True
    return False


def make_candidate(row: Mapping[str, object]) -> dict | None:
    text = str(row.get("full_text") or "")
    parsed = parse_email(text)
    headers = parsed.headers
    sender = headers.get("from", "")
    recipient = headers.get("to", "")
    subject = headers.get("subject", "")
    body = parsed.body
    ui_draft = explicit_draft_ui(text)
    mailbox_draft = draft_mailbox(text)
    sender_epstein = is_epstein_identity(sender)
    recipient_epstein = is_epstein_identity(recipient)
    other_recipients = has_other_recipients(recipient)
    blank_recipient = not compact(recipient)
    conflict = sender_display_conflict(sender)

    if ui_draft and not body:
        body = clean_body(text)
    token_count = len(words(body))
    substantive = token_count >= 8 and len(compact(body)) >= 60
    signals, pressure_count = signal_names(body, subject)
    automatic = is_automatic(subject, body)
    strong = bool(
        set(signals)
        & {
            "formal_salutation",
            "explicit_draft_language",
            "handoff_language",
            "third_party_voice",
            "documentation_language",
        }
    ) or pressure_count >= 2

    evidence: list[str] = []
    if ui_draft:
        evidence.append("explicit_draft_ui")
    if mailbox_draft and sender_epstein:
        evidence.append("draft_mailbox")
    if sender_epstein and recipient_epstein:
        evidence.append("self_copy_with_others" if other_recipients else "self_addressed")
    elif sender_epstein and blank_recipient:
        evidence.append("blank_recipient")
    elif sender_epstein and ("explicit_draft_language" in signals or "handoff_language" in signals):
        evidence.append("draft_handoff")

    include = False
    if ui_draft or (mailbox_draft and sender_epstein):
        include = True
    elif sender_epstein and recipient_epstein and substantive and not automatic:
        include = True
    elif sender_epstein and blank_recipient and substantive and strong and not automatic:
        include = not subject.lower().startswith(("re:", "fwd:", "fw:")) or "explicit_draft_language" in signals
    elif sender_epstein and substantive and {"explicit_draft_language", "handoff_language"} <= set(signals):
        include = not automatic

    if conflict and not strong and not ui_draft:
        include = False
    if not include:
        return None

    score = 0
    if "explicit_draft_ui" in evidence:
        score += 100
    if "draft_mailbox" in evidence:
        score += 95
    if "self_addressed" in evidence:
        score += 55
    if "self_copy_with_others" in evidence:
        score += 45
    if "blank_recipient" in evidence:
        score += 30
    if "draft_handoff" in evidence:
        score += 35
    if len(body) >= 300:
        score += 5
    if len(body) >= 1000:
        score += 5
    if "formal_salutation" in signals:
        score += 10
    if "explicit_draft_language" in signals:
        score += 15
    if "handoff_language" in signals:
        score += 10
    if "third_party_voice" in signals:
        score += 18
    if "documentation_language" in signals:
        score += 15
    if "public_statement_language" in signals:
        score += 8
    score += min(20, pressure_count * 4)
    if subject.lower().startswith(("re:", "fwd:", "fw:")):
        score -= 10
    if conflict:
        score -= 30

    norm = normalized_body(body)
    body_hash = hashlib.sha256(norm.encode()).hexdigest()
    priority = "high" if score >= 85 else "medium" if score >= 65 else "broad"
    return {
        "file_key": row.get("file_key") or row.get("id"),
        "document_id": row.get("id"),
        "dataset": row.get("dataset"),
        "document_type": row.get("document_type"),
        "date": row.get("date"),
        "from_field": sender,
        "to_field": recipient,
        "cc_field": headers.get("cc", ""),
        "subject": subject,
        "evidence_types": evidence,
        "signals": signals,
        "pressure_signal_count": pressure_count,
        "sender_identity_conflict": conflict,
        "score": score,
        "priority": priority,
        "word_count": token_count,
        "body_char_count": len(body),
        "body_hash": body_hash,
        "simhash": f"{simhash(norm):016x}",
        "preview": compact(body)[:500],
        "body_text": body,
        "header_text": parsed.header_text,
        "status_note": (
            "Review candidate only. Draft status and transmission status are not yet adjudicated; "
            "claims inside the text are not verified by inclusion here."
        ),
    }


def jaccard(left: str, right: str) -> float:
    a, b = set(words(left)), set(words(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def min_shingle_hashes(value: str, count: int = 8) -> list[int]:
    """Return stable content anchors for finding close revisions.

    Simhash bands are fast but can miss two near-identical documents when a few
    changed bits happen to be spread across every band.  Several minimum
    trigram hashes provide a second, deterministic candidate-generation path;
    the actual merge still requires a high whole-document Jaccard score.
    """
    tokens = words(value)
    if len(tokens) < 3:
        return []
    shingles = {" ".join(tokens[index : index + 3]) for index in range(len(tokens) - 2)}
    hashes = {
        int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for shingle in shingles
    }
    return sorted(hashes)[:count]


def assign_families(candidates: list[dict]) -> None:
    uf = UnionFind(len(candidates))
    exact: dict[str, int] = {}
    simhash_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    content_buckets: dict[int, list[int]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        body_hash = candidate["body_hash"]
        if body_hash in exact:
            uf.union(index, exact[body_hash])
        else:
            exact[body_hash] = index
        signature = int(candidate["simhash"], 16)
        if candidate["word_count"] >= 20:
            for band in range(4):
                simhash_buckets[(band, (signature >> (band * 16)) & 0xFFFF)].append(index)
            for anchor in min_shingle_hashes(candidate["body_text"]):
                content_buckets[anchor].append(index)

    compared: set[tuple[int, int]] = set()
    for members in simhash_buckets.values():
        if len(members) > 100:
            continue
        for pos, left in enumerate(members):
            for right in members[pos + 1 :]:
                pair = (min(left, right), max(left, right))
                if pair in compared:
                    continue
                compared.add(pair)
                left_sig = int(candidates[left]["simhash"], 16)
                right_sig = int(candidates[right]["simhash"], 16)
                if (left_sig ^ right_sig).bit_count() > 9:
                    continue
                if jaccard(candidates[left]["body_text"], candidates[right]["body_text"]) >= 0.62:
                    uf.union(left, right)

    for members in content_buckets.values():
        if len(members) > 100:
            continue
        for pos, left in enumerate(members):
            for right in members[pos + 1 :]:
                pair = (min(left, right), max(left, right))
                if pair in compared:
                    continue
                compared.add(pair)
                left_words = candidates[left]["word_count"]
                right_words = candidates[right]["word_count"]
                if min(left_words, right_words) / max(left_words, right_words) < 0.55:
                    continue
                if jaccard(candidates[left]["body_text"], candidates[right]["body_text"]) >= 0.62:
                    uf.union(left, right)

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(candidates)):
        groups[uf.find(index)].append(index)
    for members in groups.values():
        family_seed = min(candidates[index]["body_hash"] for index in members)
        family_id = f"draftfam-{family_seed[:12]}"
        refs = sorted(str(candidates[index]["file_key"]) for index in members)
        for index in members:
            candidates[index]["family_id"] = family_id
            candidates[index]["family_size"] = len(members)
            candidates[index]["family_member_refs"] = refs


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, candidates: list[dict]) -> None:
    fields = [
        "rank",
        "priority",
        "score",
        "file_key",
        "dataset",
        "date",
        "document_type",
        "evidence_types",
        "signals",
        "pressure_signal_count",
        "sender_identity_conflict",
        "family_id",
        "family_size",
        "from_field",
        "to_field",
        "cc_field",
        "subject",
        "word_count",
        "body_char_count",
        "preview",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            row = {field: candidate.get(field, "") for field in fields}
            row["evidence_types"] = ";".join(candidate["evidence_types"])
            row["signals"] = ";".join(candidate["signals"])
            writer.writerow(row)


def write_families(path: Path, candidates: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["family_id"]].append(candidate)
    rows = []
    for family_id, members in groups.items():
        representative = max(members, key=lambda item: (item["score"], item["word_count"]))
        rows.append(
            {
                "family_id": family_id,
                "member_count": len(members),
                "max_score": max(item["score"] for item in members),
                "priority": representative["priority"],
                "representative_ref": representative["file_key"],
                "dates": ";".join(sorted({str(item["date"] or "") for item in members})),
                "member_refs": ";".join(sorted(str(item["file_key"]) for item in members)),
                "evidence_types": ";".join(sorted({value for item in members for value in item["evidence_types"]})),
                "signals": ";".join(sorted({value for item in members for value in item["signals"]})),
                "preview": representative["preview"],
            }
        )
    rows.sort(key=lambda row: (-row["max_score"], -row["member_count"], row["family_id"]))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["family_id"])
        writer.writeheader()
        writer.writerows(rows)


def write_review(path: Path, candidates: list[dict], manifest: dict, limit: int) -> None:
    lines = [
        "# Epstein draft-artifact candidate review queue",
        "",
        f"Generated from `{manifest['source_db']}` without changing the active investigation profile.",
        "",
        "These are review candidates, not findings. Self-addressing is evidence of a working copy, not proof that a text was never transmitted. Allegations inside a draft remain unverified unless independently supported.",
        "",
        "## Counts",
        "",
        f"- Documents scanned: {manifest['documents_scanned']:,}",
        f"- Candidate rows: {manifest['candidate_count']:,}",
        f"- Candidate families: {manifest['family_count']:,}",
        f"- High priority: {manifest['priority_counts'].get('high', 0):,}",
        f"- Medium priority: {manifest['priority_counts'].get('medium', 0):,}",
        f"- Broad pool: {manifest['priority_counts'].get('broad', 0):,}",
        "",
        "## Suggested review order",
        "",
        "1. Review one representative from every high-priority family, then compare all members of that family as revisions.",
        "2. Review the medium-priority family representatives; these combine a working-copy indicator with draft, handoff, voice, documentation, or pressure-language signals.",
        "3. Search or sort the broad CSV by person, subject, date, and signal when pursuing a specific thread. The broad pool emphasizes recall and will contain ordinary self-copies.",
        "",
        "## Selection method",
        "",
        "- `explicit_draft_ui`: OCR resembles a visible mailbox Drafts listing. This is the strongest draft-state indicator, but it may expose several snippets rather than one complete artifact.",
        "- `draft_mailbox`: source metadata visibly places the item in a Drafts mailbox.",
        "- `self_addressed` / `self_copy_with_others`: Epstein appears in both sender and recipient fields. This suggests a working copy but does not establish that the text was unsent.",
        "- `blank_recipient`: no top-level recipient was parsed; inclusion also requires a stronger draft, handoff, formal-voice, documentation, or pressure signal.",
        "- `draft_handoff`: Epstein appears to send proposed text for another person to review, sign, or transmit. Both draft and handoff language are required for header-poor/non-self-addressed items.",
        "- Content signals are screening aids, not adjudications. `third_party_voice` looks for first-person language apparently written for another speaker; `pressure_language` only marks terms worth reviewing in context.",
        "- Families join exact normalized copies and high-overlap near-duplicates. Family membership indicates likely OCR duplication or revision—not independent corroboration.",
        "",
        "## Review fields",
        "",
        "For each candidate, reviewers should decide: draft-state evidence, apparent composer, intended speaker, intended recipient, purpose, transmission status, duplicate/revision status, and whether any pressure-language classification is warranted.",
        "",
        f"## Ranked candidates (top {min(limit, len(candidates)):,})",
        "",
    ]
    for candidate in candidates[:limit]:
        title = candidate["subject"] or "(no subject)"
        lines.extend(
            [
                f"### {candidate['rank']}. {candidate['file_key']} — {title}",
                "",
                f"- Priority/score: `{candidate['priority']}` / `{candidate['score']}`",
                f"- Date/dataset: `{candidate['date'] or 'unknown'}` / `{candidate['dataset']}`",
                f"- Evidence: `{', '.join(candidate['evidence_types'])}`",
                f"- Signals: `{', '.join(candidate['signals']) or 'none'}`",
                f"- Family: `{candidate['family_id']}` ({candidate['family_size']} member(s))",
                f"- Header: `{compact(candidate['from_field'])}` → `{compact(candidate['to_field']) or '[blank]'}`",
                "",
                f"> {candidate['preview'].replace(chr(10), ' ')}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n")


def compile_candidates(db_path: Path) -> tuple[list[dict], dict]:
    if not db_path.is_file():
        raise FileNotFoundError(f"Kabasshouse database not found: {db_path}")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in SCAN_DATASETS)
    query = f"""
        SELECT id, file_key, dataset, document_type, date, char_count, full_text
        FROM documents
        WHERE dataset IN ({placeholders})
          AND (
            document_type IS NULL
            OR lower(document_type) LIKE '%email%'
            OR lower(document_type) IN ('draft', 'letter')
          )
    """
    scanned = 0
    scanned_by_dataset: Counter[str] = Counter()
    candidates: list[dict] = []
    for row in db.execute(query, SCAN_DATASETS):
        scanned += 1
        scanned_by_dataset[str(row["dataset"])] += 1
        candidate = make_candidate(dict(row))
        if candidate:
            candidates.append(candidate)
    db.close()

    assign_families(candidates)
    candidates.sort(
        key=lambda item: (
            -item["score"],
            -item["family_size"],
            str(item["date"] or ""),
            str(item["file_key"]),
        )
    )
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": display_path(db_path),
        "scan_datasets": list(SCAN_DATASETS),
        "documents_scanned": scanned,
        "documents_scanned_by_dataset": dict(sorted(scanned_by_dataset.items())),
        "candidate_count": len(candidates),
        "family_count": len({item["family_id"] for item in candidates}),
        "priority_counts": dict(Counter(item["priority"] for item in candidates)),
        "evidence_type_counts": dict(Counter(value for item in candidates for value in item["evidence_types"])),
        "signal_counts": dict(Counter(value for item in candidates for value in item["signals"])),
        "known_example_presence": {
            key: any(item["file_key"] == key for item in candidates)
            for key in (
                "EFTA00743144",
                "EFTA00965059",
                "EFTA00965766",
                "EFTA00965773",
                "EFTA00965784",
                "EFTA01731558",
                "EFTA01732698",
                "EFTA01732911",
                "EFTA01928275",
                "EFTA01967528",
            )
        },
        "scope_note": (
            "Review-only extraction. No profile, lead, finding, connection, or derived-sidecar state was changed. "
            "Same-page re-OCRs and near-duplicate revisions are clustered as candidate families, not treated as corroboration."
        ),
    }
    return candidates, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-limit", type=int, default=250)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates, manifest = compile_candidates(args.db.resolve())

    jsonl_path = output_dir / "candidates.jsonl"
    csv_path = output_dir / "candidates.csv"
    family_path = output_dir / "families.csv"
    review_path = output_dir / "review.md"
    manifest_path = output_dir / "manifest.json"
    write_jsonl(jsonl_path, candidates)
    write_csv(csv_path, candidates)
    write_families(family_path, candidates)
    manifest["outputs"] = {
        "jsonl": display_path(jsonl_path),
        "csv": display_path(csv_path),
        "families_csv": display_path(family_path),
        "review_markdown": display_path(review_path),
        "manifest": display_path(manifest_path),
    }
    write_review(review_path, candidates, manifest, args.markdown_limit)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

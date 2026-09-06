#!/usr/bin/env python3
"""
Findings and connections tracker for OSINT investigations.

Part of investigation.db (shared with lead_tracker.py).

Usage:
    uv run python tools/findings_tracker.py add --target "TARGET" --summary "..." --sources courtlistener --evidence COURTLISTENER:ID --source-quote "COURTLISTENER:ID:Exact source excerpt" --claim-type paraphrase
    python tools/findings_tracker.py list [--target "Rod-Larsen"] [--type financial]
    python tools/findings_tracker.py show 42
    python tools/findings_tracker.py evidence-add 42 --ref SOURCE:ID --source-quote "..." --reason "..."
    python tools/findings_tracker.py evidence-correct 42 --ref SOURCE:ID --field source_quote --value "..." --reason "..."
    python tools/findings_tracker.py evidence-delete 42 --ref SOURCE:ID --reason "..."
    python tools/findings_tracker.py evidence-audit [--finding-id 42] [--output /tmp/evidence-audit.json]
    python tools/findings_tracker.py connect --person-a "Epstein" --person-b "Rod-Larsen" --type financial
    python tools/findings_tracker.py connection-evidence-add 7 --ref SOURCE:ID --source-quote "..." --reason "..."
    python tools/findings_tracker.py connection-verify 7 --by analyst
    python tools/findings_tracker.py connection-provenance 7 [--output /tmp/connection-7.json]
    python tools/findings_tracker.py connections "Epstein" [--depth 2]
    python tools/findings_tracker.py search "gates foundation"
    python tools/findings_tracker.py timeline [--target "Rod-Larsen"] [--start 2016-01-01] [--end 2019-12-31]
    python tools/findings_tracker.py stats
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

# Shared database with lead_tracker.py
DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH", Path(__file__).parent.parent / "investigation.db"))


def _detect_active_profile():
    """Detect active profile with fallback to direct DB read."""
    try:
        from tools.investigation_context import get_active_profile_id

        pid = get_active_profile_id()
        if pid:
            return pid
    except Exception:
        pass
    # Fallback: read directly from DB (works even if import fails in subagents)
    try:
        _db = sqlite3.connect(str(DB_PATH))
        row = _db.execute(
            "SELECT value FROM investigation_config WHERE key='active_profile'"
        ).fetchone()
        _db.close()
        if row:
            return row[0] or None
    except Exception:
        pass
    return None


def _profile_thread_id_map(profile_id, db=None):
    """Map configured thread numbers using the caller's DB when supplied."""
    if db is not None:
        try:
            from tools.investigation_context import load_profile
        except ImportError:
            from investigation_context import load_profile
        try:
            profile = load_profile(profile_id)
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            return {}
        by_title = {
            row["title"]: row["id"]
            for row in db.execute(
                "SELECT id, title FROM investigation_threads WHERE profile_id=?",
                (profile_id,),
            )
        }
        return {
            int(thread["id"]): by_title[thread["name"]]
            for thread in profile.threads
            if thread.get("id") is not None and thread.get("name") in by_title
        }
    try:
        from tools.profile_threads import profile_thread_id_map
    except ImportError:
        from profile_threads import profile_thread_id_map
    return profile_thread_id_map(profile_id)


VALID_FINDING_TYPES = [
    "communication",
    "financial",
    "relationship",
    "identity",
    "location",
    "document",
    "legal",
    "intelligence",
    "negative_result",
    "background",
]
VALID_CONFIDENCE = ["confirmed", "high", "medium", "low", "unverified"]
VALID_RELATIONSHIP_TYPES = [
    "financial",
    "social",
    "legal",
    "intelligence",
    "employment",
    "familial",
    "corporate",
    "advisory",
    "political",
    # Entity-to-entity relationship types
    "owns",
    "controls",
    "funds",
    "subsidiary_of",
    "contracts_with",
    "successor_to",
    "shares_officer",
    "supplies",
]
DIRECTIONAL_RELATIONSHIP_TYPES = {
    "controls",
    "funds",
    "owns",
    "subsidiary_of",
    "successor_to",
    "supplies",
}
VALID_STRENGTHS = ["strong", "medium", "weak", "circumstantial"]
try:
    from tools.entity_tracker import VALID_ENTITY_TYPES
except ImportError:
    try:
        from entity_tracker import VALID_ENTITY_TYPES
    except ImportError:
        VALID_ENTITY_TYPES = [
            "person",
            "llc",
            "inc",
            "ltd",
            "corporation",
            "pllc",
            "trust",
            "foundation",
            "nonprofit",
            "partnership",
            "fund",
            "association",
            "government",
            "pac",
            "agency",
            "joint_venture",
            "shell",
            "unknown",
        ]


_schema_initialized = False


def get_db():
    """Get database connection. Schema is created by lead_tracker._ensure_schema()."""
    global _schema_initialized
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")

    if not _schema_initialized:
        from tools.lead_tracker import _ensure_schema

        _ensure_schema(db)
        _schema_initialized = True

    return db


def _get_db_standalone():
    """Standalone DB init (when run directly, not as import)."""
    global _schema_initialized
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")

    if not _schema_initialized:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "lead_tracker", Path(__file__).parent / "lead_tracker.py"
        )
        lt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lt)
        lt._ensure_schema(db)
        _schema_initialized = True

    return db


# ── Findings CRUD ────────────────────────────────────────────


VALID_SOURCES = [
    "web_search",
    "doj",
    "justice_gov",
    "nj_oag",
    "doj_vol11",
    "duggan",
    "lmsband",
    "unified_db",
    # Kabasshouse consolidated Epstein corpus (PRIMARY full-text) + FBI release.
    # Same EFTA page in kabass + doj_vol11/lmsband = one source re-OCR'd, not corroboration.
    "kabass",
    "fbi",
    "efta",
    "fec",
    "edgar",
    "sec",
    "sec_iapd",
    "courtlistener",
    "supreme_court",
    "mn_court_appeals",
    "fjc",
    "finra",
    "openpayments",
    "asic_financial_advisers",
    "ny_ag",
    "sipc",
    "dmhc",
    "caltech",
    "nlrb",
    "senate_finance",
    "990",
    "registry",
    "fdacs",
    # State political-finance, company disclosure, and legislative primary sources.
    "florida_campaign_finance",
    "florida_senate",
    "georgia_campaign_finance",
    "geo_group_2024_political_activity_report",
    "geo_group_2025_political_activity_report",
    "usaspending",
    "sam_gov",
    "lobbying",
    "fara",
    "littlesis",
    # FPDS-NG ATOM feed (fpds.gov). Sole source for contract-action workflow
    # fields (createdBy/lastModifiedBy/approvedBy) — USASpending omits them and
    # HigherGov returns them null, so those tokens must not stand in for it.
    "fpds",
    "gdelt",
    "aleph",
    "icij",
    "acris",
    "la_county_assessor",
    "gleif",
    "opensanctions",
    "shodan",
    "crtsh",
    "wayback",
    "urlscan",
    "medicaid",
    "analysis_run",
    "offshorealert",
    "uk_companies_house",
    "ca_sos",
    "co_sos",
    "tx_comptroller",
    "mi_lara",
    "nj_rev",
    "ma_corps",
    "wy_sos",
    "ny_dos",
    "nv_sos",
    "fl_sunbiz",
    "nm_sos",
    "dc_dlcp",
    "wa_registry",
    "usvi",
    "ds10_financial",
    "ucc",
    "florida_ucc",
    "massachusetts_ucc",
    "faa",
    "sam_bulk",
    "highergov",
    "documentcloud",
    "muckrock",
    "fincen",
    "opencorporates",
    "zefix",
    "hudoc",
    "france_sirene",
    "panama_rp",
    "patents",
    "investigations_db",
    "fdic",
    # USPTO trademark register (tmsearch.uspto.gov). A separate registry from
    # `patents` (PatentsView/ODP) — it carries mark ownership and assignment
    # history, so the two tokens are not interchangeable.
    "trademarks",
    "propublica_disclosures",
    "propublica_congress",
    "irs_teos",
    "ppp",
    "govinfo",
    "congress_gov",
    "sec_enforcement",
    "bisbase",
    "ecfr",
    "nyscef",
    "federal_register",
    "military_corrections",
    "military_justice",
    "md_public_cases",
    "md_estate_search",
    "md_judgment_liens",
    "md_opinions",
    "md_business_opinions",
    "new_jersey_tax_court",
    "new_jersey_tax_court_opinions",
    "virginia_parcels",
    "census_acs",
    "sunat",
    "sunarp",
    "infogob",
    "oefa",
    # House Oversight Committee congressional transcribed-interview transcripts
    "house-oversight-transcripts-2026",
    "house_oversight",
    # Peru-specific primary sources
    "elperuano",
    "mindef",
    "seace",
    "contraloria",
    # Israel primary sources: TASE MAYA disclosure system, Corporations
    # Authority registry (data.gov.il), and Israeli business media.
    "tase_maya",
    "israel_registry",
    "calcalist",
    "globes_il",
    # US foreign-military-sales / lobbying primary sources
    "dsca",
    "lda",
    "fara_local",
    # Internal investigation cross-references
    "investigations",
    # Attributed reporting claims promoted only after primary-evidence review.
    "reporting",
    "government_releases",
    # White House election-integrity document release (2026-07-16):
    # declassified IC/FBI/DHS records + 2026-authored summaries, archived with
    # hashes under datasets/wh_election_integrity/. Primary government records,
    # but selectively released/redacted — corroborate externally where possible.
    "wh_election_integrity",
    # Primary federal/state/local oversight, legal, privacy, and detention records.
    "gao",
    "dhs",
    "dhs_oig",
    "dhs_pia",
    "oversight_gov",
    "ssa_oig",
    "us_code",
    "usms",
    "massachusetts_governor",
    "val_verde_county",
    "ice_odo",
    "ice_ddr",
    "ice_foia",
    "ice_detention_statistics",
    "louisiana_legislative_auditor",
    "montgomery_county_tx",
    # Court and adjudicative records not covered by the structured court tools.
    "cadc",
    "indiana_mycase",
    "justia",
    "icc_arbitration",
    "dominica_cbiu",
    "uk_judiciary",
    "ca_superior_court",
    # First-party pages without a recurring source-specific registry key. The
    # exact organization and page must remain in the evidence URL.
    "official_website",
    "internet_archive",
    # ── Selector-pivot leak/breach aggregators (provenance-opaque;
    #    findings sourced here cap at `medium` until corroborated) ──
    "leak_aggregator",
    "dehashed",
    "intelx",
    # ── Round 6 additions ──────────────────────────────────────
    # General news / wires
    "cnn",
    "bloomberg",
    "aljazeera",
    "gulfbusiness",
    "agbi",
    "ledgerinsights",
    "laraontheblock",
    "gulfnews",
    "thenationalnews",
    "reuters",
    "ft",
    "wsj",
    "nyt",
    "letemps",
    # US government / regulator (additional)
    "sec_edgar",
    "occ",
    "treasury",
    "oge",
    "ogeforms",
    "sec_oig",
    "ftc",
    # Gulf-state primary
    "mubadala",
    "dpworld",
    "adgm",
    "dfzc",
    "dfsa",
    "dfm",
    "adx",
    "adq",
    "masdar",
    "adnoc",
    "l_imad",
    "mediaoffice",
    # US corporate primary
    "apollo",
    "nasdaq",
    "oracle",
    "openai",
    "softbank",
    "oklo",
    "palantir",
    "kkr",
    "blackstone",
    "blackrock",
    "ares",
    "carlyle",
    "gs",
    "citi",
    "jpmorgan",
    "ms",
    "chubb",
    "omv",
    "borouge",
    "anthropic",
    "xai",
    "crusoe",
    "lancium",
    "paul_weiss",
    "exor",
    # Crypto / blockchain
    "theblock",
    "dune",
    "etherscan",
    "solscan",
    "bitfury",
    "anchorage",
    "circle",
    "coinbase",
    "binance",
    "blockchain_com",
    # Italian / EU media + Vatican
    "ilfattoquotidiano",
    "ansa",
    "repubblica",
    "corriere",
    "ilmessaggero",
    "domani",
    "irpimedia",
    "inkiesta",
    "vaticannews",
    "press_vatican",
    # Lux / Swiss registries
    "lux_rcs",
    "swiss_zefix",
    "lbr_lu",
    # UK registries / regulators / courts
    "companies_house",
    "fca",
    "london_gazette",
    "charity_commission",
    "bailii",
    "ewhc",
]

# Curated compatibility names used by configured corpus tools and older findings.
# These are explicit aliases rather than fuzzy normalization: an unregistered token
# must still fail validation so provenance labels cannot silently drift.
SOURCE_ALIASES = {
    "kabasshouse": "kabass",
    "kabasshouse epstein corpus": "kabass",
    "unified": "unified_db",
    "unified_epstein": "unified_db",
    "nydos": "ny_dos",
    "sec edgar": "edgar",
    "ds10": "ds10_financial",
    "doj_epstein_files": "doj",
    "house_20k": "house_oversight",
    "epstein_20k": "house_oversight",
    "fbi-files": "fbi",
    "fbi_files": "fbi",
    "fbi_epstein": "fbi",
    "fbi_epstein_files": "fbi",
    "epstein_reporting": "reporting",
    "query_investigations": "investigations_db",
    "scotus": "supreme_court",
    "scotus_filing": "supreme_court",
    "courtlistener_recap": "courtlistener",
    "senate_lda": "lda",
    "oge_form_278e": "oge",
    "ice.gov": "dhs",
    "justice.gov": "justice_gov",
    "ecfr.gov": "ecfr",
    "oge.gov": "oge",
    "gao.gov": "gao",
    "uscode.house.gov": "us_code",
    "supremecourt.gov": "supreme_court",
    "montgomery_county": "montgomery_county_tx",
    "irs_990_xml": "990",
    "irs_index": "990",
    "irs990": "990",
    "doj_epstein": "doj",
    "congress": "congress_gov",
    "sam": "sam_gov",
    "sam_local": "sam_bulk",
    "sam_public_extract": "sam_bulk",
    "florida_sunbiz": "fl_sunbiz",
    "colorado_sos": "co_sos",
    "england_wales_high_court": "ewhc",
    "california-superior-court": "ca_superior_court",
    "california_superior_court": "ca_superior_court",
    "judiciary.uk": "uk_judiciary",
    "paulweiss": "paul_weiss",
    "paulweiss_official": "paul_weiss",
    "paul_weiss_press_release": "paul_weiss",
    "exor.com": "exor",
    "harvard_clp": "official_website",
    "5rb.com": "official_website",
    "web_official": "official_website",
}
SOURCE_VOCABULARY_GUIDANCE = (
    "For a one-off first-party organization page, use 'official_website' and "
    "preserve the exact URL in --evidence. Do not use a search engine, browser, "
    "or direct-URL retrieval method as the source. Run "
    "'findings_tracker.py sources' to list canonical tokens and aliases."
)
VALID_CLAIM_TYPES = [
    "direct_quote",
    "paraphrase",
    "inference",
    "synthesis",
    "user_provided",
]
VALID_VERIFICATION = ["unverified", "verified", "disputed", "retracted"]

# Confidence caps by claim type — enforced at write time
CONFIDENCE_CAPS = {
    "direct_quote": "confirmed",  # verbatim from primary source
    "paraphrase": "high",  # agent summary of source
    "inference": "medium",  # agent conclusion from evidence
    "synthesis": "medium",  # combined multiple sources
    "user_provided": "confirmed",  # human-supplied
}
_CONFIDENCE_ORDER = ["unverified", "low", "medium", "high", "confirmed"]
PROVENANCE_OPAQUE_SOURCES = {"leak_aggregator", "dehashed", "intelx"}
PROVENANCE_OPAQUE_CONFIDENCE_CAP = "medium"
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_EVIDENCE_SUFFIXES = {
    ".csv",
    ".doc",
    ".docx",
    ".html",
    ".htm",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".txt",
    ".xml",
    ".xlsx",
}
TEXT_EVIDENCE_SUFFIXES = {".csv", ".html", ".htm", ".json", ".md", ".txt", ".xml"}
EVIDENCE_CORRECT_FIELDS = {
    "evidence_ref",
    "source_quote",
    "source_page",
    "assessment",
    "email_sender",
    "email_date",
    "chain_position",
}
EFTA_ONLY_EVIDENCE_FIELDS = {"email_sender", "email_date", "chain_position"}
CONNECTION_EVIDENCE_CORRECT_FIELDS = {
    "evidence_ref",
    "source_quote",
    "source_page",
    "assessment",
}
ALLOWED_CONNECTION_CORRECT_FIELDS = {
    "relationship_type",
    "description",
    "strength",
    "date_range",
    "finding_id",
    "profile_id",
    "valid_from",
    "valid_until",
}


def _enforce_confidence_cap(claim_type, confidence):
    """Clamp confidence to the maximum allowed for this claim type.

    Returns (clamped_confidence, was_clamped).
    """
    cap = CONFIDENCE_CAPS.get(claim_type)
    if not cap:
        return confidence, False
    cap_idx = _CONFIDENCE_ORDER.index(cap)
    conf_idx = (
        _CONFIDENCE_ORDER.index(confidence) if confidence in _CONFIDENCE_ORDER else 2
    )
    if conf_idx > cap_idx:
        return cap, True
    return confidence, False


def _enforce_source_confidence_cap(source_datasets, confidence):
    """Clamp confidence for findings sourced from provenance-opaque aggregators.

    Returns (clamped_confidence, was_clamped).
    """
    if not PROVENANCE_OPAQUE_SOURCES.intersection(source_datasets or []):
        return confidence, False
    cap_idx = _CONFIDENCE_ORDER.index(PROVENANCE_OPAQUE_CONFIDENCE_CAP)
    conf_idx = (
        _CONFIDENCE_ORDER.index(confidence) if confidence in _CONFIDENCE_ORDER else 2
    )
    if conf_idx > cap_idx:
        return PROVENANCE_OPAQUE_CONFIDENCE_CAP, True
    return confidence, False


def _classify_evidence_ref(evidence_ref):
    """Classify evidence without treating canonical refs or URL paths as files."""
    evidence_ref = str(evidence_ref or "").strip()
    if re.fullmatch(r"EFTA\d+", evidence_ref, flags=re.IGNORECASE):
        return "efta"
    parsed = urlparse(evidence_ref)
    if parsed.scheme.lower() in {"http", "https"}:
        return "url"
    if parsed.scheme.lower() == "file":
        return "file"
    # Canonical source references frequently contain slash-delimited subkeys
    # (for example CourtListener:docket/69737684). They are reproducible IDs,
    # not local paths, and must remain valid without a filesystem probe.
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*:[^\s]+", evidence_ref):
        return "ref"
    path = Path(evidence_ref).expanduser()
    if (
        path.is_absolute()
        or evidence_ref.startswith(("./", "../", "~/"))
        or "/" in evidence_ref
        or "\\" in evidence_ref
        or path.suffix.lower() in LOCAL_EVIDENCE_SUFFIXES
    ):
        return "file"
    return "ref"


def _local_evidence_path(evidence_ref):
    """Resolve a local evidence ref relative to the repository, not process cwd."""
    value = str(evidence_ref or "").strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() == "file":
        value = unquote(parsed.path)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve(strict=False)


def _validate_source_datasets(source_datasets):
    """Return a canonical source-token list or raise for unsupported shapes/tokens."""
    if isinstance(source_datasets, str) or not isinstance(
        source_datasets, (list, tuple)
    ):
        raise ValueError(
            "source_datasets must be a JSON-array-compatible list of supported source tokens"
        )
    if not source_datasets:
        raise ValueError(
            "source_datasets must contain at least one supported source token"
        )

    normalized = []
    for token in source_datasets:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("source_datasets entries must be non-empty strings")
        raw_token = token.strip()
        token = SOURCE_ALIASES.get(raw_token.casefold(), raw_token.casefold())
        if token not in VALID_SOURCES:
            token_guidance = SOURCE_VOCABULARY_GUIDANCE
            if token.startswith("fec_mur_"):
                token_guidance = (
                    "Use 'fec' for FEC matters and preserve the MUR number and "
                    f"document URL in --evidence. {SOURCE_VOCABULARY_GUIDANCE}"
                )
            raise ValueError(f"Unsupported source token '{token}'. {token_guidance}")
        if token not in normalized:
            normalized.append(token)
    return normalized


def _parse_stored_source_datasets(raw_value):
    """Parse the JSON stored in findings.source_datasets and validate its tokens."""
    try:
        parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"source_datasets is not valid JSON: {exc}") from exc
    return _validate_source_datasets(parsed)


def _resolve_finding_thread_id(db, thread_id, profile_id):
    """Resolve or validate a finding's profile-scoped thread ID."""
    try:
        from tools.profile_threads import resolve_profile_thread_id
    except ImportError:
        from profile_threads import resolve_profile_thread_id
    return resolve_profile_thread_id(
        db,
        thread_id,
        profile_id,
        local_thread_ids=lambda: _profile_thread_id_map(profile_id, db=db),
    )


def _validate_evidence_ref(evidence_ref, stored_type=None):
    """Validate a new/published evidence reference and return its canonical type."""
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise ValueError("evidence_ref must be a non-empty string")
    evidence_ref = evidence_ref.strip()
    expected_type = _classify_evidence_ref(evidence_ref)
    if stored_type is not None and stored_type != expected_type:
        raise ValueError(
            f"Evidence ref '{evidence_ref}' is stored as '{stored_type}' but must be "
            f"'{expected_type}'"
        )
    if expected_type == "file":
        path = _local_evidence_path(evidence_ref)
        if not path.is_file():
            raise ValueError(
                f"Local evidence file does not exist or is not a file: {evidence_ref} "
                f"(resolved to {path})"
            )
    return expected_type


def _normalize_quote_text(value):
    """Normalize layout/OCR whitespace while preserving the quoted words."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _load_evidence_text(evidence_ref, evidence_type):
    """Resolve locally available source text for non-network span validation.

    Returns ``(text, status_detail)``. A ``None`` text means the source has no
    local resolver; it is not a mismatch and therefore does not block a write.
    """
    if evidence_type == "efta":
        try:
            try:
                from tools.parse_email_chain import get_ocr_text
            except ImportError:
                from parse_email_chain import get_ocr_text
            text = get_ocr_text(evidence_ref.upper())
        except Exception as exc:
            return None, f"EFTA corpus unavailable: {exc}"
        return (
            (text, "EFTA OCR") if text else (None, "EFTA document unavailable locally")
        )

    if evidence_type == "file":
        path = _local_evidence_path(evidence_ref)
        if path.suffix.lower() not in TEXT_EVIDENCE_SUFFIXES:
            return (
                None,
                f"span extraction unsupported for {path.suffix or 'this file type'}",
            )
        try:
            return path.read_text(encoding="utf-8", errors="replace"), str(path)
        except OSError as exc:
            return None, f"local text unavailable: {exc}"

    return None, f"no local span resolver for evidence_type={evidence_type}"


def _check_source_quote_span(evidence_ref, source_quote, evidence_type=None):
    """Return matched/mismatch/unchecked for an exact quote against local text."""
    if not str(source_quote or "").strip():
        return "missing", "source_quote is empty"
    evidence_type = evidence_type or _classify_evidence_ref(evidence_ref)
    text, detail = _load_evidence_text(evidence_ref, evidence_type)
    if text is None:
        return "unchecked", detail
    if _normalize_quote_text(source_quote) in _normalize_quote_text(text):
        return "matched", detail
    return "mismatch", f"source_quote was not found in {detail}"


def _validate_evidence_payload(
    evidence_ref,
    source_quote=None,
    *,
    claim_type=None,
    stored_type=None,
    require_quote=False,
):
    """Validate reference/type/existence and any locally resolvable quote span."""
    evidence_type = _validate_evidence_ref(evidence_ref, stored_type=stored_type)
    needs_quote = require_quote or claim_type == "direct_quote"
    if needs_quote and not str(source_quote or "").strip():
        raise ValueError(
            f"{claim_type or 'Published'} evidence '{evidence_ref}' requires a non-empty source_quote"
        )
    if str(source_quote or "").strip():
        span_status, detail = _check_source_quote_span(
            evidence_ref, source_quote, evidence_type=evidence_type
        )
        if span_status == "mismatch":
            raise ValueError(
                f"Evidence '{evidence_ref}' failed exact quote validation: {detail}"
            )
    return evidence_type


def _parse_evidence_field_args(values, evidence_ids, field_name):
    """Map CLI ``ref:value`` entries to evidence metadata without truncating refs.

    Match an explicitly supplied evidence ref first. This lets canonical tokens such
    as ``FL-SunBiz:L10000130392`` retain their full key instead of being truncated
    to ``FL-SunBiz`` by a first-colon split.
    """
    parsed = {}
    evidence_ids = sorted(evidence_ids or [], key=len, reverse=True)
    for value in values or []:
        ref = next(
            (item for item in evidence_ids if value.startswith(f"{item}:")), None
        )
        if ref is not None:
            field_value = value[len(ref) + 1 :]
        elif ":" in value:
            fallback_ref, field_value = value.split(":", 1)
            ref = fallback_ref
        else:
            raise ValueError(
                f"Invalid {field_name} metadata {value!r}. "
                "Expected '<evidence_ref>:<value>'."
            )
        if ref in parsed:
            raise ValueError(
                f"Duplicate {field_name} metadata for evidence '{ref}'. "
                "Each --evidence reference stores one value per metadata field; "
                "combine the excerpts explicitly or use separate evidence refs."
            )
        parsed[ref] = {field_name: field_value}
    return parsed


def _parse_source_quote_args(source_quote_args, evidence_ids):
    """Map CLI ``ref:quote`` values to refs, including canonical refs with colons."""
    return _parse_evidence_field_args(source_quote_args, evidence_ids, "quote")


def _merge_evidence_metadata(evidence_ids, *metadata_maps):
    """Merge independently parsed quote/page/assessment maps for known refs."""
    merged = {ref: {} for ref in evidence_ids or []}
    for metadata in metadata_maps:
        for ref, values in (metadata or {}).items():
            if ref not in merged:
                raise ValueError(
                    f"Evidence metadata supplied for '{ref}', but that ref is not in --evidence"
                )
            merged[ref].update(values)
    return merged


def _normalize_event_date(raw_date):
    """Normalize a finding date in both package and direct-script execution."""
    if not raw_date:
        return None, None
    try:
        try:
            from tools.date_normalize import normalize_date
        except ImportError:
            from date_normalize import normalize_date
        return normalize_date(raw_date)
    except Exception as exc:
        print(
            f"WARNING: Could not normalize finding date {raw_date!r}: {exc}",
            file=sys.stderr,
        )
        return None, None


VALID_CORRECTION_TYPES = [
    "factual_error",
    "source_mismatch",
    "hallucination",
    "outdated",
    "refinement",
    "merge",
    "retraction",
]

# Fields that can be corrected via update_finding() — whitelist to prevent SQL injection
ALLOWED_CORRECT_FIELDS = {
    "summary",
    "detail",
    "target_name",
    "date_of_event",
    "confidence",
    "finding_type",
    "claim_type",
    "thread_id",
    "source_datasets",
    "profile_id",
    "lead_id",
}


def _validate_finding_candidate(candidate, evidence, *, publication=False, clamp=True):
    """Validate one candidate record for insertion, correction, or verification.

    This is pure validation/normalization: it performs no database writes and
    returns the effective confidence. New inserts and verification require every
    evidence row to be quoted and valid. Correction callers may repair legacy
    records whose provenance is incomplete without first passing publication.
    """
    claim_type = candidate["claim_type"]
    if claim_type not in VALID_CLAIM_TYPES:
        raise ValueError(
            f"Unsupported claim_type '{claim_type}'. Allowed: {', '.join(VALID_CLAIM_TYPES)}"
        )
    sources = _parse_stored_source_datasets(candidate["source_datasets"])
    confidence = candidate["confidence"]
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"Unsupported confidence '{confidence}'")
    finding_type = candidate.get("finding_type")
    if finding_type is not None and finding_type not in VALID_FINDING_TYPES:
        raise ValueError(f"Unsupported finding_type '{finding_type}'")
    if (publication or claim_type == "direct_quote") and not evidence:
        raise ValueError("Cannot record or verify this claim without at least one evidence reference")
    if publication:
        missing = [row["evidence_ref"] for row in evidence if not str(row.get("source_quote") or "").strip()]
        if missing:
            raise ValueError("missing source_quote for " + ", ".join(missing))
    for row in evidence:
        _validate_evidence_payload(
            row["evidence_ref"], row.get("source_quote"),
            stored_type=row.get("evidence_type"), claim_type=claim_type,
            require_quote=publication,
        )
    effective, claim_clamped = _enforce_confidence_cap(claim_type, confidence)
    effective, source_clamped = _enforce_source_confidence_cap(sources, effective)
    if (claim_clamped or source_clamped) and not clamp:
        raise ValueError(
            f"confidence '{confidence}' exceeds the '{effective}' cap for this claim and its sources"
        )
    if claim_clamped:
        print(
            f"WARNING: Confidence clamped to '{effective}' (max for claim_type='{claim_type}').",
            file=sys.stderr,
        )
    if source_clamped:
        print(
            f"WARNING: Confidence clamped to '{effective}' (max for provenance-opaque source(s): "
            f"{', '.join(sorted(PROVENANCE_OPAQUE_SOURCES.intersection(sources)))}).",
            file=sys.stderr,
        )
    return effective


def _finding_evidence_rows(db, finding_id):
    return [dict(row) for row in db.execute(
        "SELECT evidence_type, evidence_ref, source_quote FROM finding_evidence WHERE finding_id=?",
        (finding_id,),
    )]


def _canonical_name_on_db(db, name):
    """Resolve an unambiguous spelling alias without a second connection/cache."""
    rows = db.execute(
        "SELECT DISTINCT canonical_name FROM name_aliases WHERE lower(alias)=lower(?)",
        (name,),
    ).fetchall()
    return rows[0]["canonical_name"] if len(rows) == 1 else name


def add_finding_to_db(
    db, target_name, summary, finding_type=None, detail=None, evidence_ids=None,
    source_datasets=None, confidence="medium", date_of_event=None, lead_id=None,
    claim_type="inference", source_quotes=None, thread_id=None, email_sender=None,
    profile_id=None, agent_run_id=None,
):
    """Insert a validated finding using only the caller's open connection.

    The caller owns the transaction, rollback, commit, and connection lifetime.
    The connection must use sqlite3.Row and the current investigation schema.
    No schema migration, database open, or commit occurs here. This lets staged
    imports insert canonical evidence and their import receipt atomically.
    Every new claim requires evidence references and an exact quote per reference;
    its verification status remains unverified until a separate review.
    """
    source_datasets = _validate_source_datasets(source_datasets)
    if evidence_ids is None:
        evidence_ids = []
    elif isinstance(evidence_ids, str) or not isinstance(evidence_ids, (list, tuple)):
        raise ValueError("evidence_ids must be a list of evidence references")
    if source_quotes is not None and not isinstance(source_quotes, dict):
        raise ValueError("source_quotes must map each evidence_ref to quote metadata")
    source_quotes = source_quotes or {}
    unknown_metadata_refs = set(source_quotes) - set(evidence_ids)
    if unknown_metadata_refs:
        raise ValueError(
            "Evidence metadata supplied for refs not present in evidence_ids: "
            + ", ".join(sorted(unknown_metadata_refs))
        )
    normalized_refs = [str(ref).strip() for ref in evidence_ids]
    if len(set(normalized_refs)) != len(normalized_refs):
        raise ValueError("evidence_ids contains duplicate references")
    evidence_rows = []
    for ref in evidence_ids:
        metadata = source_quotes.get(ref) or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"source_quotes['{ref}'] must be a metadata mapping")
        if "quote" in metadata and not isinstance(metadata["quote"], str):
            raise ValueError(f"Evidence '{ref}' requires a non-empty source_quote string")
        evidence_type = _validate_evidence_payload(
            ref, metadata.get("quote"), claim_type=claim_type,
            require_quote=True,
        )
        evidence_rows.append({
            "evidence_ref": str(ref).strip(), "evidence_type": evidence_type,
            "source_quote": metadata.get("quote"), "source_page": metadata.get("page"),
            "assessment": metadata.get("assessment"),
        })
    requested_confidence = confidence
    confidence = _validate_finding_candidate({
        "claim_type": claim_type, "confidence": confidence,
        "source_datasets": source_datasets, "finding_type": finding_type,
    }, evidence_rows, publication=True)
    if profile_id is None:
        profile_id = os.environ.get("ITHILDIN_PROFILE")
        if not profile_id:
            active = db.execute(
                "SELECT value FROM investigation_config WHERE key='active_profile'"
            ).fetchone()
            profile_id = active["value"] if active else None
    if agent_run_id is None:
        agent_run_id = os.environ.get("ITHILDIN_AGENT_RUN_ID")
    target_name = _canonical_name_on_db(db, target_name)
    thread_id = _resolve_finding_thread_id(db, thread_id, profile_id)
    event_date_iso, date_precision = _normalize_event_date(date_of_event)
    cursor = db.execute(
        """INSERT INTO findings (
            target_name, finding_type, summary, detail, source_datasets, confidence,
            date_of_event, lead_id, claim_type, verification_status, thread_id,
            quality_state, confidence_requested, profile_id, agent_run_id,
            event_date_iso, date_precision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', ?, 'unchecked', ?, ?, ?, ?, ?)""",
        (target_name, finding_type, summary, detail, json.dumps(source_datasets),
         confidence, date_of_event, lead_id, claim_type, thread_id,
         requested_confidence, profile_id, agent_run_id, event_date_iso, date_precision),
    )
    finding_id = cursor.lastrowid
    _link_finding_entity(db, finding_id, target_name, agent_run_id=agent_run_id)
    for row in evidence_rows:
        db.execute(
            """INSERT INTO finding_evidence (
                finding_id, evidence_type, evidence_ref, source_quote, source_page,
                assessment, email_sender
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (finding_id, row["evidence_type"], row["evidence_ref"], row["source_quote"],
             row["source_page"], row["assessment"],
             email_sender if row["evidence_type"] == "efta" else None),
        )
    return finding_id


def add_finding(
    target_name, summary, finding_type=None, detail=None, evidence_ids=None,
    source_datasets=None, confidence="medium", date_of_event=None, lead_id=None,
    claim_type="inference", source_quotes=None, thread_id=None, email_sender=None,
    profile_id=None, agent_run_id=None,
):
    """Add a finding and its evidence atomically through the canonical writer."""
    if profile_id is None:
        profile_id = _detect_active_profile()
    db = _get_db_standalone()
    try:
        finding_id = add_finding_to_db(
            db, target_name, summary, finding_type=finding_type, detail=detail,
            evidence_ids=evidence_ids, source_datasets=source_datasets,
            confidence=confidence, date_of_event=date_of_event, lead_id=lead_id,
            claim_type=claim_type, source_quotes=source_quotes, thread_id=thread_id,
            email_sender=email_sender, profile_id=profile_id, agent_run_id=agent_run_id,
        )
        db.commit()
        return finding_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _resolve_profile(profile_id=None, all_profiles=False):
    """Resolve profile_id: explicit > active profile > None. Returns None if all_profiles."""
    if all_profiles:
        return None
    if profile_id is not None:
        return profile_id
    try:
        from tools.investigation_context import get_active_profile_id

        return get_active_profile_id() or None
    except ImportError:
        try:
            from investigation_context import get_active_profile_id

            return get_active_profile_id() or None
        except ImportError:
            return None


def list_findings(
    target=None,
    finding_type=None,
    confidence=None,
    limit=50,
    thread_id=None,
    profile_id=None,
    all_profiles=False,
):
    """List findings with optional filters."""
    db = _get_db_standalone()
    conditions = []
    params = []

    resolved_profile = _resolve_profile(profile_id, all_profiles)
    if resolved_profile:
        conditions.append("profile_id = ?")
        params.append(resolved_profile)

    if target:
        conditions.append("target_name LIKE ?")
        params.append(f"%{target}%")
    if finding_type:
        conditions.append("finding_type = ?")
        params.append(finding_type)
    if confidence:
        conditions.append("confidence = ?")
        params.append(confidence)
    if thread_id:
        conditions.append("thread_id = ?")
        params.append(thread_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"SELECT * FROM findings {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_finding(finding_id):
    """Get a single finding with evidence and connections."""
    db = _get_db_standalone()
    finding = db.execute(
        "SELECT * FROM findings WHERE id = ?", (finding_id,)
    ).fetchone()
    if not finding:
        db.close()
        return None

    result = dict(finding)
    result["evidence"] = [
        dict(e)
        for e in db.execute(
            "SELECT * FROM finding_evidence WHERE finding_id = ?", (finding_id,)
        ).fetchall()
    ]
    result["connections"] = [
        dict(c)
        for c in db.execute(
            "SELECT * FROM connections WHERE finding_id = ?", (finding_id,)
        ).fetchall()
    ]
    db.close()
    return result


def _evidence_snapshot(row):
    """Return the provenance fields stored in an evidence audit snapshot."""
    values = dict(row)
    return {
        key: values.get(key)
        for key in (
            "evidence_type",
            "evidence_ref",
            "source_quote",
            "source_page",
            "assessment",
            "email_sender",
            "email_date",
            "chain_position",
        )
    }


def _record_evidence_correction(
    db,
    finding_id,
    evidence_ref,
    field_name,
    old_value,
    new_value,
    reason,
    corrected_by,
    correction_type="refinement",
):
    """Append an immutable correction row for a composite-key evidence record."""
    if not str(reason or "").strip():
        raise ValueError("An audit reason is required for evidence changes")

    def serialize(value):
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True, default=str)
        return str(value) if value is not None else None

    db.execute(
        """
        INSERT INTO corrections (
            table_name, record_id, record_key, field_name, old_value, new_value,
            reason, corrected_by, correction_type
        ) VALUES ('finding_evidence', ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            finding_id,
            evidence_ref,
            field_name,
            serialize(old_value),
            serialize(new_value),
            reason.strip(),
            corrected_by,
            correction_type,
        ),
    )


def _invalidate_verified_finding(db, finding, reason, corrected_by):
    """Require fresh review after a verified claim or its evidence changes."""
    if finding["verification_status"] != "verified":
        return
    db.execute(
        """
        INSERT INTO corrections (
            table_name, record_id, field_name, old_value, new_value,
            reason, corrected_by, correction_type
        ) VALUES ('findings', ?, 'verification_status', 'verified', 'unverified',
                  ?, ?, 'refinement')
    """,
        (
            finding["id"],
            f"Claim or evidence changed and requires re-verification: {reason}",
            corrected_by,
        ),
    )
    db.execute(
        """
        UPDATE findings
        SET verification_status = 'unverified', verified_by = NULL, verified_at = NULL
        WHERE id = ?
    """,
        (finding["id"],),
    )


def add_finding_evidence(
    finding_id,
    evidence_ref,
    *,
    source_quote=None,
    source_page=None,
    assessment=None,
    email_sender=None,
    email_date=None,
    chain_position=None,
    reason,
    corrected_by="human",
):
    """Add one evidence row and its correction audit entry atomically."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        finding = db.execute(
            "SELECT id, claim_type, verification_status FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        if finding is None:
            raise ValueError(f"Finding #{finding_id} does not exist")
        evidence_ref = str(evidence_ref or "").strip()
        evidence_type = _validate_evidence_payload(
            evidence_ref,
            source_quote,
            claim_type=finding["claim_type"],
            require_quote=source_quote is not None,
        )
        if db.execute(
            "SELECT 1 FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
            (finding_id, evidence_ref),
        ).fetchone():
            raise ValueError(
                f"Evidence '{evidence_ref}' already exists on finding #{finding_id}"
            )
        if chain_position is not None:
            chain_position = int(chain_position)
        snapshot = {
            "evidence_type": evidence_type,
            "evidence_ref": evidence_ref,
            "source_quote": source_quote,
            "source_page": source_page,
            "assessment": assessment,
            "email_sender": email_sender if evidence_type == "efta" else None,
            "email_date": email_date if evidence_type == "efta" else None,
            "chain_position": chain_position if evidence_type == "efta" else None,
        }
        db.execute(
            """
            INSERT INTO finding_evidence (
                finding_id, evidence_type, evidence_ref, source_quote, source_page,
                assessment, email_sender, email_date, chain_position
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                finding_id,
                snapshot["evidence_type"],
                snapshot["evidence_ref"],
                snapshot["source_quote"],
                snapshot["source_page"],
                snapshot["assessment"],
                snapshot["email_sender"],
                snapshot["email_date"],
                snapshot["chain_position"],
            ),
        )
        _record_evidence_correction(
            db,
            finding_id,
            evidence_ref,
            "__row__",
            None,
            snapshot,
            reason,
            corrected_by,
        )
        _invalidate_verified_finding(db, finding, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def correct_finding_evidence(
    finding_id,
    evidence_ref,
    field,
    new_value,
    *,
    reason,
    correction_type="refinement",
    corrected_by="human",
):
    """Correct one evidence field and append its audit entry atomically."""
    if field not in EVIDENCE_CORRECT_FIELDS:
        raise ValueError(
            f"Cannot correct evidence field '{field}'. Allowed: "
            f"{', '.join(sorted(EVIDENCE_CORRECT_FIELDS))}"
        )
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        finding = db.execute(
            "SELECT id, claim_type, verification_status FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        if finding is None:
            raise ValueError(f"Finding #{finding_id} does not exist")
        row = db.execute(
            "SELECT * FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
            (finding_id, evidence_ref),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Evidence '{evidence_ref}' does not exist on finding #{finding_id}"
            )
        if field in EFTA_ONLY_EVIDENCE_FIELDS and row["evidence_type"] != "efta":
            raise ValueError(
                f"Cannot correct {field} on non-EFTA evidence '{evidence_ref}'. "
                "EFTA email metadata is only valid when evidence_type='efta'."
            )
        old_ref = row["evidence_ref"]
        old_value = row[field]
        candidate = dict(row)
        if field == "chain_position" and new_value not in (None, ""):
            new_value = int(new_value)
        elif new_value == "" and field != "evidence_ref":
            new_value = None
        if field == "evidence_ref":
            new_value = str(new_value or "").strip()
        candidate[field] = new_value
        candidate["evidence_type"] = _validate_evidence_payload(
            candidate["evidence_ref"],
            candidate.get("source_quote"),
            claim_type=finding["claim_type"],
        )
        if field == "evidence_ref" and candidate["evidence_type"] != "efta":
            populated_efta_fields = sorted(
                name
                for name in EFTA_ONLY_EVIDENCE_FIELDS
                if candidate.get(name) not in (None, "")
            )
            if populated_efta_fields:
                fields = ", ".join(populated_efta_fields)
                raise ValueError(
                    f"Cannot change EFTA evidence '{old_ref}' to non-EFTA ref "
                    f"'{candidate['evidence_ref']}' while EFTA-only metadata remains: "
                    f"{fields}. Clear each field first with an audited "
                    "evidence-correct --value '' operation, then retry the ref change."
                )

        if field == "evidence_ref":
            db.execute(
                """
                UPDATE finding_evidence
                SET evidence_ref = ?, evidence_type = ?
                WHERE finding_id = ? AND evidence_ref = ?
            """,
                (new_value, candidate["evidence_type"], finding_id, old_ref),
            )
        else:
            db.execute(
                f"UPDATE finding_evidence SET {field} = ? "
                "WHERE finding_id = ? AND evidence_ref = ?",
                (new_value, finding_id, old_ref),
            )
        _record_evidence_correction(
            db,
            finding_id,
            old_ref,
            field,
            old_value,
            new_value,
            reason,
            corrected_by,
            correction_type,
        )
        _invalidate_verified_finding(db, finding, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_finding_evidence(finding_id, evidence_ref, *, reason, corrected_by="human"):
    """Delete one evidence row while retaining an immutable audit snapshot."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        finding = db.execute(
            "SELECT id, claim_type, verification_status FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        if finding is None:
            raise ValueError(f"Finding #{finding_id} does not exist")
        row = db.execute(
            "SELECT * FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
            (finding_id, evidence_ref),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Evidence '{evidence_ref}' does not exist on finding #{finding_id}"
            )
        evidence_count = db.execute(
            "SELECT COUNT(*) FROM finding_evidence WHERE finding_id = ?",
            (finding_id,),
        ).fetchone()[0]
        if finding["claim_type"] == "direct_quote" and evidence_count <= 1:
            raise ValueError(
                "Cannot delete the last evidence row from a direct_quote finding; "
                "correct its claim_type first"
            )
        snapshot = _evidence_snapshot(row)
        db.execute(
            "DELETE FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
            (finding_id, evidence_ref),
        )
        _record_evidence_correction(
            db,
            finding_id,
            evidence_ref,
            "__row__",
            snapshot,
            None,
            reason,
            corrected_by,
            correction_type="retraction",
        )
        _invalidate_verified_finding(db, finding, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_finding(
    finding_id,
    field,
    new_value,
    reason,
    correction_type="refinement",
    corrected_by=None,
):
    """Update a finding field with correction audit trail. Returns True on success."""
    if field not in ALLOWED_CORRECT_FIELDS:
        raise ValueError(
            f"Cannot correct field '{field}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_CORRECT_FIELDS))}"
        )

    if not str(reason or "").strip():
        raise ValueError("A correction reason is required")

    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        finding = db.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        if not finding:
            db.rollback()
            return False

        candidate = dict(finding)
        stored_value = new_value
        if field == "source_datasets":
            stored_value = json.dumps(_parse_stored_source_datasets(new_value))
        elif field in {"lead_id", "thread_id"}:
            stored_value = None if new_value in (None, "") else int(new_value)
        candidate[field] = stored_value
        if field in {"thread_id", "profile_id"}:
            candidate["thread_id"] = _resolve_finding_thread_id(
                db, candidate["thread_id"], candidate["profile_id"]
            )
            if field == "thread_id":
                stored_value = candidate["thread_id"]
        effective_confidence = _validate_finding_candidate(
            candidate, _finding_evidence_rows(db, finding_id)
        )

        old_value = finding[field] if field in finding.keys() else None
        db.execute(
            """
            INSERT INTO corrections (table_name, record_id, field_name, old_value, new_value,
                                    reason, corrected_by, correction_type)
            VALUES ('findings', ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                finding_id,
                field,
                str(old_value) if old_value is not None else None,
                str(stored_value),
                reason,
                corrected_by,
                correction_type,
            ),
        )

        # Apply the update. Keep derived temporal fields synchronized atomically.
        if field == "date_of_event":
            event_date_iso, date_precision = _normalize_event_date(stored_value)
            db.execute(
                """
                UPDATE findings
                SET date_of_event = ?, event_date_iso = ?, date_precision = ?
                WHERE id = ?
                """,
                (stored_value, event_date_iso, date_precision, finding_id),
            )
        else:
            db.execute(
                f"UPDATE findings SET {field} = ? WHERE id = ?",
                (stored_value, finding_id),
            )
        if field == "confidence":
            db.execute(
                "UPDATE findings SET confidence_requested=? WHERE id=?",
                (stored_value, finding_id),
            )
        if effective_confidence != candidate["confidence"]:
            db.execute(
                """INSERT INTO corrections (
                    table_name, record_id, field_name, old_value, new_value,
                    reason, corrected_by, correction_type
                ) VALUES ('findings', ?, 'confidence', ?, ?, ?, ?, 'refinement')""",
                (finding_id, candidate["confidence"], effective_confidence,
                 f"Apply claim/source confidence cap after {field} correction: {reason}",
                 corrected_by),
            )
            db.execute(
                "UPDATE findings SET confidence=?, confidence_requested=? WHERE id=?",
                (effective_confidence, candidate["confidence"], finding_id),
            )
        if field == "profile_id" and candidate["thread_id"] != finding["thread_id"]:
            db.execute(
                "UPDATE findings SET thread_id=? WHERE id=?",
                (candidate["thread_id"], finding_id),
            )
        if field == "target_name" and old_value != stored_value:
            _reconcile_finding_subject(db, finding, stored_value, reason, corrected_by)
        if old_value != stored_value or effective_confidence != finding["confidence"]:
            _invalidate_verified_finding(db, finding, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_finding(finding_id, verified_by="human"):
    """Mark a finding verified only when its provenance satisfies publication gates.

    Legacy findings may have incomplete provenance. The audit contract requires
    valid source tokens, at least one evidence reference, and an exact source
    quote for each reference before verification. Locally
    resolvable quote spans must match; remote/canonical references remain
    publishable but are reported as unchecked by ``evidence-audit``.
    """
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        finding = db.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        if finding is None:
            raise ValueError(f"Finding #{finding_id} does not exist")
        try:
            _validate_finding_candidate(
                dict(finding), _finding_evidence_rows(db, finding_id),
                publication=True, clamp=False,
            )
        except ValueError as exc:
            raise ValueError(f"Finding #{finding_id} cannot be verified: {exc}") from exc

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            UPDATE findings SET verification_status = 'verified', verified_by = ?, verified_at = ?
            WHERE id = ?
        """,
            (verified_by, now, finding_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def dispute_finding(finding_id, reason, corrected_by=None):
    """Mark a finding as disputed with reason recorded in corrections."""
    db = _get_db_standalone()
    now = datetime.now(timezone.utc).isoformat()

    # Get current status for audit trail
    finding = db.execute(
        "SELECT verification_status FROM findings WHERE id = ?", (finding_id,)
    ).fetchone()
    old_status = finding["verification_status"] if finding else "unknown"

    db.execute(
        """
        INSERT INTO corrections (table_name, record_id, field_name, old_value, new_value,
                                reason, corrected_by, correction_type)
        VALUES ('findings', ?, 'verification_status', ?, 'disputed', ?, ?, 'factual_error')
    """,
        (finding_id, old_status, reason, corrected_by),
    )

    db.execute(
        """
        UPDATE findings SET verification_status = 'disputed', verified_by = ?, verified_at = ?
        WHERE id = ?
    """,
        (corrected_by, now, finding_id),
    )
    db.commit()
    db.close()


def retract_finding(finding_id, reason, corrected_by=None):
    """Retract a finding entirely. Flags downstream leads for review."""
    db = _get_db_standalone()
    now = datetime.now(timezone.utc).isoformat()

    finding = db.execute(
        "SELECT * FROM findings WHERE id = ?", (finding_id,)
    ).fetchone()
    if not finding:
        db.close()
        return False

    # Record the retraction
    db.execute(
        """
        INSERT INTO corrections (table_name, record_id, field_name, old_value, new_value,
                                reason, corrected_by, correction_type)
        VALUES ('findings', ?, 'verification_status', ?, 'retracted', ?, ?, 'retraction')
    """,
        (finding_id, finding["verification_status"], reason, corrected_by),
    )

    db.execute(
        """
        UPDATE findings SET verification_status = 'retracted', verified_by = ?, verified_at = ?
        WHERE id = ?
    """,
        (corrected_by, now, finding_id),
    )

    # Flag the originating lead if it exists
    if finding["lead_id"]:
        db.execute(
            """
            INSERT INTO lead_notes (lead_id, note)
            VALUES (?, ?)
        """,
            (
                finding["lead_id"],
                f"WARNING: Finding #{finding_id} was retracted. Reason: {reason}",
            ),
        )

    # Flag any connections that cite this finding
    connections = db.execute(
        "SELECT id FROM connections WHERE finding_id = ?", (finding_id,)
    ).fetchall()
    for conn in connections:
        db.execute(
            """
            INSERT INTO corrections (table_name, record_id, field_name, old_value, new_value,
                                    reason, corrected_by, correction_type)
            VALUES ('connections', ?, 'verification_status', 'unverified', 'disputed',
                    ?, ?, 'retraction')
        """,
            (
                conn["id"],
                f"Source finding #{finding_id} was retracted: {reason}",
                corrected_by,
            ),
        )
        db.execute(
            "UPDATE connections SET verification_status = 'disputed' WHERE id = ?",
            (conn["id"],),
        )

    db.commit()
    db.close()
    return True


def get_corrections(
    table_name=None, record_id=None, record_key=None, correction_type=None, limit=50
):
    """Get correction audit trail with optional filters."""
    db = _get_db_standalone()
    conditions = []
    params = []

    if table_name:
        conditions.append("table_name = ?")
        params.append(table_name)
    if record_id is not None:
        conditions.append("record_id = ?")
        params.append(record_id)
    if record_key is not None:
        conditions.append("record_key = ?")
        params.append(record_key)
    if correction_type:
        conditions.append("correction_type = ?")
        params.append(correction_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"SELECT * FROM corrections {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def audit_finding_evidence(finding_id=None, profile_id=None, all_profiles=False):
    """Report legacy provenance violations without modifying finding/evidence rows."""
    db = _get_db_standalone()
    try:
        conditions = []
        params = []
        if finding_id is not None:
            conditions.append("id = ?")
            params.append(finding_id)
        resolved_profile = _resolve_profile(profile_id, all_profiles)
        if resolved_profile:
            conditions.append("profile_id = ?")
            params.append(resolved_profile)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        findings = db.execute(
            f"SELECT id, claim_type, verification_status, source_datasets, profile_id "
            f"FROM findings {where} ORDER BY id",
            params,
        ).fetchall()
        if finding_id is not None and not findings:
            raise ValueError(
                f"Finding #{finding_id} does not exist in the selected profile scope"
            )

        issues = []
        evidence_scanned = 0
        span_counts = {"matched": 0, "mismatch": 0, "unchecked": 0, "missing": 0}

        def issue(finding, code, message, *, severity="error", evidence_ref=None):
            item = {
                "finding_id": finding["id"],
                "profile_id": finding["profile_id"],
                "severity": severity,
                "code": code,
                "message": message,
            }
            if evidence_ref is not None:
                item["evidence_ref"] = evidence_ref
            issues.append(item)

        for finding in findings:
            try:
                _parse_stored_source_datasets(finding["source_datasets"])
            except ValueError as exc:
                issue(finding, "invalid_source_datasets", str(exc))

            evidence = db.execute(
                "SELECT * FROM finding_evidence WHERE finding_id = ? ORDER BY evidence_ref",
                (finding["id"],),
            ).fetchall()
            evidence_scanned += len(evidence)
            if not evidence:
                severity = (
                    "error"
                    if finding["claim_type"] == "direct_quote"
                    or finding["verification_status"] == "verified"
                    else "warning"
                )
                issue(
                    finding,
                    "missing_evidence",
                    "Finding has no evidence references",
                    severity=severity,
                )
                continue

            for row in evidence:
                ref = row["evidence_ref"]
                expected_type = _classify_evidence_ref(ref)
                if row["evidence_type"] != expected_type:
                    issue(
                        finding,
                        "evidence_type_mismatch",
                        f"Stored as {row['evidence_type']!r}; expected {expected_type!r}",
                        evidence_ref=ref,
                    )
                try:
                    _validate_evidence_ref(ref)
                except ValueError as exc:
                    issue(
                        finding,
                        "invalid_evidence_ref",
                        str(exc),
                        evidence_ref=ref,
                    )

                quote = row["source_quote"]
                span_status, span_detail = _check_source_quote_span(
                    ref, quote, evidence_type=expected_type
                )
                span_counts[span_status] += 1
                if span_status == "missing":
                    severity = (
                        "error"
                        if finding["claim_type"] == "direct_quote"
                        or finding["verification_status"] == "verified"
                        else "warning"
                    )
                    issue(
                        finding,
                        "missing_source_quote",
                        "Evidence has no non-empty source_quote",
                        severity=severity,
                        evidence_ref=ref,
                    )
                elif span_status == "mismatch":
                    issue(
                        finding,
                        "source_quote_mismatch",
                        span_detail,
                        evidence_ref=ref,
                    )

        return {
            "report_only": True,
            "findings_scanned": len(findings),
            "evidence_scanned": evidence_scanned,
            "issue_count": len(issues),
            "span_checks": span_counts,
            "issues": issues,
        }
    finally:
        db.close()


def get_unverified(limit=50, profile_id=None, all_profiles=False):
    """Get unverified findings in the active or explicitly selected profile."""
    db = _get_db_standalone()
    conditions = ["f.verification_status = 'unverified'"]
    params = []
    resolved_profile = _resolve_profile(profile_id, all_profiles)
    if resolved_profile:
        conditions.append("f.profile_id = ?")
        params.append(resolved_profile)
    rows = db.execute(
        f"""
        SELECT f.*, GROUP_CONCAT(fe.evidence_ref, ', ') as evidence_refs
        FROM findings f
        LEFT JOIN finding_evidence fe ON fe.finding_id = f.id
        WHERE {" AND ".join(conditions)}
        GROUP BY f.id
        ORDER BY
            CASE f.confidence
                WHEN 'confirmed' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 WHEN 'low' THEN 3
                WHEN 'unverified' THEN 4
            END,
            f.created_at DESC
        LIMIT ?
    """,
        (*params, limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_provenance(finding_id):
    """Get full provenance chain for a finding: evidence with source quotes + corrections."""
    db = _get_db_standalone()
    finding = db.execute(
        "SELECT * FROM findings WHERE id = ?", (finding_id,)
    ).fetchone()
    if not finding:
        db.close()
        return None

    result = dict(finding)
    result["evidence"] = [
        dict(e)
        for e in db.execute(
            "SELECT * FROM finding_evidence WHERE finding_id = ?", (finding_id,)
        ).fetchall()
    ]
    result["corrections"] = [
        dict(c)
        for c in db.execute(
            "SELECT * FROM corrections WHERE table_name = 'findings' AND record_id = ? ORDER BY created_at",
            (finding_id,),
        ).fetchall()
    ]
    result["evidence_corrections"] = [
        dict(c)
        for c in db.execute(
            "SELECT * FROM corrections WHERE table_name = 'finding_evidence' "
            "AND record_id = ? ORDER BY created_at",
            (finding_id,),
        ).fetchall()
    ]
    result["connections"] = [
        dict(c)
        for c in db.execute(
            "SELECT * FROM connections WHERE finding_id = ?", (finding_id,)
        ).fetchall()
    ]

    # Check source reliability for each evidence source
    for ev in result["evidence"]:
        # Try to match evidence to a known source
        rel = db.execute(
            "SELECT * FROM source_reliability WHERE ? LIKE '%' || source_name || '%'",
            (ev.get("evidence_ref", ""),),
        ).fetchone()
        ev["source_reliability"] = dict(rel) if rel else None

    db.close()
    return result


def search_findings(
    query, thread_id=None, profile_id=None, all_profiles=False, limit=30
):
    """Full-text search across findings. Wraps terms in quotes for safety."""
    db = _get_db_standalone()
    safe_query = '"' + query.replace('"', '""') + '"'
    resolved_profile = _resolve_profile(profile_id, all_profiles)

    conditions = ["findings_fts MATCH ?"]
    params = [safe_query]
    if thread_id:
        conditions.append("findings.thread_id = ?")
        params.append(thread_id)
    if resolved_profile:
        conditions.append("findings.profile_id = ?")
        params.append(resolved_profile)

    where = " AND ".join(conditions)
    rows = db.execute(
        f"""
        SELECT findings.*, findings_fts.rank
        FROM findings_fts
        JOIN findings ON findings.id = findings_fts.rowid
        WHERE {where}
        ORDER BY findings_fts.rank
        LIMIT ?
    """,
        params + [limit],
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Connections CRUD ─────────────────────────────────────────


def _ensure_entity(
    db, name, entity_type="unknown", source="auto:connect", agent_run_id=None
):
    """Ensure a connection endpoint is backed by a row in the entities registry.

    Enforces the invariant that no connection can exist without both endpoints
    registered as entities — so graph/network analysis (auto_leads, analyze-network,
    systemic-analysis) can see every node. Reuses any existing entity with the same
    name (preferring a richer, jurisdiction-bearing row); otherwise inserts a stub.
    The UNIQUE(name, jurisdiction) constraint can't dedupe NULL-jurisdiction stubs
    (SQLite treats NULLs as distinct), so we check explicitly before inserting.
    Resolution (alias -> exact -> fuzzy -> create) is delegated to
    resolve_or_create_entity, so a near-duplicate spelling (e.g. "Acme L.L.C."
    vs "Acme LLC") links to the existing row instead of spawning a stub.
    Returns (entity_id, created). Enriching the matched row further is left to
    entity_tracker / entity_dedup.
    """
    if not name or not name.strip():
        return (None, False)
    name = name.strip()
    try:
        from tools.entity_resolution import resolve_or_create_entity
    except ImportError:
        from entity_resolution import resolve_or_create_entity
    res = resolve_or_create_entity(
        db,
        name,
        entity_type=entity_type or "unknown",
        source=source,
        agent_run_id=agent_run_id,
    )
    if res.entity_id is None:
        return (None, False)
    created = res.action == "created"
    if created:
        print(
            f"  + auto-registered entity #{res.entity_id}: {name} "
            f"(type={entity_type or 'unknown'}, source={source}) — enrich via entity_tracker",
            file=sys.stderr,
        )
    elif res.action == "fuzzy":
        print(
            f"  ~ linked '{name}' to existing entity #{res.entity_id} "
            f"('{res.matched_name}', fuzzy {res.score}) — recorded alias",
            file=sys.stderr,
        )
    return (res.entity_id, created)


def _link_finding_entity(
    db, finding_id, target_name, mention_role="subject", agent_run_id=None, *, strict=False
):
    """Best-effort link finding -> canonical entity in finding_entities.

    Resolves target_name through the same alias->exact->fuzzy path connections use
    (resolve_or_create_entity), so a finding's subject becomes a first-class graph
    node instead of a bare string. Never raises: a resolver failure leaves the
    finding recorded with only its target_name (dual-read fallback still works).
    Skips silently if the finding_entities table doesn't exist (pre-migration DB).
    """
    if not target_name or not target_name.strip():
        return None
    try:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='finding_entities'"
        ).fetchone()
        if not exists:
            return None
        try:
            from tools.entity_resolution import resolve_or_create_entity
        except ImportError:
            from entity_resolution import resolve_or_create_entity
        res = resolve_or_create_entity(
            db,
            target_name.strip(),
            entity_type="unknown",
            source="auto:finding",
            agent_run_id=agent_run_id,
        )
        if res.entity_id is None:
            return None
        method = {
            "exact": "exact",
            "alias": "alias",
            "fuzzy": "fuzzy",
            "created": "created",
        }.get(res.action, res.action)
        db.execute(
            """
            INSERT OR IGNORE INTO finding_entities
                (finding_id, entity_id, mention_role, raw_name,
                 resolution_status, resolution_method, resolution_score)
            VALUES (?, ?, ?, ?, 'asserted', ?, ?)
        """,
            (
                finding_id,
                res.entity_id,
                mention_role,
                target_name.strip(),
                method,
                getattr(res, "score", None),
            ),
        )
        return res.entity_id
    except Exception as e:
        if strict:
            raise
        print(f"  (finding-entity link skipped: {e})", file=sys.stderr)
        return None


def _reconcile_finding_subject(db, finding, target_name, reason, corrected_by):
    """Replace generated subject links while preserving other/manual mentions."""
    finding_id = finding["id"]
    before = [dict(row) for row in db.execute(
        "SELECT * FROM finding_entities WHERE finding_id=? AND mention_role='subject'",
        (finding_id,),
    )]
    db.execute(
        """DELETE FROM finding_entities WHERE finding_id=? AND mention_role='subject'
           AND resolution_method IN ('exact','alias','fuzzy','created','qualified_identifier')""",
        (finding_id,),
    )
    _link_finding_entity(db, finding_id, target_name, strict=True)
    after = [dict(row) for row in db.execute(
        "SELECT * FROM finding_entities WHERE finding_id=? AND mention_role='subject'",
        (finding_id,),
    )]
    db.execute(
        """INSERT INTO corrections (
            table_name, record_id, field_name, old_value, new_value,
            reason, corrected_by, correction_type
        ) VALUES ('finding_entities', ?, 'subject_links', ?, ?, ?, ?, 'refinement')""",
        (finding_id, json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True),
         f"Reconcile subject after target correction: {reason}", corrected_by),
    )


def relate_findings(
    from_finding_id, to_finding_id, relation_type, assessment=None, created_by=None
):
    """Record a typed relation between two findings (contradicts/corroborates/etc).

    Replaces the prior practice of burying "contradicted by #NNNN" in
    corrections.reason prose, making the claim graph queryable. Returns True on
    insert. Idempotent via the UNIQUE constraint.
    """
    valid = {
        "contradicts",
        "corroborates",
        "supersedes",
        "duplicates",
        "refines",
        "depends_on",
    }
    if relation_type not in valid:
        raise ValueError(f"relation_type must be one of {sorted(valid)}")
    if from_finding_id == to_finding_id:
        raise ValueError("a finding cannot relate to itself")
    db = _get_db_standalone()
    for fid in (from_finding_id, to_finding_id):
        if not db.execute("SELECT 1 FROM findings WHERE id = ?", (fid,)).fetchone():
            db.close()
            raise ValueError(f"finding #{fid} does not exist")
    db.execute(
        """
        INSERT OR IGNORE INTO finding_relations
            (from_finding_id, to_finding_id, relation_type, assessment, created_by)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            from_finding_id,
            to_finding_id,
            relation_type,
            assessment,
            created_by or "findings_tracker",
        ),
    )
    db.commit()
    db.close()
    return True


def delete_finding_relation(
    from_finding_id, to_finding_id, relation_type, reason, corrected_by=None
):
    """Delete one finding relation while retaining its full audit snapshot."""
    if not str(reason or "").strip():
        raise ValueError("An audit reason is required to delete a finding relation")

    db = _get_db_standalone()
    try:
        relation = db.execute(
            """
            SELECT * FROM finding_relations
            WHERE from_finding_id = ? AND to_finding_id = ? AND relation_type = ?
            """,
            (from_finding_id, to_finding_id, relation_type),
        ).fetchone()
        if relation is None:
            raise ValueError(
                f"finding relation #{from_finding_id} {relation_type} "
                f"#{to_finding_id} does not exist"
            )

        snapshot = json.dumps(dict(relation), sort_keys=True, default=str)
        db.execute(
            """
            INSERT INTO corrections (
                table_name, record_id, field_name, old_value, new_value,
                reason, corrected_by, correction_type
            ) VALUES ('finding_relations', ?, '__row__', ?, NULL, ?, ?, 'retraction')
            """,
            (
                relation["id"],
                snapshot,
                reason.strip(),
                corrected_by or "findings_tracker",
            ),
        )
        db.execute("DELETE FROM finding_relations WHERE id = ?", (relation["id"],))
        db.commit()
        return relation["id"]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _connection_evidence_snapshot(row):
    """Return the provenance fields stored in a connection evidence audit snapshot."""
    values = dict(row)
    return {
        key: values.get(key)
        for key in (
            "evidence_type",
            "evidence_ref",
            "source_quote",
            "source_page",
            "assessment",
        )
    }


def _record_connection_evidence_correction(
    db,
    connection_id,
    evidence_ref,
    field_name,
    old_value,
    new_value,
    reason,
    corrected_by,
    correction_type="refinement",
):
    """Append an immutable audit row for composite-key connection evidence."""
    if not str(reason or "").strip():
        raise ValueError("An audit reason is required for connection evidence changes")

    def serialize(value):
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True, default=str)
        return str(value) if value is not None else None

    db.execute(
        """
        INSERT INTO corrections (
            table_name, record_id, record_key, field_name, old_value, new_value,
            reason, corrected_by, correction_type
        ) VALUES ('connection_evidence', ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            connection_id,
            evidence_ref,
            field_name,
            serialize(old_value),
            serialize(new_value),
            reason.strip(),
            corrected_by,
            correction_type,
        ),
    )


def _record_connection_correction(
    db,
    connection_id,
    field_name,
    old_value,
    new_value,
    reason,
    corrected_by,
    correction_type="refinement",
):
    """Append an immutable audit row for a connection field/status change."""
    if not str(reason or "").strip():
        raise ValueError("An audit reason is required for connection changes")
    db.execute(
        """
        INSERT INTO corrections (
            table_name, record_id, field_name, old_value, new_value,
            reason, corrected_by, correction_type
        ) VALUES ('connections', ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            connection_id,
            field_name,
            str(old_value) if old_value is not None else None,
            str(new_value) if new_value is not None else None,
            reason.strip(),
            corrected_by,
            correction_type,
        ),
    )


def _invalidate_verified_connection(db, connection, reason, corrected_by):
    """Reset a verified edge after provenance or substantive edge data changes."""
    if connection["verification_status"] != "verified":
        return
    _record_connection_correction(
        db,
        connection["id"],
        "verification_status",
        "verified",
        "unverified",
        f"Connection provenance changed and requires re-verification: {reason}",
        corrected_by,
    )
    db.execute(
        """
        UPDATE connections
        SET verification_status='unverified', verified_by=NULL, verified_at=NULL
        WHERE id=?
    """,
        (connection["id"],),
    )


def add_connection_evidence(
    connection_id,
    evidence_ref,
    *,
    source_quote=None,
    source_page=None,
    assessment=None,
    reason,
    corrected_by="human",
):
    """Add one connection evidence row and its audit entry atomically."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        evidence_ref = str(evidence_ref or "").strip()
        evidence_type = _validate_evidence_payload(evidence_ref, source_quote)
        if db.execute(
            "SELECT 1 FROM connection_evidence WHERE connection_id=? AND evidence_ref=?",
            (connection_id, evidence_ref),
        ).fetchone():
            raise ValueError(
                f"Evidence '{evidence_ref}' already exists on connection #{connection_id}"
            )
        snapshot = {
            "evidence_type": evidence_type,
            "evidence_ref": evidence_ref,
            "source_quote": source_quote,
            "source_page": source_page,
            "assessment": assessment,
        }
        db.execute(
            """
            INSERT INTO connection_evidence (
                connection_id, evidence_type, evidence_ref,
                source_quote, source_page, assessment
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                connection_id,
                evidence_type,
                evidence_ref,
                source_quote,
                source_page,
                assessment,
            ),
        )
        _record_connection_evidence_correction(
            db,
            connection_id,
            evidence_ref,
            "__row__",
            None,
            snapshot,
            reason,
            corrected_by,
        )
        _invalidate_verified_connection(db, connection, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def correct_connection_evidence(
    connection_id,
    evidence_ref,
    field,
    new_value,
    *,
    reason,
    correction_type="refinement",
    corrected_by="human",
):
    """Correct one connection evidence field and audit the mutation atomically."""
    if field not in CONNECTION_EVIDENCE_CORRECT_FIELDS:
        raise ValueError(
            f"Cannot correct connection evidence field '{field}'. Allowed: "
            f"{', '.join(sorted(CONNECTION_EVIDENCE_CORRECT_FIELDS))}"
        )
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        row = db.execute(
            "SELECT * FROM connection_evidence WHERE connection_id=? AND evidence_ref=?",
            (connection_id, evidence_ref),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Evidence '{evidence_ref}' does not exist on connection #{connection_id}"
            )
        old_ref = row["evidence_ref"]
        old_value = row[field]
        if new_value == "" and field != "evidence_ref":
            new_value = None
        if field == "evidence_ref":
            new_value = str(new_value or "").strip()
        if old_value == new_value:
            db.rollback()
            return False
        candidate = dict(row)
        candidate[field] = new_value
        candidate["evidence_type"] = _validate_evidence_payload(
            candidate["evidence_ref"], candidate.get("source_quote")
        )

        if field == "evidence_ref":
            db.execute(
                """
                UPDATE connection_evidence
                SET evidence_ref=?, evidence_type=?
                WHERE connection_id=? AND evidence_ref=?
            """,
                (new_value, candidate["evidence_type"], connection_id, old_ref),
            )
        else:
            db.execute(
                f"UPDATE connection_evidence SET {field}=? "
                "WHERE connection_id=? AND evidence_ref=?",
                (new_value, connection_id, old_ref),
            )
        _record_connection_evidence_correction(
            db,
            connection_id,
            old_ref,
            field,
            old_value,
            new_value,
            reason,
            corrected_by,
            correction_type,
        )
        _invalidate_verified_connection(db, connection, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_connection_evidence(
    connection_id, evidence_ref, *, reason, corrected_by="human"
):
    """Delete connection evidence while preserving its complete audit snapshot."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        row = db.execute(
            "SELECT * FROM connection_evidence WHERE connection_id=? AND evidence_ref=?",
            (connection_id, evidence_ref),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Evidence '{evidence_ref}' does not exist on connection #{connection_id}"
            )
        snapshot = _connection_evidence_snapshot(row)
        db.execute(
            "DELETE FROM connection_evidence WHERE connection_id=? AND evidence_ref=?",
            (connection_id, evidence_ref),
        )
        _record_connection_evidence_correction(
            db,
            connection_id,
            evidence_ref,
            "__row__",
            snapshot,
            None,
            reason,
            corrected_by,
            correction_type="retraction",
        )
        _invalidate_verified_connection(db, connection, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def validate_connection_publication(db, connection):
    """Raise when an edge's current evidence/upstream provenance is not publishable.

    This intentionally accepts an open database connection so every publication
    surface can apply the exact same current-state gate without copying policy.
    Lifecycle status is checked by the caller: verification uses this while an
    edge is still unverified, whereas public readers first select verified rows.
    """
    if connection["finding_id"] is not None:
        finding = db.execute(
            "SELECT * FROM findings WHERE id=?",
            (connection["finding_id"],),
        ).fetchone()
        if finding is None:
            raise ValueError(f"references missing finding #{connection['finding_id']}")
        if finding["verification_status"] != "verified":
            raise ValueError(
                f"upstream finding #{connection['finding_id']} is not verified"
            )
        _validate_finding_candidate(
            dict(finding), _finding_evidence_rows(db, connection["finding_id"]),
            publication=True, clamp=False,
        )
    evidence = db.execute(
        "SELECT * FROM connection_evidence WHERE connection_id=? ORDER BY evidence_ref",
        (connection["id"],),
    ).fetchall()
    if not evidence:
        raise ValueError("has no evidence")
    for row in evidence:
        _validate_evidence_payload(
            row["evidence_ref"],
            row["source_quote"],
            stored_type=row["evidence_type"],
            require_quote=True,
        )
    return True


def get_connection(connection_id):
    """Return one connection with evidence, audit history, and upstream finding."""
    db = _get_db_standalone()
    try:
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            return None
        result = dict(connection)
        result["evidence"] = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM connection_evidence WHERE connection_id=? ORDER BY evidence_ref",
                (connection_id,),
            ).fetchall()
        ]
        result["corrections"] = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM corrections WHERE table_name='connections' AND record_id=? "
                "ORDER BY created_at,id",
                (connection_id,),
            ).fetchall()
        ]
        result["evidence_corrections"] = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM corrections WHERE table_name='connection_evidence' "
                "AND record_id=? ORDER BY created_at,id",
                (connection_id,),
            ).fetchall()
        ]
        result["upstream_finding"] = None
        if result.get("finding_id") is not None:
            finding = db.execute(
                "SELECT id,target_name,summary,verification_status FROM findings WHERE id=?",
                (result["finding_id"],),
            ).fetchone()
            result["upstream_finding"] = dict(finding) if finding else None
        for evidence in result["evidence"]:
            reliability = db.execute(
                "SELECT * FROM source_reliability "
                "WHERE ? LIKE '%' || source_name || '%'",
                (evidence["evidence_ref"],),
            ).fetchone()
            evidence["source_reliability"] = dict(reliability) if reliability else None
        result["publication_ready"] = False
        result["publication_error"] = None
        if result.get("verification_status") != "verified":
            result["publication_error"] = (
                f"connection status is {result.get('verification_status') or 'unverified'}"
            )
        else:
            try:
                validate_connection_publication(db, connection)
                result["publication_ready"] = True
            except ValueError as exc:
                result["publication_error"] = str(exc)
        return result
    finally:
        db.close()


def get_connection_provenance(connection_id):
    """Alias for the complete audited connection representation."""
    return get_connection(connection_id)


def verify_connection(connection_id, verified_by="human"):
    """Publish a connection only after every evidence row passes provenance gates."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        if connection["verification_status"] == "retracted":
            raise ValueError(
                f"Connection #{connection_id} is retracted and cannot be verified"
            )
        try:
            validate_connection_publication(db, connection)
        except ValueError as exc:
            detail = str(exc)
            if detail.startswith("upstream finding"):
                detail = "cannot be verified until " + detail
            raise ValueError(
                f"Connection #{connection_id} cannot be verified: {detail}"
            ) from exc
        if connection["verification_status"] == "verified":
            db.rollback()
            return False
        now = datetime.now(timezone.utc).isoformat()
        _record_connection_correction(
            db,
            connection_id,
            "verification_status",
            connection["verification_status"],
            "verified",
            "Connection evidence and upstream provenance passed publication validation",
            verified_by,
            correction_type="refinement",
        )
        db.execute(
            """
            UPDATE connections
            SET verification_status='verified', verified_by=?, verified_at=?
            WHERE id=?
        """,
            (verified_by, now, connection_id),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def dispute_connection(connection_id, reason, corrected_by="human"):
    """Mark a connection disputed with an immutable status correction."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        if connection["verification_status"] == "retracted":
            raise ValueError(
                f"Connection #{connection_id} is retracted and cannot be disputed"
            )
        if connection["verification_status"] == "disputed":
            db.rollback()
            return False
        _record_connection_correction(
            db,
            connection_id,
            "verification_status",
            connection["verification_status"],
            "disputed",
            reason,
            corrected_by,
            correction_type="factual_error",
        )
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            UPDATE connections
            SET verification_status='disputed', verified_by=?, verified_at=?
            WHERE id=?
        """,
            (corrected_by, now, connection_id),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def retract_connection(connection_id, reason, corrected_by="human"):
    """Retract a connection without deleting its edge or provenance."""
    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        if connection["verification_status"] == "retracted":
            db.rollback()
            return False
        _record_connection_correction(
            db,
            connection_id,
            "verification_status",
            connection["verification_status"],
            "retracted",
            reason,
            corrected_by,
            correction_type="retraction",
        )
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            UPDATE connections
            SET verification_status='retracted', verified_by=?, verified_at=?
            WHERE id=?
        """,
            (corrected_by, now, connection_id),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def correct_connection(
    connection_id,
    field,
    new_value,
    reason,
    *,
    correction_type="refinement",
    corrected_by="human",
):
    """Correct an auditable connection field while preserving canonical endpoints."""
    if field not in ALLOWED_CONNECTION_CORRECT_FIELDS:
        raise ValueError(
            f"Cannot correct connection field '{field}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_CONNECTION_CORRECT_FIELDS))}. "
            "Endpoint corrections require retracting this edge and creating a new canonical edge."
        )
    if field == "relationship_type" and new_value not in VALID_RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported relationship_type '{new_value}'")
    if field == "strength" and new_value not in VALID_STRENGTHS:
        raise ValueError(f"Unsupported strength '{new_value}'")
    if field == "finding_id":
        new_value = None if new_value in (None, "") else int(new_value)
    elif new_value == "":
        new_value = None

    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        connection = db.execute(
            "SELECT * FROM connections WHERE id=?", (connection_id,)
        ).fetchone()
        if connection is None:
            raise ValueError(f"Connection #{connection_id} does not exist")
        if field == "finding_id" and new_value is not None:
            if not db.execute(
                "SELECT 1 FROM findings WHERE id=?", (new_value,)
            ).fetchone():
                raise ValueError(f"Finding #{new_value} does not exist")
        old_value = connection[field]
        if old_value == new_value:
            db.rollback()
            return False
        _record_connection_correction(
            db,
            connection_id,
            field,
            old_value,
            new_value,
            reason,
            corrected_by,
            correction_type,
        )
        db.execute(
            f"UPDATE connections SET {field}=? WHERE id=?",
            (new_value, connection_id),
        )
        _invalidate_verified_connection(db, connection, reason, corrected_by)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_unverified_connections(limit=50, profile_id=None, all_profiles=False):
    """Return unverified connections with their attached evidence refs."""
    db = _get_db_standalone()
    try:
        conditions = ["COALESCE(c.verification_status, 'unverified')='unverified'"]
        params = []
        resolved_profile = _resolve_profile(profile_id, all_profiles)
        if resolved_profile:
            conditions.append("c.profile_id=?")
            params.append(resolved_profile)
        where = " AND ".join(conditions)
        rows = db.execute(
            f"""
            SELECT c.*, GROUP_CONCAT(ce.evidence_ref, ', ') AS evidence_refs
            FROM connections c
            LEFT JOIN connection_evidence ce ON ce.connection_id=c.id
            WHERE {where}
            GROUP BY c.id
            ORDER BY c.created_at DESC, c.id DESC
            LIMIT ?
        """,
            params + [limit],
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def add_connection(
    person_a,
    person_b,
    relationship_type=None,
    description=None,
    evidence_ids=None,
    strength="medium",
    date_range=None,
    finding_id=None,
    profile_id=None,
    agent_run_id=None,
    source_quotes=None,
    entity_a_type="unknown",
    entity_b_type="unknown",
):
    """Add a connection between two persons/entities.

    Both endpoints are auto-registered in the entities table if not already present
    (see _ensure_entity). Pass entity_a_type/entity_b_type to give freshly-created
    stubs a real type instead of 'unknown'.
    """
    if agent_run_id is None:
        agent_run_id = os.environ.get("ITHILDIN_AGENT_RUN_ID")
    if (
        relationship_type is not None
        and relationship_type not in VALID_RELATIONSHIP_TYPES
    ):
        raise ValueError(f"Unsupported relationship_type '{relationship_type}'")
    if strength not in VALID_STRENGTHS:
        raise ValueError(f"Unsupported strength '{strength}'")
    if evidence_ids is None:
        evidence_ids = []
    elif isinstance(evidence_ids, str) or not isinstance(evidence_ids, (list, tuple)):
        raise ValueError("evidence_ids must be a list of evidence references")
    if source_quotes is not None and not isinstance(source_quotes, dict):
        raise ValueError(
            "source_quotes must map each evidence_ref to provenance metadata"
        )
    source_quotes = source_quotes or {}
    unknown_metadata_refs = set(source_quotes) - set(evidence_ids)
    if unknown_metadata_refs:
        raise ValueError(
            "Evidence metadata supplied for refs not present in evidence_ids: "
            + ", ".join(sorted(unknown_metadata_refs))
        )
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("evidence_ids contains duplicate references")
    evidence_rows = []
    for ref in evidence_ids:
        metadata = source_quotes.get(ref) or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"source_quotes['{ref}'] must be a metadata mapping")
        metadata = {
            "quote": metadata.get("quote") or None,
            "page": metadata.get("page") or None,
            "assessment": metadata.get("assessment") or None,
        }
        evidence_type = _validate_evidence_payload(ref, metadata["quote"])
        evidence_rows.append((str(ref).strip(), evidence_type, metadata))

    # Auto-detect profile_id from active investigation if not provided
    if profile_id is None:
        profile_id = _detect_active_profile()

    db = _get_db_standalone()
    try:
        db.execute("BEGIN IMMEDIATE")
        # Enforce the invariant: every connection endpoint is backed by an entity row.
        # Done before the alphabetical swap so each name stays paired with its type.
        entity_a_id, _ = _ensure_entity(db, person_a, entity_a_type, agent_run_id=agent_run_id)
        entity_b_id, _ = _ensure_entity(db, person_b, entity_b_type, agent_run_id=agent_run_id)
        if entity_a_id is None or entity_b_id is None:
            raise ValueError("Connections require two non-empty entity endpoints")
        person_a = db.execute("SELECT name FROM entities WHERE id=?", (entity_a_id,)).fetchone()["name"]
        person_b = db.execute("SELECT name FROM entities WHERE id=?", (entity_b_id,)).fetchone()["name"]

        # Symmetric relationships use canonical endpoint ordering for dedup.
        # Directional verbs must retain caller order or their meaning reverses.
        if (
            relationship_type not in DIRECTIONAL_RELATIONSHIP_TYPES
            and person_a > person_b
        ):
            person_a, person_b = person_b, person_a

        insert_cursor = db.execute(
            """
            INSERT OR IGNORE INTO connections (person_a, person_b, relationship_type, description,
                                    strength, date_range, finding_id, profile_id, agent_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                person_a,
                person_b,
                relationship_type,
                description,
                strength,
                date_range,
                finding_id,
                profile_id,
                agent_run_id,
            ),
        )
        connection_created = insert_cursor.rowcount == 1

        # INSERT OR IGNORE does not reset cursor.lastrowid when the row already
        # exists. Endpoint registration above may therefore leave lastrowid set
        # to an unrelated entity ID. Always resolve the canonical connection by
        # the same key enforced by idx_connections_unique before writing evidence.
        existing = db.execute(
            """
            SELECT * FROM connections
            WHERE person_a = ? AND person_b = ?
              AND COALESCE(relationship_type, '') = COALESCE(?, '')
              AND COALESCE(profile_id, '') = COALESCE(?, '')
        """,
            (person_a, person_b, relationship_type, profile_id),
        ).fetchone()
        if existing is None:
            raise sqlite3.IntegrityError(
                "connection insert did not resolve a canonical row"
            )
        conn_id = existing["id"]
        evidence_changed = False
        audit_actor = agent_run_id or "findings_tracker:connect"
        audit_reason = "Connection evidence enriched via idempotent connect"

        for evidence_ref, evidence_type, metadata in evidence_rows:
            current = db.execute(
                "SELECT * FROM connection_evidence "
                "WHERE connection_id=? AND evidence_ref=?",
                (conn_id, evidence_ref),
            ).fetchone()
            if current is None:
                cursor = db.execute(
                    """
                    INSERT OR IGNORE INTO connection_evidence (
                        connection_id, evidence_type, evidence_ref,
                        source_quote, source_page, assessment
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        conn_id,
                        evidence_type,
                        evidence_ref,
                        metadata["quote"],
                        metadata["page"],
                        metadata["assessment"],
                    ),
                )
                if cursor.rowcount == 1:
                    evidence_changed = True
                    if not connection_created:
                        snapshot = {
                            "evidence_type": evidence_type,
                            "evidence_ref": evidence_ref,
                            "source_quote": metadata["quote"],
                            "source_page": metadata["page"],
                            "assessment": metadata["assessment"],
                        }
                        _record_connection_evidence_correction(
                            db,
                            conn_id,
                            evidence_ref,
                            "__row__",
                            None,
                            snapshot,
                            audit_reason,
                            audit_actor,
                        )
                    continue
                current = db.execute(
                    "SELECT * FROM connection_evidence "
                    "WHERE connection_id=? AND evidence_ref=?",
                    (conn_id, evidence_ref),
                ).fetchone()

            for metadata_key, column in (
                ("quote", "source_quote"),
                ("page", "source_page"),
                ("assessment", "assessment"),
            ):
                incoming = metadata[metadata_key]
                if incoming is None:
                    continue
                stored = current[column]
                if stored == incoming:
                    continue
                if stored is not None:
                    raise ValueError(
                        f"Connection #{conn_id} evidence '{evidence_ref}' already has a "
                        f"different {column}; use connection-evidence-correct with an audit reason"
                    )
                db.execute(
                    f"UPDATE connection_evidence SET {column}=? "
                    "WHERE connection_id=? AND evidence_ref=?",
                    (incoming, conn_id, evidence_ref),
                )
                _record_connection_evidence_correction(
                    db,
                    conn_id,
                    evidence_ref,
                    column,
                    stored,
                    incoming,
                    audit_reason,
                    audit_actor,
                )
                evidence_changed = True

        if not connection_created and evidence_changed:
            _invalidate_verified_connection(db, existing, audit_reason, audit_actor)

        db.commit()
        return conn_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_connections(
    person,
    depth=1,
    relationship_type=None,
    profile_id=None,
    all_profiles=False,
    verification_status=None,
):
    """Get all connections for a person, optionally multi-hop."""
    db = _get_db_standalone()
    resolved_profile = _resolve_profile(profile_id, all_profiles)

    visited = set()
    current_layer = {person.lower()}
    all_connections = []

    for _ in range(depth):
        if not current_layer:
            break

        placeholders = ",".join("?" for _ in current_layer)
        conditions = [
            f"(LOWER(person_a) IN ({placeholders}) OR LOWER(person_b) IN ({placeholders}))"
        ]
        params = list(current_layer) + list(current_layer)

        if relationship_type:
            conditions.append("relationship_type = ?")
            params.append(relationship_type)
        if resolved_profile:
            conditions.append("profile_id = ?")
            params.append(resolved_profile)
        if verification_status:
            conditions.append("verification_status = ?")
            params.append(verification_status)

        where = " AND ".join(conditions)
        rows = db.execute(f"SELECT * FROM connections WHERE {where}", params).fetchall()

        next_layer = set()
        for row in rows:
            if verification_status == "verified":
                try:
                    validate_connection_publication(db, row)
                except ValueError:
                    continue
            conn = dict(row)
            conn_key = (
                conn["person_a"],
                conn["person_b"],
                conn.get("relationship_type"),
            )
            if conn_key not in visited:
                visited.add(conn_key)
                all_connections.append(conn)
                next_layer.add(conn["person_a"].lower())
                next_layer.add(conn["person_b"].lower())

        current_layer = next_layer - {n for n in current_layer}

    db.close()
    return all_connections


def get_timeline(
    target=None,
    start_date=None,
    end_date=None,
    limit=100,
    profile_id=None,
    all_profiles=False,
):
    """Get findings ordered by event date."""
    db = _get_db_standalone()
    conditions = ["date_of_event IS NOT NULL AND date_of_event != ''"]
    params = []

    resolved_profile = _resolve_profile(profile_id, all_profiles)
    if resolved_profile:
        conditions.append("profile_id = ?")
        params.append(resolved_profile)

    if target:
        conditions.append("target_name LIKE ?")
        params.append(f"%{target}%")
    if start_date:
        conditions.append("date_of_event >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date_of_event <= ?")
        params.append(end_date)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = db.execute(
        f"SELECT * FROM findings {where} ORDER BY date_of_event LIMIT ?",
        params + [limit],
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_stats(profile_id=None, all_profiles=False):
    """Findings and connections statistics."""
    db = _get_db_standalone()
    resolved_profile = _resolve_profile(profile_id, all_profiles)
    stats = {}

    f_where = "WHERE profile_id = ?" if resolved_profile else ""
    c_where = "WHERE profile_id = ?" if resolved_profile else ""
    f_params = [resolved_profile] if resolved_profile else []
    c_params = [resolved_profile] if resolved_profile else []

    stats["total_findings"] = db.execute(
        f"SELECT COUNT(*) FROM findings {f_where}", f_params
    ).fetchone()[0]
    stats["total_connections"] = db.execute(
        f"SELECT COUNT(*) FROM connections {c_where}", c_params
    ).fetchone()[0]
    if resolved_profile:
        stats["profile_id"] = resolved_profile

    rows = db.execute(
        f"SELECT finding_type, COUNT(*) as cnt FROM findings {f_where} GROUP BY finding_type",
        f_params,
    ).fetchall()
    stats["by_type"] = {r["finding_type"]: r["cnt"] for r in rows}

    rows = db.execute(
        f"SELECT confidence, COUNT(*) as cnt FROM findings {f_where} GROUP BY confidence",
        f_params,
    ).fetchall()
    stats["by_confidence"] = {r["confidence"]: r["cnt"] for r in rows}

    rows = db.execute(
        f"SELECT target_name, COUNT(*) as cnt FROM findings {f_where} GROUP BY target_name ORDER BY cnt DESC LIMIT 20",
        f_params,
    ).fetchall()
    stats["top_targets"] = {r["target_name"]: r["cnt"] for r in rows}

    rows = db.execute(
        f"SELECT relationship_type, COUNT(*) as cnt FROM connections {c_where} GROUP BY relationship_type",
        c_params,
    ).fetchall()
    stats["connection_types"] = {r["relationship_type"]: r["cnt"] for r in rows}

    db.close()
    return stats


# ── CLI ──────────────────────────────────────────────────────


def format_finding(finding, verbose=False):
    conf_markers = {
        "confirmed": "[+++]",
        "high": "[++ ]",
        "medium": "[+  ]",
        "low": "[   ]",
        "unverified": "[?  ]",
    }
    verif_markers = {
        "verified": "V",
        "unverified": "?",
        "disputed": "D",
        "retracted": "X",
    }
    conf = conf_markers.get(finding["confidence"], "[?  ]")
    verif = verif_markers.get(finding.get("verification_status", "unverified"), "?")
    ftype = finding.get("finding_type") or "?"
    date = finding.get("date_of_event", "")
    date_str = f" ({date})" if date else ""
    line = f"{conf}{verif} #{finding['id']:>4} [{ftype:>13}] {finding['target_name']}: {finding['summary']}{date_str}"

    if verbose:
        if finding.get("claim_type"):
            line += f"\n       Claim type: {finding['claim_type']}"
        if finding.get("verification_status"):
            line += f"\n       Verification: {finding['verification_status']}"
            if finding.get("verified_by"):
                line += f" (by {finding['verified_by']} at {finding.get('verified_at', '?')})"
        if finding.get("detail"):
            line += f"\n       Detail: {finding['detail'][:300]}"
        if finding.get("evidence"):
            for ev in finding["evidence"]:
                line += (
                    f"\n       Evidence [{ev['evidence_type']}]: {ev['evidence_ref']}"
                )
                if ev.get("source_quote"):
                    line += f'\n         Quote: "{ev["source_quote"][:200]}"'
                if ev.get("source_page"):
                    line += f" (at {ev['source_page']})"
                if ev.get("assessment"):
                    line += f"\n         Assessment: {ev['assessment']}"
        if finding.get("source_datasets"):
            line += f"\n       Sources: {finding['source_datasets']}"
        if finding.get("lead_id"):
            line += f"\n       From lead: #{finding['lead_id']}"
        if finding.get("corrections"):
            line += f"\n       Corrections: {len(finding['corrections'])} recorded"
            for c in finding["corrections"]:
                line += f"\n         [{c['created_at']}] {c['correction_type']}: {c['field_name']} — {c['reason']}"

    return line


def format_connection(conn):
    strength_markers = {
        "strong": "===",
        "medium": "---",
        "weak": "- -",
        "circumstantial": "...",
    }
    verification_markers = {
        "verified": "V",
        "unverified": "?",
        "disputed": "D",
        "retracted": "X",
    }
    marker = strength_markers.get(conn["strength"], "---")
    rtype = conn.get("relationship_type", "?")
    connection_status = conn.get("verification_status", "unverified")
    verification = verification_markers.get(connection_status, "?")
    return (
        f"  [{verification}] #{conn.get('id', '?')} {conn['person_a']} "
        f"{marker}[{rtype}]{marker} {conn['person_b']} ({connection_status})"
    )


def main():
    parser = argparse.ArgumentParser(description="OSINT investigation findings tracker")
    subparsers = parser.add_subparsers(dest="command")

    # add
    add_p = subparsers.add_parser("add", help="Add an unverified finding with quoted evidence")
    add_p.add_argument("--target", required=True)
    add_p.add_argument("--summary", "-s", required=True)
    add_p.add_argument("--type", "-t", choices=VALID_FINDING_TYPES, dest="finding_type")
    add_p.add_argument("--detail", "-d")
    add_p.add_argument("--evidence", "-e", nargs="+", help="Source references required for every new finding")
    add_p.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help=(
            "Canonical provenance tokens. Run 'findings_tracker.py sources' "
            "for the registry; use official_website for one-off first-party pages."
        ),
    )
    add_p.add_argument("--confidence", "-c", choices=VALID_CONFIDENCE, default="medium")
    add_p.add_argument("--date")
    add_p.add_argument("--lead-id", type=int)
    add_p.add_argument("--claim-type", choices=VALID_CLAIM_TYPES, default="inference")
    add_p.add_argument(
        "--source-quote",
        nargs="+",
        action="extend",
        help=(
            "Required ref:quote pairs (repeatable). Each evidence ref needs one quote; "
            "combine multiple excerpts explicitly."
        ),
    )
    add_p.add_argument("--thread-id", type=int, help="Investigation thread ID")
    add_p.add_argument(
        "--email-sender", help="Email sender for EFTA evidence (e.g. 'Jeffrey Epstein')"
    )
    add_p.add_argument(
        "--profile", help="Investigation profile ID (auto-detected if omitted)"
    )
    add_output_args(add_p)

    sources_p = subparsers.add_parser(
        "sources",
        help="List canonical provenance tokens and compatibility aliases",
    )
    add_output_args(sources_p)

    # list
    list_p = subparsers.add_parser("list", help="List findings")
    list_p.add_argument("--target")
    list_p.add_argument("--type", choices=VALID_FINDING_TYPES, dest="finding_type")
    list_p.add_argument("--confidence", choices=VALID_CONFIDENCE)
    list_p.add_argument("--thread-id", type=int, help="Filter by investigation thread")
    list_p.add_argument("--limit", type=int, default=50)
    list_p.add_argument("-v", "--verbose", action="store_true")
    list_p.add_argument("--profile", help="Investigation profile (default: active)")
    list_p.add_argument(
        "--all-profiles", action="store_true", help="Include all profiles"
    )
    add_output_args(list_p)

    # show
    show_p = subparsers.add_parser("show", help="Show finding details")
    show_p.add_argument("id", type=int)
    add_output_args(show_p)

    # audited finding-evidence CRUD
    evidence_add_p = subparsers.add_parser(
        "evidence-add", help="Add finding evidence with an immutable audit entry"
    )
    evidence_add_p.add_argument("id", type=int, help="Finding ID")
    evidence_add_p.add_argument("--ref", required=True, dest="evidence_ref")
    evidence_add_p.add_argument("--source-quote")
    evidence_add_p.add_argument("--source-page")
    evidence_add_p.add_argument("--assessment")
    evidence_add_p.add_argument("--email-sender")
    evidence_add_p.add_argument("--email-date")
    evidence_add_p.add_argument("--chain-position", type=int)
    evidence_add_p.add_argument("--reason", "-r", required=True)
    evidence_add_p.add_argument("--by", default="human")

    evidence_correct_p = subparsers.add_parser(
        "evidence-correct",
        help="Correct finding evidence with an immutable audit entry",
    )
    evidence_correct_p.add_argument("id", type=int, help="Finding ID")
    evidence_correct_p.add_argument("--ref", required=True, dest="evidence_ref")
    evidence_correct_p.add_argument(
        "--field", "-f", required=True, choices=sorted(EVIDENCE_CORRECT_FIELDS)
    )
    evidence_correct_p.add_argument(
        "--value",
        "-v",
        required=True,
        help="Replacement value; use an empty string to clear nullable metadata",
    )
    evidence_correct_p.add_argument("--reason", "-r", required=True)
    evidence_correct_p.add_argument(
        "--correction-type", choices=VALID_CORRECTION_TYPES, default="refinement"
    )
    evidence_correct_p.add_argument("--by", default="human")

    evidence_delete_p = subparsers.add_parser(
        "evidence-delete",
        help="Delete finding evidence while retaining its audit snapshot",
    )
    evidence_delete_p.add_argument("id", type=int, help="Finding ID")
    evidence_delete_p.add_argument("--ref", required=True, dest="evidence_ref")
    evidence_delete_p.add_argument("--reason", "-r", required=True)
    evidence_delete_p.add_argument("--by", default="human")

    evidence_audit_p = subparsers.add_parser(
        "evidence-audit",
        help="Report provenance violations without modifying findings or evidence",
    )
    evidence_audit_p.add_argument("--finding-id", type=int)
    evidence_audit_p.add_argument(
        "--profile", help="Investigation profile (default: active)"
    )
    evidence_audit_p.add_argument("--all-profiles", action="store_true")
    add_output_args(evidence_audit_p)

    # connect
    conn_p = subparsers.add_parser(
        "connect",
        help="Add a connection between any two nodes (persons, orgs, programs)",
    )
    conn_p.add_argument("--person-a", "--node-a", "-a", required=True)
    conn_p.add_argument("--person-b", "--node-b", "-b", required=True)
    conn_p.add_argument("--type", choices=VALID_RELATIONSHIP_TYPES, dest="rel_type")
    conn_p.add_argument("--description", "-d")
    conn_p.add_argument("--evidence", "-e", nargs="+")
    conn_p.add_argument(
        "--source-quote",
        nargs="+",
        action="extend",
        help="repeatable ref:quote pairs; one combined quote per evidence ref",
    )
    conn_p.add_argument(
        "--source-page",
        nargs="+",
        action="extend",
        help="ref:page/location pairs for connection evidence",
    )
    conn_p.add_argument(
        "--assessment",
        nargs="+",
        action="extend",
        help="ref:assessment pairs explaining how evidence supports the edge",
    )
    conn_p.add_argument("--strength", choices=VALID_STRENGTHS, default="medium")
    conn_p.add_argument("--date-range")
    conn_p.add_argument("--finding-id", type=int)
    conn_p.add_argument(
        "--profile", help="Investigation profile ID (auto-detected if omitted)"
    )
    conn_p.add_argument(
        "--entity-a-type",
        choices=VALID_ENTITY_TYPES,
        default="unknown",
        help="Type for endpoint A if auto-registered as a new entity",
    )
    conn_p.add_argument(
        "--entity-b-type",
        choices=VALID_ENTITY_TYPES,
        default="unknown",
        help="Type for endpoint B if auto-registered as a new entity",
    )

    connection_evidence_add_p = subparsers.add_parser(
        "connection-evidence-add",
        help="Add connection evidence with an immutable audit entry",
    )
    connection_evidence_add_p.add_argument("id", type=int, help="Connection ID")
    connection_evidence_add_p.add_argument("--ref", required=True, dest="evidence_ref")
    connection_evidence_add_p.add_argument("--source-quote")
    connection_evidence_add_p.add_argument("--source-page")
    connection_evidence_add_p.add_argument("--assessment")
    connection_evidence_add_p.add_argument("--reason", "-r", required=True)
    connection_evidence_add_p.add_argument("--by", default="human")

    connection_evidence_correct_p = subparsers.add_parser(
        "connection-evidence-correct",
        help="Correct connection evidence with an immutable audit entry",
    )
    connection_evidence_correct_p.add_argument("id", type=int, help="Connection ID")
    connection_evidence_correct_p.add_argument(
        "--ref", required=True, dest="evidence_ref"
    )
    connection_evidence_correct_p.add_argument(
        "--field",
        "-f",
        required=True,
        choices=sorted(CONNECTION_EVIDENCE_CORRECT_FIELDS),
    )
    connection_evidence_correct_p.add_argument(
        "--value",
        "-v",
        required=True,
        help="Replacement value; use an empty string to clear nullable metadata",
    )
    connection_evidence_correct_p.add_argument("--reason", "-r", required=True)
    connection_evidence_correct_p.add_argument(
        "--correction-type", choices=VALID_CORRECTION_TYPES, default="refinement"
    )
    connection_evidence_correct_p.add_argument("--by", default="human")

    connection_evidence_delete_p = subparsers.add_parser(
        "connection-evidence-delete",
        help="Delete connection evidence while retaining its audit snapshot",
    )
    connection_evidence_delete_p.add_argument("id", type=int, help="Connection ID")
    connection_evidence_delete_p.add_argument(
        "--ref", required=True, dest="evidence_ref"
    )
    connection_evidence_delete_p.add_argument("--reason", "-r", required=True)
    connection_evidence_delete_p.add_argument("--by", default="human")

    connection_verify_p = subparsers.add_parser(
        "connection-verify", help="Verify a connection after provenance validation"
    )
    connection_verify_p.add_argument("id", type=int)
    connection_verify_p.add_argument("--by", default="human")

    connection_dispute_p = subparsers.add_parser(
        "connection-dispute", help="Mark a connection disputed with an audit reason"
    )
    connection_dispute_p.add_argument("id", type=int)
    connection_dispute_p.add_argument("--reason", "-r", required=True)
    connection_dispute_p.add_argument("--by", default="human")

    connection_retract_p = subparsers.add_parser(
        "connection-retract", help="Retract a connection without deleting provenance"
    )
    connection_retract_p.add_argument("id", type=int)
    connection_retract_p.add_argument("--reason", "-r", required=True)
    connection_retract_p.add_argument("--by", default="human")

    connection_correct_p = subparsers.add_parser(
        "connection-correct", help="Correct an auditable connection field"
    )
    connection_correct_p.add_argument("id", type=int)
    connection_correct_p.add_argument(
        "--field",
        "-f",
        required=True,
        choices=sorted(ALLOWED_CONNECTION_CORRECT_FIELDS),
    )
    connection_correct_p.add_argument("--value", "-v", required=True)
    connection_correct_p.add_argument("--reason", "-r", required=True)
    connection_correct_p.add_argument(
        "--correction-type", choices=VALID_CORRECTION_TYPES, default="refinement"
    )
    connection_correct_p.add_argument("--by", default="human")

    connection_audit_p = subparsers.add_parser(
        "connection-audit", help="Show connection and connection-evidence corrections"
    )
    connection_audit_p.add_argument("id", type=int)
    connection_audit_p.add_argument("--record-key", help="Optional evidence_ref filter")
    connection_audit_p.add_argument("--limit", type=int, default=50)
    add_output_args(connection_audit_p)

    connection_provenance_p = subparsers.add_parser(
        "connection-provenance", help="Show the full provenance chain for a connection"
    )
    connection_provenance_p.add_argument("id", type=int)
    add_output_args(connection_provenance_p)

    connection_unverified_p = subparsers.add_parser(
        "connection-unverified", help="List connections awaiting verification"
    )
    connection_unverified_p.add_argument("--limit", type=int, default=50)
    connection_unverified_p.add_argument("--profile", help="Profile (default: active)")
    connection_unverified_p.add_argument("--all-profiles", action="store_true")
    add_output_args(connection_unverified_p)

    # connections
    conns_p = subparsers.add_parser(
        "connections", help="Get connections for a node (person, org, or program)"
    )
    conns_p.add_argument("person", metavar="NODE")
    conns_p.add_argument("--depth", type=int, default=1)
    conns_p.add_argument("--type", choices=VALID_RELATIONSHIP_TYPES, dest="rel_type")
    conns_p.add_argument("--profile", help="Investigation profile (default: active)")
    conns_p.add_argument(
        "--all-profiles", action="store_true", help="Include all profiles"
    )
    conns_p.add_argument(
        "--verified-only",
        action="store_true",
        help="Publication view: include only evidence-validated verified edges",
    )
    add_output_args(conns_p)

    # search
    search_p = subparsers.add_parser("search", help="Full-text search")
    search_p.add_argument("query", nargs="?", help="Finding text to search")
    search_p.add_argument(
        "--query",
        dest="query_option",
        help="Finding text to search (compatibility form)",
    )
    search_p.add_argument(
        "--thread-id", type=int, help="Filter by investigation thread"
    )
    search_p.add_argument("--profile", help="Investigation profile (default: active)")
    search_p.add_argument(
        "--all-profiles", action="store_true", help="Include all profiles"
    )
    search_p.add_argument("--limit", type=int, default=30, help="Maximum results")
    add_output_args(search_p)

    # timeline
    tl_p = subparsers.add_parser("timeline", help="Timeline of findings")
    tl_p.add_argument("--target")
    tl_p.add_argument("--start")
    tl_p.add_argument("--end")
    tl_p.add_argument("--limit", type=int, default=100)
    tl_p.add_argument("--profile", help="Investigation profile (default: active)")
    tl_p.add_argument(
        "--all-profiles", action="store_true", help="Include all profiles"
    )
    add_output_args(tl_p)

    # verify
    verify_p = subparsers.add_parser("verify", help="Mark finding as verified")
    verify_p.add_argument("id", type=int)
    verify_p.add_argument("--by", default="human", help="Who verified (default: human)")

    # dispute
    dispute_p = subparsers.add_parser("dispute", help="Mark finding as disputed")
    dispute_p.add_argument("id", type=int)
    dispute_p.add_argument("--reason", "-r", required=True)
    dispute_p.add_argument("--by", default="human")
    dispute_p.add_argument(
        "--contradicted-by",
        type=int,
        metavar="FINDING_ID",
        help="Record a structured 'contradicts' relation to this finding",
    )

    # relate — typed finding-to-finding relation (claim graph)
    relate_p = subparsers.add_parser(
        "relate", help="Record a typed relation between two findings"
    )
    relate_p.add_argument("from_id", type=int)
    relate_p.add_argument("to_id", type=int)
    relate_p.add_argument(
        "--type",
        "--relation-type",
        "-t",
        required=True,
        dest="relation_type",
        choices=[
            "contradicts",
            "corroborates",
            "supersedes",
            "duplicates",
            "refines",
            "depends_on",
        ],
    )
    relate_p.add_argument("--assessment", "-a", help="Why the relation holds")
    relate_p.add_argument("--by", default="human")

    relation_delete_p = subparsers.add_parser(
        "relation-delete",
        aliases=["unrelate"],
        help="Delete one finding relation while retaining an audit snapshot",
    )
    relation_delete_p.add_argument("from_id", type=int)
    relation_delete_p.add_argument("to_id", type=int)
    relation_delete_p.add_argument(
        "--type",
        "-t",
        required=True,
        dest="relation_type",
        choices=[
            "contradicts",
            "corroborates",
            "supersedes",
            "duplicates",
            "refines",
            "depends_on",
        ],
    )
    relation_delete_p.add_argument("--reason", "-r", required=True)
    relation_delete_p.add_argument("--by", default="human")

    # retract
    retract_p = subparsers.add_parser(
        "retract", help="Retract a finding (cascades to connections)"
    )
    retract_p.add_argument("id", type=int)
    retract_p.add_argument("--reason", "-r", required=True)
    retract_p.add_argument("--by", default="human")

    # correct
    correct_p = subparsers.add_parser(
        "correct", help="Correct a field with audit trail"
    )
    correct_p.add_argument("id", type=int)
    correct_p.add_argument(
        "--field",
        "-f",
        required=True,
        choices=sorted(ALLOWED_CORRECT_FIELDS),
        help="Finding field to correct",
    )
    correct_p.add_argument(
        "--value",
        "-v",
        required=True,
        help=(
            "New value; source_datasets requires a JSON array such as "
            "'[\"courtlistener\"]'"
        ),
    )
    correct_p.add_argument(
        "--reason", "-r", required=True, help="Why the correction was needed"
    )
    correct_p.add_argument(
        "--correction-type", choices=VALID_CORRECTION_TYPES, default="refinement"
    )
    correct_p.add_argument("--by", default="human")

    # audit
    audit_p = subparsers.add_parser("audit", help="Show correction history")
    audit_p.add_argument("id", type=int, nargs="?", help="Finding ID (omit for all)")
    audit_p.add_argument("--table", default="findings")
    audit_p.add_argument(
        "--record-key",
        help="Composite child-row key (for finding_evidence, the evidence_ref)",
    )
    audit_p.add_argument("--correction-type", choices=VALID_CORRECTION_TYPES)
    audit_p.add_argument("--limit", type=int, default=50)
    add_output_args(audit_p)

    # provenance
    prov_p = subparsers.add_parser(
        "provenance", help="Show full provenance chain for a finding"
    )
    prov_p.add_argument("id", type=int)
    add_output_args(prov_p)

    # unverified
    unverified_p = subparsers.add_parser("unverified", help="List unverified findings")
    unverified_p.add_argument("--limit", type=int, default=50)
    unverified_p.add_argument("--profile", help="Profile (default: active)")
    unverified_p.add_argument("--all-profiles", action="store_true")
    add_output_args(unverified_p)

    # stats
    stats_p = subparsers.add_parser("stats", help="Show statistics")
    stats_p.add_argument("--profile", help="Investigation profile (default: active)")
    stats_p.add_argument(
        "--all-profiles", action="store_true", help="Include all profiles"
    )
    add_output_args(stats_p)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    if args.command == "search":
        args.query = args.query_option or args.query
        if not args.query:
            parser.error("search requires QUERY or --query QUERY")

    if args.command == "sources":
        vocabulary = {
            "canonical": sorted(VALID_SOURCES),
            "aliases": dict(sorted(SOURCE_ALIASES.items())),
            "guidance": SOURCE_VOCABULARY_GUIDANCE,
        }
        if write_output(vocabulary, args, summary="source vocabulary"):
            return
        print("Canonical source tokens:")
        print("  " + "\n  ".join(vocabulary["canonical"]))
        print("\nCompatibility aliases:")
        for alias, canonical in vocabulary["aliases"].items():
            print(f"  {alias} -> {canonical}")
        print(f"\n{SOURCE_VOCABULARY_GUIDANCE}")

    elif args.command == "add":
        try:
            # Parse source quotes from CLI (format: "ref:quote text")
            source_quotes = (
                _parse_source_quote_args(
                    getattr(args, "source_quote", None),
                    getattr(args, "evidence", None),
                )
                or None
            )
            fid = add_finding(
                target_name=args.target,
                summary=args.summary,
                finding_type=args.finding_type,
                detail=args.detail,
                evidence_ids=args.evidence,
                source_datasets=args.sources,
                confidence=args.confidence,
                date_of_event=args.date,
                lead_id=args.lead_id,
                claim_type=getattr(args, "claim_type", "inference"),
                source_quotes=source_quotes,
                thread_id=getattr(args, "thread_id", None),
                email_sender=getattr(args, "email_sender", None),
                profile_id=getattr(args, "profile", None),
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        created = {"id": fid, "target_name": args.target, "summary": args.summary}
        if not write_output(created, args, summary=f"created finding #{fid}"):
            if getattr(args, "json_out", False):
                print(json.dumps(created, indent=2))
            else:
                print(f"Created finding #{fid}: {args.target} - {args.summary}")

    elif args.command == "list":
        findings = list_findings(
            target=args.target,
            finding_type=args.finding_type,
            confidence=args.confidence,
            limit=args.limit,
            thread_id=getattr(args, "thread_id", None),
            profile_id=getattr(args, "profile", None),
            all_profiles=getattr(args, "all_profiles", False),
        )
        if not write_output(
            findings, args, summary=f"findings list: {len(findings)} results"
        ):
            if not findings:
                print("No findings match filters.")
            else:
                for f in findings:
                    print(format_finding(f, verbose=args.verbose))

    elif args.command == "show":
        finding = get_finding(args.id)
        if not finding:
            print(f"Finding #{args.id} not found.")
            sys.exit(1)
        if not write_output(finding, args, summary=f"finding #{args.id}"):
            print(format_finding(finding, verbose=True))
            if finding.get("connections"):
                print("\n  Connections:")
                for c in finding["connections"]:
                    print(format_connection(c))

    elif args.command == "evidence-add":
        try:
            add_finding_evidence(
                args.id,
                args.evidence_ref,
                source_quote=args.source_quote,
                source_page=args.source_page,
                assessment=args.assessment,
                email_sender=args.email_sender,
                email_date=args.email_date,
                chain_position=args.chain_position,
                reason=args.reason,
                corrected_by=args.by,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Added evidence to finding #{args.id}: {args.evidence_ref}")

    elif args.command == "evidence-correct":
        try:
            correct_finding_evidence(
                args.id,
                args.evidence_ref,
                args.field,
                args.value,
                reason=args.reason,
                correction_type=args.correction_type,
                corrected_by=args.by,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(
            f"Corrected evidence on finding #{args.id}: "
            f"{args.evidence_ref}.{args.field}"
        )

    elif args.command == "evidence-delete":
        try:
            delete_finding_evidence(
                args.id, args.evidence_ref, reason=args.reason, corrected_by=args.by
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Deleted evidence from finding #{args.id}: {args.evidence_ref}")

    elif args.command == "evidence-audit":
        try:
            report = audit_finding_evidence(
                finding_id=args.finding_id,
                profile_id=args.profile,
                all_profiles=args.all_profiles,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        summary = (
            f"finding evidence audit: {report['issue_count']} issues across "
            f"{report['findings_scanned']} findings"
        )
        if not write_output(report, args, summary=summary):
            print("Finding evidence audit (REPORT ONLY — no data changed)")
            print(
                f"  Findings: {report['findings_scanned']}  "
                f"Evidence: {report['evidence_scanned']}  Issues: {report['issue_count']}"
            )
            spans = report["span_checks"]
            print(
                "  Quote spans: "
                f"matched={spans['matched']} mismatch={spans['mismatch']} "
                f"unchecked={spans['unchecked']} missing={spans['missing']}"
            )
            for item in report["issues"]:
                ref = f" [{item['evidence_ref']}]" if item.get("evidence_ref") else ""
                print(
                    f"  {item['severity'].upper()} finding #{item['finding_id']}{ref} "
                    f"{item['code']}: {item['message']}"
                )

    elif args.command == "connect":
        try:
            evidence_metadata = _merge_evidence_metadata(
                args.evidence,
                _parse_evidence_field_args(args.source_quote, args.evidence, "quote"),
                _parse_evidence_field_args(args.source_page, args.evidence, "page"),
                _parse_evidence_field_args(
                    args.assessment, args.evidence, "assessment"
                ),
            )
            cid = add_connection(
                person_a=args.person_a,
                person_b=args.person_b,
                relationship_type=args.rel_type,
                description=args.description,
                evidence_ids=args.evidence,
                strength=args.strength,
                date_range=args.date_range,
                finding_id=args.finding_id,
                profile_id=getattr(args, "profile", None),
                source_quotes=evidence_metadata,
                entity_a_type=getattr(args, "entity_a_type", "unknown"),
                entity_b_type=getattr(args, "entity_b_type", "unknown"),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Created connection #{cid}: {args.person_a} <-> {args.person_b}")

    elif args.command == "connection-evidence-add":
        try:
            add_connection_evidence(
                args.id,
                args.evidence_ref,
                source_quote=args.source_quote,
                source_page=args.source_page,
                assessment=args.assessment,
                reason=args.reason,
                corrected_by=args.by,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Added evidence to connection #{args.id}: {args.evidence_ref}")

    elif args.command == "connection-evidence-correct":
        try:
            changed = correct_connection_evidence(
                args.id,
                args.evidence_ref,
                args.field,
                args.value,
                reason=args.reason,
                correction_type=args.correction_type,
                corrected_by=args.by,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        if changed:
            print(
                f"Corrected connection #{args.id} evidence "
                f"{args.evidence_ref}.{args.field}"
            )
        else:
            print(
                f"Connection #{args.id} evidence {args.evidence_ref}.{args.field} "
                "already has that value"
            )

    elif args.command == "connection-evidence-delete":
        try:
            delete_connection_evidence(
                args.id, args.evidence_ref, reason=args.reason, corrected_by=args.by
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Deleted evidence from connection #{args.id}: {args.evidence_ref}")

    elif args.command == "connection-verify":
        try:
            changed = verify_connection(args.id, verified_by=args.by)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        if changed:
            print(f"Verified connection #{args.id}")
        else:
            print(f"Connection #{args.id} is already verified")

    elif args.command == "connection-dispute":
        try:
            changed = dispute_connection(args.id, args.reason, corrected_by=args.by)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        if changed:
            print(f"Disputed connection #{args.id}: {args.reason}")
        else:
            print(f"Connection #{args.id} is already disputed")

    elif args.command == "connection-retract":
        try:
            changed = retract_connection(args.id, args.reason, corrected_by=args.by)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        if changed:
            print(f"Retracted connection #{args.id}: {args.reason}")
        else:
            print(f"Connection #{args.id} is already retracted")

    elif args.command == "connection-correct":
        try:
            changed = correct_connection(
                args.id,
                args.field,
                args.value,
                args.reason,
                correction_type=args.correction_type,
                corrected_by=args.by,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        if changed:
            print(f"Corrected connection #{args.id}.{args.field}")
        else:
            print(f"Connection #{args.id}.{args.field} already has that value")

    elif args.command == "connection-audit":
        connection = get_connection(args.id)
        if connection is None:
            print(f"Connection #{args.id} not found.", file=sys.stderr)
            raise SystemExit(1)
        report = {
            "connection_id": args.id,
            "connection_corrections": (
                []
                if args.record_key
                else get_corrections(
                    table_name="connections", record_id=args.id, limit=args.limit
                )
            ),
            "evidence_corrections": get_corrections(
                table_name="connection_evidence",
                record_id=args.id,
                record_key=args.record_key,
                limit=args.limit,
            ),
        }
        if not write_output(report, args, summary=f"connection #{args.id} audit"):
            rows = report["connection_corrections"] + report["evidence_corrections"]
            if not rows:
                print("No connection corrections found.")
            for correction in rows:
                key = (
                    f"[{correction['record_key']}]"
                    if correction.get("record_key")
                    else ""
                )
                print(
                    f"[{correction['created_at']}] {correction['table_name']}"
                    f"#{correction['record_id']}{key}.{correction['field_name']}: "
                    f"{correction['old_value']} -> {correction['new_value']}"
                )
                print(f"  Reason: {correction['reason']}")

    elif args.command == "connection-provenance":
        provenance = get_connection_provenance(args.id)
        if provenance is None:
            print(f"Connection #{args.id} not found.", file=sys.stderr)
            raise SystemExit(1)
        if not write_output(
            provenance, args, summary=f"connection #{args.id} provenance"
        ):
            print(f"=== Provenance for Connection #{args.id} ===")
            print(format_connection(provenance))
            if provenance.get("description"):
                print(f"Description: {provenance['description']}")
            if provenance.get("upstream_finding"):
                finding = provenance["upstream_finding"]
                print(
                    f"Upstream finding: #{finding['id']} "
                    f"({finding['verification_status']}) {finding['summary']}"
                )
            print(f"Evidence ({len(provenance['evidence'])}):")
            for evidence in provenance["evidence"]:
                print(f"  [{evidence['evidence_type']}] {evidence['evidence_ref']}")
                if evidence.get("source_quote"):
                    print(f'    Quote: "{evidence["source_quote"]}"')
                if evidence.get("source_page"):
                    print(f"    Page/Loc: {evidence['source_page']}")
                if evidence.get("assessment"):
                    print(f"    Assessment: {evidence['assessment']}")
            print(
                f"Corrections: {len(provenance['corrections'])} connection, "
                f"{len(provenance['evidence_corrections'])} evidence"
            )

    elif args.command == "connection-unverified":
        connections = get_unverified_connections(
            limit=args.limit,
            profile_id=args.profile,
            all_profiles=args.all_profiles,
        )
        if not write_output(
            connections,
            args,
            summary=f"unverified connections: {len(connections)}",
        ):
            if not connections:
                print("No unverified connections found.")
            for connection in connections:
                print(format_connection(connection))
                print(f"    Evidence: {connection.get('evidence_refs') or 'none'}")

    elif args.command == "connections":
        conns = get_connections(
            args.person,
            depth=args.depth,
            relationship_type=args.rel_type,
            profile_id=getattr(args, "profile", None),
            all_profiles=getattr(args, "all_profiles", False),
            verification_status=(
                "verified" if getattr(args, "verified_only", False) else None
            ),
        )
        if not write_output(
            conns,
            args,
            summary=f"connections for '{args.person}': {len(conns)} results",
        ):
            if not conns:
                print(f"No connections found for '{args.person}'")
            else:
                print(f"Connections for '{args.person}' (depth={args.depth}):")
                for c in conns:
                    print(format_connection(c))

    elif args.command == "search":
        results = search_findings(
            args.query,
            thread_id=getattr(args, "thread_id", None),
            profile_id=getattr(args, "profile", None),
            all_profiles=getattr(args, "all_profiles", False),
            limit=args.limit,
        )
        if not write_output(
            results,
            args,
            summary=f"findings search '{args.query}': {len(results)} results",
        ):
            if not results:
                print(f"No findings matching '{args.query}'")
            else:
                print(f"Found {len(results)} findings matching '{args.query}':")
                for f in results:
                    print(format_finding(f))

    elif args.command == "timeline":
        events = get_timeline(
            target=args.target,
            start_date=args.start,
            end_date=args.end,
            limit=args.limit,
            profile_id=getattr(args, "profile", None),
            all_profiles=getattr(args, "all_profiles", False),
        )
        if not write_output(events, args, summary=f"timeline: {len(events)} events"):
            if not events:
                print("No dated findings found.")
            else:
                print(f"Timeline ({len(events)} events):")
                for f in events:
                    print(f"  {f['date_of_event']}  {f['target_name']}: {f['summary']}")

    elif args.command == "verify":
        try:
            verify_finding(args.id, verified_by=args.by)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Verified finding #{args.id}")

    elif args.command == "dispute":
        dispute_finding(args.id, reason=args.reason, corrected_by=args.by)
        print(f"Disputed finding #{args.id}: {args.reason}")
        if getattr(args, "contradicted_by", None):
            relate_findings(
                args.id,
                args.contradicted_by,
                "contradicts",
                assessment=args.reason,
                created_by=args.by,
            )
            print(
                f"  + recorded relation: #{args.id} contradicts #{args.contradicted_by}"
            )

    elif args.command == "relate":
        relate_findings(
            args.from_id,
            args.to_id,
            args.relation_type,
            assessment=args.assessment,
            created_by=args.by,
        )
        print(f"Recorded: #{args.from_id} {args.relation_type} #{args.to_id}")

    elif args.command in {"relation-delete", "unrelate"}:
        try:
            relation_id = delete_finding_relation(
                args.from_id,
                args.to_id,
                args.relation_type,
                reason=args.reason,
                corrected_by=args.by,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        print(
            f"Deleted finding relation #{relation_id}: "
            f"#{args.from_id} {args.relation_type} #{args.to_id}"
        )

    elif args.command == "retract":
        if retract_finding(args.id, reason=args.reason, corrected_by=args.by):
            print(f"Retracted finding #{args.id}: {args.reason}")
            print("  (downstream connections flagged as disputed)")
        else:
            print(f"Finding #{args.id} not found.")

    elif args.command == "correct":
        if args.field not in ALLOWED_CORRECT_FIELDS:
            print(
                f"ERROR: Cannot correct field '{args.field}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_CORRECT_FIELDS))}",
                file=sys.stderr,
            )
            sys.exit(1)
        if update_finding(
            args.id,
            args.field,
            args.value,
            args.reason,
            correction_type=args.correction_type,
            corrected_by=args.by,
        ):
            print(f"Corrected finding #{args.id}.{args.field}")
            print(f"  Reason: {args.reason}")
        else:
            print(f"Finding #{args.id} not found.")

    elif args.command == "audit":
        corrections = get_corrections(
            table_name=args.table,
            record_id=args.id,
            record_key=getattr(args, "record_key", None),
            correction_type=getattr(args, "correction_type", None),
            limit=args.limit,
        )
        structured = write_output(
            corrections, args, summary=f"correction history: {len(corrections)} entries"
        )
        if not structured and getattr(args, "json_out", False):
            print(json.dumps(corrections, indent=2, default=str))
            structured = True
        if not structured and corrections:
            print(f"Correction history ({len(corrections)} entries):")
            for c in corrections:
                print(
                    f"  [{c['created_at']}] {c['table_name']}#{c['record_id']}.{c['field_name']}"
                )
                print(
                    f"    Type: {c['correction_type']}  By: {c.get('corrected_by', '?')}"
                )
                print(f"    Old: {c['old_value']}")
                print(f"    New: {c['new_value']}")
                print(f"    Reason: {c['reason']}")
                print()
        elif not structured:
            print("No corrections found.")

    elif args.command == "provenance":
        prov = get_provenance(args.id)
        if not prov:
            print(f"Finding #{args.id} not found.")
            sys.exit(1)
        if not write_output(prov, args, summary=f"provenance for finding #{args.id}"):
            print(f"=== Provenance for Finding #{args.id} ===")
            print(f"Target: {prov['target_name']}")
            print(f"Summary: {prov['summary']}")
            print(f"Claim type: {prov.get('claim_type', '?')}")
            print(f"Verification: {prov.get('verification_status', '?')}")
            print(f"Confidence: {prov['confidence']}")
            print()
            if prov["evidence"]:
                print(f"--- Evidence ({len(prov['evidence'])}) ---")
                for ev in prov["evidence"]:
                    print(f"  [{ev['evidence_type']}] {ev['evidence_ref']}")
                    if ev.get("source_quote"):
                        print(f'    Quote: "{ev["source_quote"]}"')
                    if ev.get("email_sender"):
                        sender = ev["email_sender"]
                        date_str = (
                            f" ({ev['email_date']})" if ev.get("email_date") else ""
                        )
                        pos = ev.get("chain_position")
                        pos_str = f", chain position {pos}" if pos is not None else ""
                        print(f"    Email sender: {sender}{date_str}{pos_str}")
                    if ev.get("source_page"):
                        print(f"    Page/Loc: {ev['source_page']}")
                    if ev.get("assessment"):
                        print(f"    Assessment: {ev['assessment']}")
                    if ev.get("source_reliability"):
                        rel = ev["source_reliability"]
                        print(
                            f"    Source reliability: {rel['source_type']} — {rel.get('reliability_notes', '')}"
                        )
            else:
                print("  WARNING: No evidence references attached!")
            if prov["corrections"]:
                print(f"\n--- Corrections ({len(prov['corrections'])}) ---")
                for c in prov["corrections"]:
                    print(
                        f"  [{c['created_at']}] {c['correction_type']}: {c['field_name']}"
                    )
                    print(f"    {c['old_value']} -> {c['new_value']}")
                    print(f"    Reason: {c['reason']}")
            if prov["evidence_corrections"]:
                print(
                    f"\n--- Evidence Corrections "
                    f"({len(prov['evidence_corrections'])}) ---"
                )
                for c in prov["evidence_corrections"]:
                    print(
                        f"  [{c['created_at']}] {c['correction_type']}: "
                        f"{c.get('record_key', '?')}.{c['field_name']}"
                    )
                    print(f"    {c['old_value']} -> {c['new_value']}")
                    print(f"    Reason: {c['reason']}")
            if prov["connections"]:
                print(f"\n--- Connections ({len(prov['connections'])}) ---")
                for conn in prov["connections"]:
                    vstat = conn.get("verification_status", "?")
                    print(
                        f"  {conn['person_a']} <-> {conn['person_b']} [{conn.get('relationship_type', '?')}] (verif: {vstat})"
                    )

    elif args.command == "unverified":
        findings = get_unverified(
            limit=args.limit,
            profile_id=args.profile,
            all_profiles=args.all_profiles,
        )
        structured = write_output(
            findings, args, summary=f"unverified findings: {len(findings)}"
        )
        if not structured and getattr(args, "json_out", False):
            print(json.dumps(findings, indent=2, default=str))
            structured = True
        if not structured:
            if not findings:
                print("All findings verified!")
            else:
                print(f"Unverified findings ({len(findings)}):")
                for f in findings:
                    refs = f.get("evidence_refs", "none")
                    print(
                        f"  #{f['id']:>4} [{f.get('claim_type', '?'):>12}] {f['target_name']}: {f['summary']}"
                    )
                    print(f"         Evidence: {refs}")

    elif args.command == "stats":
        p_id = getattr(args, "profile", None)
        p_all = getattr(args, "all_profiles", False)
        stats = get_stats(profile_id=p_id, all_profiles=p_all)
        # Augment with audit stats
        resolved_profile = _resolve_profile(p_id, p_all)
        db = _get_db_standalone()
        profile_cond = " AND profile_id = ?" if resolved_profile else ""
        profile_params = [resolved_profile] if resolved_profile else []
        total_corrections = db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        hallucinations = db.execute(
            "SELECT COUNT(*) FROM corrections WHERE correction_type = 'hallucination'"
        ).fetchone()[0]
        retracted = db.execute(
            f"SELECT COUNT(*) FROM findings WHERE verification_status = 'retracted'{profile_cond}",
            profile_params,
        ).fetchone()[0]
        verified = db.execute(
            f"SELECT COUNT(*) FROM findings WHERE verification_status = 'verified'{profile_cond}",
            profile_params,
        ).fetchone()[0]
        unverified_ct = db.execute(
            f"SELECT COUNT(*) FROM findings WHERE verification_status = 'unverified'{profile_cond}",
            profile_params,
        ).fetchone()[0]
        disputed = db.execute(
            f"SELECT COUNT(*) FROM findings WHERE verification_status = 'disputed'{profile_cond}",
            profile_params,
        ).fetchone()[0]
        db.close()
        stats["audit"] = {
            "verified": verified,
            "unverified": unverified_ct,
            "disputed": disputed,
            "retracted": retracted,
            "total_corrections": total_corrections,
            "hallucinations": hallucinations,
        }
        if not write_output(
            stats,
            args,
            summary=f"findings stats: {stats['total_findings']} findings, {stats['total_connections']} connections",
        ):
            print(f"Total findings: {stats['total_findings']}")
            print(f"Total connections: {stats['total_connections']}")
            if stats.get("by_type"):
                print("\nBy type:")
                for t, c in sorted(
                    stats["by_type"].items(), key=lambda x: (x[0] is None, x[0] or "")
                ):
                    print(f"  {t or '(none)'}: {c}")
            if stats.get("by_confidence"):
                print("\nBy confidence:")
                for conf, c in sorted(
                    stats["by_confidence"].items(),
                    key=lambda x: (x[0] is None, x[0] or ""),
                ):
                    print(f"  {conf or '(none)'}: {c}")
            if stats.get("top_targets"):
                print("\nTop targets:")
                for name, c in stats["top_targets"].items():
                    print(f"  {name}: {c}")
            print("\nAudit status:")
            print(f"  Verified: {verified}")
            print(f"  Unverified: {unverified_ct}")
            print(f"  Disputed: {disputed}")
            print(f"  Retracted: {retracted}")
            print(f"  Total corrections: {total_corrections}")
            if hallucinations:
                print(f"  Hallucinations caught: {hallucinations}")


if __name__ == "__main__":
    main()

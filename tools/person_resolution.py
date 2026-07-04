#!/usr/bin/env python3
"""Builder: person resolution (candidate identities) in epstein_derived.db.

Collapses the kabass `entities` person mentions — 2.1M mentions across ~156K
distinct `value` strings, `normalized_value` 100% NULL — into a small set of
CANDIDATE canonical identities. The Epstein-surname cluster alone is ~980 strings
/ 380K mentions and mixes the real subject (Jeffrey), his brother (MARK LAWRENCE
EPSTEIN), OCR typos (Jefffrey/joffrey/Jeffery), surname-first ordering (Epstein
Jeffrey), initials (JE) and title forms (Mr. Epstein).

CONTRACT / SAFETY (see tools/epstein_derived.py):
  * Read-only ATTACH of every source DB (kabass 'kab', core 'core').
  * Writes ONLY to datasets/epstein_derived.db, into tables OWNED by
    epstein_derived.py (canonical_person, person_mention, entity_crosswalk).
    This module never CREATE TABLEs and never writes investigation.db.
  * These are CANDIDATES. `reconcile` stages entity_crosswalk rows with
    match_status='candidate'; it does NOT auto-merge core entities.

Pipeline (`build`):
  1. seed     canonical_person from ground truth (kab.persons aliases/search_terms,
              core.name_aliases) -> match_method='seed', confidence='high'.
  2. load     distinct kab person strings + mention counts (all ~156K).
  3. block    normalized-key + surname + surname-metaphone blocks (never all-pairs).
  4. match    within a block: seed/exact-norm -> high; phonetic/nickname/fuzzy>=90
              -> medium; fuzzy 82-90 -> low. rapidfuzz token_sort_ratio.
  5. assign   every raw string -> a canonical_person; populate person_mention +
              canonical_person mention/doc counts, normalized_key, surname_metaphone.

  GUARDRAIL: bare surname ("Epstein"), title form ("Mr. Epstein") and initials
  ("JE") stay LOW confidence — the Mark-vs-Jeffrey ambiguity means a bare surname
  is never forced onto the dominant identity at high confidence.

Usage:
    uv run python tools/person_resolution.py build [--limit N] [--reset]
    uv run python tools/person_resolution.py reconcile [--dry-run]
    uv run python tools/person_resolution.py lookup "Jeffrey Epstein"
    uv run python tools/person_resolution.py stats
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.epstein_derived import (  # noqa: E402
    get_db, attach, init_schema, new_run,
    KABASS_DB, CORE_DB,
)
from tools.entity_resolution import normalize_person_name as _base_normalize  # noqa: E402

NICKNAMES_PATH = PROJECT_ROOT / "data" / "nicknames.json"

# rapidfuzz is an existing dependency; jellyfish provides metaphone (falls back to
# a local soundex if unavailable so the builder never hard-crashes on import).
from rapidfuzz import fuzz  # noqa: E402

try:
    import jellyfish

    def _metaphone(s):
        try:
            return jellyfish.metaphone(s) or ""
        except Exception:
            return ""
    PHONETIC_BACKEND = "jellyfish.metaphone"
except ImportError:  # pragma: no cover - jellyfish is installed in this env
    def _metaphone(s):
        return _soundex(s)
    PHONETIC_BACKEND = "soundex(fallback)"


# ── fuzzy thresholds ─────────────────────────────────────────────────────────
FUZZY_HIGH = 90    # >= this (via phonetic/nickname/fuzzy) -> medium confidence
FUZZY_LOW = 82     # [FUZZY_LOW, FUZZY_HIGH) -> low confidence
BATCH = 5000

# Extra titles/honorifics to strip beyond entity_resolution's PERSON_PREFIXES.
_EXTRA_TITLES = ("mr", "mrs", "ms", "miss", "dr", "prof", "sir", "hon",
                 "rev", "fr", "st", "lord", "lady", "the")
_TITLE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(t) for t in _EXTRA_TITLES) + r")\.?\s+", re.IGNORECASE)
_INITIAL_RE = re.compile(r"^[a-z]\.?$")


def _soundex(s):
    """Minimal Soundex — fallback only when jellyfish is unavailable."""
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    if not s:
        return ""
    codes = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"),
             **dict.fromkeys("dt", "3"), "l": "4",
             **dict.fromkeys("mn", "5"), "r": "6"}
    first = s[0].upper()
    tail, prev = "", codes.get(s[0], "")
    for ch in s[1:]:
        c = codes.get(ch, "")
        if c and c != prev:
            tail += c
        if ch not in "hw":
            prev = c
    return (first + tail + "000")[:4]


# ── normalization (extends entity_resolution.normalize_person_name) ──────────
def normalize_person_name(name):
    """Order-insensitive normalized key for a person string.

    Extends the base normalizer (title/suffix strip, lowercase) with:
      * broader title stripping (Sir/Hon/Rev/Lord/St/...),
      * folding a lone middle initial ("e"/"e.") out of the token set,
      * sorting the remaining tokens so "Epstein Jeffrey" == "Jeffrey Epstein".
    """
    if not name:
        return ""
    s = _TITLE_RE.sub("", name.strip())
    s = _base_normalize(s)  # lowercase, punctuation, prefix/suffix strip
    if not s:
        return ""
    toks = [t for t in s.split() if t]
    # Drop single-letter middle initials only when other tokens remain, so "JE"
    # or a bare "J" still produces a (weak) key rather than an empty string.
    substantive = [t for t in toks if len(t) > 1]
    kept = substantive if substantive else toks
    return " ".join(sorted(kept))


def _tokens(name):
    s = _base_normalize(_TITLE_RE.sub("", (name or "").strip()))
    return [t for t in s.split() if t]


def surname_token(name):
    """Last substantive (len>1) token — the surname block key."""
    toks = [t for t in _tokens(name) if len(t) > 1]
    return toks[-1] if toks else ""


def given_token(name):
    """First substantive token — used for nickname equivalence."""
    toks = [t for t in _tokens(name) if len(t) > 1]
    return toks[0] if toks else ""


def is_bare_or_initials(name):
    """True for a lone surname ("Epstein"), a title form ("Mr. Epstein") or
    initials ("JE" / "J.E." / "J E"). These stay LOW confidence — the guardrail
    against forcing an ambiguous fragment onto the dominant identity."""
    toks = _tokens(name)
    if not toks:
        return True
    substantive = [t for t in toks if len(t) > 1]
    if len(substantive) <= 1 and len(toks) <= 1:
        # single token total: bare surname / single initial
        return True
    if not substantive:
        return True  # e.g. "j e" -> all initials
    # "Epstein Jeffrey" has 2 substantive tokens -> not bare.
    # A single substantive token plus stray initials ("Mr Epstein" already had
    # the title stripped, so that is one token -> caught above) is still bare.
    return len(substantive) < 2


# ── nickname map ─────────────────────────────────────────────────────────────
class NicknameMap:
    """Token -> equivalence-class id. Two given names are nickname-equivalent iff
    they map to the same class (and, at match time, share a surname)."""

    def __init__(self, groups):
        self.token2class = {}
        self.groups = []
        for grp in groups:
            self._add_group(grp)

    def _add_group(self, grp):
        """Register a curated equivalence class with STRICT first-class-wins
        semantics: a token already assigned to a class is NOT moved, and two
        classes are NEVER transitively merged. (Merging on shared tokens welds
        unrelated names into one blob — an early version chained every surname
        into the 'jeff' class via a single duplicated token.) A duplicate token
        across curated groups is a data error; we keep the first and warn."""
        norm = sorted({t.strip().lower() for t in grp if t and t.strip()})
        if len(norm) < 2:
            return
        cid = len(self.groups)
        self.groups.append([])
        for t in norm:
            if t in self.token2class:
                import warnings
                warnings.warn(
                    f"nickname token {t!r} in multiple groups; keeping first "
                    f"(class {self.token2class[t]}), ignoring in class {cid}")
                continue
            self.token2class[t] = cid
            self.groups[cid].append(t)

    def add_pair(self, a, b):
        """Add a single (a, b) equivalence, joining an EXISTING class only when
        exactly one side is known (never merging two classes). Safe for injecting
        a real-world diminutive we didn't hardcode (e.g. ace/alan)."""
        a = (a or "").strip().lower()
        b = (b or "").strip().lower()
        if not a or not b or a == b:
            return
        ca, cb = self.token2class.get(a), self.token2class.get(b)
        if ca is not None and cb is not None:
            return  # both known: do NOT merge two curated classes
        if ca is not None:
            self.token2class[b] = ca
            self.groups[ca].append(b)
        elif cb is not None:
            self.token2class[a] = cb
            self.groups[cb].append(a)
        else:
            self._add_group([a, b])

    def equivalent(self, a, b):
        if not a or not b:
            return False
        if a == b:
            return True
        ca, cb = self.token2class.get(a), self.token2class.get(b)
        return ca is not None and ca == cb

    @classmethod
    def load(cls, extra_pairs=None):
        data = json.loads(NICKNAMES_PATH.read_text())
        nm = cls(data.get("groups", []))
        # Optionally inject real-world diminutive pairs we didn't hardcode via the
        # SAFE add_pair path (joins at most one existing class, never merges two).
        # NOTE: the build does NOT pass alias-harvested pairs here — given/surname
        # tokenization of single-name aliases yields (given, surname) pairs that
        # would attach surnames to given-name classes. Curated JSON is the source
        # of truth; seed aliases already collapse variants directly.
        for a, b in (extra_pairs or ()):
            nm.add_pair(a, b)
        return nm


# ── seed loading ─────────────────────────────────────────────────────────────
def _json_list(raw):
    """kab.persons stores aliases/search_terms as a JSON *string* (double-encoded).
    Return a list of clean names, tolerating '[]', bad JSON, or a bare string."""
    if not raw:
        return []
    if isinstance(raw, list):
        vals = raw
    else:
        try:
            vals = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [raw] if isinstance(raw, str) and raw.strip() else []
    out = []
    for v in vals if isinstance(vals, list) else [vals]:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def load_seeds(db):
    """Return (seeds, extra_nick_pairs).

    seeds: list of dicts {canonical_name, category, seed_source, aliases:set}.
    extra_nick_pairs: (given_a, given_b) tuples harvested from same-surname
    alias pairs, to augment the nickname map.

    Sources:
      * kab.persons  — JSON in `data`: canonical_name, category, aliases[],
                       search_terms[]  (aliases + search_terms + canonical seed
                       the identity's known strings).
      * core.name_aliases — canonical_name / alias (+ entity_id when set).
    Skips FOIA redaction placeholders like "(b) (6)" which are not real persons.
    """
    seeds = []
    nick_pairs = []

    # --- kabass curated persons ---
    for (raw,) in db.execute("SELECT data FROM kab.persons"):
        try:
            rec = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        canon = (rec.get("canonical_name") or "").strip()
        if not canon or canon.lower().startswith("(b)") or _is_redaction(canon):
            continue
        aliases = set(_json_list(rec.get("aliases")))
        aliases |= set(_json_list(rec.get("search_terms")))
        aliases.add(canon)
        aliases = {a for a in aliases if a and not _is_redaction(a)}
        if not aliases:
            continue
        seeds.append({
            "canonical_name": canon,
            "category": rec.get("category"),
            "seed_source": "kabass_persons",
            "aliases": aliases,
        })
        # Harvest nickname pairs from same-surname aliases of this identity.
        by_surname = defaultdict(set)
        for a in aliases:
            sn = surname_token(a)
            gv = given_token(a)
            if sn and gv:
                by_surname[sn].add(gv)
        for givens in by_surname.values():
            givens = sorted(givens)
            for i in range(len(givens)):
                for j in range(i + 1, len(givens)):
                    nick_pairs.append((givens[i], givens[j]))

    # --- core name_aliases (person variants) ---
    by_canon = defaultdict(lambda: {"aliases": set(), "entity_id": None})
    for row in db.execute(
        "SELECT canonical_name, alias, entity_id, alias_type FROM core.name_aliases"
    ):
        canon = (row["canonical_name"] or "").strip()
        alias = (row["alias"] or "").strip()
        if not canon:
            continue
        # Skip pure org variants; keep person + entity_as_person + unknown.
        if row["alias_type"] == "entity_variant":
            continue
        rec = by_canon[canon]
        rec["aliases"].add(canon)
        if alias:
            rec["aliases"].add(alias)
        if row["entity_id"] is not None and rec["entity_id"] is None:
            rec["entity_id"] = row["entity_id"]
    for canon, rec in by_canon.items():
        aliases = {a for a in rec["aliases"] if a and not _is_redaction(a)}
        if not aliases:
            continue
        seeds.append({
            "canonical_name": canon,
            "category": None,
            "seed_source": "name_aliases",
            "aliases": aliases,
            "core_entity_id": rec["entity_id"],
        })

    return seeds, nick_pairs


_REDACTION_RE = re.compile(r"\(b\)\s*\(\d|redact|b6|b7c|foia", re.IGNORECASE)


def _is_redaction(s):
    return bool(_REDACTION_RE.search(s or ""))


# ── canonical registry (built in-memory, flushed to sidecar) ─────────────────
class Registry:
    """Accumulates canonical_person rows + their normalized/surname/metaphone
    blocks in memory, then batch-inserts. Keeps three block indexes for O(block)
    candidate lookup instead of all-pairs over 156K strings."""

    def __init__(self, nickmap):
        self.nick = nickmap
        self.persons = []                 # index -> dict
        self.by_normkey = {}              # normkey -> person index (exact block)
        self.by_surname = defaultdict(list)   # surname -> [person index]
        self.by_metaphone = defaultdict(list)  # metaphone -> [person index]

    def _new_person(self, canonical_name, seed_source, category=None,
                    core_entity_id=None):
        nk = normalize_person_name(canonical_name)
        sn = surname_token(canonical_name)
        mp = _metaphone(sn) if sn else ""
        idx = len(self.persons)
        self.persons.append({
            "canonical_name": canonical_name,
            "normalized_key": nk,
            "surname_metaphone": mp,
            "category": category,
            "core_entity_id": core_entity_id,
            "seed_source": seed_source,
            "surname": sn,
            "given": given_token(canonical_name),
        })
        if nk and nk not in self.by_normkey:
            self.by_normkey[nk] = idx
        if sn:
            self.by_surname[sn].append(idx)
        if mp:
            self.by_metaphone[mp].append(idx)
        return idx

    def add_seed(self, seed):
        """Create a canonical person from a seed and return (idx, [aliases])."""
        idx = self._new_person(
            seed["canonical_name"], seed["seed_source"],
            category=seed.get("category"),
            core_entity_id=seed.get("core_entity_id"),
        )
        return idx, seed["aliases"]

    def match(self, raw):
        """Return (person_idx, match_method, score, confidence) for a raw string.

        Order: exact-norm (high) -> phonetic/nickname/fuzzy>=90 (medium) ->
        fuzzy 82-90 (low). Bare-surname/initials are demoted to LOW even on an
        exact-norm hit (guardrail). NB: the build routes bare strings to
        `match_bare` in a 2nd pass instead — the bare handling here keeps this a
        correct standalone matcher for any caller.
        """
        nk = normalize_person_name(raw)
        bare = is_bare_or_initials(raw)

        # 1. exact normalized-key block.
        if nk and nk in self.by_normkey:
            idx = self.by_normkey[nk]
            if bare:
                return idx, "exact_norm", 100.0, "low"
            return idx, "exact_norm", 100.0, "high"

        sn = surname_token(raw)
        gv = given_token(raw)

        # 2/3. candidate pool = surname block ∪ metaphone block.
        cand = set()
        if sn:
            cand.update(self.by_surname.get(sn, ()))
            mp = _metaphone(sn)
            if mp:
                cand.update(self.by_metaphone.get(mp, ()))
        if not cand:
            return None

        best = None  # (score, idx, method)
        for idx in cand:
            p = self.persons[idx]
            score = fuzz.token_sort_ratio(nk, p["normalized_key"])
            method = "fuzzy"
            # Nickname equivalence (same surname, nickname-equivalent given) is a
            # strong signal even if raw fuzz is mediocre (Rich Kahn vs Richard Kahn).
            if sn and p["surname"] == sn and self.nick.equivalent(gv, p["given"]):
                score = max(score, FUZZY_HIGH)
                method = "nickname"
            elif sn and p["surname"] != sn and p["surname_metaphone"] and \
                    _metaphone(sn) == p["surname_metaphone"] and \
                    self.nick.equivalent(gv, p["given"]):
                # phonetic surname + nickname given (e.g. OCR'd surname variant).
                score = max(score, FUZZY_HIGH)
                method = "phonetic"
            if best is None or score > best[0]:
                best = (score, idx, method)

        if best is None:
            return None
        score, idx, method = best
        if score < FUZZY_LOW:
            return None
        # Confidence tiers.
        if bare:
            conf = "low"
        elif score >= FUZZY_HIGH:
            conf = "medium"
        else:
            conf = "low"
        return idx, method, float(round(score, 1)), conf

    def match_bare(self, raw, canon_mass):
        """Resolve a bare surname / title-form / initials string to the DOMINANT
        (highest accumulated mention_count) canonical sharing its surname block —
        always at LOW confidence.

        Run in a second pass, after full-name strings have established mention mass
        per canonical, so "Epstein" attaches deterministically to the busiest
        Epstein identity instead of whichever seed happened to win a fuzz tie.
        Returns None if no same-surname canonical exists (caller mints a singleton).
        """
        sn = surname_token(raw)
        if not sn:
            return None
        cand = set(self.by_surname.get(sn, ()))
        mp = _metaphone(sn)
        if mp:
            cand.update(self.by_metaphone.get(mp, ()))
        cand = [i for i in cand if self.persons[i]["surname"] == sn] or list(cand)
        if not cand:
            return None
        # Dominant = most mention mass so far; tie-break on lower index (earlier
        # seed) for determinism.
        idx = max(cand, key=lambda i: (canon_mass.get(i, 0), -i))
        return idx, "bare_surname", 100.0, "low"

    def get_or_create_singleton(self, raw):
        """No block match — mint a fresh canonical person for this raw string.
        Confidence is high only if the string is a full (>=2 token) name and not
        a bare surname/initials; otherwise low."""
        idx = self._new_person(raw, "derived")
        bare = is_bare_or_initials(raw)
        return idx, "exact_norm", 100.0, ("low" if bare else "high")


def _with_retry(fn, *, retries=6, what="write"):
    """Run a write callable, retrying on 'database is locked' with backoff.

    Wraps the small prelude writes (init_schema, new_run) that also contend with
    parallel builders on epstein_derived.db."""
    import time
    for attempt in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < retries - 1:
                wait = 2 * (attempt + 1)
                print(f"  [locked] retrying {what} in {wait}s "
                      f"(attempt {attempt + 1}/{retries}) ...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def _atomic_write(db, canon_rows, mention_rows, reset=False, retries=6):
    """Write canonical_person + person_mention (optionally after clearing them)
    in ONE `BEGIN IMMEDIATE` transaction, retrying on lock.

    Under parallel builders sharing epstein_derived.db, batched commits let a
    sibling wedge the write lock between batches and then block our reacquire.
    Taking the write lock once (IMMEDIATE) and doing all inserts before COMMIT
    avoids that; busy_timeout (set in get_db) absorbs the wait, and we retry the
    whole unit a few times if we still lose the race.
    """
    import time
    for attempt in range(retries):
        try:
            db.execute("BEGIN IMMEDIATE")
            if reset:
                db.execute("DELETE FROM person_mention")
                db.execute("DELETE FROM entity_crosswalk")
                db.execute("DELETE FROM canonical_person")
            db.executemany("""
                INSERT INTO canonical_person
                    (person_id, canonical_name, normalized_key, surname_metaphone,
                     category, core_entity_id, seed_source, mention_count, doc_count,
                     review_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unreviewed')
            """, canon_rows)
            db.executemany("""
                INSERT OR REPLACE INTO person_mention
                    (raw_value, canonical_id, match_method, score, confidence, mention_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, mention_rows)
            db.commit()
            return
        except sqlite3.OperationalError as e:
            db.rollback()
            if "locked" in str(e).lower() and attempt < retries - 1:
                wait = 2 * (attempt + 1)
                print(f"  [locked] retrying write in {wait}s "
                      f"(attempt {attempt + 1}/{retries}) ...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


# ── build ────────────────────────────────────────────────────────────────────
def cmd_build(args):
    db = get_db()
    _with_retry(lambda: init_schema(db), what="init_schema")
    attach(db, "kab", KABASS_DB)
    attach(db, "core", CORE_DB)

    if args.reset:
        # The actual DELETEs run inside the atomic write below (one lock take);
        # this just announces intent.
        print("reset: will clear canonical_person / person_mention / entity_crosswalk")

    run_id = _with_retry(
        lambda: new_run(db, "person_resolution",
                        note="candidate canonical persons + mentions from kabass"),
        what="new_run")

    # 1. seeds -----------------------------------------------------------------
    print("loading seeds (kab.persons + core.name_aliases) ...")
    seeds, _nick_pairs = load_seeds(db)
    # Nickname map = CURATED JSON only. Alias-harvested pairs are intentionally
    # NOT injected: given/surname tokenization of single-name aliases produces
    # (given, surname) pairs that pollute given-name classes with surnames.
    nickmap = NicknameMap.load()
    reg = Registry(nickmap)

    # Deduplicate seeds by normalized canonical name so kab + core don't create
    # two canonicals for the same identity; merge their alias sets.
    seed_by_key = {}
    for s in seeds:
        k = normalize_person_name(s["canonical_name"]) or s["canonical_name"].lower()
        if k in seed_by_key:
            tgt = seed_by_key[k]
            tgt["aliases"] |= s["aliases"]
            tgt.setdefault("core_entity_id", None)
            if s.get("core_entity_id") and not tgt.get("core_entity_id"):
                tgt["core_entity_id"] = s["core_entity_id"]
            if s.get("category") and not tgt.get("category"):
                tgt["category"] = s["category"]
        else:
            seed_by_key[k] = dict(s)

    # seed_alias assignments: alias string -> (person_idx, method, score, conf)
    seed_assign = {}
    for s in seed_by_key.values():
        idx, aliases = reg.add_seed(s)
        for a in aliases:
            # A seed alias always maps to its canonical at high confidence,
            # UNLESS it's a bare surname/initials (guardrail): those go low so a
            # shared surname across two seeds doesn't mint a false-high mapping.
            conf = "low" if is_bare_or_initials(a) else "high"
            prev = seed_assign.get(a)
            # Prefer a high-confidence full-name seed over a low bare-surname one.
            if prev is None or (prev[3] == "low" and conf == "high"):
                seed_assign[a] = (idx, "seed", 100.0, conf)
    print(f"  seed identities: {len(reg.persons):,}  "
          f"(kab.persons + core.name_aliases, deduped)")
    print(f"  seed alias strings: {len(seed_assign):,}")
    print(f"  nickname classes: {len(nickmap.groups):,} (curated)")

    # 2. load distinct kab person strings + counts -----------------------------
    print("loading distinct kabass person strings ...")
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""
    rows = db.execute(f"""
        SELECT value, COUNT(*) AS mentions, COUNT(DISTINCT document_id) AS docs
        FROM kab.entities
        WHERE entity_type = 'person' AND value IS NOT NULL AND TRIM(value) <> ''
        GROUP BY value
        {limit_clause}
    """).fetchall()
    print(f"  distinct person strings: {len(rows):,}")

    # 3/4/5. assign every raw string — TWO PASSES ------------------------------
    #   pass 1: seeds + full-name strings (exact-norm / phonetic / nickname /
    #           fuzzy). This establishes mention mass per canonical.
    #   pass 2: bare surnames / title forms / initials, resolved to the DOMINANT
    #           same-surname canonical at LOW confidence (guardrail) using the
    #           mass from pass 1 — deterministic, not fuzz-tie dependent.
    assignments = []                       # (raw, idx, method, score, conf, m, d)
    canon_mentions = defaultdict(int)      # index -> summed mention_count
    canon_docs = defaultdict(int)          # index -> summed doc_count
    deferred_bare = []                     # (raw, m, d) resolved in pass 2

    for r in rows:
        raw = r["value"].strip()
        m, d = r["mentions"], r["docs"]

        if raw in seed_assign:
            idx, method, score, conf = seed_assign[raw]
        elif is_bare_or_initials(raw):
            deferred_bare.append((raw, m, d))
            continue
        else:
            res = reg.match(raw)
            if res is None:
                idx, method, score, conf = reg.get_or_create_singleton(raw)
            else:
                idx, method, score, conf = res
        assignments.append((raw, idx, method, score, conf, m, d))
        canon_mentions[idx] += m
        canon_docs[idx] += d

    # pass 2 — bare/initials against the now-known dominant same-surname canonical.
    for raw, m, d in deferred_bare:
        res = reg.match_bare(raw, canon_mentions)
        if res is None:
            idx, method, score, conf = reg.get_or_create_singleton(raw)
        else:
            idx, method, score, conf = res
        assignments.append((raw, idx, method, score, conf, m, d))
        canon_mentions[idx] += m
        canon_docs[idx] += d

    # Relabel `derived` canonicals (minted from a raw string) with their best
    # member as the display name: most mentions, preferring a full (>=2 token)
    # name over a bare fragment. Seeds keep their curated canonical_name.
    best_label = {}  # idx -> (rank_tuple, name)
    for raw, idx, method, score, conf, m, d in assignments:
        if reg.persons[idx]["seed_source"] != "derived":
            continue
        substantive = len([t for t in _tokens(raw) if len(t) > 1])
        rank = (substantive >= 2, m)          # full name first, then mention mass
        cur_best = best_label.get(idx)
        if cur_best is None or rank > cur_best[0]:
            best_label[idx] = (rank, raw)
    for idx, (_rank, name) in best_label.items():
        p = reg.persons[idx]
        if name != p["canonical_name"]:
            p["canonical_name"] = name
            p["normalized_key"] = normalize_person_name(name)

    # Pre-assign explicit person_ids (offset past any existing rows) so the whole
    # write is one atomic transaction — no per-row lastrowid dependency, no
    # intermediate commits. This matters under PARALLEL builders: we take the
    # write lock exactly once instead of releasing between batches (which lets a
    # sibling builder wedge in and then block our reacquire). On --reset we clear
    # first (inside the txn), so ids start at 1.
    if args.reset:
        base = 0
    else:
        base = db.execute(
            "SELECT COALESCE(MAX(person_id), 0) FROM canonical_person").fetchone()[0]
    idx2id = {idx: base + 1 + idx for idx in range(len(reg.persons))}

    canon_rows = [
        (idx2id[idx], p["canonical_name"], p["normalized_key"], p["surname_metaphone"],
         p["category"], p["core_entity_id"], p["seed_source"],
         canon_mentions.get(idx, 0), canon_docs.get(idx, 0))
        for idx, p in enumerate(reg.persons)
    ]
    mention_rows = [
        (raw, idx2id[idx], method, score, conf, m)
        for raw, idx, method, score, conf, m, d in assignments
    ]

    print(f"writing canonical_person + person_mention "
          f"({len(canon_rows):,} + {len(mention_rows):,}) in one transaction ...")
    _atomic_write(db, canon_rows, mention_rows, reset=args.reset)
    print(f"  canonical_person rows: {len(canon_rows):,}")
    print(f"  person_mention rows: {len(mention_rows):,}")
    n = len(mention_rows)

    total_mentions = sum(canon_mentions.values())

    def _finalize():
        db.execute(
            "UPDATE derivation_run SET completed_at = CURRENT_TIMESTAMP, record_count = ? "
            "WHERE run_id = ?", (len(idx2id), run_id))
        db.commit()
    _with_retry(_finalize, what="finalize run")

    # Summary.
    n_canon = len(idx2id)
    ratio = (total_mentions / n_canon) if n_canon else 0
    print(f"\nbuilt {n_canon:,} canonical persons from {len(rows):,} raw strings "
          f"({total_mentions:,} mentions; {ratio:,.1f} mentions/canonical)")
    print(f"phonetic backend: {PHONETIC_BACKEND}")
    db.close()


# ── reconcile ────────────────────────────────────────────────────────────────
def cmd_reconcile(args):
    """Match canonical_person -> core entities and stage entity_crosswalk rows.

    DRY-RUN by default: only reports counts (mapped-to-existing vs new). With
    --no-dry-run (i.e. omit --dry-run), writes candidate crosswalk rows into the
    sidecar (never investigation.db). match_status is always 'candidate'.
    """
    db = get_db()
    init_schema(db)
    attach(db, "core", CORE_DB)
    run_id = new_run(db, "person_resolution.reconcile", note="canonical->core candidates")

    # Build a normalized-name -> core entity_id index (persons + unknown types).
    core_by_norm = defaultdict(list)
    for row in db.execute(
        "SELECT id, name, entity_type FROM core.entities "
        "WHERE entity_type IN ('person') OR entity_type IS NULL OR entity_type = 'unknown'"
    ):
        nk = normalize_person_name(row["name"])
        if nk:
            core_by_norm[nk].append(row["id"])

    # name_aliases: alias-normalized -> entity_id (only rows with an entity_id).
    alias_by_norm = defaultdict(list)
    for row in db.execute(
        "SELECT alias, canonical_name, entity_id FROM core.name_aliases WHERE entity_id IS NOT NULL"
    ):
        for nm in (row["alias"], row["canonical_name"]):
            nk = normalize_person_name(nm)
            if nk:
                alias_by_norm[nk].append(row["entity_id"])

    canon = db.execute(
        "SELECT person_id, canonical_name, normalized_key, core_entity_id, mention_count "
        "FROM canonical_person"
    ).fetchall()

    mapped_exact = 0
    mapped_alias = 0
    already = 0
    new = 0
    rows_to_write = []
    for c in canon:
        nk = c["normalized_key"] or normalize_person_name(c["canonical_name"])
        core_id = None
        method = None
        if c["core_entity_id"] is not None:
            core_id, method = c["core_entity_id"], "seed_core_entity"
            already += 1
        elif nk in core_by_norm:
            core_id, method = core_by_norm[nk][0], "exact_norm"
            mapped_exact += 1
        elif nk in alias_by_norm:
            core_id, method = alias_by_norm[nk][0], "name_alias"
            mapped_alias += 1
        else:
            new += 1
            continue
        rows_to_write.append((c["person_id"], core_id, method, 100.0, run_id))

    print("\nReconcile canonical_person -> core investigation.db entities")
    print("=" * 62)
    print(f"  canonical persons:            {len(canon):,}")
    print(f"  already carry core_entity_id: {already:,}  (from name_aliases seed)")
    print(f"  match core by exact norm:     {mapped_exact:,}")
    print(f"  match core via name_alias:    {mapped_alias:,}")
    print(f"  -> map to existing core:      {already + mapped_exact + mapped_alias:,}")
    print(f"  no core match (new person):   {new:,}")

    if args.dry_run:
        print("\n  [DRY RUN] no entity_crosswalk rows written.")
        db.close()
        return

    db.executemany("""
        INSERT OR IGNORE INTO entity_crosswalk
            (derived_person_id, core_entity_id, match_method, match_score, match_status, run_id)
        VALUES (?, ?, ?, ?, 'candidate', ?)
    """, rows_to_write)
    db.commit()
    written = db.execute("SELECT COUNT(*) FROM entity_crosswalk").fetchone()[0]
    print(f"\n  wrote {len(rows_to_write):,} candidate crosswalk rows "
          f"(entity_crosswalk total: {written:,}, status='candidate').")
    db.close()


# ── lookup ───────────────────────────────────────────────────────────────────
def cmd_lookup(args):
    db = get_db()
    init_schema(db)
    name = args.name.strip()
    nk = normalize_person_name(name)

    # Resolve: prefer a person_mention on the exact raw string, then normalized
    # canonical key, then a canonical_name match.
    row = db.execute(
        "SELECT canonical_id FROM person_mention WHERE raw_value = ?", (name,)
    ).fetchone()
    person_id = row["canonical_id"] if row else None
    if person_id is None:
        row = db.execute(
            "SELECT person_id FROM canonical_person WHERE normalized_key = ? "
            "ORDER BY mention_count DESC LIMIT 1", (nk,)
        ).fetchone()
        person_id = row["person_id"] if row else None
    if person_id is None:
        row = db.execute(
            "SELECT person_id FROM canonical_person WHERE lower(canonical_name) = lower(?) "
            "ORDER BY mention_count DESC LIMIT 1", (name,)
        ).fetchone()
        person_id = row["person_id"] if row else None

    if person_id is None:
        print(f"No canonical cluster resolves '{name}'.")
        db.close()
        return

    p = db.execute("SELECT * FROM canonical_person WHERE person_id = ?", (person_id,)).fetchone()
    members = db.execute(
        "SELECT raw_value, match_method, score, confidence, mention_count "
        "FROM person_mention WHERE canonical_id = ? ORDER BY mention_count DESC",
        (person_id,)
    ).fetchall()
    total_m = sum(m["mention_count"] or 0 for m in members)

    print(f"\nCanonical #{p['person_id']}: {p['canonical_name']}")
    print("=" * 66)
    print(f"  normalized_key : {p['normalized_key']}")
    print(f"  surname_metaphone: {p['surname_metaphone']}  |  category: {p['category']}")
    print(f"  seed_source    : {p['seed_source']}  |  core_entity_id: {p['core_entity_id']}")
    print(f"  members (raw strings): {len(members):,}   total mentions: {total_m:,}")

    # Confidence rollup within the cluster.
    conf_counts = defaultdict(int)
    for m in members:
        conf_counts[m["confidence"]] += 1
    print("  confidence: " + ", ".join(
        f"{k}={conf_counts.get(k, 0)}" for k in ("high", "medium", "low")))

    shown = members if args.all else members[:args.top]
    print(f"\n  {'raw string':40s} {'method':11s} {'score':>6s} {'conf':>7s} {'mentions':>9s}")
    print("  " + "-" * 78)
    for m in shown:
        rv = (m["raw_value"] or "")[:40]
        print(f"  {rv:40s} {m['match_method'] or '':11s} "
              f"{(m['score'] or 0):6.0f} {m['confidence'] or '':>7s} "
              f"{(m['mention_count'] or 0):9,d}")
    if not args.all and len(members) > args.top:
        print(f"  ... and {len(members) - args.top:,} more (use --all)")

    # Sibling-surname warning: other canonicals sharing this surname metaphone
    # (surfaces the Mark-vs-Jeffrey Epstein distractor).
    if p["surname_metaphone"]:
        sibs = db.execute(
            "SELECT person_id, canonical_name, mention_count FROM canonical_person "
            "WHERE surname_metaphone = ? AND person_id != ? AND mention_count > 0 "
            "ORDER BY mention_count DESC LIMIT 10",
            (p["surname_metaphone"], person_id)
        ).fetchall()
        if sibs:
            print(f"\n  other canonicals sharing surname phonetic "
                  f"'{p['surname_metaphone']}' (kept SEPARATE):")
            for s in sibs:
                print(f"    #{s['person_id']:>6} {s['canonical_name'][:44]:44s} "
                      f"{s['mention_count']:>9,} mentions")
    db.close()


# ── stats ────────────────────────────────────────────────────────────────────
def cmd_stats(args):
    db = get_db()
    init_schema(db)

    n_canon = db.execute("SELECT COUNT(*) FROM canonical_person").fetchone()[0]
    n_mentions_rows = db.execute("SELECT COUNT(*) FROM person_mention").fetchone()[0]
    total_mentions = db.execute(
        "SELECT COALESCE(SUM(mention_count), 0) FROM person_mention").fetchone()[0]

    if not n_canon:
        print("canonical_person is empty — run `build` first.")
        db.close()
        return

    # mentions collapsed: 1 - (canonicals / distinct raw strings), i.e. how many
    # raw strings were folded away.
    collapse_ratio = 1 - (n_canon / n_mentions_rows) if n_mentions_rows else 0
    avg = total_mentions / n_canon if n_canon else 0

    conf = db.execute(
        "SELECT confidence, COUNT(*) c, COALESCE(SUM(mention_count),0) m "
        "FROM person_mention GROUP BY confidence").fetchall()
    method = db.execute(
        "SELECT match_method, COUNT(*) c FROM person_mention GROUP BY match_method "
        "ORDER BY c DESC").fetchall()

    top = db.execute(
        "SELECT person_id, canonical_name, seed_source, mention_count, doc_count "
        "FROM canonical_person ORDER BY mention_count DESC LIMIT 15").fetchall()

    print("\nPerson Resolution Stats")
    print("=" * 66)
    print(f"  distinct canonical persons : {n_canon:,}")
    print(f"  distinct raw strings       : {n_mentions_rows:,}")
    print(f"  total mentions             : {total_mentions:,}")
    print(f"  mentions/canonical (avg)   : {avg:,.1f}")
    print(f"  strings collapsed          : {collapse_ratio*100:.1f}%  "
          f"({n_mentions_rows - n_canon:,} of {n_mentions_rows:,} raw strings folded)")

    print("\n  confidence distribution (by raw-string count / mentions):")
    order = {"high": 0, "medium": 1, "low": 2}
    for r in sorted(conf, key=lambda x: order.get(x["confidence"], 9)):
        print(f"    {str(r['confidence']):8s} {r['c']:>8,} strings  {r['m']:>13,} mentions")

    print("\n  match methods (by raw-string count):")
    for r in method:
        print(f"    {str(r['match_method']):12s} {r['c']:>8,}")

    print("\n  top 15 canonicals by mention_count:")
    print(f"    {'#id':>7} {'canonical':42s} {'src':14s} {'mentions':>11s} {'docs':>9s}")
    for r in top:
        print(f"    {r['person_id']:>7} {r['canonical_name'][:42]:42s} "
              f"{str(r['seed_source'])[:14]:14s} {r['mention_count']:>11,} {r['doc_count']:>9,}")
    db.close()


# ── cli ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="seed + block + assign kabass person strings")
    b.add_argument("--limit", type=int, help="cap distinct kabass strings (testing)")
    b.add_argument("--reset", action="store_true",
                   help="clear canonical_person/person_mention/entity_crosswalk first")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("reconcile", help="stage candidate crosswalk to core entities")
    r.add_argument("--dry-run", action="store_true", default=True,
                   help="report only, write nothing (default)")
    r.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                   help="write candidate entity_crosswalk rows (sidecar only)")
    r.set_defaults(func=cmd_reconcile)

    lk = sub.add_parser("lookup", help="show the canonical cluster a name resolves to")
    lk.add_argument("name")
    lk.add_argument("--top", type=int, default=25, help="member rows to show")
    lk.add_argument("--all", action="store_true", help="show every member string")
    lk.set_defaults(func=cmd_lookup)

    st = sub.add_parser("stats", help="cluster/mention/confidence summary")
    st.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

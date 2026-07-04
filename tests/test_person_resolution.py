"""Behavior tests for the person-resolution builder (candidate identities).

Unit-level: the pure resolution surface — order-insensitive normalization,
title/initial stripping, surname/given tokenization, the bare-surname/initials
GUARDRAIL predicate, nickname equivalence, and the metaphone surname block.

Integration-level: run `person_resolution build` against a tiny fixture that
reproduces the Epstein-cluster problem in miniature (Jeffrey variants + OCR typo
+ surname-first + nickname + bare surname + initials, PLUS the Mark Epstein
distractor and the Edward Jay Epstein journalist), then assert the invariants the
task cares about:
  * Jeffrey's spelling/ordering/nickname variants collapse into ONE canonical.
  * MARK Epstein is kept SEPARATE (the distractor guardrail).
  * bare "Epstein" / "Mr. Epstein" / initials attach at LOW confidence, never
    high (the ambiguity guardrail), and land on the DOMINANT identity.
  * seed strings resolve at HIGH confidence.
  * every raw string is assigned (nothing dropped); counts reconcile.
  * `reconcile` maps a canonical onto an existing core entity and writes ONLY
    candidate crosswalk rows in the sidecar — never touches investigation.db.
"""

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


DERIVED = _load("epstein_derived_pr", "tools/epstein_derived.py")
PR = _load("person_resolution_t", "tools/person_resolution.py")


class NormalizationTests(unittest.TestCase):
    def test_order_insensitive_key(self):
        # surname-first ordering collapses to the same key as given-first.
        self.assertEqual(PR.normalize_person_name("Jeffrey Epstein"),
                         PR.normalize_person_name("Epstein Jeffrey"))
        self.assertEqual(PR.normalize_person_name("Jeffrey Epstein"),
                         PR.normalize_person_name("Epstein, Jeffrey"))

    def test_titles_and_middle_initial_folded(self):
        # "Mr." title stripped; a lone middle initial does not change the key.
        self.assertEqual(PR.normalize_person_name("Mr. Jeffrey Epstein"),
                         PR.normalize_person_name("Jeffrey Epstein"))
        self.assertEqual(PR.normalize_person_name("Jeffrey E. Epstein"),
                         PR.normalize_person_name("Jeffrey Epstein"))

    def test_mark_and_jeffrey_have_distinct_keys(self):
        # The distractor must NOT normalize onto Jeffrey.
        self.assertNotEqual(PR.normalize_person_name("Mark Lawrence Epstein"),
                            PR.normalize_person_name("Jeffrey Epstein"))

    def test_surname_and_given_tokens(self):
        self.assertEqual(PR.surname_token("Jeffrey Epstein"), "epstein")
        self.assertEqual(PR.given_token("Jeffrey Epstein"), "jeffrey")
        # surname is the last SUBSTANTIVE token; a trailing initial is ignored.
        self.assertEqual(PR.surname_token("Ghislaine N Maxwell"), "maxwell")

    def test_bare_and_initials_guardrail(self):
        # bare surname, title form, and initials are all "bare" -> LOW confidence.
        for s in ("Epstein", "Mr. Epstein", "JE", "J. Epstein", "Jeffrey E."):
            self.assertTrue(PR.is_bare_or_initials(s), s)
        # full multi-token names are NOT bare (incl. surname-first ordering).
        for s in ("Jeffrey Epstein", "Epstein Jeffrey", "Mark Lawrence Epstein"):
            self.assertFalse(PR.is_bare_or_initials(s), s)


class NicknameTests(unittest.TestCase):
    def test_seeded_diminutives(self):
        nm = PR.NicknameMap.load()
        self.assertTrue(nm.equivalent("jeff", "jeffrey"))
        self.assertTrue(nm.equivalent("rich", "richard"))
        self.assertTrue(nm.equivalent("les", "leslie"))
        self.assertFalse(nm.equivalent("mark", "jeffrey"))
        self.assertFalse(nm.equivalent("jeff", ""))

    def test_harvested_pairs_augment(self):
        # a real-world pair we didn't hardcode (Ace/Alan) can be injected.
        nm = PR.NicknameMap.load(extra_pairs=[("ace", "alan")])
        self.assertTrue(nm.equivalent("ace", "alan"))


class PhoneticTests(unittest.TestCase):
    def test_metaphone_folds_ocr_surname_variants(self):
        base = PR._metaphone("Epstein")
        self.assertTrue(base)  # backend produced a code
        self.assertEqual(base, PR._metaphone("Epsteen"))
        self.assertEqual(PR._metaphone("Maxwell"), PR._metaphone("Maxwel"))


def _make_source_dbs(tmp):
    """Tiny kabass + core DBs mirroring the columns the builder reads."""
    kab = tmp / "kab.db"
    core = tmp / "core.db"

    # --- kabass: persons (seed) + entities (raw mentions) ---
    k = sqlite3.connect(kab)
    k.executescript("""
        CREATE TABLE persons (data TEXT);
        CREATE TABLE entities (
            id TEXT, document_id TEXT, entity_type TEXT,
            value TEXT, normalized_value TEXT);
        CREATE TABLE curated_docs (
            id TEXT, subject TEXT, also_appears_as TEXT);
    """)
    # A seed for Jeffrey (with a nickname alias) and one for Mark — so the
    # distractor exists as a distinct curated identity too.
    persons = [
        {"canonical_name": "Jeffrey Epstein", "category": "perpetrator",
         "aliases": json.dumps(["Jeff Epstein"]),
         "search_terms": json.dumps(["Jeffrey Epstein", "Jeff Epstein", "Jeffrey E. Epstein"])},
        {"canonical_name": "Mark Epstein", "category": "associate",
         "aliases": json.dumps([]),
         "search_terms": json.dumps(["Mark Epstein", "Mark L. Epstein"])},
        {"canonical_name": "Ghislaine Maxwell", "category": "perpetrator",
         "aliases": json.dumps([]),
         "search_terms": json.dumps(["Ghislaine Maxwell"])},
        # a FOIA redaction placeholder that must be skipped as a seed.
        {"canonical_name": "(b) (6)", "category": "associate",
         "aliases": json.dumps([]), "search_terms": json.dumps(["(b) (6)"])},
    ]
    for p in persons:
        k.execute("INSERT INTO persons(data) VALUES (?)", (json.dumps(p),))

    # Raw mentions: (value, n_docs). Each is emitted n times across distinct docs.
    # Jeffrey family: canonical, OCR typo, surname-first, nickname, initials,
    #                 bare surname, title form.  Plus the Mark distractor and the
    #                 Edward Jay Epstein journalist (different person, same surname).
    raw = [
        ("Jeffrey Epstein", 50),
        ("Jefffrey Epstein", 8),      # OCR typo -> fuzzy
        ("Epstein Jeffrey", 6),       # surname-first -> exact_norm
        ("Jeff Epstein", 5),          # nickname -> nickname/seed
        ("Jeffrey E. Epstein", 4),    # middle initial -> exact_norm
        ("Jeffrey E.", 30),           # first-name + initial (bare) -> LOW
        ("Epstein", 12),              # bare surname -> LOW, dominant
        ("Mr. Epstein", 7),           # title form (bare) -> LOW, dominant
        ("Mark Epstein", 9),          # DISTRACTOR -> separate canonical
        ("Mark L. Epstein", 4),       # distractor variant -> Mark
        ("Edward Jay Epstein", 6),    # journalist -> separate canonical
        ("Ghislaine Maxwell", 20),
        ("Maxwell", 5),               # bare -> LOW, dominant Maxwell
    ]
    doc = 0
    for value, n in raw:
        for _ in range(n):
            doc += 1
            k.execute("INSERT INTO entities(id, document_id, entity_type, value) "
                      "VALUES (?, ?, 'person', ?)", (f"e{doc}", f"d{doc}", value))
    k.commit()
    k.close()

    # --- core investigation.db: a couple of entities + one alias ---
    c = sqlite3.connect(core)
    c.executescript("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            entity_type TEXT, jurisdiction TEXT, ein TEXT, address TEXT,
            status TEXT, source TEXT, notes TEXT);
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_name TEXT NOT NULL,
            alias TEXT NOT NULL, alias_type TEXT NOT NULL, entity_id INTEGER);
    """)
    c.execute("INSERT INTO entities(id, name, entity_type) VALUES (1, 'Jeffrey Epstein', 'person')")
    c.execute("INSERT INTO entities(id, name, entity_type) VALUES (2, 'Ghislaine Maxwell', 'person')")
    # a person_variant alias with an entity_id -> exercises the alias match path.
    c.execute("INSERT INTO name_aliases(canonical_name, alias, alias_type, entity_id) "
              "VALUES ('Ghislaine Maxwell', 'G. Maxwell', 'person_variant', 2)")
    c.commit()
    c.close()
    return kab, core


class BuilderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.derived = tmp / "derived.db"
        self.kab, self.core = _make_source_dbs(tmp)

        # Point the builder at the fixtures: patch the imported get_db + source
        # paths so the test NEVER touches the real datasets/investigation DBs.
        fixture = self.derived
        self._orig_get_db = PR.get_db
        PR.get_db = lambda path=fixture: DERIVED.get_db(fixture)
        self._orig_paths = (PR.KABASS_DB, PR.CORE_DB)
        PR.KABASS_DB, PR.CORE_DB = self.kab, self.core

    def tearDown(self):
        PR.get_db = self._orig_get_db
        PR.KABASS_DB, PR.CORE_DB = self._orig_paths
        self.tmp.cleanup()

    def _run(self, *argv):
        old = sys.argv
        sys.argv = ["person_resolution.py", *argv]
        try:
            PR.main()
        finally:
            sys.argv = old

    def _db(self):
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        return db

    def _canon_of(self, db, raw):
        r = db.execute(
            "SELECT cp.person_id, cp.canonical_name, cp.seed_source, "
            "       pm.confidence, pm.match_method "
            "FROM person_mention pm JOIN canonical_person cp ON cp.person_id = pm.canonical_id "
            "WHERE pm.raw_value = ?", (raw,)).fetchone()
        return r

    def test_jeffrey_variants_collapse(self):
        self._run("build")
        db = self._db()
        base = self._canon_of(db, "Jeffrey Epstein")
        self.assertIsNotNone(base)
        jeff_id = base["person_id"]
        # spelling / ordering / nickname / middle-initial variants all land on the
        # SAME canonical as "Jeffrey Epstein".
        for variant in ("Jefffrey Epstein", "Epstein Jeffrey", "Jeff Epstein",
                        "Jeffrey E. Epstein"):
            row = self._canon_of(db, variant)
            self.assertIsNotNone(row, variant)
            self.assertEqual(row["person_id"], jeff_id, f"{variant} did not collapse")
        db.close()

    def test_seed_is_high_confidence(self):
        self._run("build")
        db = self._db()
        self.assertEqual(self._canon_of(db, "Jeffrey Epstein")["confidence"], "high")
        db.close()

    def test_mark_distractor_kept_separate(self):
        self._run("build")
        db = self._db()
        jeff = self._canon_of(db, "Jeffrey Epstein")["person_id"]
        mark = self._canon_of(db, "Mark Epstein")
        self.assertIsNotNone(mark)
        self.assertNotEqual(mark["person_id"], jeff, "Mark collapsed into Jeffrey!")
        # Mark's own variant stays with Mark, not Jeffrey.
        self.assertEqual(self._canon_of(db, "Mark L. Epstein")["person_id"],
                         mark["person_id"])
        # the journalist is also separate from both.
        edward = self._canon_of(db, "Edward Jay Epstein")["person_id"]
        self.assertNotIn(edward, {jeff, mark["person_id"]})
        db.close()

    def test_bare_surname_low_confidence_on_dominant(self):
        self._run("build")
        db = self._db()
        jeff = self._canon_of(db, "Jeffrey Epstein")["person_id"]
        for bare in ("Epstein", "Mr. Epstein"):
            row = self._canon_of(db, bare)
            self.assertIsNotNone(row, bare)
            # GUARDRAIL: never high confidence.
            self.assertEqual(row["confidence"], "low", bare)
            # attaches to the DOMINANT (Jeffrey) identity, not the journalist.
            self.assertEqual(row["person_id"], jeff, f"{bare} did not go to dominant")
            self.assertEqual(row["match_method"], "bare_surname")
        db.close()

    def test_initials_stay_low(self):
        self._run("build")
        db = self._db()
        row = self._canon_of(db, "Jeffrey E.")
        self.assertIsNotNone(row)
        self.assertEqual(row["confidence"], "low")
        db.close()

    def test_every_string_assigned_and_counts_reconcile(self):
        self._run("build")
        db = self._db()
        n_raw_kab = sqlite3.connect(self.kab).execute(
            "SELECT COUNT(DISTINCT value) FROM entities WHERE entity_type='person'").fetchone()[0]
        n_mentions = db.execute("SELECT COUNT(*) FROM person_mention").fetchone()[0]
        self.assertEqual(n_mentions, n_raw_kab)  # nothing dropped
        # mention_count total == number of raw entity rows inserted.
        total = db.execute("SELECT SUM(mention_count) FROM person_mention").fetchone()[0]
        raw_rows = sqlite3.connect(self.kab).execute(
            "SELECT COUNT(*) FROM entities WHERE entity_type='person'").fetchone()[0]
        self.assertEqual(total, raw_rows)
        # canonical mention_count is the sum of its members'.
        agg = db.execute(
            "SELECT cp.mention_count, COALESCE(SUM(pm.mention_count),0) s "
            "FROM canonical_person cp LEFT JOIN person_mention pm "
            "ON pm.canonical_id = cp.person_id GROUP BY cp.person_id").fetchall()
        for r in agg:
            self.assertEqual(r["mention_count"], r["s"])
        db.close()

    def test_redaction_not_seeded(self):
        self._run("build")
        db = self._db()
        # "(b) (6)" must not become a seeded canonical_person.
        n = db.execute(
            "SELECT COUNT(*) FROM canonical_person WHERE canonical_name LIKE '%(b)%'").fetchone()[0]
        self.assertEqual(n, 0)
        db.close()

    def test_idempotent_rebuild(self):
        self._run("build")
        db = self._db()
        first = db.execute("SELECT COUNT(*) FROM canonical_person").fetchone()[0]
        first_m = db.execute("SELECT COUNT(*) FROM person_mention").fetchone()[0]
        db.close()
        self._run("build", "--reset")
        db = self._db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM canonical_person").fetchone()[0], first)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM person_mention").fetchone()[0], first_m)
        db.close()

    def test_reconcile_maps_core_and_stays_candidate(self):
        self._run("build")
        # dry-run writes nothing.
        self._run("reconcile")  # --dry-run is the default
        db = self._db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM entity_crosswalk").fetchone()[0], 0)
        db.close()
        # real run writes candidate rows into the SIDECAR only.
        self._run("reconcile", "--no-dry-run")
        db = self._db()
        xwalk = db.execute(
            "SELECT match_status, COUNT(*) c FROM entity_crosswalk GROUP BY match_status").fetchall()
        statuses = {r["match_status"]: r["c"] for r in xwalk}
        self.assertGreaterEqual(statuses.get("candidate", 0), 1)
        self.assertEqual(set(statuses) - {"candidate"}, set())  # ONLY candidate
        # Jeffrey Epstein canonical maps to core entity #1 (exact norm).
        jeff = self._canon_of(db, "Jeffrey Epstein")["person_id"]
        core_id = db.execute(
            "SELECT core_entity_id FROM entity_crosswalk WHERE derived_person_id = ?",
            (jeff,)).fetchone()
        self.assertIsNotNone(core_id)
        self.assertEqual(core_id[0], 1)
        db.close()

        # SAFETY: reconcile must NOT have written to the core fixture. The core
        # DB has no sidecar tables and its row counts are unchanged.
        c = sqlite3.connect(self.core)
        leaked = c.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name IN "
            "('canonical_person','person_mention','entity_crosswalk')").fetchone()[0]
        self.assertEqual(leaked, 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM entities").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM name_aliases").fetchone()[0], 1)
        c.close()

    def test_lookup_and_stats_run(self):
        # smoke: the reporting subcommands execute without error post-build.
        self._run("build")
        self._run("lookup", "Jeffrey Epstein")
        self._run("stats")


if __name__ == "__main__":
    unittest.main()

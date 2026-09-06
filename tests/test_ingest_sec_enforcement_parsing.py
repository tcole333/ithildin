"""Offline tests for SEC enforcement respondent-field parsing.

`enforcement_defendants` is built by splitting SEC's free-text respondent field,
which mixes actual parties with procedural role labels ("Relief Defendant") and
— for administrative proceedings — the name of the presiding administrative law
judge. Three parsing defects let that non-party text through as defendant rows,
which made `query_sec_enforcement.py repeat-offenders` rank parsing artifacts
("administrative law judge", "relief defendants", "jr") as its top results and
fed the same artifacts to `cross-ref --auto-leads`.

These tests pin the corpus rules that keep non-parties out of the defendant set:
role labels are never parties, a presiding judge is recorded as `presiding_alj`
rather than as a defendant, and a person suffix stays attached to its name.
"""

from __future__ import annotations

import sqlite3

import pytest

from tools import ingest_sec_enforcement as ing


def _names(raw, role="defendant"):
    """Raw names parsed out of `raw`, restricted to one role."""
    return [d["name_raw"] for d in ing.parse_defendants(raw) if d["role"] == role]


def _roles(raw):
    return {d["name_raw"]: d["role"] for d in ing.parse_defendants(raw)}


# ── Defect 1: person suffix rejoin ───────────────────────────


class TestPersonSuffixRejoin:
    """`et al.` stripping used to leave a stray period that broke the rejoin."""

    def test_jr_stays_attached_across_et_al(self):
        assert _names("Raymond J. Pirrello, Jr., et al.") == ["Raymond J. Pirrello, Jr."]

    def test_et_al_is_fully_stripped(self):
        # The trailing period of "al." must not survive as its own token.
        for name in _names("Raymond J. Pirrello, Jr., et al."):
            assert ".." not in name
            assert "al" not in name.lower().split()

    def test_et_al_still_flagged(self):
        parsed = ing.parse_defendants("Raymond J. Pirrello, Jr., et al.")
        assert all(d["is_et_al"] for d in parsed)

    @pytest.mark.parametrize(
        "raw",
        [
            "John A. Smith, Jr.",
            "John A. Smith, Jr., et al.",
            "John A. Smith, Jr. et al.",
            "John A. Smith, Sr., et. al.",
            "John A. Smith, III, et al",
        ],
    )
    def test_suffix_never_becomes_its_own_defendant(self, raw):
        names = _names(raw)
        assert len(names) == 1, names
        assert names[0].startswith("John A. Smith")

    def test_suffix_rejoin_without_et_al_unchanged(self):
        assert _names("John A. Smith, Jr.") == ["John A. Smith, Jr."]

    def test_stacked_suffixes_stay_attached(self):
        assert _names("Thomas Osmonde Russell, III Esq.") == [
            "Thomas Osmonde Russell, III Esq."
        ]

    def test_suffix_before_dba_stays_attached(self):
        # The comma belongs to the person's name, not to a new party.
        assert _names("Herman Ronnie Young, Jr. d/b/a Race Cycler") == [
            "Herman Ronnie Young, Jr.",
            "Race Cycler",
        ]

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # SEC's own malformed text: a suffix stranded after "and".
            ("Steven J. Manderfeld and Esq.", ["Steven J. Manderfeld"]),
            (
                "Donald J. Torbert, CPA, Nicole S. Stokes and CPA.",
                ["Donald J. Torbert, CPA", "Nicole S. Stokes"],
            ),
        ],
    )
    def test_stranded_suffix_is_dropped(self, raw, expected):
        assert _names(raw) == expected

    def test_no_suffix_only_party_survives(self):
        for raw in ["Herman Ronnie Young, Jr. d/b/a Race Cycler",
                    "Thomas Osmonde Russell, III Esq.",
                    "Steven J. Manderfeld and Esq.",
                    "Donald J. Torbert, CPA, Nicole S. Stokes and CPA."]:
            for d in ing.parse_defendants(raw):
                assert d["name_normalized"] not in {"jr", "sr", "ii", "iii", "iv",
                                                    "esq", "cpa", "c.p.a", "md"}


# ── Defect 2: procedural role labels ─────────────────────────


class TestRoleLabelsAreNotDefendants:
    ROLE_ONLY = [
        "Relief Defendant",
        "Relief Defendants",
        "Relief-Defendants",
        "Defendant",
        "Defendants",
        "defendants",
        "Respondent",
        "Respondents",
        "No Respondents",
        "Appellant",
        "Appellants",
        "Defendant-Appellant",
        "Administrative Law Judge",
        "Chief Administrative Law Judge",
    ]

    @pytest.mark.parametrize("label", ROLE_ONLY)
    def test_bare_role_label_yields_no_defendants(self, label):
        assert ing.parse_defendants(label) == []

    @pytest.mark.parametrize("label", ROLE_ONLY)
    def test_trailing_role_label_is_dropped(self, label):
        names = _names(f"The Seminar Solution, LLC, {label}")
        assert names == ["The Seminar Solution, LLC"]

    def test_whole_text_of_role_labels_yields_nothing(self):
        assert ing.parse_defendants("Relief Defendant, Relief Defendants") == []
        assert ing.parse_defendants(
            "Defendants Solely for Purposes of Equitable Relief"
        ) == []

    def test_role_word_inside_a_real_name_is_preserved(self):
        # Only an unambiguous boundary counts, so names are not truncated.
        assert _names("Movant Capital Partners LLC") == ["Movant Capital Partners LLC"]
        assert _names("Applicant Technologies Inc.") == ["Applicant Technologies Inc."]

    def test_trailing_role_label_after_semicolon(self):
        assert _names("Acme Holdings LLC; Relief Defendants") == ["Acme Holdings LLC"]

    def test_parenthetical_role_label_is_stripped_from_name(self):
        # Left glued on, "(Defendant)" corrupts name_normalized and splits the
        # same person across two repeat-offender rows.
        assert _names("Jonathan D. Nelson (Defendant)") == ["Jonathan D. Nelson"]

    def test_parenthetical_equitable_relief_clause_stripped(self):
        assert _names("Cayman Holdings Ltd. (Defendants Solely for Purposes of "
                      "Equitable Relief)") == ["Cayman Holdings Ltd."]

    def test_as_relief_defendant_form(self):
        assert _names("H. Constance Neff as Relief Defendant") == ["H. Constance Neff"]

    def test_role_label_prefixing_real_names(self):
        assert _names("Relief Defendants Tatiana Vorobieva and Anjali Walter") == [
            "Tatiana Vorobieva",
            "Anjali Walter",
        ]

    def test_trailing_role_label_after_and(self):
        assert _names("William L. Haynes and Relief Defendant") == ["William L. Haynes"]

    def test_role_label_mid_list_is_dropped(self):
        names = _names("Acme Corp., Defendants, John Q. Public")
        assert names == ["Acme Corp.", "John Q. Public"]

    def test_role_label_does_not_survive_as_person(self):
        for raw in ["The Seminar Solution, LLC, Relief Defendant",
                    "Acme Corp., Defendants, John Q. Public"]:
            for d in ing.parse_defendants(raw):
                assert "defendant" not in d["name_normalized"].lower()
                assert "respondent" not in d["name_normalized"].lower()


# ── Defect 3: presiding administrative law judge ─────────────


class TestPresidingJudge:
    def test_judge_run_together_with_party_is_split(self):
        raw = ("Phlo Corporation, James B. Hovis, Anne P. Hovis "
               "James T. Kelly, Administrative Law Judge")
        assert _names(raw) == ["Phlo Corporation", "James B. Hovis", "Anne P. Hovis"]

    def test_judge_recorded_under_presiding_alj_role(self):
        raw = ("Phlo Corporation, James B. Hovis, Anne P. Hovis "
               "James T. Kelly, Administrative Law Judge")
        assert _names(raw, role="presiding_alj") == ["James T. Kelly"]

    def test_judge_is_not_a_defendant(self):
        raw = ("Phlo Corporation, James B. Hovis, Anne P. Hovis "
               "James T. Kelly, Administrative Law Judge")
        assert _roles(raw)["James T. Kelly"] == "presiding_alj"

    def test_semicolon_separated_judge(self):
        raw = "Marc N. Geman; G. Marvin Bober, Administrative Law Judge"
        assert _names(raw) == ["Marc N. Geman"]
        assert _names(raw, role="presiding_alj") == ["G. Marvin Bober"]

    def test_chief_administrative_law_judge(self):
        raw = ("Steven E. Muth, Richard J. Rouse, and Bruce J. Bates "
               "Brenda P. Murray, Chief Administrative Law Judge")
        assert _names(raw) == ["Steven E. Muth", "Richard J. Rouse", "Bruce J. Bates"]
        assert _names(raw, role="presiding_alj") == ["Brenda P. Murray"]

    def test_judge_split_after_entity_suffix(self):
        raw = "Phlo Corporation Carol Fox Foelak, Administrative Law Judge"
        assert _names(raw) == ["Phlo Corporation"]
        assert _names(raw, role="presiding_alj") == ["Carol Fox Foelak"]

    def test_judge_split_after_et_al(self):
        raw = "Sunwest Management, Inc., et al. Robert G. Mahony, Administrative Law Judge"
        assert _names(raw) == ["Sunwest Management, Inc."]
        assert _names(raw, role="presiding_alj") == ["Robert G. Mahony"]

    def test_judge_split_after_person_suffix(self):
        raw = "John A. Smith, Jr. Cameron Elliot, Administrative Law Judge"
        assert _names(raw) == ["John A. Smith, Jr."]
        assert _names(raw, role="presiding_alj") == ["Cameron Elliot"]

    def test_known_misspelling_maps_to_canonical_judge(self):
        raw = "Monetta Financial Services, Inc.; Brenda P. Murrary, Chief Administrative Law Judge"
        assert _names(raw, role="presiding_alj") == ["Brenda P. Murray"]

    def test_judge_only_text_yields_no_defendants(self):
        raw = "Carol Fox Foelak, Administrative Law Judge"
        assert _names(raw) == []
        assert _names(raw, role="presiding_alj") == ["Carol Fox Foelak"]

    def test_unknown_judge_drops_label_without_guessing_the_split(self):
        # Under-claim rather than misattribute: with no roster match we cannot
        # tell where the party name ends, so no ALJ is recorded.
        raw = "Acme Capital LLC, Someone A. Unknown, Administrative Law Judge"
        assert _names(raw, role="presiding_alj") == []
        assert "Administrative Law Judge" not in " ".join(_names(raw))

    def test_judge_never_flagged_et_al(self):
        raw = "Sunwest Management, Inc., et al. Robert G. Mahony, Administrative Law Judge"
        judges = [d for d in ing.parse_defendants(raw) if d["role"] == "presiding_alj"]
        assert judges and not any(d["is_et_al"] for d in judges)


# ── d/b/a handling (latent mutation-during-iteration bug) ────


class TestDoingBusinessAs:
    def test_dba_yields_both_names(self):
        assert _names("Acme Corp. d/b/a Acme Trading, Jane Roe") == [
            "Acme Corp.",
            "Jane Roe",
            "Acme Trading",
        ]

    def test_bare_dba_keeps_trade_name(self):
        assert _names("d/b/a Acme Trading") == ["Acme Trading"]

    def test_dba_chain_terminates(self):
        # Guards the rewritten worklist against re-queueing forever.
        assert "Gamma Trading" in _names("Alpha Corp. d/b/a Beta LLC d/b/a Gamma Trading")


# ── Regression: previously-correct behaviour ─────────────────


class TestNoRegressions:
    def test_entity_suffix_token_rejoined(self):
        assert _names("Power Up Lending Group, Ltd., Curt Kramer") == [
            "Power Up Lending Group, Ltd.",
            "Curt Kramer",
        ]

    def test_and_split_keeps_person(self):
        assert "Fabrice Tourre" in _names("Goldman, Sachs & Co. and Fabrice Tourre")

    def test_empty_input(self):
        assert ing.parse_defendants("") == []
        assert ing.parse_defendants(None) == []
        assert ing.parse_defendants("   ") == []

    def test_classification_preserved(self):
        parsed = {d["name_raw"]: d["defendant_type"]
                  for d in ing.parse_defendants("Phlo Corporation, James B. Hovis")}
        assert parsed["Phlo Corporation"] == "entity"
        assert parsed["James B. Hovis"] == "person"

    def test_every_result_carries_a_role(self):
        raw = ("Phlo Corporation, James B. Hovis, Anne P. Hovis "
               "James T. Kelly, Administrative Law Judge")
        assert all(d["role"] in {"defendant", "presiding_alj"}
                   for d in ing.parse_defendants(raw))

    def test_no_duplicate_normalized_names(self):
        parsed = ing.parse_defendants("Acme Corp., Acme Corp., John Q. Public")
        norms = [d["name_normalized"] for d in parsed]
        assert len(norms) == len(set(norms))


# ── Schema + persistence ─────────────────────────────────────


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "DB_PATH", tmp_path / "sec.db")
    connection = ing.get_db()
    yield connection
    connection.close()


class TestSchema:
    def test_role_column_exists_and_defaults_to_defendant(self, db):
        cols = {r[1]: r for r in db.execute("PRAGMA table_info(enforcement_defendants)")}
        assert "role" in cols
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-1', 'admin', '2005-01-01', 'Doe')"""
        )
        db.execute(
            """INSERT INTO enforcement_defendants
               (action_id, name_raw, name_normalized) VALUES (1, 'Doe', 'doe')"""
        )
        assert db.execute("SELECT role FROM enforcement_defendants").fetchone()[0] == "defendant"

    def test_matches_cascade_on_defendant_delete(self, db):
        """Without ON DELETE CASCADE, `reparse` fails once matches exist."""
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-2', 'admin', '2005-01-01', 'Doe')"""
        )
        db.execute(
            """INSERT INTO enforcement_defendants
               (action_id, name_raw, name_normalized) VALUES (1, 'Doe', 'doe')"""
        )
        db.execute(
            """INSERT INTO enforcement_matches
               (defendant_id, match_source, match_source_id, match_name,
                match_type, match_score)
               VALUES (1, 'investigation', 7, 'Doe', 'exact', 1.0)"""
        )
        db.commit()
        db.execute("DELETE FROM enforcement_defendants")
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM enforcement_matches").fetchone()[0] == 0

    def test_role_migration_is_idempotent(self, db):
        before = db.execute("SELECT COUNT(*) FROM pragma_table_info('enforcement_defendants')").fetchone()[0]
        db.close()
        again = ing.get_db()
        after = again.execute(
            "SELECT COUNT(*) FROM pragma_table_info('enforcement_defendants')"
        ).fetchone()[0]
        again.close()
        assert before == after


class TestReparsePersistsRoles:
    def test_reparse_stores_judge_as_presiding_alj(self, db):
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-3', 'admin', '2005-01-01', ?)""",
            ("Phlo Corporation, James B. Hovis, Anne P. Hovis "
             "James T. Kelly, Administrative Law Judge",),
        )
        db.commit()
        ing.reparse_defendants(db)

        rows = {r["name_raw"]: r["role"] for r in db.execute(
            "SELECT name_raw, role FROM enforcement_defendants"
        )}
        assert rows == {
            "Phlo Corporation": "defendant",
            "James B. Hovis": "defendant",
            "Anne P. Hovis": "defendant",
            "James T. Kelly": "presiding_alj",
        }

    def test_reparse_drops_role_label_rows(self, db):
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-4', 'admin', '2005-01-01',
                       'The Seminar Solution, LLC, Relief Defendant')"""
        )
        db.commit()
        ing.reparse_defendants(db)
        names = [r[0] for r in db.execute("SELECT name_raw FROM enforcement_defendants")]
        assert names == ["The Seminar Solution, LLC"]

    def test_reparse_survives_existing_matches(self, db):
        """Reparse must not abort on the enforcement_matches foreign key."""
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-5', 'admin', '2005-01-01', 'Acme Corp., John Q. Public')"""
        )
        db.commit()
        ing.reparse_defendants(db)
        did = db.execute("SELECT id FROM enforcement_defendants LIMIT 1").fetchone()[0]
        db.execute(
            """INSERT INTO enforcement_matches
               (defendant_id, match_source, match_source_id, match_name,
                match_type, match_score)
               VALUES (?, 'investigation', 7, 'Acme Corp.', 'exact', 1.0)""",
            (did,),
        )
        db.commit()

        ing.reparse_defendants(db)  # must not raise sqlite3.IntegrityError
        assert db.execute("SELECT COUNT(*) FROM enforcement_defendants").fetchone()[0] == 2

    def test_fts_stays_queryable_after_reparse(self, db):
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-6', 'admin', '2005-01-01', 'Acme Corp., John Q. Public')"""
        )
        db.commit()
        ing.reparse_defendants(db)
        hits = db.execute(
            """SELECT ed.name_raw FROM enforcement_defendants ed
               JOIN enforcement_defendants_fts f ON ed.id = f.rowid
               WHERE enforcement_defendants_fts MATCH 'Public'"""
        ).fetchall()
        assert [h[0] for h in hits] == ["John Q. Public"]


class TestRosterIntegrity:
    def test_roster_maps_to_canonical_spellings(self):
        canonical = set(ing.ALJ_ROSTER.values())
        assert "Brenda P. Murray" in canonical
        assert "Brenda P. Murrary" not in canonical

    def test_roster_lookup_is_longest_first(self):
        # A short roster name must not shadow a longer one sharing its tail.
        order = ing._alj_roster_by_length()
        assert order == sorted(order, key=len, reverse=True)


class TestSqliteIntegrityGuard:
    def test_insert_requires_known_role(self, db):
        db.execute(
            """INSERT INTO enforcement_actions
               (release_number, source_type, date_published, respondent_text)
               VALUES ('34-7', 'admin', '2005-01-01', 'Doe')"""
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO enforcement_defendants
                   (action_id, name_raw, name_normalized, role)
                   VALUES (1, 'Doe', 'doe', 'bogus_role')"""
            )

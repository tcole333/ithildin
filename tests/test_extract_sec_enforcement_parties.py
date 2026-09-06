"""Offline safety tests for staged SEC party extraction.

The extractor is intentionally a quarantine boundary: model output must remain
source anchored, ambiguous or incomplete rosters must require review, and the
canonical SEC database must never be mutated.  These tests use only temporary
SQLite fixtures and stubbed Codex subprocesses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tools import extract_sec_enforcement_parties as ext


def _evidence(
    respondent_text: str,
    *,
    support_excerpt: str = "",
    source_type: str = "admin",
) -> dict:
    input_id = hashlib.sha256(respondent_text.encode()).hexdigest()
    return {
        "input_id": input_id,
        "respondent_text": respondent_text,
        "support_excerpt": support_excerpt,
        "source_type": source_type,
    }


def _mention(
    source_span: str,
    *,
    name: str | None = None,
    display_name: str | None = None,
    party_type: str = "person",
    role: str = "respondent",
    qualifiers: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    confidence: str = "high",
    certainty: str = "explicit",
    caption_evidence_text: str | None = None,
) -> dict:
    name = source_span if name is None else name
    return {
        "source_span": source_span,
        "name_verbatim": name,
        "display_name": name if display_name is None else display_name,
        "party_type": party_type,
        "role": role,
        "qualifiers": list(qualifiers),
        "aliases": list(aliases),
        "confidence": confidence,
        "certainty": certainty,
        "caption_evidence_text": caption_evidence_text,
    }


def _record(
    evidence: dict,
    parties: list[dict],
    *,
    nonparties: list[dict] | None = None,
    unresolved_spans: list[str] | None = None,
    ambiguity_reason: str | None = None,
) -> dict:
    return {
        "input_id": evidence["input_id"],
        "parties": parties,
        "nonparties": nonparties or [],
        "unresolved_spans": unresolved_spans or [],
        "ambiguity_reason": ambiguity_reason,
    }


@pytest.mark.parametrize(
    ("respondent_text", "support_excerpt", "parties"),
    [
        (
            "Bandimere, David F. Young, John O.",
            "DAVID F. BANDIMERE\nJOHN O. YOUNG",
            [
                _mention(
                    "Bandimere, David F.",
                    name="Bandimere, David F.",
                    display_name="David F. Bandimere",
                    caption_evidence_text="DAVID F. BANDIMERE",
                ),
                _mention(
                    "Young, John O.",
                    name="Young, John O.",
                    display_name="John O. Young",
                    caption_evidence_text="JOHN O. YOUNG",
                ),
            ],
        ),
        (
            "Briner, John, Esq. Dalmy, Diane. Esq.",
            "JOHN BRINER\nDIANE DALMY",
            [
                _mention(
                    "Briner, John, Esq.",
                    name="Briner, John",
                    display_name="John Briner",
                    qualifiers=("Esq.",),
                    caption_evidence_text="JOHN BRINER",
                ),
                _mention(
                    "Dalmy, Diane. Esq.",
                    name="Dalmy, Diane.",
                    display_name="Diane Dalmy",
                    qualifiers=("Esq.",),
                    caption_evidence_text="DIANE DALMY",
                ),
            ],
        ),
        (
            "Goldman, Sachs & Co. and Fabrice Tourre",
            "",
            [
                _mention(
                    "Goldman, Sachs & Co.",
                    party_type="entity",
                ),
                _mention("Fabrice Tourre"),
            ],
        ),
        (
            "Banco Santander, S.A.",
            "",
            [
                _mention(
                    "Banco Santander, S.A.",
                    party_type="entity",
                )
            ],
        ),
    ],
    ids=["bandimere", "briner", "goldman", "banco-santander"],
)
def test_known_problem_rosters_validate_only_with_exact_complete_spans(
    respondent_text,
    support_excerpt,
    parties,
):
    evidence = _evidence(
        respondent_text,
        support_excerpt=support_excerpt,
    )

    validation = ext.validate_record(_record(evidence, parties), evidence)

    assert validation == {
        "status": "valid",
        "fatal_errors": [],
        "review_reasons": [],
        "uncovered_text": "",
        "uncovered_tokens": [],
    }


def test_hallucinated_name_is_invalid_even_when_span_is_source_anchored():
    evidence = _evidence("Bandimere, David F. Young, John O.")
    record = _record(
        evidence,
        [
            _mention(
                "Bandimere, David F.",
                name="David Z. Bandimere",
            ),
            _mention("Young, John O."),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "invalid"
    assert any(
        "name_verbatim is not an exact source_span substring" in error
        for error in validation["fatal_errors"]
    )


def test_exact_but_fabricated_weld_is_quarantined_as_uncovered():
    evidence = _evidence("Bandimere, David F. Young, John O.")
    record = _record(
        evidence,
        [
            _mention("David F. Young"),
            _mention("John O."),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert "Bandimere" in validation["uncovered_tokens"]
    assert any(
        reason.startswith("uncovered_roster_text:")
        for reason in validation["review_reasons"]
    )


@pytest.mark.parametrize(
    ("respondent_text", "name", "expected_error"),
    [
        (
            "John A. Smith, Jr.",
            "John A. Smith",
            "generational suffix was not preserved",
        ),
        (
            "Banco Santander, S.A.",
            "Banco Santander",
            "entity legal form was not preserved",
        ),
    ],
)
def test_identity_suffix_or_legal_form_cannot_be_dropped(
    respondent_text,
    name,
    expected_error,
):
    evidence = _evidence(respondent_text)
    record = _record(
        evidence,
        [
            _mention(
                respondent_text,
                name=name,
                display_name=name,
                party_type="entity" if "Banco" in respondent_text else "person",
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "invalid"
    assert any(
        expected_error in error for error in validation["fatal_errors"]
    )


def test_strict_name_key_keeps_identity_suffixes_and_legal_forms_distinct():
    assert ext.strict_name_key("Harold W. Andrews, Sr.") != ext.strict_name_key(
        "Harold W. Andrews, Jr."
    )
    assert ext.strict_name_key("Acme, Inc.") != ext.strict_name_key("Acme, LLC")


def test_explicit_unresolved_span_is_quarantined_even_with_full_coverage():
    evidence = _evidence("Acme LLC and Mystery Holdings")
    record = _record(
        evidence,
        [_mention("Acme LLC", party_type="entity")],
        unresolved_spans=["Mystery Holdings"],
        ambiguity_reason="The flat roster does not expose the second boundary.",
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert validation["fatal_errors"] == []
    assert validation["uncovered_tokens"] == []
    assert "record contains unresolved roster spans" in validation["review_reasons"]
    assert "record contains an ambiguity reason" in validation["review_reasons"]


def test_unreported_roster_words_are_quarantined():
    evidence = _evidence("Acme LLC and John Q. Public")
    record = _record(
        evidence,
        [_mention("Acme LLC", party_type="entity")],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert validation["uncovered_tokens"] == ["John", "Q", "Public"]


def test_single_mention_cannot_auto_validate_a_boundary_risk_roster():
    evidence = _evidence("Bandimere, David F. Young, John O.")
    record = _record(
        evidence,
        [
            _mention(
                evidence["respondent_text"],
                party_type="unknown",
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        reason.startswith("single mention covers a boundary-risk roster:")
        for reason in validation["review_reasons"]
    )


def test_named_roster_cannot_auto_validate_as_all_nonparties():
    evidence = _evidence("Alice Example and Bob Example")
    record = _record(
        evidence,
        [],
        nonparties=[
            _mention("Alice Example", role="staff"),
            _mention("Bob Example", role="staff"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert "record extracted no parties from a named roster" in (
        validation["review_reasons"]
    )


def test_supported_boundary_requires_caption_text_for_that_name():
    evidence = _evidence(
        "Bandimere, David F. Young, John O.",
        support_excerpt="DAVID F. BANDIMERE and JOHN O. YOUNG",
    )
    record = _record(
        evidence,
        [
            _mention(
                "Bandimere, David F.",
                display_name="David F. Bandimere",
                certainty="supported",
                caption_evidence_text="JOHN O. YOUNG",
            ),
            _mention("Young, John O.", display_name="John O. Young"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "invalid"
    assert any(
        "caption evidence does not contain the display name tokens" in error
        for error in validation["fatal_errors"]
    )


@pytest.mark.parametrize(
    ("respondent_text", "mention", "reason_fragment"),
    [
        (
            "Alice Smith and Bob Jones",
            _mention("Alice Smith and Bob Jones"),
            "boundary-risk signals",
        ),
        (
            "Alice Smith, Bob Jones",
            _mention("Alice Smith, Bob Jones"),
            "boundary-risk signals",
        ),
        (
            "Goldman, Sachs & Co.",
            _mention(
                "Goldman, Sachs & Co.",
                display_name="Co & Sachs Goldman",
                party_type="entity",
            ),
            "entity display_name reorders",
        ),
        (
            "Mystery Name",
            _mention("Mystery Name", party_type="unknown"),
            "party_type is unknown",
        ),
    ],
)
def test_semantically_risky_exact_spans_are_quarantined(
    respondent_text,
    mention,
    reason_fragment,
):
    evidence = _evidence(respondent_text)

    validation = ext.validate_record(_record(evidence, [mention]), evidence)

    assert validation["status"] == "needs_review"
    assert any(
        reason_fragment in reason for reason in validation["review_reasons"]
    )


def test_name_elsewhere_in_roster_cannot_be_attached_as_an_alias():
    evidence = _evidence("John Smith and Jane Doe")
    record = _record(
        evidence,
        [
            _mention("John Smith", aliases=("Jane Doe",)),
            _mention("Jane Doe"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        "alias is not part of this roster span" in reason
        for reason in validation["review_reasons"]
    )


def test_trade_name_must_be_decomposed_and_alias_legal_form_is_preserved():
    evidence = _evidence("John Smith d/b/a Acme Consulting, LLC")

    fused = ext.validate_record(
        _record(
            evidence,
            [
                _mention(
                    evidence["respondent_text"],
                    party_type="person",
                )
            ],
        ),
        evidence,
    )
    decomposed = ext.validate_record(
        _record(
            evidence,
            [
                _mention(
                    evidence["respondent_text"],
                    name="John Smith",
                    display_name="John Smith",
                    aliases=("Acme Consulting, LLC",),
                    party_type="person",
                )
            ],
        ),
        evidence,
    )

    assert fused["status"] == "needs_review"
    assert any(
        "cue lacks an assigned alias" in reason
        for reason in fused["review_reasons"]
    )
    assert decomposed == {
        "status": "valid",
        "fatal_errors": [],
        "review_reasons": [],
        "uncovered_text": "",
        "uncovered_tokens": [],
    }


def test_now_known_as_and_dotted_foreign_legal_form_validate():
    alias_evidence = _evidence(
        "Old Holdings, Inc. n/k/a New Holdings B.V."
    )
    bv_evidence = _evidence("Example Holdings B.V.")

    alias_validation = ext.validate_record(
        _record(
            alias_evidence,
            [
                _mention(
                    alias_evidence["respondent_text"],
                    name="Old Holdings, Inc.",
                    display_name="Old Holdings, Inc.",
                    aliases=("New Holdings B.V.",),
                    party_type="entity",
                )
            ],
        ),
        alias_evidence,
    )
    bv_validation = ext.validate_record(
        _record(
            bv_evidence,
            [
                _mention(
                    "Example Holdings B.V.",
                    party_type="entity",
                )
            ],
        ),
        bv_evidence,
    )

    assert alias_validation["status"] == "valid"
    assert bv_validation["status"] == "valid"


def test_credentials_and_entity_descriptors_are_nonidentity_qualifiers():
    cpa_evidence = _evidence(
        "Richard P. Scalzo, C.P.A.",
        source_type="litigation",
    )
    descriptor_evidence = _evidence(
        "Madison Real Estate Group, LLC, a Wyoming limited liability company",
        source_type="litigation",
    )
    ca_evidence = _evidence(
        "Erez Bahar, C.A.",
        source_type="litigation",
    )

    cpa_validation = ext.validate_record(
        _record(
            cpa_evidence,
            [
                _mention(
                    cpa_evidence["respondent_text"],
                    name="Richard P. Scalzo",
                    display_name="Richard P. Scalzo",
                    qualifiers=("C.P.A.",),
                    role="defendant",
                )
            ],
        ),
        cpa_evidence,
    )
    descriptor_validation = ext.validate_record(
        _record(
            descriptor_evidence,
            [
                _mention(
                    descriptor_evidence["respondent_text"],
                    name="Madison Real Estate Group, LLC",
                    display_name="Madison Real Estate Group, LLC",
                    party_type="entity",
                    qualifiers=("a Wyoming limited liability company",),
                    role="defendant",
                )
            ],
        ),
        descriptor_evidence,
    )
    ca_validation = ext.validate_record(
        _record(
            ca_evidence,
            [
                _mention(
                    ca_evidence["respondent_text"],
                    name="Erez Bahar",
                    display_name="Erez Bahar",
                    qualifiers=("C.A.",),
                    role="defendant",
                )
            ],
        ),
        ca_evidence,
    )

    assert cpa_validation["status"] == "valid"
    assert descriptor_validation["status"] == "valid"
    assert ca_validation["status"] == "valid"


def test_person_form_roster_is_quarantined_when_support_defines_entity_alias():
    evidence = _evidence(
        "Afame, Onwuka",
        support_excerpt=(
            'against Onwuka Afame ("Respondent" or the "Afame Trust"). '
            "The Afame Trust registered as a transfer agent."
        ),
    )
    record = _record(
        evidence,
        [
            _mention(
                "Afame, Onwuka",
                display_name="Onwuka Afame",
                party_type="person",
            )
        ],
    )

    validation = ext.validate_record(record, evidence)
    entity_validation = ext.validate_record(
        _record(
            evidence,
            [
                _mention(
                    "Afame, Onwuka",
                    display_name="Afame, Onwuka",
                    party_type="entity",
                )
            ],
        ),
        evidence,
    )

    assert validation["status"] == "needs_review"
    assert any(
        "organization-form respondent alias" in reason
        for reason in validation["review_reasons"]
    )
    assert entity_validation["status"] == "valid"


def test_unrelated_company_alias_does_not_retype_nearby_people():
    evidence = _evidence(
        "William H. Warner and Robert J. Quigley",
        support_excerpt=(
            "WILLIAM H. WARNER and ROBERT J. QUIGLEY, Respondents. "
            'International Trading Business ("ITB" or "the company") '
            "conducted the transactions."
        ),
    )
    record = _record(
        evidence,
        [
            _mention("William H. Warner"),
            _mention("Robert J. Quigley"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_whitespace_only_boundary_requires_direct_caption_support():
    evidence = _evidence("John Ronald Reuel Tolkien")
    record = _record(
        evidence,
        [
            _mention("John Ronald"),
            _mention("Reuel Tolkien"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        reason.startswith("whitespace_only_boundary")
        for reason in validation["review_reasons"]
    )

    whole_name_caption = _evidence(
        "John Ronald Reuel Tolkien",
        support_excerpt="John Ronald Reuel Tolkien",
    )
    whole_name_validation = ext.validate_record(
        _record(
            whole_name_caption,
            [
                _mention(
                    "John Ronald",
                    caption_evidence_text="John Ronald Reuel Tolkien",
                ),
                _mention(
                    "Reuel Tolkien",
                    caption_evidence_text="John Ronald Reuel Tolkien",
                ),
            ],
        ),
        whole_name_caption,
    )
    assert whole_name_validation["status"] == "needs_review"


def test_trailing_list_delimiter_supports_adjacent_party_boundary():
    evidence = _evidence("Alice Smith, Bob Jones")
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith, ",
                name="Alice Smith",
                display_name="Alice Smith",
            ),
            _mention("Bob Jones"),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_leading_list_delimiter_supports_adjacent_party_boundary():
    evidence = _evidence("Alice Smith and Bob Jones")
    record = _record(
        evidence,
        [
            _mention("Alice Smith"),
            _mention(
                " and Bob Jones",
                name="Bob Jones",
                display_name="Bob Jones",
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_collective_caption_requires_an_explicit_name_separator():
    evidence = _evidence(
        "Alice Smith Bob Jones",
        support_excerpt="RESPONDENTS Alice Smith and Bob Jones",
    )
    collective_caption = "Alice Smith and Bob Jones"
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith",
                caption_evidence_text=collective_caption,
            ),
            _mention(
                "Bob Jones",
                caption_evidence_text=collective_caption,
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_collective_caption_suffix_is_local_to_the_named_party():
    evidence = _evidence(
        "Alice Smith Bob Jones II",
        support_excerpt="RESPONDENTS Alice Smith and Bob Jones II",
    )
    collective_caption = "Alice Smith and Bob Jones II"
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith",
                caption_evidence_text=collective_caption,
            ),
            _mention(
                "Bob Jones II",
                caption_evidence_text=collective_caption,
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_collective_caption_detects_a_local_missing_suffix():
    evidence = _evidence(
        "Alice Smith Bob Jones",
        support_excerpt="RESPONDENTS Alice Smith and Bob Jones II",
    )
    collective_caption = "Alice Smith and Bob Jones II"
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith",
                caption_evidence_text=collective_caption,
            ),
            _mention(
                "Bob Jones",
                caption_evidence_text=collective_caption,
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        "support caption contains an additional identity suffix" in reason
        for reason in validation["review_reasons"]
    )


def test_nonparty_caption_may_include_its_exact_role_label():
    evidence = _evidence(
        "Alice Smith Carol Fox Foelak, Administrative Law Judge",
        support_excerpt=(
            "Alice Smith\n"
            "Carol Fox Foelak, Administrative Law Judge"
        ),
    )
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith",
                caption_evidence_text="Alice Smith",
            ),
        ],
        nonparties=[
            _mention(
                "Carol Fox Foelak, Administrative Law Judge",
                name="Carol Fox Foelak",
                display_name="Carol Fox Foelak",
                role="presiding_alj",
                qualifiers=("Administrative Law Judge",),
                caption_evidence_text=(
                    "Carol Fox Foelak, Administrative Law Judge"
                ),
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_recognized_document_annotation_is_nonidentity_roster_glue():
    evidence = _evidence("Alice Smith (Corrected)")
    record = _record(
        evidence,
        [
            _mention(
                evidence["respondent_text"],
                name="Alice Smith",
                display_name="Alice Smith",
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_exact_party_role_label_may_be_recorded_as_a_qualifier():
    evidence = _evidence(
        "Alice Smith, As Relief Defendant",
        source_type="litigation",
    )
    record = _record(
        evidence,
        [
            _mention(
                evidence["respondent_text"],
                name="Alice Smith",
                display_name="Alice Smith",
                role="relief_defendant",
                qualifiers=("As Relief Defendant",),
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_alias_cue_may_be_redundantly_recorded_as_a_qualifier():
    evidence = _evidence("Alpha Corp. f/k/a Beta Corp.")
    record = _record(
        evidence,
        [
            _mention(
                evidence["respondent_text"],
                name="Alpha Corp.",
                display_name="Alpha Corp.",
                party_type="entity",
                qualifiers=("f/k/a",),
                aliases=("Beta Corp.",),
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_near_duplicate_cpa_person_and_firm_forms_require_review():
    evidence = _evidence(
        "Michael T. Remus, CPA and Michael Remus CPA",
        support_excerpt=(
            "MICHAEL T. REMUS, CPA, AND\n"
            "MICHAEL REMUS CPA"
        ),
    )
    record = _record(
        evidence,
        [
            _mention(
                "Michael T. Remus, CPA",
                name="Michael T. Remus",
                display_name="Michael T. Remus",
                qualifiers=("CPA",),
                caption_evidence_text="MICHAEL T. REMUS, CPA",
            ),
            _mention(
                "Michael Remus CPA",
                name="Michael Remus",
                display_name="Michael Remus",
                qualifiers=("CPA",),
                caption_evidence_text="MICHAEL REMUS CPA",
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        "unpunctuated form may be a firm" in reason
        for reason in validation["review_reasons"]
    )


def test_mixed_defendant_roles_require_exact_local_role_evidence():
    evidence = _evidence(
        "Alice Smith, Bob Jones and Carol Doe",
        source_type="aaer",
        support_excerpt="Carol Doe, as a relief defendant",
    )
    record = _record(
        evidence,
        [
            _mention(
                "Alice Smith, ",
                name="Alice Smith",
                display_name="Alice Smith",
                role="defendant",
            ),
            _mention(
                "Bob Jones and ",
                name="Bob Jones",
                display_name="Bob Jones",
                role="defendant",
            ),
            _mention(
                "Carol Doe",
                role="relief_defendant",
                certainty="supported",
                caption_evidence_text=(
                    "Carol Doe, as a relief defendant"
                ),
            ),
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        "mixed defendant/relief-defendant roster" in reason
        for reason in validation["review_reasons"]
    )


def test_exceptional_party_role_requires_exact_role_evidence():
    unsupported = _evidence("John Smith", source_type="admin")
    supported = _evidence(
        "John Smith",
        source_type="admin",
        support_excerpt="RELIEF DEFENDANT JOHN SMITH",
    )

    unsupported_validation = ext.validate_record(
        _record(
            unsupported,
            [_mention("John Smith", role="relief_defendant")],
        ),
        unsupported,
    )
    supported_validation = ext.validate_record(
        _record(
            supported,
            [
                _mention(
                    "John Smith",
                    role="relief_defendant",
                    caption_evidence_text="RELIEF DEFENDANT JOHN SMITH",
                )
            ],
        ),
        supported,
    )

    assert unsupported_validation["status"] == "needs_review"
    assert any(
        "relief_defendant role lacks an exact role label" in reason
        for reason in unsupported_validation["review_reasons"]
    )
    assert supported_validation["status"] == "valid"


def test_source_type_default_party_roles_are_enforced():
    litigation = _evidence(
        "John Smith",
        source_type="litigation",
    )

    expected = ext.validate_record(
        _record(
            litigation,
            [_mention("John Smith", role="defendant")],
        ),
        litigation,
    )
    unsupported_exception = ext.validate_record(
        _record(
            litigation,
            [_mention("John Smith", role="respondent")],
        ),
        litigation,
    )

    assert expected["status"] == "valid"
    assert unsupported_exception["status"] == "needs_review"
    assert any(
        "exceptional for litigation" in reason
        for reason in unsupported_exception["review_reasons"]
    )


def test_aaer_role_follows_proceeding_context():
    administrative = _evidence(
        "Michael P. Toups",
        source_type="aaer",
        support_excerpt=(
            "ADMINISTRATIVE PROCEEDING\n"
            "In the Matter of Michael P. Toups, Respondent."
        ),
    )
    litigation = _evidence(
        "John Smith",
        source_type="aaer",
        support_excerpt=(
            "Securities and Exchange Commission v. John Smith\nDefendant"
        ),
    )

    administrative_valid = ext.validate_record(
        _record(
            administrative,
            [_mention("Michael P. Toups", role="respondent")],
        ),
        administrative,
    )
    administrative_wrong = ext.validate_record(
        _record(
            administrative,
            [_mention("Michael P. Toups", role="defendant")],
        ),
        administrative,
    )
    litigation_valid = ext.validate_record(
        _record(
            litigation,
            [_mention("John Smith", role="defendant")],
        ),
        litigation,
    )

    assert administrative_valid["status"] == "valid"
    assert administrative_wrong["status"] == "needs_review"
    assert litigation_valid["status"] == "valid"


def test_nonparty_role_label_can_be_an_exact_qualifier():
    evidence = _evidence(
        "Acme LLC and Brenda Murray, Administrative Law Judge"
    )
    record = _record(
        evidence,
        [_mention("Acme LLC", party_type="entity")],
        nonparties=[
            _mention(
                "Brenda Murray, Administrative Law Judge",
                name="Brenda Murray",
                display_name="Brenda Murray",
                role="presiding_alj",
                qualifiers=("Administrative Law Judge",),
            )
        ],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "valid"


def test_single_comma_bearing_entity_is_not_treated_as_surname_chain():
    evidence = _evidence("Stifel, Nicolaus & Company, Inc.")

    validation = ext.validate_record(
        _record(
            evidence,
            [
                _mention(
                    evidence["respondent_text"],
                    party_type="entity",
                )
            ],
        ),
        evidence,
    )

    assert validation["status"] == "valid"


def test_bancorp_is_an_entity_signal():
    evidence = _evidence("First Bancorp")

    validation = ext.validate_record(
        _record(
            evidence,
            [_mention("First Bancorp", party_type="entity")],
        ),
        evidence,
    )

    assert validation["status"] == "valid"


def test_et_al_roster_is_never_treated_as_party_exhaustive():
    evidence = _evidence("Patriarch Partners, et al.")
    record = _record(
        evidence,
        [_mention("Patriarch Partners", party_type="entity")],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert "roster contains et al. and is not party-exhaustive" in (
        validation["review_reasons"]
    )


@pytest.mark.parametrize(
    ("roster", "support", "expected_roster_token"),
    [
        (
            "William Aven",
            "William Avent, Respondent",
            "aven",
        ),
        (
            "First LendersIndemnity Company",
            "First Lenders Indemnity Company, Respondent",
            "lendersindemnity",
        ),
        (
            "John Aristotle DilworthII",
            "John Aristotle Dilworth II, Respondent",
            "dilworthii",
        ),
    ],
)
def test_support_token_variants_quarantine_corrupted_index_rosters(
    roster,
    support,
    expected_roster_token,
):
    evidence = _evidence(roster, support_excerpt=support)
    record = _record(
        evidence,
        [_mention(roster, party_type="unknown")],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        expected_roster_token in reason
        and reason.startswith("support suggests corrupted")
        for reason in validation["review_reasons"]
    )


def test_nonparty_role_requires_exact_role_evidence():
    evidence = _evidence("John Smith and Jane Doe")
    record = _record(
        evidence,
        [_mention("John Smith")],
        nonparties=[_mention("Jane Doe", role="counsel")],
    )

    validation = ext.validate_record(record, evidence)

    assert validation["status"] == "needs_review"
    assert any(
        "counsel role lacks an exact role label" in reason
        for reason in validation["review_reasons"]
    )


def test_suspicion_assessment_flags_comma_bearing_entity_roster():
    reasons = ext.assess_suspicion(
        "Goldman, Sachs & Co. and Fabrice Tourre",
        [
            {
                "name_raw": "Sachs & Co.",
                "role": "defendant",
            },
            {
                "name_raw": "Fabrice Tourre",
                "role": "defendant",
            },
        ],
    )

    assert "multi_comma_entity" in reasons


@pytest.mark.parametrize(
    "respondent_text",
    [
        "Banco Santander, S.A.",
        "Acme Law Group, P.C.",
        "Example Bank, N.A.",
        "Example Holdings, N.V.",
        "Example Securities, S.p.A.",
    ],
)
def test_suspicion_assessment_flags_dotted_legal_forms(respondent_text):
    reasons = ext.assess_suspicion(
        respondent_text,
        [
            {
                "name_raw": respondent_text.rsplit(",", 1)[0],
                "role": "defendant",
            }
        ],
    )

    assert "dotted_legal_form" in reasons


def _create_source_database(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE enforcement_actions (
            id INTEGER PRIMARY KEY,
            release_number TEXT NOT NULL,
            source_type TEXT NOT NULL,
            date_published TEXT,
            respondent_text TEXT NOT NULL,
            release_url TEXT,
            file_number TEXT,
            body_text TEXT,
            body_extraction_method TEXT
        );
        CREATE TABLE enforcement_defendants (
            id INTEGER PRIMARY KEY,
            action_id INTEGER NOT NULL,
            name_raw TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            defendant_type TEXT,
            role TEXT NOT NULL DEFAULT 'defendant'
        );
        """
    )
    roster = "Goldman, Sachs & Co. and Fabrice Tourre"
    db.executemany(
        """
        INSERT INTO enforcement_actions(
            id, release_number, source_type, date_published, respondent_text,
            release_url, file_number, body_text, body_extraction_method
        ) VALUES (?, ?, 'admin', ?, ?, ?, '3-12345', ?, 'pdftotext')
        """,
        [
            (
                1,
                "34-100",
                "2010-01-01",
                roster,
                "https://www.sec.gov/files/34-100.pdf",
                "IN THE MATTER OF\nGoldman, Sachs & Co.\nFINAL ORDER",
            ),
            (
                2,
                "34-101",
                "2010-02-01",
                roster,
                "https://www.sec.gov/files/34-101.pdf",
                (
                    "ORDER INSTITUTING ADMINISTRATIVE PROCEEDINGS\n"
                    "IN THE MATTER OF\nGoldman, Sachs & Co. and Fabrice Tourre"
                ),
            ),
        ],
    )
    db.executemany(
        """
        INSERT INTO enforcement_defendants(
            action_id, name_raw, name_normalized, defendant_type, role
        ) VALUES (?, ?, ?, ?, 'defendant')
        """,
        [
            (1, "Sachs & Co.", "sachs co", "entity"),
            (1, "Fabrice Tourre", "fabrice tourre", "person"),
            (2, "Sachs & Co.", "sachs co", "entity"),
            (2, "Fabrice Tourre", "fabrice tourre", "person"),
        ],
    )
    db.commit()
    db.close()


@pytest.fixture
def staged_fixture(tmp_path):
    source_path = tmp_path / "source.db"
    sidecar_path = tmp_path / "sidecar.db"
    _create_source_database(source_path)
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest = ext.prepare_inputs(
        source_db_path=source_path,
        sidecar_db_path=sidecar_path,
        mode="all",
        sample_size=0,
    )
    after = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return source_path, sidecar_path, manifest, before, after


def test_prepare_groups_duplicate_rosters_selects_initiating_order_and_is_read_only(
    staged_fixture,
):
    source_path, sidecar_path, manifest, before, after = staged_fixture

    assert before == after
    assert manifest["case_count"] == 1
    case = manifest["cases"][0]
    assert [
        action["source_action_id_snapshot"] for action in case["actions"]
    ] == [1, 2]
    assert case["support_document"]["source_action_id_snapshot"] == 2
    assert (
        case["support_document"]["selection_reason"]
        == "earliest_initiating_order"
    )
    assert [item["name_raw"] for item in case["current_parse"]] == [
        "Sachs & Co.",
        "Fabrice Tourre",
    ]

    with sqlite3.connect(sidecar_path) as sidecar:
        assert sidecar.execute(
            "SELECT COUNT(*) FROM party_extraction_input"
        ).fetchone()[0] == 1
        assert sidecar.execute(
            "SELECT COUNT(*) FROM party_extraction_input_action"
        ).fetchone()[0] == 2
    with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
        assert source.execute(
            "SELECT COUNT(*) FROM enforcement_actions"
        ).fetchone()[0] == 2
        assert source.execute(
            "SELECT COUNT(*) FROM enforcement_defendants"
        ).fetchone()[0] == 4


def test_prepare_does_not_merge_repeated_rosters_without_file_number(tmp_path):
    source_path = tmp_path / "source.db"
    sidecar_path = tmp_path / "sidecar.db"
    _create_source_database(source_path)
    with sqlite3.connect(source_path) as source:
        source.execute("UPDATE enforcement_actions SET file_number=NULL")
        source.commit()

    manifest = ext.prepare_inputs(
        source_db_path=source_path,
        sidecar_db_path=sidecar_path,
        mode="all",
        sample_size=0,
    )

    assert manifest["case_count"] == 2
    assert sorted(
        case["actions"][0]["release_number"] for case in manifest["cases"]
    ) == ["34-100", "34-101"]
    assert all(len(case["actions"]) == 1 for case in manifest["cases"])


def test_mismatched_support_is_removed_and_blocks_adjudication(
    tmp_path,
    monkeypatch,
):
    source_path = tmp_path / "source.db"
    sidecar_path = tmp_path / "sidecar.db"
    _create_source_database(source_path)
    with sqlite3.connect(source_path) as source:
        source.execute(
            """
            UPDATE enforcement_actions
            SET body_text='IN THE MATTER OF Stephen R. Becker, Respondent'
            """
        )
        source.commit()

    manifest = ext.prepare_inputs(
        source_db_path=source_path,
        sidecar_db_path=sidecar_path,
        mode="all",
        sample_size=0,
    )
    input_id = manifest["cases"][0]["input_id"]
    with sqlite3.connect(sidecar_path) as sidecar:
        evidence = json.loads(
            sidecar.execute(
                """
                SELECT evidence_payload_json
                FROM party_extraction_input
                WHERE input_sha256=?
                """,
                (input_id,),
            ).fetchone()[0]
        )

    assert evidence["support_excerpt"] == ""
    assert (
        evidence["support_document"]["support_consistency"]["status"]
        == "mismatch"
    )
    assert "rejected_roster_mismatch" in (
        evidence["support_document"]["selection_reason"]
    )

    def fake_codex(evidence_records, **_kwargs):
        output = {
            "records": [
                _record(
                    item,
                    [
                        _mention(
                            "Goldman, Sachs & Co.",
                            party_type="entity",
                        ),
                        _mention("Fabrice Tourre"),
                    ],
                )
                for item in evidence_records
            ]
        }
        return ext.CodexBatchResult(
            output=output,
            raw_text=json.dumps(output),
            exit_code=0,
            error_text=None,
            cli_version="codex-cli test",
            auth_mode="chatgpt",
        )

    monkeypatch.setattr(ext, "run_codex_batch", fake_codex)
    extracted = ext.run_extractions(
        sidecar_db_path=sidecar_path,
        batch_size=1,
    )
    adjudication = ext.run_extractions(
        sidecar_db_path=sidecar_path,
        purpose="adjudicate",
        model="gpt-5.6-sol",
        batch_size=1,
        dry_run=True,
    )

    assert extracted["status_counts"] == {"needs_review": 1}
    assert adjudication["planned_count"] == 0
    assert adjudication["adjudication_skips"] == [
        {
            "input_id": input_id,
            "attempt_ref": extracted["attempts"][0]["attempt_ref"],
            "reasons": ["support_document_rejected_roster_mismatch"],
        }
    ]


def test_prepare_rejects_direct_and_hardlinked_source_sidecars(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source_database(source_path)
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()

    with pytest.raises(ext.PartyExtractionError, match="different files"):
        ext.prepare_inputs(
            source_db_path=source_path,
            sidecar_db_path=source_path,
            mode="all",
            sample_size=0,
        )

    hardlink_path = tmp_path / "hardlinked-sidecar.db"
    os.link(source_path, hardlink_path)
    with pytest.raises(ext.PartyExtractionError, match="same file"):
        ext.prepare_inputs(
            source_db_path=source_path,
            sidecar_db_path=hardlink_path,
            mode="all",
            sample_size=0,
        )
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before


def test_nonprepare_commands_reject_canonical_database_as_sidecar(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source_database(source_path)
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()

    with pytest.raises(ext.PartyExtractionError, match="application_id mismatch"):
        ext.extraction_status(sidecar_db_path=source_path)
    with pytest.raises(ext.PartyExtractionError, match="application_id mismatch"):
        ext.run_extractions(sidecar_db_path=source_path, dry_run=True)

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
    with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
        tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert not any(name.startswith("party_extraction_") for name in tables)


def test_output_preflight_rejects_database_aliases_and_sqlite_headers(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source_database(source_path)
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()

    hardlink = tmp_path / "hardlink.json"
    os.link(source_path, hardlink)
    with pytest.raises(ext.PartyExtractionError, match="alias protected input"):
        ext._require_safe_output_path(
            hardlink,
            protected_paths=[source_path],
        )

    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(source_path)
    with pytest.raises(ext.PartyExtractionError, match="protected input"):
        ext._require_safe_output_path(
            symlink,
            protected_paths=[source_path],
        )

    unrelated_sqlite = tmp_path / "unrelated.json"
    shutil_source = sqlite3.connect(unrelated_sqlite)
    shutil_source.execute("CREATE TABLE example(id INTEGER)")
    shutil_source.commit()
    shutil_source.close()
    with pytest.raises(ext.PartyExtractionError, match="SQLite database"):
        ext._require_safe_output_path(
            unrelated_sqlite,
            protected_paths=[],
        )

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before


def test_sanitized_codex_environment_removes_provider_credentials():
    sanitized = ext.sanitized_codex_environment(
        {
            "PATH": "/usr/bin",
            "CODEX_HOME": "/tmp/codex-home",
            "OPENAI_API_KEY": "secret",
            "openai_base_url": "https://provider.invalid",
            "AZURE_OPENAI_API_KEY": "secret",
            "VENDOR_OPENAI_API_KEY": "secret",
            "UNRELATED_TOKEN": "preserved",
            "HTTPS_PROXY": "http://proxy.invalid",
        }
    )

    assert sanitized == {
        "PATH": "/usr/bin",
        "CODEX_HOME": "/tmp/codex-home",
        "HTTPS_PROXY": "http://proxy.invalid",
    }


def test_codex_auth_rejects_non_chatgpt_login(monkeypatch):
    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="Logged in using an API key\n",
            stderr="",
        )

    monkeypatch.setattr(ext, "_run_command", fake_run)

    with pytest.raises(ext.PartyExtractionError, match="authenticated with ChatGPT"):
        ext.codex_auth_and_version(codex_binary="/test/bin/codex")


def test_codex_auth_accepts_chatgpt_status_from_stderr(monkeypatch):
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        if list(args)[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="",
                stderr="Logged in using ChatGPT\n",
            )
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="codex-cli 1.2.3\n",
            stderr="",
        )

    monkeypatch.setattr(ext, "_run_command", fake_run)

    auth_mode, version, _environment = ext.codex_auth_and_version(
        codex_binary="/test/bin/codex"
    )

    assert auth_mode == "chatgpt"
    assert version == "codex-cli 1.2.3"
    assert calls == [
        ["/test/bin/codex", "login", "status"],
        ["/test/bin/codex", "--version"],
    ]


def test_codex_invocation_uses_stdin_safe_args_and_sanitized_environment(
    monkeypatch,
):
    input_id = "a" * 64
    hostile_text = 'Acme LLC"; touch /tmp/should-not-exist; #'
    calls = []
    captured_schema = {}

    def fake_run(args, *, environment, timeout, input_text=None):
        calls.append(
            {
                "args": list(args),
                "environment": dict(environment),
                "timeout": timeout,
                "input_text": input_text,
            }
        )
        if list(args)[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="Logged in using ChatGPT\n",
                stderr="",
            )
        if list(args)[1:] == ["--version"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="codex-cli 1.2.3\n",
                stderr="",
            )
        response_index = list(args).index("--output-last-message") + 1
        schema_index = list(args).index("--output-schema") + 1
        captured_schema.update(
            json.loads(Path(args[schema_index]).read_text(encoding="utf-8"))
        )
        Path(args[response_index]).write_text(
            json.dumps({"records": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(ext, "_run_command", fake_run)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-child")
    monkeypatch.setenv("CODEX_API_KEY", "must-not-reach-child")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-reach-child")
    result = ext.run_codex_batch(
        [
            {
                "input_id": input_id,
                "respondent_text": hostile_text,
                "support_excerpt": "",
            }
        ],
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        codex_binary="/test/bin/codex",
    )

    assert result.output == {"records": []}
    exec_call = calls[-1]
    args = exec_call["args"]
    assert args[1] == "exec"
    assert args[-1] == "-"
    assert hostile_text not in args
    assert "touch /tmp/should-not-exist" in exec_call["input_text"]
    assert "--ephemeral" in args
    assert "--ignore-user-config" in args
    assert "--ignore-rules" in args
    assert "--strict-config" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    argument_pairs = set(zip(args, args[1:], strict=False))
    assert ("-c", "shell_environment_policy.inherit=none") in argument_pairs
    for feature in ext.DISABLED_CODEX_FEATURES:
        assert ("--disable", feature) in argument_pairs
    assert "OPENAI_API_KEY" not in exec_call["environment"]
    assert "CODEX_API_KEY" not in exec_call["environment"]
    assert "UNRELATED_SECRET" not in exec_call["environment"]
    assert captured_schema == ext.build_output_schema()


def test_model_argument_rejects_shell_metacharacters_before_execution(monkeypatch):
    monkeypatch.setattr(
        ext,
        "codex_auth_and_version",
        lambda **_kwargs: pytest.fail("authentication should not be attempted"),
    )

    with pytest.raises(ext.PartyExtractionError, match="invalid model name"):
        ext.run_codex_batch(
            [],
            model="gpt-5.6-terra; touch /tmp/nope",
            reasoning_effort="medium",
            codex_binary="/test/bin/codex",
        )


def test_attempt_review_and_export_remain_in_sidecar(
    staged_fixture,
    monkeypatch,
):
    source_path, sidecar_path, manifest, before, _after = staged_fixture
    input_id = manifest["cases"][0]["input_id"]

    def fake_codex(evidence_records, **_kwargs):
        records = []
        for evidence in evidence_records:
            records.append(
                _record(
                    evidence,
                    [
                        _mention(
                            "Goldman, Sachs & Co.",
                            party_type="entity",
                        ),
                        _mention("Fabrice Tourre"),
                    ],
                )
            )
        output = {"records": records}
        return ext.CodexBatchResult(
            output=output,
            raw_text=json.dumps(output),
            exit_code=0,
            error_text=None,
            cli_version="codex-cli test",
            auth_mode="chatgpt",
        )

    monkeypatch.setattr(ext, "run_codex_batch", fake_codex)
    run = ext.run_extractions(
        sidecar_db_path=sidecar_path,
        model="gpt-5.6-terra",
        batch_size=1,
    )
    assert run["status_counts"] == {"valid": 1}
    assert run["attempt_count"] == 1
    attempt_ref = run["attempts"][0]["attempt_ref"]

    reviewed = ext.review_attempt(
        attempt_ref,
        decision="accepted",
        decided_by="test-reviewer",
        notes="Both exact spans checked against the roster.",
        sidecar_db_path=sidecar_path,
    )
    assert reviewed["review"]["decision"] == "accepted"

    exported = ext.export_reviewed(sidecar_db_path=sidecar_path)
    assert exported["record_count"] == 1
    exported_record = exported["records"][0]
    assert exported_record["input_id"] == input_id
    assert exported_record["review"]["decided_by"] == "test-reviewer"
    assert [mention["name_verbatim"] for mention in exported_record["mentions"]] == [
        "Goldman, Sachs & Co.",
        "Fabrice Tourre",
    ]
    assert [
        action["source_action_id_snapshot"]
        for action in exported_record["actions"]
    ] == [1, 2]
    assert all(
        action["requires_live_id_resolution"]
        for action in exported_record["actions"]
    )
    assert "must be resolved" in exported["action_identity_notice"]
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
    with sqlite3.connect(sidecar_path) as sidecar:
        with pytest.raises(sqlite3.IntegrityError, match="mentions are immutable"):
            sidecar.execute(
                "UPDATE party_extraction_mention SET display_name='Tampered'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="inputs are immutable"):
            sidecar.execute(
                "UPDATE party_extraction_input SET respondent_text='Tampered'"
            )


def test_needs_review_attempt_cannot_be_accepted(staged_fixture, monkeypatch):
    _source_path, sidecar_path, _manifest, _before, _after = staged_fixture

    def fake_codex(evidence_records, **_kwargs):
        records = [
            _record(
                evidence,
                [
                    _mention(
                        "Goldman, Sachs & Co.",
                        party_type="entity",
                        confidence="medium",
                    ),
                    _mention("Fabrice Tourre"),
                ],
            )
            for evidence in evidence_records
        ]
        output = {"records": records}
        return ext.CodexBatchResult(
            output=output,
            raw_text=json.dumps(output),
            exit_code=0,
            error_text=None,
            cli_version="codex-cli test",
            auth_mode="chatgpt",
        )

    monkeypatch.setattr(ext, "run_codex_batch", fake_codex)
    run = ext.run_extractions(sidecar_db_path=sidecar_path, batch_size=1)
    assert run["status_counts"] == {"needs_review": 1}

    with pytest.raises(ext.PartyExtractionError, match="current validator"):
        ext.review_attempt(
            run["attempts"][0]["attempt_ref"],
            decision="accepted",
            decided_by="test-reviewer",
            sidecar_db_path=sidecar_path,
        )


def test_adjudication_uses_stable_extract_parent_and_then_hits_cache(
    staged_fixture,
    monkeypatch,
):
    _source_path, sidecar_path, _manifest, _before, _after = staged_fixture
    calls = []

    def fake_codex(evidence_records, **kwargs):
        calls.append(kwargs["purpose"])
        records = [
            _record(
                evidence,
                [
                    _mention(
                        "Goldman, Sachs & Co.",
                        party_type="entity",
                        confidence="medium",
                    ),
                    _mention("Fabrice Tourre"),
                ],
            )
            for evidence in evidence_records
        ]
        output = {"records": records}
        return ext.CodexBatchResult(
            output=output,
            raw_text=json.dumps(output),
            exit_code=0,
            error_text=None,
            cli_version="codex-cli test",
            auth_mode="chatgpt",
        )

    monkeypatch.setattr(ext, "run_codex_batch", fake_codex)
    extracted = ext.run_extractions(sidecar_db_path=sidecar_path, batch_size=1)
    assert extracted["status_counts"] == {"needs_review": 1}

    first = ext.run_extractions(
        sidecar_db_path=sidecar_path,
        model="gpt-5.6-sol",
        purpose="adjudicate",
        batch_size=1,
    )
    second = ext.run_extractions(
        sidecar_db_path=sidecar_path,
        model="gpt-5.6-sol",
        purpose="adjudicate",
        batch_size=1,
    )

    assert first["attempt_count"] == 1
    assert first["status_counts"] == {"needs_review": 1}
    assert second["attempt_count"] == 0
    assert second["cache_hit_count"] == 1
    assert calls == ["extract", "adjudicate"]


def test_model_invocation_failure_aborts_remaining_batches(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    sidecar_path = tmp_path / "sidecar.db"
    _create_source_database(source_path)
    with sqlite3.connect(source_path) as source:
        source.execute(
            """
            INSERT INTO enforcement_actions(
                id, release_number, source_type, date_published, respondent_text,
                release_url, file_number, body_text, body_extraction_method
            ) VALUES (3, '34-102', 'admin', '2011-01-01', 'Acme LLC',
                      'https://www.sec.gov/files/34-102.pdf', '3-99999',
                      'IN THE MATTER OF Acme LLC', 'pdftotext')
            """
        )
        source.execute(
            """
            INSERT INTO enforcement_defendants(
                action_id, name_raw, name_normalized, defendant_type, role
            ) VALUES (3, 'Acme LLC', 'acme', 'entity', 'defendant')
            """
        )
        source.commit()
    manifest = ext.prepare_inputs(
        source_db_path=source_path,
        sidecar_db_path=sidecar_path,
        mode="all",
        sample_size=0,
    )
    assert manifest["case_count"] == 2
    calls = []

    def fail_codex(*_args, **_kwargs):
        calls.append("called")
        raise ext.PartyExtractionError("ChatGPT auth unavailable")

    monkeypatch.setattr(ext, "run_codex_batch", fail_codex)
    result = ext.run_extractions(sidecar_db_path=sidecar_path, batch_size=1)

    assert result["status"] == "failed"
    assert result["attempt_count"] == 1
    assert result["status_counts"] == {"failed": 1}
    assert calls == ["called"]

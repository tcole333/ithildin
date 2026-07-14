from scripts import review_dossier_checks


def _dossier_with_citation(finding_id: int) -> dict:
    return {
        "findings": [{"id": 1}],
        "curation": {
            "lead": f"<p>Documented statement [Finding #{finding_id}].</p>",
            "sections": [],
        },
    }


def test_global_finding_citation_is_not_reported_as_orphan() -> None:
    issues, metrics = review_dossier_checks.check_citations(
        _dossier_with_citation(2),
        global_finding_ids={2},
    )

    assert metrics["orphan_citations"] == 0
    assert not any("Orphan citation" in issue["detail"] for issue in issues)


def test_unknown_finding_citation_remains_orphaned() -> None:
    issues, metrics = review_dossier_checks.check_citations(
        _dossier_with_citation(999),
        global_finding_ids=set(),
    )

    assert metrics["orphan_citations"] == 1
    assert any("Finding #999" in issue["detail"] for issue in issues)


def test_unverified_global_finding_citation_is_blocking() -> None:
    issues, metrics = review_dossier_checks.check_citations(
        _dossier_with_citation(2),
        global_finding_ids={2},
        global_finding_statuses={2: "unverified"},
    )

    assert metrics["orphan_citations"] == 0
    assert metrics["non_verified_citations"] == 1
    assert any(
        issue["severity"] == "BLOCKING" and "status unverified" in issue["detail"]
        for issue in issues
    )


def test_verified_global_finding_citation_is_allowed() -> None:
    issues, metrics = review_dossier_checks.check_citations(
        _dossier_with_citation(2),
        global_finding_ids={2},
        global_finding_statuses={2: "verified"},
    )

    assert metrics["non_verified_citations"] == 0
    assert not any("Non-verified citation" in issue["detail"] for issue in issues)


def test_object_valued_applicable_models_are_blocking() -> None:
    dossier = {
        "curation": {
            "lead": "<p>Lead.</p>",
            "sections": [{"title": "Section", "content": "<p>Text.</p>", "viz": None}],
            "applicable_models": [{"model": "network-broker"}],
        }
    }

    issues = review_dossier_checks.check_structure(dossier)

    assert any(
        issue["severity"] == "BLOCKING" and "applicable_models" in issue["detail"]
        for issue in issues
    )


def test_static_citation_finding_is_available_without_database_catalog() -> None:
    dossier = _dossier_with_citation(2)
    dossier["citation_findings"] = [
        {"id": 2, "verification_status": "verified", "claim_type": "direct_quote"}
    ]

    issues, metrics = review_dossier_checks.check_citations(
        dossier,
        global_finding_ids=set(),
        global_finding_statuses={},
    )

    assert metrics["orphan_citations"] == 0
    assert metrics["non_verified_citations"] == 0
    assert not any(issue["severity"] == "BLOCKING" for issue in issues)


def test_source_bounded_negative_counts_as_synthesis_attribution() -> None:
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "The records do not establish that the lawyer was retained."
    )
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "An archived biography lists the company as a client."
    )
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "The verified sequence involves messages among the four participants."
    )
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "A later iMessage export labels a participant only as Jack."
    )
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "The evidence therefore does not establish a personal engagement."
    )
    assert review_dossier_checks.ATTRIBUTION_RE.search(
        "At 1:12 p.m., Epstein relayed the statement to Weingarten."
    )


def test_html_paragraphs_preserve_sentence_boundaries() -> None:
    parsed = review_dossier_checks.parse_html(
        "<p>First sentence [Finding #1].</p><p>The records show a second fact.</p>"
    )

    assert review_dossier_checks.extract_sentences(parsed.text) == [
        "First sentence [Finding #1].",
        "The records show a second fact.",
    ]

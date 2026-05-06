from tools.query_nyscef import _derive_person_fields, _filter_documents, _normalize_date


def test_derive_person_fields_single_token_defaults_to_last_name():
    fields = _derive_person_fields("Epstein")
    assert fields == {"first_name": "", "middle_name": "", "last_name": "Epstein"}


def test_derive_person_fields_multi_token_splits_middle_name():
    fields = _derive_person_fields("Jeffrey Edward Epstein")
    assert fields == {
        "first_name": "Jeffrey",
        "middle_name": "Edward",
        "last_name": "Epstein",
    }


def test_normalize_date_accepts_iso_and_slashed_dates():
    assert _normalize_date("2019-07-10") == "2019-07-10"
    assert _normalize_date("07/10/2019") == "07/10/2019"


def test_filter_documents_matches_multiple_optional_filters():
    docs = [
        {
            "document_number": "1",
            "document_type": "PETITION",
            "filed_by": "SAURBORN, HENRY L",
            "motion_number": None,
            "status": "Processed",
        },
        {
            "document_number": "7",
            "document_type": "ORDER TO SHOW CAUSE ( PROPOSED )",
            "filed_by": "MOSKOWITZ, BENNET J",
            "motion_number": "002",
            "status": "Processed",
        },
    ]

    class Args:
        doc_type = "order to show cause"
        filed_by = "moskowitz"
        motion = "002"
        doc_number = None
        status = "processed"

    filtered = _filter_documents(docs, Args())
    assert len(filtered) == 1
    assert filtered[0]["document_number"] == "7"

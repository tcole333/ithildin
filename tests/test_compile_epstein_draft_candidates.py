from scripts import compile_epstein_draft_candidates as compiler


def row(text: str, key: str = "EFTA_TEST") -> dict:
    return {
        "id": key,
        "file_key": key,
        "dataset": "DataSet10",
        "document_type": "Email",
        "date": "July 18, 2013",
        "char_count": len(text),
        "full_text": text,
    }


def test_parse_email_separates_top_body_from_quoted_thread():
    parsed = compiler.parse_email(
        """From: Jeffrey Epstein <jeevacation@gmail.com>
To: Jeffrey Epstein <jeevacation@gmail.com>
Subject: bill

dear Bill
This is the newly composed text.

----- Original Message -----
From: Someone Else
Dear Jeffrey, old quoted text.
"""
    )
    assert parsed.headers["from"].startswith("Jeffrey Epstein")
    assert parsed.headers["to"].startswith("Jeffrey Epstein")
    assert parsed.body == "dear Bill\nThis is the newly composed text."


def test_self_addressed_formal_pressure_letter_is_high_priority():
    candidate = compiler.make_candidate(
        row(
            """From: Jeffrey Epstein <jeevacation@gmail.com>
To: Jeffrey Epstein <jeevacation@gmail.com>
Subject: bill

dear Bill
I have decided to resign my position effective immediately. In my role as his right hand I was asked to sign a confidentiality agreement. If I do not receive a response, I will make the emails public and file a bar complaint.
"""
        )
    )
    assert candidate is not None
    assert "self_addressed" in candidate["evidence_types"]
    assert "third_party_voice" in candidate["signals"]
    assert "pressure_language" in candidate["signals"]
    assert candidate["priority"] == "high"


def test_blank_recipient_reply_with_only_quoted_salutation_is_excluded():
    candidate = compiler.make_candidate(
        row(
            """From: Jeffrey Epstein <jeevacation@gmail.com>
To:
Subject: Re: news

call
On Monday, November 30, 2015 at 4:07 PM, Person wrote:
Dear Jeffrey, I would like to help with a settlement and public statement.
"""
        )
    )
    assert candidate is None


def test_explicit_draft_ui_is_included_without_headers():
    candidate = compiler.make_candidate(
        row(
            """Draft
(no subject) - I am not sending this email, only documenting the issue.
Draft
Re: proposed letter language
Select: All, None, Read, Unread, Starred, Unstarred
""",
            "EFTA_UI",
        )
    )
    assert candidate is not None
    assert candidate["priority"] == "high"
    assert candidate["evidence_types"] == ["explicit_draft_ui"]


def test_sender_name_address_conflict_is_flagged_and_weak_row_excluded():
    candidate = compiler.make_candidate(
        row(
            """From: Jes Staley <jeevacation@gmail.com>
To: Jeffrey Epstein <jeevacation@gmail.com>
Subject: Re:

Thanks, I will call you tomorrow morning when I arrive in New York.
"""
        )
    )
    assert candidate is None


def test_long_attachment_like_ocr_is_not_sent_through_attachment_only_regex():
    body = ("IMG_1234.jpg " * 2_000) + "substantive prose follows"
    assert compiler.is_automatic("", body) is False


def test_family_assignment_clusters_close_revisions():
    first = compiler.make_candidate(
        row(
            """From: Jeffrey Epstein <jeevacation@gmail.com>
To: Jeffrey Epstein <jeevacation@gmail.com>

dear Bill, I have decided to resign my position immediately. In my role as his right hand I was asked to sign a confidentiality agreement and protect the reputation of the organization. I cannot continue under these conditions.
""",
            "EFTA_A",
        )
    )
    second = compiler.make_candidate(
        row(
            """From: Jeffrey Epstein <jeevacation@gmail.com>
To: Jeffrey Epstein <jeevacation@gmail.com>

dear Bill, I have decided to resign my position effective immediately. In my role as his right hand I was asked to sign a confidentiality agreement and protect the reputation of the organization. I cannot continue under those conditions.
""",
            "EFTA_B",
        )
    )
    assert first and second
    compiler.assign_families([first, second])
    assert first["family_id"] == second["family_id"]
    assert first["family_size"] == 2

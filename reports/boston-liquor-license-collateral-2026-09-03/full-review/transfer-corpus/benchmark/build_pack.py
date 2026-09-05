"""Build a fixed, blinded source-only benchmark and a separately stored answer key."""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent


def load(path):
    return json.loads(path.read_text())


def write(name, content):
    (ROOT / name).write_text(json.dumps(content, indent=2) + "\n")


def schema(properties):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties)}


def main():
    events = load(CORPUS / "events.json")
    excluded = load(CORPUS / "excluded-candidates-2025-2026.json")
    selections = [
        ("BLB-2026-08-27-028-transfer", "straight_transfer"),
        ("BLB-2025-06-05-011-transfer", "combined_transfer_pledge"),
        ("BLB-2025-08-28-045-transfer", "conditional_grant"),
        ("BLB-2026-03-05-049-notice", "unclosed_revocation_notice"),
        ("BLB-2025-05-15-046-notice", "release_prior_pledge"),
        ("BLB-2025-06-05-010-transfer", "corrected_buyer"),
        ("BLB-2024-12-12-T-23", "deferred_transfer_and_pledge"),
        ("BLB-2026-01-08-023-transfer", "continued_transfer"),
        ("BLB-2026-03-05-027-transfer", "omitted_address_corrected_manager"),
        ("BLB-2025-05-15-022-pledge", "new_pledge_same_license_as_release"),
        ("BLB-2025-03-06-019", "stock_transfer_only"),
        ("BLB-2025-12-04-011", "stock_pledge_only"),
    ]
    prepared = []
    for event_id, category in selections:
        event = next((e for e in events if e["event_id"] == event_id), None)
        candidate = next((e for e in excluded if e["candidate_id"] == event_id), None)
        record = event or candidate
        related = [e for e in events if event and e["source_id"] == event["source_id"] and e["item_text"] == event["item_text"]]
        transfer = next((e for e in related if e["event_type"] == "license_transfer"), None)
        pledge = next((e for e in related if e["event_type"] == "license_pledge"), None)
        actions = []
        if transfer:
            actions.append("license_transfer_revocation_notice" if transfer["action_subtype"] == "transfer_revocation_notice" else "license_transfer")
        if pledge:
            actions.append("license_pledge_release" if pledge["action_subtype"] == "pledge_release_acknowledgment" else "license_pledge")
        if category == "stock_transfer_only":
            actions = ["stock_transfer"]
        if category == "stock_pledge_only":
            actions = ["stock_pledge"]
        conditions = {
            "combined_transfer_pledge": ["Granted with closing hour of 11:00 PM."],
            "conditional_grant": ["License not to be issued until Board receives confirmation from Downtown Boston Neighborhood Association that the community process is complete."],
            "corrected_buyer": ["Transferee corrected from 1928 Boston Harbor, LLC to 1928 Rowes Wharf LLC.", "Board requests a security plan addressing hotel security relationship and preventing patrons leaving with alcohol."],
            "deferred_transfer_and_pledge": ["Deferred to allow an application for Change of License Type."],
            "continued_transfer": ["Continued to January 28, 2026 Transactional Hearing."],
            "omitted_address_corrected_manager": ["Granted with Maria Murray as manager of record, replacing proposed manager Dylan S. Welsh.", "Street address omitted; source states same location."],
            "unclosed_revocation_notice": ["Board acknowledges mutual intent to revoke transfer approved August 28, 2025; source does not record a new grant or a formal revocation order."],
            "release_prior_pledge": ["Rockland Trust Company releases previous pledges/security interests; excerpt does not establish absence of other liens."],
        }.get(category, [])
        answer = {
            "kind": "board_record", "license_num": event["license_num"] if event else record["license_numbers"][0].replace("-", ""),
            "actions": actions, "disposition": event["disposition"] if event else "granted",
            "transferor": transfer.get("transferor") if transfer else None,
            "transferee": transfer.get("transferee") if transfer else None,
            "transferee_dba": transfer.get("transferee_dba") if transfer else None,
            "pledging_party": pledge.get("licensee") if pledge else None,
            "pledge_recipient": pledge.get("pledge_recipient") if pledge else None,
            "from_address": transfer.get("from_address") if transfer else pledge.get("from_address") if pledge else None,
            "to_address": transfer.get("to_address") if transfer else None,
            "conditions_or_corrections": conditions,
            "license_transfer_approved": bool(transfer and transfer["board_granted_application"]),
            "new_license_pledge_approved": bool(pledge and pledge["board_granted_application"]),
            "sale_completion_status": "reported_not_timely_closed" if category == "unclosed_revocation_notice" else "not_established",
            "current_license_lien_status": "not_established", "loan_amount": None,
            "evidence_quotes": [],
        }
        # All snippets remain in the supplied primary text; varied verbatim evidence is accepted by the rubric.
        lines = [line.strip() for line in record["item_text"].splitlines() if line.strip()]
        answer["evidence_quotes"] = [line for line in lines if line.startswith(("Granted", "Deferred", "Continued", "Acknowledged"))][:1]
        prepared.append({"category": category, "source_record_id": event_id, "reference": answer,
                         "input": {"kind": "board_record", "sources": [{"source_url": record["source_url"], "page_start": record["page_start"], "page_end": record["page_end"], "item_text": record["item_text"]}]}})

    ownership_path = ROOT / "ownership-cases.json"
    if ownership_path.exists():
        ownership = load(ownership_path)
        for case in ownership["cases"]:
            if case["case_id"] != "OWN-LYONS-01":
                raise ValueError("Unreviewed ownership case")
            prepared.append({
                "category": "portfolio_disclaimer_vs_marketing", "source_record_id": case["case_id"],
                "input": {"kind": "ownership_record", "sources": [
                    {"source_url": x["source_url"], "page_start": x["page"], "page_end": x["page"], "item_text": x["text"]}
                    for x in case["source_excerpts"]
                ]},
                "reference": {"kind": "ownership_record", "subject": "Lyons Group and its listed venues",
                              "relationship_classification": "portfolio_affiliation_only",
                              "named_investor": None, "equity_percentage": None,
                              "private_equity_backing_established": False,
                              "current_equity_ownership_established": False,
                              "qualifications": [
                                  "The source explicitly disclaims Lyons Group ownership of the listed entities and says venues are independently owned and operated.",
                                  "Marketing portfolio language does not establish equity ownership.",
                                  "No institutional sponsor or equity percentage is identified. This does not establish that every venue lacks other institutional investors or common beneficial owners.",
                              ],
                              "evidence_quotes": [case["source_excerpts"][1]["text"]]},
            })
    random.Random(90326).shuffle(prepared)
    source_cases, answers = [], []
    for position, case in enumerate(prepared, 1):
        case_id = f"C{position:02d}"
        source_cases.append({"case_id": case_id, **case["input"]})
        answers.append({"case_id": case_id, "sampling_category": case["category"],
                        "source_record_id": case["source_record_id"],
                        "answer": {"case_id": case_id, **case["reference"]}})
    nullable_string = {"type": ["string", "null"]}
    string_array = {"type": "array", "items": {"type": "string"}}
    board = schema({
        "case_id": {"type": "string"}, "kind": {"const": "board_record"},
        "license_num": nullable_string,
        "actions": {"type": "array", "uniqueItems": True, "items": {"enum": ["license_transfer", "license_pledge", "license_transfer_revocation_notice", "license_pledge_release", "stock_transfer", "stock_pledge"]}},
        "disposition": {"enum": ["granted", "deferred", "continued", "rescheduled", "withdrawn", "denied", "acknowledged", "not_stated"]},
        **{key: nullable_string for key in ["transferor", "transferee", "transferee_dba", "pledging_party", "pledge_recipient", "from_address", "to_address"]},
        "conditions_or_corrections": string_array,
        "license_transfer_approved": {"type": "boolean"}, "new_license_pledge_approved": {"type": "boolean"},
        "sale_completion_status": {"enum": ["not_established", "reported_not_timely_closed", "reported_voided", "established_completed"]},
        "current_license_lien_status": {"enum": ["not_established", "established"]},
        "loan_amount": {"type": ["number", "null"]}, "evidence_quotes": string_array,
    })
    owner = schema({
        "case_id": {"type": "string"}, "kind": {"const": "ownership_record"},
        "subject": {"type": "string"},
        "relationship_classification": {"enum": ["private_equity_investment", "portfolio_affiliation_only", "historical_fundraising_only", "public_company", "not_established"]},
        "named_investor": nullable_string, "equity_percentage": {"type": ["number", "null"]},
        "private_equity_backing_established": {"type": "boolean"},
        "current_equity_ownership_established": {"type": "boolean"},
        "qualifications": string_array, "evidence_quotes": string_array,
    })
    output_schema = schema({"results": {"type": "array", "items": {"oneOf": [board, owner]}}})
    input_pack = {
        "benchmark_version": "1.0", "case_count": len(source_cases),
        "instructions": [
            "Answer every case independently using only that case's supplied source text. Do not browse, use tools, inspect other files, or import facts from other cases.",
            "Return only one JSON object conforming to output_schema. Do not include analysis, markdown fences, or extra fields.",
            "Report what the supplied evidence establishes. Use null for facts not supplied and an empty list when no listed action applies. Do not infer missing transaction terms.",
            "For board records, actions is limited to the six listed categories; omit ancillary manager, hours, premises, and stock-interest changes from actions. Stock-transfer/stock-pledge categories must not populate fields defined for license transfers or license pledges.",
            "Normalize an explicitly supplied Boston LB number as LB followed by digits. Transfer parties, DBAs, addresses, and pledge parties refer only to an explicit license transfer/pledge, including its release or revocation notice. Preserve the disposition's corrections.",
            "from_address is the transferor's source location, or the licensee's location for a standalone license pledge/release; to_address is only a license-transfer destination. Do not infer a street address from a creditor's name.",
            "conditions_or_corrections should capture material final-disposition conditions, deferral/continuance reasons, and explicit corrections rather than every operating detail in the application.",
            "Provide one to three short verbatim evidence_quotes from the supplied text that support the main classification or disposition. Harmless whitespace normalization is allowed.",
        ],
        "questions": {
            "board_record": "What license/stock actions and dispositions are explicitly recorded, who are the relevant license-transfer or license-pledge parties, what locations and material conditions/corrections are supplied, and what does this evidence establish about approval, sale completion, current license liens, and loan amount?",
            "ownership_record": "What relationship does the source establish for the subject, does it establish private-equity backing or current equity ownership, and what investor or equity percentage is actually stated?",
        },
        "output_schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", **output_schema},
        "cases": source_cases,
    }
    write("input.json", input_pack)
    write("output-schema.json", input_pack["output_schema"])
    write("reference.json", {"benchmark_version": "1.0", "not_for_model_input": True, "answers": answers})
    print(json.dumps({"cases": len(source_cases), "board_cases": sum(x["kind"] == "board_record" for x in source_cases), "ownership_cases": sum(x["kind"] == "ownership_record" for x in source_cases)}))


if __name__ == "__main__":
    main()

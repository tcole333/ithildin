#!/usr/bin/env python3
"""Write curation fields into content/dossiers/nine-east-71st-street-corporation.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/nine-east-71st-street-corporation.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Nine East 71st Street Corporation was the domestic business corporation "
    "that held title to 9 East 71st Street, Manhattan — the seven-story townhouse "
    "central to federal sex-trafficking charges against Jeffrey Epstein — from "
    "September 1989 until December 2011. It was incorporated with a registered "
    "address at 41 South High Street, Columbus, Ohio, the headquarters of "
    "<a href=\"/dossiers/les-wexner\">Leslie Wexner</a>'s L Brands (then The Limited) "
    "[Finding #492, ACRIS:1690000317169]. The corporation acquired the property "
    "from Birch Wathen School in September 1989 for no recorded consideration "
    "[Finding #481].</p>"
    "<p>In late 1998, Wexner transferred the corporation itself — not just the "
    "property — to NES LLC, an Epstein entity, via a documented sale that included "
    "a Nominee Agreement, Stock Power, Stock Certificate, and Wexner's personal "
    "resignation as director. GRM document EFTA00300480 indexes the transaction "
    "binder under \"Leslie H. Wexner Sale of Nine East 71st Street Corporation to "
    "NES, LLC\" with a General Ledger dated September 30, 1998 [Finding #2468]. "
    "By December 2011 the corporation's address of record had shifted from Columbus "
    "to 301 East 66th Street, 10th Floor — the office address of "
    "<a href=\"/dossiers/richard-kahn\">Richard Kahn</a>'s HBRK Associates — when "
    "it transferred the property to Maple Inc, a USVI corporation, for no recorded "
    "consideration [Finding #1514, ACRIS:2011122700736001].</p>"
    "<p>Federal civil plaintiffs named Nine East 71st Street Corporation as a "
    "defendant alongside the Epstein estate in at least three SDNY lawsuits filed "
    "in August 2019: Katlyn Doe v. Indyke (1:19-cv-07771), Priscilla Doe v. Indyke "
    "(1:19-cv-07772), and Lisa Doe v. Indyke (1:19-cv-07773). The Katlyn Doe "
    "complaint named the corporation specifically on a negligent-security count "
    "(Count III) for its ownership of the premises where abuse occurred [Finding #3261]. "
    "The principal place of business was separately documented in court filings as "
    "575 Lexington Avenue, Fourth Floor, New York, NY 10022 — the same floor as "
    "<a href=\"/dossiers/darren-indyke\">Darren Indyke</a>'s DKIP PLLC and "
    "HBRK Associates [Finding #3263].</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Nine East 71st Street Corporation was the legal title-holder for Epstein's "
    "primary operational premises for approximately 22 years, spanning the Wexner "
    "patronage period, Epstein's independent years, his 2007–2008 Florida plea, and "
    "his work-release period. Its corporate life tracks the three-phase Wexner-to-Epstein "
    "transfer: (1) initial acquisition by a Wexner-addressed entity in 1989; "
    "(2) stock transfer to Epstein's NES LLC in 1998 via a nominee agreement that "
    "preserved the existing corporate shell rather than a direct deed conveyance; "
    "(3) a final title transfer to Maple Inc, a USVI entity in Epstein's four-property "
    "tree-named holding structure, in December 2011. At each stage the corporation "
    "served as the transactional intermediary — insulating the property from direct "
    "individual ownership and from the scrutiny that a personal deed chain would attract."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "origin-and-wexner-acquisition",
        "title": "Origin and the Wexner Acquisition",
        "viz": None,
        "content": (
            "<p>Nine East 71st Street Corporation was formed as a New York domestic "
            "business corporation with its principal registered address at 41 South High "
            "Street, Columbus, Ohio — the L Brands corporate headquarters where "
            "<a href=\"/dossiers/les-wexner\">Leslie Wexner</a> operated his retail empire "
            "[Finding #492]. On September 6, 1989, the corporation acquired the property "
            "at 9 East 71st Street (Block 1386, Lot 10) from Birch Wathen School for no "
            "recorded consideration [Finding #481]. This was not an isolated transaction: "
            "ACRIS records confirm that Wexner-addressed entities also controlled the "
            "adjacent property at 11 East 71st Street (BBL 1/1386/12), acquired through "
            "SAM Conversion Corp — also registered at 41 South High Street — from Xandra "
            "Corporation N.V., a Netherlands Antilles offshore entity, in 1988 "
            "[Finding #483, Finding #489]. Parkview Financial Inc, another entity at the "
            "same Columbus address, appears in ACRIS as a mortgage-assignment intermediary "
            "on the adjacent property [Finding #491]. The three entities — Nine East 71st "
            "St Corp, SAM Conversion Corp, and Parkview Financial Inc — formed a coherent "
            "Wexner real-estate infrastructure for the 71st Street block [Finding #499].</p>"
            "<p>Epstein's entry into the 11 East 71st Street chain preceded the Nine East "
            "transaction: ACRIS shows SAM Conversion transferred the adjacent property to "
            "\"Epstein Jeffrey E Trustee / 11 East 71st St Trust\" at the same Columbus "
            "address in December 1992 for no recorded consideration [Finding #484]. Epstein "
            "then moved that property through two more entities before it reached "
            "<a href=\"/dossiers/howard-lutnick\">Howard Lutnick</a> in January 1998 via "
            "the Comet Trust, trusteed by Guido Goldman [Finding #485]. This establishes "
            "that Epstein had been operating inside Wexner's NYC property structure for "
            "at least six years before he acquired Nine East 71st Street Corporation itself.</p>"
        ),
    },
    {
        "id": "the-1998-stock-transfer",
        "title": "The 1998 Stock Transfer to NES LLC",
        "viz": None,
        "content": (
            "<p>The mechanism for transferring Nine East 71st Street Corporation from "
            "Wexner to Epstein was a stock sale rather than a property deed — a structure "
            "that preserved the existing corporate shell and avoided recording a new deed "
            "in ACRIS. GRM filing index EFTA00300480 documents the complete transaction "
            "binder titled \"Leslie H. Wexner Sale of Nine East 71st Street Corporation to "
            "NES, LLC.\" The binder contains: a General Ledger dated September 30, 1998; "
            "Vorys legal reviews; a Draft Contract of Sale; a Nominee Agreement; NES LLC "
            "Articles of Organization; a Lease Agreement; a Biennial Statement; a "
            "Purchase &amp; Sale Agreement; a Promissory Note; a Guaranty; an Assignment "
            "&amp; Assumption Agreement; a Stock Power; a Stock Certificate; "
            "Wexner's resignation letter as director; a Settlement Statement; and Closing "
            "Documents [Finding #2468]. The General Ledger date places the transaction in "
            "the fall of 1998.</p>"
            "<p>NES LLC — the acquiring entity — was an Epstein USVI entity that appeared "
            "across JPMorgan bank records as a payroll and operational vehicle. JPMorgan "
            "records show regular ADP payroll processing debits from NES LLC's account "
            "(JPM account 739121472), and the entity appears in the 2006 JPM data-tape "
            "entity master list alongside 22 other Epstein-affiliated accounts [Finding #662]. "
            "Deutsche Bank later conducted AML due diligence on NES LLC, and the entity "
            "maintained a Deutsche Bank account balance of approximately $504K as of "
            "August 2014 [Finding #221]. In the December 2019 estate liquidation, the NES "
            "LLC balance transferred to Southern Trust Company was $1,345,169 [Finding #1461]. "
            "The Nominee Agreement included in the 1998 binder is significant: its presence "
            "confirms that the stock transfer included a formal understanding about "
            "Epstein's status as the beneficial owner while the Wexner-era corporate form "
            "was preserved.</p>"
        ),
    },
    {
        "id": "operational-period-and-litigation-function",
        "title": "Operational Period and Litigation Function",
        "viz": None,
        "content": (
            "<p>During the roughly thirteen years between the 1998 stock transfer and the "
            "2011 deed transfer to Maple Inc, Nine East 71st Street Corporation was the "
            "formal owner of the premises where federal civil complaints allege "
            "<a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> conducted commercial "
            "sex trafficking. The Katlyn Doe complaint (1:19-cv-07771 SDNY) names the "
            "corporation on a standalone negligent-security count (Count III) based on its "
            "property ownership during the abuse period, identifying its principal place "
            "of business as 575 Lexington Avenue, Fourth Floor, New York, NY 10022 "
            "[Finding #3189, Finding #3263]. That address is the same fourth-floor suite "
            "occupied by <a href=\"/dossiers/richard-kahn\">Richard Kahn</a>'s HBRK "
            "Associates and <a href=\"/dossiers/darren-indyke\">Darren Indyke</a>'s "
            "DKIP PLLC [Finding #383].</p>"
            "<p>The Priscilla Doe complaint (1:19-cv-07772) and Lisa Doe complaint "
            "(1:19-cv-07773) also named the corporation as co-defendant alongside the "
            "Epstein estate, NES LLC, Financial Trust Company, Maple Inc, HBRK Associates, "
            "JEGE Inc, and LSJ LLC [Finding #1716]. The complaint paras mapped a division "
            "of function across the corporate array: Nine East 71st Street Corp and Maple "
            "Inc owned the physical premises; NES LLC employed the staff who recruited, "
            "scheduled, and paid victims; JEGE Inc owned the Boeing 727 used to transport "
            "victims; HBRK Associates employed post-conviction staff who continued those "
            "functions after Epstein's 2008 Florida plea [Finding #3252]. During Epstein's "
            "work-release period, employees of HBRK Associates, NES LLC, and JEGE Inc "
            "transported a plaintiff to Florida to engage in commercial sex while Epstein "
            "was wearing an ankle monitor [Finding #3218].</p>"
            "<p>L.A.W. Plantation Management Corp., a Georgia corporation with Epstein as "
            "CEO and Indyke as Secretary, appeared in Deutsche Bank KYC searches alongside "
            "Nine East 71st Street Corp and Ghislaine Corp as part of the Epstein entity "
            "cluster. Its initials almost certainly reference Leslie A. Wexner, and its "
            "address (515 Abigail Plantation Rd, Albany GA) links to the Wexner naming "
            "pattern [Finding #577]. The presence of both entities in the same KYC "
            "review reflects how Deutsche Bank encountered them as a single relational "
            "cluster rather than independent legal persons.</p>"
        ),
    },
    {
        "id": "2011-transfer-to-maple-inc-and-post-death-sale",
        "title": "The 2011 Transfer to Maple Inc and Post-Death Sale",
        "viz": "ego_network",
        "content": (
            "<p>On December 23, 2011 — roughly three years after Epstein's Florida plea "
            "and during the period when he was reconstituting his operational structure — "
            "Nine East 71st Street Corporation transferred 9 East 71st Street to "
            "Maple Inc, a USVI corporation, for no recorded consideration. "
            "The deed records the grantor address as 301 East 66th Street, 10th Floor — "
            "the Ossa Properties address associated with Kahn and Epstein's operational "
            "office — rather than the original Columbus, Ohio address, reflecting the "
            "completed shift in administrative control [Finding #1514, Finding #492]. "
            "The Katlyn Doe complaint gives the transfer date as December 11, 2011; "
            "ACRIS gives December 23, 2011 — a minor inconsistency within the same "
            "complaint's paragraphs [Finding #3189].</p>"
            "<p>Maple Inc was one of four tree-named USVI entities Epstein used to hold "
            "real property: Maple Inc (9 E 71st St, NYC), Nautilus Inc (Little Saint James "
            "island, USVI), Laurel Inc (Palm Beach, FL), and Cypress (Zorro Ranch, NM). "
            "<a href=\"/dossiers/richard-kahn\">Richard Kahn</a>'s HBRK Associates at "
            "301 East 66th Street, Suite 10F coordinated JPMorgan Chase bank accounts "
            "for all four entities [Finding #376]. Maple Inc was registered as USVI "
            "entity 581976 on November 22, 2011 — just one month before the Nine East "
            "deed transfer — and managed through Business Basics VI LLC, "
            "<a href=\"/dossiers/erika-kellerhals\">Erika Kellerhals</a>'s registered "
            "agent hub [Finding #1514]. The Epstein estate inventory valued the property "
            "at $55,931,000 [Finding #617].</p>"
            "<p>Following Epstein's death in August 2019, Maple Inc held the property "
            "through the estate administration. On March 8, 2021, Maple Inc transferred "
            "9 East 71st Street to Back To NYC 71 LLC — registered at 24 Lansdowne Road, "
            "London W11 3LL — for $51 million, with a $30.6 million MERS mortgage taken "
            "simultaneously. That entity subsequently sold to Bolt 1 LP for $65.6 million "
            "on June 22, 2023 [Finding #481, Finding #1514]. The full recorded title "
            "history thus spans four parties over 34 years: Birch Wathen School (1989) "
            "to Nine East 71st Street Corporation (1989–2011) to Maple Inc (2011–2021) "
            "to Back To NYC 71 LLC (2021–2023) to Bolt 1 LP (2023–present).</p>"
        ),
    },
    {
        "id": "address-network-and-control-indicators",
        "title": "Address Network and Control Indicators",
        "viz": None,
        "content": (
            "<p>The addresses attached to Nine East 71st Street Corporation across its "
            "corporate life function as control indicators. The 1989 acquisition deed "
            "lists 41 South High Street, Columbus, Ohio — Wexner's L Brands headquarters "
            "[Finding #492]. The 1998 Wexner-to-NES transfer binder includes the Articles "
            "of Organization for NES LLC, placing the transaction firmly within Epstein's "
            "corporate formation process [Finding #2468]. The 2011 deed transfer lists "
            "301 East 66th Street, 10th Floor — Kahn's HBRK Associates office — as the "
            "grantor address. Federal court complaints document the principal place of "
            "business as 575 Lexington Avenue, Fourth Floor, where Indyke's DKIP PLLC "
            "and HBRK Associates both operated [Finding #3263, Finding #383].</p>"
            "<p>ACRIS document 2008012900966001 records a power of attorney from "
            "Abigail S. Wexner — at 15 Central Park West — to "
            "<a href=\"/dossiers/darren-indyke\">Darren Indyke</a> dated January 23, 2008, "
            "on a separate NYC property parcel (BBL 1/1114/1507). This instrument "
            "establishes a direct Wexner-Indyke property-law nexus outside the Nine East "
            "chain itself, running through the same attorney who later served as Epstein's "
            "primary lawyer and co-executor of the estate [Finding #486]. The OCCRP Aleph "
            "dataset separately confirms Indyke as Secretary of the Wexner Foundation "
            "at 8000 Walton Parkway, New Albany, Ohio [Finding #1711], reinforcing the "
            "administrative overlap between the Wexner and Epstein organizations at the "
            "individual-officer level.</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "The 1998 transaction binder (EFTA00300480) includes a Nominee Agreement and "
        "a Promissory Note. The face value of the promissory note — i.e., whether "
        "there was any recorded purchase price for the stock transfer — has not been "
        "retrieved. What did Epstein or NES LLC pay for the corporation, and who "
        "received that payment?"
    ),
    (
        "Maple Inc was registered on November 22, 2011 — approximately one month before "
        "the Nine East deed transfer on December 23, 2011. What precipitated the "
        "reorganization at that specific moment? Epstein had been operating from the "
        "property for over a decade, and the timing does not align with any known "
        "legal event. Were there any JPMorgan account restructurings, insurance "
        "policy changes, or tax planning events in late 2011 that drove the "
        "timing of the USVI re-titling?"
    ),
    (
        "The Katlyn Doe complaint (Count III) frames Nine East 71st Street Corporation "
        "as the negligent-security defendant for the ownership period ending December "
        "2011. The Lisa Doe case (1:19-cv-07773) was terminated January 5, 2021 and "
        "the Priscilla Doe case terminated March 9, 2022. Neither disposition is "
        "documented as a contested adjudication. What were the settlement terms, "
        "if any, as to Nine East 71st Street Corporation specifically, and was the "
        "corporation dissolved as part of the estate wind-down?"
    ),
    (
        "The 1998 transfer binder includes \"LHW Resignation as Director\" — confirming "
        "Wexner held a director position in the corporation. Were there other directors "
        "or shareholders at the time of transfer? The Biennial Statement in the binder "
        "would contain officer and address information as of its filing date. That "
        "document has not been separately reviewed."
    ),
    (
        "Back To NYC 71 LLC, which purchased the property for $51 million in March 2021, "
        "is registered at 24 Lansdowne Road, London W11 3LL — a Notting Hill residential "
        "address. Bolt 1 LP subsequently acquired it for $65.6 million in June 2023. "
        "The identities of the beneficial owners of Back To NYC 71 LLC and Bolt 1 LP "
        "have not been established. Were any of these buyers connected to the Epstein "
        "network, or were they arms-length purchasers with no prior Epstein exposure?"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "corporate-layering",
    "nominee-ownership",
    "asset-insulation",
    "estate-dissolution",
]

curation["curated_at"] = datetime.now(timezone.utc).isoformat()

dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)
    f.write("\n")

print("Curation written successfully.")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {curation['applicable_models']}")

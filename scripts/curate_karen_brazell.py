#!/usr/bin/env python3
"""Write curation fields into content/dossiers/karen-brazell.json."""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/karen-brazell.json")

with DOSSIER_PATH.open() as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── lead ──────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Karen Brazell is an Army veteran and career defense contractor turned federal acquisition executive whose employment history traces a direct circuit between the Department of Veterans Affairs procurement office and Science Applications International Corporation. She served as VA Chief Acquisition Officer and Principal Executive Director from August 2018, overseeing $30 billion in annual procurement and more than 12,000 employees, before leaving government in January 2021 to become SAIC's Vice President for Veterans Affairs Account — the role specifically responsible for managing SAIC's business with the agency she had just left [Finding #5416]. SAIC completed more than $935 million in VA task orders and held more than $800 million in active VA contracts during her commercial tenure, and financial disclosures placed her SAIC stock holdings in the $100 million to $250 million range [Finding #5261].</p>"
    "<p>She returned to the VA in January 2025 as Senior Adviser to Secretary Collins under the new Trump administration, and in June 2025 was nominated as Under Secretary for Benefits — the executive who sets programmatic priorities for the Veterans Benefits Administration, which administers $189 billion in annual payments to six million veterans and controls a $4 billion discretionary budget [Finding #5416] [Finding #5419]. During the DOGE-era contract review she helped design as senior adviser, 2,500 of 76,000 VA contracts were cancelled. SAIC's approximately $70 million in annual VA business received zero cancellations. When Senator Blumenthal raised this at the September 10, 2025 confirmation hearing, Brazell testified: \"I have not reviewed any contracts of my former employer. Again, I am not a contracting authority\" [Finding #5417]. Senator King responded: \"You just lost my vote on this nomination\" [Finding #5417].</p>"
    "<p>Brazell withdrew her nomination on October 8, 2025, citing personal reasons, following Senate Veterans Affairs Committee challenges on three issues: the SAIC contract exemption, her role in designing the cancellation review structure, and proposed changes to benefits eligibility based on veterans' financial means [Finding #5418]. No public ethics recusal agreement regarding SAIC was produced before or during the confirmation process; when asked about ethics compliance she stated only \"I've met all the requirements of the law\" and confirmed she had communicated with SAIC solely for financial disclosure purposes [Finding #5420]. Approximately 1,400 VBA employees departed through voluntary separation programs and roughly 1,000 claims adjudicators left during her advisory tenure [Finding #5422].</p>"
)

# ── system_role ───────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Brazell occupies the structural position of a procurement executive whose government and private-sector roles were mirror images of each other: as VA Chief Acquisition Officer she oversaw the procurement system that awards SAIC contracts; as SAIC VP she managed the business that collected those contracts; as VA Senior Adviser she participated in the review process that determined which contracts survived DOGE-era cuts. Her nomination represented an attempt to install a person with $100–250 million in SAIC equity as the executive who sets programmatic requirements that drive IT procurement at the agency responsible for that equity's value."
)

# ── sections ──────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "career-circuit",
        "title": "Career Circuit: VA Procurement to SAIC and Back",
        "viz": "ego_network",
        "content": (
            "<p>Brazell's career describes a closed loop between VA acquisition authority and the contractor that benefited from it. After Army service (1984–1988) and a period in defense contracting, she joined the Navy as a civil servant in 2006, eventually reaching White House Military Office Chief of Staff (2015–2018). In August 2018 she moved to VA as Chief Acquisition Officer and Principal Executive Director, positions that placed her at the top of the agency's $30 billion procurement apparatus and gave her authority over 12,000 employees [Finding #5416]. She simultaneously served as Acting Assistant Secretary for the Office of Enterprise Integration from April 2020 until her January 2021 retirement [Finding #5416].</p>"
            "<p>Within months of leaving government she joined <a href=\"/dossiers/saic\">SAIC</a> as VP for Veterans Affairs Account — the business development role dedicated to winning and retaining contracts from her former agency. SAIC held more than $935 million in completed VA task orders and more than $800 million in active contracts, including Benefit Gateway Services (claims processing support), VAProfile Longitudinal Veteran Record (the core veteran identity system), and the Enterprise Services Integrated Platform (data consolidation) [Finding #5261] [Finding #5419]. SAIC acquired Halfaker and Associates in July 2021 for $250 million, partly for Halfaker's top-five Technology Transformation and Operations (T4NG) contract position and its VA portfolio, and Brazell's account role absorbed that expanded business [Finding #5261].</p>"
            "<p>She returned to VA in January 2025 as Senior Adviser to Secretary Collins and was nominated for Under Secretary for Benefits in June 2025, a Senate-confirmed position that would have placed her in charge of the VBA — the very component whose IT infrastructure is operated by SAIC systems she had spent four years selling. Her SAIC stock holdings remained in the $100 million to $250 million range through the nomination period [Finding #5261] [Finding #5416].</p>"
        ),
    },
    {
        "id": "contract-review-conduct",
        "title": "Role in DOGE-Era Contract Review and SAIC Exemption",
        "viz": None,
        "content": (
            "<p>During her tenure as VA Senior Adviser, Brazell testified that her role was \"to recommend a review structure for career leaders\" in the DOGE-era contract cancellation process [Finding #5422]. That structure determined which of VA's 76,000 contracts were flagged for cancellation. Of the 2,500 contracts ultimately cancelled, none belonged to SAIC, which received approximately $70 million annually from VA [Finding #5417]. Senator Blumenthal stated this on the record during the September 10, 2025 hearing: SAIC \"receives $70 million from the VA — no contracts cancelled\" [Finding #5417].</p>"
            "<p>Brazell's defense was procedural — she was not a contracting authority and had not reviewed SAIC contracts directly. The structural problem senators identified, however, was that the framework designer does not need to sign contracts to determine which vendors' contracts receive scrutiny and which do not [Finding #5419]. The Under Secretary for Benefits role she sought sets programmatic priorities and requirements that determine what IT capabilities the VBA procures, which in turn shapes the scope of future contract competitions. Even without signatory authority, the position's programmatic power is the upstream determinant of contract value [Finding #5419].</p>"
            "<p>Senator King's public declaration that the confirmation had lost his vote, combined with at least two other senators' stated concerns, left the nomination without a clear path to committee approval [Finding #5417] [Finding #5418]. Brazell withdrew October 8, 2025. The Congressional Record (CREC-2025-10-08-pt1-PgS7040-7) reflects the withdrawal; VA relaunched the search for a new nominee in January 2026, with Margarita Devlin performing delegable duties of Under Secretary for Benefits in the interim [Finding #5418].</p>"
        ),
    },
    {
        "id": "ethics-and-disclosure",
        "title": "Ethics Compliance and Disclosure Record",
        "viz": None,
        "content": (
            "<p>No public ethics recusal agreement regarding SAIC was filed or produced before or during Brazell's confirmation process [Finding #5420]. Federal ethics rules generally require executive branch employees to recuse from matters affecting former employers for one year and from matters affecting financial holdings that create conflicts until those holdings are divested or placed in a qualified blind trust. Brazell's SAIC equity — valued at $100 million to $250 million in her financial disclosure — was reported but no public divestiture commitment or recusal pledge was entered into the record [Finding #5420] [Finding #5261].</p>"
            "<p>When senators asked directly about ethics compliance, she said: \"I've met all the requirements of the law.\" When asked whether she had communicated with SAIC since joining VA, she confirmed contact only \"for financial disclosure purposes\" [Finding #5420]. Multiple senators on the Veterans Affairs Committee expressed frustration with the indirectness of her answers. The Nimitz Group's hearing analysis flagged the absence of a public recusal agreement as the central unanswered ethics question of the confirmation [Finding #5420].</p>"
        ),
    },
    {
        "id": "vba-workforce-impact",
        "title": "VBA Workforce Reductions During Advisory Tenure",
        "viz": None,
        "content": (
            "<p>Between January and October 2025, while Brazell served as VA Senior Adviser, approximately 1,400 VBA employees departed through voluntary separation programs and roughly 1,000 claims adjudicators left the agency [Finding #5422]. Claims adjudicators are the personnel who process disability and pension claims for veterans; their departure created a backlog risk in a system already managing pending claims in the hundreds of thousands. Senator King described the contract cancellation process Brazell helped design as \"one of the most disastrous\" he had witnessed in decades in government [Finding #5422].</p>"
            "<p>The Under Secretary for Benefits position she was nominated to fill oversees 56 regional offices, 540 intake sites, and $189 billion in annual benefits disbursements [Finding #5419]. The combination of workforce reduction in claims processing and the pending appointment of an executive with undisclosed recusal obligations to the agency's primary IT contractor was the factual core of the Senate committee's objections [Finding #5417] [Finding #5419] [Finding #5422].</p>"
        ),
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    "Did any formal ethics recusal agreement covering SAIC exist in Brazell's Senior Adviser appointment papers, and if so, why was it not produced at the confirmation hearing?",
    "What specific criteria did Brazell's recommended contract review structure use to classify contracts for cancellation, and are those criteria documents subject to FOIA? [Finding #5417] [Finding #5422]",
    "Were SAIC contracts excluded from the cancellation pool at the category or vendor level, and who had authority to set those exclusion parameters within Brazell's recommended review structure?",
    "What is the current status of Brazell's SAIC equity holdings — were they divested, placed in trust, or retained after her October 2025 withdrawal from the nomination? [Finding #5261]",
    "What programmatic changes to VBA IT procurement priorities, if any, were initiated during Brazell's advisory tenure that would affect the scope of SAIC's active task orders under Benefit Gateway Services, VAProfile, or ESIP? [Finding #5419]",
]

# ── applicable_models ─────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "revolving-door",
    "regulatory-capture",
    "manufactured-dependency",
    "access-capitalism",
]

# Preserve existing metadata fields
curation.setdefault("key_finding_ids", [5261, 5416, 5417, 5418, 5419, 5420, 5422])

with DOSSIER_PATH.open("w") as f:
    json.dump(dossier, f, indent=2)
    f.write("\n")

print(f"Wrote curation to {DOSSIER_PATH}")

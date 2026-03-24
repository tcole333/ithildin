#!/usr/bin/env python3
"""
Curation script for CIC Digital LLC dossier.
Writes the curation field to content/dossiers/cic-digital-llc.json.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content" / "dossiers" / "cic-digital-llc.json"


def build_curation() -> dict:
    lead = (
        '<p>CIC Digital LLC is a Delaware limited liability company wholly owned by The Donald J. Trump '
        'Revocable Trust. It serves as the primary Trump Organization vehicle for the meme-coin and '
        'digital asset business line that the Trump family launched three days before the presidential '
        'inauguration on January 17, 2025. CIC Digital co-owns <a href="/dossiers/fight-fight-fight-llc">'
        'Fight Fight Fight LLC</a> — the token issuer — with Celebration Cards LLC (Wyoming), and holds '
        'the largest single tranche of TRUMP token supply: 36% of the 1 billion token total under the '
        '"Creators &amp; CIC Digital 1" wallet group. Together, CIC Digital and Fight Fight Fight LLC '
        'initially held 800 million tokens (80% of total supply). Both entities receive ongoing revenue '
        'from every TRUMP token trade. [Finding #3689, SEC EDGAR S-1/A accession 000199937126003355]</p>'
        '<p>By May 22, 2025, the Trump family had earned over $320 million in aggregate trading fees '
        'since launch. [Finding #3740] CIC Digital operates in parallel with <a href="/dossiers/dt-marks-defi-llc">'
        'DT Marks DEFI LLC</a>, the Trump family vehicle for the separate <a href="/dossiers/world-liberty-financial">'
        'World Liberty Financial</a> venture — two structurally distinct crypto businesses sharing the same '
        'beneficial owner and the same presidential platform.</p>'
    )

    system_role = (
        "CIC Digital LLC is the Trump Organization's designated vehicle for meme-coin revenue extraction: "
        "it holds the dominant insider allocation in a token launched at the moment of maximum political "
        "leverage, earns perpetual trading fees from every secondary transaction, and has attracted "
        "capital from foreign nationals and entities whose regulatory outcomes subsequently moved in "
        "their favor. The entity sits at the intersection of presidential office-holding and "
        "commercial digital asset issuance in a structure with no precedent in U.S. disclosure law."
    )

    sections = [
        {
            "id": "entity-structure-and-ownership",
            "title": "Entity Structure and Ownership",
            "viz": None,
            "content": (
                '<p>CIC Digital LLC is wholly owned by The Donald J. Trump Revocable Trust, as disclosed '
                'in Trump\'s 2024 personal financial disclosure. The entity jointly owns Fight Fight Fight '
                'LLC alongside Celebration Cards LLC, a Wyoming entity registered through Cloud Peak Law '
                'LLC in Sheridan, Wyoming — a registered agent known for anonymous LLC formation. '
                '<a href="/dossiers/bill-zanker">Bill Zanker</a> is identified as the authorized person '
                'on Fight Fight Fight LLC\'s Delaware filing and leads day-to-day operations; he conceived '
                "Trump's NFT and crypto ventures and organized the May 2025 top-holder dinner. [Finding #4119]</p>"
                '<p>Fight Fight Fight LLC is the formal token issuer. Its name references Trump\'s '
                'reaction after the July 2024 assassination attempt. The ownership chain means that '
                'trading-fee revenue flows upward from Fight Fight Fight LLC to CIC Digital LLC and '
                'Celebration Cards LLC, and from CIC Digital to the Trump Revocable Trust. The '
                'Canary Capital S-1/A (SEC Registration 333-289857, filed February 13, 2026) is the '
                'most complete primary-source description of this structure, describing CIC Digital as '
                '"an affiliate of President Trump" and detailing all six insider wallet groups '
                'with their staggered unlock schedules. [Finding #3689]</p>'
                '<p>CIC Digital operates alongside but structurally separate from '
                '<a href="/dossiers/dt-marks-defi-llc">DT Marks DEFI LLC</a>, the Trump family vehicle '
                'holding 60% equity in <a href="/dossiers/world-liberty-financial">World Liberty Financial</a> '
                'and its USD1 stablecoin. The two entities share a beneficial owner — '
                '<a href="/dossiers/donald-trump">Donald Trump</a> — and collectively represent parallel '
                'commercial crypto positions held by a sitting president. [Finding #3689, connection #2471]</p>'
            ),
        },
        {
            "id": "token-launch-and-insider-allocation",
            "title": "Token Launch and Insider Allocation",
            "viz": "timeline",
            "content": (
                '<p>The TRUMP token launched on January 17, 2025 — three days before the presidential '
                'inauguration. Within 48 hours the token reached an approximate market capitalization of '
                '$73 billion before declining sharply. The MELANIA token launched on January 18, further '
                'diluting TRUMP holders. [Finding #3732]</p>'
                '<p>At launch, CIC Digital LLC and Fight Fight Fight LLC collectively held 800 million of '
                'the 1 billion total tokens (80%). The insider allocation is divided across six wallet '
                'groups with staggered three-month unlock cliffs and 24-month linear vesting: Group 1 '
                '(36% of supply) carries a three-month cliff from launch with a first unlock date of '
                'April 18, 2025; Group 2 (18%) at six months; Group 3 (18%) at 12 months. As of '
                'February 11, 2026, approximately 53% of the total supply had unlocked and the market '
                'capitalization stood at $1.68 billion at a price of $3.14. [Finding #3689]</p>'
                '<p>The token runs on the Solana blockchain via the Meteora liquidity pool. Initial '
                'liquidity consisted of 200 million tokens (20% of supply) paired with SOL. All '
                'transaction fees from TRUMP trading flow to CIC Digital LLC and Celebration Cards LLC '
                'as owners of Fight Fight Fight LLC — the fee structure is permanent and is not subject '
                'to the unlock schedule that governs the token allocation. The launch timing — three '
                'days before assuming the regulatory authority that governs cryptocurrency oversight — '
                'concentrated retail speculative demand at the moment of highest political salience. '
                '[Finding #3732]</p>'
            ),
        },
        {
            "id": "gala-dinner-and-foreign-national-holders",
            "title": "Gala Dinner and Foreign National Holders",
            "viz": None,
            "content": (
                '<p>On May 22, 2025, President Trump hosted a black-tie dinner at his Virginia golf club '
                'for the top 220 TRUMP token holders, who had collectively spent approximately $148 '
                'million to qualify. Bloomberg analysis of the top 25 wallet holders estimated that 19 '
                'were likely foreign nationals. [Finding #3740]</p>'
                '<p>The largest single holder at the dinner was <a href="/dossiers/justin-sun">Justin '
                'Sun</a>, founder of the Tron blockchain, who faced an active SEC fraud case at the '
                'time. The SEC paused Sun\'s case on February 27, 2025, citing "public interest" — '
                'one of 10 cryptocurrency enforcement actions dropped in the 70-day window from '
                'inauguration to March 27, 2025. [Finding #6515] Sun had separately invested $75 '
                'million in <a href="/dossiers/world-liberty-financial">World Liberty Financial</a> '
                'tokens and attended the May 22 dinner as the top TRUMP holder. [Connection #2192]</p>'
                '<p>GD Culture Group, a Nasdaq-listed company with eight employees, zero revenue, and '
                'a business model dependent on TikTok, announced a $300 million plan to purchase '
                'Bitcoin and TRUMP tokens. The $300 million was funded through a stock sale to an '
                'unnamed British Virgin Islands entity. The timing correlated with Trump\'s signaling '
                'of a TikTok ban delay. [Finding #3769] The BVI funding source for the GD Culture '
                'purchase has not been publicly identified.</p>'
                '<p>Representatives Sean Casten and Christopher Smith formally demanded a DOJ '
                'investigation, citing potential violations of federal bribery statutes and the '
                'foreign emoluments clause. Thirty-five House Democrats co-signed. Even cryptocurrency '
                'industry lobbyists expressed concern that the gala structure was jeopardizing passage '
                'of the GENIUS Act stablecoin legislation. By the day following the dinner, the '
                'TRUMP token price had declined 16%. [Finding #3740]</p>'
                '<p>By the time of the gala, the Trump family had earned over $320 million in '
                'aggregate trading fees since launch. Approximately 764,000 retail wallets of '
                'small-denomination holders had lost money on their TRUMP token positions. '
                '[Finding #3740]</p>'
            ),
        },
        {
            "id": "regulatory-environment",
            "title": "Regulatory Environment",
            "viz": None,
            "content": (
                '<p>On inauguration day, January 20, 2025, the SEC dropped its case against Nova Labs — '
                'the first of 10 cryptocurrency enforcement actions closed in the subsequent 70 days. '
                'The sequence: January 23, the SEC announced its Crypto Task Force; February 21, '
                'cases against Robinhood, OpenSea, Uniswap, and Crypto.com were closed; February 27, '
                'the Coinbase case was dismissed and Justin Sun\'s case was paused; March 27, cases '
                'against Kraken, ConsenSys, Cumberland, and Gemini were dropped. All closures occurred '
                'before new SEC Chair Paul Atkins was sworn in on April 21, 2025. [Finding #6515]</p>'
                '<p><a href="/dossiers/jay-clayton">Jay Clayton</a>, Trump\'s first-term SEC Chair '
                '(2017–2020), was installed as U.S. Attorney for the Southern District of New York in '
                'April 2025. Clayton\'s post-government financial disclosure, filed under the name '
                '"Walter Joseph Clayton," documented holdings in Fireblocks, Coinbase Asset Management, '
                'and Electric Capital Partners — digital asset firms — alongside his Apollo Global '
                'Management chairmanship and Sullivan &amp; Cromwell senior policy advisor role. '
                'Clayton sat atop the federal prosecutor\'s office with primary jurisdiction over '
                'securities fraud while holding disclosed positions in the crypto sector he had '
                'overseen as regulator. [Finding #5198]</p>'
                '<p>No federal disclosure framework required Trump to divest CIC Digital LLC upon '
                'taking office. Presidential conflict-of-interest statutes (18 U.S.C. § 208) do not '
                'apply to the President or Vice President. The Office of Government Ethics rules '
                'governing blind trusts apply to executive branch employees, not to the President. '
                'The structure thus operates in a legal gap where the largest single holder of a '
                'commercially issued digital asset is the President of the United States, with no '
                'mandatory divestiture, blind trust requirement, or trading restriction.</p>'
            ),
        },
    ]

    open_questions = [
        (
            "The BVI entity that funded GD Culture Group's $300 million stock purchase — enabling its "
            "TRUMP token acquisition — has not been publicly identified. What is the beneficial owner "
            "of that BVI entity, and is it connected to Chinese state-linked capital?"
        ),
        (
            "Celebration Cards LLC (Wyoming, registered through Cloud Peak Law LLC) co-owns Fight Fight "
            "Fight LLC and receives trading fee revenue alongside CIC Digital. Who is the beneficial "
            "owner of Celebration Cards LLC, and is the entity connected to any individual in the "
            "Trump Organization or Trump family?"
        ),
        (
            "The six CIC Digital/Fight Fight Fight insider wallet groups have staggered unlock schedules "
            "running through at least mid-2027. What is the aggregate dollar value of tokens that have "
            "been liquidated by CIC Digital and Celebration Cards as of the current date, and through "
            "which exchanges or OTC desks?"
        ),
        (
            "Justin Sun's WLFI wallet was frozen by the WLFI team (595 million tokens, approximately "
            "$107 million) after he attempted to move tokens to exchanges post-TGE. Was any similar "
            "freeze or wallet restriction applied to any TRUMP token wallet associated with Sun or "
            "other gala dinner attendees whose regulatory proceedings were concurrently paused?"
        ),
        (
            "The Canary Capital S-1/A ETF registration (333-289857) would create a regulated investment "
            "product tracking a token in which the President holds an 80% insider position. Has the "
            "SEC issued any comment letters on this filing, and has any formal conflict-of-interest "
            "review been conducted of the registration?"
        ),
        (
            "The Houston shipping company that purchased $20 million in TRUMP tokens reportedly did so "
            "to advocate for U.S.-Mexico free trade policy. Is there documentation of any subsequent "
            "policy meeting, executive order, or trade negotiation position that benefited the company "
            "or its principals?"
        ),
    ]

    applicable_models = [
        "pay-to-play",
        "regulatory-capture",
        "jurisdictional-arbitrage",
        "conflict-of-interest",
        "offshore-opacity",
        "access-capitalism",
        "parallel-financial-system",
        "disclosure-timing",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
    }


def main():
    if not DOSSIER_PATH.exists():
        print(f"ERROR: dossier not found at {DOSSIER_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(DOSSIER_PATH, "r", encoding="utf-8") as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    # Preserve existing scaffold fields (key_finding_ids, key_identifiers, section_suggestions, curated_at)
    curation.update(build_curation())
    curation["curated_at"] = datetime.utcnow().isoformat()
    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w", encoding="utf-8") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(curation['lead'])} chars")
    print(f"  system_role: {len(curation['system_role'])} chars")
    print(f"  sections: {len(curation['sections'])}")
    print(f"  open_questions: {len(curation['open_questions'])}")
    print(f"  applicable_models: {len(curation['applicable_models'])}")


if __name__ == "__main__":
    main()

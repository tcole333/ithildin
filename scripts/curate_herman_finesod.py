#!/usr/bin/env python3
"""Curate the Herman Finesod dossier."""

import json
from datetime import datetime
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content" / "dossiers" / "herman-finesod.json"


def build_curation() -> dict:
    lead = (
        "<p>Herman Finesod was the founder and controlling principal of <a href='/dossiers/jackie-fine-arts-inc'>Jackie Fine Arts Inc</a>, "
        "a Pennsylvania-incorporated entity that sold reproduction rights to Picasso and other artists' works to more than 2,000 investors "
        "at prices of $225,000&ndash;$250,000 per master, against an actual acquisition cost of roughly $10,000, generating $409 million in "
        "notes receivable by 1986 [Finding #2131]. Finesod controlled Jackie Fine Arts through M and J Holding Corporation, whose 1986 tax return "
        "reported total assets of $1.33 billion [Finding #2140]. Before Jackie Fine Arts, Finesod operated Hambrose Stamps Ltd, a philatelic tax "
        "shelter under the same structural logic: rare postage stamps acquired for $3.60 each were sold to investors at $106,000&ndash;$207,000 "
        "each, generating over $160 million in philatelic notes; the United States sued Finesod under 26 U.S.C. &sect; 6700 for promoting abusive "
        "tax shelters [Finding #2132]. The stamp scheme preceded and was superseded by the art master scheme; Finesod also faced copyright disputes "
        "involving Museum Boutique Intercontinental during this period [Finding #2132].</p>"
        "<p>Following nationwide civil litigation in more than ten federal districts, the bellwether case <em>Faircloth v. Finesod</em>, "
        "938 F.2d 513 (4th Cir. 1991), produced a jury verdict of fraud, RICO violations, and civil conspiracy against Finesod personally. "
        "The judgment against Finesod totaled $4.3 million in compensatory, trebled RICO, and punitive damages, with an additional $5 million "
        "in punitive damages against Jackie Fine Arts and $615,170 in attorney fees; the Fourth Circuit affirmed the RICO judgment and issued a "
        "permanent injunction while reversing state fraud claims [Finding #2120]. Total civil judgments against Finesod across the stamp and art "
        "schemes exceeded $9 million; judgments against Jackie Fine Arts exceeded $5 million [Finding #2132]. Finesod filed personal bankruptcy "
        "in the Western District of Pennsylvania in 1994 (Case No. 94-20640) [Finding #2121].</p>"
        "<p>Finesod's relevance to the broader investigation derives from a single institutional link: <a href='/dossiers/bernard-indyke'>Bernard Indyke</a> "
        "served as manager and board member of Jackie Fine Arts, which was represented in litigation by <a href='/dossiers/gold-and-wachtel'>Gold and Wachtel</a> "
        "&mdash; the same firm that employed Bernard's son <a href='/dossiers/darren-indyke'>Darren Indyke</a> from 1986, first as a pre-law assistant "
        "and later as an associate, and that served as process agent for Jeffrey E. Epstein, Inc. from at least November 1988. William B. Wachtel "
        "personally appeared as defense counsel for Finesod in the Fourth Circuit RICO appeal while simultaneously employing the son of Finesod's "
        "own company manager [Finding #2133, Connection #1086]. As of 2018, Finesod resided at 200 East 62nd Street, New York, NY 10021, where "
        "building owner 200 East 62nd Street Owner LLC filed suit against him in November 2018 at approximately age 84, despite the decade-old "
        "civil judgments against him [Finding #2134].</p>"
    )

    system_role = (
        "Finesod is the upstream originator of a structural pattern &mdash; layered corporate control, inflated professional valuations, "
        "coordinated third-party opinions, and non-recourse note financing &mdash; whose institutional residue persisted through Jackie Fine "
        "Arts, into Gold and Wachtel, and from there into the Epstein corporate network managed by Darren Indyke. His direct significance "
        "to this investigation is as the employer of Bernard Indyke, which created the patronage relationship that placed Darren Indyke at "
        "Gold and Wachtel and, subsequently, at the center of Epstein's financial infrastructure."
    )

    sections = [
        {
            "id": "tax-shelter-operations",
            "title": "Tax Shelter Operations: Stamps, Then Art",
            "viz": "timeline",
            "content": (
                "<p>Finesod ran two sequential tax shelter operations using the same structural architecture. The first, Hambrose Stamps Ltd, "
                "sold rare postage stamps to investors as tax deductions: stamps acquired for $3.60 each were sold at $106,000&ndash;$207,000 each, "
                "with the price differential presented as a deductible investment loss. Over $160 million in philatelic notes were issued. The United "
                "States sued Finesod under 26 U.S.C. &sect; 6700, the statutory provision prohibiting the promotion of abusive tax shelters, "
                "in litigation documented in <em>Newmyer v. Philatelic Leasing</em>, 888 F.2d 385 (6th Cir. 1989) [Finding #2132].</p>"
                "<p>The second and larger operation was <a href='/dossiers/jackie-fine-arts-inc'>Jackie Fine Arts Inc</a>. Reproduction rights to "
                "Picasso works and other masters were acquired through intermediary AMI from Paraselenes SA &mdash; a company controlled by Marina "
                "Picasso &mdash; at approximately $10,000 per master, then sold to more than 2,000 investors at $225,000&ndash;$250,000 each, "
                "supported by fraudulent independent appraisals. Sigmund Rothschild and F. Peter Rose, who shared an office and a secretary, "
                "valued the same masters at $700,000&ndash;$750,000; Rothschild paid Rose a $50 kickback per transaction; a Los Angeles law firm "
                "provided tax opinions while secretly receiving one percent of cash proceeds [Finding #2131]. By 1986, Jackie Fine Arts carried "
                "$409 million in notes receivable, and its parent M and J Holding Corporation reported $1.33 billion in total assets [Finding #2140]. "
                "The IRS disallowed all resulting deductions; the Sixth Circuit affirmed in <em>Rose v. Commissioner</em>, 868 F.2d 851 (6th Cir. 1989), "
                "holding that the art master packages lacked economic substance [Finding #2135]. Finesod also faced copyright disputes involving "
                "Museum Boutique Intercontinental during the same period [Finding #2132].</p>"
                "<p>Finesod appeared in 16 SEC EDGAR filings, all related to Electronic Control Security Inc (CIK 0000803044, Clifton, NJ, SIC 3669) "
                "and MFC Development Corp (CIK 0001125532, New Rochelle, NY) &mdash; two entities distinct from the art and stamp operations, "
                "indicating continued corporate activity into the 1990s. He challenged the IRS in the Southern District of New York on two occasions, "
                "in 1987 and 1992 (<em>Finesod v. United States</em>) [Finding #2121]. No corporate registrations for Jackie Fine Arts have been "
                "located in any state registry searched, including Florida, New York, New Mexico, Pennsylvania, California, the U.S. Virgin Islands, "
                "or the United Kingdom; a German subsidiary, Jackie Fine Arts GmbH (Handelsregister HRB 58801, Munich), was registered and has "
                "since been removed [Finding #2121].</p>"
            ),
        },
        {
            "id": "legal-proceedings",
            "title": "Legal Proceedings",
            "viz": "timeline",
            "content": (
                "<p>Civil litigation against Finesod and Jackie Fine Arts began in 1983 and extended through at least 1992 across more than ten "
                "federal districts: <em>Turner v. JFA</em> (S.D. Cal. 1983), <em>Menish v. JFA</em> (C.D. Cal. 1984), <em>Ross v. JFA</em> "
                "(D.S.C. 1985), <em>Westheimer v. Finesod</em> (S.D. Tex. 1986), <em>Nichols v. JFA</em> (D. Me. 1987), "
                "<em>Bergin v. JFA</em> (D. Minn. 1987), <em>Faircloth v. JFA</em> (E.D.N.Y. 1:89-mc-00437, not terminated until 2016), "
                "and multiple Ross actions in S.D. Cal. through 1992 [Finding #2106].</p>"
                "<p>The controlling decision is <em>Faircloth v. Finesod</em>, 938 F.2d 513 (4th Cir. 1991). At trial in the Eastern District of "
                "New York, a jury found Finesod liable for fraud, civil conspiracy, and RICO violations. Finesod did not appear at trial. The jury "
                "awarded $469,839 in compensatory damages, trebled to $1,409,517 under RICO, plus $2.5 million in punitive damages against Finesod "
                "personally, $5 million in punitive damages against Jackie Fine Arts, $500,000 in punitive damages against Rose, and $615,170 in "
                "attorney fees [Finding #2120]. On appeal, the Fourth Circuit reversed the state law fraud claims but affirmed the RICO judgment "
                "and issued a permanent injunction. <a href='/dossiers/gold-and-wachtel'>Gold and Wachtel</a>, through William B. Wachtel, appeared "
                "on brief as defense counsel for Finesod in this appeal [Finding #2133, Connection #1086].</p>"
                "<p>Finesod filed personal bankruptcy in the Western District of Pennsylvania in 1994 (Case No. 94-20640) [Finding #2121]. Total "
                "civil judgments against him exceeded $9 million across the stamp and art operations [Finding #2132]. Despite this, he maintained "
                "a residence at 200 East 62nd Street, New York, NY 10021, a building on the Upper East Side; in November 2018, at approximately "
                "age 84, the building owner 200 East 62nd Street Owner LLC filed suit against him in New York state court "
                "(UniCourt case ny-sue1-200-east-62nd-street-owner-llc-v-herman-finesod-et-al-404037) [Finding #2134].</p>"
            ),
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "content": (
                "<p><strong><a href='/dossiers/bernard-indyke'>Bernard Indyke</a></strong> served as manager and board member of "
                "<a href='/dossiers/jackie-fine-arts-inc'>Jackie Fine Arts Inc</a>, Finesod's principal operating entity, during the period of "
                "the fraud [Connection #1076, #1082]. This role was documented in footnote 1 of the <em>Faircloth v. Finesod</em> appellate record "
                "and confirmed through LittleSis entity 349261. The significance of this connection is that Jackie Fine Arts was a client of "
                "<a href='/dossiers/gold-and-wachtel'>Gold and Wachtel</a>, and Bernard's position at the company predated and enabled his "
                "patronage relationship with the firm. Bernard placed his son <a href='/dossiers/darren-indyke'>Darren Indyke</a> at Gold and "
                "Wachtel in 1986, where Darren first encountered Jeffrey Epstein as a client; Darren returned to the firm after Cornell Law School "
                "and subsequently became Epstein's exclusive in-house attorney for over two decades.</p>"
                "<p><strong><a href='/dossiers/gold-and-wachtel'>Gold and Wachtel</a></strong>, through <strong>William B. Wachtel</strong>, "
                "defended Finesod on appeal in the Fourth Circuit RICO case while simultaneously employing the son of Finesod's own company manager "
                "[Finding #2133, Connection #1086]. Wachtel's personal involvement in the appeal &mdash; he was on brief as defense counsel &mdash; "
                "means he was directly managing Finesod's defense at the same time Bernard Indyke's son Darren was working at his firm. When "
                "subsequently asked by The Daily Beast about Bernard's role, Wachtel described him as a mailroom employee; court records establish "
                "he was manager and board member of a Gold and Wachtel client [Finding #2098].</p>"
                "<p><strong><a href='/dossiers/darren-indyke'>Darren Indyke</a></strong> is connected to Finesod through the institutional chain "
                "described above [Connection #1089]: Finesod controlled Jackie Fine Arts; Bernard Indyke managed Jackie Fine Arts; Bernard placed "
                "Darren at Gold and Wachtel; Gold and Wachtel represented Epstein from 1988; Darren became Epstein's exclusive legal operative "
                "circa 1996. The synthesis finding (#2144) establishes that the structural practices used at Jackie Fine Arts &mdash; shell entity "
                "layering, inflated professional valuations, coordinated third-party opinions, non-recourse notes, and international subsidiaries "
                "&mdash; appear in parallel form in the Epstein corporate network Darren subsequently managed.</p>"
            ),
        },
    ]

    open_questions = [
        "Finesod's 1986 M and J Holding tax return reported $1.33 billion in assets — what additional entities sat within that holding structure beyond Jackie Fine Arts, and were any connected to the Electronic Control Security or MFC Development Corp filings?",
        "No corporate registration for Jackie Fine Arts has been found in any state searched; the Pennsylvania incorporation is referenced in court records but not located in the registry. Was the entity dissolved, revoked, or registered under a variant name?",
        "Finesod litigated against the United States in the SDNY on two separate occasions (1987 and 1992) — what were the precise claims and outcomes in those proceedings, beyond what appears in the appellate record?",
        "Finesod maintained an Upper East Side residence (200 East 62nd Street) through at least 2018, over two decades after the $9 million in civil judgments and his 1994 bankruptcy. What asset protection mechanisms, if any, preserved that tenancy?",
        "William Wachtel was personally on brief in the Finesod RICO appeal while employing Bernard Indyke's son at the same firm. Was Wachtel's personal involvement in the appeal documented in correspondence with Finesod, and what was the firm's fee arrangement?",
    ]

    applicable_models = [
        "circular-valuation",
        "complexity-as-credential",
        "legal-shield",
        "shell-company",
        "enabler-gradient",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
        "curated_at": datetime.utcnow().isoformat(),
    }


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})
    new_curation = build_curation()

    # Preserve key_finding_ids, key_identifiers, and section_suggestions from existing curation
    for key in ("key_finding_ids", "key_identifiers", "section_suggestions"):
        if key in existing_curation:
            new_curation[key] = existing_curation[key]

    dossier["curation"] = new_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(new_curation['lead'])} chars")
    print(f"  system_role: {len(new_curation['system_role'])} chars")
    print(f"  sections: {len(new_curation['sections'])}")
    print(f"  open_questions: {len(new_curation['open_questions'])}")
    print(f"  applicable_models: {new_curation['applicable_models']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Curation script for Robert Gold dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/robert-gold.json")

CURATION = {
    "lead": (
        "<p>Robert Gold (born September 16, 1945) is a New York attorney whose career arc runs"
        " from federal prosecutor to private practitioner and, in between, to co-founding partner"
        " of <a href=\"/dossiers/gold-and-wachtel\">Gold &amp; Wachtel</a> &mdash; the firm that"
        " first brought <a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> into the legal"
        " mainstream. Gold graduated from Columbia University (BA Economics, 1967) and Cornell"
        " Law School (JD/MBA, 1971), then spent four years as an Assistant United States Attorney"
        " in the Southern District of New York's Criminal Division (1973&ndash;1977), assigned to"
        " both the Official Corruption Unit and the Securities Fraud Unit. That prosecutorial"
        " background &mdash; specifically his knowledge of how SDNY investigations were organized"
        " and whom to contact &mdash; would later become the central element of his documented"
        " value to Epstein (Finding #2096, EFTA01332942).</p>"
        "\n\n"
        "<p>Gold returned to private practice and co-founded Gold &amp; Wachtel in 1984 with"
        " <a href=\"/dossiers/harry-wachtel\">Harry Wachtel</a> at 10 East 53rd Street, Manhattan."
        " The firm became Epstein's process agent and institutional legal home from approximately"
        " 1988 onward, and it is the origin point for both <a href=\"/dossiers/darren-indyke\">Darren"
        " Indyke</a> and <a href=\"/dossiers/jeffrey-schantz\">Jeffrey Schantz</a> &mdash; the two"
        " successive individuals who ran Epstein's day-to-day operations for the following three"
        " decades. Gold departed the firm in the late 1990s, joining Ranieri &amp; Co (1998&ndash;2000)"
        " for crisis management work, then Of Counsel at Sullivan &amp; Worcester, then litigation"
        " partner at DLA Piper Rudnick (July 2006), Wilson Sonsini Goodrich &amp; Rosati (2008/2013),"
        " and finally Mishcon de Reya's New York office (2014). A June 2014 email from his Mishcon"
        " account reads: <em>\"Jeffrey: I just spent the day in Paris working with Alan. Think its"
        " time to get reunited at last?\"</em> (EFTA01920882). Thirteen documents in the DOJ"
        " corpus document his continuing personal relationship with Epstein from 2011 through 2014,"
        " including a 2001 Epstein trust naming him for debt forgiveness as &ldquo;his friend,"
        " ROBERT GOLD&rdquo; (EFTA01266298).</p>"
    ),

    "system_role": (
        "Gold occupies a specific structural position in the Epstein network: the institutional"
        " origin point. As co-managing partner of the firm where Epstein first received legal"
        " services, Gold's career provides the earliest documented connection between Epstein and"
        " the prosecutorial networks of the Southern District of New York. The allegation recorded"
        " in House Oversight documents &mdash; that Gold used those former AUSA relationships to"
        " delay SDNY action on the Towers Financial fraud until the statute of limitations had nearly"
        " expired &mdash; frames him not merely as a transactional attorney but as someone whose"
        " institutional knowledge of federal enforcement timelines could be deployed as a protective"
        " resource. His later career shows a pattern of serial lateral moves across large firms"
        " (DLA Piper, Wilson Sonsini, Mishcon de Reya) while maintaining personal contact with"
        " Epstein through correspondence and travel. Gold represents the revolving-door dynamic at"
        " its most specific: a prosecutor who built network capital in a division focused on"
        " official corruption and securities fraud, then applied that capital in private practice"
        " on behalf of a client whose exposure was precisely in those categories."
    ),

    "sections": [
        {
            "id": "career-and-credentials",
            "title": "Career and Credentials",
            "content": (
                "<p>Robert Gold's professional record is documented across corporate filings,"
                " court records, press releases, and EFTA corpus documents. After Shea &amp; Gould"
                " (1971), four years as AUSA in SDNY's Criminal Division (1973&ndash;1977), and a"
                " return to private practice in 1978, Gold co-founded <a href=\"/dossiers/gold-and-wachtel\">"
                "Gold &amp; Wachtel</a> in 1984 with <a href=\"/dossiers/harry-wachtel\">Harry H."
                " Wachtel</a> (1917&ndash;1997), a figure known for advising Martin Luther King Jr."
                " and for his executive role at Rapid American Corporation under Meshulam Riklis."
                " Gold served as co-managing partner alongside William B. Wachtel, Harry's son"
                " (Finding #2082). The firm's client record included George Steinbrenner, the"
                " successful defense of Hudson News against a Ronald Perelman hostile takeover,"
                " and representation in matters touching on Watergate, Iran-Contra, and the Marcos"
                " prosecution (Finding #2096, EFTA01332942). In 1987, Gold appeared as counsel"
                " in <em>Walters v. Fullwood</em> (SDNY) on behalf of World Sports and Entertainment"
                " (Finding #2083).</p>"
                "\n\n"
                "<p>Gold left the firm in the late 1990s. A July 2006 DLA Piper press release"
                " confirms his arrival as a litigation partner at DLA Piper Rudnick Gray Cary,"
                " describing him as a former AUSA and former co-managing partner at Gold &amp;"
                " Wachtel (Finding #2083). EFTA documents place him at Wilson Sonsini Goodrich"
                " &amp; Rosati by 2013 &mdash; one corpus document explicitly identifies him as"
                " &ldquo;Robert Gold Partner at Wilson Sonsini Goodrich and Rosati&rdquo; (EFTA02377483)"
                " &mdash; and at Mishcon de Reya's New York office by June 2014, where his email"
                " domain is robert.gold@mishcon.com (EFTA01920882). Ranieri &amp; Co, the crisis"
                " management firm founded by mortgage-backed securities pioneer Lewis Ranieri,"
                " employed Gold from approximately 1998 to 2000, a detail corroborated by FedEx"
                " shipping records from NYSG LLC to the Ranieri &amp; Co Uniondale address that"
                " also appear in the EFTA corpus (Finding #2031, EFTA01316638).</p>"
            ),
            "viz": None,
        },
        {
            "id": "towers-financial-allegation",
            "title": "Towers Financial and the Statute of Limitations Allegation",
            "content": (
                "<p>The most consequential allegation concerning Robert Gold appears in House"
                " Oversight documents derived from the James Patterson investigative narrative"
                " (HOUSE_OVERSIGHT_022081&ndash;022082). <a href=\"/dossiers/steven-hoffenberg\">Steven"
                " Hoffenberg</a>, who co-operated Towers Financial Corporation with Epstein in the"
                " late 1980s before pleading guilty to a $460 million Ponzi scheme and serving 19"
                " years in federal prison, was asked why Epstein was never charged in the same"
                " prosecution. Hoffenberg's sole response: <em>&ldquo;Ask Robert Gold.&rdquo;</em>"
                " A corroborating source in the same document states that Gold &ldquo;the former"
                " federal prosecutor who had helped Epstein recover Ana Obregon money, kept the"
                " US attorney away from Epstein until there were only a few weeks left before the"
                " statute of limitations ran out.&rdquo; (HOUSE_OVERSIGHT_022081)</p>"
                "\n\n"
                "<p>This account, if accurate, describes Gold deploying his former AUSA relationships"
                " &mdash; specifically in a division covering securities fraud and official"
                " corruption, the precise categories of the Towers Financial conduct &mdash; to"
                " create a delay sufficient to extinguish Epstein's exposure. The claim is medium"
                " confidence, sourced from a Patterson narrative and Hoffenberg's indirect"
                " attribution; it is an unverified paraphrase, not a direct government document"
                " (Finding #2085). The reference to &ldquo;Ana Obregon money&rdquo; indicates"
                " Gold had previously performed a separate legal service for Epstein involving"
                " asset recovery from Spanish entertainer Ana Obregon, a transaction for which"
                " no primary document has yet been located. Hoffenberg served 19 years;"
                " Epstein was never charged in connection with Towers Financial.</p>"
                "\n\n"
                "<p>The connection record (Connection #1061) documents this as a legal relationship"
                " between Gold and Hoffenberg, with the causative mechanism being Gold's institutional"
                " access to SDNY. The specific framing in the source &mdash; &ldquo;kept the US"
                " attorney away&rdquo; until a narrow window &mdash; is consistent with someone"
                " managing prosecutorial attention rather than making affirmative legal arguments."
                " That form of access management is structurally distinct from standard criminal"
                " defense practice and relies on relationships that are not transferable across"
                " attorneys.</p>"
            ),
            "viz": None,
        },
        {
            "id": "epstein-relationship",
            "title": "Personal Relationship with Epstein Post-Conviction",
            "content": (
                "<p>Thirteen documents in the DOJ corpus document direct correspondence between"
                " Gold and Epstein spanning November 2011 through June 2014 &mdash; a period after"
                " Epstein's 2008 Florida conviction and registration as a sex offender. The tone"
                " and frequency of the correspondence are those of a personal friendship, not a"
                " professional relationship.</p>"
                "\n\n"
                "<p>On November 24, 2011 (Thanksgiving Day), Gold emailed"
                " jeevacation@gmail.com from his Wilson Sonsini account: <em>&ldquo;Jeff: Is it"
                " time yet? Hope so! Warm regards, Bob&rdquo;</em> (EFTA02522672). On January 5,"
                " 2012, following an in-person meeting: <em>&ldquo;Jeff: Hard to describe how much"
                " I enjoyed spending time with you today. Stay safe and well. Hope to see you when"
                " you get back. Warmest, Bob&rdquo;</em> (EFTA02548651). On February 15, 2012,"
                " Gold wrote to Epstein from a hospital recovery: <em>&ldquo;Jeff: Surgery went"
                " well: gallbladder is gone; abdominal tumor also gone; bladder tumor also gone."
                " I'm full of percocet and loopy right now but I should be alert enough to call"
                " this afternoon...&rdquo;</em> (EFTA02549608). An August 22, 2013 LinkedIn"
                " notification in the corpus confirms Epstein sent Gold a connection request, which"
                " Gold accepted (EFTA02377483). On June 24, 2014, from his Mishcon de Reya account:"
                " <em>&ldquo;Jeffrey: I just spent the day in Paris working with Alan. Think its"
                " time to get reunited at last? Warm regards, Bob Gold&rdquo;</em> (EFTA01920882)."
                " The reference to &ldquo;Alan&rdquo; has not been definitively identified from"
                " existing corpus documents.</p>"
                "\n\n"
                "<p>Separately, Epstein's 2001 Trust ONE names Gold seventh on the Fifth Amendment"
                " debt forgiveness schedule: <em>&ldquo;The indebtedness, if any, owed to the"
                " Grantor by his friend, ROBERT GOLD&rdquo;</em> (EFTA01266298, EFTA01266329)."
                " The trust language is notable: it explicitly characterizes Gold as a friend,"
                " and the debt forgiveness provision creates a documented financial entanglement"
                " that predates the post-conviction correspondence by a decade. What the indebtedness"
                " consisted of &mdash; a loan, a fee arrangement, or something else &mdash; is not"
                " specified in the trust document.</p>"
            ),
            "viz": "ego_network",
        },
        {
            "id": "institutional-legacy",
            "title": "Gold &amp; Wachtel as Institutional Origin",
            "content": (
                "<p>Gold's most durable contribution to the Epstein network is structural rather"
                " than personal. <a href=\"/dossiers/gold-and-wachtel\">Gold &amp; Wachtel</a>"
                " became Epstein's process agent for J. Epstein &amp; Company, Inc. (formerly"
                " Jeffrey E. Epstein, Inc.) from approximately 1988, its address at 10 East 53rd"
                " Street appearing on New York State corporate filings for the Epstein entity"
                " (Finding #2067). The firm is the documented origin of the two individuals who"
                " ran Epstein's operations successively for the following three decades:"
                " <a href=\"/dossiers/darren-indyke\">Darren Indyke</a> worked at Gold &amp; Wachtel"
                " from 1986 as a pre-law assistant (introduced through his father Bernard Indyke's"
                " role managing Jackie Fine Arts, a Gold &amp; Wachtel client), returned after"
                " Cornell Law in 1991, and transitioned to exclusive Epstein work by 1996; and"
                " <a href=\"/dossiers/jeffrey-schantz\">Jeffrey A. Schantz</a> (Fordham JD 1983)"
                " joined Epstein in-house in May 1995 from the successor firm Wachtel &amp; Masyr"
                " LLP (Finding #2078, Finding #2037).</p>"
                "\n\n"
                "<p>Gold himself departed the firm in the late 1990s. The firm went through two"
                " name changes after Harry Wachtel's death in February 1997: Gold &amp; Wachtel"
                " became Wachtel &amp; Masyr LLP (which represented Epstein in the 1998 SDNY"
                " eviction case at 34 East 69th Street), then Wachtel Missry LLP, which continued"
                " representing Epstein through at least 1998 and whose partner William B. Wachtel"
                " subsequently chaired Saker Aviation Services alongside former firm attorney"
                " Jesse Masyr (Finding #2069, Connection #1060). Gold's co-founding role means"
                " that the firm's entire pipeline to Epstein &mdash; including Indyke's lifelong"
                " service as his primary attorney &mdash; originated during Gold's tenure as"
                " managing partner.</p>"
            ),
            "viz": None,
        },
    ],

    "open_questions": [
        "What was the nature of the indebtedness described in Epstein's 2001 Trust ONE debt forgiveness provision for Robert Gold &mdash; was it a loan, deferred legal fees, or another financial arrangement, and was it ever collected?",
        "Who is &ldquo;Alan&rdquo; referenced in Gold's June 2014 Paris email to Epstein, and what was the nature of the work Gold performed at Mishcon de Reya that brought him to Paris in connection with Epstein's network?",
        "What are the primary documents &mdash; if any exist &mdash; describing Gold's role in the Ana Obregon asset recovery referenced in the House Oversight narrative, and in what year did that representation occur?",
        "Were there additional contacts between Gold and Epstein beyond the 13 documents identified in the DOJ corpus, and does the Mishcon de Reya correspondence produced through that firm reflect a legal or purely personal relationship?",
        "Does the Gold &amp; Wachtel client relationship with Jackie Fine Arts (the Herman Finesod tax shelter operation that recruited Darren Indyke) predate or postdate the firm's engagement by Epstein in 1988, and was Gold personally involved in the Jackie Fine Arts representation?",
    ],

    "applicable_models": [
        "revolving-door",
        "enabler-gradient",
        "regulatory-capture",
        "narrative-shield",
    ],
}


def main():
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})
    existing_curation.update(CURATION)
    dossier["curation"] = existing_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(CURATION['lead'])} chars")
    print(f"  system_role: {len(CURATION['system_role'])} chars")
    print(f"  sections: {len(CURATION['sections'])}")
    print(f"  open_questions: {len(CURATION['open_questions'])}")
    print(f"  applicable_models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()

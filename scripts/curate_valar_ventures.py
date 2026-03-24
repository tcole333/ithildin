#!/usr/bin/env python3
"""
Curate the Valar Ventures dossier.

Usage: uv run python scripts/curate_valar_ventures.py
"""

import json
from datetime import datetime

DOSSIER_PATH = "content/dossiers/valar-ventures.json"

CURATION = {
    "lead": (
        "<p><strong>Valar Ventures</strong> was Peter Thiel's international early-stage venture capital"
        " platform, founded circa 2010 and managed by Andrew McCormack and James Fitzgerald out of"
        " 915 Broadway, Suite 1101, New York NY 10010. The fund's stated strategy was to find"
        " technology companies outside Silicon Valley — its two flagship early wins were Xero"
        " (New Zealand accounting software) and TransferWise (UK money transfer). Valar ran at"
        " least four fund vehicles: Valar Global Fund II LP (USD 102M final close, January 2015),"
        " Valar Global Fund III LP (USD 104M final close, June 20, 2016, SEC CIK 1664457, GP:"
        " Valar Ventures GP III LLC, 23 investors per Form D), and Valar Global Fund IV LP"
        " (SEC CIK 1726616). <a href=\"/dossiers/peter-thiel\">Peter Thiel</a> committed USD 30M"
        " of his own capital to Fund III.</p>"
        "<p>DOJ and House Oversight documents establish that"
        " <a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> became by far the largest"
        " single limited partner in both Fund II and Fund III. As of February 14, 2019 — five"
        " months before his arrest — Epstein's estimated unaudited capital account balances were"
        " USD 40.7M in Valar Global Fund II LP and USD 49.69M in Valar Global Fund III LP, for"
        " a combined total of USD 90.39M (EFTA02629770). Those figures imply Epstein held"
        " approximately 44% of Fund II and approximately 48% of Fund III — positions that"
        " individually exceeded Thiel's own USD 30M commitment to Fund III. The capital was"
        " routed entirely through <a href=\"/dossiers/southern-trust-company-inc\">Southern"
        " Trust Company Inc.</a>, Epstein's U.S. Virgin Islands financial vehicle, via Deutsche"
        " Bank.</p>"
        "<p>The relationship began with an introduction circa November 2014"
        " (EFTA02594707), when Thiel wrote to Epstein recommending McCormack and Fitzgerald as"
        " \"two guys scouring the world for me to look for terrific early-stage VC investments.\""
        " An in-person pitch meeting took place at 9 East 71st Street on December 3, 2014."
        " <a href=\"/dossiers/nicole-junkermann\">Nicole Junkermann</a>, the German-British"
        " investor with documented offshore structures in the British Virgin Islands, flew to"
        " New York specifically to attend that pitch alongside McCormack and Fitzgerald"
        " (EFTA02595701, EFTA02403336). All communications with Epstein regarding Valar"
        " thereafter were routed through <a href=\"/dossiers/richard-kahn\">Richard Kahn</a>"
        " at HBRK Associates (575 Lexington Avenue), who actively monitored portfolio company"
        " performance and flagged political risk to the investment.</p>"
    ),

    "system_role": (
        "Valar Ventures functioned as the vehicle through which Epstein deployed"
        " more capital — USD 90.39M — than any other single investment entity in his portfolio,"
        " converting an initial pitch for USD 10–20M into a dominant LP stake that constituted"
        " nearly half of each fund's capital base, while all capital flowed through Southern"
        " Trust Company Inc., all communications were intermediated by Richard Kahn at HBRK"
        " Associates, and Nicole Junkermann's unexplained attendance at the pitch meeting"
        " introduces a second network pathway alongside the Thiel-brokered introduction."
    ),

    "sections": [
        {
            "id": "pitch-and-introduction",
            "title": "The Pitch and Introduction",
            "content": (
                "<p>The documented pathway to the Valar investment begins in November 2014, when"
                " <a href=\"/dossiers/peter-thiel\">Peter Thiel</a> wrote to"
                " <a href=\"/dossiers/jeffrey-epstein\">Epstein</a> from his address at"
                " peter@thielcapital.com, describing McCormack and Fitzgerald as his scouts for"
                " international early-stage deals and recommending Epstein meet them (EFTA02594707)."
                " The pitch materials cited Xero and TransferWise as the fund's marquee wins and"
                " proposed an investment in the range of USD 10–20M in Fund II. The meeting was"
                " scheduled for 2:00pm on December 3, 2014, at 9 East 71st Street.</p>"
                "<p>Six schedule documents confirm the meeting (EFTA02351944, EFTA02390441,"
                " EFTA02403336, EFTA02596951, EFTA02597854, EFTA02599239). The most significant"
                " detail across those documents is the attendance of"
                " <a href=\"/dossiers/nicole-junkermann\">Nicole Junkermann</a>. EFTA02595701"
                " records an email noting that Junkermann \"would like to attend the Valar Ventures"
                " meeting with you on Wed. Dec. 3rd at 2pm\" and was \"going to look into tickets"
                " to fly to NY\" — confirming she traveled specifically for this meeting rather"
                " than being incidentally present. Junkermann is separately documented in ICIJ"
                " Offshore Leaks as an officer of two offshore entities, United in Sports Parallel"
                " I GP Limited (BVI) and Copeland Securities Inc. No document in the available"
                " corpus explains why Junkermann attended a VC pitch to Epstein, or what role, if"
                " any, she played in the relationship between Epstein and Valar.</p>"
                "<p>A second independent introduction pathway exists through"
                " <a href=\"/dossiers/brad-karp\">Brad Karp</a>, chairman of Paul, Weiss, Rifkind,"
                " Wharton &amp; Garrison LLP and Epstein's primary legal point of contact across"
                " 1,038+ documented communications. EFTA02473480 records Karp referencing an"
                " \"interminable Xero board call\" while corresponding with Epstein — Xero being"
                " one of Valar's two cited success investments. Karp's concurrent position as a"
                " Xero board member and as Epstein's attorney means that a secondary pathway to"
                " the Valar introduction through Karp cannot be excluded, alongside the"
                " Thiel-brokered channel.</p>"
            ),
            "viz": "timeline",
        },
        {
            "id": "scale-of-investment",
            "title": "Scale of Investment and Fund Structure",
            "content": (
                "<p>The gap between the initial pitch and the eventual scale of investment is"
                " the central documented fact of the Valar relationship. Thiel proposed USD 10–20M"
                " (EFTA02594707); the eventual combined position reached USD 90.39M."
                " Valar Global Fund II LP closed at USD 102M in January 2015. Fund III closed at"
                " USD 104M on June 20, 2016, with Thiel committing USD 30M of that total"
                " (EFTA02460935: \"Total capital commitments for new fund are $104M, with Peter"
                " Thiel committing $30M\"). Form D for Fund III (SEC CIK 1664457) records 23"
                " investors total. Fund IV (SEC CIK 1726616) also received Epstein's participation;"
                " the 2018 Annual Report and Fund IV Initial Investments materials were forwarded"
                " to Epstein through Richard Kahn in May 2018 (EFTA02634238).</p>"
                "<p>As of February 14, 2019, estimated unaudited capital account balances were:"
                " Valar Global Fund II LP = USD 40.7M and Valar Global Fund III LP = USD 49.69M,"
                " total USD 90.39M (EFTA02629770: \"I would call them estimated 12/31/2018 capital"
                " account balances\"). The Fund III balance of USD 49.69M exceeds Thiel's own"
                " USD 30M commitment to that same fund. On a proportional basis, Epstein held"
                " approximately 44% of Fund II and approximately 48% of Fund III — positions that,"
                " in a 23-investor vehicle, would constitute effective dominance of the LP base."
                " These proportions are inferences from the closing totals and reported balances;"
                " actual ownership percentages depend on mark-to-market adjustments and capital"
                " calls not fully documented in the available corpus.</p>"
                "<p>Epstein's engagement with the fund was active, not passive. In August 2015,"
                " Fitzgerald updated him on Fund II deal flow and Epstein requested a call"
                " (EFTA02489953, EFTA02490229). In November 2015, McCormack sought a catch-up"
                " on Valar (EFTA02480444, EFTA02373015). In 2016, McCormack asked Epstein to"
                " \"sort out allocations for the first closing\" of Fund III, with Epstein described"
                " as \"thinking in a pretty broad range\" (EFTA02485187). Epstein lunched with"
                " Thiel on November 27, 2017 (EFTA02230818: \"12:00pm LUNCH w/Peter Thiel\") and"
                " a November 2017 email records \"Jeffrey is ready for your Valar call\""
                " (EFTA02229858). Epstein also queried whether there was a \"side car of valar\""
                " for a separate investment (EFTA02634108).</p>"
            ),
            "viz": "timeline",
        },
        {
            "id": "capital-flows",
            "title": "Capital Flows Through Southern Trust",
            "content": (
                "<p>All documented wire activity for the Valar investment was routed through"
                " <a href=\"/dossiers/southern-trust-company-inc\">Southern Trust Company Inc.</a>,"
                " Epstein's USVI-incorporated trust vehicle held at Deutsche Bank. Three wire"
                " transactions are confirmed in the corpus:</p>"
                "<ul>"
                "<li>EFTA01285647: Outgoing wires from Southern Trust to Valar Global Fund II LP"
                " at Silicon Valley Bank — USD 600K on 7/24 and USD 1M on 7/28 (dates and year"
                " inferred from document context).</li>"
                "<li>EFTA01299550: USD 2.5M wire from Southern Trust to Silicon Valley Bank for"
                " Valar Global Fund III LP.</li>"
                "<li>EFTA01387768: USD 52.5M wire from Southern Trust to Valar Global Fund III"
                " on April 4, 2017 via Deutsche Bank, with Vahe Stepanian processing and"
                " Stewart Oldfield copied.</li>"
                "</ul>"
                "<p>The April 4, 2017 wire of USD 52.5M is the single largest documented"
                " transaction between Southern Trust and any investment vehicle. Southern Trust"
                " held a peak balance of USD 109.98M at Deutsche Bank in December 2015"
                " (documented separately in the Southern Trust dossier). At the time of the"
                " USD 52.5M wire, Epstein's Fund III capital account ultimately registered"
                " USD 49.69M — indicating that some of the initial wire principal was not"
                " retained as capital account value, consistent with management fees, expenses,"
                " or market adjustments between April 2017 and the December 2018 reporting date."
                "</p>"
                "<p>The Dechert Exhibit B investment ledger (EFTA00027019) lists both Valar"
                " (attributed to \"Peter Thiel\") at approximately USD 28M and"
                " <a href=\"/dossiers/honeycomb-asset-management-lp\">Honeycomb Asset Management"
                " LP</a> at approximately USD 34M across five transactions. Both funds appear on"
                " the same ledger page as major allocations from Epstein's capital. David Fiszel,"
                " Honeycomb's founder and a former SAC Capital portfolio manager, was introduced"
                " to \"Peter\" (likely Thiel) by Epstein at 9 East 71st Street in February 2016"
                " (EFTA02473752), and subsequently invested in Palantir through Honeycomb."
                " The co-appearance of Valar and Honeycomb on the same ledger does not establish"
                " a connection between the two funds beyond their common LP.</p>"
            ),
            "viz": "timeline",
        },
        {
            "id": "monitoring-and-intermediation",
            "title": "Richard Kahn and HBRK Associates as Intermediary",
            "content": (
                "<p>All of Epstein's ongoing communications about Valar after the initial pitch"
                " were intermediated through <a href=\"/dossiers/richard-kahn\">Richard Kahn</a>"
                " at HBRK Associates Inc., 575 Lexington Avenue 4th Floor, New York NY 10022."
                " Kahn's role was that of a monitor and forwarding agent: he transmitted LP"
                " updates, portfolio company news, and risk alerts to Epstein, and appears to"
                " have served as the day-to-day point of contact for Valar's managing partners"
                " while Epstein dealt directly with Thiel only for high-level meetings.</p>"
                "<p>Documented monitoring activity includes: forwarding a Bloomberg article"
                " (October 24, 2016) about Thiel's politics becoming a \"deal killer in Silicon"
                " Valley\" with the question \"if article true will it impact our Valar"
                " investments\" (EFTA02447091); forwarding a Crunchbase and StashInvest link"
                " describing Stash (Valar Fund III's identified largest holding per Fitzgerald)"
                " with a note from James Fitzgerald as board member (EFTA02618729); forwarding"
                " MarketWatch coverage of Stash's debit rewards launch (EFTA02632880) with the"
                " question \"should I try to open an account?\"; and forwarding news of Valar's"
                " investment in Trading Ticket, a stock-trading startup backed by Valar Ventures"
                " and Citi Ventures (EFTA02487966). Kahn also forwarded the 2018 Annual Report"
                " and Fund IV Initial Investments materials to Epstein (EFTA02634238).</p>"
                "<p>The intermediation of all ongoing LP communications through Kahn and HBRK"
                " is consistent with the pattern observed across other major Epstein investments:"
                " Kahn served as a buffer layer between Epstein and investment managers, handling"
                " routine communications while Epstein reserved direct contact for Thiel himself."
                " Whether Kahn received compensation from Epstein, from Valar, or from both for"
                " this function is not established in the available corpus.</p>"
            ),
            "viz": None,
        },
    ],

    "open_questions": [
        (
            "Why did Nicole Junkermann fly to New York specifically to attend a venture capital"
            " pitch meeting between Epstein and Valar Ventures' managing partners? No document"
            " in the available corpus explains her role or interest in the Valar investment."
            " Her offshore structures in the BVI and her documented position in Epstein's network"
            " make this attendance worth tracing through UK and BVI corporate records."
        ),
        (
            "What was the total capital deployed into Valar across all fund tranches, including"
            " Fund IV? The USD 90.39M figure covers only Funds II and III as of December 2018."
            " Epstein queried about a \"side car\" (EFTA02634108) and received Fund IV materials"
            " (EFTA02634238), but the resulting Fund IV capital account balance is not documented"
            " in available records."
        ),
        (
            "What were the actual LP returns on Valar Funds II and III, and what happened to"
            " the USD 90.39M position after Epstein's arrest on July 6, 2019? The estate"
            " liquidation and any redemption or transfer of these LP interests is not documented"
            " in the available corpus."
        ),
        (
            "Did Brad Karp's presence on the Xero board serve as an independent introduction"
            " pathway to Valar Ventures, or was his Xero connection coincidental to the"
            " Thiel-brokered pitch? Establishing or eliminating this pathway would clarify"
            " whether the Valar relationship had multiple independent origin points."
        ),
        (
            "What was Richard Kahn's compensation structure for intermediating Valar"
            " communications? The corpus shows Kahn acting as a forwarding and monitoring agent"
            " for a USD 90M investment position, but no retainer, fee, or carried-interest"
            " arrangement between Kahn/HBRK and Epstein or Valar is documented."
        ),
        (
            "Vahe Stepanian and Stewart Oldfield are named as the Deutsche Bank personnel"
            " on the USD 52.5M wire (EFTA01387768). What were their roles at Deutsche Bank"
            " relative to Epstein's broader account relationship, and were they among the"
            " bank personnel who later faced regulatory scrutiny for the Epstein account?"
        ),
    ],

    "applicable_models": [
        "access-capitalism",
        "bridge-tax",
        "complexity-as-credential",
        "enabler-gradient",
        "offshore-opacity",
        "parallel-financial-system",
        "principal-representative",
    ],

    "key_finding_ids": [564, 599, 568, 566, 600, 583],

    "key_identifiers": {
        "jurisdictions": ["usvi", "delaware"],
        "officers": [
            "Andrew McCormack",
            "James Fitzgerald",
            "Reuben Kobulnik",
        ],
        "entities": [
            "Valar Global Fund II LP",
            "Valar Global Fund III LP",
            "Valar Ventures GP III LLC",
            "Southern Trust Company Inc.",
            "HBRK Associates Inc.",
        ],
    },

    "section_suggestions": [
        {
            "id": "pitch-and-introduction",
            "title": "The Pitch and Introduction",
            "viz": "timeline",
            "finding_ids": [564],
            "connection_ids": [],
            "guidance": "Origin of the Valar relationship and the unexplained Junkermann attendance.",
        },
        {
            "id": "scale-of-investment",
            "title": "Scale of Investment and Fund Structure",
            "viz": "timeline",
            "finding_ids": [599, 568, 583],
            "connection_ids": [],
            "guidance": "USD 90.39M total position, proportional dominance of LP base, active engagement.",
        },
        {
            "id": "capital-flows",
            "title": "Capital Flows Through Southern Trust",
            "viz": "timeline",
            "finding_ids": [566],
            "connection_ids": [852],
            "guidance": "Wire routing, USD 52.5M single transaction, Dechert ledger co-appearance with Honeycomb.",
        },
        {
            "id": "monitoring-and-intermediation",
            "title": "Richard Kahn and HBRK Associates as Intermediary",
            "viz": None,
            "finding_ids": [583],
            "connection_ids": [],
            "guidance": "Kahn's forwarding and monitoring role across portfolio company news and political risk.",
        },
    ],

    "curated_at": datetime.utcnow().isoformat(),
}


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    # Merge curation fields — preserve existing key_finding_ids etc. from section_suggestions
    dossier["curation"] = CURATION

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

#!/usr/bin/env python3
"""Write curation fields into content/dossiers/rockbridge-network.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/rockbridge-network.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# -- LEAD --------------------------------------------------------------------
curation["lead"] = (
    "<p>Rockbridge Network is a Delaware LLC (file 5834011, incorporated April 12, 2021) "
    "co-founded in 2019 by Vice President JD Vance and "
    "<a href=\"/dossiers/chris-buskirk\">Chris Buskirk</a> as a Trump-aligned alternative "
    "to the Koch donor network. The organization steers eight sub-entities: four 501(c)(4) "
    "organizations (Over the Horizon Action, Better Tomorrow, Firebrand Action, and "
    "The Faithful in Action), two super PACs (Turnout for America and the terminated "
    "Saving Arizona PAC), one donor-advised 501(c)(3) (Revitalization Partners), and "
    "the umbrella LLC itself — a structure documented through review of filings and "
    "reporting [Finding #6722] [Finding #6769]. Membership ranges from "
    "150 to 200 individuals paying $100,000 to $1 million annually, with total "
    "contributions exceeding $100 million since 2019 and an estimated 2024 budget of "
    "$75 million [Finding #6724].</p>"
    "<p>The network's primary super PAC, Turnout for America (FEC C00883520), raised "
    "$45.67 million in the 2023-2024 cycle, with top donors including Diane Hendricks "
    "($11 million), Kelcy Warren ($7.5 million), and Andrew Beal ($2 million). Over the "
    "Horizon Action served as the central 501(c)(4) financial distribution hub, receiving "
    "$20.7 million and distributing $6.9 million to Better Tomorrow and $2.05 million to "
    "Faithful in Action — grant flow analysis of 990 and FEC filings documents these "
    "distributions [Finding #6768] [Finding #6721]. Rockbridge deployed approximately "
    "5,000 field operatives across seven swing states for the 2024 election and allocated "
    "a $3 million Transition Project budget to identify and train personnel for the Trump "
    "administration [Finding #6726] [Finding #6739].</p>"
    "<p>As of March 2026, multiple Rockbridge members or speakers hold senior government "
    "positions: VP Vance (co-founder), White House Chief of Staff Susie Wiles, Treasury "
    "Secretary Scott Bessent, HHS Secretary RFK Jr., DNI Tulsi Gabbard, and Middle East "
    "envoy <a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a>. Analysis of personnel records and reporting indicates at least "
    "seven officials placed through the Transition Project now serve in the "
    "administration, according to analysis of reporting and financial disclosures "
    "[Finding #6727] [Finding #6750]. Rockbridge Korea was established "
    "in Seoul in September 2025, with planned expansion to Taiwan and Japan, transforming "
    "the network from a domestic donor organization into an international influence "
    "operation with direct channels between foreign business elites and the Vice "
    "President's office [Finding #6731] [Finding #6753].</p>"
)

# -- SYSTEM ROLE --------------------------------------------------------------
curation["system_role"] = (
    "Rockbridge Network is the central donor-coordination and personnel-placement "
    "organization connecting Silicon Valley wealth to the Trump administration. Its "
    "investigative significance derives from three functions: (1) it operates the "
    "financial infrastructure through which tech billionaires and traditional conservative "
    "donors fund Republican campaigns and voter mobilization at scale, channeling over "
    "$100 million since 2019 through a structure of 501(c)(4)s and super PACs designed "
    "to obscure individual donor identities; (2) it runs a Transition Project that placed "
    "multiple officials in senior government positions, creating a direct donor-to-appointee "
    "channel; (3) it is expanding internationally through Rockbridge Korea and planned "
    "branches in Taiwan and Japan, establishing bilateral influence channels between "
    "foreign business elites and the office of the Vice President. Buskirk's simultaneous "
    "control of Rockbridge, 1789 Capital, Firebrand Action, Faithful in Action, and the "
    "Executive Branch private club creates a single individual at the center of political "
    "fundraising, media operations, venture capital, church mobilization, and donor "
    "access to Cabinet officials."
)

# -- SECTIONS -----------------------------------------------------------------
curation["sections"] = [
    {
        "id": "organizational-structure",
        "title": "Legal and Organizational Structure",
        "viz": None,
        "content": (
            "<p>Rockbridge Network LLC was incorporated in Delaware on April 12, 2021, "
            "as file number 5834011. The umbrella LLC steers eight sub-organizations, each "
            "serving a distinct function in the network's political operations, "
            "according to review of filings and organizational records "
            "[Finding #6769]. Over the Horizon Action (EIN 88-0696885, Arlington, VA) "
            "is the primary 501(c)(4) financial distribution hub, receiving $20.7 million "
            "and re-granting to subsidiary entities: $6.9 million to Better Tomorrow, "
            "$2.05 million to Faithful in Action, and $1.25 million to DAFgiving360 — "
            "grant flow analysis of 990 filings documents these distributions "
            "[Finding #6768]. Better Tomorrow (EIN 87-2086524, Richmond, VA) handles "
            "voter turnout operations. Firebrand Action (EIN 92-0533628, Glen Allen, VA, "
            "incorporated 2022) functions as the media and investigative journalism arm, "
            "with $8 million committed to rapid response, polling, documentaries, and "
            "influencer programs [Finding #6721]. The Faithful in Action (EIN 93-1558726, "
            "Cheyenne, WY, incorporated 2023) manages church mobilization and claims "
            "160,000 members [Finding #6718].</p>"
            "<p>Turnout for America (FEC C00883520, Alexandria, VA, registered July 17, "
            "2024) is the primary super PAC, raising $45.67 million in the 2023-2024 "
            "cycle and disbursing $34.5 million, including $14 million to Patriot "
            "Grassroots LLC for field canvassing [Finding #6721]. The terminated Saving "
            "Arizona PAC (FEC C00777185, established 2021) raised $31.8 million, "
            "including $15 million from <a href=\"/dossiers/peter-thiel\">Peter Thiel</a>, "
            "to support Blake Masters's 2022 Senate campaign, according to FEC records "
            "[Finding #6767]. America 21 "
            "PAC (FEC C00804690) operates as a satellite super PAC receiving funds from "
            "both Saving Arizona and Turnout for America. Review of filings indicates "
            "Revitalization Partners functions as a 501(c)(3) donor-advised fund account, "
            "likely held at Schwab Charitable/DAFgiving360 [Finding #6769].</p>"
            "<p>All Rockbridge PACs share identical professional services infrastructure: "
            "Janna Rutland (a Crosby Ottenhoff Group employee) serves as treasurer across "
            "all entities, Crosby Ottenhoff Group LLC (Mountain Brook, AL) provides "
            "compliance consulting, Holtzman Vogel PLLC handles legal work, CMDI manages "
            "databases, and Chain Bridge Bank (McLean, VA) provides banking. PO Box 9891 "
            "in Arlington, VA is shared by Over the Horizon Action and Saving Arizona "
            "PAC, the same address used by WinRed. Review of FEC records shows Rutland "
            "serves as treasurer for 58 or more FEC-registered committees across the "
            "conservative ecosystem [Finding #6770].</p>"
        ),
    },
    {
        "id": "financial-flows",
        "title": "Financial Flows and Donor Base",
        "viz": None,
        "content": (
            "<p>The network's budget trajectory reflects rapid growth: approximately "
            "$15 million in 2021 ($3 million for the Transition Project, $8 million for "
            "media, $3.75 million for litigation), roughly $30 million in 2022, and "
            "$75 million in 2024. Total member contributions since 2019 exceed "
            "$100 million. Membership grew from 125 in 2023 to 150-200 by late 2024. "
            "After Trump's 2024 election victory, the minimum attendance price at "
            "Rockbridge events rose from $5,000 to $25,000 [Finding #6724].</p>"
            "<p>FEC filings for Turnout for America identify the largest individual "
            "donors: Diane Hendricks ($11 million, ABC Supply chairman), Kelcy Warren "
            "($7.5 million, Energy Transfer Partners), and Andrew Beal ($2 million, Beal "
            "Bank). Additional major donors to the broader Rockbridge network include "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> (described as early financier), "
            "the Winklevoss twins (who made a $1 million Bitcoin donation to Trump), and "
            "<a href=\"/dossiers/1789-capital\">1789 Capital</a> co-founder Rebekah Mercer "
            "[Finding #6721] [Finding #6728]. <a href=\"/dossiers/howard-lutnick\">Howard Lutnick</a> donated $1.98 million "
            "to Rockbridge-associated PACs before being named Secretary of Commerce, "
            "according to FEC records [Finding #6767].</p>"
            "<p>Over the Horizon Action operates as the central routing node for "
            "501(c)(4) money: its $20.7 million in receipts flowed to Better Tomorrow "
            "($6.9 million), Faithful in Action ($2.05 million), and DAFgiving360 "
            "($1.25 million). Better Tomorrow in turn re-granted to American Encore "
            "($275,000), Faithful in Action ($125,000), and Firebrand Action ($12,500). "
            "Turnout for America's $34.5 million in disbursements included $750,000 to "
            "America 21 PAC and $1.7 million to American Majority Action — financial "
            "flow analysis of 990 and FEC filings documents these distributions "
            "[Finding #6768]. The 501(c)(4) structure shields donor identities; only the "
            "super PAC disclosures provide individual donor data, and even those are "
            "routed through the WinRed-affiliated back-office infrastructure, as "
            "examination of FEC records reveals [Finding #6770].</p>"
        ),
    },
    {
        "id": "government-personnel",
        "title": "Government Personnel Placement",
        "viz": "timeline",
        "content": (
            "<p>The Rockbridge Transition Project, funded at $3 million, was designed to "
            "identify, recruit, and train personnel for a Republican administration. Its "
            "stated mission was to 'create a government-in-waiting with the people and "
            "the plans to staff the next Republican Administration' [Finding #6739]. "
            "Analysis of reporting and personnel records indicates the following "
            "Rockbridge-associated individuals now hold senior government positions: "
            "VP JD Vance (co-founder), White House Chief of Staff Susie Wiles (headlined "
            "the Fall 2024 summit and hosted a private dinner for 30 Rockbridge donors "
            "in Las Vegas before being named to the role the same month), Treasury "
            "Secretary Scott Bessent (member and speaker at April 2025 Miami event), "
            "HHS Secretary RFK Jr. (paid $100,000 by Over the Horizon Action to speak at "
            "the November 2024 summit, nominated for HHS weeks later), DNI Tulsi Gabbard "
            "(speaker at April 2025 Miami event), and Middle East envoy <a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a> "
            "(speaker at Ritz-Carlton Key Biscayne, April 2025) — analysis of "
            "reporting and financial disclosures documents these pathways "
            "[Finding #6750].</p>"
            "<p>David Sacks, White House AI and Crypto Czar, is a confirmed Rockbridge "
            "speaker and PayPal Mafia member with longstanding ties to Vance through the "
            "Stanford Review and Thiel's network [Finding #6728]. James Blair served as "
            "secretary of Firebrand Action (a Rockbridge subsidiary), resigned to join the "
            "Trump campaign, and became White House Deputy Chief of Staff, demonstrating "
            "a direct subsidiary-to-White House personnel pathway, according to "
            "review of FEC filings and reporting [Finding #6756]. "
            "At the Spring 2025 gathering at the Ritz-Carlton in Key Biscayne, four "
            "sitting Cabinet officials briefed Rockbridge donors: Bessent, RFK Jr., "
            "Gabbard, and Witkoff, according to reporting and event records "
            "[Finding #6723]. Campaign officials Chris LaCivita "
            "(co-manager), Tony Fabrizio (pollster), and Meredith O'Rourke (fundraising "
            "director) attended Rockbridge events during the 2024 cycle, according to "
            "reporting [Finding #6727].</p>"
        ),
    },
    {
        "id": "silicon-valley-nexus",
        "title": "Silicon Valley and Tech Donor Nexus",
        "viz": "ego_network",
        "content": (
            "<p>After the 2024 election, roughly 50 percent of new Rockbridge members "
            "came from the tech industry, shifting the network's center of gravity from "
            "traditional conservative donors toward Silicon Valley wealth, according to "
            "reporting [Finding #6734]. "
            "Confirmed Silicon Valley members, donors, or speakers include: "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> (described as early financier "
            "and mentor to Vance, maintains presence at high-dollar retreats), "
            "David Sacks (speaker and member, now White House AI and Crypto Czar, PayPal "
            "Mafia), <a href=\"/dossiers/palmer-luckey\">Palmer Luckey</a> (speaker, "
            "<a href=\"/dossiers/anduril-industries\">Anduril Industries</a> founder), "
            "<a href=\"/dossiers/marc-andreessen\">Marc Andreessen</a> (speaker and member, "
            "a16z co-founder), <a href=\"/dossiers/kenneth-howery\">Ken Howery</a> (member, "
            "<a href=\"/dossiers/founders-fund\">Founders Fund</a> partner, former US "
            "Ambassador to Sweden, described as working the social scene at Rockbridge "
            "events), Tyler and Cameron Winklevoss (major donors), <a href=\"/dossiers/emil-michael\">Emil Michael</a> (former "
            "Uber executive, April 2024 attendee), Erik Voorhees (crypto, April 2024 "
            "attendee), and Blake Masters (backer, Thiel protege) [Finding #6728].</p>"
            "<p><a href=\"/dossiers/elon-musk\">Elon Musk</a> is listed as a member per Economy.ac, though primary-source "
            "evidence for his direct participation is thinner than for the confirmed "
            "speakers above [Finding #6728]. The systemic pattern identified across "
            "eleven individuals in the PayPal Mafia and defense-tech network shows "
            "Rockbridge serving as the coordinating infrastructure for this group's "
            "political operations, bridging tech wealth to political power through a "
            "shared institutional node — cross-reference of LittleSis and FEC "
            "records indicates this pattern [Finding #5448].</p>"
            "<p>Policy priorities promoted at Rockbridge gatherings align with tech-sector "
            "interests: crypto deregulation, reduced AI oversight, SEC weakening, "
            "anti-ESG, and anti-DEI. Buskirk has characterized the Rockbridge vision as "
            "building a 'productive elite aristocracy rather than an extractive elite "
            "oligarchy.' The network views itself as the leading edge of a Republican "
            "Party where tech-populist donors replace traditional twentieth-century "
            "donors on both left and right, according to reporting on Rockbridge's "
            "internal positioning [Finding #6734].</p>"
        ),
    },
    {
        "id": "buskirk-operational-hub",
        "title": "Chris Buskirk as Operational Hub",
        "viz": None,
        "content": (
            "<p><a href=\"/dossiers/chris-buskirk\">Chris Buskirk</a> (born circa 1968-69, "
            "Claremont McKenna graduate, Claremont Institute Publius Fellow) is the "
            "operational center connecting Rockbridge to multiple conservative institutions, "
            "according to review of records across LittleSis, corporate filings, and FEC "
            "data [Finding #6732]. He simultaneously holds the following positions: co-founder "
            "and leader of Rockbridge Network, founder and CIO of "
            "<a href=\"/dossiers/1789-capital\">1789 Capital</a> (which crossed "
            "$1 billion AUM in September 2025), publisher of American Greatness, president "
            "of Firebrand Action and Faithful in Action, and co-owner of Executive Branch "
            "(a Georgetown private club providing donor access to Trump Cabinet members, "
            "alongside Donald Trump Jr. and Omeed Malik), according to review of records "
            "[Finding #6719] [Finding #6767].</p>"
            "<p>1789 Capital, co-founded with Omeed Malik and Rebekah Mercer in October "
            "2022, emerged directly from the Rockbridge Network and has invested $15 million "
            "in Tucker Carlson's media company, holds positions in <a href=\"/dossiers/spacex\">SpaceX</a>, <a href=\"/dossiers/xai\">xAI</a>, and "
            "Neuralink, and added Donald Trump Jr. as a partner after the 2024 election "
            "[Finding #6744]. FEC records show Buskirk's personal political spending includes "
            "$110,000 to Trump 47 Committee, $106,700 to the RNC, $10,000 to Vance Victory, "
            "and $5,800 to Blake Masters — examination of FEC filings documents "
            "these contributions [Finding #6767].</p>"
            "<p>Analysis of corporate filings reveals that Buskirk operates through a "
            "deliberate opacity structure: the only entity where he appears as a named "
            "officer is the Center for American Greatness Inc. (EIN 81-4984970), the "
            "501(c)(3) research arm. All other entities use proxy officers drawn from two "
            "distinct personal networks (the Gibson cluster and the Yoder cluster), "
            "maintaining legal distance between Buskirk's public profile and his "
            "organizational control — examination of corporate filings across multiple "
            "jurisdictions reveals this pattern [Finding #6785] [Finding #6783].</p>"
        ),
    },
    {
        "id": "election-operations",
        "title": "Election and Field Operations",
        "viz": None,
        "content": (
            "<p>Rockbridge's Red State Project allocated $6-8 million per state to convert "
            "Arizona, Michigan, and Nevada from battleground to reliably conservative "
            "states. All three flipped to Trump in 2024: Arizona by 5.5 points (the "
            "largest margin of any swing state), Nevada by 3.1 points, and Michigan by "
            "1.4 points. Rockbridge deployed approximately 5,000 field operatives across "
            "seven swing states via Better Tomorrow and Over the Horizon Action GOTV "
            "operations. Turnout for America's primary expenditure was $14 million to "
            "Patriot Grassroots LLC (Cheyenne, WY) for field canvassing — analysis of "
            "FEC disbursement records documents these expenditures [Finding #6751] "
            "[Finding #6721].</p>"
            "<p>The voter registration program registered 125,000 voters in 2023 using "
            "an ambassador model (ten new voters per organizer) and targeted doubling "
            "that figure for 2024. The voter database was built through non-political "
            "memberships in outdoor groups and churches, a method that creates a contact "
            "list outside traditional political channels. Faithful in Action's 160,000 "
            "members provide the church mobilization pathway [Finding #6726] "
            "[Finding #6718]. Attribution is inherently difficult: multiple factors "
            "drove the 2024 results, and Rockbridge's specific marginal contribution "
            "cannot be isolated from the broader Trump campaign infrastructure, as "
            "analysis of the results indicates [Finding #6751].</p>"
            "<p>Firebrand Action handles Rockbridge's media operations with $8 million "
            "committed to investigative journalism, documentaries, influencer programs, "
            "and rapid response communications. A leaked seven-page prospectus obtained "
            "by Reuters describes Rockbridge as a 'political venture capital firm' that "
            "will 'leverage investors' capital with the right political expertise to "
            "replace the current Republican ecosystem of think tanks, media organizations "
            "and activist groups.' The group is planning deployment for the 2026 midterms "
            "and 2028 presidential race [Finding #6733].</p>"
        ),
    },
    {
        "id": "international-expansion",
        "title": "International Expansion",
        "viz": None,
        "content": (
            "<p>Rockbridge Korea was established in Seoul in September 2025 as a think "
            "tank, with its first general meeting held on September 24, 2025. The board "
            "includes former Prime Minister Kim Boo-kyum, former Finance Minister Bahk "
            "Jae-wan, and Shinsegae Group chairman Chung Yong-jin, who was named head of "
            "Rockbridge Asia to oversee regional operations. Chairperson Kim Hae-young "
            "(lawyer, former Democratic Party lawmaker) leads the Seoul entity. Chung met "
            "VP Vance at a December 2025 Christmas dinner and has been spotted meeting "
            "Donald Trump Jr. in Spain [Finding #6731] [Finding #6753].</p>"
            "<p>The Asia expansion extends to two additional markets: Richard Tsai "
            "(chairman of Fubon Financial Holdings) is designated to lead a Taiwan branch, "
            "and Tadashi Maeda (Japan Bank for International Cooperation) is designated "
            "to chair a Japan branch. Park Byung-eun heads 1789 Partners, a Korea-based "
            "investment arm linked to Rockbridge and <a href=\"/dossiers/1789-capital\">1789 Capital</a>. Buskirk visited South "
            "Korea in January 2026 to pledge deeper bilateral collaboration "
            "[Finding #6753] [Finding #6739].</p>"
            "<p>This expansion transforms Rockbridge from a domestic donor network into "
            "an international influence operation. Donald Trump Jr., who holds no official "
            "government title, is described as instrumental in the global expansion, "
            "creating direct channels between foreign business elites and the US Vice "
            "President's office via Rockbridge infrastructure. Japanese political and "
            "business leaders are expected to join next [Finding #6753].</p>"
        ),
    },
    {
        "id": "key-relationships",
        "title": "Key Organizational Relationships",
        "viz": "ego_network",
        "content": (
            "<p><strong><a href=\"/dossiers/peter-thiel\">Peter Thiel</a></strong> is "
            "described as the early financier and mentor to Vance since before the 2022 "
            "Senate race. Thiel contributed $15 million to Saving Arizona PAC (backing "
            "Blake Masters) and maintains a presence at Rockbridge retreats. As founder "
            "of Palantir and co-founder of <a href=\"/dossiers/founders-fund\">Founders Fund</a>, "
            "he bridges the Rockbridge donor network to the defense-tech venture capital "
            "ecosystem [Connection #3409].</p>"
            "<p><strong><a href=\"/dossiers/heritage-foundation\">Heritage Foundation</a></strong> "
            "represents a competing conservative personnel pipeline. Rockbridge views "
            "Heritage as outdated and aims to replace its ecosystem. Both organizations "
            "seek to staff Republican administrations but through different approaches: "
            "Rockbridge via elite donor network, Heritage via policy blueprint and mass "
            "training [Connection #3432].</p>"
            "<p><strong>Teneo Network</strong> was co-founded by Vance (with Josh Hawley) "
            "and is chaired by Leonard Leo. JD Vance co-founded both Rockbridge and "
            "Teneo, and Leo spoke at the April 2024 Rockbridge retreat, serving as "
            "the primary node connecting both organizations to the Federalist Society "
            "judicial infrastructure and Leo's $1.6 billion donor-advised fund network — "
            "cross-reference of LittleSis records confirms these connections "
            "[Connection #3420] [Connection #3433] [Finding #6761].</p>"
            "<p><strong>Claremont Institute</strong> provides the ideological foundation "
            "that complements Rockbridge's financial operations. Buskirk is a Claremont "
            "Publius Fellow, and Ryan P. Williams (Claremont president) sits on the board "
            "of the Society for American Civic Renewal. This creates a three-layer "
            "structure: Rockbridge supplies concentrated donor money, Claremont supplies "
            "doctrine and intellectual cover for executive power expansion, and SACR "
            "provides ground-level fraternal organization, according to analysis of "
            "organizational records and reporting [Connection #3434] "
            "[Finding #6756].</p>"
            "<p><strong>Crosby Ottenhoff Group</strong> serves as the shared back-office "
            "compliance infrastructure across all Rockbridge PACs. Janna Rutland, a "
            "Crosby Ottenhoff employee, treasures 58 or more FEC-registered committees, "
            "making her one of the most prolific shared treasurers in the conservative "
            "PAC ecosystem, as review of FEC records shows [Connection #3451] "
            "[Finding #6770].</p>"
        ),
    },
]

# -- OPEN QUESTIONS -----------------------------------------------------------
curation["open_questions"] = [
    (
        "What is the complete donor list for Rockbridge's 501(c)(4) entities? "
        "Only the super PAC (Turnout for America) discloses donors via FEC filings. "
        "The four 501(c)(4) organizations, which collectively moved over $20 million "
        "through Over the Horizon Action alone, do not disclose individual donors. "
        "The identities of the 150-200 members paying $100,000-$1,000,000 annually "
        "are not publicly documented."
    ),
    (
        "What specific government positions were filled through the Rockbridge "
        "Transition Project, beyond the Cabinet-level appointments documented in "
        "reporting? The $3 million budget and stated goal of creating a "
        "'government-in-waiting' imply sub-Cabinet placements that have not been "
        "publicly identified."
    ),
    (
        "What is the relationship between Rockbridge Korea, 1789 Partners (the "
        "Korea-based investment arm), and 1789 Capital (the US-based fund)? Are "
        "they formally affiliated, and do they share investors or management? "
        "The South Korean entities are new and their corporate structure has not "
        "been verified through Korean registry filings."
    ),
    (
        "What are the terms and structure of the Executive Branch private club in "
        "Georgetown? Buskirk, Trump Jr., and Omeed Malik are identified as co-owners, "
        "but membership pricing, legal structure, and ethics implications of sitting "
        "Cabinet officials attending a club co-owned by the President's son and a "
        "major donor network operator have not been examined."
    ),
    (
        "How does Rockbridge coordinate with America PAC (Elon Musk's super PAC) "
        "and the broader MAGA donor infrastructure? Musk is listed as a Rockbridge "
        "member per Economy.ac but the operational relationship between the two "
        "networks — which together deployed tens of thousands of field operatives "
        "in 2024 — is not documented in primary sources."
    ),
]

# -- APPLICABLE MODELS -------------------------------------------------------
curation["applicable_models"] = [
    "parallel-financial-system",
    "private-order",
    "jurisdictional-arbitrage",
    "complexity-as-credential",
    "enabler-gradient",
]

# -- WRITE --------------------------------------------------------------------
curation["curated_at"] = datetime.now(timezone.utc).isoformat()
dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"Wrote curation to {DOSSIER_PATH}")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {curation['applicable_models']}")

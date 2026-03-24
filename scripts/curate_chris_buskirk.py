#!/usr/bin/env python3
"""Write curation fields into content/dossiers/chris-buskirk.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/chris-buskirk.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# -- SYSTEM ROLE ---------------------------------------------------------------
curation["system_role"] = (
    "Buskirk demonstrates how a single operator can build an integrated political-financial "
    "platform spanning media, donor coordination, venture capital, public-market vehicles, "
    "election litigation, voter mobilization, and executive access while remaining absent "
    "from nearly all corporate filings through systematic use of proxy officers."
)

# -- LEAD ----------------------------------------------------------------------
curation["lead"] = (
    '<p>Chris Buskirk (born ~1968-69, Claremont McKenna College graduate) is a Scottsdale-based '
    'political entrepreneur who co-founded the <a href="/dossiers/rockbridge-network">Rockbridge '
    'Network</a> with JD Vance in 2019, co-founded <a href="/dossiers/1789-capital">1789 Capital</a> '
    'with Omeed Malik and Rebekah Mercer in October 2022, and publishes the conservative media '
    'outlet American Greatness [Finding #6735]. Before entering political media, Buskirk spent '
    'two decades in financial services \u2014 insurance, reinsurance, specialty lending, and tax-credit '
    'financing \u2014 through entities including JAS Intermediaries, Nexteco Energy Capital, and Steadfast '
    'Holdings LLC [Finding #6777].</p>'

    '<p>Buskirk\'s organizational footprint is extensive. '
    '<a href="/dossiers/rockbridge-network">Rockbridge</a> operates with a ~$75M budget and '
    '150-200 members paying $100K-$1M in annual dues, steering eight organizations including two '
    'super PACs, four 501(c)(4)s, and a donor-advised 501(c)(3) [Finding #6742]. His Turnout for '
    'America super PAC raised $45.67M in the 2024 cycle from donors including Diane Hendricks '
    '($11M), Kelcy Warren ($7.5M+), and <a href="/dossiers/howard-lutnick">Howard Lutnick</a> '
    '($1.98M) [Finding #6741]. <a href="/dossiers/1789-capital">1789 Capital</a> has grown from '
    '$10M at launch (from a single investor, likely Mercer) to over $3B in total AUM across 11 '
    'registered fund entities, a $2B growth equity fund holding positions in '
    '<a href="/dossiers/spacex">SpaceX</a>, '
    '<a href="/dossiers/anduril-industries">Anduril</a>, '
    '<a href="/dossiers/xai">xAI</a>, and Neuralink, and a $1B real '
    'estate partnership [Finding #6776] [Finding #6779]. Donald Trump Jr. joined the firm as a '
    'partner in November 2024 [Finding #6779].</p>'

    '<p>A distinguishing operational pattern is Buskirk\'s near-total absence from corporate '
    'filings. American Greatness Inc. lists Ryan and Julie Gibson as officers; 1789 Foundation '
    '(which operates Citizen AG election litigation) lists the Yoder family and law partners. '
    'The only entity where Buskirk appears as a named officer is the Center for American '
    'Greatness 501(c)(3), where he is listed as President with $128,125 in compensation '
    '[Finding #6783]. Analysis of filings indicates a consistent proxy officer pattern '
    '[Finding #6785]. He also co-owns the Executive Branch, a private '
    'Georgetown club with $500K founding membership fees, alongside Trump Jr., Malik, and the '
    'Witkoff brothers [Finding #6743].</p>'
)

# -- SECTIONS ------------------------------------------------------------------
curation["sections"] = [
    {
        "id": "career-and-organizational-network",
        "title": "Career and Organizational Network",
        "viz": None,
        "content": (
            '<p>Buskirk was born on a US military base in Germany and raised in Scottsdale, '
            'Arizona. He graduated from Claremont McKenna College with a BA in Political Science '
            'and Government, followed by a Publius Fellowship at the Claremont Institute (1990 '
            'cohort, alongside Jeremy Fand, Agnes Howard, and Julie Ponzi) and an Earhart '
            'Foundation fellowship [Finding #6764]. His early career was in his father\'s '
            'insurance businesses in Scottsdale before founding JAS Intermediaries Ltd, Inc. '
            '(insurance/reinsurance intermediary), followed by Diversified Risk Management '
            'Holdings, Nexteco Energy Capital, Crucible Energy Partners (renewable energy tax '
            'credit financing), Americas Cash Express (consumer lending), and Steadfast Holdings '
            'LLC (family investment vehicle) [Finding #6777] [Finding #6765].</p>'

            '<p>Buskirk sold most of his business operations around 2015 and pivoted to political '
            'media, co-founding American Greatness in early 2016 with Seth Leibsohn [Finding #6766]. '
            'He serves as publisher and editor, while also co-hosting \'The Seth and Chris Show\' '
            'on 960 KKNT AM in Phoenix [Finding #6766]. His publishing credentials include opinion '
            'writing for the New York Times, Washington Post, USA Today, and The Hill, along with '
            'regular appearances on PBS NewsHour, NPR, Fox News, and CNN [Finding #6766]. He has '
            'authored three books through Encounter Books: \'American Greatness\' (2017, co-authored '
            'with Leibsohn), \'Trump vs The Leviathan\' (2018), and \'America and the Art of the '
            'Possible\' (2023, blurbed by JD Vance) [Finding #6766].</p>'

            '<p>The Center for American Greatness Inc. (EIN 81-4984970) is a 501(c)(3) nonprofit '
            'based at 3107 E Camelback Rd, Phoenix AZ, with 2023 gross receipts of $1.845M and '
            '2024 revenue of $1.7M (99.8% from contributions) [Finding #6783]. Buskirk serves as '
            'President and Director ($128,125 compensation in 2024) [Finding #6783]. Fellow '
            'directors include J. Eric E. Wise (Secretary/Director, King &amp; Spalding restructuring '
            'partner) and Ned Ryun, who also serves as director of Better Tomorrow, the '
            '<a href="/dossiers/rockbridge-network">Rockbridge Network</a>\'s voter mobilization '
            'arm \u2014 a board overlap linking the publishing organization to the political '
            'operation [Finding #6783] [Finding #6780].</p>'
        ),
    },
    {
        "id": "rockbridge-network-operations",
        "title": "Rockbridge Network Operations",
        "viz": "ego_network",
        "content": (
            '<p>Buskirk co-founded the <a href="/dossiers/rockbridge-network">Rockbridge '
            'Network</a> with JD Vance in 2019, growing it from informal dinners near '
            'Rockbridge, Ohio into a 150-200 member donor coordination network with an '
            'estimated $75M budget for the 2024 cycle [Finding #6742]. Donors include '
            '<a href="/dossiers/peter-thiel">Peter Thiel</a>, Rebekah Mercer, and Cameron and '
            'Tyler Winklevoss [Finding #6742]. Membership costs between $100K and $1M annually '
            '[Finding #6742]. Buskirk runs day-to-day operations while Vance, now Vice President, '
            'provides the political profile [Finding #6742].</p>'

            '<p>According to available records, Rockbridge steers eight organizations: four '
            '501(c)(4)s, two super PACs, one donor-advised 501(c)(3), and the umbrella LLC '
            '[Finding #6742]. According to reporting, Buskirk directly leads at least three '
            'subsidiaries: Turnout for America (super PAC, $45.67M raised in 2024), Firebrand '
            'Action (501(c)(4), established 2022, media/investigative journalism arm), and '
            'Faithful in Action (Wyoming-registered, 160K+ members, Christian voter mobilization) '
            '[Finding #6767]. According to FEC records, he also advised Saving Arizona PAC '
            '($31.8M raised, $15M from <a href="/dossiers/peter-thiel">Thiel</a>), which backed '
            'Blake Masters\'s 2022 Senate run [Finding #6767].</p>'

            '<p>According to multiple reporting accounts, Buskirk\'s relationship with '
            '<a href="/dossiers/peter-thiel">Thiel</a> predates Rockbridge: Thiel is described '
            'as having financed Buskirk\'s early political activism through committees that paid '
            'consulting fees to Buskirk\'s company, and as having introduced Vance to Buskirk '
            '[Finding #6771]. According to these accounts, '
            '<a href="/dossiers/marc-andreessen">Marc Andreessen</a> and '
            '<a href="/dossiers/emil-michael">Emil Michael</a> have appeared at Rockbridge '
            'events as speakers and attendees, respectively, and '
            '<a href="/dossiers/palmer-luckey">Palmer Luckey</a> has also spoken at Rockbridge '
            'gatherings [Finding #6771]. Leonard Leo spoke at the April 2024 Palm Beach retreat, '
            'connecting the Rockbridge donor network to the Federalist Society\'s judicial '
            'personnel infrastructure [Finding #6742].</p>'
        ),
    },
    {
        "id": "1789-capital-and-colombier-spacs",
        "title": "1789 Capital and the Colombier SPAC Series",
        "viz": None,
        "content": (
            '<p><a href="/dossiers/1789-capital">1789 Capital</a> was co-founded in October 2022 '
            'by Buskirk (Founder &amp; CIO), Omeed Malik (Founder &amp; President), and Rebekah '
            'Mercer [Finding #6744]. The firm emerged from discussions at a Rockbridge Mar-a-Lago '
            'meeting in 2022 [Finding #6744]. SEC filings reveal 11 distinct fund entities '
            'registered under 1789 Capital, all originally at 214 Brazilian Ave Ste 200-J, Palm '
            'Beach FL, recently moving to 375 S County Rd Ste 220 [Finding #6772].</p>'

            '<p>The original February 2023 Form D disclosed $10M raised from a single investor '
            'against a $100M target, with Malik, Mercer, and Buskirk as three Managing Members '
            'of the GP [Finding #6776]. By December 2025, Fund I LP had grown to $270.5M across '
            '71 investors, and Mercer had been removed from filings [Finding #6776]. Total AUM '
            'across all vehicles exceeds $3B as of early 2026: the Growth Equity Fund grew from '
            '$200M to $2B in 2025 alone (now closed to new investors) and holds positions in '
            '<a href="/dossiers/spacex">SpaceX</a>, '
            '<a href="/dossiers/anduril-industries">Anduril</a>, '
            '<a href="/dossiers/xai">xAI</a>, Neuralink, Groq, Cerebras, Perplexity AI, Plaid, '
            'and Ramp [Finding #6779]. A $1B real estate fund with Frisbie Group targets South '
            'Florida luxury properties [Finding #6779]. Donald Trump Jr. became a partner in '
            'November 2024 [Finding #6779].</p>'

            '<p>The Colombier SPAC franchise is a public-markets arm of the 1789 Capital '
            'ecosystem. Colombier I (2021) merged with PSQ Holdings/PublicSq [Finding #6775]. '
            'Colombier II (2023, $130M IPO) merged with GrabAGun (online firearms retailer) on '
            'July 14-15, 2025, creating GrabAGun Digital Holdings Inc (NYSE: PEW) with $179M+ '
            'gross proceeds and near-zero redemptions [Finding #6774]. The GrabAGun board includes '
            'Trump Jr. (Director, 11,433 RSUs), Blake Masters (Director), and Chris W. Cox '
            '[Finding #6774]. Buskirk served as independent Director and Audit Committee Chair; '
            'his Form 4 discloses 17,250 Class A shares directly, plus 500,000 shares and '
            '1,250,000 warrants indirectly via Anabasis VI LLC and 1789 Capital Fund I LP '
            '[Finding #6773]. Colombier III completed a $299M IPO on February 4-5, 2026, with a '
            'target still to be announced [Finding #6775]. Combined, the three SPACs have raised '
            'approximately $600M+ in public markets [Finding #6775].</p>'
        ),
    },
    {
        "id": "political-infrastructure",
        "title": "Political Infrastructure",
        "viz": None,
        "content": (
            '<p>Turnout for America (C00883520) raised $45.67M in the 2024 cycle [Finding #6741]. '
            'Top donors include Diane Hendricks ($11M), Kelcy Warren/Energy Transfer ($7.5M+), '
            'D. Andrew Beal ($2M), <a href="/dossiers/howard-lutnick">Howard Lutnick</a> ($1.98M), '
            'Jeff Sprecher ($1M), Roger Penske ($1M), and Luke Nosek of the PayPal Mafia ($500K) '
            '[Finding #6741]. The PAC spent $4.66M on Patriot Grassroots for canvassing, $750K to '
            'America 21 PAC, $645K to Primo Communications, $562K to Timoleon LLC, $501K to '
            'Telperion LLC, $400K to Forward Strategies, and smaller amounts to Grigsby Applegate, '
            'Pulse Associates, American Majority Action, Crowned Eagle Consulting, and American '
            'Encore [Finding #6741].</p>'

            '<p>America 21 PAC (C00804690), registered February 2022, is linked to Buskirk '
            'through shared operational infrastructure [Finding #6745]. He donated $30,500 '
            'personally [Finding #6748]. The PAC received $800K from Saving Arizona PAC (the '
            'Thiel-funded Blake Masters vehicle), $750K from Turnout for America, and $87.6K from '
            'Michigan Strong [Finding #6745]. Analysis of FEC records indicates it uses an '
            'identical vendor network: Telperion LLC, Timoleon LLC, Pulse Associates, Crosby '
            'Ottenhoff, Holtzman Vogel PLLC, Howard Sckolnik CPA, and Chain Bridge Bank '
            '[Finding #6746]. America 21\'s largest single disbursement was $750K to MAGA KY, an '
            'anti-Thomas Massie PAC run by Trump operatives Fabrizio and LaCivita [Finding #6745]. '
            'Paul Singer donated $1M in November 2025 [Finding #6745].</p>'

            '<p>Both PACs bank at Chain Bridge Bank (McLean, VA), founded by former Senator '
            'Peter Fitzgerald [Finding #6747]. Known as the financial backbone of Republican '
            'political operations, it has served every GOP presidential campaign since McCain '
            '2008 and the RNC [Finding #6747]. Chain Bridge makes monthly interest deposits to '
            'both PACs: $28-39K per month to TFA and $1.9-4.5K per month to America 21 '
            '[Finding #6747]. The bank completed its IPO in October 2024, raising $41M '
            '[Finding #6747].</p>'

            '<p>According to available records, Faithful in Action (Wyoming-registered, 2023) '
            'is a church mobilization organization with 160K+ members, led by Buskirk as '
            'President, and Firebrand Action (Virginia, 2022) handles journalism for the '
            'Rockbridge ecosystem [Finding #6767].</p>'
        ),
    },
    {
        "id": "proxy-officer-pattern",
        "title": "Proxy Officer Pattern",
        "viz": None,
        "content": (
            '<p>Buskirk is publicly identified as publisher, CIO, president, or founder of '
            'multiple entities, yet he is absent from nearly all corporate filings. Analysis '
            'of filings indicates this pattern operates through at least two distinct officer '
            'clusters [Finding #6785].</p>'

            '<p>According to Florida records, American Greatness Inc (EIN 45-2338676) was '
            'incorporated on May 5, 2011 \u2014 five years before the blog launched in 2016 '
            '[Finding #6782]. Review of records indicates its officers are Ryan C Gibson '
            '(President and registered agent), Julie C Gibson (Secretary/Treasurer), and Bonnie '
            'McQuiston (VP), all at 14 Alligator Cove, Santa Rosa Beach FL 32459, and that the '
            'same three individuals operate SJ Consulting LLC (formed 2006) from the same '
            'residential address [Finding #6782]. Examination of filings shows Buskirk appears '
            'on zero corporate records despite being publicly identified as publisher since launch '
            '[Finding #6782].</p>'

            '<p>1789 Foundation Inc. (EIN 88-3099118), the legal entity behind Citizen AG '
            'election litigation, was founded in May 2022 in Florida [Finding #6781]. Its '
            'officers are Eric Scharfenberger (President), Gabrielle Yoder (Secretary), and '
            'Nicole Cristine Pearson (Treasurer) [Finding #6781]. Mike Yoder founded Citizen '
            'AG; Gabrielle Yoder is his wife [Finding #6781]. The entity operates from a '
            'Northwest Registered Agent address at 7901 4th St N Ste 300, St. Petersburg FL '
            '[Finding #6781]. Buskirk does not appear on any filing [Finding #6781]. The law '
            'firm Yoder Dreher Pearson LLP connects all three officers [Finding #6781].</p>'

            '<p>The sole entity where Buskirk appears as a named officer is the Center for '
            'American Greatness Inc., the 501(c)(3) research arm [Finding #6783]. Analysis of '
            'filings indicates his consistent absence from other entities \u2014 using the Gibson '
            'household cluster for the media entity and the Yoder legal cluster for the '
            'litigation entity \u2014 represents a pattern of maintaining operational control '
            'while minimizing formal corporate footprint [Finding #6785].</p>'
        ),
    },
    {
        "id": "executive-branch-club",
        "title": "Executive Branch Private Club",
        "viz": None,
        "content": (
            '<p>Buskirk is co-owner of the Executive Branch, a private club in Georgetown, DC, '
            'alongside Donald Trump Jr., Omeed Malik, Alex Witkoff, and '
            '<a href="/dossiers/zachary-witkoff">Zachary Witkoff</a> (sons of '
            '<a href="/dossiers/steve-witkoff">Steve Witkoff</a>, Trump\'s Middle East envoy) '
            '[Finding #6743]. Founding membership costs $500K [Finding #6743]. Founding members '
            'include David Sacks, Chamath Palihapitiya, the Winklevoss twins, and Jeff Miller '
            '[Finding #6743].</p>'

            '<p>Documented attendees include Secretary of State Rubio, Attorney General '
            '<a href="/dossiers/pam-bondi">Pam Bondi</a>, DNI Gabbard, FCC Chair Carr, FTC '
            'Chair Ferguson, SEC Chair Atkins, Dan Bongino, and Mehmet Oz [Finding #6743]. '
            'The club is structured to facilitate private access between business executives '
            'and Trump administration officials \u2014 a physical venue for the same network that '
            'Rockbridge coordinates financially [Finding #6743].</p>'

            '<p>The Palm Beach address cluster further connects Buskirk and Malik: 214 Brazilian '
            'Ave Ste 200-J houses <a href="/dossiers/1789-capital">1789 Capital</a>, Colombier '
            'Sponsor II LLC, Knights Court LLC (Malik as manager), and Pecora1718 LLC (formed '
            'February 2025, purpose unknown) [Finding #6778]. The co-ownership of a DC access '
            'venue plus shared Florida office space indicates a tightly integrated business '
            'relationship spanning investment, SPACs, and political access [Finding #6778].</p>'
        ),
    },
    {
        "id": "fec-donation-history",
        "title": "FEC Donation History",
        "viz": None,
        "content": (
            '<p>FEC records show Buskirk\'s personal political contributions across multiple '
            'cycles [Finding #6748]. In the 2021-2022 cycle, with employer listed as \'CAG\' '
            '(Center for American Greatness): $30,500 to America 21 PAC, $5,800 to Ohioans for '
            'JD (Vance super PAC), $2,900 to JD Vance for Senate, $2,900 to Working for Ohio, '
            'and $5,800 to WinRed [Finding #6748].</p>'

            '<p>In the 2023-2024 cycle, with employer listed as \'self-employed\' or \'CAG\' from '
            'Paradise Valley, AZ: $110K to Trump 47 Committee, $106.7K to RNC, $5.8K to Blake '
            'Masters for Congress, $10K to Vance Victory, $5K to JD Vance for Senate, $5.6K to '
            'Never Surrender Inc, and $5.3K to WinRed [Finding #6740]. According to analysis of '
            'FEC records, his total personal giving across both cycles exceeds $290K, directed to '
            'Trump infrastructure, Vance-linked vehicles, and Masters [Finding #6767].</p>'

            '<p>Records show the early timing of Buskirk\'s Vance donations: the September 2021 '
            'donation to Ohioans for JD predates the Senate primary [Finding #6748]. His son, '
            'Christopher Buskirk Jr. (listed as student, Paradise Valley AZ), donated $500 '
            'to Brandon Gill for Texas in January 2024 [Finding #6748].</p>'
        ),
    },
    {
        "id": "1789-foundation-election-litigation",
        "title": "1789 Foundation Election Litigation",
        "viz": "timeline",
        "content": (
            '<p>1789 Foundation Inc., operating as Citizen AG, filed three coordinated voter '
            'roll challenge cases within 72 hours of each other in late October 2024 \u2014 a '
            'pre-election litigation strategy targeting swing states [Finding #6787].</p>'

            '<p>In Arizona, <em>1789 Foundation v. Fontes</em> (2:24-cv-02987) was filed '
            'October 28, 2024 [Finding #6787]. A temporary restraining order was denied on '
            'November 1, but the court ordered voter roll records released [Finding #6787]. '
            'The case was voluntarily dismissed on May 8, 2025 [Finding #6787]. The lead '
            'attorney was Alexander Kolodin (AZ state representative, District 3), who had been '
            'disciplined by the Arizona Bar in December 2023 \u2014 receiving 18 months probation '
            '\u2014 for filing frivolous cases, including serving as local counsel for Sidney '
            'Powell\'s \'Kraken\' lawsuit (<em>Bowyer v. Ducey</em>, 2:20-cv-02321) '
            '[Finding #6784]. Kolodin is now running for Arizona Secretary of State in the '
            '2026 Republican primary [Finding #6784].</p>'

            '<p>In Pennsylvania, <em>1789 Foundation v. Schmidt</em> (3:24-cv-01865) was filed '
            'October 30 [Finding #6787]. A TRO and preliminary injunction were denied October 29 '
            '[Finding #6787]. Plaintiffs failed to file an amended complaint, and the case was '
            'finally dismissed on June 10, 2025 [Finding #6787].</p>'

            '<p>In Wisconsin, <em>1789 Foundation v. ERIC</em> (3:24-cv-00755) challenged '
            'ERIC\'s use of driver records under the DPPA [Finding #6787]. WisDOT and CEIR were '
            'dismissed as parties by January 2025; the case against ERIC and David Becker '
            'remained ongoing as of November 2025 with discovery stayed pending motions to '
            'dismiss [Finding #6787].</p>'

            '<p>Nicole Cristine Pearson, who serves as 1789 Foundation\'s treasurer, '
            'simultaneously acted as litigation counsel in the Arizona case \u2014 concentrating '
            'fiduciary and legal control in the same individual [Finding #6786]. Her firm Yoder '
            'Dreher Pearson LLP, co-founded with Mike Yoder and Rachel Dreher, handled Citizen '
            'AG litigation across all three jurisdictions [Finding #6786].</p>'
        ),
    },
]

# -- OPEN QUESTIONS ------------------------------------------------------------
curation["open_questions"] = [
    (
        "Buskirk's name is absent from nearly all corporate filings across his organizational "
        "network. What is the full scope of the proxy officer architecture \u2014 are the Gibson "
        "cluster (American Greatness Inc.) and the Yoder cluster (1789 Foundation) the only "
        "two, or do additional proxy officer groups exist for Rockbridge subsidiaries, "
        "Firebrand Action, or Faithful in Action? [Finding #6785]"
    ),
    (
        "1789 Capital's original Form D listed Rebekah Mercer as one of three Managing Members "
        "of the GP. By December 2025, she had been removed from filings. What triggered "
        "Mercer's removal \u2014 was it a genuine divestiture, or a cosmetic change to reduce "
        "public visibility of her involvement? [Finding #6776]"
    ),
    (
        "Turnout for America and America 21 PAC share an identical vendor network (Telperion "
        "LLC, Timoleon LLC, Pulse Associates, Crosby Ottenhoff, Holtzman Vogel, Howard "
        "Sckolnik CPA, Chain Bridge Bank). Who are the beneficial owners of Telperion LLC "
        "and Timoleon LLC \u2014 both Delaware entities \u2014 and do any of these vendors have direct "
        "financial relationships with Buskirk beyond their PAC service contracts? "
        "[Finding #6746]"
    ),
    (
        "The Executive Branch club charges $500K founding memberships and hosts sitting "
        "Cabinet members and agency heads. Are any of the club's founding members or "
        "attendees also investors in 1789 Capital funds or Colombier SPACs, creating a "
        "potential overlap between executive-branch access and investment relationships? "
        "[Finding #6743]"
    ),
    (
        "Anabasis VI LLC is disclosed on Buskirk's Form 4 as holding 100K shares and 250K "
        "warrants in the GrabAGun/Colombier II merger. This entity does not appear in "
        "Florida Sunbiz or Delaware records under that name. What is the full corporate "
        "structure of the Anabasis entity series, and does it function as Buskirk's personal "
        "investment holding vehicle? [Finding #6773]"
    ),
]

# -- APPLICABLE MODELS ---------------------------------------------------------
curation["applicable_models"] = [
    "bridge-tax",
    "private-order",
    "narrative-shield",
    "enabler-gradient",
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

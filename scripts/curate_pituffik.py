#!/usr/bin/env python3
"""Writes curated fields into content/dossiers/pituffik-space-base.json."""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/pituffik-space-base.json")

with DOSSIER_PATH.open() as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Pituffik Space Base (latitude 76°N, northwest Greenland) is the United States' "
    "northernmost military installation and the only high-Arctic base under US control "
    "that operates without treaty restrictions on military satellite activity. The 1951 "
    "US-Denmark Defense Agreement, revised in 2004, already authorizes an expanded US "
    "military presence at the site without requiring territorial sovereignty over Greenland. "
    "The installation hosts two operationally distinct space missions: the 12th Space Warning "
    "Squadron's AN/FPS-132 Upgraded Early Warning Radar, a solid-state phased array with a "
    "3,000-plus mile detection range covering ICBM trajectories from Russia and SLBM approaches "
    "from the North Atlantic and Arctic [Finding #6147]; and the 23rd Space Operations Squadron "
    "Detachment 1, callsign POGO, one of seven Remote Tracking Stations in the Air Force "
    "Satellite Control Network, executing more than 15,000 annual satellite contacts for "
    "Department of Defense, US government, and allied satellites [Finding #6101].</p>"
    "<p>A ten-item Military Construction program underway at Pituffik includes a Network "
    "Operations Center described as a state-of-the-art data and communications facility for "
    "strategic air defense, alongside runway approach and landing system upgrades, aircraft "
    "support facilities, munitions and jet fuel storage, billeting, Taxiway D reconstruction, "
    "a fuel cell maintenance hangar, and a personnel recovery hangar [Finding #6099]. In June "
    "2025 the Pentagon transferred command authority over Pituffik from US European Command "
    "to US Northern Command, whose statutory mission encompasses homeland defense and missile "
    "defense — a realignment that occurred within months of the January 2025 executive order "
    "launching the Golden Dome missile defense program [Finding #6107]. A separate $32 million "
    "NDAA authorization for Pituffik runway and landing systems was cited as directly linked to "
    "Golden Dome data throughput requirements [Finding #6115].</p>"
    "<p>The base's strategic value for satellite ground-station operations is defined in part "
    "by what its Arctic neighbors cannot do. Svalbard Satellite Station (SvalSat, 78°N), "
    "operated by KSAT/Kongsberg, is the highest-latitude commercial ground station but is "
    "explicitly prohibited from serving military satellites under Norwegian concessions to the "
    "1920 Svalbard Treaty [Finding #6104]. The European Space Agency and Lithuanian firm "
    "Astrolight are constructing the northernmost optical laser ground station at Kangerlussuaq, "
    "Greenland — approximately 600 kilometers south of Pituffik — specifically because Greenland's "
    "polar desert atmosphere provides superior conditions for high-throughput laser satellite "
    "communications at ten times the data rate and seventy percent lower cost than RF links "
    "[Finding #6105]. Expert assessment of Pituffik's role in a future missile defense "
    "architecture is divided: the Australian Strategic Policy Institute characterizes the "
    "base as the 'operational fulcrum' for Golden Dome ground infrastructure, while the "
    "Bulletin of Atomic Scientists argues the location provides no added benefit for a "
    "space-based interceptor architecture designed around low Earth orbit global coverage "
    "[Finding #6147] [Finding #6108].</p>"
)

# ── system_role ───────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Pituffik Space Base functions as the United States' sole high-Arctic military "
    "installation operating without treaty-imposed constraints on military satellite use, "
    "giving it a structural position in polar orbit satellite tracking and early warning "
    "radar coverage that no other ground station in the region can replicate. Its ongoing "
    "Military Construction program and EUCOM-to-NORTHCOM command transfer have made it "
    "the central physical node in the contested question of whether Greenland has material "
    "operational value for the Golden Dome missile defense program — a question on which "
    "institutional experts are split, and whose answer has significant procurement and "
    "diplomatic consequences for parties with financial exposure to that program."
)

# ── sections ──────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "radar-and-missile-warning",
        "title": "Radar Infrastructure and Missile Warning Mission",
        "viz": None,
        "content": (
            "<p>The AN/FPS-132 Upgraded Early Warning Radar operated by the 12th Space Warning "
            "Squadron is a two-sided solid-state phased array with 3,589 antenna elements per "
            "face, 870 kilowatts of transmit power, and a detection range exceeding 3,000 miles. "
            "Upgraded by Raytheon in 2009 with additional enhancements in 2016 and 2017 totaling "
            "$40 million, the radar is oriented to detect intercontinental ballistic missile "
            "trajectories from Russia and submarine-launched ballistic missile approaches from "
            "the North Atlantic and Arctic [Finding #6147]. The 12th SWS mission also encompasses "
            "space surveillance — tracking objects in orbit — which creates operational overlap "
            "with the satellite control mission housed separately under 23rd SOPS Det 1.</p>"
            "<p>Pituffik's radar coverage arc has been cited as 5,550 kilometers, covering the "
            "principal threat corridors relevant to the <a href=\"/dossiers/golden-dome\">Golden Dome</a> "
            "homeland defense program [Finding #5663]. The "
            "<a href=\"/dossiers/golden-dome\">Golden Dome</a> ground segment architecture, as "
            "described in public DoD planning documents, designates the AN/FPS-132 at Pituffik "
            "and the Long Range Discrimination Radar at Clear Space Force Station, Alaska as the "
            "two primary ground-based radar nodes — meaning Pituffik occupies a defined slot in "
            "the baseline architecture regardless of how the space-layer debate resolves "
            "[Finding #6139].</p>"
        ),
    },
    {
        "id": "satellite-control-network",
        "title": "Satellite Control Network and Polar Orbit Coverage",
        "viz": None,
        "content": (
            "<p>The 23rd Space Operations Squadron Detachment 1 (POGO) is one of seven Remote "
            "Tracking Stations in the Air Force Satellite Control Network, executing telemetry, "
            "tracking, and commanding for Department of Defense, US government, and allied "
            "satellites. The station logs more than 15,000 satellite contacts annually and "
            "operates as a mission-dedicated facility distinct from the missile warning radar "
            "mission at the same base [Finding #6101]. High-latitude ground stations provide "
            "extended contact windows for satellites in polar and highly elliptical orbits, "
            "making Pituffik's position at 76°N geometrically valuable for polar-orbit "
            "constellation management.</p>"
            "<p>The Space Development Agency's ground segment for its Proliferated Warfighter "
            "Space Architecture uses a Norwegian station at Andoya (69°N) for polar orbit "
            "coverage, with operations centers at Redstone Arsenal, Alabama, and Grand Forks, "
            "North Dakota. As of the SDA Director's public statements, Greenland and Pituffik "
            "are not mentioned in SDA ground segment planning [Finding #6103]. This creates "
            "a direct evidential tension: the existing AFSCN tracking infrastructure at "
            "Pituffik is an established asset, but the agency currently building the Golden "
            "Dome satellite constellation has not designated it as a ground node. Whether "
            "that reflects a firm architectural decision or a planning gap yet to be resolved "
            "is not established in the public record.</p>"
        ),
    },
    {
        "id": "arctic-ground-station-landscape",
        "title": "Arctic Ground Station Landscape and Treaty Constraints",
        "viz": None,
        "content": (
            "<p>The competitive geography of Arctic ground stations shapes Pituffik's value "
            "proposition. SvalSat at 78°N is the highest-latitude commercial ground station "
            "in the world, operated by KSAT/Kongsberg, and provides polar coverage for "
            "commercial and civil satellites. However, Norwegian concessions to the 1920 "
            "Svalbard Treaty explicitly prohibit military satellite operations and warlike "
            "purposes, removing SvalSat from consideration for any US military mission "
            "[Finding #6104]. Alternatives at Andoya (69°N) and Tromso (69°N) in Norway "
            "and at multiple Alaskan stations each carry different coverage geometry and "
            "latency trade-offs but are not subject to the Svalbard Treaty's military "
            "exclusion [Finding #6149].</p>"
            "<p>ESA's ScyLight/IRIS2 program, through Astrolight, is building the "
            "northernmost optical laser satellite ground station at Kangerlussuaq, Greenland "
            "(approximately 600 kilometers south of Pituffik), targeting completion in late "
            "2026. The rationale for siting this station in Greenland's polar desert is "
            "atmospheric: low humidity and minimal cloud cover support sustained optical "
            "links at ten times the data throughput of RF at seventy percent lower operating "
            "cost. The same atmospheric advantages apply at Pituffik, 600 kilometers further "
            "north [Finding #6105]. If the <a href=\"/dossiers/golden-dome\">Golden Dome</a> "
            "architecture incorporates optical or laser inter-satellite and downlink "
            "communications — as commercial LEO programs are actively pursuing — Pituffik's "
            "atmospheric profile becomes a relevant operational factor rather than a "
            "geographic abstraction.</p>"
        ),
    },
    {
        "id": "milcon-and-command-realignment",
        "title": "Military Construction Program and Command Realignment",
        "viz": None,
        "content": (
            "<p>Ten active Military Construction projects at Pituffik span a broad range of "
            "infrastructure categories: runway approach and landing system, aircraft support "
            "facilities, munitions storage, jet fuel storage, billeting, Taxiway D "
            "reconstruction, fuel cell maintenance hangar, personnel recovery hangar, and "
            "a Network Operations Center characterized as a state-of-the-art data and "
            "communications facility for strategic air defense [Finding #6099]. Separately, "
            "Serco was awarded a $323 million contract by the Army Corps of Engineers in "
            "August 2024 for power plant renovation at Pituffik [Finding #5667]. A $32 million "
            "NDAA authorization specifically for runway and landing systems has been publicly "
            "linked to data throughput requirements for the Golden Dome program [Finding #6115]."
            "</p>"
            "<p>The June 2025 transfer of Pituffik from US European Command to US Northern "
            "Command moved the base from a European theater asset to one under the command "
            "responsible for homeland defense and missile defense of the North American "
            "continent. USNORTHCOM is the US component of NORAD. This realignment "
            "occurred approximately five months after the January 2025 Golden Dome executive "
            "order and corresponds to what Air and Space Forces Magazine described as renewed "
            "Arctic geopolitical interest [Finding #6107]. The transfer is a command "
            "administrative action, not a construction event, but it establishes the "
            "institutional chain under which future Pituffik mission assignments — and "
            "budget requests — would flow.</p>"
            "<p><a href=\"/dossiers/kenneth-howery\">Kenneth Howery</a>, confirmed as US "
            "Ambassador to Denmark (which exercises sovereignty over Greenland) in October "
            "2025, named Arctic security with focus on Greenland and Pituffik Space Base as "
            "his third stated priority at his Senate confirmation hearing [Finding #5676]. "
            "Howery co-founded <a href=\"/dossiers/founders-fund\">Founders Fund</a>, which "
            "invested $1 billion in <a href=\"/dossiers/anduril-industries\">Anduril</a> in "
            "June 2025 — the largest single check in Founders Fund history. Anduril holds a "
            "space-based interceptor prototype contract and is a SHIELD IDIQ awardee for "
            "the Golden Dome program [Finding #6112]. Howery's ethics agreement does not "
            "require recusal from Anduril-affecting matters, including decisions regarding "
            "Pituffik infrastructure that bears on Anduril's Golden Dome bid [Finding #6112]."
            "</p>"
        ),
    },
    {
        "id": "expert-dispute",
        "title": "Expert Dispute on Operational Necessity",
        "viz": None,
        "content": (
            "<p>Whether Pituffik — and by extension Greenland — is operationally necessary "
            "for the Golden Dome program is contested among analysts, and the Pentagon's own "
            "published infrastructure plans do not list Greenland as a designated node "
            "[Finding #6151]. The Bulletin of Atomic Scientists, in a February 2026 analysis "
            "by Diaz-Maurin, argues that Greenland provides no added benefit for a "
            "space-based interceptor architecture built around LEO constellation global "
            "coverage — because a sufficiently large LEO constellation achieves polar "
            "coverage through orbital geometry without requiring a specific high-latitude "
            "ground station [Finding #6108]. This argument addresses the interceptor "
            "satellite layer specifically.</p>"
            "<p>It does not address three distinct functions where Pituffik's existing "
            "infrastructure has established operational relevance: ground-station telemetry "
            "and commanding for the satellite control network (23rd SOPS Det 1), missile "
            "warning radar coverage (12th SWS AN/FPS-132), and the atmospheric advantages "
            "for high-throughput optical satellite communications that ESA has independently "
            "validated at Kangerlussuaq [Finding #6108]. The Australian Strategic Policy "
            "Institute's characterization of Pituffik as the 'operational fulcrum' for "
            "Golden Dome ground infrastructure reflects a broader assessment that includes "
            "these functions [Finding #6147]. The gap between these two positions — "
            "interceptor satellite geometry versus ground station operations — defines "
            "the actual scope of the disagreement, which the public record does not "
            "resolve.</p>"
        ),
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Has the Space Development Agency formally evaluated Pituffik as a candidate "
        "Remote Tracking Station for the Proliferated Warfighter Space Architecture ground "
        "segment, and if not, what is the basis for the decision to rely on Andoya (69°N) "
        "rather than the existing AFSCN station at 76°N?"
    ),
    (
        "What is the specific data throughput requirement that the $32 million NDAA "
        "runway and landing system authorization is designed to support, and which "
        "Golden Dome program element generates that requirement?"
    ),
    (
        "The June 2025 EUCOM-to-NORTHCOM command transfer of Pituffik has not been "
        "accompanied by a publicly disclosed review of existing missions. Has the 23rd "
        "SOPS Det 1 AFSCN mission been reassigned, retained under Space Operations "
        "Command, or placed under a dual-hat arrangement with NORTHCOM?"
    ),
    (
        "Kenneth Howery's ethics agreement does not list Anduril as a covered entity "
        "requiring recusal. Has the Office of Government Ethics or the State Department's "
        "ethics office conducted any formal review of whether Pituffik-related diplomatic "
        "activities by the Ambassador to Denmark constitute participation in matters "
        "affecting Anduril's Golden Dome contracting position?"
    ),
    (
        "ESA's Astrolight optical ground station at Kangerlussuaq is scheduled for "
        "completion in late 2026. Has the US Space Force or any DoD component evaluated "
        "whether to establish a military optical ground terminal at Pituffik to serve "
        "Golden Dome or other classified satellite programs, and has any contract or "
        "planning document for such a facility been issued?"
    ),
    (
        "The 1951 US-Denmark Defense Agreement (revised 2004) authorizes expanded US "
        "military presence at Pituffik without territorial sovereignty. What specific "
        "installations or capabilities are currently authorized under that agreement "
        "that have not yet been constructed, and has Denmark been consulted on any "
        "Golden Dome-related expansion plans beyond the existing MILCON program?"
    ),
]

# ── applicable_models ─────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "manufactured-dependency",
    "bridge-tax",
    "complexity-as-credential",
]

# ── write back ────────────────────────────────────────────────────────────────
with DOSSIER_PATH.open("w") as f:
    json.dump(dossier, f, indent=2)
    f.write("\n")

print("Wrote curation fields to", DOSSIER_PATH)

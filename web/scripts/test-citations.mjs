import assert from "node:assert/strict";
import { resolve } from "node:path";
import { createJiti } from "jiti";

const jiti = createJiti(import.meta.url);
const citationsPath = resolve("./src/lib/citations.ts");
const {
  applyCitations,
  createCitationState,
  extractEvidenceLinks,
  splitCitationGroup,
  getCitationHealthTier,
} = jiti(citationsPath);

let passed = 0;
let failed = 0;

function run(name, fn) {
  try {
    fn();
    process.stdout.write(`PASS ${name}\n`);
    passed++;
  } catch (error) {
    process.stderr.write(`FAIL ${name}\n`);
    process.stderr.write(`  ${error.message}\n`);
    failed++;
  }
}

// ---------------------------------------------------------------------------
// EFTA
// ---------------------------------------------------------------------------

run("EFTA: resolves token to jmail.world URL", () => {
  const result = applyCitations("See [EFTA02504960] for details.");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "EFTA02504960");
  assert.equal(result.entries[0].url, "https://jmail.world/thread/EFTA02504960?view=inbox");
  assert.ok(result.entries[0].key.startsWith("efta:"));
});

run("EFTA: extractEvidenceLinks resolves EFTA ID", () => {
  const links = extractEvidenceLinks("EFTA02504960");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /jmail\.world/);
});

run("EFTA: handles range notation (EFTA-EFTA)", () => {
  const result = applyCitations("Pages [EFTA02504960-EFTA02504965].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /EFTA02504960/);
});

// ---------------------------------------------------------------------------
// HOUSE_OVERSIGHT
// ---------------------------------------------------------------------------

run("HOUSE_OVERSIGHT: resolves to jmail.world URL", () => {
  const result = applyCitations("See [HOUSE_OVERSIGHT_12345].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /jmail\.world\/thread\/HOUSE_OVERSIGHT_12345/);
});

// ---------------------------------------------------------------------------
// SEC / EDGAR
// ---------------------------------------------------------------------------

run("SEC: resolves accession number to EDGAR URL", () => {
  const result = applyCitations("Filed [SEC:0001193125-21-123456].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "SEC 0001193125-21-123456");
  assert.match(result.entries[0].url ?? "", /sec\.gov\/Archives\/edgar/);
});

run("EDGAR: resolves same as SEC variant", () => {
  const result = applyCitations("See [EDGAR:0001193125-21-123456].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /sec\.gov\/Archives\/edgar/);
});

run("SEC: extractEvidenceLinks resolves accession", () => {
  const links = extractEvidenceLinks("SEC:0001193125-21-123456");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /sec\.gov/);
});

// ---------------------------------------------------------------------------
// IRS 990
// ---------------------------------------------------------------------------

run("990: resolves EIN to ProPublica URL", () => {
  const result = applyCitations("Per [990:660789697] filing.");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "990 EIN 660789697");
  assert.equal(result.entries[0].url, "https://projects.propublica.org/nonprofits/organizations/660789697");
});

run("990: extractEvidenceLinks resolves EIN", () => {
  const links = extractEvidenceLinks("990:660789697");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /propublica\.org/);
});

// ---------------------------------------------------------------------------
// ACRIS
// ---------------------------------------------------------------------------

run("ACRIS: resolves document ID to NYC ACRIS URL", () => {
  const result = applyCitations("Recorded [ACRIS:2017021700466001].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "ACRIS 2017021700466001");
  assert.match(result.entries[0].url ?? "", /a836-acris\.nyc\.gov/);
});

run("ACRIS: extractEvidenceLinks resolves doc ID", () => {
  const links = extractEvidenceLinks("ACRIS:2017021700466001");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /doc_id=2017021700466001/);
});

// ---------------------------------------------------------------------------
// CourtListener
// ---------------------------------------------------------------------------

run("CL: resolves docket ID to CourtListener URL", () => {
  const result = applyCitations("Docket [CL:69737684].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "CourtListener 69737684");
  assert.equal(result.entries[0].url, "https://www.courtlistener.com/docket/69737684/united-states-of-america-ex-rel-v-international-peace-institute-inc/");
});

run("CL: extractEvidenceLinks resolves docket", () => {
  const links = extractEvidenceLinks("CL:69737684");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /courtlistener\.com\/docket\/69737684/);
});

// ---------------------------------------------------------------------------
// FEC (multiple variants)
// ---------------------------------------------------------------------------

run("FEC: committee ID resolves to FEC committee URL", () => {
  const result = applyCitations("See [FEC:C00352732].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /fec\.gov\/data\/committee\/C00352732/);
});

run("FEC: name query resolves to FEC search URL", () => {
  // Comma in name splits the group — use extractEvidenceLinks directly
  const links = extractEvidenceLinks("FEC:KELLERHALS");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /fec\.gov\/data\/search\/\?q=/);
  assert.match(links[0].url ?? "", /KELLERHALS/);
});

run("FEC: committee-year resolves to receipts URL", () => {
  const result = applyCitations("See [FEC:C00352732-2000].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /receipts\/\?committee_id=C00352732&two_year_transaction_period=2000/);
});

run("FEC: committee/schedule_a resolves to receipts URL", () => {
  const result = applyCitations("See [FEC:C00393702/schedule_a].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /receipts\/\?committee_id=C00393702/);
});

run("FEC: normalizes odd-year to two-year cycle", () => {
  const oddYear = extractEvidenceLinks("FEC:C00384123-2003");
  assert.equal(oddYear.length, 1);
  assert.match(oddYear[0].url ?? "", /two_year_transaction_period=2004/);
});

run("FEC: does not emit orphaned suffix fragments", () => {
  const yearSuffix = extractEvidenceLinks("FEC:C00352732-2000");
  assert.equal(yearSuffix.length, 1);
  assert.equal(yearSuffix[0].label, "FEC:C00352732-2000");

  const scheduleA = extractEvidenceLinks("FEC:C00393702/schedule_a");
  assert.equal(scheduleA.length, 1);
  assert.equal(scheduleA[0].label, "FEC:C00393702/schedule_a");
});

// ---------------------------------------------------------------------------
// FARA
// ---------------------------------------------------------------------------

run("FARA: resolves registration number to efile URL", () => {
  const result = applyCitations("See [FARA:6458].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "FARA #6458");
  assert.match(result.entries[0].url ?? "", /efile\.fara\.gov/);
});

run("FARA: extractEvidenceLinks resolves FARA number", () => {
  const links = extractEvidenceLinks("FARA:6458");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /fara\.gov/);
});

// ---------------------------------------------------------------------------
// USVI
// ---------------------------------------------------------------------------

run("USVI: resolves entity ID to USVI URL", () => {
  const result = applyCitations("See [USVI:582530].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /ltg\.gov\.vi/);
});

// ---------------------------------------------------------------------------
// REG (Registry)
// ---------------------------------------------------------------------------

run("REG: resolves jurisdiction:id to registry URL", () => {
  const result = applyCitations("See [REG:VI:582530].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "VI 582530");
  assert.ok(result.entries[0].url);
});

run("REG: FL jurisdiction links to SunBiz", () => {
  const result = applyCitations("See [REG:FL:F08000003048].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /sunbiz\.org/);
});

run("REG: UK jurisdiction links to Companies House", () => {
  const result = applyCitations("See [REG:UK:12345678].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /company-information\.service\.gov\.uk/);
});

run("REG: extractEvidenceLinks resolves registry ref", () => {
  const links = extractEvidenceLinks("REG:FL:F08000003048");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /sunbiz\.org/);
});

// ---------------------------------------------------------------------------
// FL-SunBiz, NM-SoS, NY-SoS (shorthand registry refs)
// ---------------------------------------------------------------------------

run("FL-SunBiz: shorthand resolves to SunBiz URL", () => {
  const fl = extractEvidenceLinks("FL-SunBiz:F08000003048");
  assert.equal(fl.length, 1);
  assert.equal(fl[0].label, "FL-SunBiz:F08000003048");
  assert.match(fl[0].url ?? "", /search\.sunbiz\.org/);
});

run("NM-SoS: shorthand resolves to NM portal URL", () => {
  const nm = extractEvidenceLinks("NM-SoS:1615137");
  assert.equal(nm.length, 1);
  assert.match(nm[0].url ?? "", /nm\.us/);
});

run("NY-SoS: shorthand resolves to NY DOS URL", () => {
  const ny = extractEvidenceLinks("NY-SoS:2773652");
  assert.equal(ny.length, 1);
  assert.match(ny[0].url ?? "", /dos\.ny\.gov/);
});

// ---------------------------------------------------------------------------
// DS10
// ---------------------------------------------------------------------------

run("DS10: plain token links to financials page", () => {
  const result = applyCitations("See [DS10] for data.");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "DS10");
  assert.equal(result.entries[0].url, "/financials");
});

run("DS10: qualified token links to financials page", () => {
  const result = applyCitations("See [DS10:query_thiel].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "DS10:query_thiel");
  assert.equal(result.entries[0].url, "/financials");
});

run("DS10: extractEvidenceLinks resolves DS10 ref", () => {
  const links = extractEvidenceLinks("DS10:GRATITUDE");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "/financials");
});

// ---------------------------------------------------------------------------
// KPMG (label-only, no URL)
// ---------------------------------------------------------------------------

run("KPMG: resolves to label-only citation (no URL)", () => {
  const result = applyCitations("Per [KPMG:IPI] review.");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /KPMG.*IPI/);
  assert.equal(result.entries[0].url, undefined);
});

run("KPMG: extractEvidenceLinks returns label without URL", () => {
  const links = extractEvidenceLinks("KPMG:IPI");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, undefined);
});

// ---------------------------------------------------------------------------
// LDA (Lobbying Disclosure Act)
// ---------------------------------------------------------------------------

run("LDA: resolves to Senate LDA search URL", () => {
  const result = applyCitations("Filed [LDA:Broidy Capital].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /LDA.*Broidy Capital/);
  assert.match(result.entries[0].url ?? "", /lda\.senate\.gov/);
  assert.match(result.entries[0].url ?? "", /registrant=Broidy/);
});

run("LDA: extractEvidenceLinks resolves LDA registrant", () => {
  const links = extractEvidenceLinks("LDA:Broidy Capital");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /lda\.senate\.gov/);
});

// ---------------------------------------------------------------------------
// OpenSanctions
// ---------------------------------------------------------------------------

run("OpenSanctions: resolves entity ID to opensanctions.org URL", () => {
  const result = applyCitations("See [OpenSanctions:Q125731].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /OpenSanctions.*Q125731/);
  assert.equal(result.entries[0].url, "https://www.opensanctions.org/entities/Q125731/");
});

run("OpenSanctions: extractEvidenceLinks resolves entity", () => {
  const links = extractEvidenceLinks("OpenSanctions:Q125731");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://www.opensanctions.org/entities/Q125731/");
});

// ---------------------------------------------------------------------------
// DocumentCloud
// ---------------------------------------------------------------------------

run("DocumentCloud: resolves document ID to DocumentCloud URL", () => {
  const result = applyCitations("See [DOCUMENTCLOUD:24402693].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "DocumentCloud 24402693");
  assert.equal(result.entries[0].url, "https://www.documentcloud.org/documents/24402693");
});

run("DocumentCloud: extractEvidenceLinks resolves doc ID", () => {
  const links = extractEvidenceLinks("DOCUMENTCLOUD:24402693");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /documentcloud\.org\/documents\/24402693/);
});

// ---------------------------------------------------------------------------
// OffshoreAlert
// ---------------------------------------------------------------------------

run("OffshoreAlert: resolves slug to OffshoreAlert URL", () => {
  const result = applyCitations("See [OffshoreAlert:DB-Consent-Order-NYDFS].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "OffshoreAlert:DB-Consent-Order-NYDFS");
  assert.match(result.entries[0].url ?? "", /offshorealert\.com\/DB-Consent-Order-NYDFS/);
});

run("OffshoreAlert: extractEvidenceLinks resolves slug", () => {
  const links = extractEvidenceLinks("OffshoreAlert:Katlyn-Doe-v-Epstein");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /offshorealert\.com\/Katlyn-Doe-v-Epstein/);
});

// ---------------------------------------------------------------------------
// MuckRock
// ---------------------------------------------------------------------------

run("MuckRock: resolves request ID to MuckRock URL", () => {
  const result = applyCitations("See [MUCKROCK:78799].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "MuckRock 78799");
  assert.equal(result.entries[0].url, "https://www.muckrock.com/foi/78799/");
});

run("MuckRock: resolves request ID with filename", () => {
  const result = applyCitations("See [MUCKROCK:78799/Docs.redacted.pdf].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "MuckRock 78799/Docs.redacted.pdf");
  assert.equal(result.entries[0].url, "https://www.muckrock.com/foi/78799/");
});

run("MuckRock: extractEvidenceLinks resolves request", () => {
  const links = extractEvidenceLinks("MUCKROCK:80009/2019-083151_RC.pdf");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /muckrock\.com\/foi\/80009/);
});

// ---------------------------------------------------------------------------
// LittleSis
// ---------------------------------------------------------------------------

run("LittleSis: resolves colon-separated ID to LittleSis URL", () => {
  const result = applyCitations("See [LittleSis:101661].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "LittleSis 101661");
  assert.equal(result.entries[0].url, "https://littlesis.org/entities/101661");
});

run("LittleSis: resolves underscore variant", () => {
  const result = applyCitations("See [LITTLESIS_429018].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "LittleSis 429018");
  assert.match(result.entries[0].url ?? "", /littlesis\.org\/entities\/429018/);
});

run("LittleSis: extractEvidenceLinks resolves entity ID", () => {
  const links = extractEvidenceLinks("LittleSis:101661");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /littlesis\.org\/entities\/101661/);
});

// ---------------------------------------------------------------------------
// ICIJ
// ---------------------------------------------------------------------------

run("ICIJ: resolves plain format to offshore leaks URL", () => {
  const result = applyCitations("See [ICIJ:82004676].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "ICIJ 82004676");
  assert.equal(result.entries[0].url, "https://offshoreleaks.icij.org/nodes/82004676");
});

run("ICIJ: resolves PP variant", () => {
  const result = applyCitations("See [ICIJ-PP:55063719].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /offshoreleaks\.icij\.org\/nodes\/55063719/);
});

run("ICIJ: resolves node variant", () => {
  const result = applyCitations("See [ICIJ-node:56105421].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /offshoreleaks\.icij\.org\/nodes\/56105421/);
});

run("ICIJ: extractEvidenceLinks resolves ICIJ ref", () => {
  const links = extractEvidenceLinks("ICIJ:82004676");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /offshoreleaks\.icij\.org\/nodes\/82004676/);
});

// ---------------------------------------------------------------------------
// USAspending
// ---------------------------------------------------------------------------

run("USAspending: resolves award ID to award URL", () => {
  const result = applyCitations("See [USASPENDING:CONT_AWD_W91WAW11F0017].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "USAspending Award CONT_AWD_W91WAW11F0017");
  assert.ok(result.entries[0].url.includes("/award/CONT_AWD_W91WAW11F0017/"));
});

run("USAspending: resolves recipient UEI to recipient URL", () => {
  const result = applyCitations("See [USASPENDING:RECIPIENT:RN99S3S7N977].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "USAspending Recipient RN99S3S7N977");
  assert.ok(result.entries[0].url.includes("/recipient/RN99S3S7N977/latest"));
});

run("USAspending: extractEvidenceLinks resolves award and recipient", () => {
  const links = extractEvidenceLinks("Award USASPENDING:ABC-123 and recipient USASPENDING:RECIPIENT:XYZ-789");
  // We check for the presence of the two canonical URLs we expect
  const urls = links.map(l => l.url);
  assert.ok(urls.some(u => u?.includes("/award/ABC-123/")), "should find award URL");
  assert.ok(urls.some(u => u?.includes("/recipient/XYZ-789/latest")), "should find recipient URL");
});

// ---------------------------------------------------------------------------
// Medicare
// ---------------------------------------------------------------------------

run("Medicare: resolves NPI to search URL", () => {
  const result = applyCitations("See [MEDICARE:1003000126].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Medicare Provider 1003000126");
  assert.ok(result.entries[0].url.includes("search_query=1003000126"));
});

run("Medicare: extractEvidenceLinks resolves NPI", () => {
  const links = extractEvidenceLinks("Provider MEDICARE:1003000126");
  const urls = links.map(l => l.url);
  assert.ok(urls.some(u => u?.includes("search_query=1003000126")), "should find provider search URL");
});

// ---------------------------------------------------------------------------
// Finding references
// ---------------------------------------------------------------------------

run("Finding: resolves with evidence map to primary source URL", () => {
  const findingEvidenceMap = { "2108": ["EFTA01296686"] };
  const result = applyCitations("See [Finding #2108].", { findingEvidenceMap });
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Finding #2108");
  assert.ok(result.entries[0].url, "expected a URL for the finding");
  assert.ok(result.entries[0].sources?.length);
});

run("Finding: resolves without evidence map to label-only", () => {
  const result = applyCitations("See [Finding #105].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Finding #105");
});

run("Finding: dedupes co-cited evidence refs", () => {
  const findingEvidenceMap = { "2108": ["EFTA01296686"] };
  const result = applyCitations(
    "(Finding #2108, EFTA01296686).",
    { findingEvidenceMap },
  );
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Finding #2108");
});

// ---------------------------------------------------------------------------
// URL citations
// ---------------------------------------------------------------------------

run("URL: extractEvidenceLinks resolves raw URL", () => {
  const links = extractEvidenceLinks("https://example.com/doc");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://example.com/doc");
  assert.equal(links[0].label, "https://example.com/doc");
});

// ---------------------------------------------------------------------------
// Statute citations (should pass through as unknown/label-only)
// ---------------------------------------------------------------------------

run("Statute: unrecognized pattern passes through unchanged", () => {
  const input = "Under 22 U.S.C. 611(c)(1), agents must register.";
  const result = applyCitations(input);
  assert.equal(result.entries.length, 0);
  assert.ok(result.markdown.includes("22 U.S.C. 611(c)(1)"));
});

// ---------------------------------------------------------------------------
// Cross-cutting behavior
// ---------------------------------------------------------------------------

run("preserves markdown links and does not split URL citations", () => {
  const input = "Israel and Qatar had [no formal diplomatic relations](https://en.wikipedia.org/wiki/Israel%E2%80%93Qatar_relations). [EFTA02609150]";
  const result = applyCitations(input);
  assert.ok(
    result.markdown.includes("[no formal diplomatic relations](https://en.wikipedia.org/wiki/Israel%E2%80%93Qatar_relations)"),
    "markdown link target should remain intact",
  );
  const labels = result.entries.map((e) => e.label);
  for (const frag of ["https:", "en.wikipedia.org", "wiki"]) {
    assert.ok(!labels.includes(frag), `unexpected split fragment: ${frag}`);
  }
});

run("shares stable numbering across multiple citation blocks", () => {
  const state = createCitationState();
  const first = applyCitations("First [EFTA01234567].", {}, state);
  const second = applyCitations("Second [EFTA01234567] and [EFTA07654321].", {}, state);
  assert.equal(state.entries.length, 2);
  assert.match(first.markdown, />1<\/a>/);
  assert.match(second.markdown, />1<\/a>/);
  assert.match(second.markdown, />2<\/a>/);
});

run("splitCitationGroup: splits comma-separated tokens", () => {
  const tokens = splitCitationGroup("EFTA02504960, 990:660789697");
  assert.equal(tokens.length, 2);
  assert.ok(tokens[0].includes("EFTA"));
  assert.ok(tokens[1].includes("990:"));
});

run("multiple types in one group: each gets a citation entry", () => {
  const result = applyCitations("See [EFTA02504960, 990:660789697].");
  assert.equal(result.entries.length, 2);
});

// ---------------------------------------------------------------------------
// getCitationHealthTier
// ---------------------------------------------------------------------------

run("getCitationHealthTier: returns correct tier for known prefixes", () => {
  assert.equal(getCitationHealthTier("efta:EFTA02504960"), "tier4");
  assert.equal(getCitationHealthTier("sec:0001193125-21-123456"), "tier1");
  assert.equal(getCitationHealthTier("fec:C00352732"), "tier1");
  assert.equal(getCitationHealthTier("fara:6458"), "tier3");
  assert.equal(getCitationHealthTier("lda:Broidy Capital"), "tier2");
  assert.equal(getCitationHealthTier("kpmg:IPI"), "label-only");
  assert.equal(getCitationHealthTier("finding:2108"), "label-only");
});

run("getCitationHealthTier: returns skip for unknown prefixes", () => {
  assert.equal(getCitationHealthTier("unknown:something"), "skip");
  assert.equal(getCitationHealthTier(""), "skip");
  assert.equal(getCitationHealthTier("https://example.com"), "skip");
});

// ---------------------------------------------------------------------------
// Registry: all 26 types resolve through applyCitations
// ---------------------------------------------------------------------------

run("Registry: all 26 types produce citation entries", () => {
  const tokens = [
    "Finding #1",
    "EFTA02504960",
    "HOUSE_OVERSIGHT_12345",
    "SEC:0001193125-21-123456",
    "EDGAR:0001193125-21-123456",
    "990:660789697",
    "ACRIS:2017021700466001",
    "CL:69737684",
    "FEC:C00352732",
    "FARA:6458",
    "USVI:582530",
    "FL-SunBiz:F08000003048",
    "NM-SoS:1615137",
    "NY-SoS:2773652",
    "REG:FL:F08000003048",
    "DS10",
    "KPMG:IPI",
    "LDA:Broidy Capital",
    "OpenSanctions:Q125731",
    "DOCUMENTCLOUD:24402693",
    "OffshoreAlert:DB-Consent-Order",
    "MUCKROCK:78799",
    "LittleSis:101661",
    "ICIJ:82004676",
    "USASPENDING:CONT_AWD_W91WAW11F0017",
    "MEDICARE:1003000126",
  ];

  for (const token of tokens) {
    const result = applyCitations(`See [${token}].`);
    assert.ok(
      result.entries.length >= 1,
      `Token "${token}" should produce at least one citation entry, got ${result.entries.length}`,
    );
  }
});

// ---------------------------------------------------------------------------
// Registry: all 19 types extract from raw evidence text
// ---------------------------------------------------------------------------

run("Registry: all extractable types produce evidence links", () => {
  // Finding has no extract (only resolves in bracket context) — excluded
  const rawRefs = [
    { input: "EFTA02504960", expectMin: 1 },
    { input: "HOUSE_OVERSIGHT_12345", expectMin: 1 },
    { input: "SEC:0001193125-21-123456", expectMin: 1 },
    { input: "EDGAR:0001193125-21-123456", expectMin: 1 },
    { input: "990:660789697", expectMin: 1 },
    { input: "ACRIS:2017021700466001", expectMin: 1 },
    { input: "CL:69737684", expectMin: 1 },
    { input: "FEC:C00352732", expectMin: 1 },
    { input: "FARA:6458", expectMin: 1 },
    { input: "USVI:582530", expectMin: 1 },
    { input: "FL-SunBiz:F08000003048", expectMin: 1 },
    { input: "NM-SoS:1615137", expectMin: 1 },
    { input: "NY-SoS:2773652", expectMin: 1 },
    { input: "REG:FL:F08000003048", expectMin: 1 },
    { input: "DS10:GRATITUDE", expectMin: 1 },
    { input: "KPMG:IPI", expectMin: 1 },
    { input: "LDA:Broidy Capital", expectMin: 1 },
    { input: "OpenSanctions:Q125731", expectMin: 1 },
    { input: "DOCUMENTCLOUD:24402693", expectMin: 1 },
    { input: "OffshoreAlert:DB-Consent-Order", expectMin: 1 },
    { input: "MUCKROCK:78799", expectMin: 1 },
    { input: "LittleSis:101661", expectMin: 1 },
    { input: "ICIJ:82004676", expectMin: 1 },
  ];

  for (const { input, expectMin } of rawRefs) {
    const links = extractEvidenceLinks(input);
    assert.ok(
      links.length >= expectMin,
      `extractEvidenceLinks("${input}") should produce >= ${expectMin} links, got ${links.length}`,
    );
  }
});

// ---------------------------------------------------------------------------
// Registry: unknown tokens fall through gracefully
// ---------------------------------------------------------------------------

run("Registry: unrecognized bracket content passes through unchanged", () => {
  const result = applyCitations("See [some random text].");
  assert.equal(result.entries.length, 0);
  assert.ok(result.markdown.includes("[some random text]"));
});

run("Registry: empty evidence string returns empty links", () => {
  const links = extractEvidenceLinks("");
  assert.equal(links.length, 0);
});

// ---------------------------------------------------------------------------
// Registry: token pattern derivation works
// ---------------------------------------------------------------------------

run("Registry: splitCitationGroup recognizes all token types", () => {
  const combined = "EFTA02504960, SEC:0001193125-21-123456, FEC:C00352732, DS10, KPMG:IPI";
  const tokens = splitCitationGroup(combined);
  assert.equal(tokens.length, 5, `Expected 5 tokens from group, got ${tokens.length}: ${JSON.stringify(tokens)}`);
});

run("Registry: splitCitationGroup recognizes new types", () => {
  const combined = "DOCUMENTCLOUD:24402693, ICIJ:82004676, LittleSis:101661, USASPENDING:CONT_AWD_W91WAW11F0017, MEDICARE:1003000126";
  const tokens = splitCitationGroup(combined);
  assert.equal(tokens.length, 5, `Expected 5 tokens, got ${tokens.length}: ${JSON.stringify(tokens)}`);
});

// ---------------------------------------------------------------------------
// source-urls.json override (structural test — file exists and is loaded)
// ---------------------------------------------------------------------------

run("source-urls.json: override file is loaded without error", () => {
  // If the JSON file didn't parse or import correctly, the module would
  // have thrown at import time. This test confirms the file exists and
  // is valid JSON. Actual override behavior is tested by adding a key
  // to source-urls.json and verifying it resolves.
  // For now, just verify extractEvidenceLinks still works (module loaded).
  const links = extractEvidenceLinks("some-unknown-ref");
  assert.ok(Array.isArray(links));
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests.\n`);
if (failed > 0) {
  process.exit(1);
}
process.stdout.write("All citation tests passed.\n");

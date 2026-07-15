import assert from "node:assert/strict";
import { resolve } from "node:path";
import { createJiti } from "jiti";

const jiti = createJiti(import.meta.url);
const citationsPath = resolve("./src/lib/citations.ts");
const {
  applyCitations,
  createCitationState,
  extractEvidenceLinks,
  resolveSourceRecord,
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

run("EFTA: resolves token to DOJ DataSet URL", () => {
  const result = applyCitations("See [EFTA02504960] for details.");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "EFTA02504960");
  // EFTA02504960 falls in DataSet 11's Bates range.
  assert.equal(
    result.entries[0].url,
    "https://www.justice.gov/epstein/files/DataSet%2011/EFTA02504960.pdf",
  );
  assert.ok(result.entries[0].key.startsWith("efta:"));
  assert.equal(result.entries[0].directLink, true);
});

run("EFTA: extractEvidenceLinks resolves EFTA ID to DOJ URL", () => {
  const links = extractEvidenceLinks("EFTA02504960");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /justice\.gov\/epstein\/files\/DataSet%2011\/EFTA02504960\.pdf/);
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
  assert.equal(
    result.entries[0].url,
    "https://www.sec.gov/Archives/edgar/data/1193125/000119312521123456/0001193125-21-123456-index.html",
  );
});

run("EDGAR: resolves same as SEC variant", () => {
  const result = applyCitations("See [EDGAR:0001193125-21-123456].");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].url ?? "", /sec\.gov\/Archives\/edgar/);
});

run("SEC ADSH: resolves prose accession notation", () => {
  const result = applyCitations("Filed (SEC EDGAR ADSH 0001193125-23-045802).");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "SEC 0001193125-23-045802");
  assert.equal(
    result.entries[0].url,
    "https://www.sec.gov/Archives/edgar/data/1193125/000119312523045802/0001193125-23-045802-index.html",
  );
  assert.match(result.markdown, /href="\/sources\//);
});

run("SEC CIK: resolves prose CIK notation", () => {
  const result = applyCitations("Issuer (CIK 0001823896).");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "CIK 1823896");
  assert.equal(result.entries[0].url, "https://www.sec.gov/edgar/browse/?CIK=1823896");
  assert.match(result.markdown, /href="\/sources\//);
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
// CMS Open Payments
// ---------------------------------------------------------------------------

run("OPENPAYMENTS: resolves covered-recipient profile ID", () => {
  const result = applyCitations("Per [OPENPAYMENTS:704135].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "CMS Open Payments profile 704135");
  assert.equal(result.entries[0].url, "https://openpaymentsdata.cms.gov/physician/704135");
});

run("OPENPAYMENTS: extractEvidenceLinks resolves profile ID", () => {
  const links = extractEvidenceLinks("OPENPAYMENTS:704135");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://openpaymentsdata.cms.gov/physician/704135");
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

run("ACRIS: strips FT_ document-type prefix before building doc_id URL", () => {
  const result = applyCitations("Recorded [ACRIS:FT_1690000317169].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "ACRIS 1690000317169");
  assert.equal(
    result.entries[0].url,
    "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentDetail?doc_id=1690000317169",
  );
  const links = extractEvidenceLinks("ACRIS:FT_1690000317169");
  assert.ok(links.some(l => l.url === "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentDetail?doc_id=1690000317169"));
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

run("CourtListener opinion: explicit opinion/<id> resolves to opinion URL", () => {
  const result = applyCitations("See [CourtListener:opinion/564802].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, "https://www.courtlistener.com/opinion/564802/");
});

run("CourtListener opinion: extractEvidenceLinks resolves explicit opinion ref", () => {
  const links = extractEvidenceLinks("CourtListener:opinion/564802");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /courtlistener\.com\/opinion\/564802\//);
});

run("CourtListener bare numeric: NOT guessed as an opinion URL", () => {
  // Bare "CourtListener:<id>" ids are unreliable in the corpus (junk like
  // CourtListener:1 plus 8-digit docket-magnitude values), so they must never
  // resolve to a fabricated opinion URL — they stay an honest record_only card.
  const links = extractEvidenceLinks("CourtListener:68822588");
  assert.equal(links.length, 1);
  assert.equal(links[0].sourceKind, "record_only");
  assert.ok(!(links[0].url ?? "").includes("courtlistener.com"));
});

run("CourtListener junk numeric: small ids never link out", () => {
  const links = extractEvidenceLinks("CourtListener:1");
  assert.ok(links.every((link) => !(link.url ?? "").includes("courtlistener.com")));
});

run("NYSCEF_CASE: resolves encoded docket ID to NYSCEF URL", () => {
  const result = applyCitations("See [NYSCEF_CASE:abc%2F123].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "NYSCEF abc%2F123");
  assert.match(result.entries[0].url ?? "", /iapps\.courts\.state\.ny\.us\/nyscef\/CaseDetails/);
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
// Federal Register
// ---------------------------------------------------------------------------

run("FR: resolves document number to Federal Register URL", () => {
  const result = applyCitations("See [FR:2025-06461].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Federal Register 2025-06461");
  assert.match(result.entries[0].url ?? "", /federalregister\.gov\/d\/2025-06461/);
});

run("FR: extractEvidenceLinks resolves Federal Register document", () => {
  const links = extractEvidenceLinks("FR:2025-06461");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /federalregister\.gov\/d\/2025-06461/);
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
  assert.equal(result.entries[0].label, "USVI 582530");
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

run("REG: GB jurisdiction links to Companies House", () => {
  const result = applyCitations("See [REG:GB:11441275].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "GB 11441275");
  assert.equal(result.entries[0].url, "https://find-and-update.company-information.service.gov.uk/company/11441275");
});

run("REG: GB jurisdiction handles OC (LLP) numbers", () => {
  const result = applyCitations("See [REG:GB:OC379532].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, "https://find-and-update.company-information.service.gov.uk/company/OC379532");
});

// ---------------------------------------------------------------------------
// Companies House (companies-house: prefix)
// ---------------------------------------------------------------------------

run("Companies House: resolves numeric company number", () => {
  const result = applyCitations("See [companies-house:08150769].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Companies House 08150769");
  assert.equal(result.entries[0].url, "https://find-and-update.company-information.service.gov.uk/company/08150769");
});

run("Companies House: resolves OC (LLP) number, uppercased", () => {
  const result = applyCitations("See [companies-house:oc377122].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, "https://find-and-update.company-information.service.gov.uk/company/OC377122");
});

run("Companies House: extractEvidenceLinks resolves company number", () => {
  const links = extractEvidenceLinks("companies-house:12667034");
  assert.ok(links.some(l => l.url === "https://find-and-update.company-information.service.gov.uk/company/12667034"));
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
// KPMG (record-only source record)
// ---------------------------------------------------------------------------

run("KPMG: resolves to source-record citation", () => {
  const result = applyCitations("Per [KPMG:IPI] review.");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /KPMG.*IPI/);
  assert.equal(result.entries[0].sourceKind, "hosted_copy");
  assert.equal(result.entries[0].url, "/source-artifacts/ipi-kpmg-forensic-review-2020.pdf");
  assert.match(result.entries[0].sourceRecordUrl ?? "", /^\/sources\//);
});

run("KPMG: extractEvidenceLinks returns source-record link", () => {
  const links = extractEvidenceLinks("KPMG:IPI");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "/source-artifacts/ipi-kpmg-forensic-review-2020.pdf");
  assert.match(links[0].sourceRecordUrl ?? "", /^\/sources\//);
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

run("OpenSanctions: resolves space-separated entity notation", () => {
  const result = applyCitations("See (OpenSanctions Q28591).");
  assert.equal(result.entries.length, 1);
  assert.match(result.entries[0].label, /OpenSanctions.*Q28591/);
  assert.equal(result.entries[0].url, "https://www.opensanctions.org/entities/Q28591/");
});

run("OpenSanctions: extractEvidenceLinks resolves entity", () => {
  const links = extractEvidenceLinks("OpenSanctions:Q125731");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://www.opensanctions.org/entities/Q125731/");
});

run("OpenSanctions: resolves dataset-prefixed canonical ID (NK- hash)", () => {
  const result = applyCitations("See [OpenSanctions:NK-TLjnXcjHHZa2yULEzGNW65].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].sourceKind, "external");
  assert.equal(
    result.entries[0].url,
    "https://www.opensanctions.org/entities/NK-TLjnXcjHHZa2yULEzGNW65/",
  );
});

run("OpenSanctions: resolves dataset-prefixed canonical ID (ohchr- hash)", () => {
  const id = "ohchr-e23c9d0fa04724b6c4108ec8e42db7b83eb9ffcb";
  const result = applyCitations(`See [OpenSanctions:${id}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, `https://www.opensanctions.org/entities/${id}/`);
});

run("OpenSanctions: garbage token does not emit a dead entity URL", () => {
  // "search" is a UI path, not an entity ID — /entities/search/ 404s.
  const result = applyCitations("See [OpenSanctions:search].");
  for (const entry of result.entries) {
    assert.ok(
      !(entry.url ?? "").includes("opensanctions.org"),
      `unexpected opensanctions.org link: ${entry.url}`,
    );
  }
  // Malformed slugs (a search query, not an entity) also must not link out.
  const slug = applyCitations("See [OpenSanctions:search-Darren-Indyke].");
  for (const entry of slug.entries) {
    assert.ok(!(entry.url ?? "").includes("opensanctions.org"));
  }
});

run("OpenSanctions: prose mention does not become a citation", () => {
  // "OpenSanctions search returned ..." is narrative, not a cite — no source card.
  const result = applyCitations("OpenSanctions search returned 3 PEP hits.");
  assert.equal(result.entries.length, 0);
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

run("OffshoreAlert: resolves slug to hosted consent-order copy", () => {
  const result = applyCitations("See [OffshoreAlert:DB-Consent-Order-NYDFS].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "OffshoreAlert:DB-Consent-Order-NYDFS");
  assert.equal(result.entries[0].sourceKind, "hosted_copy");
  assert.equal(result.entries[0].url, "/source-artifacts/nydfs-deutsche-bank-epstein-consent-order-2020.pdf");
});

run("OffshoreAlert: hosted primary copies resolve to local PDFs, never offshorealert.com", () => {
  const hosted = {
    "OffshoreAlert:Priscilla-Doe-v-Epstein": "/source-artifacts/priscilla-doe-v-epstein-estate-complaint.pdf",
    "OffshoreAlert:Katlyn-Doe-v-Epstein": "/source-artifacts/katlyn-doe-v-epstein-estate-complaint.pdf",
    "OffshoreAlert:Ali-Karimi-v-DB": "/source-artifacts/ali-karimi-v-deutsche-bank-class-action-complaint.pdf",
    "OffshoreAlert:Madoff-Victims-SIPA-08-01789": "/source-artifacts/madoff-victims-sipa-08-01789.pdf",
  };
  for (const [token, pdf] of Object.entries(hosted)) {
    const result = applyCitations(`See [${token}].`);
    assert.equal(result.entries.length, 1, `${token} should resolve to one entry`);
    assert.equal(result.entries[0].sourceKind, "hosted_copy", `${token} should be hosted_copy`);
    assert.equal(result.entries[0].url, pdf, `${token} should point at hosted PDF`);
  }
});

run("OffshoreAlert: un-hosted slug is honest record_only with no dead link", () => {
  // Liquid Funding RoC PDF is ~43MB, over the Cloudflare 25 MiB per-file limit.
  const result = applyCitations("See [OffshoreAlert:Liquid-Funding-RoC-EC29378].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].sourceKind, "record_only");
  assert.ok(!(result.entries[0].url ?? "").includes("offshorealert.com"));
});

run("OffshoreAlert: extractEvidenceLinks never emits an offshorealert.com URL", () => {
  for (const token of [
    "OffshoreAlert:Katlyn-Doe-v-Epstein",
    "OffshoreAlert:Liquid-Funding-RoC-EC29378",
    "OffshoreAlert:Some-Unknown-Doc",
  ]) {
    for (const link of extractEvidenceLinks(token)) {
      assert.ok(
        !(link.url ?? "").includes("offshorealert.com"),
        `${token} produced a dead offshorealert.com link: ${link.url}`,
      );
    }
  }
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

run("LittleSis: resolves whitespace-separated entity ID", () => {
  const result = applyCitations("See [LittleSis 5617].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, "https://littlesis.org/entities/5617");
});

run("LittleSis: resolves 'entity' keyword form", () => {
  const links = extractEvidenceLinks("LittleSis entity 63898");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://littlesis.org/entities/63898");
});

run("LittleSis: resolves 'ID' keyword form", () => {
  const result = applyCitations("See [LittleSis ID 5617].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].url, "https://littlesis.org/entities/5617");
});

run("LittleSis: resolves 'rel' relationship form", () => {
  const result = applyCitations("See [LittleSis rel 2043488].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "LittleSis relationship 2043488");
  assert.equal(result.entries[0].url, "https://littlesis.org/relationships/2043488");
});

run("LittleSis: resolves full 'relationship' keyword form", () => {
  const links = extractEvidenceLinks("LittleSis relationship 274178");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://littlesis.org/relationships/274178");
});

run("LittleSis: whitespace year is not mistaken for an entity ID", () => {
  // "LittleSis 2010" in prose is a year, not entity 2010 — it must never
  // resolve to a littlesis.org link (a generic record_only card is fine).
  const result = applyCitations("Brad donated per [LittleSis 2010].");
  assert.ok(!result.entries.some(e => /littlesis\.org/.test(e.url ?? "")));
  const links = extractEvidenceLinks("LittleSis 2010");
  assert.ok(!links.some(l => /littlesis\.org/.test(l.url ?? "")));
});

run("LittleSis: explicit keyword overrides the year guard", () => {
  const links = extractEvidenceLinks("LittleSis entity 2010");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://littlesis.org/entities/2010");
});

run("LittleSis: bare 'relationships' word with no ID is not a citation", () => {
  const links = extractEvidenceLinks("zero LittleSis relationships found");
  assert.ok(!links.some(l => /littlesis\.org/.test(l.url ?? "")));
});

run("LittleSis: extracts entity ID amid multi-token evidence ref", () => {
  const links = extractEvidenceLinks("ArcticToday / Politiken / LittleSis 82179");
  assert.ok(links.some(l => l.url === "https://littlesis.org/entities/82179"));
});

run("LittleSis: entity ID stops at trailing parenthetical", () => {
  const links = extractEvidenceLinks("LittleSis entity 68579 (Biden bundler 2008)");
  assert.ok(links.some(l => l.url === "https://littlesis.org/entities/68579"));
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

run("ICIJ: resolves dataset slug form to node URL", () => {
  const result = applyCitations("See [icij-paradise-papers-56009779].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "ICIJ 56009779");
  assert.equal(result.entries[0].url, "https://offshoreleaks.icij.org/nodes/56009779");
  const links = extractEvidenceLinks("icij-paradise-papers-56009779");
  assert.ok(links.some(l => l.url === "https://offshoreleaks.icij.org/nodes/56009779"));
});

// ---------------------------------------------------------------------------
// Finding references
// ---------------------------------------------------------------------------

run("Finding: resolves with evidence map to popover citation plus sources", () => {
  const findingEvidenceMap = { "2108": ["EFTA01296686"] };
  const result = applyCitations("See [Finding #2108].", { findingEvidenceMap });
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Finding #2108");
  assert.equal(result.entries[0].kind, "finding");
  assert.equal(result.entries[0].targetKind, "finding_popover");
  assert.equal(result.entries[0].url, undefined);
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

run("Finding evidence: recursively resolves finding-backed sources", () => {
  const findingEvidenceMap = {
    "42": ["Finding #7"],
    "7": ["EFTA01296686"],
  };
  const links = extractEvidenceLinks("Finding #42", { findingEvidenceMap });
  assert.equal(links.length, 1);
  assert.ok((links[0].url ?? "").includes("EFTA01296686"));
});

run("Internal refs: finding groups expand into finding citations", () => {
  const result = applyCitations("See [Finding #5115, #4755].");
  assert.equal(result.entries.length, 2);
  assert.ok(!result.markdown.includes("[Finding #5115, #4755]"));
  assert.ok(result.markdown.includes('data-citation-key="finding:5115"'));
  assert.ok(result.markdown.includes('data-citation-key="finding:4755"'));
});

run("Internal refs: plural finding groups expand into finding citations", () => {
  const result = applyCitations("See [Findings #1728, #1744].");
  assert.equal(result.entries.length, 2);
  assert.ok(!result.markdown.includes("[Findings #1728, #1744]"));
  assert.ok(result.markdown.includes('data-citation-key="finding:1728"'));
  assert.ok(result.markdown.includes('data-citation-key="finding:1744"'));
});

run("Internal refs: mixed connection and source groups keep the source citation", () => {
  const result = applyCitations("See [Connection #783, EFTA01896707].");
  assert.equal(result.entries.length, 1);
  assert.ok(!result.markdown.includes("[Connection #783, EFTA01896707]"));
  assert.ok(result.markdown.includes("Connection #783"));
  assert.match(result.markdown, /<sup class="citation">/);
});

run("Internal refs: mixed finding and loose source labels render cleanly", () => {
  const result = applyCitations("See [Finding #4190; SEC Litigation Release 25155].", {
    findingEvidenceMap: { "4190": ["EFTA01896707"] },
  });
  assert.equal(result.entries.length, 2);
  assert.ok(!result.markdown.includes("[Finding #4190; SEC Litigation Release 25155]"));
  assert.equal(result.entries[0].kind, "finding");
  assert.equal(result.entries[1].kind, "source");
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

run("Rendered EFTA citations link directly to DOJ, preserving the source record", () => {
  const result = applyCitations("See [EFTA02504960].");
  assert.equal(result.entries.length, 1);
  // Gated DOJ PDFs can't embed, so the inline citation links straight out.
  assert.match(result.entries[0].url ?? "", /justice\.gov\/epstein\/files\/DataSet%2011\//);
  assert.equal(result.entries[0].directLink, true);
  // The provenance record still exists and is reachable from the footnote.
  assert.match(result.entries[0].sourceRecordUrl ?? "", /^\/sources\//);
  assert.match(result.markdown, /href="https:\/\/www\.justice\.gov\/epstein\/files\/DataSet%2011\/EFTA02504960\.pdf"/);
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
// Registry: all 19 types resolve through applyCitations
// ---------------------------------------------------------------------------

run("Registry: all 29 types produce citation entries", () => {
  const tokens = [
    "Finding #1",
    "EFTA02504960",
    "HOUSE_OVERSIGHT_12345",
    "SEC:0001193125-21-123456",
    "EDGAR:0001193125-21-123456",
    "CIK 0001823896",
    "SEC EDGAR ADSH 0001193125-23-045802",
    "990:660789697",
    "ACRIS:2017021700466001",
    "CL:69737684",
    "NYSCEF_CASE:abc%2F123",
    "FEC:C00352732",
    "FARA:6458",
    "FR:2025-06461",
    "USVI:582530",
    "FL-SunBiz:F08000003048",
    "NM-SoS:1615137",
    "NY-SoS:2773652",
    "REG:FL:F08000003048",
    "companies-house:08150769",
    "DS10",
    "KPMG:IPI",
    "LDA:Broidy Capital",
    "OpenSanctions:Q125731",
    "DOCUMENTCLOUD:24402693",
    "OffshoreAlert:DB-Consent-Order",
    "MUCKROCK:78799",
    "LittleSis:101661",
    "ICIJ:82004676",
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
    { input: "CIK 0001823896", expectMin: 1 },
    { input: "SEC EDGAR ADSH 0001193125-23-045802", expectMin: 1 },
    { input: "990:660789697", expectMin: 1 },
    { input: "ACRIS:2017021700466001", expectMin: 1 },
    { input: "CL:69737684", expectMin: 1 },
    { input: "NYSCEF_CASE:abc%2F123", expectMin: 1 },
    { input: "FEC:C00352732", expectMin: 1 },
    { input: "FARA:6458", expectMin: 1 },
    { input: "FR:2025-06461", expectMin: 1 },
    { input: "USVI:582530", expectMin: 1 },
    { input: "FL-SunBiz:F08000003048", expectMin: 1 },
    { input: "NM-SoS:1615137", expectMin: 1 },
    { input: "NY-SoS:2773652", expectMin: 1 },
    { input: "REG:FL:F08000003048", expectMin: 1 },
    { input: "companies-house:08150769", expectMin: 1 },
    { input: "DS10:GRATITUDE", expectMin: 1 },
    { input: "KPMG:IPI", expectMin: 1 },
    { input: "LDA:Broidy Capital", expectMin: 1 },
    { input: "OpenSanctions:Q125731", expectMin: 1 },
    { input: "OpenSanctions Q28591", expectMin: 1 },
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
  const combined = "DOCUMENTCLOUD:24402693, ICIJ:82004676, LittleSis:101661";
  const tokens = splitCitationGroup(combined);
  assert.equal(tokens.length, 3, `Expected 3 tokens, got ${tokens.length}: ${JSON.stringify(tokens)}`);
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
// Provenance honesty: internal-artifact suppression (WS2) + honest text (WS4)
// ---------------------------------------------------------------------------

run("Internal artifact: temp/session path produces no source card", () => {
  assert.equal(resolveSourceRecord("/tmp/osint-5RXDUfzR/ethics-agreement.txt"), null);
  assert.equal(extractEvidenceLinks("/tmp/osint-5RXDUfzR/ethics-agreement.txt").length, 0);
});

run("Internal artifact: analysis-run handle produces no source card", () => {
  assert.equal(resolveSourceRecord("analysis-run-1"), null);
  assert.equal(extractEvidenceLinks("analysis-run-1").length, 0);
});

run("Internal artifact: analysis_run underscore variant is suppressed", () => {
  assert.equal(resolveSourceRecord("analysis_run"), null);
  assert.equal(extractEvidenceLinks("analysis_run").length, 0);
});

run("Internal artifact: bare #N internal ref produces no source card", () => {
  assert.equal(resolveSourceRecord("#739110438"), null);
  assert.equal(extractEvidenceLinks("#739110438").length, 0);
  assert.equal(extractEvidenceLinks("#4").length, 0);
});

run("Internal artifact: #YYYY is NOT suppressed (neutral-citation year guard)", () => {
  const record = resolveSourceRecord("#2014");
  assert.ok(record, "#2014 should resolve to a record, not null");
  assert.notEqual(record.kind, "private_internal");
});

run("Internal artifact: underscore redaction notation is NOT suppressed", () => {
  // "[_____]" is legitimate redaction notation in source prose (e.g. an SEC
  // filing blanking an investor name), not analyst junk — must not be treated
  // as an internal artifact.
  const record = resolveSourceRecord("_____");
  assert.ok(record === null || record.kind !== "private_internal", "_____ must not be classified internal");
});

run("Internal artifact: inline artifact-only group renders as plain text", () => {
  // [analysis_run] / [#4] in prose must not become a chip OR a raw [..] token.
  for (const tok of ["analysis_run", "#4", "#739110438"]) {
    const result = applyCitations(`As shown [${tok}] here.`);
    assert.equal(result.entries.length, 0, `[${tok}] should produce no citation entry`);
    assert.ok(!result.markdown.includes(`[${tok}]`), `[${tok}] bracket token should be stripped`);
    assert.ok(!result.markdown.includes('class="citation"'), `[${tok}] should not render a citation chip`);
  }
});

run("Internal artifact: real internal reference and source still render in brackets", () => {
  const finding = applyCitations("See [Finding #6023].");
  assert.equal(finding.entries.length, 1);
  const source = applyCitations("See [companies-house:08150769].");
  assert.equal(source.entries.length, 1);
  assert.match(source.entries[0].url ?? "", /company-information\.service\.gov\.uk/);
});

run("Internal artifact: finding-NNNN self-ref produces no source card", () => {
  assert.equal(resolveSourceRecord("finding-11099"), null);
  assert.equal(extractEvidenceLinks("finding-11099").length, 0);
});

run("Internal artifact: bare-numeric self-ref produces no source card", () => {
  // Non-4-digit bare numbers (counters, finding ids) are suppressed; 4-digit
  // years are carved out (see the UK-neutral-cite test below).
  assert.equal(resolveSourceRecord("100"), null);
  assert.equal(extractEvidenceLinks("100").length, 0);
  assert.equal(resolveSourceRecord("11099"), null);
});

run("Internal artifact: 4-digit years are NOT suppressed (UK neutral cites)", () => {
  // "[2014] EWHC 1887" etc. — suppressing the bare year would orphan the inline
  // citation. Years stay resolvable (record_only), never private_internal.
  for (const year of ["2014", "2022", "2025"]) {
    const record = resolveSourceRecord(year);
    assert.ok(record, `${year} should resolve to a record, not null`);
    assert.notEqual(record.kind, "private_internal", `${year} must not be suppressed`);
  }
});

run("record_only: honest access note, no 'held locally' language", () => {
  const record = resolveSourceRecord("web:CNN-2019-04-02");
  assert.ok(record, "web: ref should resolve to a record, not null");
  assert.equal(record.kind, "record_only");
  assert.equal(record.accessNote, "On file; no public URL is available for this source.");
  assert.ok(!/held locally/i.test(record.accessNote));
});

run("Namespaced refs: web:/ref:/hf_ stay record_only, not suppressed", () => {
  // These point at real (often public) sources that lack a captured URL.
  // They must surface as honest record_only cards to preserve provenance —
  // suppressing them as private_internal would hide the source entirely.
  for (const token of [
    "web:aegismalta.com",
    "ref:American-Oversight-cyber-ninjas-emails",
    "hf_notesbymuneeb:Gulen-audio-recording",
  ]) {
    const record = resolveSourceRecord(token);
    assert.ok(record, `${token} should resolve to a record, not null`);
    assert.equal(record.kind, "record_only", `${token} should be record_only`);
  }
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests.\n`);
if (failed > 0) {
  process.exit(1);
}
process.stdout.write("All citation tests passed.\n");

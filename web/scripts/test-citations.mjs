import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createJiti } from "jiti";

const jiti = createJiti(import.meta.url);
const citationsPath = fileURLToPath(
  new URL("../src/lib/citations.ts", import.meta.url),
);
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

run("DOJCOURT: preserves the exact case-grouped DOJ document URL", () => {
  const result = applyCitations("See [DOJCOURT:EFTA02824136].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "DOJCOURT:EFTA02824136");
  assert.match(
    result.entries[0].url ?? "",
    /Court%20Records\/United%20States%20v\.%20Epstein/,
  );
  assert.equal(result.entries[0].directLink, true);
  assert.equal(result.entries[0].sourceType, "court_record");
});

run("DOJCOURT: extractEvidenceLinks uses the exact release mapping", () => {
  const links = extractEvidenceLinks("DOJCOURT:EFTA02824136");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /EFTA02824136\.pdf$/);
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
// Senate Finance Committee
// ---------------------------------------------------------------------------

run("SENATE_FINANCE: resolves an official archive path", () => {
  const ref = "SENATE_FINANCE:ranking-members-news/example-release";
  const result = applyCitations(`See [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, ref);
  assert.equal(
    result.entries[0].url,
    "https://www.finance.senate.gov/ranking-members-news/example-release",
  );
});

run("SENATE_FINANCE: extractEvidenceLinks resolves an attachment", () => {
  const links = extractEvidenceLinks("SENATE_FINANCE:download/example-memo");
  assert.equal(links.length, 1);
  assert.equal(links[0].url, "https://www.finance.senate.gov/download/example-memo");
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

const propertySourceFixtures = [
  {
    sourceId: "us-nc-onemap-parcels",
    jurisdiction: "37005",
    kind: "parcel",
    nativeId: "3013467134",
    url: "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1",
  },
  {
    sourceId: "us-nm-santa-fe-clerktrack-index",
    jurisdiction: "35049",
    kind: "recorded_instrument",
    nativeId: "1019405",
    url: "https://www.santafecountynm.gov/clerk/divisions/public-records-access",
  },
  {
    sourceId: "us-fl-dor-property-roll",
    jurisdiction: "12",
    kind: "bulk_release",
    nativeId: "nal-2026-01",
    url: "https://www.floridarevenue.com/property/Pages/DataPortal_RequestAssessmentRollGISData.aspx",
  },
  {
    sourceId: "us-mt-msl-cadastral",
    jurisdiction: "30069",
    kind: "parcel",
    nativeId: "56382732101040000",
    url: "https://msl.mt.gov/geoinfo/msdi/cadastral/",
  },
  {
    sourceId: "us-fl-miami-dade-official-records",
    jurisdiction: "12086",
    kind: "instrument",
    nativeId: "CFN-2026-42",
    url: "https://www.miamidadeclerk.gov/clerk/official-records.page",
  },
  {
    sourceId: "us-fl-miami-dade-official-records-public",
    jurisdiction: "12086",
    kind: "instrument",
    nativeId: "2026-R-55844",
    url: "https://onlineservices.miamidadeclerk.gov/officialrecords/",
  },
  {
    sourceId: "us-fl-miami-dade-property-appraiser",
    jurisdiction: "12086",
    kind: "parcel",
    nativeId: "0101000000020",
    url: "https://www.miamidade.gov/propertysearch/",
  },
  {
    sourceId: "us-fl-orange-official-records",
    jurisdiction: "12095",
    kind: "instrument",
    nativeId: "2026-OR-1",
    url: "https://www.occompt.com/161/Official-Records",
  },
  {
    sourceId: "us-fl-orange-tax-collector-property-tax",
    jurisdiction: "12095",
    kind: "tax_account",
    nativeId: "01-20-27-0000-00001",
    url: "https://www.octaxcol.com/taxes/about-property-tax/tax-roll-download/",
  },
  {
    sourceId: "us-fl-orange-comptroller-tax-deed-sales",
    jurisdiction: "12095",
    kind: "tax_deed_sale",
    nativeId: "TDA-2026-1",
    url: "https://or.occompt.com/recorder/tdsmweb/applicationSearch.jsp?guest=true",
  },
  {
    sourceId: "us-ma-massgis-parcels",
    jurisdiction: "25",
    kind: "bulk_release",
    nativeId: "GOSNOLD-2026",
    url: "https://www.mass.gov/info-details/massgis-data-property-tax-parcels",
  },
  {
    sourceId: "us-il-cook-parcel-universe",
    jurisdiction: "17031",
    kind: "parcel_snapshot",
    nativeId: "01-01-106-009-1001",
    url: "https://datacatalog.cookcountyil.gov/Property-Taxation/Assessor-Parcel-Universe/nj4t-kc8j",
  },
  {
    sourceId: "us-md-sdat-property-hidden",
    jurisdiction: "24005",
    kind: "parcel",
    nativeId: "04030311078580",
    url: "https://opendata.maryland.gov/Business-and-Economy/Maryland-Real-Property-Assessments_Hidden-Property/ed4q-f8tm",
  },
  {
    sourceId: "us-md-mdp-parcel-points",
    jurisdiction: "24037",
    kind: "parcel_feature",
    nativeId: "OBJECTID%3A42",
    url: "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0",
  },
  ...[
    ["us-md-mdp-parcel-downloads", "parcels-2026-02"],
    ["us-md-mdp-cama-downloads", "cama-2026-q1-statewide"],
    ["us-md-mdp-property-sales-downloads", "sales-2026-02"],
  ].map(([sourceId, nativeId]) => ({
    sourceId,
    jurisdiction: "24",
    kind: "bulk_release",
    nativeId,
    url: "https://planning.maryland.gov/MSDC/Pages/9_gam/district-download-gis-files.aspx",
  })),
  {
    sourceId: "us-md-land-records",
    jurisdiction: "24005",
    kind: "instrument",
    nativeId: "LIBER-123/FOLIO-456",
    url: "https://mdlandrec.net/",
  },
  {
    sourceId: "us-md-local-finance-tax-liens",
    jurisdiction: "24005",
    kind: "tax_account",
    nativeId: "ACCOUNT-1",
    url: "https://www.mdcourts.gov/legalhelp/landrecords",
  },
  {
    sourceId: "us-md-plats",
    jurisdiction: "24031",
    kind: "recorded-plat",
    nativeId: "MO%3AC1136-1",
    url: "https://plats.msa.maryland.gov/pages/index.aspx",
  },
  {
    sourceId: "us-md-sdat-real-property",
    jurisdiction: "24005",
    kind: "parcel",
    nativeId: "04030311078580",
    url: "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx",
  },
  {
    sourceId: "us-ny-statewide-parcels",
    jurisdiction: "36001",
    kind: "parcel",
    nativeId: "01010004100000021270000000",
    url: "https://gis.ny.gov/parcels",
  },
  {
    sourceId: "us-ny-statewide-parcels-bulk",
    jurisdiction: "36",
    kind: "release",
    nativeId: "2025-centroids",
    url: "https://gis.ny.gov/parcels",
  },
  {
    sourceId: "us-ny-orpts-sales-web",
    jurisdiction: "36001",
    kind: "property_sale",
    nativeId: "2047101021",
    url: "https://www.tax.ny.gov/research/property/assess/sales/salesweb.htm",
  },
  {
    sourceId: "us-ny-county-parcel-resource-directory",
    jurisdiction: "36027",
    kind: "county_route",
    nativeId: "Dutchess",
    url: "https://gis.ny.gov/parcels",
  },
  {
    sourceId: "us-ny-ogs-land-records",
    jurisdiction: "36",
    kind: "land_record",
    nativeId: "STATE-LAND-1",
    url: "https://ogs.ny.gov/real-estate/land-records-and-maps",
  },
  {
    sourceId: "us-ny-richmond-county-clerk-land-documents",
    jurisdiction: "36085",
    kind: "instrument",
    nativeId: "RICHMOND-1",
    url: "https://richmondcountyclerk.com/Search/SearchIndex",
  },
  {
    sourceId: "us-ny-assessment-coordinate-lookup",
    jurisdiction: "36",
    kind: "coordinate_lookup",
    nativeId: "-73.868%2C42.721",
    url: "https://gisservices.its.ny.gov/arcgis/rest/services/NYSTaxAssessmentLookup/GPServer/TaxAssessment",
  },
  {
    sourceId: "us-nyc-acris",
    jurisdiction: "36061",
    kind: "instrument",
    nativeId: "2017021700466001",
    url: "https://www.nyc.gov/site/finance/property/acris.page",
  },
  {
    sourceId: "us-nyc-property-information-portal",
    jurisdiction: "36061",
    kind: "parcel",
    nativeId: "1013860010",
    url: "https://propertyinformationportal.nyc.gov/",
  },
  {
    sourceId: "us-nyc-acris-images",
    jurisdiction: "36061",
    kind: "document_image",
    nativeId: "2017021700466001",
    url: "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentImageView",
  },
  {
    sourceId: "us-la-ebr-property",
    jurisdiction: "22033",
    kind: "parcel",
    nativeId: "030-7623-7",
    url: "https://data.brla.gov/",
  },
  {
    sourceId: "us-fl-palm-beach-official-records",
    jurisdiction: "12099",
    kind: "instrument",
    nativeId: "19860255822",
    url: "https://erec.mypalmbeachclerk.com/",
  },
  {
    sourceId: "us-fl-palm-beach-official-records-daily-index",
    jurisdiction: "12099",
    kind: "bulk_release",
    nativeId: "2026-07-30",
    url: "https://www.mypalmbeachclerk.com/records/official-records/electronic-distribution-index-service",
  },
  {
    sourceId: "us-fl-palm-beach-official-records-cd-archive",
    jurisdiction: "12099",
    kind: "bulk_archive",
    nativeId: "1968-present",
    url: "https://www.mypalmbeachclerk.com/records/official-records/official-record-index-and-images-on-cd-rom",
  },
  {
    sourceId: "us-fl-palm-beach-property-appraiser",
    jurisdiction: "12099",
    kind: "parcel",
    nativeId: "00424411190010180",
    url: "https://gis.pbcgov.org/arcgis/rest/services/Parcels/PARCEL_INFO/FeatureServer/4",
  },
  {
    sourceId: "us-fl-palm-beach-tax-collector",
    jurisdiction: "12099",
    kind: "tax_account",
    nativeId: "00424411190010180",
    url: "https://www.pbctax.gov/propertytax/",
  },
  {
    sourceId: "us-fl-palm-beach-tax-deeds",
    jurisdiction: "12099",
    kind: "tax_deed_case",
    nativeId: "43079",
    url: "https://taxdeed.mypalmbeachclerk.com/Home/",
  },
  {
    sourceId: "us-la-orleans-property-viewer",
    jurisdiction: "22071",
    kind: "parcel",
    nativeId: "TAXBILLID-EXAMPLE",
    url: "https://property.nola.gov/",
  },
  {
    sourceId: "us-or-lincoln-propertyweb",
    jurisdiction: "41041",
    kind: "property_account",
    nativeId: "R452940",
    url: "https://propertyweb.co.lincoln.or.us/Home",
  },
  {
    sourceId: "us-or-lincoln-county-taxlots-wfs",
    jurisdiction: "41041",
    kind: "taxlot_owner_geometry",
    nativeId: "42750936",
    url: "https://maps.co.lincoln.or.us/",
  },
  {
    sourceId: "us-or-lincoln-helion-recorder",
    jurisdiction: "41041",
    kind: "instrument",
    nativeId: "2025-001695",
    url: "https://helion.co.lincoln.or.us/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-yamhill-county-ascendweb-property",
    jurisdiction: "41071",
    kind: "property_account",
    nativeId: "41270",
    url: "https://ascendweb.co.yamhill.or.us/AcsendWeb/",
  },
  {
    sourceId: "us-or-yamhill-county-at-taxlots",
    jurisdiction: "41071",
    kind: "current_assessment_taxlot",
    nativeId: "5144427",
    url: "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/AT_Taxlots/FeatureServer/1",
  },
  {
    sourceId: "us-or-yamhill-county-retired-taxlots",
    jurisdiction: "41071",
    kind: "retired_assessment_taxlot",
    nativeId: "1",
    url: "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/ConnectExplorer_Taxlots/FeatureServer/3",
  },
  {
    sourceId: "us-or-yamhill-county-assessment-permits",
    jurisdiction: "41071",
    kind: "assessment_permit",
    nativeId: "979-25-001787-ELEC",
    url: "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/2026_Permits/FeatureServer/1",
  },
  {
    sourceId: "us-or-yamhill-helion-recorder",
    jurisdiction: "41071",
    kind: "instrument",
    nativeId: "2026-003177",
    url: "https://clerkwebapp.co.yamhill.or.us/DigitalResearchRoom/",
  },
  {
    sourceId: "us-or-clackamas-county-ascendweb-property",
    jurisdiction: "41005",
    kind: "property_account",
    nativeId: "01092276",
    url: "https://ascendweb.clackamas.us/",
  },
  {
    sourceId: "us-or-clackamas-county-cmap-taxlots",
    jurisdiction: "41005",
    kind: "current_assessment_taxlot",
    nativeId: "109341",
    url: "https://services3.arcgis.com/I2eWXOndpF9m8oKC/ArcGIS/rest/services/Taxlots_CMap/FeatureServer/0",
  },
  {
    sourceId: "us-or-wasco-county-ascendweb-property",
    jurisdiction: "41065",
    kind: "property_account",
    nativeId: "9450",
    url: "https://public.co.wasco.or.us/webtax/",
  },
  {
    sourceId: "us-or-wasco-county-taxlots",
    jurisdiction: "41065",
    kind: "county_taxlot",
    nativeId: "6575814",
    url: "https://public.co.wasco.or.us/gisserver/rest/services/Taxlots/FeatureServer/0",
  },
  ...[
    ["us-or-wasco-county-surveyor-road-records", "47"],
    ["us-or-wasco-county-surveyor-file-cabinet-surveys", "48"],
    ["us-or-wasco-county-surveyor-roll-maps", "50"],
    ["us-or-wasco-county-surveyor-commissioner-records", "52"],
    ["us-or-wasco-county-surveyor-land-corners", "53"],
    ["us-or-wasco-county-surveyor-plats", "54"],
    ["us-or-wasco-county-surveyor-subdivisions", "55"],
    ["us-or-wasco-county-surveyor-survey-book", "56"],
  ].map(([sourceId, layer]) => ({
    sourceId,
    jurisdiction: "41065",
    kind: "survey_reference",
    nativeId: "1",
    url: `https://public.co.wasco.or.us/gisserver/rest/services/SurveyorData/FeatureServer/${layer}`,
  })),
  {
    sourceId: "us-or-washington-county-casefiles",
    jurisdiction: "41067",
    kind: "planning_casefile",
    nativeId: "L2500106",
    url: "https://webapps.washingtoncountyor.gov/casefile-report/",
  },
  {
    sourceId: "us-or-washington-county-taxlot-project-activity",
    jurisdiction: "41067",
    kind: "taxlot_activity",
    nativeId: "2N2330002700",
    url: "https://webapps.washingtoncountyor.gov/permits/",
  },
  {
    sourceId: "us-or-washington-county-building-permits",
    jurisdiction: "41067",
    kind: "building_permit",
    nativeId: "05214429",
    url: "https://webapps.washingtoncountyor.gov/bps/",
  },
  {
    sourceId: "us-or-washington-county-permit-reports",
    jurisdiction: "41067",
    kind: "permit_report",
    nativeId: "HR25-0008",
    url: "https://webapps.washingtoncountyor.gov/project-report/",
  },
  {
    sourceId: "us-or-washington-county-accela-current-planning",
    jurisdiction: "41067",
    kind: "current_planning_record",
    nativeId: "25PLN-00000-00371",
    url: "https://permits.washingtoncountyor.gov/CitizenAccess/",
  },
  {
    sourceId: "us-or-washington-county-land-use-document-routes",
    jurisdiction: "41067",
    kind: "casefile_document_routes",
    nativeId: "L2500106",
    url: "https://www.washingtoncountyor.gov/current-planning/development-applications-progress",
  },
  {
    sourceId: "us-or-washington-county-survey-explorer-api",
    jurisdiction: "41067",
    kind: "survey_reference",
    nativeId: "35242",
    url: "https://webapps.washingtoncountyor.gov/surveyexplorer/",
  },
  {
    sourceId: "us-or-washington-county-survey-explorer-arcgis",
    jurisdiction: "41067",
    kind: "survey_geometry",
    nativeId: "35242",
    url: "https://gispub.co.washington.or.us/server/rest/services/LUT_ETS/Survey_Explorer/MapServer",
  },
  {
    sourceId: "us-or-washington-county-taxlots",
    jurisdiction: "41067",
    kind: "taxlot_geometry",
    nativeId: "2N2330002700",
    url: "https://gispub.co.washington.or.us/server/rest/services/Washington_County_Taxlots/FeatureServer/0",
  },
  {
    sourceId: "us-or-washington-county-situs-addresses",
    jurisdiction: "41067",
    kind: "situs_address",
    nativeId: "2N2330002700",
    url: "https://gispub.co.washington.or.us/server/rest/services/Intermap/Situs_address_WMAS/MapServer/0",
  },
  {
    sourceId: "us-or-washington-county-intermap-property",
    jurisdiction: "41067",
    kind: "assessment_report",
    nativeId: "2N2330002700",
    url: "https://gisims.co.washington.or.us/GIS/index.cfm",
  },
  {
    sourceId: "us-or-washington-county-washcotax",
    jurisdiction: "41067",
    kind: "property_tax_account",
    nativeId: "R2069997",
    url: "https://washcotax.co.washington.or.us",
  },
  {
    sourceId: "us-dc-itspe-property-lineage",
    jurisdiction: "11",
    kind: "property_lineage",
    nativeId: "DC-SSL-LINEAGE",
    url: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land/MapServer",
  },
  {
    sourceId: "us-dc-itspe-public-extract",
    jurisdiction: "11",
    kind: "assessment_tax_account",
    nativeId: "PAR-01300036",
    url: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land/MapServer/53",
  },
  {
    sourceId: "us-dc-common-ownership-polygons",
    jurisdiction: "11",
    kind: "common_ownership_polygon",
    nativeId: "4D65CD69-DE47-4E51-BECE-9BF1DDA701E8",
    url: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land/MapServer/40",
  },
  {
    sourceId: "us-dc-cama-property-sales",
    jurisdiction: "11",
    kind: "property_sale",
    nativeId: "420252",
    url: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land/MapServer/57",
  },
  {
    sourceId: "us-dc-surveyor-document-system",
    jurisdiction: "11",
    kind: "survey_document",
    nativeId: "9B59CB35-62CB-C473-B297-59097C200000",
    url: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land/MapServer/69",
  },
  {
    sourceId: "us-dc-recorder-of-deeds-public-records",
    jurisdiction: "11",
    kind: "recorded_instrument",
    nativeId: "2023000123",
    url: "https://washington.dc.publicsearch.us/",
  },
  {
    sourceId: "us-wa-state-archives-digital-recorded-land",
    jurisdiction: "53001",
    kind: "recorded_instrument",
    nativeId: "64742C2528B8C19D43FCC54D20DC97D0",
    url: "https://digitalarchives.wa.gov/Collections",
  },
  {
    sourceId: "us-wa-mason-county-tax-parcels-gis",
    jurisdiction: "53045",
    kind: "parcel_feature",
    nativeId: "FID%3A0",
    url: "https://gis.masoncountywa.gov/arcgis/rest/services/MasonCoSite/TaxParcels/MapServer/0",
  },
  {
    sourceId: "us-wa-state-parcels-normalized",
    jurisdiction: "53",
    kind: "parcel_lineage",
    nativeId: "001-2038010000001",
    url: "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer",
  },
  {
    sourceId: "us-wa-current-parcels-ecology",
    jurisdiction: "53001",
    kind: "parcel",
    nativeId: "001-2038010000001",
    url: "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer/0",
  },
  {
    sourceId: "us-wa-current-parcels-dnr",
    jurisdiction: "53001",
    kind: "parcel",
    nativeId: "001-2038010000001",
    url: "https://gis.dnr.wa.gov/site2/rest/services/Public_Forest_Practices/WADNR_PUBLIC_OCIO_Parcels/MapServer/0",
  },
  {
    sourceId: "us-wa-current-parcels-wisaard",
    jurisdiction: "53001",
    kind: "parcel_parity",
    nativeId: "001-2038010000001",
    url: "https://wisaard.dahp.wa.gov/server/rest/services/County_Parcels/MapServer/0",
  },
  {
    sourceId: "us-wa-current-parcels-county-freshness",
    jurisdiction: "53001",
    kind: "county_freshness",
    nativeId: "53001",
    url: "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer/1",
  },
  {
    sourceId: "us-wa-current-parcels-county-land-use",
    jurisdiction: "53001",
    kind: "county_land_use",
    nativeId: "53001-R",
    url: "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer/2",
  },
  ...[
    [
      "us-or-multnomah-sail-tax-parcels",
      "parcel",
      "R330254",
      "Multnomah_County_Taxlot_Parcels",
    ],
    [
      "us-or-multnomah-sail-survey-records",
      "survey_record",
      "7220",
      "SAIL_Survey_Records",
    ],
    [
      "us-or-multnomah-sail-subdivision-plats",
      "subdivision_plat",
      "1",
      "SAIL_Subdivision_Plat",
    ],
    [
      "us-or-multnomah-sail-partition-plats",
      "partition_plat",
      "1",
      "SAIL_Partition_Plat",
    ],
    [
      "us-or-multnomah-sail-condominium-plats",
      "condominium_plat",
      "1",
      "SAIL_Condominium_Plat",
    ],
    [
      "us-or-multnomah-sail-road-surveys",
      "road_survey",
      "1",
      "SAIL_Road_Survey",
    ],
    [
      "us-or-multnomah-sail-bearing-tree-public-land-corners",
      "land_corner",
      "1",
      "SAIL_Bearing_Tree_Public_Land_Corner",
    ],
    [
      "us-or-multnomah-sail-field-book-quarter-sheets",
      "field_book",
      "1",
      "SAIL_Field_Book_Quarter_Sheets",
    ],
  ].map(([sourceId, kind, nativeId, serviceName]) => ({
    sourceId,
    jurisdiction: "41051",
    kind,
    nativeId,
    url: `https://services5.arcgis.com/x7DNZL1YqNQVNykA/ArcGIS/rest/services/${serviceName}/FeatureServer/0`,
  })),
  {
    sourceId: "us-ca-los-angeles-county-assessor-parcels",
    jurisdiction: "06037",
    kind: "parcel",
    nativeId: "AIN-EXAMPLE",
    url: "https://portal.assessor.lacounty.gov/",
  },
  {
    sourceId: "us-ca-los-angeles-county-ttc-payment-history",
    jurisdiction: "06037",
    kind: "tax-payment",
    nativeId: "2004001003%3A7",
    url: "https://ttc.lacounty.gov/property-tax-payment-history/",
  },
  {
    sourceId: "us-ca-los-angeles-county-ttc-tax-sale",
    jurisdiction: "06037",
    kind: "tax-sale-result",
    nativeId: "2025B%3Afollow_up%3A1520%3A2004001003",
    url: "https://ttc.lacounty.gov/schedule-of-upcoming-auctions/",
  },
  {
    sourceId: "us-ca-los-angeles-registrar-recorder-real-estate",
    jurisdiction: "06037",
    kind: "instrument",
    nativeId: "RECORDING-DOCUMENT-EXAMPLE",
    url: "https://www.lavote.gov/home/recorder/real-estate-records/general-info",
  },
  {
    sourceId: "us-tx-bexar-bcad-property",
    jurisdiction: "48029",
    kind: "parcel",
    nativeId: "612115",
    url: "https://bcad.org/",
  },
  {
    sourceId: "us-tx-comptroller-epts",
    jurisdiction: "48",
    kind: "reported-property-transaction",
    nativeId: "artifact-row-occurrence",
    url: "https://comptroller.texas.gov/taxes/property-tax/data-submissions.php",
  },
  {
    sourceId: "us-tx-reeves-county-clerk-official-records",
    jurisdiction: "48389",
    kind: "instrument",
    nativeId: "RP%3A20798096",
    url: "https://reeves.tx.publicsearch.us/",
  },
  {
    sourceId: "us-pa-dep-parcels",
    jurisdiction: "42",
    kind: "parcel",
    nativeId: "DEP-PARCEL-1",
    url: "https://gis.dep.pa.gov/depgisprd/rest/services/Parcels/PA_Parcels/MapServer/0",
  },
  {
    sourceId: "us-pa-pasda-parcels",
    jurisdiction: "42",
    kind: "parcel",
    nativeId: "PASDA-PARCEL-1",
    url: "https://maps.pasda.psu.edu/ArcGIS/rest/services/PA_Parcels/MapServer/1",
  },
  {
    sourceId: "us-pa-philadelphia-property-data",
    jurisdiction: "42101",
    kind: "parcel",
    nativeId: "PHL-PARCEL-1",
    url: "https://opendataphilly.org/datasets/philadelphia-properties-and-assessment-history/",
  },
  {
    sourceId: "us-pa-philadelphia-opa-properties",
    jurisdiction: "42101",
    kind: "parcel",
    nativeId: "341086700",
    url: "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/OPA_PROPERTIES_PUBLIC/FeatureServer/0",
  },
  {
    sourceId: "us-pa-philadelphia-opa-current-bulk",
    jurisdiction: "42101",
    kind: "parcel",
    nativeId: "341086700",
    url: "https://opendata-downloads.s3.amazonaws.com/opa_properties_public.csv",
  },
  {
    sourceId: "us-pa-philadelphia-opa-carto-mirror",
    jurisdiction: "42101",
    kind: "parcel",
    nativeId: "341086700",
    url: "https://phl.carto.com/api/v2/sql?filename=opa_properties_public&format=geojson&q=SELECT%20*%20FROM%20opa_properties_public",
  },
  {
    sourceId: "us-pa-philadelphia-opa-assessment-history",
    jurisdiction: "42101",
    kind: "parcel-assessment",
    nativeId: "341086700%3A2023",
    url: "https://phl.carto.com/api/v2/sql",
  },
  {
    sourceId: "us-pa-philadelphia-opa-history-bulk",
    jurisdiction: "42101",
    kind: "parcel-assessment",
    nativeId: "341086700%3A2023",
    url: "https://opendata-downloads.s3.amazonaws.com/assessments.csv",
  },
  {
    sourceId: "us-pa-philadelphia-dor-parcels",
    jurisdiction: "42101",
    kind: "registry",
    nativeId: "062N200131",
    url: "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/DOR_Parcel/FeatureServer/0",
  },
  {
    sourceId: "us-pa-philadelphia-atlas",
    jurisdiction: "42101",
    kind: "property",
    nativeId: "341086700",
    url: "https://atlas.phila.gov/",
  },
  {
    sourceId: "us-pa-philadelphia-philadox",
    jurisdiction: "42101",
    kind: "instrument",
    nativeId: "062N200131",
    url: "https://epayss.phila-records.com/",
  },
  {
    sourceId: "us-pa-philadelphia-records-and-archives",
    jurisdiction: "42101",
    kind: "instrument",
    nativeId: "062N200131",
    url: "https://www.phila.gov/services/property-lots-housing/get-a-copy-of-a-deed-or-other-recorded-document/",
  },
  {
    sourceId: "us-pa-philadelphia-property-application",
    jurisdiction: "42101",
    kind: "parcel",
    nativeId: "341086700",
    url: "https://property.phila.gov/",
  },
  {
    sourceId: "us-pa-allegheny-property-feeds",
    jurisdiction: "42003",
    kind: "parcel",
    nativeId: "ALLEGHENY-PARCEL-1",
    url: "https://data.wprdc.org/en/dataset/property-assessments",
  },
  {
    sourceId: "us-pa-county-recorder-and-court-routing",
    jurisdiction: "42",
    kind: "directory",
    nativeId: "COUNTY-ROUTING",
    url: "https://www.pacourts.us/courts/courts-of-common-pleas/prothonotaries",
  },
  {
    sourceId: "us-de-firstmap-parcels",
    jurisdiction: "10",
    kind: "parcel",
    nativeId: "FIRSTMAP-PARCEL-1",
    url: "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/PlanningCadastre/DE_StateParcels/FeatureServer/0",
  },
  {
    sourceId: "us-de-kent-parcels",
    jurisdiction: "10001",
    kind: "parcel",
    nativeId: "KENT-PARCEL-1",
    url: "https://gis.kentcountyde.gov/server/rest/services/Parcels/Parcels/MapServer/0",
  },
  {
    sourceId: "us-de-sussex-parcels",
    jurisdiction: "10005",
    kind: "parcel",
    nativeId: "SUSSEX-PARCEL-1",
    url: "https://map.sussexcountyde.gov/trdserver/rest/services/Geographic_Information_Office/Parcels_PIN_With_Assessment_Unit/FeatureServer",
  },
  {
    sourceId: "us-de-new-castle-parcel-search",
    jurisdiction: "10003",
    kind: "parcel",
    nativeId: "NEW-CASTLE-PARCEL-1",
    url: "https://www3.newcastlede.gov/parcel/search/",
  },
  {
    sourceId: "us-de-kent-recorder-i2",
    jurisdiction: "10001",
    kind: "instrument",
    nativeId: "KENT-I2-1",
    url: "https://i2g.uslandrecords.com/DE/Kent2/D/Default.aspx",
  },
  {
    sourceId: "us-de-sussex-recorder-landmark",
    jurisdiction: "10005",
    kind: "instrument",
    nativeId: "SUSSEX-LANDMARK-1",
    url: "https://deeds.sussexcountyde.gov/LandmarkWeb/home/index",
  },
  {
    sourceId: "us-de-new-castle-recorder-index",
    jurisdiction: "10003",
    kind: "instrument",
    nativeId: "NEW-CASTLE-INDEX-1",
    url: "https://www.newcastlede.gov/144/Document-Search",
  },
  {
    sourceId: "us-de-new-castle-recorder-pax",
    jurisdiction: "10003",
    kind: "document_image",
    nativeId: "NEW-CASTLE-PAX-1",
    url: "https://www.newcastlede.gov/144/Document-Search",
  },
  {
    sourceId: "us-pa-berks-recorder-publicsearch",
    jurisdiction: "42011",
    kind: "instrument",
    nativeId: "RP%3A203097905",
    url: "https://berks.pa.publicsearch.us/",
  },
  {
    sourceId: "us-pa-delaware-recorder-publicsearch",
    jurisdiction: "42045",
    kind: "instrument",
    nativeId: "RP%3A187146913",
    url: "https://delaware.pa.publicsearch.us/",
  },
  {
    sourceId: "us-pa-indiana-recorder-publicsearch",
    jurisdiction: "42063",
    kind: "instrument",
    nativeId: "RP%3A133236252",
    url: "https://indiana.pa.publicsearch.us/",
  },
  {
    sourceId: "us-pa-lawrence-recorder-publicsearch",
    jurisdiction: "42073",
    kind: "instrument",
    nativeId: "RP%3A104759101",
    url: "https://lawrence.pa.publicsearch.us/",
  },
  {
    sourceId: "us-de-kent-recorder-publicsearch",
    jurisdiction: "10001",
    kind: "instrument",
    nativeId: "RP%3A36619563",
    url: "https://kent.de.ds.search.govos.com/",
  },
  {
    sourceId: "us-co-denver-recorder-publicsearch",
    jurisdiction: "08031",
    kind: "instrument",
    nativeId: "RP%3A293353911",
    url: "https://denver.co.publicsearch.us/",
  },
  {
    sourceId: "us-co-denver-parcels",
    jurisdiction: "08031",
    kind: "parcel",
    nativeId: "0017103008000",
    url: "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_PROP_PARCELS_A/FeatureServer/245",
  },
  {
    sourceId: "us-co-denver-public-trustee-gts",
    jurisdiction: "08031",
    kind: "foreclosure",
    nativeId: "2026-000418",
    url: "https://denvergov.org/foreclosuresearch/default?AspxAutoDetectCookieSupport=1",
  },
  {
    sourceId: "us-co-denver-delinquent-real-property-tax-list",
    jurisdiction: "08031",
    kind: "tax_delinquency",
    nativeId: "2024-0017103008000",
    url: "https://www.denvergov.org/Government/Agencies-Departments-Offices/Agencies-Departments-Offices-Directory/Department-of-Finance/Our-Divisions/Treasury/Property-Taxes/Real-Estate-Delinquent-Taxes-and-Tax-Lien-Sale",
  },
  {
    sourceId: "us-co-denver-spatialest-property-tax",
    jurisdiction: "08031",
    kind: "tax_account",
    nativeId: "0017103008000",
    url: "https://property.spatialest.com/co/denver",
  },
  {
    sourceId: "us-co-denver-tax-lien-auction",
    jurisdiction: "08031",
    kind: "tax_lien_sale",
    nativeId: "2024-0017103008000",
    url: "https://denver.coloradotaxsale.com/",
  },
  {
    sourceId: "us-co-denver-realforeclose-auctions",
    jurisdiction: "08031",
    kind: "foreclosure_auction",
    nativeId: "2026-000418",
    url: "https://www.denver.realforeclose.com/",
  },
  {
    sourceId: "us-tx-reeves-clerk-bulk-images",
    jurisdiction: "48389",
    kind: "bulk_release",
    nativeId: "2026-07",
    url: "https://www.reevescounty.org/departments/county-clerk",
  },
  {
    sourceId: "us-tx-culberson-clerk-historical-deeds",
    jurisdiction: "48109",
    kind: "recorded_instrument",
    nativeId: "DEED-178-42",
    url: "https://kofilequicklinks.com/culberson/",
  },
  {
    sourceId: "us-tx-culberson-clerk-records-request",
    jurisdiction: "48109",
    kind: "instrument_request",
    nativeId: "REQUEST-1",
    url: "https://www.co.culberson.tx.us/page/culberson.County.Clerk",
  },
  {
    sourceId: "us-tx-sos-ucc-portal",
    jurisdiction: "48",
    kind: "ucc_filing",
    nativeId: "UCC-1",
    url: "https://webservices.sos.state.tx.us/",
  },
  {
    sourceId: "us-tx-sos-ucc-bulk",
    jurisdiction: "48",
    kind: "bulk_release",
    nativeId: "MASTER-2026-07",
    url: "https://www.sos.state.tx.us/ucc/bulk-order-file-layouts.shtml",
  },
  {
    sourceId: "us-tx-rrc-p4-bulk",
    jurisdiction: "48",
    kind: "operator_history",
    nativeId: "08-12345-1",
    url: "https://mft.rrc.texas.gov/link/19f9b9c7-2b82-4d7c-8dbd-77145a86d3de",
  },
  {
    sourceId: "us-tx-rrc-p5-bulk",
    jurisdiction: "48",
    kind: "organization",
    nativeId: "P5-12345",
    url: "https://mft.rrc.texas.gov/link/04652169-eed6-4396-9019-2e270e790f6c",
  },
  {
    sourceId: "us-tx-rrc-wellbore-bulk",
    jurisdiction: "48",
    kind: "well",
    nativeId: "API-42-389-12345",
    url: "https://mft.rrc.texas.gov/link/650649b7-e019-4d77-a8e0-d118d6455381",
  },
  {
    sourceId: "us-tx-harris-clerk-real-property",
    jurisdiction: "48201",
    kind: "instrument",
    nativeId: "RP-2026-42",
    url: "https://www.cclerk.hctx.net/PublicRecords.aspx",
  },
  {
    sourceId: "us-tx-harris-clerk-foreclosures",
    jurisdiction: "48201",
    kind: "foreclosure_notice",
    nativeId: "FRCL-2026-4797",
    url: "https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx",
  },
  {
    sourceId: "us-tx-harris-hcad-property",
    jurisdiction: "48201",
    kind: "bulk_release",
    nativeId: "2026-Real_acct_owner.zip",
    url: "https://hcad.org/pdata/pdata-property-downloads.html/",
  },
  {
    sourceId: "us-tx-harris-hcad-gis",
    jurisdiction: "48201",
    kind: "parcel",
    nativeId: "1144740190749",
    url: "https://hcad.org/pdata/pdata-gis-downloads.html/",
  },
  {
    sourceId: "us-tx-txgio-land-parcels",
    jurisdiction: "48",
    kind: "bulk_release",
    nativeId: "0fa04328-872e-481c-b453-126a74777593",
    url: "https://gio.texas.gov/stratmap/land-parcels.html",
  },
  {
    sourceId: "us-or-deschutes-county-taxlots",
    jurisdiction: "41017",
    kind: "parcel",
    nativeId: "141031B000700",
    url: "https://services1.arcgis.com/znO8Hz1SuVVohYhZ/arcgis/rest/services/Taxlots/FeatureServer",
  },
  {
    sourceId: "us-or-deschutes-cdd-weblink",
    jurisdiction: "41017",
    kind: "document",
    nativeId: "1383062",
    url: "https://weblink.deschutes.org/CDD/",
  },
  {
    sourceId: "us-or-deschutes-dial-property",
    jurisdiction: "41017",
    kind: "account",
    nativeId: "135278",
    url: "http://dial.deschutes.org/",
  },
  {
    sourceId: "us-or-umatilla-helion-recorder",
    jurisdiction: "41059",
    kind: "instrument",
    nativeId: "2026-000001",
    url: "https://public.co.umatilla.or.us/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-wasco-helion-recorder",
    jurisdiction: "41065",
    kind: "instrument",
    nativeId: "2023-002123",
    url: "https://public.co.wasco.or.us/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-crook-helion-recorder",
    jurisdiction: "41013",
    kind: "instrument",
    nativeId: "county-index",
    url: "https://clerk.crookcountyor.gov/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-benton-helion-recorder",
    jurisdiction: "41003",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://records.co.benton.or.us/",
  },
  {
    sourceId: "us-or-benton-county-taxlot-owners",
    jurisdiction: "41003",
    kind: "taxlot_owner_party",
    nativeId: "107939",
    url: "https://gis.co.benton.or.us/arcgis/rest/services/Public/TaxlotOwners/MapServer/0",
  },
  {
    sourceId: "us-or-benton-county-assessment-bulk",
    jurisdiction: "41003",
    kind: "bulk_release",
    nativeId: "fixture-release",
    url: "https://gis.co.benton.or.us/gisdata/Assessment/",
  },
  {
    sourceId: "us-or-benton-county-assessment-maps",
    jurisdiction: "41003",
    kind: "assessment_map",
    nativeId: "11513A.pdf",
    url: "https://gis.co.benton.or.us/gisdata/Assessment/AssessmentMapsPDF/",
  },
  {
    sourceId: "us-or-deschutes-helion-recorder",
    jurisdiction: "41017",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://recordings.deschutes.org/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-hood-river-helion-recorder",
    jurisdiction: "41027",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://records.co.hood-river.or.us/DigitalResearchRoom/",
  },
  {
    sourceId: "us-or-jackson-helion-recorder",
    jurisdiction: "41029",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://apps.jacksoncountyor.gov/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-jackson-county-assessor-taxlots",
    jurisdiction: "41029",
    kind: "parcel",
    nativeId: "30-2E-100",
    url: "https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Taxlots/FeatureServer/2",
  },
  {
    sourceId: "us-or-douglas-county-assessor-parcels",
    jurisdiction: "41019",
    kind: "parcel",
    nativeId: "R12345",
    url: "https://gis.co.douglas.or.us/server/rest/services/Parcel/Parcels/FeatureServer/0",
  },
  {
    sourceId: "us-or-jackson-county-building-permits",
    jurisdiction: "41029",
    kind: "building_permit_observation",
    nativeId: "439-24-000123",
    url: "https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_Building/FeatureServer/1",
  },
  {
    sourceId: "us-or-jackson-county-accela-building-details",
    jurisdiction: "41029",
    kind: "building_permit_detail",
    nativeId: "26CAP-00000-006GM",
    url: "https://aca-oregon.accela.com/oregon/Cap/CapDetail.aspx",
  },
  {
    sourceId: "us-or-jackson-county-land-use-permits",
    jurisdiction: "41029",
    kind: "land_use_permit_observation",
    nativeId: "439-LU-000123",
    url: "https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_LandUse/FeatureServer/0",
  },
  {
    sourceId: "us-or-jackson-county-accela-planning-details",
    jurisdiction: "41029",
    kind: "land_use_permit_detail",
    nativeId: "14HIS-00000-03BD6",
    url: "https://aca-oregon.accela.com/oregon/Cap/CapDetail.aspx",
  },
  {
    sourceId: "us-or-jackson-county-code-compliance",
    jurisdiction: "41029",
    kind: "code_compliance_observation",
    nativeId: "VIOLATION-123",
    url: "https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_CodeCompliance/FeatureServer/2",
  },
  {
    sourceId: "us-or-jefferson-helion-recorder",
    jurisdiction: "41031",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://clerk.co.jefferson.or.us/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-multnomah-helion-recorder",
    jurisdiction: "41051",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://multcorecords.com/",
  },
  {
    sourceId: "us-or-polk-helion-recorder",
    jurisdiction: "41053",
    kind: "instrument",
    nativeId: "2026-000001",
    url: "https://apps2.co.polk.or.us/DigitalResearchRoom/",
  },
  {
    sourceId: "us-or-tillamook-helion-recorder",
    jurisdiction: "41057",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://query.co.tillamook.or.us/DigitalResearchRoomPublic/",
  },
  {
    sourceId: "us-or-wheeler-helion-recorder",
    jurisdiction: "41069",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://wheelercountyoregonrecords.com/DigitalResearchRoom/",
  },
  {
    sourceId: "us-or-clackamas-tax-foreclosure-publications",
    jurisdiction: "41005",
    kind: "tax-publication-event",
    nativeId: "auction-results",
    url: "https://www.clackamas.us/at/foreclosures",
  },
  {
    sourceId: "us-or-marion-tax-foreclosure-publications",
    jurisdiction: "41047",
    kind: "tax-publication-event",
    nativeId: "end-redemption-notice",
    url: "https://www.co.marion.or.us/AO/TAX/Pages/foreclosure.aspx",
  },
  {
    sourceId: "us-or-multnomah-tax-foreclosure-publications",
    jurisdiction: "41051",
    kind: "tax-publication-event",
    nativeId: "tax-title-inventory",
    url: "https://multco.us/info/property-tax-foreclosure",
  },
  {
    sourceId: "us-or-tillamook-tax-foreclosure-publications",
    jurisdiction: "41057",
    kind: "tax-publication-event",
    nativeId: "foreclosure-list",
    url: "https://www.tillamookcounty.gov/assessment/page/real-property-tax-foreclosure",
  },
  {
    sourceId: "us-or-lane-county-assessor-parcels",
    jurisdiction: "41039",
    kind: "parcel",
    nativeId: "1501000000100",
    url: "https://lcmaps.lanecounty.org/arcgis/rest/services/AT/AddressParcelSales/MapServer/2",
  },
  {
    sourceId: "us-or-lane-county-recent-property-sales",
    jurisdiction: "41039",
    kind: "sale_reference",
    nativeId: "2024-019914",
    url: "https://lcmaps.lanecounty.org/arcgis/rest/services/AT/AddressParcelSales/MapServer/1",
  },
  {
    sourceId: "us-or-lane-property-account-information",
    jurisdiction: "41039",
    kind: "property_account_detail",
    nativeId: "0057313",
    url: "https://apps.lanecounty.org/propertyaccountinformation/",
  },
  {
    sourceId: "us-or-lane-tax-maps",
    jurisdiction: "41039",
    kind: "tax_map_locator",
    nativeId: "1605070001100%3A326",
    url: "https://apps.lanecounty.org/TaxMap/Search.aspx",
  },
  {
    sourceId: "us-or-lane-tax-maps",
    jurisdiction: "41039",
    kind: "tax_map_document",
    nativeId: "326",
    url: "https://apps.lanecounty.org/TaxMap/Search.aspx",
  },
  {
    sourceId: "us-or-marion-county-assessor-parcels",
    jurisdiction: "41047",
    kind: "parcel",
    nativeId: "032W290000400",
    url: "https://services3.arcgis.com/SXXjryU22GsO8OEC/ArcGIS/rest/services/Parcels/FeatureServer/0",
  },
  {
    sourceId: "us-or-marion-sales-data",
    jurisdiction: "41047",
    kind: "bulk_release",
    nativeId: "2026-current-sales",
    url: "https://www.co.marion.or.us/AO/Pages/datacenter.aspx",
  },
  {
    sourceId: "us-or-marion-assessor-data-request",
    jurisdiction: "41047",
    kind: "request",
    nativeId: "custom-assessor-data",
    url: "https://apps.co.marion.or.us/AssessorDataRequest/",
  },
  {
    sourceId: "us-or-portland-regional-taxlots",
    jurisdiction: "41005",
    kind: "parcel",
    nativeId: "11E25BA23600",
    url: "https://www.portlandmaps.com/arcgis/rest/services/Public/Taxlots/MapServer/0",
  },
  {
    sourceId: "us-or-metro-rlis-public-taxlots",
    jurisdiction: "41051",
    kind: "parcel",
    nativeId: "21E35BB01800",
    url: "https://services2.arcgis.com/McQ0OlIABe29rJJy/arcgis/rest/services/Taxlots_(Public)/FeatureServer/3",
  },
  {
    sourceId: "us-or-owrd-public-tax-lots",
    jurisdiction: "41069",
    kind: "parcel",
    nativeId: "public-taxlot",
    url: "https://gis.wrd.state.or.us/server/rest/services/tax/Tax_Lots_Public_View_WGS84/FeatureServer/2",
  },
  {
    sourceId: "us-or-umatilla-helion-property",
    jurisdiction: "41059",
    kind: "parcel",
    nativeId: "ACCOUNT-1",
    url: "https://public.co.umatilla.or.us/pso/",
  },
  {
    sourceId: "us-or-morrow-helion-property",
    jurisdiction: "41049",
    kind: "parcel",
    nativeId: "2S2627-DA-02000",
    url: "https://records.morrowcountyor.gov/PSO/",
  },
  {
    sourceId: "us-or-polk-helion-property",
    jurisdiction: "41053",
    kind: "parcel",
    nativeId: "ACCOUNT-1",
    url: "https://apps2.co.polk.or.us/pso/",
  },
  {
    sourceId: "us-or-tillamook-helion-property",
    jurisdiction: "41057",
    kind: "parcel",
    nativeId: "ACCOUNT-1",
    url: "https://query.co.tillamook.or.us/PSO/",
  },
  {
    sourceId: "us-or-columbia-helion-property",
    jurisdiction: "41009",
    kind: "parcel",
    nativeId: "ACCOUNT-28102",
    url: "https://propertysearch.columbiacountyor.gov/PSO/",
  },
  {
    sourceId: "us-or-coos-helion-property",
    jurisdiction: "41011",
    kind: "parcel",
    nativeId: "ACCOUNT-1",
    url: "https://records.co.coos.or.us/PSO/",
  },
  {
    sourceId: "us-va-arlington-property-map",
    jurisdiction: "51013",
    kind: "parcel",
    nativeId: "03001009",
    url: "https://arlgis.arlingtonva.us/arcgis/rest/services/StaffMap/Property_Map_public/MapServer/3",
  },
  {
    sourceId: "us-va-vgin-parcels",
    jurisdiction: "51",
    kind: "parcel",
    nativeId: "VGIN-PARCEL-1",
    url: "https://www.arcgis.com/home/item.html?id=29627d7c051a47dc8ce71b4484531ab3",
  },
  {
    sourceId: "us-va-virginia-beach-delinquent-real-estate-taxes",
    jurisdiction: "51810",
    kind: "tax-delinquency",
    nativeId: "1125000027%3A2%3A14469645070000%3A2025",
    url: "https://data.virginiabeach.gov/datasets/1b2d03addfaa41bb83c17f9237e1504c_0/explore",
  },
  {
    sourceId: "us-va-vgin-parcels-bulk",
    jurisdiction: "51",
    kind: "release",
    nativeId: "29627d7c051a47dc8ce71b4484531ab3",
    url: "https://www.arcgis.com/sharing/rest/content/items/29627d7c051a47dc8ce71b4484531ab3/data",
  },
  {
    sourceId: "us-va-local-property-systems",
    jurisdiction: "51",
    kind: "directory",
    nativeId: "VA-LOCALITIES",
    url: "https://www.tax.virginia.gov/localities",
  },
  {
    sourceId: "us-va-arlington-land-records-publicsearch",
    jurisdiction: "51013",
    kind: "instrument",
    nativeId: "ARLINGTON-DEED-1",
    url: "https://arlington.va.publicsearch.us/",
  },
  {
    sourceId: "us-va-secure-remote-access-land-records",
    jurisdiction: "51",
    kind: "land_record",
    nativeId: "SRA-COURT-1",
    url: "https://risweb.vacourts.gov/jsra/sra/",
  },
  {
    sourceId: "us-wi-statewide-parcels",
    jurisdiction: "55001",
    kind: "parcel",
    nativeId: "001008015540000",
    url: "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/Wisconsin_Statewide_Parcels_DB/FeatureServer/0",
  },
  {
    sourceId: "us-wi-statewide-parcels-bulk",
    jurisdiction: "55",
    kind: "release",
    nativeId: "V12",
    url: "https://www.sco.wisc.edu/parcels/data/",
  },
  {
    sourceId: "us-wi-geodata",
    jurisdiction: "55",
    kind: "catalog",
    nativeId: "COUNTY-DATASET",
    url: "https://geodata.wisc.edu/",
  },
  {
    sourceId: "us-wi-county-land-record-directory",
    jurisdiction: "55",
    kind: "route",
    nativeId: "ADAMS",
    url: "https://doa.wi.gov/DIR/County_Contacts.pdf",
  },
  {
    sourceId: "us-wi-dor-retr",
    jurisdiction: "55",
    kind: "transfer",
    nativeId: "RETR-1",
    url: "https://tap.revenue.wi.gov/RETRSearch",
  },
  {
    sourceId: "us-wi-dor-retr-historical",
    jurisdiction: "55",
    kind: "release",
    nativeId: "HISTORICAL-1",
    url: "https://tap.revenue.wi.gov/RETRHistoric",
  },
  {
    sourceId: "us-wi-dor-parcel-number-formats",
    jurisdiction: "55",
    kind: "reference",
    nativeId: "FORMAT-1",
    url: "https://www.revenue.wi.gov/pages/ust/parcels.aspx",
  },
  {
    sourceId: "us-wi-statewide-parcel-map",
    jurisdiction: "55",
    kind: "map",
    nativeId: "MAP-1",
    url: "https://maps.sco.wisc.edu/Parcels/",
  },
  {
    sourceId: "us-nj-njgin-parcels-modiv",
    jurisdiction: "34013",
    kind: "parcel",
    nativeId: "0703_14_5",
    url: "https://www.nj.gov/njgin/edata/parcels/",
  },
  {
    sourceId: "us-nj-njgin-property-explorer",
    jurisdiction: "34",
    kind: "map",
    nativeId: "MAP-1",
    url: "https://newjersey.maps.arcgis.com/apps/webappviewer/index.html?id=3a4290e1b3d64094a8b8a127965ab43a",
  },
  {
    sourceId: "us-nj-njgin-parcels-modiv-bulk",
    jurisdiction: "34",
    kind: "release",
    nativeId: "STATEWIDE-1",
    url: "https://njogis-newjersey.opendata.arcgis.com/documents/newjersey::parcels-and-mod-iv-composite-of-nj-download/about",
  },
  {
    sourceId: "us-nj-njgin-parcels-only-bulk",
    jurisdiction: "34",
    kind: "release",
    nativeId: "PARCELS-ONLY-1",
    url: "https://njogis-newjersey.opendata.arcgis.com/documents/d543ddcc1e6844319ffa826fee52fccf/about",
  },
  {
    sourceId: "us-nj-njgin-modiv-tax-list",
    jurisdiction: "34",
    kind: "assessment",
    nativeId: "MODIV-1",
    url: "https://njogis-newjersey.opendata.arcgis.com/documents/property-tax-list-mod-iv-of-nj-fgdb-download/about",
  },
  {
    sourceId: "us-nj-treasury-modiv-files",
    jurisdiction: "34",
    kind: "release",
    nativeId: "2026",
    url: "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  },
  {
    sourceId: "us-nj-treasury-sr1a-sales",
    jurisdiction: "34",
    kind: "sale",
    nativeId: "SR1A-1",
    url: "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  },
  {
    sourceId: "us-nj-local-assessors-tax-boards",
    jurisdiction: "34",
    kind: "route",
    nativeId: "ASSESSOR-1",
    url: "https://www.nj.gov/treasury/taxation/pdf/lpt/assessor/statewidebycounty.pdf",
  },
  {
    sourceId: "us-nj-county-clerks-registers",
    jurisdiction: "34",
    kind: "instrument",
    nativeId: "DEED-1",
    url: "https://www.nj.gov/nj/gov/county/counties.shtml",
  },
  {
    sourceId: "us-nj-opra-property-records",
    jurisdiction: "34",
    kind: "request",
    nativeId: "REQUEST-1",
    url: "https://www.nj.gov/opra/home/request-records.shtml",
  },
  {
    sourceId: "us-nj-tax-court-property-cases",
    jurisdiction: "34",
    kind: "case",
    nativeId: "CASE-1",
    url: "https://www.njcourts.gov/courts/tax/docketed-cases",
  },
  {
    sourceId: "us-nj-local-property-assessment-sources",
    jurisdiction: "34",
    kind: "route",
    nativeId: "ASSESSMENT-CONTEXT",
    url: "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  },
  {
    sourceId: "us-nj-property-tax-appeals",
    jurisdiction: "34",
    kind: "statistics",
    nativeId: "2025",
    url: "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  },
  {
    sourceId: "us-nj-county-tax-boards",
    jurisdiction: "34",
    kind: "route",
    nativeId: "BERGEN",
    url: "https://www.nj.gov/treasury/taxation/pdf/lpt/CountyBoardsofTaxation.pdf",
  },
  {
    sourceId: "us-nj-dca-property-registration",
    jurisdiction: "34",
    kind: "registration",
    nativeId: "REGISTRATION-1",
    url: "https://serviceportal.dca.nj.gov/ultra-bhi-home/ultra-bhi-propertysearch/",
  },
  {
    sourceId: "us-nj-dca-bhi-active-buildings-opra",
    jurisdiction: "34",
    kind: "report",
    nativeId: "ACTIVE-BUILDINGS",
    url: "https://app.powerbigov.us/view?r=eyJrIjoiZmI2MzIxZDEtN2UwNi00M2VlLWJiZjgtNTMzMTExYjc3YzgyIiwidCI6IjUwNzZjM2QxLTM4MDItNGI5Zi1iMzZhLWUwYTQxYmQ2NDJhNyJ9",
  },
  {
    sourceId: "us-oh-ogrip-statewide-parcels",
    jurisdiction: "39049",
    kind: "parcel",
    nativeId: "39049-010-042534",
    url: "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/OhioStatewidePacels_full_view/FeatureServer/0",
  },
  {
    sourceId: "us-oh-franklin-county-auditor-property",
    jurisdiction: "39049",
    kind: "assessment_route",
    nativeId: "010-042534",
    url: "https://property.franklincountyauditor.com/",
  },
  {
    sourceId: "us-oh-franklin-county-auditor-bulk",
    jurisdiction: "39049",
    kind: "bulk_release",
    nativeId: "appraisal-2026-07-15",
    url: "https://auditor.franklincountyohio.gov/Auditor/FTP",
  },
  {
    sourceId: "us-oh-franklin-county-auditor-sales-gis",
    jurisdiction: "39049",
    kind: "assessor_sale",
    nativeId: "0A9D3B4A-060D-4B4F-A84B-DF332C586A1F",
    url: "https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/FeatureServer/0",
  },
  {
    sourceId: "us-oh-franklin-county-recorder-publicsearch",
    jurisdiction: "39049",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://franklin.oh.publicsearch.us/",
  },
  {
    sourceId: "us-oh-licking-county-auditor-gis",
    jurisdiction: "39089",
    kind: "parcel_feature",
    nativeId: "001-000006-01.000",
    url: "https://apps.lickingcounty.gov/maps/taxparcelviewer/default.html",
  },
  {
    sourceId: "us-oh-licking-county-auditor-ontrac",
    jurisdiction: "39089",
    kind: "assessment_route",
    nativeId: "source-route",
    url: "https://ontrac.lickingcounty.gov/",
  },
  {
    sourceId: "us-oh-licking-county-recorder-pax",
    jurisdiction: "39089",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://apps.lickingcounty.gov/recorder/paxworld/",
  },
  {
    sourceId: "us-oh-licking-county-recorder-instrument-detail",
    jurisdiction: "39089",
    kind: "instrument_detail",
    nativeId: "2026000123",
    url: "https://apps.lickingcounty.gov/recorder/record-search/",
  },
  {
    sourceId: "us-oh-licking-county-recorder-archives",
    jurisdiction: "39089",
    kind: "archive_route",
    nativeId: "deeds-1803-1918",
    url: "https://lickingcounty.gov/depts/records_n_archives/list_of_record_collections_by_department/recorder.htm",
  },
  {
    sourceId: "us-oh-delaware-county-auditor-property",
    jurisdiction: "39041",
    kind: "assessment_route",
    nativeId: "10010001001000",
    url: "https://delaware-auditor-ohio.manatron.com/",
  },
  {
    sourceId: "us-oh-delaware-county-auditor-gis",
    jurisdiction: "39041",
    kind: "parcel_map",
    nativeId: "10010001001000",
    url: "https://auditor.delco-gis.org/",
  },
  {
    sourceId: "us-oh-delaware-county-recorder-pax",
    jurisdiction: "39041",
    kind: "instrument_index",
    nativeId: "source-index",
    url: "https://delaware.dts-central-oh.com/PaxWorld/",
  },
];

for (const fixture of propertySourceFixtures) {
  run(`PROPERTY: ${fixture.sourceId} resolves to its official source`, () => {
    const ref = `PROPERTY:${fixture.sourceId}/${fixture.jurisdiction}/${fixture.kind}/${fixture.nativeId}`;
    const result = applyCitations(`Recorded [${ref}].`);
    assert.equal(result.entries.length, 1);
    assert.equal(result.entries[0].label, ref);
    assert.equal(result.entries[0].openUrl, fixture.url);
    assert.equal(result.entries[0].sourceKind, "external");
  });
}

run("PAX: Licking exact-instrument evidence deep-links without changing identity", () => {
  const ref = "PAX:39089:instrument:201310100025382";
  const result = applyCitations(`Recorded [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, ref);
  assert.equal(
    result.entries[0].url,
    "https://apps.lickingcounty.gov/recorder/record-search/?instrument=201310100025382",
  );
  assert.equal(result.entries[0].sourceType, "property_record");
});

run("PAXDOC: Licking public PDF evidence resolves to the official document", () => {
  const ref = "PAXDOC:39089:201310100025382:instrument";
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(
    links[0].url,
    "https://apps.lickingcounty.gov/recorder/record-search/document?instrument=201310100025382",
  );
});

run("PAX: Delaware evidence never persists a session or ticket locator", () => {
  const recordRef = "PAX:39041:reference:3824679";
  const documentRef = "PAXDOC:39041:202600019719:3824679";
  const result = applyCitations(
    `Detail [${recordRef}] and document [${documentRef}].`,
  );
  assert.equal(result.entries.length, 2);
  for (const entry of result.entries) {
    assert.equal(entry.url, "https://delaware.dts-central-oh.com/PaxWorld/");
    assert.doesNotMatch(entry.url ?? "", /session|ticket|3824679/i);
  }
});

run("PROPERTY: Lane tax-map locator and PDF retain distinct citations", () => {
  const locatorRef =
    "PROPERTY:us-or-lane-tax-maps/41039/tax_map_locator/1605070001100%3A326";
  const documentRef =
    "PROPERTY:us-or-lane-tax-maps/41039/tax_map_document/326";
  const result = applyCitations(
    `Locator [${locatorRef}] and document [${documentRef}].`,
  );
  assert.equal(result.entries.length, 2);
  assert.notEqual(result.entries[0].key, result.entries[1].key);
  assert.deepEqual(
    result.entries.map(entry => entry.label),
    [locatorRef, documentRef],
  );
});

run("PROPERTY: unmapped source remains an honest record-only citation", () => {
  const ref = "PROPERTY:us-example-county/99999/parcel/APN-123";
  const result = applyCitations(`Recorded [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].sourceKind, "record_only");
  assert.equal(result.entries[0].openUrl, undefined);
});

const stateCourtSourceFixtures = [
  [
    "au-qld-authorised-and-unreported-judgments",
    "https://www.queenslandjudgments.com.au/",
  ],
  [
    "au-qld-court-record-copy-request",
    "https://www.qld.gov.au/law/court/court-services/access-court-records-files-and-services/apply-to-search-and-copy-court-documents",
  ],
  [
    "au-qld-criminal-case-lookup",
    "https://www.courts.qld.gov.au/services-and-online-actions/file-searches/criminal-case-lookup",
  ],
  [
    "au-qld-daily-law-lists",
    "https://www.courts.qld.gov.au/services/court-lists",
  ],
  [
    "au-qld-ecourts-civil",
    "https://apps.courts.qld.gov.au/esearching/Search.aspx",
  ],
  [
    "au-qld-official-caselaw",
    "https://www.sclqld.org.au/caselaw",
  ],
  [
    "au-qld-state-archives-court-records",
    "https://www.archivessearch.qld.gov.au/",
  ],
  [
    "us-nj-tax-court-property-cases",
    "https://www.njcourts.gov/courts/tax/docketed-cases",
  ],
  [
    "us-nj-tax-court-current-object-versions",
    "https://njj-aocmedia-prod-general-purpose.s3.amazonaws.com/?versions&prefix=tax-reports/localtaxcases",
  ],
  [
    "us-nj-tax-court-judgment-archives",
    "https://www.njcourts.gov/courts/tax/docketed-cases",
  ],
  [
    "us-nj-govconnect-tax-notices",
    "https://www.nj.gov/govconnect/news/tax/",
  ],
  [
    "us-nj-tax-case-public-access",
    "https://www.njcourts.gov/public/get-help/tax-case-public-access",
  ],
  [
    "us-nj-tax-court-opinions",
    "https://www.njcourts.gov/attorneys/opinions/published-tax",
  ],
  ["us-nj-courts-full-site-search", "https://www.njcourts.gov/search"],
  [
    "us-nj-tax-court-reports",
    "https://dspace.njstatelib.org/communities/e0d4b9ee-35be-4c30-8449-8caae2251a91",
  ],
  [
    "us-nj-local-property-assessment-sources",
    "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  ],
  [
    "us-nj-rutgers-court-opinions",
    "https://njlaw.rutgers.edu/collections/courts/",
  ],
  ["us-courtlistener-opinions", "https://www.courtlistener.com/"],
  [
    "us-nj-property-tax-appeals",
    "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
  ],
  [
    "us-nj-county-tax-boards",
    "https://www.nj.gov/treasury/taxation/pdf/lpt/CountyBoardsofTaxation.pdf",
  ],
  [
    "us-courtlistener-api",
    "https://wiki.free.law/c/courtlistener/help/api/rest/v4/overview",
  ],
  [
    "us-doj-epstein-court-records",
    "https://www.justice.gov/epstein/doj-disclosures",
  ],
  [
    "us-ny-oca-attorney-registrations",
    "https://data.ny.gov/d/eqw2-r5nb",
  ],
  ["us-ny-nyscef", "https://iapps.courts.state.ny.us/nyscef/CaseSearch"],
  [
    "us-pa-ujs-public-dockets",
    "https://ujsportal.pacourts.us/Home/CaseInformation",
  ],
  [
    "us-pa-aopc-bulk",
    "https://www.pacourts.us/Storage/media/pdfs/20211119/145411-amendedecrpolicyeffective1.1.22.pdf",
  ],
  [
    "us-pa-appellate-opinions-postings",
    "https://www.pacourts.us/courts/supreme-court/court-opinions",
  ],
  [
    "us-pa-judges-and-mdj-districts",
    "https://www.pacourts.us/api/judgeView",
  ],
  ["us-md-case-search", "https://casesearch.mdcourts.gov/casesearch/"],
  [
    "us-md-aoc-court-data",
    "https://www.mdcourts.gov/judicialrecords/recordsrequests",
  ],
  [
    "us-md-appellate-opinions",
    "https://www.mdcourts.gov/opinions/opinions",
  ],
  [
    "us-md-business-technology-opinions",
    "https://www.mdcourts.gov/businesstech/opinions",
  ],
  ["us-md-circuit-clerk-records", "https://www.mdcourts.gov/circuit"],
  [
    "us-md-estate-claims",
    "https://registers.maryland.gov/RowNetWeb/Claims/frmClaimSearch.aspx",
  ],
  [
    "us-md-estate-legal-notices",
    "https://registers.maryland.gov/LegalNotice/Notices/NoticeSearch.aspx",
  ],
  ["us-md-estate-search", "https://registers.maryland.gov/main/search.html"],
  [
    "us-md-judgment-liens",
    "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf",
  ],
  [
    "us-md-mdec-public-cases",
    "https://www.mdcourts.gov/mdec/publiccases",
  ],
  [
    "us-md-register-of-wills-offices",
    "https://registers.maryland.gov/main/directory.html",
  ],
  [
    "us-mi-appellate-case-opinion-order-search",
    "https://www.courts.michigan.gov/case-search/",
  ],
  [
    "us-mi-business-court-search",
    "https://www.courts.michigan.gov/business-court-search/",
  ],
  [
    "us-mi-micourt-developer-case-search-api",
    "https://developer.micourt.courts.michigan.gov/docs/case-search-api-reference-v4",
  ],
  [
    "us-mi-micourt-trial-case-search",
    "https://micourt.courts.michigan.gov/case-search/court-selection",
  ],
  [
    "us-mi-trial-court-directory",
    "https://www.courts.michigan.gov/courts/trial-courts/",
  ],
  [
    "us-dc-court-of-appeals-calendars",
    "https://www.dccourts.gov/court-of-appeals/court-of-appeals-case-calendars",
  ],
  [
    "us-dc-court-of-appeals-case-search",
    "https://efile.dcappeals.gov/public/caseSearch.do",
  ],
  [
    "us-dc-court-of-appeals-opinions-mojs",
    "https://www.dccourts.gov/court-of-appeals/opinions-and-memorandum-of-judgments",
  ],
  [
    "us-dc-superior-court-criminal-calendar",
    "https://www.dccourts.gov/superior-court/superior-court-case-calendars/criminal-attorney-case-calendar",
  ],
  [
    "us-dc-superior-court-tax-calendars",
    "https://www.dccourts.gov/superior-court/superior-court-divisions/tax-division/tax-case-calendar",
  ],
  [
    "us-dc-superior-court-today-calendar",
    "https://www.dccourts.gov/superior-court/superior-court-case-calendars/todays-superior-court-cases",
  ],
  [
    "us-dc-superior-court-portal",
    "https://portal-dc.tylertech.cloud/Portal",
  ],
  [
    "us-dc-superior-eaccess",
    "https://www.dccourts.gov/superior-court/superior-court-case-search",
  ],
  ["us-de-courtconnect", "https://courts.delaware.gov/docket.aspx"],
  [
    "us-de-court-directory-and-calendars",
    "https://courts.delaware.gov/calendars/",
  ],
  [
    "us-de-project-rightful-owner",
    "https://courts.delaware.gov/superior/rightfulowner/",
  ],
  [
    "us-de-court-records-access",
    "https://www.courts.delaware.gov/forms/download.aspx?id=191608",
  ],
  ["us-de-file-and-servexpress", "https://www.fileandservexpress.com"],
  ["us-de-opinions-orders", "https://courts.delaware.gov/opinions/"],
  ["us-fl-acis", "https://acis.flcourts.gov/portal/home"],
  [
    "us-fl-state-court-location-directory",
    "https://www.flcourts.gov/Courts-System/court-structure/court-locations",
  ],
  [
    "us-fl-virtual-courtroom-directory",
    "https://courtrooms.flcourts.gov/",
  ],
  [
    "us-fl-osca-public-records-request",
    "https://www.flcourts.gov/Services/Communications/public-records",
  ],
  [
    "us-fl-trial-court-statistical-reference-guide",
    "https://www.flcourts.gov/Data/trial-court-statistical-reference-guide",
  ],
  [
    "us-ga-aoc-court-personnel-directory",
    "https://georgiacourts.gov/georgia-courts-directory/",
  ],
  [
    "us-fl-ninth-circuit-division-calendars",
    "https://calendar.ninthcircuit.org/",
  ],
  [
    "us-fl-ninth-circuit-appellate-opinions-archive",
    "https://ninthcircuit.org/resources/appellate-opinions-archived",
  ],
  [
    "us-fl-ninth-circuit-administrative-orders",
    "https://ninthcircuit.org/resources/admin-orders",
  ],
  [
    "us-fl-orange-clerk-records-request",
    "https://www.myorangeclerk.com/Divisions/Records/Request-Court-Records",
  ],
  [
    "us-fl-ninth-circuit-court-reporters",
    "https://ninthcircuit.org/programs-services/court-reporters",
  ],
  [
    "us-fl-orange-court-registry-balance",
    "https://myeclerk.myorangeclerk.com/RegistryBalance/Index",
  ],
  [
    "us-fl-orange-confidentiality-notices",
    "https://www.myorangeclerk.com/sealed-case/judicial-notices-and-orders",
  ],
  [
    "us-fl-appellate-opinions-search",
    "https://supremecourt.flcourts.gov/case-information/opinions/Opinion-Search-For-All-Appellate-Courts",
  ],
  [
    "us-fl-sixth-dca-opinion-releases",
    "https://6dca.flcourts.gov/Opinions",
  ],
  [
    "us-flmd-recent-opinions",
    "https://ecf.flmd.uscourts.gov/cgi-bin/Opinions.pl",
  ],
  [
    "us-ca11-published-opinions",
    "https://www.ca11.uscourts.gov/search-published-opinions",
  ],
  [
    "us-ca11-unpublished-opinions",
    "https://www.ca11.uscourts.gov/search-unpublished-opinions",
  ],
  [
    "us-az-pima-superior-agave",
    "https://www.cosc.pima.gov/services/case-records/",
  ],
  [
    "us-ca-los-angeles-superior-probate",
    "https://www.lacourt.ca.gov/pages/lp/probate",
  ],
  [
    "us-ca-los-angeles-superior-probate-name-index",
    "https://www.lacourt.ca.gov/paos/v2web3/CivilIndex",
  ],
  [
    "us-ca-los-angeles-superior-probate-document-images",
    "https://www.lacourt.ca.gov/paos/v2web3/DocumentImages",
  ],
  [
    "us-ca-los-angeles-superior-probate-records",
    "https://www.lacourt.ca.gov/pages/lp/obtaining-copies-of-court-records",
  ],
  [
    "us-ca-los-angeles-superior-civil",
    "https://www.lacourt.ca.gov/pages/lp/civil",
  ],
  [
    "us-ca-los-angeles-superior-civil-archives-records-center",
    "https://www.lacourt.org/generalinfo/Archives/GI_AR001.aspx",
  ],
  [
    "us-ca-los-angeles-superior-civil-name-index",
    "https://www.lacourt.ca.gov/paos/v2web3/CivilIndex",
  ],
  [
    "us-ca-los-angeles-superior-civil-document-images",
    "https://www.lacourt.ca.gov/paos/v2web3/DocumentImages",
  ],
  [
    "us-ca-los-angeles-superior-divorce-judgment-orders",
    "https://www.lacourt.ca.gov/ldos/v2pubweb3/",
  ],
  [
    "us-ca-trellis-los-angeles-superior-court",
    "https://trellis.law/coverage/california/losangeles",
  ],
  [
    "us-ca-los-angeles-superior-family-case-summary",
    "https://www.lacourt.ca.gov/casesummary/v2web3/?casetype=familylaw",
  ],
  [
    "us-ca-los-angeles-superior-small-claims-case-summary",
    "https://www.lacourt.ca.gov/casesummary/v2web3/?casetype=smallclaims",
  ],
  [
    "us-ca-los-angeles-superior-appellate-tentative-rulings",
    "https://www.lacourt.ca.gov/tentativeRulingNet/ui/main.aspx?casetype=appellate",
  ],
  [
    "us-ca-fresno-superior-court-public-records",
    "https://www.fresno.courts.ca.gov/online-services/case-information",
  ],
  [
    "us-ca-fresno-superior-court-ecourt-portal",
    "https://publicportal.fresno.courts.ca.gov/public-portal/?q=Home",
  ],
  [
    "us-ca-fresno-superior-court-daily-calendar",
    "https://www.fresno.courts.ca.gov/general-information/calendar-daily-hearings",
  ],
  [
    "us-ca-fresno-superior-court-tentative-rulings",
    "https://www.fresno.courts.ca.gov/online-services/tentative-rulings",
  ],
  [
    "us-ca-fresno-superior-court-probate-examiner-notes",
    "https://info.fresno.courts.ca.gov/ProbateExaminersNotes/ProbateExaminerNotesSearch.aspx",
  ],
  [
    "us-ca-fresno-superior-court-case-index-product",
    "https://www.fresno.courts.ca.gov/online-services/case-information/case-index-ordering",
  ],
  [
    "us-ca-fresno-superior-court-records-routes",
    "https://www.fresno.courts.ca.gov/online-services/case-information/archives",
  ],
  [
    "us-ca-orange-superior-court-public-records",
    "https://www.occourts.org/online-services",
  ],
  [
    "us-ca-orange-superior-court-calendar",
    "https://courtcalendar.occourts.org/search.do",
  ],
  [
    "us-ca-orange-superior-court-civil-tentative-rulings",
    "https://www.occourts.org/online-services/tentative-rulings/civil-tentative-rulings",
  ],
  [
    "us-ca-orange-superior-court-family-tentative-rulings",
    "https://www.occourts.org/online-services/tentative-rulings/family-law-tentative-rulings",
  ],
  [
    "us-ca-orange-superior-court-probate-tentative-rulings",
    "https://www.occourts.org/online-services/tentative-rulings/probate-tentative-rulings",
  ],
  [
    "us-ca-orange-superior-court-case-name-search",
    "https://namesearch.occourts.org/",
  ],
  [
    "us-ca-orange-superior-court-case-access-portals",
    "https://www.occourts.org/online-services/case-access",
  ],
  [
    "us-ca-orange-superior-court-permanent-case-index",
    "https://courtindex.occourts.org/",
  ],
  [
    "us-ca-orange-superior-court-case-index-products",
    "https://www.occourts.org/online-services/order-case-indexes",
  ],
  [
    "us-ca-orange-superior-court-probate-notes",
    "https://ocscefm1.occourts.org/probate-notes",
  ],
  [
    "us-ca-orange-superior-court-records-and-copies",
    "https://www.occourts.org/general-information/records",
  ],
  [
    "us-ca-riverside-superior-court-public-records",
    "https://www.riverside.courts.ca.gov/online-services/court-calendars",
  ],
  [
    "us-ca-riverside-superior-court-ecalendar",
    "https://ecourtcalendars.riverside.courts.ca.gov/",
  ],
  [
    "us-ca-riverside-superior-court-tentative-rulings",
    "https://www.riverside.courts.ca.gov/online-services/tentative-rulings",
  ],
  [
    "us-ca-riverside-superior-court-public-access",
    "https://epublic-access.riverside.courts.ca.gov/public-portal/",
  ],
  [
    "us-ca-riverside-superior-court-public-access-guide",
    "https://www.riverside.courts.ca.gov/online-services/search-court-records-public-access",
  ],
  [
    "us-ca-riverside-superior-court-name-index-products",
    "https://www.riverside.courts.ca.gov/online-services/purchase-indexes",
  ],
  [
    "us-ca-riverside-superior-court-clerk-search",
    "https://rrs.riverside.courts.ca.gov/",
  ],
  [
    "us-ca-riverside-superior-court-records-and-certified-copies",
    "https://riverside.courts.ca.gov/mServices/LocalForms/local-forms.php",
  ],
  [
    "us-ca-riverside-superior-court-probate-notes",
    "https://www.riverside.courts.ca.gov/self-help/estates-wills-trusts",
  ],
  [
    "us-ca-riverside-superior-court-high-interest-cases",
    "https://www.riverside.courts.ca.gov/general-information/media-information/high-interest-cases",
  ],
  [
    "us-ca-riverside-superior-court-transcript-requests",
    "https://transcriptrequest.riverside.courts.ca.gov/",
  ],
  [
    "us-ca-riverside-superior-court-appellate-division",
    "https://www.riverside.courts.ca.gov/divisions/appeals",
  ],
  [
    "us-ca-fourth-district-division-two-case-information",
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=42",
  ],
  [
    "us-ca-san-mateo-midx",
    "https://web.sanmateocourt.org/midx/",
  ],
  [
    "us-ca-san-mateo-odyssey",
    "https://odyportal-ext.sanmateocourt.org/portal-external",
  ],
  [
    "us-ca-san-mateo-hearings-rulings",
    "https://web.sanmateocourt.org/online_services/edd_jcc.php",
  ],
  [
    "us-ca-san-mateo-records",
    "https://sanmateo.courts.ca.gov/divisions/records-management",
  ],
  [
    "us-ca-first-district-appellate-case-information",
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=1",
  ],
  [
    "us-ca-second-district-appellate-case-information",
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=2",
  ],
  ["us-ca-judicial-branch-opinions", "https://courts.ca.gov/opinions"],
  ["us-ca-public-notices", "https://www.capublicnotice.com/"],
  [
    "us-tax-court-dawson",
    "https://dawson.ustaxcourt.gov/",
  ],
  [
    "us-tax-court-reports",
    "https://ustaxcourt.gov/pamphlets/",
  ],
  [
    "us-tax-court-records-transcripts",
    "https://ustaxcourt.gov/transcripts-and-copies/",
  ],
  [
    "us-govinfo-uscourts",
    "https://www.govinfo.gov/app/collection/uscourts/",
  ],
  [
    "us-ny-law-reporting-bureau",
    "https://www.nycourts.gov/reporter/",
  ],
  [
    "us-ny-webcivil-supreme",
    "https://iapps.courts.state.ny.us/webcivil/FCASMain",
  ],
  [
    "us-ny-court-pass",
    "https://courtpass.nycourts.gov/public_search",
  ],
  [
    "us-ny-court-appeals-archives",
    "https://www.nycourts.gov/palawlibraries/ResearchQuestions/FindingRecordsandBriefsforNYSAppellateCases.pdf",
  ],
  [
    "us-ny-county-clerk-court-records",
    "https://www.nycourts.gov/help/representing-yourself-court/getting-court-records-case-information",
  ],
  [
    "us-ny-public-notices-column",
    "https://newyork.column.us/",
  ],
  [
    "us-ny-trellis",
    "https://trellis.law/coverage/new-york",
  ],
  [
    "us-ny-courtlink",
    "https://www.lexisnexis.com/en-us/products/courtlink.page",
  ],
  [
    "us-ny-elaw",
    "https://www.elaw.com/eLaw21/products/edocket.aspx",
  ],
  [
    "us-fl-orange-clerk-my-eclerk",
    "https://myeclerk.myorangeclerk.com/Cases/Search",
  ],
  [
    "us-fl-orange-county-hearing-calendar",
    "https://myeclerk.myorangeclerk.com/Court/Index",
  ],
  [
    "us-co-denver-county-court-public-docket",
    "https://public.denvercountycourt.org/Docket/Docket",
  ],
  [
    "us-co-appellate-case-law-search",
    "https://research.coloradojudicial.gov/",
  ],
  [
    "us-co-judicial-appellate-opinion-releases",
    "https://www.coloradojudicial.gov/supreme-court/opinions",
  ],
  [
    "us-co-judicial-compiled-aggregate-data-requests",
    "https://www.coloradojudicial.gov/access-guide-public-records",
  ],
  [
    "us-co-judicial-data-reports",
    "https://www.coloradojudicial.gov/data-and-reports",
  ],
  [
    "us-co-judicial-annual-statistical-reports",
    "https://www.coloradojudicial.gov/annual-statistical-reports",
  ],
  [
    "us-co-judicial-case-parties-without-representation",
    "https://www.coloradojudicial.gov/case-parties-without-representation",
  ],
  [
    "us-co-judicial-eviction-filings-dashboard",
    "https://www.coloradojudicial.gov/eviction-filings",
  ],
  [
    "us-co-judicial-docket-search",
    "https://www.coloradojudicial.gov/dockets",
  ],
  [
    "us-co-denver-district-court-records-request",
    "https://www.coloradojudicial.gov/courts/trial-courts/denver-district",
  ],
  [
    "us-co-denver-county-court-records-request",
    "https://www.coloradojudicial.gov/public-access-information",
  ],
  [
    "us-co-denver-district-administrative-orders",
    "https://www.coloradojudicial.gov/courts/trial-courts/denver-district",
  ],
  [
    "us-va-general-district-court-case-information",
    "https://eapps.courts.state.va.us/gdcourts/landing.do?landing=landing",
  ],
  [
    "us-va-circuit-court-case-information",
    "https://eapps.courts.state.va.us/CJISWeb/circuit.jsp?hl=en-US",
  ],
  [
    "us-va-appellate-opinions",
    "https://www.vacourts.gov/opinions/home",
  ],
  [
    "us-fl-palm-beach-ecaseview",
    "https://appsgp.mypalmbeachclerk.com/ecaseview",
  ],
  [
    "us-fl-palm-beach-clerkcart",
    "https://appsgp.mypalmbeachclerk.com/clerkcart/",
  ],
  [
    "us-fl-palm-beach-records-service",
    "https://www.mypalmbeachclerk.com/records/court-records",
  ],
  ["us-in-iocs-bulk", "https://www.in.gov/courts/iocs/statistics/bulk-data/"],
  ["us-wi-wcca-public", "https://wcca.wicourts.gov/"],
  ["us-wi-wscca-public", "https://wscca.wicourts.gov/"],
  ["us-wi-court-opinions", "https://www.wicourts.gov/opinions/"],
  [
    "us-wi-state-law-library-briefs",
    "https://wilawlibrary.gov/search/briefs.html",
  ],
  [
    "us-wi-uw-law-historical-briefs",
    "https://repository.law.wisc.edu/s/uwlaw/page/wisconsin-briefs",
  ],
  [
    "us-wi-appellate-clerk",
    "https://www.wicourts.gov/courts/offices/clerkcontact.htm",
  ],
  [
    "us-wi-wcca-rest",
    "https://www.wicourts.gov/courts/resources/docs/RESTagreementpaid.pdf",
  ],
  [
    "us-mn-court-bulk",
    "https://mncourts.gov/help-topics/court-statistics/bulk-data",
  ],
  [
    "us-nc-rpa-courts",
    "https://www.nccourts.gov/services/remote-public-access-program/rpa-online-access",
  ],
  ["us-az-eaccess", "https://www.azcourts.gov/eaccess/eAccess-Information"],
  [
    "us-or-ojcin",
    "https://www.courts.oregon.gov/services/online/Pages/ojcin-signup.aspx",
  ],
  [
    "us-or-ojd-statewide-court-data-products",
    "https://www.courts.oregon.gov/services/online/pages/ojcin.aspx",
  ],
  [
    "us-or-ojcin-oeci-subscription",
    "https://www.courts.oregon.gov/services/online/pages/ojcin-signup.aspx",
  ],
  [
    "us-or-ojcin-acms-subscription",
    "https://www.courts.oregon.gov/services/online/pages/ojcin-signup.aspx",
  ],
  [
    "us-or-ojcin-standard-report-package",
    "https://www.courts.oregon.gov/services/online/pages/ojcin.aspx",
  ],
  [
    "us-or-ojcin-bulk-data-transfer",
    "https://www.courts.oregon.gov/services/online/pages/ojcin.aspx",
  ],
  [
    "us-or-osca-statewide-court-data-request",
    "https://www.courts.oregon.gov/about/Pages/records-request.aspx",
  ],
  [
    "us-or-ojd-smart-search",
    "https://webportal.courts.oregon.gov/portal/Home/Dashboard/29",
  ],
  [
    "us-or-appellate-record-search",
    "https://trportal.courts.oregon.gov/",
  ],
  [
    "us-or-circuit-tax-court-calendars",
    "https://publicaccess.courts.oregon.gov/PublicAccess/default.aspx",
  ],
  [
    "us-or-court-of-appeals-calendar",
    "https://www.courts.oregon.gov/courts/appellate/go/Pages/coa-calendar.aspx",
  ],
  [
    "us-or-eugene-municipal-record-search",
    "https://www.municipalrecordsearch.com/eugeneor/",
  ],
  [
    "us-or-clackamas-county-justice-record-search",
    "https://www.municipalrecordsearch.com/clackamascountyor/",
  ],
  [
    "us-or-corvallis-municipal-record-search",
    "https://www.municipalrecordsearch.com/corvallisor/",
  ],
  [
    "us-or-hermiston-municipal-record-search",
    "https://www.municipalrecordsearch.com/hermistonor/",
  ],
  [
    "us-or-linn-county-justice-record-search",
    "https://www.municipalrecordsearch.com/linncountyor/",
  ],
  [
    "us-or-medford-municipal-record-search",
    "https://www.municipalrecordsearch.com/medfordor/",
  ],
  [
    "us-or-springfield-municipal-record-search",
    "https://www.municipalrecordsearch.com/springfieldor/",
  ],
  [
    "us-tribal-grand-ronde-record-search",
    "https://www.municipalrecordsearch.com/confederatedtribesofgrandrondeor/",
  ],
  [
    "us-or-supreme-court-calendar",
    "https://www.courts.oregon.gov/courts/appellate/go/Pages/sc-calendar.aspx",
  ],
  [
    "us-or-state-court-directory",
    "https://www.courts.oregon.gov/courts/Pages/locations.aspx",
  ],
  [
    "us-or-state-judge-directory",
    "https://www.courts.oregon.gov/courts/Pages/judges.aspx",
  ],
  [
    "us-or-local-court-registry",
    "https://www.courts.oregon.gov/courts/Pages/other-courts.aspx",
  ],
  [
    "us-or-local-judge-registry",
    "https://www.courts.oregon.gov/courts/Pages/other-courts.aspx",
  ],
  [
    "us-or-law-library-supreme-opinions",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll3",
  ],
  [
    "us-or-law-library-coa-opinions",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll5",
  ],
  [
    "us-or-law-library-tax-court-decisions",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll6",
  ],
  [
    "us-or-law-library-supreme-briefs",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll7",
  ],
  [
    "us-or-law-library-coa-briefs",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll8",
  ],
  [
    "us-or-law-library-coa-orders-interest",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll17",
  ],
  [
    "us-or-law-library-multnomah-presiding-orders",
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll15",
  ],
  ["us-wa-jis-link", "https://www.courts.wa.gov/jislink/?fa=jislink.home"],
  [
    "us-tx-appellate-released-orders-opinions",
    "https://search.txcourts.gov/DocketSrch.aspx?coa=cossup",
  ],
  [
    "us-tx-appellate-tames",
    "https://search.txcourts.gov/CaseSearch.aspx?coa=cossup",
  ],
  [
    "us-tx-bexar-district-historical-cases",
    "https://bexardistrict.tx.publicsearch.us/",
  ],
  [
    "us-tx-bexar-justice-portal",
    "https://www.bexar.org/3856/New-Justice-Information-Portal",
  ],
  [
    "us-vi-c-track",
    "https://usvipublicportal.vicourts.org/portal/home",
  ],
  [
    "us-tx-bexar-district-clerk-records-request",
    "https://www.bexar.org/3703/Records",
  ],
  [
    "us-tx-bexar-county-clerk-records-request",
    "https://www.bexar.org/2984/Public-Record-Search",
  ],
  [
    "us-tx-hays-county-clerk-courts",
    "https://public.hayscountytx.gov/",
  ],
  [
    "us-tx-hays-district-clerk-records-request",
    "https://www.hayscountytx.gov/492/District-Clerk-Records-Search-Copy-Reque",
  ],
  [
    "us-tx-hays-district-court-portal",
    "https://portal-txhays.tylertech.cloud/Portal/",
  ],
  [
    "us-tx-harris-district-clerk-courts",
    "https://www.hcdistrictclerk.com/edocs/public/search.aspx",
  ],
  [
    "us-tx-harris-district-clerk-public-datasets",
    "https://www.hcdistrictclerk.com/common/e-services/PublicDatasets.aspx",
  ],
  [
    "us-tx-oca-citations-notices",
    "https://topics.txcourts.gov/CitationsPublic/SearchCitationNoticeDoc",
  ],
  [
    "us-tx-oca-court-activity",
    "https://www.txcourts.gov/statistics/court-activity-database/",
  ],
  [
    "us-tx-oca-local-rules-standing-orders",
    "https://www.txcourts.gov/rules-forms/local-rules-forms-and-standing-orders/",
  ],
  [
    "us-tx-oca-statistical-supplements",
    "https://www.txcourts.gov/statistics/annual-statistical-reports/",
  ],
  [
    "us-tx-oca-vexatious-litigants",
    "https://www.txcourts.gov/judicial-data/vexatious-litigants/",
  ],
  [
    "us-tx-researchtx",
    "https://research.txcourts.gov/CourtRecordsSearch/Home#!/home",
  ],
  [
    "us-tx-supreme-orders-opinions",
    "https://www.txcourts.gov/supreme/orders-opinions/",
  ],
  [
    "us-tx-travis-criminal-docket-search",
    "https://publiccourts.traviscountytx.gov/dsa/",
  ],
  [
    "us-tx-travis-district-clerk-records-request",
    "https://www.traviscountytx.gov/district-clerk/case-information-records",
  ],
  [
    "us-tx-travis-odyssey-courts",
    "https://odysseyweb.traviscountytx.gov/Portal/",
  ],
  [
    "us-oh-franklin-common-pleas-cio",
    "https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/",
  ],
  [
    "us-oh-franklin-probate-netdata",
    "https://probate.franklincountyohio.gov/Record-Search/General-Case-Search",
  ],
];

for (const [sourceId, url] of stateCourtSourceFixtures) {
  run(`STATECOURT: ${sourceId} resolves to its source landing page`, () => {
    const ref = `STATECOURT:${sourceId}/example-court/CV-2026-1/case`;
    const result = applyCitations(`Recorded [${ref}].`);
    assert.equal(result.entries.length, 1);
    assert.equal(result.entries[0].label, ref);
    assert.equal(result.entries[0].openUrl, url);
    assert.equal(result.entries[0].sourceKind, "external");
    assert.ok(!(result.entries[0].openUrl ?? "").includes("CV-2026-1"));
  });
}

run("Eugene Municipal Court request complement resolves to the City JustFOIA form", () => {
  const ref =
    "PUBLICRECORDSOURCE:us-or-eugene-municipal-record-search/justfoia-municipal-court-request";
  const record = resolveSourceRecord(ref);
  assert.ok(record);
  assert.equal(
    record.externalUrl,
    "https://eugeneor.justfoia.com/Forms/Launch/81b9da81-94d7-49b8-8750-3452f260414f",
  );
  assert.equal(record.kind, "external");
  assert.equal(record.canonicalRef, ref);
});

run("STATECOURT: unmapped source remains record-only", () => {
  const ref = "STATECOURT:us-example-courts/example-court/CV-2026-1/case";
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(links[0].sourceKind, "record_only");
  assert.equal(links[0].openUrl, undefined);
});

run("USCENSUS:ACS5 observation resolves to its official release page", () => {
  const ref = "USCENSUS:ACS5:2024:05000US24005";
  const result = applyCitations(`Denominator [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, ref);
  assert.equal(
    result.entries[0].openUrl,
    "https://api.census.gov/data/2024/acs/acs5.html",
  );
  assert.equal(result.entries[0].sourceKind, "external");
});

run("USCENSUS:ACS5 route refs resolve to the Census data catalog", () => {
  const ref = `USCENSUS:ACS5:ROUTES:${"a".repeat(64)}`;
  const record = resolveSourceRecord(ref);
  assert.ok(record);
  assert.equal(record.canonicalRef, ref);
  assert.equal(record.externalUrl, "https://api.census.gov/data.html");
});

run("PAOPINION: resolves through the official publication source", () => {
  const ref =
    "PAOPINION:us-pa-appellate-opinions-postings/supreme/85654/94487";
  const result = applyCitations(`Published [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, ref);
  assert.equal(
    result.entries[0].openUrl,
    "https://www.pacourts.us/courts/supreme-court/court-opinions",
  );
});

for (const [court, expectedUrl] of [
  [
    "superior",
    "https://www.pacourts.us/courts/superior-court/court-opinions",
  ],
  [
    "commonwealth",
    "https://www.pacourts.us/courts/commonwealth-court/court-opinions",
  ],
]) {
  run(`PAOPINION: ${court} resolves through its own court page`, () => {
    const ref =
      `PAOPINION:us-pa-appellate-opinions-postings/${court}/85654/94487`;
    const links = extractEvidenceLinks(ref);
    assert.equal(links.length, 1);
    assert.equal(links[0].url, expectedUrl);
  });
}

run("PAOPINION-ARTIFACT: resolves through the artifact court page", () => {
  const digest = "a".repeat(64);
  const ref = `PAOPINION-ARTIFACT:superior:${digest}`;
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(
    links[0].url,
    "https://www.pacourts.us/courts/superior-court/court-opinions",
  );
});

run("DECOURTCONNECT judgment resolves through the official source", () => {
  const ref = "DECOURTCONNECT:JUDGMENT:775119:4623454";
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(
    links[0].url,
    "https://courts.delaware.gov/docket.aspx",
  );
});

run("COURT-BULK resolves through the official artifact catalog", () => {
  const ref =
    "COURT-BULK:us-tx-harris-district-clerk-public-datasets/Civil%5C2024-08-15%20FIELD_CODES.xlsx";
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(
    links[0].url,
    "https://www.hcdistrictclerk.com/common/e-services/PublicDatasets.aspx",
  );
});

run("COURT-DATA resolves through the component source", () => {
  const ref =
    "COURT-DATA:us-co-judicial-annual-statistical-reports/annual-statistical-report-fy-2024";
  const links = extractEvidenceLinks(ref);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, ref);
  assert.equal(
    links[0].url,
    "https://www.coloradojudicial.gov/annual-statistical-reports",
  );
});

run("Colorado opinion refs retain component provenance", () => {
  const opinion =
    "COOPINION:us-co-appellate-case-law-search/supreme/887202075";
  const release =
    "COOPINION-RELEASE:us-co-judicial-appellate-opinion-releases/appeals/2026-07-23";
  const artifact =
    `COOPINION-ARTIFACT:us-co-appellate-case-law-search:${"a".repeat(64)}`;
  const links = extractEvidenceLinks(`${opinion} ${release} ${artifact}`);
  assert.equal(links.length, 3);
  assert.equal(
    links[0].url,
    "https://research.coloradojudicial.gov/",
  );
  assert.equal(
    links[1].url,
    "https://www.coloradojudicial.gov/supreme-court/opinions",
  );
  assert.equal(
    links[2].url,
    "https://research.coloradojudicial.gov/",
  );
});

run("Oregon court-document refs retain collection provenance", () => {
  const document =
    "ORCOURT-DOC:us-or-law-library-coa-briefs:124865";
  const artifact =
    `ORCOURT-ARTIFACT:us-or-law-library-coa-briefs:${"a".repeat(64)}`;
  const links = extractEvidenceLinks(`${document} ${artifact}`);
  assert.equal(links.length, 2);
  assert.equal(
    links[0].url,
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll8",
  );
  assert.equal(
    links[1].url,
    "https://cdm17027.contentdm.oclc.org/digital/collection/p17027coll8",
  );
});

run("DEOPINION: resolves to the exact official archive PDF", () => {
  const links = extractEvidenceLinks("DEOPINION:398840");
  assert.equal(links.length, 1);
  assert.equal(links[0].label, "DEOPINION:398840");
  assert.equal(
    links[0].url,
    "https://courts.delaware.gov/opinions/download.aspx?id=398840",
  );
});

run("TAXCOURT: resolves suffixed docket to stable base case URL", () => {
  const ref = "TAXCOURT:455-22S";
  const result = applyCitations(`Filed [${ref}].`);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "TAXCOURT:455-22");
  assert.equal(
    result.entries[0].url,
    "https://dawson.ustaxcourt.gov/case-detail/455-22",
  );
});

run("TAXCOURT: preserves docket-entry UUID in canonical label", () => {
  const entryId = "8fbd790c-3af0-43fb-9059-9754310faa24";
  const links = extractEvidenceLinks(`TAXCOURT:455-22S:${entryId}`);
  assert.equal(links.length, 1);
  assert.equal(links[0].label, `TAXCOURT:455-22:${entryId}`);
  assert.equal(
    links[0].url,
    "https://dawson.ustaxcourt.gov/case-detail/455-22",
  );
});

run("NY_LAW_REPORTS: resolves slip opinion to official full text", () => {
  const result = applyCitations(
    "See [NY_LAW_REPORTS:2026_26113].",
  );
  assert.equal(result.entries.length, 1);
  assert.equal(
    result.entries[0].url,
    "https://www.nycourts.gov/reporter/current/3dseries/2026/2026_26113.shtml",
  );
});

run("NY_COLUMN: resolves notice ID to the direct public notice", () => {
  const noticeId = "5r3wmbl7IAfYExOneLRQ-3";
  const links = extractEvidenceLinks(`NY_COLUMN:${noticeId}`);
  assert.equal(links.length, 1);
  assert.equal(
    links[0].url,
    `https://newyork.column.us/?activeNotice=${noticeId}`,
  );
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

run("CourtListener docket refs resolve both explicit separators", () => {
  const slash = extractEvidenceLinks("CourtListener:docket/69737684");
  const colon = extractEvidenceLinks("courtlistener:docket:49921079");
  assert.equal(slash.length, 1);
  assert.equal(colon.length, 1);
  assert.equal(
    slash[0].url,
    "https://www.courtlistener.com/docket/69737684/united-states-of-america-ex-rel-v-international-peace-institute-inc/",
  );
  assert.equal(
    colon[0].url,
    "https://www.courtlistener.com/docket/49921079/",
  );
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
// Massachusetts UCC (MA-UCC: prefix)
// ---------------------------------------------------------------------------

run("MA-UCC: filing citation links to the official search page", () => {
  const result = applyCitations("See [MA-UCC:202600001234].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "MA-UCC:202600001234");
  assert.equal(result.entries[0].sourceType, "ucc_filing");
  assert.equal(
    result.entries[0].url,
    "https://corp.sec.state.ma.us/corpweb/UCCSearch/UCCSearch.aspx",
  );
  assert.equal(getCitationHealthTier(result.entries[0].key), "tier3");
});

run("MA-UCC: distinct filing references stay distinct at the same portal URL", () => {
  const links = extractEvidenceLinks("MA-UCC:202600001234; ma-ucc:202600005678");
  assert.equal(links.length, 2);
  assert.deepEqual(links.map(link => link.label), ["MA-UCC:202600001234", "MA-UCC:202600005678"]);
  assert.equal(links[0].url, links[1].url);
  assert.notEqual(links[0].key, links[1].key);
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
  assert.equal(result.entries[0].url, "https://www.muckrock.com/foi/request/78799/");
});

run("MuckRock: resolves request ID with filename", () => {
  const result = applyCitations("See [MUCKROCK:78799/Docs.redacted.pdf].");
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "MuckRock 78799/Docs.redacted.pdf");
  assert.equal(result.entries[0].url, "https://www.muckrock.com/foi/request/78799/");
});

run("MuckRock: extractEvidenceLinks resolves request", () => {
  const links = extractEvidenceLinks("MUCKROCK:80009/2019-083151_RC.pdf");
  assert.equal(links.length, 1);
  assert.match(links[0].url ?? "", /muckrock\.com\/foi\/request\/80009/);
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
  assert.equal(getCitationHealthTier("property:source/parcel/id"), "label-only");
  assert.equal(getCitationHealthTier("statecourt:source/case/id"), "label-only");
  assert.equal(getCitationHealthTier("court-data:source/report/id"), "label-only");
  assert.equal(getCitationHealthTier("coopinion:source/case/id"), "label-only");
  assert.equal(
    getCitationHealthTier("coopinion-release:source/release/id"),
    "label-only",
  );
  assert.equal(
    getCitationHealthTier("coopinion-artifact:source:digest"),
    "label-only",
  );
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
    "PROPERTY:us-nc-onemap-parcels/37005/parcel/3013467134",
    "ACRIS:2017021700466001",
    "STATECOURT:us-example-courts/example-court/CV-2026-1/case",
    "PAOPINION:us-pa-appellate-opinions-postings/supreme/85654/94487",
    `PAOPINION-ARTIFACT:superior:${"a".repeat(64)}`,
    "DECOURTCONNECT:JUDGMENT:775119:4623454",
    "COURT-BULK:us-tx-harris-district-clerk-public-datasets/Civil%5C2024-08-15%20FIELD_CODES.xlsx",
    "COURT-DATA:us-co-judicial-annual-statistical-reports/annual-statistical-report-fy-2024",
    "COOPINION:us-co-appellate-case-law-search/supreme/887202075",
    "COOPINION-RELEASE:us-co-judicial-appellate-opinion-releases/appeals/2026-07-23",
    `COOPINION-ARTIFACT:us-co-appellate-case-law-search:${"a".repeat(64)}`,
    "DEOPINION:398840",
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
    { input: "PROPERTY:us-nc-onemap-parcels/37005/parcel/3013467134", expectMin: 1 },
    { input: "ACRIS:2017021700466001", expectMin: 1 },
    { input: "STATECOURT:us-example-courts/example-court/CV-2026-1/case", expectMin: 1 },
    {
      input: "PAOPINION:us-pa-appellate-opinions-postings/supreme/85654/94487",
      expectMin: 1,
    },
    {
      input: `PAOPINION-ARTIFACT:superior:${"a".repeat(64)}`,
      expectMin: 1,
    },
    {
      input: "DECOURTCONNECT:JUDGMENT:775119:4623454",
      expectMin: 1,
    },
    {
      input: "COURT-BULK:us-tx-harris-district-clerk-public-datasets/Civil%5C2024-08-15%20FIELD_CODES.xlsx",
      expectMin: 1,
    },
    {
      input: "COURT-DATA:us-co-judicial-annual-statistical-reports/annual-statistical-report-fy-2024",
      expectMin: 1,
    },
    {
      input: "COOPINION:us-co-appellate-case-law-search/supreme/887202075",
      expectMin: 1,
    },
    {
      input: "COOPINION-RELEASE:us-co-judicial-appellate-opinion-releases/appeals/2026-07-23",
      expectMin: 1,
    },
    {
      input: `COOPINION-ARTIFACT:us-co-appellate-case-law-search:${"a".repeat(64)}`,
      expectMin: 1,
    },
    { input: "DEOPINION:398840", expectMin: 1 },
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

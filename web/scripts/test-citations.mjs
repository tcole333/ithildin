import assert from "node:assert/strict";
import { resolve } from "node:path";
import { createJiti } from "jiti";

const jiti = createJiti(import.meta.url);
const citationsPath = resolve("./src/lib/citations.ts");
const {
  applyCitations,
  createCitationState,
  extractEvidenceLinks,
} = jiti(citationsPath);

function run(name, fn) {
  try {
    fn();
    process.stdout.write(`PASS ${name}\n`);
  } catch (error) {
    process.stderr.write(`FAIL ${name}\n`);
    throw error;
  }
}

run("preserves markdown links and does not split URL citations", () => {
  const input = "Israel and Qatar had [no formal diplomatic relations](https://en.wikipedia.org/wiki/Israel%E2%80%93Qatar_relations). [EFTA02609150]";
  const result = applyCitations(input);

  assert.ok(
    result.markdown.includes("[no formal diplomatic relations](https://en.wikipedia.org/wiki/Israel%E2%80%93Qatar_relations)"),
    "markdown link target should remain intact",
  );

  const labels = result.entries.map((entry) => entry.label);
  for (const fragment of ["https:", "en.wikipedia.org", "wiki", "Israel%E2%80%93Qatar_relations"]) {
    assert.ok(!labels.includes(fragment), `unexpected split URL fragment citation: ${fragment}`);
  }
});

run("dedupes explicit source refs when same finding is cited", () => {
  const findingEvidenceMap = {
    "2108": ["EFTA01296686"],
  };
  const result = applyCitations(
    "Through DKIP PLLC, Indyke managed entities (Finding #2108, EFTA01296686).",
    { findingEvidenceMap },
  );

  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].label, "Finding #2108");
  assert.equal((result.markdown.match(/<sup class=\"citation\">/g) || []).length, 1);
});

run("builds corporate registry links for FL-SunBiz, NM-SoS, and NY-SoS refs", () => {
  const fl = extractEvidenceLinks("FL-SunBiz:F08000003048");
  assert.equal(fl.length, 1);
  assert.equal(fl[0].label, "FL-SunBiz:F08000003048");
  assert.match(fl[0].url ?? "", /search\.sunbiz\.org/i);

  const nm = extractEvidenceLinks("NM-SoS:1615137");
  assert.equal(nm.length, 1);
  assert.equal(nm[0].label, "NM-SoS:1615137");
  assert.match(nm[0].url ?? "", /nm\.us/i);

  const ny = extractEvidenceLinks("NY-SoS:2773652");
  assert.equal(ny.length, 1);
  assert.equal(ny[0].label, "NY-SoS:2773652");
  assert.match(ny[0].url ?? "", /dos\.ny\.gov/i);
});

run("does not emit orphaned FEC suffix fragments", () => {
  const yearSuffix = extractEvidenceLinks("FEC:C00352732-2000");
  assert.equal(yearSuffix.length, 1);
  assert.equal(yearSuffix[0].label, "FEC:C00352732-2000");
  assert.match(yearSuffix[0].url ?? "", /receipts\/\?committee_id=C00352732&two_year_transaction_period=2000/);

  const scheduleA = extractEvidenceLinks("FEC:C00393702/schedule_a");
  assert.equal(scheduleA.length, 1);
  assert.equal(scheduleA[0].label, "FEC:C00393702/schedule_a");
  assert.match(scheduleA[0].url ?? "", /receipts\/\?committee_id=C00393702/);
});

run("normalizes odd-year FEC references to two-year FEC cycle", () => {
  const oddYear = extractEvidenceLinks("FEC:C00384123-2003");
  assert.equal(oddYear.length, 1);
  assert.equal(oddYear[0].label, "FEC:C00384123-2003");
  assert.match(oddYear[0].url ?? "", /receipts\/\?committee_id=C00384123&two_year_transaction_period=2004/);
});

run("shares stable numbering across multiple citation blocks", () => {
  const state = createCitationState();
  const first = applyCitations("First block [EFTA01234567].", {}, state);
  const second = applyCitations("Second block [EFTA01234567] and [EFTA07654321].", {}, state);

  assert.equal(state.entries.length, 2);
  assert.match(first.markdown, />1<\/a>/);
  assert.match(second.markdown, />1<\/a>/);
  assert.match(second.markdown, />2<\/a>/);
});

run("renders DS10 citation tokens and links to financials", () => {
  const result = applyCitations("See [DS10] and [DS10:query_thiel] for transaction context.");
  assert.equal(result.entries.length, 2);
  assert.equal(result.entries[0].label, "DS10");
  assert.equal(result.entries[0].url, "/financials");
  assert.equal(result.entries[1].label, "DS10:query_thiel");
  assert.equal(result.entries[1].url, "/financials");
  assert.match(result.markdown, /href=\"\/financials\"/);

  const links = extractEvidenceLinks("DS10:query_thiel");
  assert.equal(links.length, 1);
  assert.equal(links[0].label, "DS10:query_thiel");
  assert.equal(links[0].url, "/financials");
});

process.stdout.write("All citation regression checks passed.\n");

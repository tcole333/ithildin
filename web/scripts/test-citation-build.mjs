import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const distRoot = resolve(process.cwd(), "dist");

function readDist(path) {
  return readFileSync(resolve(distRoot, path), "utf-8");
}

const articleHtml = readDist("articles/corporate-shell-network/index.html");
const dossierHtml = readDist("dossiers/southern-financial-llc/index.html");
const astroFiles = readdirSync(resolve(distRoot, "_astro"));
const evidenceBootstrapFile = astroFiles.find((file) => file.startsWith("evidencePageBootstrap."));
assert.ok(evidenceBootstrapFile, "Built assets should include the shared evidence bootstrap bundle.");
const bootstrapSource = readDist(`_astro/${evidenceBootstrapFile}`);

assert.ok(!articleHtml.includes("[NYDFS-Consent-Order-2020-p8]"), "Raw NYDFS citation token remained in built article HTML.");
assert.ok(!articleHtml.includes("#registry-VI-"), "Built article still contains dead VI registry hash links.");
assert.ok(articleHtml.includes("/sources/"), "Built article should expose source-record links in the sources section.");

assert.ok(bootstrapSource.includes("finding-detail-data"), "Shared evidence bootstrap should initialize finding popovers.");
assert.ok(bootstrapSource.includes("data-evidence-page"), "Shared evidence bootstrap should initialize support mode when present.");
assert.ok(dossierHtml.includes('data-citation-key="finding:596"') || dossierHtml.includes("finding:596"), "Built dossier should include finding #596 citation data.");
assert.ok(dossierHtml.includes('href="#fn-'), "Built dossier finding citations should target footnotes for popover interception.");
assert.ok(dossierHtml.includes("/sources/"), "Built dossier should expose source-record links.");

process.stdout.write("Citation build checks passed.\n");

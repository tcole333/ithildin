import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createJiti } from "jiti";

const args = new Set(process.argv.slice(2));
const update = args.has("--update");

const cwd = process.cwd();
const projectRoot = resolve(cwd, "..");
const snapshotPath = resolve(cwd, "scripts", "citation-snapshots.json");

const jiti = createJiti(import.meta.url);
const { applyCitations, createCitationState, renderFootnotes } = jiti(resolve(cwd, "src", "lib", "citations.ts"));
const {
  processArticleEvidenceContent,
  processDossierCurationEvidence,
  buildDossierFindingEvidenceMap,
} = jiti(resolve(cwd, "src", "lib", "contentEvidencePipeline.ts"));

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function normalizeCitationNumbering(value) {
  return normalizeText(value)
    .replace(/data-support-span-id="[^"]+"/g, 'data-support-span-id="support-N"')
    .replace(/data-citation-number="\d+"/g, 'data-citation-number="N"')
    .replace(/id="fn-\d+"/g, 'id="fn-N"')
    .replace(/aria-label="Source \d+:/g, 'aria-label="Source N:')
    .replace(/<span class="citation-index">\d+\.<\/span>/g, '<span class="citation-index">N.</span>')
    .replace(/>(\d+)<\/a>/g, ">N</a>");
}

function extractFirstMatch(value, pattern) {
  const match = String(value || "").match(pattern);
  return match ? normalizeCitationNumbering(match[0]) : "";
}

function extractFootnoteEntry(footnotesHtml, needle) {
  const entries = String(footnotesHtml || "").match(/<li id="fn-\d+">[\s\S]*?<\/li>/g) || [];
  const entry = entries.find((item) => item.includes(needle));
  return normalizeCitationNumbering(entry || "");
}

async function buildArticleSnapshot() {
  const articlePath = resolve(projectRoot, "content", "articles", "gulf-intelligence-web.mdx");
  const raw = readFileSync(articlePath, "utf-8");
  const body = raw.replace(/^---\n[\s\S]*?\n---\n*/, "");

  const state = createCitationState();
  const { markdown } = applyCitations(body, {}, state);
  const footnotesHtml = renderFootnotes(state.entries);
  const articleEvidence = await processArticleEvidenceContent(body, {});

  return {
    markdown_link_line: extractFirstMatch(markdown, /Israel and Qatar had[\s\S]*?EFTA02609150[\s\S]*?<\/sup>/),
    efta_footnote: extractFootnoteEntry(footnotesHtml, "EFTA02609150"),
    support_span_line: extractFirstMatch(
      articleEvidence.contentHtml,
      /<span class="support-span support-span--supported"[^>]*>He offered a notable accommodation[\s\S]*?<\/span>/,
    ),
    has_unsupported_spans: articleEvidence.supportMap.spans.some((span) => span.supported === false),
    has_split_fragments: state.entries.some((entry) =>
      ["https:", "en.wikipedia.org", "wiki", "Israel%E2%80%93Qatar_relations"].includes(String(entry.label || "")),
    ),
  };
}

function buildDossierSnapshot() {
  const dossierPath = resolve(projectRoot, "content", "dossiers", "darren-indyke.json");
  const dossier = JSON.parse(readFileSync(dossierPath, "utf-8"));

  const findingEvidenceMap = buildDossierFindingEvidenceMap(dossier);
  const dossierEvidence = processDossierCurationEvidence({
    findingEvidenceMap,
    lead: dossier.curation?.lead || "",
    sections: Array.isArray(dossier.curation?.sections) ? dossier.curation.sections : [],
    legacyOverview: dossier.curation?.overview || "",
    legacyFinancialSummary: dossier.curation?.financial_summary || "",
  });
  const footnotesHtml = dossierEvidence.footnotesHtml;
  const finding1725 = extractFootnoteEntry(footnotesHtml, "Finding #1725");
  const urls = Array.from(finding1725.matchAll(/href="([^"]+)"/g), (match) => match[1]);
  const supportLine = extractFirstMatch(
    dossierEvidence.leadHtml,
    /<span class="support-span support-span--supported"[^>]*>Through his law firm DKIP PLLC[\s\S]*?<\/span>/,
  );

  return {
    finding_1725_footnote: finding1725,
    finding_1725_urls: urls,
    lead_support_span_line: supportLine,
    has_source_data_attrs: /data-source-key=/.test(finding1725) && /data-parent-citation-key=/.test(finding1725),
  };
}

async function buildSnapshotPayload() {
  return {
    article_gulf_intelligence_web: await buildArticleSnapshot(),
    dossier_darren_indyke: buildDossierSnapshot(),
  };
}

const current = await buildSnapshotPayload();

assert.ok(current.article_gulf_intelligence_web.markdown_link_line, "Expected Gulf article citation line to be present.");
assert.ok(current.article_gulf_intelligence_web.efta_footnote, "Expected Gulf article EFTA footnote to be present.");
assert.ok(current.article_gulf_intelligence_web.support_span_line, "Expected Gulf article support span sample to be present.");
assert.equal(current.article_gulf_intelligence_web.has_unsupported_spans, true, "Expected unsupported article spans.");
assert.equal(current.article_gulf_intelligence_web.has_split_fragments, false, "Split URL citation fragments detected.");
assert.ok(current.dossier_darren_indyke.finding_1725_footnote, "Expected Darren Finding #1725 footnote to be present.");
assert.ok(current.dossier_darren_indyke.lead_support_span_line, "Expected Darren lead support span sample to be present.");
assert.equal(current.dossier_darren_indyke.has_source_data_attrs, true, "Expected finding footnote source data attributes.");

if (update || !existsSync(snapshotPath)) {
  writeFileSync(snapshotPath, `${JSON.stringify(current, null, 2)}\n`, "utf-8");
  process.stdout.write(`Updated citation snapshot fixture at ${snapshotPath}\n`);
  process.exit(0);
}

const expected = JSON.parse(readFileSync(snapshotPath, "utf-8"));
assert.deepEqual(current, expected);
process.stdout.write("Citation snapshot regression checks passed.\n");

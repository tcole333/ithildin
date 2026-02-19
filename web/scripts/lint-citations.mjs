import { readFileSync, readdirSync, existsSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { createJiti } from "jiti";

const cwd = process.cwd();
const projectRoot = resolve(cwd, "..");
const contentRoot = resolve(projectRoot, "content");
const articlesDir = resolve(contentRoot, "articles");
const dossiersDir = resolve(contentRoot, "dossiers");
const baselinePath = resolve(cwd, "scripts", "citation-lint-baseline.json");

const argv = process.argv.slice(2);
const args = new Set(argv.filter((arg) => arg.startsWith("--")));

function readArgValue(flag) {
  const index = argv.indexOf(flag);
  if (index === -1) return "";
  const candidate = argv[index + 1];
  if (!candidate || candidate.startsWith("--")) return "";
  return candidate;
}

const strict = args.has("--strict");
const updateBaseline = args.has("--update-baseline");
const changedFilesMode = args.has("--changed-files");
const strictChangedFiles = args.has("--strict-changed-files");
const baseRef = readArgValue("--base-ref") || process.env.CITATION_LINT_BASE_REF || "";
const headRef = readArgValue("--head-ref") || process.env.CITATION_LINT_HEAD_REF || "HEAD";

const jiti = createJiti(import.meta.url);
const { applyCitations, createCitationState } = jiti(resolve(cwd, "src", "lib", "citations.ts"));
const { loadFindingEvidenceMap } = jiti(resolve(cwd, "src", "lib", "findingEvidence.ts"));

/** @typedef {{severity: 'error'|'warning', code: string, file: string, location: string, subject: string, message: string}} LintIssue */

/** @type {LintIssue[]} */
const issues = [];
const seenIssueKeys = new Set();

function issueKey(issue) {
  return `${issue.code}|${issue.file}|${issue.location}|${issue.subject}`;
}

function addIssue(severity, code, file, location, subject, message) {
  const issue = { severity, code, file, location, subject, message };
  const key = issueKey(issue);
  if (seenIssueKeys.has(key)) return;
  seenIssueKeys.add(key);
  issues.push(issue);
}

function normalizeRef(ref) {
  return String(ref || "").trim();
}

function lintCitationEntries(file, location, entries) {
  for (const entry of entries || []) {
    const label = String(entry.label || "");
    const url = typeof entry.url === "string" ? entry.url : "";

    if (/^https?:$/i.test(label)) {
      addIssue(
        "error",
        "CITE_SPLIT_URL_SCHEME",
        file,
        location,
        label,
        `Citation label is an URL scheme fragment (${label}) and likely came from URL splitting.`,
      );
    }

    if (!url && /%[0-9a-f]{2}/i.test(label)) {
      addIssue(
        "error",
        "CITE_SPLIT_URL_FRAGMENT",
        file,
        location,
        label,
        "Citation label looks like a URL path fragment but has no URL.",
      );
    }

    if (!url && /^www\./i.test(label)) {
      addIssue(
        "warning",
        "CITE_BARE_DOMAIN",
        file,
        location,
        label,
        "Citation label looks like a bare domain without an attached URL.",
      );
    }
  }
}

function lintEvidenceRef(file, findingId, ref) {
  const value = normalizeRef(ref);
  const loc = `finding:${findingId}`;

  if (!value) {
    addIssue("warning", "EVIDENCE_EMPTY", file, loc, "", "Evidence reference is empty.");
    return;
  }

  if (/^https?:\/\//i.test(value)) {
    try {
      // eslint-disable-next-line no-new
      new URL(value);
    } catch {
      addIssue("error", "EVIDENCE_BAD_URL", file, loc, value, "Evidence reference URL is malformed.");
    }
    return;
  }

  if (/^EFTA/i.test(value) && !/^EFTA\d{6,}$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_EFTA", file, loc, value, "EFTA reference must be EFTA followed by at least 6 digits.");
    return;
  }

  if (/^HOUSE_OVERSIGHT/i.test(value) && !/^HOUSE_OVERSIGHT_\d+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_HOUSE", file, loc, value, "HOUSE_OVERSIGHT reference must be HOUSE_OVERSIGHT_<digits>.");
    return;
  }

  if (/^SEC:/i.test(value) && !/^SEC:\d{10}-\d{2}-\d{6}$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_SEC", file, loc, value, "SEC reference must be SEC:##########-##-######.");
    return;
  }

  if (/^EDGAR:/i.test(value) && !/^EDGAR:\d{10}-\d{2}-\d{6}$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_EDGAR", file, loc, value, "EDGAR reference must be EDGAR:##########-##-######.");
    return;
  }

  if (/^990:/i.test(value) && !/^990:\d{9}$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_990", file, loc, value, "IRS 990 reference must be 990:<9-digit EIN>.");
    return;
  }

  if (/^ACRIS:/i.test(value) && !/^ACRIS:\d{13,16}$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_ACRIS", file, loc, value, "ACRIS reference must be ACRIS:<13-16 digits>.");
    return;
  }

  if (/^CL:/i.test(value) && !/^CL:\d+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_CL", file, loc, value, "CourtListener reference must be CL:<docket id>.");
    return;
  }

  if (/^FARA:/i.test(value) && !/^FARA:\d+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_FARA", file, loc, value, "FARA reference must be FARA:<digits>.");
    return;
  }

  if (/^USVI:/i.test(value) && !/^USVI:[A-Za-z0-9]+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_USVI", file, loc, value, "USVI reference must be USVI:<entity id>.");
    return;
  }

  if (/^REG:/i.test(value) && !/^REG:[A-Z]{2}:[A-Za-z0-9]+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_REG", file, loc, value, "Registry reference must be REG:<CC>:<entity id>.");
    return;
  }

  if (/^FL[-_]?SunBiz/i.test(value) && !/^FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_FL_SUNBIZ", file, loc, value, "FL-SunBiz reference must include a valid entity id.");
    return;
  }

  if (/^NM[-_]?SoS/i.test(value) && !/^NM[-_]?SoS[:\s]+[A-Za-z0-9]+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_NM_SOS", file, loc, value, "NM-SoS reference must include a valid entity id.");
    return;
  }

  if (/^NY[-_]?SoS/i.test(value) && !/^NY[-_]?SoS[:\s]+[A-Za-z0-9]+$/i.test(value)) {
    addIssue("error", "EVIDENCE_BAD_NY_SOS", file, loc, value, "NY-SoS reference must include a valid entity id.");
    return;
  }

  if (/^FEC:/i.test(value)) {
    const isCommittee = /^FEC:C\d{8}$/i.test(value);
    const isScheduleA = /^FEC:C\d{8}\/schedule_a$/i.test(value);
    const isCommitteeYear = /^FEC:C\d{8}-(\d{4})$/i.test(value);
    const isAlias = /^FEC:[A-Za-z0-9_]+$/i.test(value);

    if (!(isCommittee || isScheduleA || isCommitteeYear || isAlias)) {
      addIssue(
        "error",
        "EVIDENCE_BAD_FEC",
        file,
        loc,
        value,
        "FEC reference must be one of: FEC:C########, FEC:C########/schedule_a, FEC:C########-YYYY, or FEC:<alias>.",
      );
      return;
    }

    if (isCommitteeYear) return;

    if (isAlias && !value.includes("C")) {
      addIssue(
        "warning",
        "FEC_ALIAS",
        file,
        loc,
        value,
        "FEC alias token is not a canonical committee id; check source provenance.",
      );
    }
  }
}

function loadBaseline() {
  if (!existsSync(baselinePath)) {
    return new Set();
  }

  try {
    const parsed = JSON.parse(readFileSync(baselinePath, "utf-8"));
    if (!Array.isArray(parsed.ignored)) {
      return new Set();
    }
    return new Set(parsed.ignored.map(String));
  } catch {
    return new Set();
  }
}

function saveBaseline(issueKeys) {
  const payload = {
    generated_at: new Date().toISOString(),
    ignored: issueKeys,
  };
  writeFileSync(baselinePath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

function runGit(args) {
  try {
    return execFileSync("git", args, { cwd: projectRoot, encoding: "utf-8" }).trim();
  } catch {
    return "";
  }
}

function normalizeRepoPath(path) {
  const normalized = String(path || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\.\//, "");
  if (normalized.startsWith("site/")) {
    return normalized.slice("site/".length);
  }
  return normalized;
}

function isCitationTrackedContent(path) {
  return /^content\/articles\/.+\.mdx$/.test(path) || /^content\/dossiers\/[^/]+\.json$/.test(path);
}

function getChangedContentFiles() {
  if (!changedFilesMode && !strictChangedFiles) {
    return null;
  }

  /** @type {string[]} */
  const candidates = [];

  if (baseRef) {
    const rangeOutput = runGit(["diff", "--name-only", "--diff-filter=ACMR", `${baseRef}...${headRef}`]);
    if (rangeOutput) {
      candidates.push(...rangeOutput.split("\n"));
    }
  } else {
    const unstaged = runGit(["diff", "--name-only", "--diff-filter=ACMR"]);
    const staged = runGit(["diff", "--name-only", "--diff-filter=ACMR", "--cached"]);

    if (unstaged) candidates.push(...unstaged.split("\n"));
    if (staged) candidates.push(...staged.split("\n"));

    if (!unstaged && !staged && process.env.CI === "true") {
      const recentRange = runGit(["diff", "--name-only", "--diff-filter=ACMR", "HEAD~1...HEAD"]);
      if (recentRange) {
        candidates.push(...recentRange.split("\n"));
      }
    }
  }

  const out = new Set();
  for (const rawPath of candidates) {
    const file = normalizeRepoPath(rawPath);
    if (isCitationTrackedContent(file)) {
      out.add(file);
    }
  }
  return out;
}

function lintArticles(fileScope = null) {
  if (!existsSync(articlesDir)) return;

  const findingEvidenceMap = loadFindingEvidenceMap();
  const files = readdirSync(articlesDir).filter((f) => f.endsWith(".mdx"));
  for (const fileName of files) {
    const abs = resolve(articlesDir, fileName);
    const rel = abs.replace(`${projectRoot}/`, "");
    if (fileScope && !fileScope.has(rel)) continue;
    const raw = readFileSync(abs, "utf-8");
    const body = raw.replace(/^---\n[\s\S]*?\n---\n*/, "");
    const state = createCitationState();
    applyCitations(body, { findingEvidenceMap }, state);
    lintCitationEntries(rel, "article:body", state.entries);
  }
}

function buildDossierFindingEvidenceMap(dossier) {
  const map = {};
  for (const finding of dossier.findings || []) {
    const id = String(finding.id);
    map[id] = [];
    for (const ev of finding.evidence || []) {
      if (typeof ev.evidence_ref === "string" && ev.evidence_ref.trim()) {
        map[id].push(ev.evidence_ref.trim());
      }
    }
  }
  return map;
}

function lintDossiers(fileScope = null) {
  if (!existsSync(dossiersDir)) return;

  const files = readdirSync(dossiersDir).filter((f) => f.endsWith(".json") && !f.startsWith("_"));
  for (const fileName of files) {
    const abs = resolve(dossiersDir, fileName);
    const rel = abs.replace(`${projectRoot}/`, "");
    if (fileScope && !fileScope.has(rel)) continue;
    const dossier = JSON.parse(readFileSync(abs, "utf-8"));

    for (const finding of dossier.findings || []) {
      for (const ev of finding.evidence || []) {
        lintEvidenceRef(rel, String(finding.id), ev.evidence_ref);
      }
    }

    const findingEvidenceMap = buildDossierFindingEvidenceMap(dossier);
    const state = createCitationState();

    const lead = dossier.curation?.lead;
    if (typeof lead === "string" && lead.trim()) {
      applyCitations(lead, { findingEvidenceMap }, state);
    }

    const sections = Array.isArray(dossier.curation?.sections) ? dossier.curation.sections : [];
    for (const [index, section] of sections.entries()) {
      const content = typeof section?.content === "string" ? section.content : "";
      if (!content.trim()) continue;
      applyCitations(content, { findingEvidenceMap }, state);
      lintCitationEntries(rel, `section:${index}:${section?.title || "untitled"}`, state.entries);
    }

    const overview = dossier.curation?.overview;
    if (typeof overview === "string" && overview.trim()) {
      applyCitations(overview, { findingEvidenceMap }, state);
    }

    const finSummary = dossier.curation?.financial_summary;
    if (typeof finSummary === "string" && finSummary.trim()) {
      applyCitations(finSummary, { findingEvidenceMap }, state);
    }

    lintCitationEntries(rel, "dossier:curation", state.entries);
  }
}

const changedContentFiles = getChangedContentFiles();
if (changedContentFiles && changedContentFiles.size === 0) {
  process.stdout.write("Citation lint found no changed article/dossier files to check.\n");
}

lintArticles(changedContentFiles);
lintDossiers(changedContentFiles);

const baseline = loadBaseline();
const allKeys = issues.map(issueKey).sort();

if (updateBaseline) {
  saveBaseline(allKeys);
  process.stdout.write(`Updated citation lint baseline with ${allKeys.length} issue key(s).\n`);
  process.exit(0);
}

const existing = [];
const fresh = [];
for (const issue of issues) {
  if (baseline.has(issueKey(issue))) {
    existing.push(issue);
  } else {
    fresh.push(issue);
  }
}

const freshErrors = fresh.filter((i) => i.severity === "error");
const freshWarnings = fresh.filter((i) => i.severity === "warning");

const scopeLabel = changedContentFiles
  ? `changed scope (${changedContentFiles.size} file(s))`
  : "full scope";

process.stdout.write(
  `Citation lint scanned ${issues.length} unique issue(s) in ${scopeLabel}: ${existing.length} baseline, ${fresh.length} new.\n`,
);

function printIssueBucket(label, bucket, headingPrefix = "New") {
  if (bucket.length === 0) return;
  process.stdout.write(`\n${headingPrefix} ${label}s (${bucket.length}):\n`);
  for (const issue of bucket.slice(0, 200)) {
    process.stdout.write(`- [${issue.code}] ${issue.file} (${issue.location}) ${issue.subject} :: ${issue.message}\n`);
  }
  if (bucket.length > 200) {
    process.stdout.write(`- ... ${bucket.length - 200} more ${label}(s)\n`);
  }
}

if (fresh.length > 0) {
  printIssueBucket("error", freshErrors);
  printIssueBucket("warning", freshWarnings);
}

if (strictChangedFiles && issues.length > 0) {
  const changedErrors = issues.filter((i) => i.severity === "error");
  const changedWarnings = issues.filter((i) => i.severity === "warning");
  process.stdout.write(
    "\nStrict changed-file mode failed: citation issues are not allowed in modified article/dossier files, even if baseline-listed.\n",
  );
  printIssueBucket("error", changedErrors, "Changed-file");
  printIssueBucket("warning", changedWarnings, "Changed-file");
  process.exit(1);
}

if (freshErrors.length > 0) {
  process.exit(1);
}

if (strict && freshWarnings.length > 0) {
  process.exit(1);
}

process.exit(0);

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const contentRoot = resolve(projectRoot, "content");
const articlesDir = resolve(contentRoot, "articles");
const dossiersDir = resolve(contentRoot, "dossiers");
const dbPath = resolve(projectRoot, "investigation.db");
const args = new Set(process.argv.slice(2));
const write = args.has("--write");

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function sortNumericIds(values) {
  return [...values].sort((left, right) => Number(left) - Number(right));
}

function collectFindingIds(value, allowBareShorthand = false) {
  const text = String(value || "");
  const ids = new Set();

  for (const match of text.matchAll(/\bFindings?\s*#\s*\d+(?:\s*(?:,|and)\s*#?\s*\d+)*/gi)) {
    for (const id of match[0].match(/\d+/g) || []) ids.add(id);
  }
  for (const match of text.matchAll(/\bFinding\s*#\s*(\d+)/gi)) ids.add(match[1]);
  if (allowBareShorthand) {
    for (const match of text.matchAll(/(?:^|[;,\s])F(\d{1,6})(?=$|[;,\s])/g)) ids.add(match[1]);
    for (const match of text.matchAll(/\bfindings?\s*:\s*(\d+)\b/gi)) ids.add(match[1]);
    for (const match of text.matchAll(/\bfindings?\s+(\d+)\b/gi)) ids.add(match[1]);
  }

  return [...ids];
}

function normalizeFindingListSegment(segment) {
  const ids = segment.match(/\d+/g) || [];
  if (!ids.length) return segment;
  return ids.map((id) => `Finding #${id}`).join("; ");
}

function normalizeEvidenceRef(value) {
  let normalized = String(value || "").trim();
  if (!normalized) return normalized;

  normalized = normalized.replace(/(^|[^:A-Za-z0-9_])F(\d{1,6})\b/g, "$1Finding #$2");
  normalized = normalized.replace(/\bfindings?\s*:\s*(\d+)\b/gi, "Finding #$1");
  normalized = normalized.replace(/\bfindings?\s+(\d+)\b/gi, "Finding #$1");
  normalized = normalized.replace(
    /\bFindings?\s*#\s*\d+(?:\s*(?:,|and)\s*#?\s*\d+)*/gi,
    (match) => normalizeFindingListSegment(match),
  );

  return normalized;
}

function parseSourceDatasets(value) {
  if (!value) return null;
  if (Array.isArray(value)) return value;
  const raw = String(value).trim();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return raw.split(",").map((part) => part.trim()).filter(Boolean);
  }
}

function queryFindings(ids) {
  if (!ids.length) return [];
  const where = ids
    .map((id) => `'${String(id).replace(/'/g, "''")}'`)
    .join(",");
  const sql = `
    SELECT
      f.id,
      f.target_name,
      f.finding_type,
      f.summary,
      f.detail,
      f.source_datasets,
      f.confidence,
      f.date_of_event,
      f.claim_type,
      f.verification_status,
      f.created_at,
      f.profile_id,
      fe.evidence_type,
      fe.evidence_ref,
      fe.source_quote,
      fe.source_page,
      fe.assessment
    FROM findings f
    LEFT JOIN finding_evidence fe ON fe.finding_id = f.id
    WHERE f.id IN (${where})
    ORDER BY f.id, fe.evidence_ref;
  `;

  const output = execFileSync("sqlite3", [dbPath, ".mode json", sql], {
    encoding: "utf-8",
    maxBuffer: 16 * 1024 * 1024,
  }).trim();
  return output ? JSON.parse(output) : [];
}

function buildFindingMap(rows) {
  const map = new Map();
  for (const row of rows) {
    const id = String(row.id);
    if (!map.has(id)) {
      map.set(id, {
        id: Number.isFinite(Number(row.id)) ? Number(row.id) : row.id,
        finding_type: row.finding_type ?? null,
        summary: row.summary || "",
        detail: row.detail ?? null,
        source_datasets: parseSourceDatasets(row.source_datasets),
        confidence: row.confidence || "medium",
        date_of_event: row.date_of_event ?? null,
        claim_type: row.claim_type || "inference",
        verification_status: row.verification_status || "unverified",
        created_at: row.created_at ?? null,
        target_name: row.target_name || "",
        profile_id: row.profile_id || null,
        evidence: [],
      });
    }

    if (row.evidence_ref) {
      map.get(id).evidence.push({
        evidence_type: row.evidence_type || "ref",
        evidence_ref: normalizeEvidenceRef(row.evidence_ref),
        source_quote: row.source_quote ?? null,
        source_page: row.source_page ?? null,
        assessment: row.assessment ?? null,
      });
    }
  }
  return map;
}

function buildArticleTarget(fileName) {
  const path = resolve(articlesDir, fileName);
  const findingsPath = resolve(articlesDir, `${fileName.replace(/\.mdx$/, "")}-findings.json`);
  const raw = readFileSync(path, "utf-8");
  const body = raw.replace(/^---\n[\s\S]*?\n---\n*/, "");
  const refs = new Set(collectFindingIds(body, false));

  if (existsSync(findingsPath)) {
    const findings = loadJson(findingsPath);
    for (const detail of Object.values(findings)) {
      for (const evidence of detail?.evidence || []) {
        for (const id of collectFindingIds(evidence?.evidence_ref, true)) refs.add(id);
      }
    }
  }

  return {
    kind: "article",
    path,
    findingsPath,
    refs,
  };
}

function buildDossierTarget(fileName) {
  const path = resolve(dossiersDir, fileName);
  const dossier = loadJson(path);
  const refs = new Set();
  const proseFields = [
    dossier?.curation?.lead,
    dossier?.curation?.overview,
    dossier?.curation?.financial_summary,
  ];

  for (const value of proseFields) {
    for (const id of collectFindingIds(value, false)) refs.add(id);
  }
  for (const section of dossier?.curation?.sections || []) {
    for (const id of collectFindingIds(section?.content, false)) refs.add(id);
  }
  for (const finding of dossier?.findings || []) {
    for (const evidence of finding?.evidence || []) {
      for (const id of collectFindingIds(evidence?.evidence_ref, true)) refs.add(id);
    }
  }

  return {
    kind: "dossier",
    path,
    dossier,
    refs,
  };
}

function loadExistingContentIds() {
  const ids = new Set();

  for (const fileName of readdirSync(articlesDir).filter((file) => file.endsWith("-findings.json")).sort()) {
    const findings = loadJson(resolve(articlesDir, fileName));
    for (const id of Object.keys(findings)) ids.add(String(id));
  }

  for (const fileName of readdirSync(dossiersDir).filter((file) => file.endsWith(".json") && !file.startsWith("_")).sort()) {
    const dossier = loadJson(resolve(dossiersDir, fileName));
    for (const finding of dossier?.findings || []) ids.add(String(finding?.id));
  }

  return ids;
}

function recomputeFindingStats(dossier) {
  const counts = {};
  for (const finding of dossier?.findings || []) {
    const findingType = String(finding?.finding_type || "unknown");
    counts[findingType] = (counts[findingType] || 0) + 1;
  }

  dossier.stats = {
    ...(dossier.stats || {}),
    total_findings: Array.isArray(dossier.findings) ? dossier.findings.length : 0,
    finding_types: counts,
  };

  if (dossier.last_updated && dossier.stats) {
    dossier.stats.last_updated = dossier.last_updated;
  }
}

function writeArticleFindings(target, assignedIds, fetchedFindings) {
  const existing = existsSync(target.findingsPath) ? loadJson(target.findingsPath) : {};
  let changed = false;

  for (const id of sortNumericIds(assignedIds)) {
    if (existing[id]) continue;
    const finding = fetchedFindings.get(id);
    if (!finding) continue;
    existing[id] = finding;
    changed = true;
  }

  if (!changed) return false;

  const sorted = {};
  for (const id of Object.keys(existing).sort((left, right) => Number(left) - Number(right))) {
    sorted[id] = existing[id];
  }

  if (write) {
    writeFileSync(target.findingsPath, `${JSON.stringify(sorted, null, 2)}\n`, "utf-8");
  }
  return true;
}

function writeDossierFindings(target, assignedIds, fetchedFindings) {
  const dossier = loadJson(target.path);
  const localIds = new Set((dossier.findings || []).map((finding) => String(finding?.id)));
  let changed = false;

  for (const id of sortNumericIds(assignedIds)) {
    if (localIds.has(id)) continue;
    const finding = fetchedFindings.get(id);
    if (!finding) continue;
    dossier.findings = dossier.findings || [];
    dossier.findings.push(finding);
    localIds.add(id);
    changed = true;
  }

  if (!changed) return false;

  dossier.findings.sort((left, right) => Number(left?.id) - Number(right?.id));
  recomputeFindingStats(dossier);

  if (write) {
    writeFileSync(target.path, `${JSON.stringify(dossier, null, 2)}\n`, "utf-8");
  }
  return true;
}

if (!existsSync(dbPath)) {
  throw new Error(`Missing investigation DB at ${dbPath}`);
}

const targets = [];
for (const fileName of readdirSync(articlesDir).filter((file) => file.endsWith(".mdx")).sort()) {
  targets.push(buildArticleTarget(fileName));
}
for (const fileName of readdirSync(dossiersDir).filter((file) => file.endsWith(".json") && !file.startsWith("_")).sort()) {
  targets.push(buildDossierTarget(fileName));
}

const existingIds = loadExistingContentIds();
const assignedToFile = new Map();
const fileAssignments = new Map();

for (const target of targets) {
  for (const id of target.refs) {
    if (existingIds.has(id) || assignedToFile.has(id)) continue;
    assignedToFile.set(id, target.path);
    if (!fileAssignments.has(target.path)) fileAssignments.set(target.path, new Set());
    fileAssignments.get(target.path).add(id);
  }
}

const fetchedFindings = new Map();
const processedByFile = new Map();
let pending = [...assignedToFile.keys()];

while (pending.length > 0) {
  const rows = queryFindings(pending);
  const batch = buildFindingMap(rows);
  const newlyFetched = [];

  for (const id of pending) {
    if (!batch.has(id)) continue;
    fetchedFindings.set(id, batch.get(id));
    newlyFetched.push(id);
  }

  const unresolved = pending.filter((id) => !batch.has(id));
  if (unresolved.length > 0) {
    process.stderr.write(`Missing DB finding rows for ids: ${unresolved.join(", ")}\n`);
  }

  pending = [];
  for (const target of targets) {
    const assigned = fileAssignments.get(target.path);
    if (!assigned || assigned.size === 0) continue;
    if (!processedByFile.has(target.path)) processedByFile.set(target.path, new Set());
    const processed = processedByFile.get(target.path);

    for (const id of sortNumericIds(assigned)) {
      if (processed.has(id)) continue;
      const finding = fetchedFindings.get(id);
      if (!finding) continue;
      processed.add(id);

      for (const evidence of finding.evidence || []) {
        for (const childId of collectFindingIds(evidence?.evidence_ref, true)) {
          if (existingIds.has(childId) || assignedToFile.has(childId)) continue;
          assignedToFile.set(childId, target.path);
          assigned.add(childId);
          pending.push(childId);
        }
      }
    }
  }
}

let changedFiles = 0;
for (const target of targets) {
  const assigned = fileAssignments.get(target.path);
  if (!assigned || assigned.size === 0) continue;
  const changed = target.kind === "article"
    ? writeArticleFindings(target, assigned, fetchedFindings)
    : writeDossierFindings(target, assigned, fetchedFindings);
  if (changed) changedFiles += 1;
}

const summary = {
  write,
  targets_changed: changedFiles,
  imported_findings: assignedToFile.size,
  unresolved_findings: [...assignedToFile.keys()].filter((id) => !fetchedFindings.has(id)),
};

process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);

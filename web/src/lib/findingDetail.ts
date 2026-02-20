import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { extractEvidenceLinks, type CitationEntry, type CitationLink } from "./citations";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FindingEvidenceDetail = {
  evidence_type: string;
  evidence_ref: string;
  source_quote?: string;
  source_page?: string;
  assessment?: string;
  resolved_links: CitationLink[];
};

export type FindingDetail = {
  id: string;
  summary: string;
  finding_type: string;
  confidence: string;
  claim_type: string;
  verification_status: string;
  date_of_event?: string;
  evidence: FindingEvidenceDetail[];
};

export type FindingDetailMap = Record<string, FindingDetail>;

// ---------------------------------------------------------------------------
// extractCitedFindingIds — scan citation entries for finding:* keys
// ---------------------------------------------------------------------------

export function extractCitedFindingIds(entries: CitationEntry[]): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const entry of entries) {
    if (!entry.key.startsWith("finding:")) continue;
    const id = entry.key.slice("finding:".length);
    if (seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}

// ---------------------------------------------------------------------------
// DB helpers (same pattern as findingEvidence.ts)
// ---------------------------------------------------------------------------

function candidateDbPaths(): string[] {
  const envPath = String(process.env.INVESTIGATION_DB_PATH || "").trim();
  const moduleDir = dirname(fileURLToPath(import.meta.url));
  const candidates = [
    envPath,
    resolve(process.cwd(), "investigation.db"),
    resolve(process.cwd(), "..", "investigation.db"),
    resolve(moduleDir, "..", "..", "..", "investigation.db"),
  ].filter((value): value is string => Boolean(value));
  return Array.from(new Set(candidates));
}

function isUsableDb(path: string): boolean {
  if (!existsSync(path)) return false;
  try {
    return statSync(path).size > 0;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// loadFindingDetails — DB-backed (for articles)
// ---------------------------------------------------------------------------

type DbRow = {
  id: number;
  summary: string;
  finding_type: string;
  confidence: string;
  claim_type: string;
  verification_status: string;
  date_of_event: string | null;
  evidence_type: string | null;
  evidence_ref: string | null;
  source_quote: string | null;
  source_page: string | null;
  assessment: string | null;
};

function queryFindingDetails(dbPath: string, findingIds: string[]): DbRow[] {
  if (findingIds.length === 0) return [];

  const placeholders = findingIds.map((id) => `'${id.replace(/'/g, "''")}'`).join(",");
  const sql = `
    SELECT f.id, f.summary, f.finding_type, f.confidence, f.claim_type,
           f.verification_status, f.date_of_event,
           fe.evidence_type, fe.evidence_ref, fe.source_quote,
           fe.source_page, fe.assessment
    FROM findings f
    LEFT JOIN finding_evidence fe ON fe.finding_id = f.id
    WHERE f.id IN (${placeholders})
    ORDER BY f.id;
  `;

  try {
    const output = execFileSync("sqlite3", [dbPath, ".mode json", sql], {
      encoding: "utf-8",
    }).trim();
    if (!output) return [];
    return JSON.parse(output) as DbRow[];
  } catch {
    return [];
  }
}

function groupRowsIntoDetails(rows: DbRow[]): FindingDetailMap {
  const map: FindingDetailMap = {};

  for (const row of rows) {
    const id = String(row.id);
    if (!map[id]) {
      map[id] = {
        id,
        summary: row.summary,
        finding_type: row.finding_type || "unknown",
        confidence: row.confidence || "medium",
        claim_type: row.claim_type || "inference",
        verification_status: row.verification_status || "unverified",
        date_of_event: row.date_of_event || undefined,
        evidence: [],
      };
    }

    if (row.evidence_ref) {
      map[id].evidence.push({
        evidence_type: row.evidence_type || "unknown",
        evidence_ref: row.evidence_ref,
        source_quote: row.source_quote || undefined,
        source_page: row.source_page || undefined,
        assessment: row.assessment || undefined,
        resolved_links: extractEvidenceLinks(row.evidence_ref),
      });
    }
  }

  return map;
}

export function loadFindingDetails(findingIds: string[], slug?: string): FindingDetailMap {
  if (findingIds.length === 0) return {};

  // Try DB first (local dev / local build)
  for (const dbPath of candidateDbPaths()) {
    if (!isUsableDb(dbPath)) continue;
    const rows = queryFindingDetails(dbPath, findingIds);
    if (rows.length > 0) {
      return groupRowsIntoDetails(rows);
    }
  }

  // Fallback: pre-baked JSON file (CI builds without investigation.db)
  if (slug) {
    const map = loadFindingDetailsFromFile(slug, findingIds);
    if (Object.keys(map).length > 0) return map;
  }

  return {};
}

// ---------------------------------------------------------------------------
// loadFindingDetailsFromFile — JSON file fallback (for CI builds)
// ---------------------------------------------------------------------------

function findArticleFindingsFile(slug: string): string | null {
  const candidates = [
    resolve(process.cwd(), "..", "content", "articles", `${slug}-findings.json`),
    resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "content", "articles", `${slug}-findings.json`),
  ];
  for (const p of candidates) {
    if (existsSync(p)) return p;
  }
  return null;
}

function loadFindingDetailsFromFile(slug: string, findingIds: string[]): FindingDetailMap {
  const filePath = findArticleFindingsFile(slug);
  if (!filePath) return {};

  try {
    const raw = JSON.parse(readFileSync(filePath, "utf-8")) as FindingDetailMap;
    // Re-resolve citation links (they may have changed since file was generated)
    const idSet = new Set(findingIds);
    const result: FindingDetailMap = {};
    for (const [id, detail] of Object.entries(raw)) {
      if (!idSet.has(id)) continue;
      result[id] = {
        ...detail,
        evidence: (detail.evidence || []).map((ev) => ({
          ...ev,
          resolved_links: extractEvidenceLinks(ev.evidence_ref),
        })),
      };
    }
    return result;
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// buildDossierFindingDetailMap — JSON-backed (for dossiers)
// ---------------------------------------------------------------------------

export function buildDossierFindingDetailMap(
  dossier: any,
  citedFindingIds: string[],
): FindingDetailMap {
  if (!citedFindingIds.length) return {};

  const idSet = new Set(citedFindingIds);
  const map: FindingDetailMap = {};

  for (const finding of dossier?.findings || []) {
    const id = String(finding?.id);
    if (!idSet.has(id)) continue;

    const evidence: FindingEvidenceDetail[] = [];
    for (const ev of finding?.evidence || []) {
      const ref = typeof ev?.evidence_ref === "string" ? ev.evidence_ref.trim() : "";
      if (!ref) continue;
      evidence.push({
        evidence_type: ev.evidence_type || "unknown",
        evidence_ref: ref,
        source_quote: ev.source_quote || undefined,
        source_page: ev.source_page || undefined,
        assessment: ev.assessment || undefined,
        resolved_links: extractEvidenceLinks(ref),
      });
    }

    map[id] = {
      id,
      summary: finding.summary || "",
      finding_type: finding.finding_type || "unknown",
      confidence: finding.confidence || "medium",
      claim_type: finding.claim_type || "inference",
      verification_status: finding.verification_status || "unverified",
      date_of_event: finding.date_of_event || undefined,
      evidence,
    };
  }

  return map;
}

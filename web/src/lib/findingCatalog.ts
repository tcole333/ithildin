import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export type FindingEvidenceMap = Record<string, string[]>;

export type RawFindingEvidenceDetail = {
  evidence_type: string;
  evidence_ref: string;
  source_quote?: string;
  source_page?: string;
  assessment?: string;
};

export type RawFindingDetail = {
  id: string;
  summary: string;
  finding_type: string;
  confidence: string;
  claim_type: string;
  verification_status: string;
  date_of_event?: string;
  evidence: RawFindingEvidenceDetail[];
};

export type RawFindingDetailMap = Record<string, RawFindingDetail>;

export type FindingCatalog = {
  detailMap: RawFindingDetailMap;
  evidenceMap: FindingEvidenceMap;
};

type CatalogOptions = {
  findingIds?: string[];
  /** @deprecated Ignored: use publication_snapshot.py --db for an explicit audit. */
  includeDbFallback?: boolean;
};

let cachedContentCatalog: FindingCatalog | null = null;
let cachedPublicationCatalog: FindingCatalog | null = null;

function contentRoot(): string {
  return resolve(process.env.ITHILDIN_CONTENT_DIR || resolve(process.cwd(), "..", "content"));
}

function articlesDir(): string {
  return resolve(contentRoot(), "articles");
}

function dossiersDir(): string {
  return resolve(contentRoot(), "dossiers");
}

function normalizeEvidenceItem(evidence: any): RawFindingEvidenceDetail | null {
  const evidenceRef = typeof evidence?.evidence_ref === "string" ? evidence.evidence_ref.trim() : "";
  if (!evidenceRef) return null;
  return {
    evidence_type: evidence?.evidence_type || "unknown",
    evidence_ref: evidenceRef,
    source_quote: evidence?.source_quote || undefined,
    source_page: evidence?.source_page || undefined,
    assessment: evidence?.assessment || undefined,
  };
}

function normalizeFindingRecord(finding: any): RawFindingDetail | null {
  const id = String(finding?.id || "").trim();
  if (!id) return null;
  return {
    id,
    summary: finding?.summary || "",
    finding_type: finding?.finding_type || "unknown",
    confidence: finding?.confidence || "medium",
    claim_type: finding?.claim_type || "inference",
    verification_status: finding?.verification_status || "unverified",
    date_of_event: finding?.date_of_event || undefined,
    evidence: Array.isArray(finding?.evidence)
      ? finding.evidence.map(normalizeEvidenceItem).filter((item: RawFindingEvidenceDetail | null): item is RawFindingEvidenceDetail => Boolean(item))
      : [],
  };
}

export function buildFindingEvidenceMapFromItems(
  items: Array<{ id?: string | number; evidence?: Array<{ evidence_ref?: string | null }> }> = [],
): FindingEvidenceMap {
  const map: FindingEvidenceMap = {};
  for (const item of items) {
    const id = String(item?.id || "").trim();
    if (!id) continue;
    map[id] = [];
    for (const evidence of item?.evidence || []) {
      const ref = typeof evidence?.evidence_ref === "string" ? evidence.evidence_ref.trim() : "";
      if (ref) {
        map[id].push(ref);
      }
    }
  }
  return map;
}

export function buildRawFindingDetailMapFromItems(items: any[] = []): RawFindingDetailMap {
  const detailMap: RawFindingDetailMap = {};
  for (const finding of items) {
    const normalized = normalizeFindingRecord(finding);
    if (!normalized) continue;
    detailMap[normalized.id] = normalized;
  }
  return detailMap;
}

export function catalogFromFindingItems(items: any[] = []): FindingCatalog {
  const detailMap = buildRawFindingDetailMapFromItems(items);
  return {
    detailMap,
    evidenceMap: buildFindingEvidenceMapFromItems(Object.values(detailMap)),
  };
}

function mergeDetailMaps(...maps: RawFindingDetailMap[]): RawFindingDetailMap {
  const merged: RawFindingDetailMap = {};
  for (const map of maps) {
    for (const [id, detail] of Object.entries(map || {})) {
      merged[id] = detail;
    }
  }
  return merged;
}

export function mergeFindingCatalogs(...catalogs: Array<FindingCatalog | null | undefined>): FindingCatalog {
  const publication = loadPublicationFindingCatalog();
  if (publication) return publication;
  const detailMaps = catalogs.filter(Boolean).map((catalog) => catalog!.detailMap);
  const detailMap = mergeDetailMaps(...detailMaps);
  return {
    detailMap,
    evidenceMap: buildFindingEvidenceMapFromItems(Object.values(detailMap)),
  };
}

function filterCatalog(catalog: FindingCatalog, findingIds?: string[]): FindingCatalog {
  if (!findingIds || findingIds.length === 0) return catalog;
  const idSet = new Set(findingIds.map((id) => String(id).trim()).filter(Boolean));
  const detailMap: RawFindingDetailMap = {};
  for (const id of idSet) {
    if (catalog.detailMap[id]) {
      detailMap[id] = catalog.detailMap[id];
    }
  }
  return {
    detailMap,
    evidenceMap: buildFindingEvidenceMapFromItems(Object.values(detailMap)),
  };
}

function scanArticleFindings(detailMap: RawFindingDetailMap): void {
  const dir = articlesDir();
  if (!existsSync(dir)) return;
  const files = readdirSync(dir).filter((file) => file.endsWith("-findings.json"));
  for (const fileName of files) {
    const raw = JSON.parse(readFileSync(resolve(dir, fileName), "utf-8")) as Record<string, any>;
    Object.assign(detailMap, buildRawFindingDetailMapFromItems(Object.values(raw)));
  }
}

function scanDossierFindings(detailMap: RawFindingDetailMap): void {
  const dir = dossiersDir();
  if (!existsSync(dir)) return;
  const files = readdirSync(dir).filter((file) => file.endsWith(".json") && !file.startsWith("_"));
  for (const fileName of files) {
    const dossier = JSON.parse(readFileSync(resolve(dir, fileName), "utf-8"));
    Object.assign(
      detailMap,
      buildRawFindingDetailMapFromItems([
        ...(dossier?.findings || []),
        ...(dossier?.citation_findings || []),
      ]),
    );
  }
}

export function loadContentFindingCatalog(): FindingCatalog {
  if (cachedContentCatalog) return cachedContentCatalog;
  const detailMap: RawFindingDetailMap = {};
  scanArticleFindings(detailMap);
  scanDossierFindings(detailMap);
  cachedContentCatalog = {
    detailMap,
    evidenceMap: buildFindingEvidenceMapFromItems(Object.values(detailMap)),
  };
  return cachedContentCatalog;
}

function recordFingerprint(record: any): string {
  const normalized = normalizeFindingRecord(record);
  if (!normalized) throw new Error("Publication finding is missing an id");
  normalized.evidence.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return JSON.stringify(normalized);
}

export function loadPublicationFindingCatalog(): FindingCatalog | null {
  const snapshotPath = process.env.ITHILDIN_FINDING_SNAPSHOT;
  if (!snapshotPath) return null; // Unreviewed local preview; release requires a snapshot.
  if (cachedPublicationCatalog) return cachedPublicationCatalog;
  const snapshot = JSON.parse(readFileSync(resolve(snapshotPath), "utf-8"));
  if (snapshot.schema_version !== 1 || !snapshot.source_hashes || !snapshot.findings) {
    throw new Error("Invalid publication finding snapshot");
  }
  const expectedFiles = [
    ...readdirSync(dossiersDir()).filter((file) => file.endsWith(".json") && !file.startsWith("_")).map((file) => `dossiers/${file}`),
    ...readdirSync(articlesDir()).filter((file) => file.endsWith(".mdx") || file.endsWith("-findings.json")).map((file) => `articles/${file}`),
  ].sort();
  if (JSON.stringify(expectedFiles) !== JSON.stringify(Object.keys(snapshot.source_hashes).sort())) {
    throw new Error("Publication snapshot source files changed; regenerate and review the snapshot");
  }
  for (const relative of expectedFiles) {
    const raw = readFileSync(resolve(contentRoot(), relative));
    if (createHash("sha256").update(raw).digest("hex") !== snapshot.source_hashes[relative]) {
      throw new Error(`Publication snapshot is stale: ${relative}`);
    }
    if (!relative.endsWith(".json")) continue;
    const payload = JSON.parse(raw.toString("utf-8"));
    const records = relative.endsWith("-findings.json") ? Object.values(payload)
      : [...(payload.findings || []), ...(payload.citation_findings || [])];
    for (const record of records as any[]) {
      const approved = snapshot.findings[String(record.id)];
      if (!approved || recordFingerprint(record) !== recordFingerprint(approved)) {
        throw new Error(`Finding ${record.id} differs from the publication snapshot in ${relative}`);
      }
    }
  }
  for (const [id, record] of Object.entries(snapshot.findings) as Array<[string, any]>) {
    if (String(record.id) !== id || record.verification_status !== "verified") {
      throw new Error(`Non-verified or invalid finding ${id} in publication snapshot`);
    }
  }
  cachedPublicationCatalog = catalogFromFindingItems(Object.values(snapshot.findings));
  return cachedPublicationCatalog;
}

export function loadGlobalFindingCatalog(options: CatalogOptions = {}): FindingCatalog {
  // Builds are static and deterministic. Current DB status is audited explicitly
  // by publication_snapshot.py; it is never silently merged into a web build.
  return filterCatalog(loadPublicationFindingCatalog() || loadContentFindingCatalog(), options.findingIds);
}

export function loadArticleFindingCatalog(slug: string): FindingCatalog {
  const filePath = resolve(articlesDir(), `${slug}-findings.json`);
  if (!existsSync(filePath)) {
    return { detailMap: {}, evidenceMap: {} };
  }
  const raw = JSON.parse(readFileSync(filePath, "utf-8")) as Record<string, any>;
  return catalogFromFindingItems(Object.values(raw));
}

export function loadDossierFindingCatalog(dossier: any): FindingCatalog {
  return catalogFromFindingItems([
    ...(dossier?.findings || []),
    ...(dossier?.citation_findings || []),
  ]);
}

export function loadFindingEvidenceMap(options: CatalogOptions = {}): FindingEvidenceMap {
  return loadGlobalFindingCatalog(options).evidenceMap;
}

export function loadFindingDetailMap(options: CatalogOptions = {}): RawFindingDetailMap {
  return loadGlobalFindingCatalog(options).detailMap;
}

export function findArticleFindingsFile(slug: string): string | null {
  const candidates = [
    resolve(articlesDir(), `${slug}-findings.json`),
    resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "content", "articles", `${slug}-findings.json`),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export function listContentFindingIds(): string[] {
  return Object.keys(loadContentFindingCatalog().detailMap);
}

export function findFindingOwners(findingId: string): Array<{ routeType: "article" | "dossier"; slug: string }> {
  const owners: Array<{ routeType: "article" | "dossier"; slug: string }> = [];
  const normalizedId = String(findingId).trim();
  if (!normalizedId) return owners;

  const articleDir = articlesDir();
  if (existsSync(articleDir)) {
    const files = readdirSync(articleDir).filter((file) => file.endsWith("-findings.json"));
    for (const fileName of files) {
      const raw = JSON.parse(readFileSync(resolve(articleDir, fileName), "utf-8")) as Record<string, any>;
      if (raw[normalizedId]) {
        owners.push({ routeType: "article", slug: basename(fileName, "-findings.json") });
      }
    }
  }

  const dossierDir = dossiersDir();
  if (existsSync(dossierDir)) {
    const files = readdirSync(dossierDir).filter((file) => file.endsWith(".json") && !file.startsWith("_"));
    for (const fileName of files) {
      const dossier = JSON.parse(readFileSync(resolve(dossierDir, fileName), "utf-8"));
      if ((dossier?.findings || []).some((finding: any) => String(finding?.id) === normalizedId)) {
        owners.push({ routeType: "dossier", slug: basename(fileName, ".json") });
      }
    }
  }

  return owners;
}

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, resolve } from "node:path";
import {
  applyCitations,
  createCitationState,
  extractEvidenceSourceRecords,
  type CitationEntry,
  type CitationLink,
  type SourceRecord,
} from "./citations";
import {
  loadArticleFindingCatalog,
  loadDossierFindingCatalog,
  loadGlobalFindingCatalog,
  mergeFindingCatalogs,
} from "./findingCatalog";

export type SourceOccurrence = {
  routeType: "article" | "dossier";
  slug: string;
  title: string;
  context: "inline_citation" | "finding_evidence";
  findingId?: string;
  evidenceType?: string;
  sourceQuote?: string;
  sourcePage?: string;
  assessment?: string;
};

export type CatalogSourceRecord = SourceRecord & {
  occurrences: SourceOccurrence[];
};

type CatalogMap = Record<string, CatalogSourceRecord>;

let cachedCatalog: CatalogMap | null = null;

function parseFrontmatterTitle(raw: string, fallback: string): string {
  const match = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return fallback;
  for (const line of match[1].split("\n")) {
    const titleMatch = line.match(/^title:\s*(.+)$/);
    if (titleMatch) {
      return titleMatch[1].trim().replace(/^["']|["']$/g, "");
    }
  }
  return fallback;
}

function createSourceRecordFromLink(link: CitationLink): SourceRecord | null {
  if (!link.sourceId) return null;
  const kind = link.sourceKind || (link.openUrl ? "external" : "record_only");
  return {
    id: link.sourceId,
    label: link.label,
    title: link.label,
    kind,
    canonicalRef: link.key,
    externalUrl: kind === "external" ? (link.openUrl || link.url) : undefined,
    hostedAssetUrl: kind === "hosted_copy" ? (link.openUrl || link.url) : undefined,
    archiveUrl: kind === "archived_copy" ? (link.openUrl || link.url) : link.archiveUrl,
    recordUrl: link.sourceRecordUrl || link.url || `/sources/${encodeURIComponent(link.sourceId)}`,
    sourceType: "source_record",
    accessNote: kind === "record_only"
      ? "On file; no public URL is available for this source."
      : "Public source artifact available.",
    publishValid: link.publishValid ?? true,
  };
}

function mergeRecord(target: CatalogSourceRecord | undefined, source: SourceRecord): CatalogSourceRecord {
  if (!target) {
    return { ...source, occurrences: [] };
  }
  return {
    ...target,
    label: source.label || target.label,
    title: source.title || target.title,
    kind: source.kind === "record_only" ? target.kind : source.kind,
    canonicalRef: source.canonicalRef || target.canonicalRef,
    externalUrl: source.externalUrl || target.externalUrl,
    hostedAssetUrl: source.hostedAssetUrl || target.hostedAssetUrl,
    archiveUrl: source.archiveUrl || target.archiveUrl,
    archiveLookupUrl: source.archiveLookupUrl || target.archiveLookupUrl,
    recordUrl: source.recordUrl || target.recordUrl,
    sourceType: source.sourceType || target.sourceType,
    publisherOrOrigin: source.publisherOrOrigin || target.publisherOrOrigin,
    publicationOrCaptureDate: source.publicationOrCaptureDate || target.publicationOrCaptureDate,
    pageOrLocator: source.pageOrLocator || target.pageOrLocator,
    excerptOrQuote: source.excerptOrQuote || target.excerptOrQuote,
    accessNote: source.accessNote || target.accessNote,
    integrity: source.integrity || target.integrity,
    publishValid: source.publishValid ?? target.publishValid,
    occurrences: target.occurrences,
  };
}

function addOccurrence(
  catalog: CatalogMap,
  record: SourceRecord,
  occurrence: SourceOccurrence,
): void {
  const existing = mergeRecord(catalog[record.id], record);
  existing.occurrences.push(occurrence);
  catalog[record.id] = existing;
}

function collectSourceEntries(markdown: string, findingEvidenceMap: Record<string, string[]> = {}): CitationEntry[] {
  const state = createCitationState();
  applyCitations(markdown, { findingEvidenceMap }, state);
  return state.entries.filter((entry) => entry.kind === "source");
}

function scanArticles(catalog: CatalogMap): void {
  const articlesDir = resolve(process.cwd(), "..", "content", "articles");
  if (!existsSync(articlesDir)) return;

  const articleFiles = readdirSync(articlesDir).filter((file) => file.endsWith(".mdx"));
  for (const fileName of articleFiles) {
    const slug = basename(fileName, ".mdx");
    const raw = readFileSync(resolve(articlesDir, fileName), "utf-8");
    const title = parseFrontmatterTitle(raw, slug);
    const body = raw.replace(/^---\n[\s\S]*?\n---\n*/, "");
    const findingEvidenceMap = mergeFindingCatalogs(
      loadGlobalFindingCatalog({ includeDbFallback: true }),
      loadArticleFindingCatalog(slug),
    ).evidenceMap;
    const entries = collectSourceEntries(body, findingEvidenceMap);
    for (const entry of entries) {
      const record = createSourceRecordFromLink(entry);
      if (!record || !record.publishValid) continue;
      addOccurrence(catalog, record, {
        routeType: "article",
        slug,
        title,
        context: "inline_citation",
      });
    }
  }

  const findingsFiles = readdirSync(articlesDir).filter((file) => file.endsWith("-findings.json"));
  for (const fileName of findingsFiles) {
    const articleSlug = fileName.replace(/-findings\.json$/, "");
    const raw = JSON.parse(readFileSync(resolve(articlesDir, fileName), "utf-8")) as Record<string, any>;
    const findingEvidenceMap = mergeFindingCatalogs(
      loadGlobalFindingCatalog({ includeDbFallback: true }),
      loadArticleFindingCatalog(articleSlug),
    ).evidenceMap;
    for (const [findingId, detail] of Object.entries(raw)) {
      for (const ev of detail?.evidence || []) {
        const records = extractEvidenceSourceRecords(ev.evidence_ref || "", { findingEvidenceMap });
        for (const record of records) {
          addOccurrence(catalog, {
            ...record,
            pageOrLocator: record.pageOrLocator || ev.source_page || undefined,
            excerptOrQuote: record.excerptOrQuote || ev.source_quote || undefined,
          }, {
            routeType: "article",
            slug: articleSlug,
            title: articleSlug,
            context: "finding_evidence",
            findingId,
            evidenceType: ev.evidence_type || undefined,
            sourceQuote: ev.source_quote || undefined,
            sourcePage: ev.source_page || undefined,
            assessment: ev.assessment || undefined,
          });
        }
      }
    }
  }
}

function scanDossiers(catalog: CatalogMap): void {
  const dossiersDir = resolve(process.cwd(), "..", "content", "dossiers");
  if (!existsSync(dossiersDir)) return;

  const dossierFiles = readdirSync(dossiersDir).filter((file) => file.endsWith(".json") && !file.startsWith("_"));
  for (const fileName of dossierFiles) {
    const slug = basename(fileName, ".json");
    const dossier = JSON.parse(readFileSync(resolve(dossiersDir, fileName), "utf-8"));
    const title = dossier?.name || slug;
    const findingEvidenceMap = mergeFindingCatalogs(
      loadGlobalFindingCatalog({ includeDbFallback: true }),
      loadDossierFindingCatalog(dossier),
    ).evidenceMap;

    const proseSections = [
      typeof dossier?.curation?.lead === "string" ? dossier.curation.lead : "",
      typeof dossier?.curation?.overview === "string" ? dossier.curation.overview : "",
      typeof dossier?.curation?.financial_summary === "string" ? dossier.curation.financial_summary : "",
      ...(Array.isArray(dossier?.curation?.sections) ? dossier.curation.sections.map((section: any) => section?.content || "") : []),
    ].filter(Boolean);

    for (const prose of proseSections) {
      const entries = collectSourceEntries(String(prose), findingEvidenceMap);
      for (const entry of entries) {
        const record = createSourceRecordFromLink(entry);
        if (!record || !record.publishValid) continue;
        addOccurrence(catalog, record, {
          routeType: "dossier",
          slug,
          title,
          context: "inline_citation",
        });
      }
    }

    for (const finding of dossier?.findings || []) {
      for (const ev of finding?.evidence || []) {
        const records = extractEvidenceSourceRecords(ev.evidence_ref || "", { findingEvidenceMap });
        for (const record of records) {
          addOccurrence(catalog, {
            ...record,
            pageOrLocator: record.pageOrLocator || ev.source_page || undefined,
            excerptOrQuote: record.excerptOrQuote || ev.source_quote || undefined,
          }, {
            routeType: "dossier",
            slug,
            title,
            context: "finding_evidence",
            findingId: String(finding.id),
            evidenceType: ev.evidence_type || undefined,
            sourceQuote: ev.source_quote || undefined,
            sourcePage: ev.source_page || undefined,
            assessment: ev.assessment || undefined,
          });
        }
      }
    }
  }
}

export function loadPublicSourceCatalog(): CatalogMap {
  if (cachedCatalog) return cachedCatalog;
  const catalog: CatalogMap = {};
  scanArticles(catalog);
  scanDossiers(catalog);
  cachedCatalog = catalog;
  return cachedCatalog;
}

export function listPublicSourceRecords(): CatalogSourceRecord[] {
  return Object.values(loadPublicSourceCatalog()).sort((left, right) => left.title.localeCompare(right.title));
}

export function getPublicSourceRecord(sourceId: string): CatalogSourceRecord | null {
  return loadPublicSourceCatalog()[sourceId] || null;
}

import MiniSearch, { type SearchResult } from 'minisearch';

export interface SearchDocument {
  id: string;
  type: 'dossier' | 'article' | 'model';
  title: string;
  slug: string;
  aliases: string;
  description: string;
  mentions: string;
  mentionCount: number;
  stats: string;
  href: string;
}

export interface RankedResult extends SearchDocument {
  tier: 'primary' | 'article' | 'model' | 'cross-reference';
}

let engine: MiniSearch<SearchDocument> | null = null;
let initPromise: Promise<MiniSearch<SearchDocument>> | null = null;

export function parseSearchDocuments(value: unknown): SearchDocument[] {
  if (!Array.isArray(value)) throw new Error('Search index must be a list of documents');
  const ids = new Set<string>();
  return value.map((item: unknown) => {
    if (!item || typeof item !== 'object') throw new Error('Invalid search document');
    const doc = item as Record<string, unknown>;
    for (const field of ['id', 'title', 'slug', 'href'] as const) {
      if (typeof doc[field] !== 'string' || !doc[field]) throw new Error(`Search document requires ${field}`);
    }
    if (!['dossier', 'article', 'model'].includes(String(doc.type))) throw new Error('Invalid search document type');
    if (!String(doc.href).startsWith('/') || String(doc.href).startsWith('//') || /[\x00-\x20\\]/.test(String(doc.href))) {
      throw new Error('Search result must link to a local route');
    }
    if (ids.has(doc.id as string)) throw new Error(`Duplicate search document: ${doc.id}`);
    ids.add(doc.id as string);
    for (const field of ['aliases', 'description', 'mentions', 'stats']) {
      if (doc[field] !== undefined && typeof doc[field] !== 'string') throw new Error(`Invalid search field: ${field}`);
    }
    if (doc.mentionCount !== undefined && (!Number.isInteger(doc.mentionCount) || Number(doc.mentionCount) < 0)) {
      throw new Error('Invalid search mention count');
    }
    return {
      ...doc, aliases: doc.aliases ?? '', description: doc.description ?? '',
      mentions: doc.mentions ?? '', stats: doc.stats ?? '', mentionCount: doc.mentionCount ?? 0,
    } as unknown as SearchDocument;
  });
}

export async function getSearchEngine(): Promise<MiniSearch<SearchDocument>> {
  if (engine) return engine;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    const resp = await fetch('/content/search-index.json');
    if (!resp.ok) throw new Error(`Search index request failed (${resp.status})`);
    const docs = parseSearchDocuments(await resp.json());

    const ms = new MiniSearch<SearchDocument>({
      fields: ['title', 'aliases', 'description', 'mentions'],
      storeFields: ['id', 'type', 'title', 'slug', 'aliases', 'description', 'mentions', 'mentionCount', 'stats', 'href'],
      searchOptions: {
        prefix: true,
        fuzzy: 0.2,
        boost: { title: 5, aliases: 3, description: 1, mentions: 0.5 },
      },
    });

    ms.addAll(docs);
    engine = ms;
    return ms;
  })().catch((error: unknown) => {
    // A rejected request must not poison every subsequent search opening.
    initPromise = null;
    throw error;
  });

  return initPromise;
}

function queryMatchesTitleOrAlias(query: string, doc: SearchResult): boolean {
  const q = query.toLowerCase().trim();
  const title = (doc.title as string || '').toLowerCase();
  const aliases = (doc.aliases as string || '').toLowerCase();
  return title.includes(q) || aliases.includes(q);
}

export function searchWithRanking(
  ms: MiniSearch<SearchDocument>,
  query: string,
  limit = 12,
): RankedResult[] {
  if (!query.trim()) return [];

  const raw = ms.search(query, { prefix: true, fuzzy: 0.2 });

  const primary: RankedResult[] = [];
  const articles: RankedResult[] = [];
  const models: RankedResult[] = [];
  const crossRef: RankedResult[] = [];

  for (const hit of raw) {
    const doc = hit as unknown as SearchDocument & SearchResult;

    if (doc.type === 'dossier') {
      if (queryMatchesTitleOrAlias(query, hit)) {
        primary.push({ ...doc, tier: 'primary' });
      } else {
        crossRef.push({ ...doc, tier: 'cross-reference' });
      }
    } else if (doc.type === 'article') {
      articles.push({ ...doc, tier: 'article' });
    } else {
      models.push({ ...doc, tier: 'model' });
    }
  }

  // Cross-references sorted by mentionCount descending
  crossRef.sort((a, b) => (b.mentionCount || 0) - (a.mentionCount || 0));

  return [...primary, ...articles, ...models, ...crossRef].slice(0, limit);
}

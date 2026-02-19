import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkStringify from "remark-stringify";

export type CitationLink = {
  key: string;
  label: string;
  url?: string;
};

export type CitationEntry = CitationLink & {
  number: number;
  sources?: CitationLink[];
};

type CitationOptions = {
  findingEvidenceMap?: Record<string, string[]>;
};

export type CitationState = {
  entries: CitationEntry[];
  index: Map<string, number>;
};

const FINDING_RE = /Finding\s*#\s*(\d+)/i;
const URL_RE = /https?:\/\/[^\s\]]+/gi;

// Non-EFTA source patterns
const SEC_RE = /SEC:(\d{10}-\d{2}-\d{6})/i;
const IRS990_RE = /990:(\d{9})/i;
const ACRIS_RE = /ACRIS:(\d{13,16})/i;
const CL_RE = /CL:(\d+)/i;
const FEC_RE = /FEC:([A-Za-z0-9_/-]+)/i;
const FARA_RE = /FARA:(\d+)/i;
const USVI_RE = /USVI:([A-Za-z0-9]+)/i;
const REG_RE = /REG:([A-Z]{2}):([A-Za-z0-9]+)/i;
const EDGAR_RE = /EDGAR:(\d{10}-\d{2}-\d{6})/i;
const FL_SUNBIZ_RE = /FL[-_]?SunBiz[:\s]+([A-Za-z0-9]+)/i;
const NM_SOS_RE = /NM[-_]?SoS[:\s]+([A-Za-z0-9]+)/i;
const NY_SOS_RE = /NY[-_]?SoS[:\s]+([A-Za-z0-9]+)/i;

const CITE_TOKEN_PATTERNS = [
  "EFTA\\d{6,}",
  "HOUSE_OVERSIGHT_\\d+",
  "Finding\\s*#\\s*\\d+",
  "DS10(?::[A-Za-z0-9_-]+)?",
  "SEC:\\d{10}-\\d{2}-\\d{6}",
  "EDGAR:\\d{10}-\\d{2}-\\d{6}",
  "990:\\d{9}",
  "ACRIS:\\d{13,16}",
  "CL:\\d+",
  "FEC:[A-Za-z0-9_/-]+",
  "FARA:\\d+",
  "USVI:[A-Za-z0-9]+",
  "REG:[A-Z]{2}:[A-Za-z0-9]+",
  "FL[-_]?SunBiz[:\\s]+[A-Za-z0-9]+",
  "NM[-_]?SoS[:\\s]+[A-Za-z0-9]+",
  "NY[-_]?SoS[:\\s]+[A-Za-z0-9]+",
  "https?:\\/\\/[^\\s,;)]+",
];
const CITE_TOKEN_PATTERN = CITE_TOKEN_PATTERNS.join("|");
const CITE_TOKEN_RE = new RegExp(`(?:${CITE_TOKEN_PATTERN})`, "i");

const JMAIL_BASE = "https://jmail.world/thread";

function getCiteTokenGlobalRe(): RegExp {
  return new RegExp(CITE_TOKEN_PATTERN, "gi");
}

function buildSecEdgarUrl(accession: string): string {
  const dashless = accession.replace(/-/g, "");
  return `https://www.sec.gov/Archives/edgar/data/${dashless.slice(0, 10)}/${accession}-index.htm`;
}

function build990Url(ein: string): string {
  return `https://projects.propublica.org/nonprofits/organizations/${ein}`;
}

function buildAcrisUrl(docId: string): string {
  return `https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentDetail?doc_id=${docId}`;
}

function buildCourtListenerUrl(docketId: string): string {
  return `https://www.courtlistener.com/docket/${docketId}/`;
}

function buildDs10Url(): string {
  return "/financials";
}

function buildFecCommitteeUrl(committeeId: string): string {
  return `https://www.fec.gov/data/committee/${committeeId}/`;
}

function buildFecSearchUrl(query: string): string {
  return `https://www.fec.gov/data/search/?q=${encodeURIComponent(query)}`;
}

function normalizeFecCycle(year: number): number {
  return year % 2 === 0 ? year : year + 1;
}

function buildFecReceiptsUrl(committeeId: string, year?: string): string {
  const params = new URLSearchParams({ committee_id: committeeId });
  if (year && /^\d{4}$/.test(year)) {
    const parsed = Number.parseInt(year, 10);
    if (Number.isFinite(parsed)) {
      params.set("two_year_transaction_period", String(normalizeFecCycle(parsed)));
    }
  }
  return `https://www.fec.gov/data/receipts/?${params.toString()}`;
}

function buildFaraUrl(_regNum: string): string {
  return "https://efile.fara.gov/docs/";
}

function buildRegistryUrl(jurisdiction: string, entityId: string): string {
  const builders: Record<string, (id: string) => string> = {
    FL: (id) => `https://search.sunbiz.org/Inquiry/CorporationSearch/SearchByNumber?searchNumber=${id}`,
    NY: () => "https://appext20.dos.ny.gov/corp_public/CORPSEARCH.ENTITY_SEARCH_ENTRY",
    NM: () => "https://portal.sos.state.nm.us/BFS/online/CorporationBusinessSearch",
    DE: () => "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
    USVI: () => "https://www.ltg.gov.vi/division-of-corporations/",
    UK: (id) => `https://find-and-update.company-information.service.gov.uk/company/${id}`,
  };
  const builder = builders[jurisdiction];
  return builder ? builder(entityId) : `#registry-${jurisdiction}-${entityId}`;
}

function cleanToken(value: string): string {
  return value
    .replace(/^[\s[(]+/, "")
    .replace(/[\s\])]+$/, "")
    .replace(/\s+/g, " ")
    .replace(/[.,;]+$/, "")
    .trim();
}

function cleanUrl(value: string): string {
  return value.replace(/[),.;]+$/, "");
}

function buildJmailUrl(id: string): string {
  return `${JMAIL_BASE}/${id}?view=inbox`;
}

function isExternalUrl(url?: string): boolean {
  return Boolean(url && /^https?:\/\//i.test(url));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function uniqueInOrder(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}

function sourceFingerprint(value?: string): string {
  if (!value) return "";
  return value
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/[^a-z0-9]+/g, "");
}

function resolveFecToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(FEC_RE);
  if (!match) return null;

  const rawBody = match[1];
  const body = rawBody.trim();
  const committeeMatch = body.match(/^(C\d{8})(?:([/-])(.*))?$/i);

  if (!committeeMatch) {
    return {
      key: `fec:query:${body.toLowerCase()}`,
      label: `FEC:${body}`,
      url: buildFecSearchUrl(body),
    };
  }

  const committeeId = committeeMatch[1].toUpperCase();
  const separator = committeeMatch[2] || "";
  const suffix = committeeMatch[3] || "";
  const normalizedSuffix = suffix.toLowerCase();

  if (normalizedSuffix === "schedule_a") {
    return {
      key: `fec:${committeeId}:schedule_a`,
      label: `FEC:${committeeId}/schedule_a`,
      url: buildFecReceiptsUrl(committeeId),
    };
  }

  if (separator === "-" && /^\d{4}$/.test(suffix)) {
    return {
      key: `fec:${committeeId}:${suffix}`,
      label: `FEC:${committeeId}-${suffix}`,
      url: buildFecReceiptsUrl(committeeId, suffix),
    };
  }

  return {
    key: suffix ? `fec:${committeeId}:${normalizedSuffix}` : `fec:${committeeId}`,
    label: `FEC:${committeeId}${separator}${suffix}`,
    url: buildFecCommitteeUrl(committeeId),
  };
}

function resolveFlSunBizToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(FL_SUNBIZ_RE);
  if (!match) return null;

  const entityId = match[1].toUpperCase();
  return {
    key: `reg:FL:${entityId}`,
    label: `FL-SunBiz:${entityId}`,
    url: buildRegistryUrl("FL", entityId),
  };
}

function resolveNmSosToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(NM_SOS_RE);
  if (!match) return null;

  const entityId = match[1];
  return {
    key: `reg:NM:${entityId}`,
    label: `NM-SoS:${entityId}`,
    url: buildRegistryUrl("NM", entityId),
  };
}

function resolveNySosToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(NY_SOS_RE);
  if (!match) return null;

  const entityId = match[1];
  return {
    key: `reg:NY:${entityId}`,
    label: `NY-SoS:${entityId}`,
    url: buildRegistryUrl("NY", entityId),
  };
}

function isLikelyMarkdownLinkTarget(text: string, openParenIndex: number): boolean {
  let cursor = openParenIndex - 1;
  while (cursor >= 0 && /\s/.test(text[cursor])) {
    cursor -= 1;
  }
  return cursor >= 0 && text[cursor] === "]";
}

export function createCitationState(): CitationState {
  return {
    entries: [],
    index: new Map<string, number>(),
  };
}

export function splitCitationGroup(group: string): string[] {
  const normalized = cleanToken(group);
  if (!normalized) return [];

  const tokenRe = getCiteTokenGlobalRe();
  const matches = normalized.match(tokenRe);
  if (matches && matches.length > 0) {
    const remainder = normalized
      .replace(tokenRe, "")
      .replace(/[\s,;|/]+/g, "")
      .replace(/and/gi, "")
      .trim();

    if (!remainder) {
      return uniqueInOrder(matches.map(cleanToken).filter(Boolean));
    }
  }

  return uniqueInOrder(
    normalized
      .split(";")
      .flatMap(part => part.split(","))
      .flatMap(part => part.split(/\s+and\s+/i))
      .map(cleanToken)
      .filter(Boolean),
  );
}

export function extractEvidenceLinks(raw: string): CitationLink[] {
  const links: CitationLink[] = [];
  const seen = new Set<string>();
  const add = (label: string, url?: string) => {
    const key = url || label;
    if (!key || seen.has(key)) return;
    seen.add(key);
    links.push({ key, label, url });
  };

  if (!raw) return links;

  const urls = raw.match(URL_RE) || [];
  for (const url of urls) {
    const cleaned = cleanUrl(url);
    add(cleaned, cleaned);
  }

  const eftaMatches = raw.match(/EFTA\d{6,}/gi) || [];
  for (const id of eftaMatches) {
    const normalized = id.toUpperCase();
    add(normalized, buildJmailUrl(normalized));
  }

  const houseMatches = raw.match(/HOUSE_OVERSIGHT_\d+/gi) || [];
  for (const id of houseMatches) {
    const normalized = id.toUpperCase();
    add(normalized, buildJmailUrl(normalized));
  }

  const secRefMatches = raw.match(/SEC:\d{10}-\d{2}-\d{6}/gi) || [];
  for (const ref of secRefMatches) {
    const acc = ref.replace(/SEC:/i, "");
    add(`SEC:${acc}`, buildSecEdgarUrl(acc));
  }

  const edgarRefMatches = raw.match(/EDGAR:\d{10}-\d{2}-\d{6}/gi) || [];
  for (const ref of edgarRefMatches) {
    const acc = ref.replace(/EDGAR:/i, "");
    add(`EDGAR:${acc}`, buildSecEdgarUrl(acc));
  }

  const irs990RefMatches = raw.match(/990:\d{9}/gi) || [];
  for (const ref of irs990RefMatches) {
    const ein = ref.replace(/990:/i, "");
    add(`990:${ein}`, build990Url(ein));
  }

  const acrisRefMatches = raw.match(/ACRIS:\d{13,16}/gi) || [];
  for (const ref of acrisRefMatches) {
    const docId = ref.replace(/ACRIS:/i, "");
    add(`ACRIS:${docId}`, buildAcrisUrl(docId));
  }

  const clRefMatches = raw.match(/CL:\d+/gi) || [];
  for (const ref of clRefMatches) {
    const docketId = ref.replace(/CL:/i, "");
    add(`CL:${docketId}`, buildCourtListenerUrl(docketId));
  }

  const ds10RefMatches = raw.match(/\bDS10(?::[A-Za-z0-9_-]+)?\b/gi) || [];
  for (const ref of ds10RefMatches) {
    add(ref.replace(/^ds10/i, "DS10"), buildDs10Url());
  }

  const fecRefMatches = raw.match(/FEC:[A-Za-z0-9_/-]+/gi) || [];
  for (const ref of fecRefMatches) {
    const resolved = resolveFecToken(ref);
    if (resolved) {
      add(resolved.label, resolved.url);
    }
  }

  const faraRefMatches = raw.match(/FARA:\d+/gi) || [];
  for (const ref of faraRefMatches) {
    const regNum = ref.replace(/FARA:/i, "");
    add(`FARA:${regNum}`, buildFaraUrl(regNum));
  }

  const usviRefMatches = raw.match(/USVI:[A-Za-z0-9]+/gi) || [];
  for (const ref of usviRefMatches) {
    const entityId = ref.replace(/USVI:/i, "");
    add(`USVI:${entityId}`, buildRegistryUrl("USVI", entityId));
  }

  const flSunBizMatches = raw.match(/FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+/gi) || [];
  for (const ref of flSunBizMatches) {
    const resolved = resolveFlSunBizToken(ref);
    if (resolved) add(resolved.label, resolved.url);
  }

  const nmSosMatches = raw.match(/NM[-_]?SoS[:\s]+[A-Za-z0-9]+/gi) || [];
  for (const ref of nmSosMatches) {
    const resolved = resolveNmSosToken(ref);
    if (resolved) add(resolved.label, resolved.url);
  }

  const nySosMatches = raw.match(/NY[-_]?SoS[:\s]+[A-Za-z0-9]+/gi) || [];
  for (const ref of nySosMatches) {
    const resolved = resolveNySosToken(ref);
    if (resolved) add(resolved.label, resolved.url);
  }

  const regRefMatches = raw.match(/REG:[A-Z]{2}:[A-Za-z0-9]+/gi) || [];
  for (const ref of regRefMatches) {
    const regMatch = ref.match(REG_RE);
    if (!regMatch) continue;
    const jurisdiction = regMatch[1].toUpperCase();
    const entityId = regMatch[2];
    add(`REG:${jurisdiction}:${entityId}`, buildRegistryUrl(jurisdiction, entityId));
  }

  const remainder = raw
    .replace(URL_RE, "")
    .replace(/EFTA\d{6,}/gi, "")
    .replace(/HOUSE_OVERSIGHT_\d+/gi, "")
    .replace(/SEC:\d{10}-\d{2}-\d{6}/gi, "")
    .replace(/EDGAR:\d{10}-\d{2}-\d{6}/gi, "")
    .replace(/990:\d{9}/gi, "")
    .replace(/ACRIS:\d{13,16}/gi, "")
    .replace(/CL:\d+/gi, "")
    .replace(/\bDS10(?::[A-Za-z0-9_-]+)?\b/gi, "")
    .replace(/FEC:[A-Za-z0-9_/-]+/gi, "")
    .replace(/FARA:\d+/gi, "")
    .replace(/USVI:[A-Za-z0-9]+/gi, "")
    .replace(/FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+/gi, "")
    .replace(/NM[-_]?SoS[:\s]+[A-Za-z0-9]+/gi, "")
    .replace(/NY[-_]?SoS[:\s]+[A-Za-z0-9]+/gi, "")
    .replace(/REG:[A-Z]{2}:[A-Za-z0-9]+/gi, "")
    .replace(/[;:,]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (remainder) {
    add(cleanToken(remainder));
  }

  if (links.length === 0) {
    const fallback = cleanToken(raw);
    if (fallback) add(fallback);
  }

  return links;
}

function resolveCitationToken(token: string, options: CitationOptions): Omit<CitationEntry, "number"> {
  const trimmed = cleanToken(token);
  if (!trimmed) {
    return { key: "unknown", label: "Unknown" };
  }

  const urlMatch = trimmed.match(/https?:\/\/[^\s\]]+/i);
  if (urlMatch && urlMatch[0]) {
    const url = cleanUrl(urlMatch[0]);
    return { key: url, label: url, url };
  }

  const findingMatch = trimmed.match(FINDING_RE);
  if (findingMatch) {
    const findingId = findingMatch[1];
    const rawRefs = options.findingEvidenceMap?.[findingId] || [];
    const sources: CitationLink[] = [];
    const seen = new Set<string>();

    for (const ref of rawRefs) {
      for (const link of extractEvidenceLinks(ref)) {
        if (seen.has(link.key)) continue;
        seen.add(link.key);
        sources.push(link);
      }
    }

    const url = sources.find(s => s.url)?.url;
    return {
      key: `finding:${findingId}`,
      label: `Finding #${findingId}`,
      url,
      sources: sources.length ? sources : undefined,
    };
  }

  const eftaMatches = trimmed.match(/EFTA\d{6,}/gi);
  if (eftaMatches && eftaMatches.length > 0) {
    const first = eftaMatches[0].toUpperCase();
    let label = first;
    if (eftaMatches.length > 1 && trimmed.includes("-")) {
      label = `${first}-${eftaMatches[1].toUpperCase()}`;
    }
    return { key: `efta:${label}`, label, url: buildJmailUrl(first) };
  }

  const houseMatches = trimmed.match(/HOUSE_OVERSIGHT_\d+/gi);
  if (houseMatches && houseMatches.length > 0) {
    const id = houseMatches[0].toUpperCase();
    return { key: `house:${id}`, label: id, url: buildJmailUrl(id) };
  }

  const secMatch = trimmed.match(SEC_RE);
  if (secMatch) {
    const accession = secMatch[1];
    return { key: `sec:${accession}`, label: `SEC ${accession}`, url: buildSecEdgarUrl(accession) };
  }

  const edgarMatch = trimmed.match(EDGAR_RE);
  if (edgarMatch) {
    const accession = edgarMatch[1];
    return { key: `sec:${accession}`, label: `EDGAR ${accession}`, url: buildSecEdgarUrl(accession) };
  }

  const irs990Match = trimmed.match(IRS990_RE);
  if (irs990Match) {
    const ein = irs990Match[1];
    return { key: `990:${ein}`, label: `990 EIN ${ein}`, url: build990Url(ein) };
  }

  const acrisMatch = trimmed.match(ACRIS_RE);
  if (acrisMatch) {
    const docId = acrisMatch[1];
    return { key: `acris:${docId}`, label: `ACRIS ${docId}`, url: buildAcrisUrl(docId) };
  }

  const clMatch = trimmed.match(CL_RE);
  if (clMatch) {
    const docketId = clMatch[1];
    return { key: `cl:${docketId}`, label: `CourtListener ${docketId}`, url: buildCourtListenerUrl(docketId) };
  }

  const fecResolved = resolveFecToken(trimmed);
  if (fecResolved) {
    return fecResolved;
  }

  const faraMatch = trimmed.match(FARA_RE);
  if (faraMatch) {
    const regNum = faraMatch[1];
    return { key: `fara:${regNum}`, label: `FARA #${regNum}`, url: buildFaraUrl(regNum) };
  }

  const usviMatch = trimmed.match(USVI_RE);
  if (usviMatch) {
    const entityId = usviMatch[1];
    return { key: `usvi:${entityId}`, label: `USVI ${entityId}`, url: buildRegistryUrl("USVI", entityId) };
  }

  const flSunBizResolved = resolveFlSunBizToken(trimmed);
  if (flSunBizResolved) {
    return flSunBizResolved;
  }

  const nmSosResolved = resolveNmSosToken(trimmed);
  if (nmSosResolved) {
    return nmSosResolved;
  }

  const nySosResolved = resolveNySosToken(trimmed);
  if (nySosResolved) {
    return nySosResolved;
  }

  const regMatch = trimmed.match(REG_RE);
  if (regMatch) {
    const jurisdiction = regMatch[1].toUpperCase();
    const entityId = regMatch[2];
    return {
      key: `reg:${jurisdiction}:${entityId}`,
      label: `${jurisdiction} ${entityId}`,
      url: buildRegistryUrl(jurisdiction, entityId),
    };
  }

  const ds10Match = trimmed.match(/^DS10(?::[A-Za-z0-9_-]+)?$/i);
  if (ds10Match) {
    const normalized = trimmed.replace(/^ds10/i, "DS10");
    return {
      key: `dataset:${normalized.toLowerCase()}`,
      label: normalized,
      url: buildDs10Url(),
    };
  }

  return { key: trimmed, label: trimmed };
}

/**
 * Normalize common citation patterns to canonical bracket token format.
 * Example: (Finding #2108, EFTA01296686) -> [Finding #2108, EFTA01296686]
 */
function normalizeCitationPatterns(text: string): string {
  return text.replace(/\(([^()]+)\)/g, (full, inner, offset, source) => {
    const index = typeof offset === "number" ? offset : 0;
    const content = typeof source === "string" ? source : "";

    // Keep markdown links intact: [label](https://...)
    if (isLikelyMarkdownLinkTarget(content, index)) {
      return full;
    }

    const candidate = cleanToken(String(inner));
    if (!candidate || !CITE_TOKEN_RE.test(candidate)) {
      return full;
    }

    const tokenRe = getCiteTokenGlobalRe();
    const matches = candidate.match(tokenRe);
    if (!matches || matches.length === 0) {
      return full;
    }

    const remainder = candidate
      .replace(tokenRe, "")
      .replace(/[\s,;|/]+/g, "")
      .replace(/and/gi, "")
      .trim();

    if (remainder) {
      return full;
    }

    const renderedTokens = matches
      .map(token => cleanToken(token))
      .filter(Boolean);
    if (!renderedTokens.length) {
      return full;
    }

    return `[${renderedTokens.join(", ")}]`;
  });
}

function renderCitationSuperscripts(inner: string, options: CitationOptions, citationState: CitationState, fallback: string): string {
  if (!CITE_TOKEN_RE.test(inner)) {
    return fallback;
  }

  const tokens = splitCitationGroup(inner);
  if (!tokens.length) {
    return fallback;
  }

  const resolvedTokens = tokens.map(token => resolveCitationToken(token, options));

  // If a group cites a finding and one of the finding's own evidence refs,
  // suppress the duplicate standalone source citation in that group.
  const findingSourceFingerprints = new Set<string>();
  for (const resolved of resolvedTokens) {
    if (!resolved.key.startsWith("finding:") || !resolved.sources) continue;
    for (const source of resolved.sources) {
      const byLabel = sourceFingerprint(source.label);
      const byUrl = sourceFingerprint(source.url);
      if (byLabel) findingSourceFingerprints.add(byLabel);
      if (byUrl) findingSourceFingerprints.add(byUrl);
    }
  }

  const filteredResolved: Array<Omit<CitationEntry, "number">> = [];
  const seenResolvedKeys = new Set<string>();

  for (const resolved of resolvedTokens) {
    if (!resolved.key.startsWith("finding:") && findingSourceFingerprints.size > 0) {
      const byLabel = sourceFingerprint(resolved.label);
      const byUrl = sourceFingerprint(resolved.url);
      if ((byLabel && findingSourceFingerprints.has(byLabel)) || (byUrl && findingSourceFingerprints.has(byUrl))) {
        continue;
      }
    }

    if (seenResolvedKeys.has(resolved.key)) continue;
    seenResolvedKeys.add(resolved.key);
    filteredResolved.push(resolved);
  }

  if (!filteredResolved.length) {
    return fallback;
  }

  const rendered = filteredResolved.map(resolved => {
    const key = resolved.key;
    let number = citationState.index.get(key);

    if (!number) {
      number = citationState.entries.length + 1;
      citationState.entries.push({ ...resolved, number });
      citationState.index.set(key, number);
    }

    const href = resolved.url || `#fn-${number}`;
    const external = isExternalUrl(resolved.url);
    const attrs = external ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<sup class="citation"><a href="${escapeHtml(href)}"${attrs} data-citation-number="${number}" data-citation-key="${escapeHtml(resolved.key)}" aria-label="Source ${number}: ${escapeHtml(resolved.label)}">${number}</a></sup>`;
  });

  return rendered.join("");
}

function applyCitationReplacementsToText(text: string, options: CitationOptions, citationState: CitationState): string {
  const normalized = normalizeCitationPatterns(text);
  return normalized.replace(/\[([^\]]+)\]/g, (match, inner) =>
    renderCitationSuperscripts(inner, options, citationState, match),
  );
}

function splitInlineCitationNodes(value: string): Array<{ type: "text" | "html"; value: string }> {
  const chunkRe = /(<sup class="citation">[\s\S]*?<\/sup>)/g;
  const chunks = value.split(chunkRe);
  const out: Array<{ type: "text" | "html"; value: string }> = [];
  for (const chunk of chunks) {
    if (!chunk) continue;
    if (/^<sup class="citation">[\s\S]*<\/sup>$/.test(chunk)) {
      out.push({ type: "html", value: chunk });
    } else {
      out.push({ type: "text", value: chunk });
    }
  }
  return out;
}

function transformCitationTextNodes(node: any, options: CitationOptions, citationState: CitationState, excluded = false): void {
  if (!node || typeof node !== "object") return;
  const type = typeof node.type === "string" ? node.type : "";
  const isExcluded = excluded || type === "link" || type === "linkReference" || type === "inlineCode" || type === "code";

  if (!Array.isArray(node.children)) return;

  for (let index = 0; index < node.children.length; index += 1) {
    const child = node.children[index];
    if (!child || typeof child !== "object") continue;

    if (!isExcluded && child.type === "text" && typeof child.value === "string") {
      const replaced = applyCitationReplacementsToText(child.value, options, citationState);
      if (replaced !== child.value) {
        const replacementNodes = splitInlineCitationNodes(replaced);
        node.children.splice(index, 1, ...replacementNodes);
        index += replacementNodes.length - 1;
        continue;
      }
    }

    if (!isExcluded && child.type === "html" && typeof child.value === "string") {
      const replaced = applyCitationReplacementsToText(child.value, options, citationState);
      if (replaced !== child.value) {
        child.value = replaced;
      }
      continue;
    }

    transformCitationTextNodes(child, options, citationState, isExcluded);
  }
}

export function applyCitations(markdown: string, options: CitationOptions = {}, state?: CitationState) {
  const citationState = state ?? createCitationState();

  try {
    const parser = unified().use(remarkParse).use(remarkGfm);
    const tree = parser.parse(markdown) as any;
    transformCitationTextNodes(tree, options, citationState, false);

    const output = unified()
      .use(remarkStringify, { allowDangerousHtml: true })
      .stringify(tree);

    return { markdown: output, entries: citationState.entries };
  } catch {
    // Fall back to direct text replacement if AST parsing fails.
    const replaced = applyCitationReplacementsToText(markdown, options, citationState);
    return { markdown: replaced, entries: citationState.entries };
  }
}

export function renderFootnotes(entries: CitationEntry[]): string {
  if (!entries.length) return "";

  const items = entries.map(entry => {
    const label = escapeHtml(entry.label);
    const number = entry.number;
    const external = isExternalUrl(entry.url);
    const attrs = external ? ' target="_blank" rel="noopener noreferrer"' : "";
    const link = entry.url
      ? `<a href="${escapeHtml(entry.url)}"${attrs} data-citation-number="${number}" data-citation-key="${escapeHtml(entry.key)}">${label}</a>`
      : `<span data-citation-number="${number}" data-citation-key="${escapeHtml(entry.key)}">${label}</span>`;

    let sources = "";
    if (entry.sources && entry.sources.length) {
      const sourceLinks = entry.sources
        .map(source => {
          const sourceLabel = escapeHtml(source.label);
          if (source.url) {
            const sourceAttrs = isExternalUrl(source.url) ? ' target="_blank" rel="noopener noreferrer"' : "";
            return `<a href="${escapeHtml(source.url)}"${sourceAttrs} data-source-key="${escapeHtml(source.key)}" data-parent-citation-key="${escapeHtml(entry.key)}">${sourceLabel}</a>`;
          }
          return `<span data-source-key="${escapeHtml(source.key)}" data-parent-citation-key="${escapeHtml(entry.key)}">${sourceLabel}</span>`;
        })
        .join(", ");
      sources = `<div class="citation-sources">Sources: ${sourceLinks}</div>`;
    }

    return `<li id="fn-${number}"><span class="citation-index">${number}.</span><span class="citation-entry">${link}${sources}</span></li>`;
  });

  return `
    <section class="citation-block">
      <div class="section-label">Sources</div>
      <ol class="citation-list">
        ${items.join("\n")}
      </ol>
    </section>
  `;
}

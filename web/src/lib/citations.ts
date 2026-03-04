import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkStringify from "remark-stringify";
import jmailOverridesData from "../data/jmail-overrides.json";
import clOverridesData from "../data/cl-overrides.json";
import sourceUrlOverridesData from "../data/source-urls.json";

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

export type HealthTier = "tier1" | "tier2" | "tier3" | "tier4" | "label-only";

type CitationTypeDef = {
  id: string;
  tokenPattern: string;
  healthTier: HealthTier;
  resolve(token: string, options: CitationOptions): Omit<CitationEntry, "number"> | null;
  extract(raw: string): CitationLink[];
  stripPattern?: RegExp | false;
};

const URL_RE = /https?:\/\/[^\s\]]+/gi;

const JMAIL_BASE = "https://jmail.world/thread";

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

const clOverrides: Record<string, string> = clOverridesData;
const sourceUrlOverrides: Record<string, string> = sourceUrlOverridesData;

function buildCourtListenerUrl(docketId: string): string {
  if (clOverrides[docketId]) return clOverrides[docketId];
  return `https://www.courtlistener.com/docket/${docketId}/`;
}

function buildDs10Url(): string {
  return "/financials";
}

function buildLdaUrl(registrant: string): string {
  return `https://lda.senate.gov/filings/public/filing/search/?registrant=${encodeURIComponent(registrant)}&filing_type=`;
}

function buildOpenSanctionsUrl(entityId: string): string {
  return `https://www.opensanctions.org/entities/${entityId}/`;
}

function buildDocumentCloudUrl(docId: string): string {
  return `https://www.documentcloud.org/documents/${docId}`;
}

function buildOffshoreAlertUrl(slug: string): string {
  return `https://www.offshorealert.com/${slug}/`;
}

function buildMuckRockUrl(requestId: string): string {
  return `https://www.muckrock.com/foi/${requestId}/`;
}

function buildLittleSisUrl(entityId: string): string {
  return `https://littlesis.org/entities/${entityId}`;
}

function buildIcijUrl(nodeId: string): string {
  return `https://offshoreleaks.icij.org/nodes/${nodeId}`;
}

function buildUSAspendingAwardUrl(generatedId: string): string {
  return `https://www.usaspending.gov/award/${generatedId}/`;
}

function buildUSAspendingRecipientUrl(uei: string): string {
  return `https://www.usaspending.gov/recipient/${uei}/latest`;
}

function buildMedicareUrl(npi: string): string {
  return `https://data.cms.gov/provider-data/search?search_query=${npi}`;
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

const jmailOverrides: Record<string, string> = jmailOverridesData;

function buildJmailUrl(id: string): string {
  if (jmailOverrides[id]) return jmailOverrides[id];
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
  const match = cleanToken(token).match(/FEC:([A-Za-z0-9_/-]+)/i);
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
  const match = cleanToken(token).match(/FL[-_]?SunBiz[:\s]+([A-Za-z0-9]+)/i);
  if (!match) return null;

  const entityId = match[1].toUpperCase();
  return {
    key: `reg:FL:${entityId}`,
    label: `FL-SunBiz:${entityId}`,
    url: buildRegistryUrl("FL", entityId),
  };
}

function resolveNmSosToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(/NM[-_]?SoS[:\s]+([A-Za-z0-9]+)/i);
  if (!match) return null;

  const entityId = match[1];
  return {
    key: `reg:NM:${entityId}`,
    label: `NM-SoS:${entityId}`,
    url: buildRegistryUrl("NM", entityId),
  };
}

function resolveNySosToken(token: string): Omit<CitationEntry, "number"> | null {
  const match = cleanToken(token).match(/NY[-_]?SoS[:\s]+([A-Za-z0-9]+)/i);
  if (!match) return null;

  const entityId = match[1];
  return {
    key: `reg:NY:${entityId}`,
    label: `NY-SoS:${entityId}`,
    url: buildRegistryUrl("NY", entityId),
  };
}

// ---------------------------------------------------------------------------
// Citation Type Registry
// ---------------------------------------------------------------------------

const CITATION_REGISTRY: CitationTypeDef[] = [
  {
    id: "finding",
    tokenPattern: "Finding\\s*#\\s*\\d+",
    healthTier: "label-only",
    resolve(token, options) {
      const findingMatch = token.match(/Finding\s*#\s*(\d+)/i);
      if (!findingMatch) return null;

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
    },
    extract() { return []; },
    stripPattern: false,
  },
  {
    id: "efta",
    tokenPattern: "EFTA\\d{6,}",
    healthTier: "tier4",
    resolve(token) {
      const eftaMatches = token.match(/EFTA\d{6,}/gi);
      if (!eftaMatches || eftaMatches.length === 0) return null;
      const first = eftaMatches[0].toUpperCase();
      let label = first;
      if (eftaMatches.length > 1 && token.includes("-")) {
        label = `${first}-${eftaMatches[1].toUpperCase()}`;
      }
      return { key: `efta:${label}`, label, url: buildJmailUrl(first) };
    },
    extract(raw) {
      return (raw.match(/EFTA\d{6,}/gi) || []).map(id => {
        const normalized = id.toUpperCase();
        const url = buildJmailUrl(normalized);
        return { key: url, label: normalized, url };
      });
    },
  },
  {
    id: "house_oversight",
    tokenPattern: "HOUSE_OVERSIGHT_\\d+",
    healthTier: "tier4",
    resolve(token) {
      const houseMatches = token.match(/HOUSE_OVERSIGHT_\d+/gi);
      if (!houseMatches || houseMatches.length === 0) return null;
      const id = houseMatches[0].toUpperCase();
      return { key: `house:${id}`, label: id, url: buildJmailUrl(id) };
    },
    extract(raw) {
      return (raw.match(/HOUSE_OVERSIGHT_\d+/gi) || []).map(id => {
        const normalized = id.toUpperCase();
        const url = buildJmailUrl(normalized);
        return { key: url, label: normalized, url };
      });
    },
  },
  {
    id: "sec",
    tokenPattern: "SEC:\\d{10}-\\d{2}-\\d{6}",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/SEC:(\d{10}-\d{2}-\d{6})/i);
      if (!match) return null;
      const accession = match[1];
      return { key: `sec:${accession}`, label: `SEC ${accession}`, url: buildSecEdgarUrl(accession) };
    },
    extract(raw) {
      return (raw.match(/SEC:\d{10}-\d{2}-\d{6}/gi) || []).map(ref => {
        const acc = ref.replace(/SEC:/i, "");
        const url = buildSecEdgarUrl(acc);
        return { key: url, label: `SEC:${acc}`, url };
      });
    },
  },
  {
    id: "edgar",
    tokenPattern: "EDGAR:\\d{10}-\\d{2}-\\d{6}",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/EDGAR:(\d{10}-\d{2}-\d{6})/i);
      if (!match) return null;
      const accession = match[1];
      return { key: `sec:${accession}`, label: `EDGAR ${accession}`, url: buildSecEdgarUrl(accession) };
    },
    extract(raw) {
      return (raw.match(/EDGAR:\d{10}-\d{2}-\d{6}/gi) || []).map(ref => {
        const acc = ref.replace(/EDGAR:/i, "");
        const url = buildSecEdgarUrl(acc);
        return { key: url, label: `EDGAR:${acc}`, url };
      });
    },
  },
  {
    id: "irs990",
    tokenPattern: "990:\\d{9}",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/990:(\d{9})/i);
      if (!match) return null;
      const ein = match[1];
      return { key: `990:${ein}`, label: `990 EIN ${ein}`, url: build990Url(ein) };
    },
    extract(raw) {
      return (raw.match(/990:\d{9}/gi) || []).map(ref => {
        const ein = ref.replace(/990:/i, "");
        const url = build990Url(ein);
        return { key: url, label: `990:${ein}`, url };
      });
    },
  },
  {
    id: "acris",
    tokenPattern: "ACRIS:\\d{13,16}",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/ACRIS:(\d{13,16})/i);
      if (!match) return null;
      const docId = match[1];
      return { key: `acris:${docId}`, label: `ACRIS ${docId}`, url: buildAcrisUrl(docId) };
    },
    extract(raw) {
      return (raw.match(/ACRIS:\d{13,16}/gi) || []).map(ref => {
        const docId = ref.replace(/ACRIS:/i, "");
        const url = buildAcrisUrl(docId);
        return { key: url, label: `ACRIS:${docId}`, url };
      });
    },
  },
  {
    id: "cl",
    tokenPattern: "CL:\\d+",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/CL:(\d+)/i);
      if (!match) return null;
      const docketId = match[1];
      return { key: `cl:${docketId}`, label: `CourtListener ${docketId}`, url: buildCourtListenerUrl(docketId) };
    },
    extract(raw) {
      return (raw.match(/CL:\d+/gi) || []).map(ref => {
        const docketId = ref.replace(/CL:/i, "");
        const url = buildCourtListenerUrl(docketId);
        return { key: url, label: `CL:${docketId}`, url };
      });
    },
  },
  {
    id: "fec",
    tokenPattern: "FEC:[A-Za-z0-9_/-]+",
    healthTier: "tier1",
    resolve(token) {
      return resolveFecToken(token);
    },
    extract(raw) {
      return (raw.match(/FEC:[A-Za-z0-9_/-]+/gi) || []).flatMap(ref => {
        const resolved = resolveFecToken(ref);
        if (!resolved) return [];
        return [{ key: resolved.url || resolved.label, label: resolved.label, url: resolved.url }];
      });
    },
  },
  {
    id: "fara",
    tokenPattern: "FARA:\\d+",
    healthTier: "tier3",
    resolve(token) {
      const match = token.match(/FARA:(\d+)/i);
      if (!match) return null;
      const regNum = match[1];
      return { key: `fara:${regNum}`, label: `FARA #${regNum}`, url: buildFaraUrl(regNum) };
    },
    extract(raw) {
      return (raw.match(/FARA:\d+/gi) || []).map(ref => {
        const regNum = ref.replace(/FARA:/i, "");
        const url = buildFaraUrl(regNum);
        return { key: url, label: `FARA:${regNum}`, url };
      });
    },
  },
  {
    id: "usvi",
    tokenPattern: "USVI:[A-Za-z0-9]+",
    healthTier: "tier3",
    resolve(token) {
      const match = token.match(/USVI:([A-Za-z0-9]+)/i);
      if (!match) return null;
      const entityId = match[1];
      return { key: `usvi:${entityId}`, label: `USVI ${entityId}`, url: buildRegistryUrl("USVI", entityId) };
    },
    extract(raw) {
      return (raw.match(/USVI:[A-Za-z0-9]+/gi) || []).map(ref => {
        const entityId = ref.replace(/USVI:/i, "");
        const url = buildRegistryUrl("USVI", entityId);
        return { key: url, label: `USVI:${entityId}`, url };
      });
    },
  },
  {
    id: "fl_sunbiz",
    tokenPattern: "FL[-_]?SunBiz[:\\s]+[A-Za-z0-9]+",
    healthTier: "tier1",
    resolve(token) {
      return resolveFlSunBizToken(token);
    },
    extract(raw) {
      return (raw.match(/FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+/gi) || []).flatMap(ref => {
        const resolved = resolveFlSunBizToken(ref);
        if (!resolved) return [];
        return [{ key: resolved.url || resolved.label, label: resolved.label, url: resolved.url }];
      });
    },
  },
  {
    id: "nm_sos",
    tokenPattern: "NM[-_]?SoS[:\\s]+[A-Za-z0-9]+",
    healthTier: "tier3",
    resolve(token) {
      return resolveNmSosToken(token);
    },
    extract(raw) {
      return (raw.match(/NM[-_]?SoS[:\s]+[A-Za-z0-9]+/gi) || []).flatMap(ref => {
        const resolved = resolveNmSosToken(ref);
        if (!resolved) return [];
        return [{ key: resolved.url || resolved.label, label: resolved.label, url: resolved.url }];
      });
    },
  },
  {
    id: "ny_sos",
    tokenPattern: "NY[-_]?SoS[:\\s]+[A-Za-z0-9]+",
    healthTier: "tier3",
    resolve(token) {
      return resolveNySosToken(token);
    },
    extract(raw) {
      return (raw.match(/NY[-_]?SoS[:\s]+[A-Za-z0-9]+/gi) || []).flatMap(ref => {
        const resolved = resolveNySosToken(ref);
        if (!resolved) return [];
        return [{ key: resolved.url || resolved.label, label: resolved.label, url: resolved.url }];
      });
    },
  },
  {
    id: "reg",
    tokenPattern: "REG:[A-Z]{2}:[A-Za-z0-9]+",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/REG:([A-Z]{2}):([A-Za-z0-9]+)/i);
      if (!match) return null;
      const jurisdiction = match[1].toUpperCase();
      const entityId = match[2];
      return {
        key: `reg:${jurisdiction}:${entityId}`,
        label: `${jurisdiction} ${entityId}`,
        url: buildRegistryUrl(jurisdiction, entityId),
      };
    },
    extract(raw) {
      return (raw.match(/REG:[A-Z]{2}:[A-Za-z0-9]+/gi) || []).flatMap(ref => {
        const regMatch = ref.match(/REG:([A-Z]{2}):([A-Za-z0-9]+)/i);
        if (!regMatch) return [];
        const jurisdiction = regMatch[1].toUpperCase();
        const entityId = regMatch[2];
        const url = buildRegistryUrl(jurisdiction, entityId);
        return [{ key: url, label: `REG:${jurisdiction}:${entityId}`, url }];
      });
    },
  },
  {
    id: "ds10",
    tokenPattern: "DS10(?::[A-Za-z0-9_-]+)?",
    healthTier: "label-only",
    resolve(token) {
      const match = token.match(/^DS10(?::[A-Za-z0-9_-]+)?$/i);
      if (!match) return null;
      const normalized = token.replace(/^ds10/i, "DS10");
      return {
        key: `dataset:${normalized.toLowerCase()}`,
        label: normalized,
        url: buildDs10Url(),
      };
    },
    extract(raw) {
      return (raw.match(/\bDS10(?::[A-Za-z0-9_-]+)?\b/gi) || []).map(ref => {
        const label = ref.replace(/^ds10/i, "DS10");
        const url = buildDs10Url();
        return { key: url, label, url };
      });
    },
    stripPattern: /\bDS10(?::[A-Za-z0-9_-]+)?\b/gi,
  },
  {
    id: "kpmg",
    tokenPattern: "KPMG:[A-Za-z0-9_-]+",
    healthTier: "label-only",
    resolve(token) {
      const match = token.match(/KPMG:([A-Za-z0-9_-]+)/i);
      if (!match) return null;
      const subject = match[1];
      return {
        key: `kpmg:${subject.toLowerCase()}`,
        label: `KPMG: ${subject}`,
      };
    },
    extract(raw) {
      return (raw.match(/KPMG:[A-Za-z0-9_-]+/gi) || []).flatMap(ref => {
        const m = ref.match(/KPMG:([A-Za-z0-9_-]+)/i);
        if (!m) return [];
        return [{ key: `KPMG:${m[1]}`, label: `KPMG:${m[1]}` }];
      });
    },
  },
  {
    id: "lda",
    tokenPattern: "LDA:[A-Za-z0-9_ -]+",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/LDA:([A-Za-z0-9_ -]+)/i);
      if (!match) return null;
      const registrant = match[1].trim();
      return {
        key: `lda:${registrant.toLowerCase()}`,
        label: `LDA: ${registrant}`,
        url: buildLdaUrl(registrant),
      };
    },
    extract(raw) {
      return (raw.match(/LDA:[A-Za-z0-9_ -]+/gi) || []).flatMap(ref => {
        const m = ref.match(/LDA:([A-Za-z0-9_ -]+)/i);
        if (!m) return [];
        const registrant = m[1].trim();
        const url = buildLdaUrl(registrant);
        return [{ key: url, label: `LDA:${registrant}`, url }];
      });
    },
  },
  {
    id: "opensanctions",
    tokenPattern: "OpenSanctions:[A-Za-z0-9]+",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/OpenSanctions:([A-Za-z0-9]+)/i);
      if (!match) return null;
      const entityId = match[1];
      return {
        key: `opensanctions:${entityId}`,
        label: `OpenSanctions ${entityId}`,
        url: buildOpenSanctionsUrl(entityId),
      };
    },
    extract(raw) {
      return (raw.match(/OpenSanctions:[A-Za-z0-9]+/gi) || []).flatMap(ref => {
        const m = ref.match(/OpenSanctions:([A-Za-z0-9]+)/i);
        if (!m) return [];
        const url = buildOpenSanctionsUrl(m[1]);
        return [{ key: url, label: `OpenSanctions:${m[1]}`, url }];
      });
    },
  },
  {
    id: "documentcloud",
    tokenPattern: "DOCUMENTCLOUD:\\d+",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/DOCUMENTCLOUD:(\d+)/i);
      if (!match) return null;
      const docId = match[1];
      return {
        key: `documentcloud:${docId}`,
        label: `DocumentCloud ${docId}`,
        url: buildDocumentCloudUrl(docId),
      };
    },
    extract(raw) {
      return (raw.match(/DOCUMENTCLOUD:\d+/gi) || []).map(ref => {
        const docId = ref.replace(/DOCUMENTCLOUD:/i, "");
        const url = buildDocumentCloudUrl(docId);
        return { key: url, label: `DOCUMENTCLOUD:${docId}`, url };
      });
    },
  },
  {
    id: "offshorealert",
    tokenPattern: "OffshoreAlert:[A-Za-z0-9_-]+",
    healthTier: "tier3",
    resolve(token) {
      const match = token.match(/OffshoreAlert:([A-Za-z0-9_-]+)/i);
      if (!match) return null;
      const slug = match[1];
      return {
        key: `offshorealert:${slug.toLowerCase()}`,
        label: `OffshoreAlert:${slug}`,
        url: buildOffshoreAlertUrl(slug),
      };
    },
    extract(raw) {
      return (raw.match(/OffshoreAlert:[A-Za-z0-9_-]+/gi) || []).flatMap(ref => {
        const m = ref.match(/OffshoreAlert:([A-Za-z0-9_-]+)/i);
        if (!m) return [];
        const url = buildOffshoreAlertUrl(m[1]);
        return [{ key: url, label: `OffshoreAlert:${m[1]}`, url }];
      });
    },
  },
  {
    id: "muckrock",
    tokenPattern: "MUCKROCK:\\d+(?:\\/[A-Za-z0-9_.-]+)?",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/MUCKROCK:(\d+)(?:\/([A-Za-z0-9_.-]+))?/i);
      if (!match) return null;
      const requestId = match[1];
      const fileName = match[2];
      const label = fileName ? `MuckRock ${requestId}/${fileName}` : `MuckRock ${requestId}`;
      return {
        key: `muckrock:${requestId}`,
        label,
        url: buildMuckRockUrl(requestId),
      };
    },
    extract(raw) {
      return (raw.match(/MUCKROCK:\d+(?:\/[A-Za-z0-9_.-]+)?/gi) || []).flatMap(ref => {
        const m = ref.match(/MUCKROCK:(\d+)(?:\/([A-Za-z0-9_.-]+))?/i);
        if (!m) return [];
        const url = buildMuckRockUrl(m[1]);
        const label = m[2] ? `MUCKROCK:${m[1]}/${m[2]}` : `MUCKROCK:${m[1]}`;
        return [{ key: url, label, url }];
      });
    },
  },
  {
    id: "littlesis",
    tokenPattern: "LittleSis[_:]?\\d+",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/LittleSis[_:]?(\d+)/i);
      if (!match) return null;
      const entityId = match[1];
      return {
        key: `littlesis:${entityId}`,
        label: `LittleSis ${entityId}`,
        url: buildLittleSisUrl(entityId),
      };
    },
    extract(raw) {
      return (raw.match(/LittleSis[_:]\d+/gi) || []).flatMap(ref => {
        const m = ref.match(/LittleSis[_:](\d+)/i);
        if (!m) return [];
        const url = buildLittleSisUrl(m[1]);
        return [{ key: url, label: `LittleSis:${m[1]}`, url }];
      });
    },
  },
  {
    id: "icij",
    tokenPattern: "ICIJ(?:-PP|-node)?[:\\s]\\d+",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/ICIJ(?:-PP|-node)?[:\s](\d+)/i);
      if (!match) return null;
      const nodeId = match[1];
      return {
        key: `icij:${nodeId}`,
        label: `ICIJ ${nodeId}`,
        url: buildIcijUrl(nodeId),
      };
    },
    extract(raw) {
      return (raw.match(/ICIJ(?:-PP|-node)?[:\s]\d+/gi) || []).flatMap(ref => {
        const m = ref.match(/ICIJ(?:-PP|-node)?[:\s](\d+)/i);
        if (!m) return [];
        const url = buildIcijUrl(m[1]);
        return [{ key: url, label: ref.trim(), url }];
      });
    },
  },
  {
    id: "usaspending",
    tokenPattern: "USASPENDING:(?:RECIPIENT:)?[A-Za-z0-9_-]+",
    healthTier: "tier1",
    resolve(token) {
      const recipientMatch = token.match(/USASPENDING:RECIPIENT:([A-Za-z0-9_-]+)/i);
      if (recipientMatch) {
        const uei = recipientMatch[1];
        return {
          key: `usaspending:recipient:${uei.toLowerCase()}`,
          label: `USAspending Recipient ${uei}`,
          url: buildUSAspendingRecipientUrl(uei),
        };
      }
      const awardMatch = token.match(/USASPENDING:([A-Za-z0-9_-]+)/i);
      if (awardMatch) {
        const awardId = awardMatch[1];
        return {
          key: `usaspending:award:${awardId.toLowerCase()}`,
          label: `USAspending Award ${awardId}`,
          url: buildUSAspendingAwardUrl(awardId),
        };
      }
      return null;
    },
    extract(raw) {
      const results: CitationLink[] = [];
      const awardRefs = raw.match(/USASPENDING:(?:RECIPIENT:)?[A-Za-z0-9_-]+/gi) || [];
      for (const ref of awardRefs) {
        const recipientMatch = ref.match(/USASPENDING:RECIPIENT:([A-Za-z0-9_-]+)/i);
        if (recipientMatch) {
          const uei = recipientMatch[1];
          results.push({ key: buildUSAspendingRecipientUrl(uei), label: `USASPENDING:RECIPIENT:${uei}`, url: buildUSAspendingRecipientUrl(uei) });
          continue;
        }
        const awardMatch = ref.match(/USASPENDING:([A-Za-z0-9_-]+)/i);
        if (awardMatch) {
          const awardId = awardMatch[1];
          results.push({ key: buildUSAspendingAwardUrl(awardId), label: `USASPENDING:${awardId}`, url: buildUSAspendingAwardUrl(awardId) });
        }
      }
      return results;
    },
    stripPattern: /USASPENDING:(?:RECIPIENT:)?[A-Za-z0-9_-]+/gi,
  },
  {
    id: "medicare",
    tokenPattern: "MEDICARE:\\d{10}",
    healthTier: "tier1",
    resolve(token) {
      const match = token.match(/MEDICARE:(\d{10})/i);
      if (!match) return null;
      const npi = match[1];
      return {
        key: `medicare:${npi}`,
        label: `Medicare Provider ${npi}`,
        url: buildMedicareUrl(npi),
      };
    },
    extract(raw) {
      return (raw.match(/MEDICARE:\d{10}/gi) || []).map(ref => {
        const npi = ref.split(":")[1];
        const url = buildMedicareUrl(npi);
        return { key: url, label: `MEDICARE:${npi}`, url };
      });
    },
  },
  {
    id: "ppp",
    tokenPattern: "PPP:[A-Za-z0-9_-]+",
    healthTier: "tier2",
    resolve(token) {
      const match = token.match(/PPP:([A-Za-z0-9_-]+)/i);
      if (!match) return null;
      const loanRef = match[1];
      return {
        key: `ppp:${loanRef.toLowerCase()}`,
        label: `PPP Loan ${loanRef}`,
        url: `https://data.sba.gov/dataset/ppp-foia`,
      };
    },
    extract(raw) {
      return (raw.match(/PPP:[A-Za-z0-9_-]+/gi) || []).map(ref => {
        const loanRef = ref.split(":")[1];
        return { key: `ppp:${loanRef.toLowerCase()}`, label: ref, url: `https://data.sba.gov/dataset/ppp-foia` };
      });
    },
  },
];

// ---------------------------------------------------------------------------
// Derived patterns from registry
// ---------------------------------------------------------------------------

const CITE_TOKEN_PATTERNS = [
  ...CITATION_REGISTRY.map(t => t.tokenPattern),
  "https?:\\/\\/[^\\s,;)]+",
];
const CITE_TOKEN_PATTERN = CITE_TOKEN_PATTERNS.join("|");
const CITE_TOKEN_RE = new RegExp(`(?:${CITE_TOKEN_PATTERN})`, "i");

function getCiteTokenGlobalRe(): RegExp {
  return new RegExp(CITE_TOKEN_PATTERN, "gi");
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

// ---------------------------------------------------------------------------
// extractEvidenceLinks — registry-driven
// ---------------------------------------------------------------------------

export function extractEvidenceLinks(raw: string): CitationLink[] {
  const links: CitationLink[] = [];
  const seen = new Set<string>();
  const add = (link: CitationLink) => {
    if (!link.key || seen.has(link.key)) return;
    seen.add(link.key);
    links.push(link);
  };

  if (!raw) return links;

  // URLs first (not in registry)
  const urls = raw.match(URL_RE) || [];
  for (const url of urls) {
    const cleaned = cleanUrl(url);
    add({ key: cleaned, label: cleaned, url: cleaned });
  }

  // Each registered type
  for (const type of CITATION_REGISTRY) {
    for (const link of type.extract(raw)) add(link);
  }

  // Remainder: strip all known patterns, add leftover as label
  let remainder = raw.replace(URL_RE, "");
  for (const type of CITATION_REGISTRY) {
    if (type.stripPattern === false) continue;
    const strip = type.stripPattern ?? new RegExp(type.tokenPattern, "gi");
    remainder = remainder.replace(strip, "");
  }
  remainder = remainder.replace(/[;:,]+/g, " ").replace(/\s+/g, " ").trim();

  if (remainder) {
    const cleanedRemainder = cleanToken(remainder);
    const remainderOverride = sourceUrlOverrides[cleanedRemainder];
    if (remainderOverride) {
      add({ key: cleanedRemainder, label: cleanedRemainder, url: remainderOverride });
    } else {
      add({ key: cleanedRemainder, label: cleanedRemainder });
    }
  }

  if (links.length === 0) {
    const fallback = cleanToken(raw);
    if (fallback) {
      const fallbackOverride = sourceUrlOverrides[fallback];
      if (fallbackOverride) {
        add({ key: fallback, label: fallback, url: fallbackOverride });
      } else {
        add({ key: fallback, label: fallback });
      }
    }
  }

  return links;
}

// ---------------------------------------------------------------------------
// resolveCitationToken — registry-driven
// ---------------------------------------------------------------------------

function resolveCitationToken(token: string, options: CitationOptions): Omit<CitationEntry, "number"> {
  const trimmed = cleanToken(token);
  if (!trimmed) {
    return { key: "unknown", label: "Unknown" };
  }

  // URL citations (not in registry)
  const urlMatch = trimmed.match(/https?:\/\/[^\s\]]+/i);
  if (urlMatch && urlMatch[0]) {
    const url = cleanUrl(urlMatch[0]);
    return { key: url, label: url, url };
  }

  // Walk the registry
  for (const type of CITATION_REGISTRY) {
    const result = type.resolve(trimmed, options);
    if (result) return result;
  }

  // Check source-urls.json override as last resort
  const overrideUrl = sourceUrlOverrides[trimmed];
  if (overrideUrl) {
    return { key: trimmed, label: trimmed, url: overrideUrl };
  }

  return { key: trimmed, label: trimmed };
}

// ---------------------------------------------------------------------------
// Health tier lookup (for optional use by check-citation-health.mjs)
// ---------------------------------------------------------------------------

export function getCitationHealthTier(citationKey: string): HealthTier | "skip" {
  const prefix = citationKey.split(":")[0];
  const type = CITATION_REGISTRY.find(t => t.id === prefix);
  return type?.healthTier ?? "skip";
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

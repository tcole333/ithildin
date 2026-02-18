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

const EFTA_RE = /EFTA\d{6,}/g;
const HOUSE_RE = /HOUSE_OVERSIGHT_\d+/g;
const FINDING_RE = /Finding\s*#\s*(\d+)/i;
const URL_RE = /https?:\/\/[^\s\]]+/g;
const CITE_TOKEN_RE = /(EFTA\d{6,}|HOUSE_OVERSIGHT_\d+|Finding\s*#\s*\d+|https?:\/\/)/i;

const JMAIL_BASE = "https://jmail.world/thread";

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

export function splitCitationGroup(group: string): string[] {
  return group
    .split(";")
    .flatMap(part => part.split(","))
    .flatMap(part => part.split("/"))
    .flatMap(part => part.split(/\s+and\s+/i))
    .map(cleanToken)
    .filter(Boolean);
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

  const eftaMatches = raw.match(EFTA_RE) || [];
  for (const id of eftaMatches) {
    add(id, buildJmailUrl(id));
  }

  const houseMatches = raw.match(HOUSE_RE) || [];
  for (const id of houseMatches) {
    add(id, buildJmailUrl(id));
  }

  const remainder = raw
    .replace(URL_RE, "")
    .replace(EFTA_RE, "")
    .replace(HOUSE_RE, "")
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

  const urlMatch = trimmed.match(URL_RE);
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

  const eftaMatches = trimmed.match(EFTA_RE);
  if (eftaMatches && eftaMatches.length > 0) {
    let label = eftaMatches[0];
    if (eftaMatches.length > 1 && trimmed.includes("-")) {
      label = `${eftaMatches[0]}-${eftaMatches[1]}`;
    }
    return { key: `efta:${label}`, label, url: buildJmailUrl(eftaMatches[0]) };
  }

  const houseMatches = trimmed.match(HOUSE_RE);
  if (houseMatches && houseMatches.length > 0) {
    return { key: `house:${houseMatches[0]}`, label: houseMatches[0], url: buildJmailUrl(houseMatches[0]) };
  }

  if (/^DS10$/i.test(trimmed)) {
    return { key: "dataset:ds10", label: "DS10", url: "/financials" };
  }

  return { key: trimmed, label: trimmed };
}

export function applyCitations(markdown: string, options: CitationOptions = {}) {
  const entries: CitationEntry[] = [];
  const index = new Map<string, number>();

  const replaced = markdown.replace(/\[([^\]]+)\]/g, (match, inner) => {
    if (!CITE_TOKEN_RE.test(inner)) {
      return match;
    }

    const tokens = splitCitationGroup(inner);
    if (!tokens.length) {
      return match;
    }

    const rendered = tokens.map(token => {
      const resolved = resolveCitationToken(token, options);
      const key = resolved.key;
      let number = index.get(key);
      if (!number) {
        number = entries.length + 1;
        entries.push({ ...resolved, number });
        index.set(key, number);
      }

      const href = resolved.url || `#fn-${number}`;
      const external = isExternalUrl(resolved.url);
      const attrs = external ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<sup class="citation"><a href="${escapeHtml(href)}"${attrs} aria-label="Source ${number}: ${escapeHtml(resolved.label)}">${number}</a></sup>`;
    });

    return rendered.join("");
  });

  return { markdown: replaced, entries };
}

export function renderFootnotes(entries: CitationEntry[]): string {
  if (!entries.length) return "";

  const items = entries.map(entry => {
    const label = escapeHtml(entry.label);
    const number = entry.number;
    const external = isExternalUrl(entry.url);
    const attrs = external ? ' target="_blank" rel="noopener noreferrer"' : "";
    const link = entry.url
      ? `<a href="${escapeHtml(entry.url)}"${attrs}>${label}</a>`
      : label;

    let sources = "";
    if (entry.sources && entry.sources.length) {
      const sourceLinks = entry.sources
        .map(source => {
          const sourceLabel = escapeHtml(source.label);
          if (source.url) {
            const sourceAttrs = isExternalUrl(source.url) ? ' target="_blank" rel="noopener noreferrer"' : "";
            return `<a href="${escapeHtml(source.url)}"${sourceAttrs}>${sourceLabel}</a>`;
          }
          return sourceLabel;
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

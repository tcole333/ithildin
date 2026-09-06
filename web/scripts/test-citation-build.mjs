import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

const distRoot = resolve(process.cwd(), 'dist');
const contentRoot = resolve(process.env.ITHILDIN_CONTENT_DIR || '../content');
assert.ok(existsSync(contentRoot), `Selected publication content directory is missing: ${contentRoot}`);
assert.ok(existsSync(resolve(distRoot, 'index.html')), 'Built publication index.html is missing');

function filesIn(directory, extension) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory).filter(name => name.endsWith(extension) && !name.startsWith('_')).sort();
}

function expectedPages() {
  const pages = [];
  const redirectsPath = resolve(contentRoot, 'dossiers/_redirects.json');
  const redirects = existsSync(redirectsPath) ? JSON.parse(readFileSync(redirectsPath, 'utf8')) : {};
  const dossierSlugs = new Set();
  for (const name of filesIn(resolve(contentRoot, 'articles'), '.mdx')) {
    const prose = readFileSync(resolve(contentRoot, 'articles', name), 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n*/, '');
    pages.push({ route: `articles/${name.slice(0, -4)}`, prose });
  }
  for (const name of filesIn(resolve(contentRoot, 'dossiers'), '.json')) {
    const slug = name.slice(0, -5);
    dossierSlugs.add(slug);
    if (redirects[slug]) {
      pages.push({ route: `dossiers/${slug}`, redirect: redirects[slug] });
      continue;
    }
    const dossier = JSON.parse(readFileSync(resolve(contentRoot, 'dossiers', name), 'utf8'));
    const curation = dossier.curation || {};
    const sections = Array.isArray(curation.sections) ? curation.sections : [];
    const prose = [curation.lead, ...sections.map(section => section.content),
      ...(sections.length ? [] : [curation.overview, curation.financial_summary])]
      .filter(value => typeof value === 'string').join('\n');
    pages.push({ route: `dossiers/${slug}`, prose });
  }
  for (const [slug, target] of Object.entries(redirects)) {
    if (!dossierSlugs.has(slug)) pages.push({ route: `dossiers/${slug}`, redirect: target });
  }
  return pages;
}

function attributes(tag) {
  return Object.fromEntries(Array.from(tag.matchAll(/([\w-]+)=(?:"([^"]*)"|'([^']*)')/g), match => [match[1], match[2] ?? match[3]]));
}

let pageCount = 0;
let citationCount = 0;
let hasFindingCitations = false;
for (const { route, prose, redirect } of expectedPages()) {
  const pagePath = resolve(distRoot, route, 'index.html');
  assert.ok(existsSync(pagePath), `Selected publication page is missing from build: ${route}`);
  const html = readFileSync(pagePath, 'utf8');
  if (redirect) {
    const expectedTarget = `/dossiers/${redirect}`;
    const refreshes = Array.from(html.matchAll(/<meta\b[^>]*>/gi), match => attributes(match[0]))
      .filter(meta => meta['http-equiv']?.toLowerCase() === 'refresh');
    assert.ok(refreshes.some(meta => meta.content === `0;url=${expectedTarget}`), `Redirect ${route} does not target ${expectedTarget}`);
    const targetPath = resolve(distRoot, `.${expectedTarget}`, 'index.html');
    assert.ok(targetPath.startsWith(`${distRoot}/`) && existsSync(targetPath), `Redirect target ${expectedTarget} is missing`);
    pageCount += 1;
    continue;
  }
  const visibleHtml = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  // Dossier finding cards can quote unprocessed source text outside curated
  // prose. The article body is rendered entirely by the citation pipeline.
  if (route.startsWith('articles/')) {
    assert.ok(!/\[(?:Findings?\s*#\s*\d|NYDFS-|EFTA\d{8}|REG:)[^\]]*\]/i.test(visibleHtml), `Raw citation token remained in ${route}`);
  }
  assert.ok(!/href=["']#registry-VI-/i.test(visibleHtml), `Dead VI registry link remained in ${route}`);
  const anchors = Array.from(visibleHtml.matchAll(/<a\b[^>]*>/gi), match => attributes(match[0]));
  const citations = anchors.filter(anchor => anchor['data-citation-key']);
  const citationKeys = new Set(citations.map(anchor => anchor['data-citation-key']));
  // Independently check ordinary finding/group syntax against emitted anchors.
  // A removed citation must not pass merely because no raw token survives.
  for (const group of prose.matchAll(/\[Findings?\s*#\s*\d+(?:\s*,\s*#?\s*\d+)*\]/gi)) {
    for (const findingId of group[0].match(/\d+/g)) {
      assert.ok(citationKeys.has(`finding:${findingId}`), `Finding #${findingId} citation is missing from ${route}`);
    }
  }
  if (/\[(?:NYDFS-|EFTA\d{8}|REG:)[^\]]*\]/i.test(prose)) {
    assert.ok(anchors.some(anchor => anchor.href?.startsWith('/sources/')), `Source-record links are missing from ${route}`);
  }
  for (const anchor of citations) {
    assert.ok(anchor.href, `Citation ${anchor['data-citation-key']} has no target in ${route}`);
    if (anchor['data-citation-key'].startsWith('finding:')) {
      hasFindingCitations = true;
      assert.match(anchor.href, /^#fn-\d+$/, `Finding citation must target its footnote in ${route}`);
      assert.ok(visibleHtml.includes(`id="${anchor.href.slice(1)}"`) || visibleHtml.includes(`id='${anchor.href.slice(1)}'`), `Citation footnote ${anchor.href} is missing from ${route}`);
    }
  }
  for (const anchor of anchors.filter(anchor => anchor.href?.startsWith('/sources/'))) {
    const target = new URL(anchor.href, 'https://publication.invalid').pathname;
    const targetPath = resolve(distRoot, `.${decodeURIComponent(target)}`, 'index.html');
    assert.ok(targetPath.startsWith(`${distRoot}/`) && existsSync(targetPath), `Source-record page ${target} linked from ${route} is missing`);
  }
  pageCount += 1;
  citationCount += citations.length;
}

if (hasFindingCitations) {
  const assetRoot = resolve(distRoot, '_astro');
  const bootstrapFiles = filesIn(assetRoot, '.js').filter(name => name.startsWith('evidencePageBootstrap.'));
  assert.ok(bootstrapFiles.length, 'Built assets should include the shared evidence bootstrap bundle.');
  const bootstrapSource = bootstrapFiles.map(name => readFileSync(resolve(assetRoot, name), 'utf8')).join('\n');
  assert.ok(bootstrapSource.includes('finding-detail-data'), 'Shared evidence bootstrap should initialize finding popovers.');
  assert.ok(bootstrapSource.includes('data-evidence-page'), 'Shared evidence bootstrap should initialize support mode when present.');
}

process.stdout.write(`Citation build checks passed: ${pageCount} selected pages, ${citationCount} citation anchors.\n`);

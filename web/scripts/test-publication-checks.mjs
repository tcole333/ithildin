/** Exercise publication gate CLIs against a selected synthetic publication. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';

const webRoot = process.cwd();
const temporary = mkdtempSync(resolve(tmpdir(), 'osint-publication-checks-'));
let checks = 0;
const write = (file, value) => {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, value);
};
const pageHtml = (id) => `<html><a href="#fn-1" data-citation-key="finding:${id}">1</a><li id="fn-1"><a href="/sources/selected-record">Primary source</a></li></html>`;

function fixture(name) {
  const root = resolve(temporary, name);
  const content = resolve(root, 'selected');
  write(resolve(content, 'articles/alternate-article.mdx'), '---\ntitle: Alternate article\n---\nClaim [Finding #596]. Source [NYDFS-Consent-Order-2020-p8].');
  write(resolve(content, 'dossiers/alternate-dossier.json'), JSON.stringify({ name: 'Alternate dossier', findings: [], curation: { lead: 'Claim [Finding #597].' } }));
  write(resolve(root, 'dist/index.html'), '<html>Selected publication</html>');
  write(resolve(root, 'dist/articles/alternate-article/index.html'), pageHtml(596));
  write(resolve(root, 'dist/dossiers/alternate-dossier/index.html'), pageHtml(597));
  write(resolve(root, 'dist/sources/selected-record/index.html'), '<html>Primary source</html>');
  write(resolve(root, 'dist/_astro/evidencePageBootstrap.fixture.js'), 'finding-detail-data;data-evidence-page');
  const env = { ...process.env, ITHILDIN_CONTENT_DIR: content };
  delete env.ITHILDIN_FINDING_SNAPSHOT;
  return { root, content, env };
}

function buildCheck(name, mutate, expectedError, expectedOutput = /2 selected pages, 2 citation anchors/) {
  const data = fixture(name);
  mutate?.(data);
  const result = spawnSync(process.execPath, [resolve(webRoot, 'scripts/test-citation-build.mjs')], {
    cwd: data.root, env: data.env, encoding: 'utf8', timeout: 30_000,
  });
  assert.ifError(result.error);
  if (expectedError) {
    assert.notEqual(result.status, 0, `${name} must fail`);
    assert.match(result.stderr, expectedError);
  } else {
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, expectedOutput);
  }
  checks += 1;
}

try {
  buildCheck('alternate-slugs');
  buildCheck('missing-build', ({ root }) => rmSync(resolve(root, 'dist'), { recursive: true }), /Built publication index.html is missing/);
  buildCheck('missing-content', ({ content }) => rmSync(content, { recursive: true }), /Selected publication content directory is missing/);
  buildCheck('missing-article', ({ root }) => rmSync(resolve(root, 'dist/articles'), { recursive: true }), /Selected publication page is missing.*alternate-article/);
  buildCheck('missing-dossier', ({ root }) => rmSync(resolve(root, 'dist/dossiers'), { recursive: true }), /Selected publication page is missing.*alternate-dossier/);
  buildCheck('removed-finding-citation', ({ root }) => write(resolve(root, 'dist/articles/alternate-article/index.html'), '<html>Claim with its citation removed.</html>'), /Finding #596 citation is missing/);
  buildCheck('raw-nydfs-citation', ({ root }) => write(resolve(root, 'dist/articles/alternate-article/index.html'), pageHtml(596) + '[NYDFS-Consent-Order-2020-p8]'), /Raw citation token/);
  buildCheck('dead-registry-anchor', ({ root }) => write(resolve(root, 'dist/articles/alternate-article/index.html'), pageHtml(596) + '<a href="#registry-VI-123">Registry</a>'), /Dead VI registry link/);
  buildCheck('missing-footnote', ({ root }) => write(resolve(root, 'dist/dossiers/alternate-dossier/index.html'), '<a href="#fn-1" data-citation-key="finding:597">1</a>'), /Citation footnote #fn-1 is missing/);
  buildCheck('missing-source-record', ({ root }) => rmSync(resolve(root, 'dist/sources'), { recursive: true }), /Source-record page .* is missing/);
  buildCheck('missing-bootstrap', ({ root }) => rmSync(resolve(root, 'dist/_astro'), { recursive: true }), /shared evidence bootstrap bundle/);
  buildCheck('broken-bootstrap', ({ root }) => write(resolve(root, 'dist/_astro/evidencePageBootstrap.fixture.js'), 'unrelated script'), /initialize finding popovers/);
  const redirect = (target) => `<meta http-equiv="refresh" content="0;url=/dossiers/${target}">`;
  buildCheck('redirected-old-prose', ({ root, content }) => {
    write(resolve(content, 'dossiers/_redirects.json'), JSON.stringify({ 'alternate-dossier': 'current-dossier' }));
    write(resolve(content, 'dossiers/current-dossier.json'), JSON.stringify({ name: 'Current dossier', findings: [], curation: { lead: 'Claim [Finding #599].' } }));
    write(resolve(root, 'dist/dossiers/current-dossier/index.html'), pageHtml(599));
    write(resolve(root, 'dist/dossiers/alternate-dossier/index.html'), redirect('current-dossier'));
  }, null, /3 selected pages, 2 citation anchors/);
  buildCheck('redirect-only-alias', ({ root, content }) => {
    write(resolve(content, 'dossiers/_redirects.json'), JSON.stringify({ 'old-alias': 'alternate-dossier' }));
    write(resolve(root, 'dist/dossiers/old-alias/index.html'), redirect('alternate-dossier'));
  }, null, /3 selected pages, 2 citation anchors/);
  buildCheck('missing-redirect-target', ({ root, content }) => {
    write(resolve(content, 'dossiers/_redirects.json'), JSON.stringify({ 'alternate-dossier': 'missing-target' }));
    write(resolve(root, 'dist/dossiers/alternate-dossier/index.html'), redirect('missing-target'));
  }, /Redirect target .* is missing/);
  buildCheck('wrong-redirect-target', ({ root, content }) => {
    write(resolve(content, 'dossiers/_redirects.json'), JSON.stringify({ 'alternate-dossier': 'current-dossier' }));
    write(resolve(root, 'dist/dossiers/alternate-dossier/index.html'), redirect('different-target'));
  }, /Redirect .* does not target/);

  const selected = fixture('lint-selected');
  write(resolve(selected.content, 'articles/alternate-article.mdx'), '---\ntitle: Selected lint fixture\n---\nClaim [Finding #987654321].');
  write(resolve(selected.content, 'dossiers/alternate-dossier.json'), JSON.stringify({ name: 'Selected fixture', findings: [], curation: { lead: 'Ordinary prose.' } }));
  const report = resolve(selected.root, 'lint-report.json');
  const lint = (...args) => spawnSync(process.execPath, [resolve(webRoot, 'scripts/lint-citations.mjs'), '--report-file', report, ...args], {
    cwd: webRoot, env: selected.env, encoding: 'utf8', timeout: 30_000,
  });
  const invalid = lint();
  assert.ifError(invalid.error);
  assert.equal(invalid.status, 1, invalid.stderr);
  const issues = JSON.parse(readFileSync(report, 'utf8')).issues;
  assert.ok(issues.some(issue => issue.code === 'FINDING_NO_SOURCES' && issue.file.includes('alternate-article.mdx')));
  assert.ok(issues.every(issue => issue.file.startsWith(selected.content)), 'Lint must not read the checkout publication');
  checks += 1;

  write(resolve(selected.content, 'articles/alternate-article.mdx'), '---\ntitle: Selected lint fixture\n---\nOrdinary prose.');
  const valid = lint();
  assert.ifError(valid.error);
  assert.equal(valid.status, 0, valid.stderr + valid.stdout);
  assert.deepEqual(JSON.parse(readFileSync(report, 'utf8')).issues, []);
  checks += 1;

  const changed = lint('--changed-files');
  assert.ifError(changed.error);
  assert.equal(changed.status, 1);
  assert.match(changed.stderr, /Changed-file citation lint requires the repository content directory/);
  checks += 1;
  console.log(`Publication gate selected-content checks passed: ${checks}.`);
} finally {
  rmSync(temporary, { recursive: true, force: true });
}

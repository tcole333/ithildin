import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createJiti } from 'jiti';

mkdirSync('.cache', { recursive: true });
const work = mkdtempSync(resolve('.cache/content-selection-'));
const content = resolve(work, 'selected-content');
const generated = resolve(work, 'generated-public');
try {
  mkdirSync(resolve(content, 'articles'), { recursive: true });
  mkdirSync(resolve(content, 'timelines'), { recursive: true });
  writeFileSync(resolve(content, 'articles/actual-route.mdx'), '---\ntitle: "Selected: article"\ncluster: different-cluster\ntargets:\n - Example\n---\nSelected content body.');
  writeFileSync(resolve(content, 'timelines/current.json'), '{"events":[]}');
  const env = { ...process.env, ITHILDIN_CONTENT_DIR: content, ITHILDIN_WEB_PUBLIC_DIR: generated };
  const prepare = () => execFileSync(process.execPath, ['scripts/prepare-content.mjs'], { env, stdio: 'pipe' });
  prepare();
  const search = JSON.parse(readFileSync(resolve(generated, 'content/search-index.json')));
  assert.deepEqual(search.map(item => item.href), ['/articles/actual-route']);
  assert.equal(search[0].title, 'Selected: article');
  assert.ok(existsSync(resolve(generated, 'content/timelines/current.json')));
  // No old default dossier data or subsequently removed visualization survives.
  assert.equal(existsSync(resolve(generated, 'content/dossiers')), false);
  rmSync(resolve(content, 'timelines/current.json'));
  prepare();
  assert.equal(existsSync(resolve(generated, 'content/timelines/current.json')), false);
  const previous = process.env.ITHILDIN_CONTENT_DIR;
  process.env.ITHILDIN_CONTENT_DIR = content;
  try {
    const { loadArticles } = createJiti(import.meta.url)(resolve('src/lib/articleContent.ts'));
    const article = loadArticles()[0];
    assert.equal(article.slug, search[0].slug);
    assert.equal(article.title, search[0].title);
    assert.deepEqual(article.targets, ['Example']);
    assert.equal(article.wordCount, 3);
    writeFileSync(resolve(content, 'articles/actual-route.mdx'), '---\ntitle: Changed\n---\nChanged body.');
    assert.equal(loadArticles()[0].title, 'Changed');
  } finally {
    if (previous === undefined) delete process.env.ITHILDIN_CONTENT_DIR;
    else process.env.ITHILDIN_CONTENT_DIR = previous;
  }
  console.log('Selected content, page/index parity, changed metadata, and removed browser asset checks passed.');
} finally {
  rmSync(work, { recursive: true, force: true });
}

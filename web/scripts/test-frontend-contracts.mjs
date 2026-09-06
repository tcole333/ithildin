import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { createJiti } from 'jiti';

const jiti = createJiti(import.meta.url);
const { parseSearchDocuments, getSearchEngine, searchWithRanking } = jiti(resolve('src/lib/searchEngine.ts'));
const { parseManualSourceRecords } = jiti(resolve('src/lib/citations.ts'));
const doc = { id: 'article:example', title: 'Example article', slug: 'example', href: '/articles/example', type: 'article' };
assert.equal(parseSearchDocuments([doc])[0].mentionCount, 0);
for (const value of [{}, [null], [{ ...doc, title: 2 }], [{ ...doc, href: '//evil.test' }], [{ ...doc, href: '/\\evil.test' }], [{ ...doc, mentionCount: -1 }], [doc, doc]]) {
  assert.throws(() => parseSearchDocuments(value));
}
assert.throws(() => parseManualSourceRecords({ example: { kind: 'not-a-kind' } }));
assert.throws(() => parseManualSourceRecords({ example: { publish_valid: 'true' } }));
assert.throws(() => parseManualSourceRecords({ example: { title: {} } }));
assert.equal(parseManualSourceRecords({ example: { kind: 'record_only', publish_valid: false } }).example.publish_valid, false);
let calls = 0;
globalThis.fetch = async () => {
  calls += 1;
  return calls === 1 ? { ok: false, status: 503 } : { ok: true, json: async () => [doc] };
};
await assert.rejects(getSearchEngine(), /503/);
const [first, second] = await Promise.all([getSearchEngine(), getSearchEngine()]);
assert.equal(first, second);
assert.equal(calls, 2);
assert.equal(searchWithRanking(first, 'Example')[0].href, '/articles/example');
console.log('Frontend JSON validation, retry, shared initialization, and ranking checks passed.');

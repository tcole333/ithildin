import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createJiti } from 'jiti';

const articleSlug = 'selected-source-catalog-article';
const dossierSlug = 'selected-source-catalog-dossier';
const articleRef = 'EFTA99999111';
const dossierRef = 'EFTA99999222';
const citedRef = 'EFTA99999333';

if (process.argv.includes('--probe')) {
  const { listPublicSourceRecords } = createJiti(import.meta.url)(resolve('src/lib/sourceCatalog.ts'));
  const records = listPublicSourceRecords();
  const occurrences = records.flatMap(record => record.occurrences);
  process.stdout.write(JSON.stringify({
    selectedArticle: records.some(record => record.canonicalRef.endsWith(articleRef) && record.occurrences.some(item => item.slug === articleSlug)),
    selectedDossier: records.some(record => record.canonicalRef.endsWith(dossierRef) && record.occurrences.some(item => item.slug === dossierSlug)),
    selectedCitationEvidence: records.some(record => record.canonicalRef.endsWith(citedRef) && record.occurrences.some(item => item.slug === dossierSlug && item.findingId === '900000001')),
    unrelatedOccurrences: occurrences.filter(item => ![articleSlug, dossierSlug].includes(item.slug)).length,
  }));
} else {
  const work = mkdtempSync(resolve(tmpdir(), 'ithildin-source-catalog-'));
  try {
    const selected = resolve(work, 'selected-content');
    mkdirSync(resolve(selected, 'articles'), { recursive: true });
    mkdirSync(resolve(selected, 'dossiers'));
    writeFileSync(resolve(selected, `articles/${articleSlug}.mdx`), `---\ntitle: Selected article\n---\nSynthetic source [${articleRef}].`);
    writeFileSync(resolve(selected, `dossiers/${dossierSlug}.json`), JSON.stringify({
      name: 'Selected dossier', findings: [], curation: { lead: `Synthetic source [${dossierRef}]. Referenced finding [Finding #900000001].` },
      citation_findings: [{
        id: 900000001, summary: 'Synthetic cited finding', claim_type: 'direct_quote', confidence: 'confirmed', verification_status: 'verified',
        evidence: [{ evidence_type: 'efta', evidence_ref: citedRef, source_quote: 'Synthetic quoted evidence' }],
      }],
    }));
    const env = { ...process.env, ITHILDIN_CONTENT_DIR: selected };
    delete env.ITHILDIN_FINDING_SNAPSHOT;
    const probe = JSON.parse(execFileSync(process.execPath, [fileURLToPath(import.meta.url), '--probe'], { env, encoding: 'utf8' }));
    assert.equal(probe.selectedArticle, true, 'Selected article citations must receive source records.');
    assert.equal(probe.selectedDossier, true, 'Selected dossier citations must receive source records.');
    assert.equal(probe.selectedCitationEvidence, true, 'Evidence of citation-only findings must receive source records.');
    assert.equal(probe.unrelatedOccurrences, 0, 'Source pages must not import occurrences from another content tree.');
    console.log('Selected article/dossier source catalog and corpus isolation checks passed.');
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

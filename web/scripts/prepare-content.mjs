/** Refresh derived browser assets from the same explicit content root as Astro. */
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve('..');
const content = resolve(process.env.ITHILDIN_CONTENT_DIR || '../content');
const publicRoot = resolve(process.env.ITHILDIN_WEB_PUBLIC_DIR || './.cache/public');
const publicContent = resolve(publicRoot, 'content');
// Fresh generated output prevents an old file surviving a retraction/removal.
if (publicRoot === resolve('public') || !publicRoot.startsWith(resolve('.cache') + '/')) {
  throw new Error('Generated public assets must use a directory under web/.cache');
}
rmSync(publicRoot, { recursive: true, force: true });
mkdirSync(publicRoot, { recursive: true });
cpSync(resolve('public'), publicRoot, {
  recursive: true,
  filter: file => file !== resolve('public/content'),
});
mkdirSync(publicContent, { recursive: true });
// Dossier data itself is rendered by Astro; browser visualizations need only
// these deliberate public datasets, not source-only reviews/findings sidecars.
for (const name of ['financials', 'structures', 'ego', 'timelines', 'models', 'backlinks.json', 'clusters.json', 'network.json', 'investigations.json']) {
  const source = resolve(content, name);
  if (existsSync(source)) cpSync(source, resolve(publicContent, name), { recursive: true });
}
const env = { ...process.env, ITHILDIN_CONTENT_DIR: content, ITHILDIN_PUBLIC_CONTENT_DIR: publicContent };
for (const script of ['export_search_index.py', 'export_preview_index.py']) {
  execFileSync('uv', ['run', '--locked', 'python', `pipeline/${script}`], { cwd: root, env, stdio: 'inherit' });
}

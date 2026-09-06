/** Server/build boundary: one Python YAML/schema loader supplies every route/index. */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { contentRoot } from './contentPaths';
export { contentRoot } from './contentPaths';

export interface Article {
  slug: string;
  title: string;
  subtitle: string;
  cluster: string;
  targets: string[];
  content: string;
  wordCount: number;
}

let cached: { hash: string; articles: Article[] } | undefined;

export function loadArticles(): Article[] {
  const directory = resolve(contentRoot(), 'articles');
  if (!existsSync(directory)) return [];
  const hash = createHash('sha256').update(directory);
  for (const name of readdirSync(directory).filter(name => name.endsWith('.mdx')).sort()) {
    hash.update(name).update(readFileSync(resolve(directory, name)));
  }
  const digest = hash.digest('hex');
  if (cached?.hash === digest) return cached.articles;
  const articles: Article[] = JSON.parse(execFileSync('uv', [
    'run', '--locked', 'python', 'pipeline/article_metadata.py', '--articles-dir', directory,
  ], { cwd: resolve(process.cwd(), '..'), encoding: 'utf-8', maxBuffer: 32 * 1024 * 1024 }));
  cached = { hash: digest, articles };
  return articles;
}

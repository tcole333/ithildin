/** Local deployment consumes the same validated immutable artifact as CI. */
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const args = process.argv.slice(2);
const branch = args[args.indexOf('--branch') + 1];
const artifactIndex = args.indexOf('--artifact-dir');
if (!['main', 'preview'].includes(branch) || artifactIndex < 0 || !args[artifactIndex + 1]) {
  throw new Error('Usage: npm run deploy[:preview] -- --artifact-dir /absolute/validated-artifact');
}
const artifact = resolve(args[artifactIndex + 1]);
execFileSync('uv', ['run', '--locked', 'python', 'scripts/validate_release.py', 'verify-artifact', '--artifact-dir', artifact], { cwd: resolve('..'), stdio: 'inherit' });
execFileSync('npx', ['wrangler', 'pages', 'deploy', resolve(artifact, 'site'), '--project-name=ithildin', `--branch=${branch}`, '--commit-dirty=true'], { stdio: 'inherit' });

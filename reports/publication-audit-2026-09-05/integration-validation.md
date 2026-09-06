# Integration PR #12 CI repair

Initial head inspected: `d021f58326ff11a6becd495ee96d3ee7cf1ab4a6`.
Checkout: `/tmp/osint-SUw5NK21/merge-worktree`.

The failed [web job](https://github.com/tcole333/ithildin/actions/runs/34003596974/job/101406700713) reported 59 Astro/TypeScript errors after a clean `npm ci`: Node built-in modules and `process` were untyped, followed by downstream inferred-type errors. `@types/node` was absent from both the package's direct development dependencies and the lockfile; Vite mentioned it only as an optional peer dependency.

With the root task's file-ownership approval, added `@types/node` **22.20.1** as an exact development dependency in `web/package.json` and `web/package-lock.json`. Its only newly locked transitive dependency is `undici-types` **6.21.0**. No type-check flags, source guards, publication gates, or frontend implementation changed. The task owner handles all commits, pushes, and merging.

## Local validation

Runtime: Node **v22.23.2**, npm **10.9.8**.

- Exact `npm ci` — passed.
- `npm run check` — passed, **0 errors / 0 warnings**, 31 informational hints.
- `npm run test:frontend` — passed, including citation snapshots, changed-content selection, support spans, search loading/retry/ranking, selected content, publication gates, and source-catalog isolation.
- `npm run test:frontend:browser` — passed, including delayed readiness, failure/retry, focus trap/restore, and tooltip text.
- `PUBLIC_ENABLE_EVIDENCE_MODE=false npm run build` — passed, **10,613 pages**.
- `npm run test:citations:build` — passed, **589 selected pages / 17,909 citation anchors**.
- Changed-path `git diff --check` — passed before the task owner committed the fix.
- Exact strict agent-docs validator from CI — pending.

The original remote repository-policy check passed. Python and agent-docs checks were still running at the last observed remote snapshot. Remote polling stopped when the task owner relayed the user's CI-credit exhaustion instruction; no remote success is claimed for pending checks.

Logs: `pr12-web-failure.log`, `pr12-web-check-clean.log`, `pr12-web-frontend.log`, `pr12-web-browser.log`, `pr12-web-build.log`, `pr12-web-citations-build.log`, and `pr12-docs-lint.log`, all under `/tmp/osint-SUw5NK21/`.

Papercut **#2782** is tracked centrally by the root task. Resolution evidence: a clean install now contains the explicitly declared Node type package, and the unchanged strict type check goes from 59 errors to zero.

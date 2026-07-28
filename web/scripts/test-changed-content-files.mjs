import assert from "node:assert/strict";
import { collectChangedContentFiles } from "./changed-content-files.mjs";

const calls = [];
function fakeGit(_projectRoot, args) {
  calls.push(args);
  const command = args.join(" ");
  if (command === "diff --name-only --diff-filter=ACMR HEAD --") {
    return "content/dossiers/changed.json\nweb/src/lib/citations.ts";
  }
  if (command === "ls-files --others --exclude-standard") {
    return "content/dossiers/new.json\nnotes.txt";
  }
  return "";
}

const worktreeFiles = collectChangedContentFiles({
  projectRoot: "/repo",
  baseRef: "HEAD",
  headRef: "WORKTREE",
  isTrackedContent: (path) => /^content\/dossiers\/.+\.json$/.test(path),
  git: fakeGit,
});

assert.deepEqual(
  Array.from(worktreeFiles).sort(),
  ["content/dossiers/changed.json", "content/dossiers/new.json"],
);
assert.ok(
  calls.some((args) => args.join(" ") === "diff --name-only --diff-filter=ACMR HEAD --"),
  "WORKTREE scope must compare the base revision to the working tree.",
);
assert.ok(
  calls.some((args) => args.join(" ") === "ls-files --others --exclude-standard"),
  "WORKTREE scope must include untracked content.",
);

const commitCalls = [];
collectChangedContentFiles({
  projectRoot: "/repo",
  baseRef: "main",
  headRef: "feature",
  isTrackedContent: () => true,
  git: (_projectRoot, args) => {
    commitCalls.push(args);
    return "";
  },
});
assert.deepEqual(
  commitCalls,
  [["diff", "--name-only", "--diff-filter=ACMR", "main...feature", "--"]],
);

assert.throws(
  () => collectChangedContentFiles({
    projectRoot: "/repo",
    baseRef: "bad-ref",
    headRef: "HEAD",
    isTrackedContent: () => true,
    git: () => {
      throw new Error("unknown revision");
    },
  }),
  /unknown revision/,
);

process.stdout.write("Changed-content selection checks passed.\n");

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { selectCoverageFiles } from "./support-coverage-scope.mjs";

const root = mkdtempSync(join(tmpdir(), "osint-coverage-targets-"));
try {
  mkdirSync(join(root, "content/articles"), { recursive: true });
  const files = ["new", "modified", "unchanged"].map((name) => `content/articles/${name}.mdx`);
  for (const file of files) writeFileSync(join(root, file), `Current bytes for ${file}`);
  const git = () => { throw new Error("Explicit content review must not depend on Git change state"); };
  assert.deepEqual([...selectCoverageFiles({ projectRoot: root, files, git })], files);
  assert.deepEqual([...selectCoverageFiles({ projectRoot: root, files: [join(root, files[2])], git })], [files[2]]);
  writeFileSync(join(root, files[1]), "Revised current bytes");
  assert.deepEqual([...selectCoverageFiles({ projectRoot: root, files: [files[1]], git })], [files[1]]);
  assert.throws(() => selectCoverageFiles({ projectRoot: root, files: ["content/articles/missing.mdx"] }), /does not exist/);
  assert.throws(() => selectCoverageFiles({ projectRoot: root, files: ["../outside.mdx"] }), /Not an article/);
  assert.throws(() => selectCoverageFiles({ projectRoot: root, files, changed: true }), /not both/);
  assert.equal(selectCoverageFiles({ projectRoot: root }), null);
  const env = { ...process.env, ITHILDIN_CONTENT_DIR: join(root, "content") };
  delete env.ITHILDIN_FINDING_SNAPSHOT;
  const script = fileURLToPath(new URL("./report-support-coverage.mjs", import.meta.url));
  const result = spawnSync(process.execPath, [script, ...files.flatMap((file) => ["--file", file])], {
    cwd: root, env, encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.scope, "explicit");
  assert.equal(report.file_count, 3);
  for (const item of report.files) {
    assert.equal(item.content_sha256, createHash("sha256").update(readFileSync(join(root, item.file))).digest("hex"));
  }
  console.log("Current-target coverage selection passed for new, modified and unchanged content.");
} finally {
  rmSync(root, { recursive: true, force: true });
}

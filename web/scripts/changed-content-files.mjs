import { execFileSync } from "node:child_process";

function splitLines(value) {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function normalizeRepoPath(path) {
  const normalized = String(path || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\.\//, "");
  if (normalized.startsWith("site/")) {
    return normalized.slice("site/".length);
  }
  return normalized;
}

export function runGit(projectRoot, argsList) {
  try {
    return execFileSync("git", argsList, {
      cwd: projectRoot,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    const detail = String(error?.stderr || error?.message || error).trim();
    throw new Error(`git ${argsList.join(" ")} failed${detail ? `: ${detail}` : ""}`);
  }
}

export function collectChangedContentFiles({
  projectRoot,
  baseRef = "",
  headRef = "HEAD",
  isTrackedContent,
  ciFallback = false,
  git = runGit,
}) {
  const candidates = [];
  const worktreeHead = String(headRef).toUpperCase() === "WORKTREE";

  if (baseRef && !worktreeHead) {
    candidates.push(
      ...splitLines(
        git(projectRoot, [
          "diff",
          "--name-only",
          "--diff-filter=ACMR",
          `${baseRef}...${headRef}`,
          "--",
        ]),
      ),
    );
  } else if (baseRef && worktreeHead) {
    candidates.push(
      ...splitLines(
        git(projectRoot, [
          "diff",
          "--name-only",
          "--diff-filter=ACMR",
          baseRef,
          "--",
        ]),
      ),
    );
    candidates.push(
      ...splitLines(
        git(projectRoot, ["ls-files", "--others", "--exclude-standard"]),
      ),
    );
  } else {
    candidates.push(
      ...splitLines(
        git(projectRoot, ["diff", "--name-only", "--diff-filter=ACMR"]),
      ),
    );
    candidates.push(
      ...splitLines(
        git(projectRoot, [
          "diff",
          "--name-only",
          "--diff-filter=ACMR",
          "--cached",
        ]),
      ),
    );
    candidates.push(
      ...splitLines(
        git(projectRoot, ["ls-files", "--others", "--exclude-standard"]),
      ),
    );

    if (candidates.length === 0 && ciFallback) {
      candidates.push(
        ...splitLines(
          git(projectRoot, [
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            "HEAD~1...HEAD",
            "--",
          ]),
        ),
      );
    }
  }

  const out = new Set();
  for (const rawPath of candidates) {
    const file = normalizeRepoPath(rawPath);
    if (isTrackedContent(file)) out.add(file);
  }
  return out;
}

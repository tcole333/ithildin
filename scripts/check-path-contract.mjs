#!/usr/bin/env node

import { execFileSync } from "node:child_process";

function loadTrackedSitePaths() {
  const raw = execFileSync("git", ["ls-files", "-z", "site"], { encoding: "utf8" });
  return raw
    .split("\u0000")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function main() {
  const tracked = loadTrackedSitePaths();
  if (tracked.length > 0) {
    console.error("Path contract check failed.");
    console.error("");
    console.error("Tracked files are not allowed under site/ in Phase 2.");
    console.error("Move or delete these paths:");
    for (const path of tracked) {
      console.error(`- ${path}`);
    }
    console.error("");
    console.error("Canonical paths are /content, /pipeline, and /web.");
    process.exit(1);
  }

  console.log("Path contract check passed.");
}

main();

import { existsSync } from "node:fs";
import { relative, resolve } from "node:path";
import { collectChangedContentFiles } from "./changed-content-files.mjs";

export function isCoverageTrackedContent(file) {
  return /^content\/articles\/[^/]+\.mdx$/.test(file)
    || /^content\/dossiers\/(?!_)[^/]+\.json$/.test(file);
}

export function selectCoverageFiles({ projectRoot, contentRoot = resolve(projectRoot, "content"), files = [], changed = false, baseRef = "", headRef = "HEAD", git, exists = existsSync }) {
  if (files.length) {
    if (changed) throw new Error("Use explicit --file targets or --changed-files, not both.");
    return new Set(files.map((file) => {
      const absolute = file.startsWith("content/") ? resolve(contentRoot, file.slice(8)) : resolve(projectRoot, file);
      const normalized = `content/${relative(contentRoot, absolute).replace(/\\/g, "/")}`;
      if (!isCoverageTrackedContent(normalized)) throw new Error(`Not an article/dossier content target: ${file}`);
      if (!exists(absolute)) throw new Error(`Requested content target does not exist: ${file}`);
      return normalized;
    }));
  }
  if (!changed) return null;
  return collectChangedContentFiles({ projectRoot, baseRef, headRef, git, isTrackedContent: isCoverageTrackedContent });
}

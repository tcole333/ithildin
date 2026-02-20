import { execFileSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

let cached: Record<string, string[]> | null = null;

function candidateDbPaths(): string[] {
  const envPath = String(process.env.INVESTIGATION_DB_PATH || "").trim();
  const moduleDir = dirname(fileURLToPath(import.meta.url));
  const candidates = [
    envPath,
    resolve(process.cwd(), "investigation.db"),
    resolve(process.cwd(), "..", "investigation.db"),
    resolve(moduleDir, "..", "..", "..", "investigation.db"),
  ].filter((value): value is string => Boolean(value));
  return Array.from(new Set(candidates));
}

function isUsableDb(path: string): boolean {
  if (!existsSync(path)) return false;
  try {
    return statSync(path).size > 0;
  } catch {
    return false;
  }
}

function loadFromDb(path: string): Record<string, string[]> | null {
  try {
    const output = execFileSync("sqlite3", [
      path,
      ".mode json",
      "SELECT finding_id, evidence_ref FROM finding_evidence;",
    ], { encoding: "utf-8" }).trim();

    if (!output) {
      return {};
    }

    const rows: Array<{ finding_id: number; evidence_ref: string | null }> = JSON.parse(output);
    const map: Record<string, string[]> = {};
    for (const row of rows) {
      const key = String(row.finding_id);
      if (!map[key]) map[key] = [];
      if (row.evidence_ref) {
        map[key].push(row.evidence_ref);
      }
    }
    return map;
  } catch {
    return null;
  }
}

export function loadFindingEvidenceMap(): Record<string, string[]> {
  if (cached) return cached;

  for (const dbPath of candidateDbPaths()) {
    if (!isUsableDb(dbPath)) continue;
    const map = loadFromDb(dbPath);
    if (map) {
      cached = map;
      return cached;
    }
  }

  cached = {};
  return cached;
}

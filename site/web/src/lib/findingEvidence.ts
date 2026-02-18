import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

let cached: Record<string, string[]> | null = null;

export function loadFindingEvidenceMap(): Record<string, string[]> {
  if (cached) return cached;

  const dbPath = resolve(process.cwd(), "..", "..", "investigation.db");
  if (!existsSync(dbPath)) {
    cached = {};
    return cached;
  }

  try {
    const output = execFileSync("sqlite3", [
      dbPath,
      ".mode json",
      "SELECT finding_id, evidence_ref FROM finding_evidence;",
    ], { encoding: "utf-8" }).trim();

    if (!output) {
      cached = {};
      return cached;
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
    cached = map;
    return cached;
  } catch (_err) {
    cached = {};
    return cached;
  }
}

#!/usr/bin/env python3
"""Build an isolated candidate publication tree without overwriting authored content."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "pipeline"


def export_steps(stage: Path, db_path: Path) -> list[tuple[list[str], str]]:
    def command(script: str, *args: str) -> list[str]:
        return ["uv", "run", "python", str(PIPELINE_DIR / script), *args]

    return [
        (command("export_investigations.py"), "Export investigations"),
        (command("export_dossiers.py", "--all-profiles"), "Export dossiers"),
        (command("curate_dossier.py", "--all"), "Curate dossiers"),
        (command("export_network.py"), "Export network graph"),
        (command("export_financials.py"), "Export financial flows"),
        (command("story_clustering.py"), "Export story clusters"),
        (command("export_structures.py"), "Export corporate structures"),
        (command("export_models.py"), "Validate and index models"),
        (command("export_dossier_indexes.py"), "Index complete staged dossier set"),
        (command("compute_backlinks.py"), "Compute backlinks"),
        (command("export_agent_context.py", "--all"), "Export agent context"),
        (command("export_search_index.py"), "Export search index"),
        (command("export_preview_index.py"), "Export preview index"),
        (command("publication_snapshot.py", "build", "--content-dir", str(stage / "content"),
                 "--db", str(db_path), "--output", str(stage / "content/finding-catalog.json")),
         "Validate candidate finding snapshot"),
    ]


def build_candidate(output_dir: Path, *, source_content: Path = ROOT / "content",
                    source_public: Path = ROOT / "web/public/content",
                    db_path: Path = ROOT / "investigation.db") -> Path:
    """Fail on the first failed prerequisite; keep failed staging available for review."""
    stage = output_dir.resolve()
    for label, source in (("content", source_content), ("public content", source_public)):
        source = source.resolve()
        if stage == source or stage in source.parents or source in stage.parents:
            raise ValueError(f"Output directory must not overlap the {label} input: {source}")
    if stage.exists():
        raise ValueError(f"Output directory already exists: {stage}; choose a fresh candidate directory")
    if not source_content.is_dir() or not db_path.is_file():
        raise ValueError("Candidate export requires an existing content directory and investigation DB")
    stage.mkdir(parents=True)
    shutil.copytree(source_content, stage / "content")
    if source_public.exists():
        shutil.copytree(source_public, stage / "public/content")
    else:
        (stage / "public/content").mkdir(parents=True)
    env = {
        **os.environ,
        "ITHILDIN_CONTENT_DIR": str(stage / "content"),
        "ITHILDIN_PUBLIC_CONTENT_DIR": str(stage / "public/content"),
        "ITHILDIN_DB_PATH": str(db_path.resolve()),
        "INVESTIGATION_DB_PATH": str(db_path.resolve()),
    }
    completed = []
    for cmd, label in export_steps(stage, db_path.resolve()):
        print(label, flush=True)
        result = subprocess.run(cmd, cwd=ROOT, env=env, check=False)
        if result.returncode:
            (stage / "export-result.json").write_text(json.dumps({
                "ok": False, "completed": completed, "failed": label,
                "returncode": result.returncode,
            }, indent=2) + "\n")
            raise RuntimeError(f"{label} failed ({result.returncode}); candidate retained at {stage}")
        completed.append(label)

    # Browser-only visualizations consume public copies. Keep them in the same
    # staged generation as the Astro source content and generated indexes.
    for name in ("financials", "structures", "ego", "timelines"):
        source = stage / "content" / name
        if source.exists():
            shutil.copytree(source, stage / "public/content" / name, dirs_exist_ok=True)
    for name in ("backlinks.json", "clusters.json", "network.json", "investigations.json"):
        source = stage / "content" / name
        if source.exists():
            shutil.copy2(source, stage / "public/content" / name)
    (stage / "export-result.json").write_text(json.dumps({
        "ok": True, "completed": completed, "review_required": True,
        "content_dir": str(stage / "content"),
        "public_content_dir": str(stage / "public/content"),
    }, indent=2) + "\n")
    return stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh candidate directory; never the authored content tree")
    parser.add_argument("--content-dir", type=Path, default=ROOT / "content")
    parser.add_argument("--public-content-dir", type=Path, default=ROOT / "web/public/content")
    parser.add_argument("--db", type=Path, default=ROOT / "investigation.db")
    args = parser.parse_args()
    try:
        stage = build_candidate(args.output_dir, source_content=args.content_dir,
                                source_public=args.public_content_dir, db_path=args.db)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error))
        return 1
    print(f"Candidate ready for review: {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

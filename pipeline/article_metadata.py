"""Canonical article metadata and routes for exporters and the static web build."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml


def load_article(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", raw, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: article requires YAML frontmatter")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: article metadata must be a mapping")
    for key in ("title", "subtitle", "cluster"):
        value = metadata.get(key, "")
        if not isinstance(value, str) or (key == "title" and not value.strip()):
            raise ValueError(f"{path}: {key} must be {'a nonempty ' if key == 'title' else 'a '}string")
    targets = metadata.get("targets", [])
    if isinstance(targets, str):
        targets = [part.strip() for part in targets.split(",") if part.strip()]
    if not isinstance(targets, list) or any(not isinstance(item, str) for item in targets):
        raise ValueError(f"{path}: targets must be a string or list of strings")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.stem):
        raise ValueError(f"{path}: article filename must be a lowercase route slug")
    # The filename defines the route. A story cluster can differ without
    # creating a search link to a nonexistent page.
    body = raw[match.end():].lstrip("\r\n")
    return {
        "slug": path.stem,
        "title": metadata["title"],
        "subtitle": metadata.get("subtitle", ""),
        "cluster": metadata.get("cluster", ""),
        "targets": targets,
        "content": body,
        "wordCount": len(body.split()),
    }


def load_articles(directory: Path) -> list[dict]:
    return [load_article(path) for path in sorted(directory.glob("*.mdx"))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = json.dumps(load_articles(args.articles_dir), ensure_ascii=False)
    if args.output:
        args.output.write_text(encoded + "\n")
    else:
        print(encoded)


if __name__ == "__main__":
    main()

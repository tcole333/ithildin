from __future__ import annotations

import json
from pathlib import Path

from pipeline.curate_dossier import resolve_dossier_path


def write_dossier(directory: Path, slug: str, name: str, aliases: list[str] | None = None) -> Path:
    path = directory / f"{slug}.json"
    path.write_text(
        json.dumps(
            {
                "slug": slug,
                "name": name,
                "aliases": aliases or [],
            }
        )
    )
    return path


def test_resolve_dossier_path_follows_redirect_alias(tmp_path: Path) -> None:
    canonical = write_dossier(tmp_path, "brad-karp", "Brad Karp")
    (tmp_path / "_redirects.json").write_text(
        json.dumps({"brad-s-karp": "brad-karp"})
    )

    assert resolve_dossier_path(tmp_path, "brad-s-karp") == canonical


def test_resolve_dossier_path_accepts_unambiguous_long_legal_name(
    tmp_path: Path,
) -> None:
    canonical = write_dossier(tmp_path, "paul-weiss", "Paul Weiss")
    write_dossier(tmp_path, "another-firm", "Another Firm")

    assert (
        resolve_dossier_path(
            tmp_path,
            "Paul, Weiss, Rifkind, Wharton & Garrison LLP",
        )
        == canonical
    )


def test_resolve_dossier_path_rejects_ambiguous_prefix(tmp_path: Path) -> None:
    write_dossier(tmp_path, "alpha-beta", "Alpha Beta")
    write_dossier(tmp_path, "alpha-beta-holdings", "Alpha Beta")

    assert resolve_dossier_path(tmp_path, "Alpha Beta Global Partners") is None

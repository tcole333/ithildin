"""Catalog parse reuse must preserve fresh-file and mutable-caller semantics."""

import os

import pytest
import yaml

from tools import seed_public_records_catalog as catalog


@pytest.fixture(autouse=True)
def clear_parse_cache():
    catalog._cached_config_yaml.cache_clear()
    yield
    catalog._cached_config_yaml.cache_clear()


def write_config(path, source_id="us-aa-first"):
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": source_id,
                        "access_review": {"limits": {"maximum_page_size": 10}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def count_parses(monkeypatch):
    original = yaml.safe_load
    calls = []

    def parse(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(catalog.yaml, "safe_load", parse)
    return calls


def test_unchanged_catalog_parses_once_and_is_deeply_isolated(tmp_path, monkeypatch):
    path = tmp_path / "sources.yaml"
    write_config(path)
    calls = count_parses(monkeypatch)

    first = catalog._load_config(path)
    first["sources"][0]["access_review"]["limits"]["maximum_page_size"] = 99
    first["sources"].append({"source_id": "us-aa-added"})
    second = catalog._load_config(path)

    assert len(calls) == 1
    assert len(second["sources"]) == 1
    assert second["sources"][0]["access_review"]["limits"]["maximum_page_size"] == 10


def test_same_size_same_mtime_edit_reloads_contents(tmp_path, monkeypatch):
    path = tmp_path / "sources.yaml"
    write_config(path, "us-aa-first")
    calls = count_parses(monkeypatch)
    catalog._load_config(path)
    prior = path.stat()

    write_config(path, "us-aa-other")
    os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    assert path.stat().st_size == prior.st_size
    assert path.stat().st_mtime_ns == prior.st_mtime_ns
    result = catalog._load_config(path)

    assert result["sources"][0]["source_id"] == "us-aa-other"
    assert len(calls) == 2


def test_custom_paths_do_not_share_mutable_results(tmp_path, monkeypatch):
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    write_config(first_path)
    write_config(second_path, "us-aa-other")
    calls = count_parses(monkeypatch)

    first = catalog._load_config(first_path)
    second = catalog._load_config(second_path)
    first["sources"][0]["source_id"] = "us-aa-mutated"

    assert second["sources"][0]["source_id"] == "us-aa-other"
    assert catalog._load_config(first_path)["sources"][0]["source_id"] == "us-aa-first"
    assert len(calls) == 2


def test_replaced_parser_is_not_hidden_by_cached_contents(tmp_path, monkeypatch):
    path = tmp_path / "sources.yaml"
    write_config(path)
    catalog._load_config(path)
    calls = count_parses(monkeypatch)

    catalog._load_config(path)

    assert len(calls) == 1


def test_deleted_cached_file_still_raises(tmp_path):
    path = tmp_path / "sources.yaml"
    write_config(path)
    catalog._load_config(path)
    path.unlink()

    with pytest.raises(FileNotFoundError):
        catalog._load_config(path)


def test_yaml_parse_failures_are_not_cached(tmp_path, monkeypatch):
    path = tmp_path / "sources.yaml"
    path.write_text("sources: [\n", encoding="utf-8")
    calls = count_parses(monkeypatch)

    for _ in range(2):
        with pytest.raises(yaml.YAMLError):
            catalog._load_config(path)

    assert len(calls) == 2


def test_cached_parse_does_not_skip_validation(tmp_path, monkeypatch):
    path = tmp_path / "sources.yaml"
    path.write_text("schema_version: 2\nsources: []\n", encoding="utf-8")
    calls = count_parses(monkeypatch)

    for _ in range(2):
        with pytest.raises(ValueError, match="unsupported.*schema"):
            catalog._load_config(path)

    assert len(calls) == 1


def test_parse_cache_has_a_small_entry_bound(tmp_path, monkeypatch):
    calls = count_parses(monkeypatch)
    paths = [tmp_path / f"sources-{index}.yaml" for index in range(5)]
    for path in paths:
        write_config(path)
        catalog._load_config(path)

    assert catalog._cached_config_yaml.cache_info().currsize == 4
    catalog._load_config(paths[0])
    assert len(calls) == 6

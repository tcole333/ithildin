import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import tools.registry_address_index as address_index
from tools.registry_address_index import (
    RegistryAddressIndexError,
    address_query_diagnostics,
    address_query_plans,
    build_index,
    normalize_address,
    normalize_selector,
    search_addresses,
    validate_index_fast,
    validate_index_full,
    rollback_index,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture
def registry_paths(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "registry.db"
    index = tmp_path / "registry_address_search.db"
    db = sqlite3.connect(source)
    db.executescript(
        """
        CREATE TABLE registry_entities(
            id INTEGER PRIMARY KEY,
            entity_name TEXT NOT NULL,
            principal_address TEXT,
            mailing_address TEXT,
            source_jurisdiction TEXT NOT NULL
        );
        CREATE TABLE registry_officers(
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            officer_name TEXT NOT NULL,
            address TEXT
        );
        CREATE TABLE registry_agents(
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            address TEXT
        );
        CREATE INDEX idx_re_name ON registry_entities(entity_name);
        CREATE INDEX idx_ro_name ON registry_officers(officer_name);
        CREATE INDEX idx_ra_name ON registry_agents(agent_name);

        INSERT INTO registry_entities VALUES
            (1, 'Zulu Holdings', '200 South Biscayne Boulevard, Suite 3400', NULL, 'fl'),
            (2, 'Alpha Mail', '99 Bay Street', 'P.O. Box 42', 'ny'),
            (3, 'Beta Limited', '12 Green Boulevard', NULL, 'de'),
            (4, 'Aardvark Suites', '500 Suite Road', NULL, 'nv');
        INSERT INTO registry_officers VALUES
            (11, 1, 'Zulu Officer', '200 S Biscayne Blvd., Suite 3400'),
            (12, 4, 'Alpha Officer', '500 Suite Road');
        INSERT INTO registry_agents VALUES
            (21, 1, 'Zulu Agent', '200 South Biscayne Boulevard'),
            (22, 2, 'Alpha Agent', 'P.O. Box 42, Suite 8');
        """
    )
    db.commit()
    db.close()
    return source, index


def test_normalization_and_short_selector_rejection() -> None:
    assert normalize_address("  P.O. Bôx #42  ") == "PO BOX 42"
    assert normalize_address("Straße 7") == "STRASSE 7"
    assert normalize_selector("A-1-B") == "A 1 B"
    with pytest.raises(RegistryAddressIndexError, match="at least 3"):
        normalize_selector("A-1")


def test_build_query_and_validate_without_changing_source(
    registry_paths: tuple[Path, Path],
) -> None:
    source, index = registry_paths
    db = sqlite3.connect(source)
    db.execute(
        "INSERT INTO registry_entities VALUES (5, 'Aardvark Suites', "
        "'501 Suite Road', NULL, 'nv')"
    )
    db.execute(
        "INSERT INTO registry_officers VALUES "
        "(13, 5, 'Alpha Officer', '501 Suite Road')"
    )
    db.execute(
        "INSERT INTO registry_agents VALUES "
        "(23, 5, 'Alpha Agent', '501 Suite Road')"
    )
    db.commit()
    db.close()
    source_hash = _sha256(source)
    source_stat = source.stat()

    built = build_index(source, index, batch_size=2, min_free_gib=0)

    assert built["status"] == "built"
    assert built["metrics"]["entities"]["rows"] == 5
    assert built["metrics"]["officers"]["rows"] == 3
    assert built["metrics"]["agents"]["rows"] == 3
    assert _sha256(source) == source_hash
    assert source.stat().st_size == source_stat.st_size
    assert source.stat().st_mtime_ns == source_stat.st_mtime_ns

    assert validate_index_fast(source, index)["source_fingerprint"]["max_ids"] == {
        "registry_agents": 23,
        "registry_entities": 5,
        "registry_officers": 13,
    }
    assert validate_index_full(source, index)["integrity_check"] == "ok"

    exact = search_addresses(
        "200 SOUTH BISCAYNE BOULEVARD", 20, source_path=source, index_path=index
    )
    assert [row["entity_name"] for row in exact["entities"]] == ["Zulu Holdings"]
    assert [row["agent_name"] for row in exact["agents"]] == ["Zulu Agent"]

    fragment = search_addresses(
        "SOUTH BISCAYNE", 20, source_path=source, index_path=index
    )
    assert [row["entity_name"] for row in fragment["entities"]] == ["Zulu Holdings"]

    interior = search_addresses("ISCAYN", 20, source_path=source, index_path=index)
    assert [row["entity_name"] for row in interior["entities"]] == ["Zulu Holdings"]
    assert [row["officer_name"] for row in interior["officers"]] == ["Zulu Officer"]

    punctuation = search_addresses("P O BOX", 20, source_path=source, index_path=index)
    assert [row["entity_name"] for row in punctuation["entities"]] == ["Alpha Mail"]
    assert [row["agent_name"] for row in punctuation["agents"]] == ["Alpha Agent"]

    common = search_addresses("SUITE", 1, source_path=source, index_path=index)
    assert [row["entity_name"] for row in common["entities"]] == ["Aardvark Suites"]
    assert [row["officer_name"] for row in common["officers"]] == ["Alpha Officer"]
    assert [row["agent_name"] for row in common["agents"]] == ["Alpha Agent"]

    ties = search_addresses("SUITE", 2, source_path=source, index_path=index)
    assert [row["id"] for row in ties["entities"]] == [4, 5]
    assert [row["id"] for row in ties["officers"]] == [12, 13]
    assert [row["id"] for row in ties["agents"]] == [22, 23]

    plans = address_query_plans("SUITE", source_path=source, index_path=index)
    for details in plans.values():
        assert any("VIRTUAL TABLE INDEX" in detail for detail in details)
        assert any("USE TEMP B-TREE FOR ORDER BY" in detail for detail in details)


def test_adaptive_base_first_plan_preserves_strict_candidate_first_results(
    registry_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, index = registry_paths
    assert address_index._address_strategy(10_000) == "fts_candidates"
    assert address_index._address_strategy(10_001) == "base_name_index"
    build_index(source, index, min_free_gib=0)
    candidate_first = search_addresses(
        "SUITE", 20, source_path=source, index_path=index
    )

    monkeypatch.setattr(address_index, "HIGH_CARDINALITY_CANDIDATES", 0)
    base_first = search_addresses("SUITE", 20, source_path=source, index_path=index)
    assert base_first == candidate_first

    diagnostics = address_query_diagnostics(
        "SUITE", source_path=source, index_path=index
    )
    expected_indexes = {
        "entities": "idx_re_name",
        "officers": "idx_ro_name",
        "agents": "idx_ra_name",
    }
    for bucket, details in diagnostics.items():
        assert details["candidate_count"] > 0
        assert details["strategy"] == "base_name_index"
        plan = details["query_plan"]
        assert any(expected_indexes[bucket] in item for item in plan)
        assert any(
            "VIRTUAL TABLE INDEX" in item and "=" in item and "M" in item
            for item in plan
        )
        assert not any("TEMP B-TREE FOR ORDER BY" in item for item in plan)


def test_missing_and_stale_sidecars_fail_without_scan_fallback(
    registry_paths: tuple[Path, Path],
) -> None:
    source, index = registry_paths
    with pytest.raises(RegistryAddressIndexError, match="missing"):
        search_addresses("SUITE", 20, source_path=source, index_path=index)

    build_index(source, index, min_free_gib=0)
    db = sqlite3.connect(source)
    db.execute(
        "INSERT INTO registry_agents VALUES (23, 3, 'New Agent', '77 Suite Avenue')"
    )
    db.commit()
    db.close()

    with pytest.raises(RegistryAddressIndexError, match="stale"):
        search_addresses("SUITE", 20, source_path=source, index_path=index)


def test_idempotent_build_and_atomic_backup(registry_paths: tuple[Path, Path]) -> None:
    source, index = registry_paths
    build_index(source, index, min_free_gib=0)
    first_hash = _sha256(index)

    current = build_index(source, index, min_free_gib=0)
    assert current["status"] == "up_to_date"
    assert _sha256(index) == first_hash

    rebuilt = build_index(source, index, force=True, min_free_gib=0)
    backup = Path(rebuilt["backup_path"])
    assert backup.is_file()
    assert _sha256(backup) == first_hash
    rebuilt_hash = _sha256(index)
    assert validate_index_full(source, index)["integrity_check"] == "ok"

    rollback_index(index)
    assert _sha256(index) == first_hash
    assert _sha256(backup) == rebuilt_hash


def test_publish_failure_never_removes_or_replaces_live_index(
    registry_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, index = registry_paths
    build_index(source, index, min_free_gib=0)
    original_hash = _sha256(index)
    real_replace = address_index.os.replace

    def fail_new_publish(source_path, destination_path):
        source_path = Path(source_path)
        destination_path = Path(destination_path)
        if destination_path == index and source_path.name.startswith(index.name + ".tmp-"):
            assert index.is_file()
            raise OSError("injected publish failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(address_index.os, "replace", fail_new_publish)
    with pytest.raises(OSError, match="injected publish failure"):
        build_index(source, index, force=True, min_free_gib=0)

    assert index.is_file()
    assert _sha256(index) == original_hash
    assert _sha256(index.with_name(index.name + ".bak")) == original_hash


def test_post_publish_validation_failure_restores_previous_index(
    registry_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, index = registry_paths
    build_index(source, index, min_free_gib=0)
    original_hash = _sha256(index)

    def fail_validation(*args, **kwargs):
        raise RegistryAddressIndexError("injected post-publish validation failure")

    monkeypatch.setattr(address_index, "validate_index_fast", fail_validation)
    with pytest.raises(RegistryAddressIndexError, match="injected"):
        build_index(source, index, force=True, min_free_gib=0)

    assert index.is_file()
    assert _sha256(index) == original_hash
    assert _sha256(index.with_name(index.name + ".bak")) == original_hash


def test_rollback_failure_restores_original_pair_without_live_path_gap(
    registry_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, index = registry_paths
    build_index(source, index, min_free_gib=0)
    first_hash = _sha256(index)
    build_index(source, index, force=True, min_free_gib=0)
    current_hash = _sha256(index)
    backup = index.with_name(index.name + ".bak")
    assert _sha256(backup) == first_hash

    real_replace = address_index.os.replace
    failed = False

    def fail_backup_swap(source_path, destination_path):
        nonlocal failed
        source_path = Path(source_path)
        destination_path = Path(destination_path)
        if (
            not failed
            and destination_path == backup
            and ".rollback-current-" in source_path.name
        ):
            failed = True
            assert index.is_file()
            raise OSError("injected rollback failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(address_index.os, "replace", fail_backup_swap)
    with pytest.raises(OSError, match="injected rollback failure"):
        rollback_index(index)

    assert index.is_file()
    assert _sha256(index) == current_hash
    assert _sha256(backup) == first_hash


def test_lifecycle_lock_rejects_concurrent_mutation(
    registry_paths: tuple[Path, Path],
) -> None:
    source, index = registry_paths
    index.parent.mkdir(parents=True, exist_ok=True)
    lock_path = index.with_name(index.name + ".lock")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,os,sys; "
                "fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT,0o600); "
                "fcntl.flock(fd,fcntl.LOCK_EX); "
                "print('locked',flush=True); sys.stdin.read(1)"
            ),
            str(lock_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(RegistryAddressIndexError, match="Another .* lifecycle"):
            build_index(source, index, min_free_gib=0)
    finally:
        assert holder.stdin is not None
        holder.stdin.write("x")
        holder.stdin.close()
        holder.wait(timeout=5)


def test_active_wal_update_and_delete_make_sidecar_stale(
    registry_paths: tuple[Path, Path],
) -> None:
    source, index = registry_paths
    writer = sqlite3.connect(source)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    build_index(source, index, min_free_gib=0)

    writer.execute(
        "UPDATE registry_entities SET principal_address='777 Updated Avenue' WHERE id=3"
    )
    writer.execute("DELETE FROM registry_agents WHERE id=21")
    writer.commit()
    assert Path(str(source) + "-wal").stat().st_size > 0

    with pytest.raises(RegistryAddressIndexError, match="stale"):
        validate_index_fast(source, index)

    rebuilt = build_index(source, index, force=True, min_free_gib=0)
    assert rebuilt["metrics"]["agents"]["rows"] == 1
    updated = search_addresses(
        "UPDATED AVENUE", 20, source_path=source, index_path=index
    )
    assert [row["entity_name"] for row in updated["entities"]] == ["Beta Limited"]
    writer.close()


def test_free_space_preflight_leaves_no_partial_sidecar(
    registry_paths: tuple[Path, Path],
) -> None:
    source, index = registry_paths
    with pytest.raises(RegistryAddressIndexError, match="Insufficient free space"):
        build_index(source, index, min_free_gib=10**9)
    assert not index.exists()
    assert not list(index.parent.glob(index.name + ".tmp-*"))

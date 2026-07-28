#!/usr/bin/env python3
"""Content-addressed storage and evidence provenance for public records.

The store keeps bytes under their SHA-256 digest and records acquisitions,
derived representations, extracted field evidence, and restriction events as
append-only observations. Rights, retention, and restriction values are
source-specific metadata; restriction events also maintain a queryable current
state projection without altering the underlying audit history.

Usage:
    uv run python tools/public_records_artifacts.py init
    uv run python tools/public_records_artifacts.py put deed.pdf \
      --source-id us-nyc-acris --canonical-ref PROPERTY:us-nyc-acris:doc:123
    uv run python tools/public_records_artifacts.py verify --output verify.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, utc_now_iso
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, utc_now_iso


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "datasets" / "public_records_artifacts.db"
DEFAULT_STORE = PROJECT_ROOT / "datasets" / "public_records_artifacts"
SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TARGET_TYPES = frozenset(
    {"artifact", "acquisition", "representation", "evidence", "canonical_ref"}
)
_JSON_COLUMNS = frozenset(
    {
        "retrieval_json",
        "receipt_json",
        "rights_json",
        "retention_json",
        "restriction_json",
        "parameters_json",
        "metadata_json",
        "region_json",
        "field_value_json",
        "validation_details_json",
        "details_json",
    }
)


class ArtifactStoreError(RuntimeError):
    """Base error raised by the public-record artifact store."""


class ArtifactNotFoundError(ArtifactStoreError):
    """Raised when a referenced artifact or observation is absent."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Raised when stored bytes do not match their recorded digest."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact (
    sha256 TEXT PRIMARY KEY,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    storage_relpath TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    first_media_type TEXT,
    first_filename TEXT,
    CHECK (length(sha256) = 64)
);

CREATE TABLE IF NOT EXISTS acquisition_observation (
    acquisition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_ref TEXT NOT NULL UNIQUE,
    artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
    source_id TEXT NOT NULL,
    canonical_ref TEXT NOT NULL,
    source_url TEXT,
    retrieved_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    retrieval_method TEXT,
    receipt_ref TEXT,
    rights_state TEXT,
    retention_state TEXT,
    restriction_state TEXT,
    media_type TEXT,
    original_filename TEXT,
    retrieval_json TEXT NOT NULL DEFAULT '{}',
    receipt_json TEXT NOT NULL DEFAULT '{}',
    rights_json TEXT NOT NULL DEFAULT '{}',
    retention_json TEXT NOT NULL DEFAULT '{}',
    restriction_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_acquisition_artifact
    ON acquisition_observation(artifact_sha256);
CREATE INDEX IF NOT EXISTS idx_acquisition_source_ref
    ON acquisition_observation(source_id, canonical_ref);
CREATE INDEX IF NOT EXISTS idx_acquisition_retrieved
    ON acquisition_observation(retrieved_at);

CREATE TABLE IF NOT EXISTS representation (
    representation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    representation_ref TEXT NOT NULL UNIQUE,
    parent_artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
    artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
    acquisition_id INTEGER REFERENCES acquisition_observation(acquisition_id),
    parent_representation_id INTEGER REFERENCES representation(representation_id),
    representation_type TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    ocr_engine TEXT,
    ocr_version TEXT,
    parser_name TEXT,
    parser_version TEXT,
    model_name TEXT,
    model_version TEXT,
    prompt_id TEXT,
    prompt_version TEXT,
    schema_id TEXT,
    schema_version TEXT,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    derivation_fingerprint TEXT NOT NULL UNIQUE,
    CHECK (
        parent_representation_id IS NULL
        OR parent_representation_id != representation_id
    )
);
CREATE INDEX IF NOT EXISTS idx_representation_parent
    ON representation(parent_artifact_sha256);
CREATE INDEX IF NOT EXISTS idx_representation_artifact
    ON representation(artifact_sha256);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_ref TEXT NOT NULL UNIQUE,
    evidence_fingerprint TEXT NOT NULL UNIQUE,
    artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
    acquisition_id INTEGER REFERENCES acquisition_observation(acquisition_id),
    representation_id INTEGER REFERENCES representation(representation_id),
    page_number INTEGER,
    page_label TEXT,
    region_json TEXT,
    exact_quote TEXT,
    quote_sha256 TEXT,
    field_name TEXT NOT NULL,
    field_value_json TEXT NOT NULL,
    validation_state TEXT NOT NULL,
    validator_name TEXT NOT NULL,
    validator_version TEXT NOT NULL,
    validation_details_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    confidence_ceiling REAL NOT NULL
        CHECK (confidence_ceiling >= 0.0 AND confidence_ceiling <= 1.0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK (page_number IS NULL OR page_number >= 1),
    CHECK (confidence <= confidence_ceiling),
    CHECK (
        page_number IS NOT NULL
        OR page_label IS NOT NULL
        OR region_json IS NOT NULL
        OR exact_quote IS NOT NULL
    )
);
CREATE INDEX IF NOT EXISTS idx_evidence_artifact
    ON evidence(artifact_sha256);
CREATE INDEX IF NOT EXISTS idx_evidence_field
    ON evidence(field_name, validation_state);

CREATE TABLE IF NOT EXISTS restriction_event (
    restriction_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    restriction_ref TEXT NOT NULL UNIQUE,
    event_fingerprint TEXT NOT NULL UNIQUE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    state TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    reason TEXT,
    authority_ref TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    supersedes_event_id INTEGER REFERENCES restriction_event(restriction_event_id),
    CHECK (
        target_type IN (
            'artifact', 'acquisition', 'representation', 'evidence',
            'canonical_ref'
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_restriction_target
    ON restriction_event(target_type, target_id, effective_at);

CREATE TABLE IF NOT EXISTS restriction_projection (
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    current_event_id INTEGER NOT NULL
        REFERENCES restriction_event(restriction_event_id),
    source_id TEXT NOT NULL,
    state TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (target_type, target_id)
);

CREATE TRIGGER IF NOT EXISTS artifact_no_update
BEFORE UPDATE ON artifact
BEGIN
    SELECT RAISE(ABORT, 'artifact rows are immutable');
END;
CREATE TRIGGER IF NOT EXISTS artifact_no_delete
BEFORE DELETE ON artifact
BEGIN
    SELECT RAISE(ABORT, 'artifact rows are immutable');
END;

CREATE TRIGGER IF NOT EXISTS acquisition_no_update
BEFORE UPDATE ON acquisition_observation
BEGIN
    SELECT RAISE(ABORT, 'acquisition observations are immutable');
END;
CREATE TRIGGER IF NOT EXISTS acquisition_no_delete
BEFORE DELETE ON acquisition_observation
BEGIN
    SELECT RAISE(ABORT, 'acquisition observations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS representation_no_update
BEFORE UPDATE ON representation
BEGIN
    SELECT RAISE(ABORT, 'representation links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS representation_no_delete
BEFORE DELETE ON representation
BEGIN
    SELECT RAISE(ABORT, 'representation links are immutable');
END;

CREATE TRIGGER IF NOT EXISTS evidence_no_update
BEFORE UPDATE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'evidence rows are immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete
BEFORE DELETE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'evidence rows are immutable');
END;

CREATE TRIGGER IF NOT EXISTS restriction_event_no_update
BEFORE UPDATE ON restriction_event
BEGIN
    SELECT RAISE(ABORT, 'restriction events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS restriction_event_no_delete
BEFORE DELETE ON restriction_event
BEGIN
    SELECT RAISE(ABORT, 'restriction events are immutable');
END;
"""


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _normalize_sha256(value: str) -> str:
    digest = _require_text(value, "sha256").lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    return digest


def _normalize_timestamp(value: str | datetime | None, field_name: str) -> str:
    if value is None:
        return utc_now_iso()
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from exc
    else:
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_json_value(value: Any, field_name: str) -> Any:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-compatible data") from exc


def _normalize_mapping(value: Mapping[str, Any] | None, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    normalized = _normalize_json_value(value, field_name)
    if not isinstance(normalized, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return normalized


def _json_text(value: Any) -> str:
    return canonical_json(value)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_confidence(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number from 0 to 1")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{field_name} must be a number from 0 to 1")
    return result


def _normalize_region(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    region = _normalize_mapping(value, "region")
    bbox_keys = ("x", "y", "width", "height")
    provided = [key for key in bbox_keys if key in region]
    if provided and len(provided) != len(bbox_keys):
        raise ValueError("region bounding boxes require x, y, width, and height")
    if provided:
        for key in bbox_keys:
            coordinate = region[key]
            if (
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                or not math.isfinite(float(coordinate))
            ):
                raise ValueError(f"region {key} must be a finite number")
        if float(region["x"]) < 0 or float(region["y"]) < 0:
            raise ValueError("region x and y must be non-negative")
        if float(region["width"]) <= 0 or float(region["height"]) <= 0:
            raise ValueError("region width and height must be positive")
    return region


def _parse_json_argument(value: str | None, field_name: str) -> Any:
    if value is None:
        return {}
    raw = value
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} is not valid JSON: {exc.msg}") from exc


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in _JSON_COLUMNS.intersection(result):
        if result[key] is not None:
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


def connect_artifact_db(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open and initialize an artifact metadata database in WAL mode."""

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 5000")
    db.executescript(SCHEMA)
    db.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()
    return db


class PublicRecordsArtifactStore:
    """SQLite provenance index plus a filesystem SHA-256 object store."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB,
        store_root: str | Path = DEFAULT_STORE,
    ) -> None:
        self.db_path = Path(db_path)
        self.store_root = Path(store_root)
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.db = connect_artifact_db(self.db_path)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> PublicRecordsArtifactStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _relpath(digest: str) -> Path:
        return Path("sha256") / digest[:2] / digest[2:4] / digest

    def artifact_path(self, digest: str) -> Path:
        """Return the expected path for a digest."""

        normalized = _normalize_sha256(digest)
        return self.store_root / self._relpath(normalized)

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                hasher.update(chunk)
                size += len(chunk)
        return hasher.hexdigest(), size

    def _install_stream(
        self,
        source: BinaryIO,
        *,
        media_type: str | None,
        filename: str | None,
    ) -> tuple[dict[str, Any], bool]:
        temp_dir = self.store_root / ".tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temporary:
                temp_path = Path(temporary.name)
                while chunk := source.read(1024 * 1024):
                    hasher.update(chunk)
                    size += len(chunk)
                    temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())

            digest = hasher.hexdigest()
            relpath = self._relpath(digest)
            target = self.store_root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            if existed:
                existing_digest, existing_size = self._hash_file(target)
                if existing_digest != digest or existing_size != size:
                    raise ArtifactIntegrityError(
                        f"existing object {digest} does not match its content address"
                    )
                temp_path.unlink()
                temp_path = None
            else:
                os.replace(temp_path, target)
                temp_path = None

            existing_row = self.db.execute(
                "SELECT * FROM artifact WHERE sha256 = ?", (digest,)
            ).fetchone()
            if existing_row is not None:
                if (
                    existing_row["size_bytes"] != size
                    or existing_row["storage_relpath"] != str(relpath)
                ):
                    raise ArtifactIntegrityError(
                        f"artifact metadata for {digest} conflicts with stored bytes"
                    )
                deduplicated = True
            else:
                self.db.execute(
                    """
                    INSERT INTO artifact(
                        sha256, size_bytes, storage_relpath, created_at,
                        first_media_type, first_filename
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        digest,
                        size,
                        str(relpath),
                        utc_now_iso(),
                        _optional_text(media_type, "media_type"),
                        _optional_text(filename, "filename"),
                    ),
                )
                self.db.commit()
                deduplicated = existed
            row = self.db.execute(
                "SELECT * FROM artifact WHERE sha256 = ?", (digest,)
            ).fetchone()
            return _row_to_dict(row) or {}, deduplicated
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def store_file(
        self,
        path: str | Path,
        *,
        media_type: str | None = None,
        filename: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Store a file by content hash without creating an acquisition."""

        source_path = Path(path)
        if not source_path.is_file():
            raise FileNotFoundError(f"artifact file not found: {source_path}")
        with source_path.open("rb") as source:
            return self._install_stream(
                source,
                media_type=media_type,
                filename=filename or source_path.name,
            )

    def store_bytes(
        self,
        content: bytes,
        *,
        media_type: str | None = None,
        filename: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Store in-memory bytes by content hash without an acquisition."""

        import io

        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        return self._install_stream(
            io.BytesIO(content), media_type=media_type, filename=filename
        )

    def _require_artifact(self, digest: str) -> sqlite3.Row:
        normalized = _normalize_sha256(digest)
        row = self.db.execute(
            "SELECT * FROM artifact WHERE sha256 = ?", (normalized,)
        ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"artifact not found: {normalized}")
        return row

    def record_acquisition(
        self,
        artifact_sha256: str,
        *,
        source_id: str,
        canonical_ref: str,
        source_url: str | None = None,
        retrieved_at: str | datetime | None = None,
        retrieval_method: str | None = None,
        receipt_ref: str | None = None,
        rights_state: str | None = None,
        retention_state: str | None = None,
        restriction_state: str | None = None,
        media_type: str | None = None,
        original_filename: str | None = None,
        retrieval: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
        rights: Mapping[str, Any] | None = None,
        retention: Mapping[str, Any] | None = None,
        restriction: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an immutable acquisition observation for stored content."""

        artifact = self._require_artifact(artifact_sha256)
        observation_ref = f"ACQ:{uuid.uuid4()}"
        values = {
            "retrieval": _normalize_mapping(retrieval, "retrieval"),
            "receipt": _normalize_mapping(receipt, "receipt"),
            "rights": _normalize_mapping(rights, "rights"),
            "retention": _normalize_mapping(retention, "retention"),
            "restriction": _normalize_mapping(restriction, "restriction"),
            "metadata": _normalize_mapping(metadata, "metadata"),
        }
        cursor = self.db.execute(
            """
            INSERT INTO acquisition_observation(
                observation_ref, artifact_sha256, source_id, canonical_ref,
                source_url, retrieved_at, recorded_at, retrieval_method,
                receipt_ref, rights_state, retention_state, restriction_state,
                media_type, original_filename, retrieval_json, receipt_json,
                rights_json, retention_json, restriction_json, metadata_json
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                observation_ref,
                artifact["sha256"],
                _require_text(source_id, "source_id"),
                _require_text(canonical_ref, "canonical_ref"),
                _optional_text(source_url, "source_url"),
                _normalize_timestamp(retrieved_at, "retrieved_at"),
                utc_now_iso(),
                _optional_text(retrieval_method, "retrieval_method"),
                _optional_text(receipt_ref, "receipt_ref"),
                _optional_text(rights_state, "rights_state"),
                _optional_text(retention_state, "retention_state"),
                _optional_text(restriction_state, "restriction_state"),
                _optional_text(media_type, "media_type"),
                _optional_text(original_filename, "original_filename"),
                _json_text(values["retrieval"]),
                _json_text(values["receipt"]),
                _json_text(values["rights"]),
                _json_text(values["retention"]),
                _json_text(values["restriction"]),
                _json_text(values["metadata"]),
            ),
        )
        self.db.commit()
        return self.get_acquisition(cursor.lastrowid)

    def put_file(
        self,
        path: str | Path,
        *,
        source_id: str,
        canonical_ref: str,
        source_url: str | None = None,
        retrieved_at: str | datetime | None = None,
        retrieval_method: str | None = None,
        receipt_ref: str | None = None,
        rights_state: str | None = None,
        retention_state: str | None = None,
        restriction_state: str | None = None,
        media_type: str | None = None,
        retrieval: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
        rights: Mapping[str, Any] | None = None,
        retention: Mapping[str, Any] | None = None,
        restriction: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store file content and append its acquisition observation."""

        source_path = Path(path)
        artifact, deduplicated = self.store_file(
            source_path, media_type=media_type, filename=source_path.name
        )
        acquisition = self.record_acquisition(
            artifact["sha256"],
            source_id=source_id,
            canonical_ref=canonical_ref,
            source_url=source_url,
            retrieved_at=retrieved_at,
            retrieval_method=retrieval_method,
            receipt_ref=receipt_ref,
            rights_state=rights_state,
            retention_state=retention_state,
            restriction_state=restriction_state,
            media_type=media_type,
            original_filename=source_path.name,
            retrieval=retrieval,
            receipt=receipt,
            rights=rights,
            retention=retention,
            restriction=restriction,
            metadata=metadata,
        )
        return {
            "status": "ok",
            "deduplicated_content": deduplicated,
            "artifact": artifact,
            "acquisition": acquisition,
        }

    def _require_acquisition(self, identifier: int | str) -> sqlite3.Row:
        if isinstance(identifier, int) or str(identifier).isdigit():
            row = self.db.execute(
                "SELECT * FROM acquisition_observation WHERE acquisition_id = ?",
                (int(identifier),),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM acquisition_observation WHERE observation_ref = ?",
                (str(identifier),),
            ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"acquisition not found: {identifier}")
        return row

    def get_acquisition(self, identifier: int | str) -> dict[str, Any]:
        return _row_to_dict(self._require_acquisition(identifier)) or {}

    def _require_representation(self, identifier: int | str) -> sqlite3.Row:
        if isinstance(identifier, int) or str(identifier).isdigit():
            row = self.db.execute(
                "SELECT * FROM representation WHERE representation_id = ?",
                (int(identifier),),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM representation WHERE representation_ref = ?",
                (str(identifier),),
            ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"representation not found: {identifier}")
        return row

    def get_representation(self, identifier: int | str) -> dict[str, Any]:
        return _row_to_dict(self._require_representation(identifier)) or {}

    @staticmethod
    def _validate_version_pair(
        name: str | None,
        version: str | None,
        name_field: str,
        version_field: str,
    ) -> tuple[str | None, str | None]:
        normalized_name = _optional_text(name, name_field)
        normalized_version = _optional_text(version, version_field)
        if (normalized_name is None) != (normalized_version is None):
            raise ValueError(
                f"{name_field} and {version_field} must be provided together"
            )
        return normalized_name, normalized_version

    def add_representation(
        self,
        parent_artifact_sha256: str,
        path: str | Path,
        *,
        representation_type: str,
        media_type: str | None = None,
        generated_at: str | datetime | None = None,
        acquisition_id: int | str | None = None,
        parent_representation_id: int | str | None = None,
        ocr_engine: str | None = None,
        ocr_version: str | None = None,
        parser_name: str | None = None,
        parser_version: str | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
        schema_id: str | None = None,
        schema_version: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store derived bytes and append a versioned provenance link."""

        parent = self._require_artifact(parent_artifact_sha256)
        acquisition = (
            self._require_acquisition(acquisition_id)
            if acquisition_id is not None
            else None
        )
        parent_representation = (
            self._require_representation(parent_representation_id)
            if parent_representation_id is not None
            else None
        )
        version_pairs = {
            "ocr": self._validate_version_pair(
                ocr_engine, ocr_version, "ocr_engine", "ocr_version"
            ),
            "parser": self._validate_version_pair(
                parser_name, parser_version, "parser_name", "parser_version"
            ),
            "model": self._validate_version_pair(
                model_name, model_version, "model_name", "model_version"
            ),
            "prompt": self._validate_version_pair(
                prompt_id, prompt_version, "prompt_id", "prompt_version"
            ),
            "schema": self._validate_version_pair(
                schema_id, schema_version, "schema_id", "schema_version"
            ),
        }
        normalized_parameters = _normalize_mapping(parameters, "parameters")
        normalized_metadata = _normalize_mapping(metadata, "metadata")
        artifact, content_deduplicated = self.store_file(
            path, media_type=media_type, filename=Path(path).name
        )
        fingerprint_payload = {
            "parent_artifact_sha256": parent["sha256"],
            "artifact_sha256": artifact["sha256"],
            "acquisition_id": acquisition["acquisition_id"] if acquisition else None,
            "parent_representation_id": (
                parent_representation["representation_id"]
                if parent_representation
                else None
            ),
            "representation_type": _require_text(
                representation_type, "representation_type"
            ),
            "versions": version_pairs,
            "parameters": normalized_parameters,
            "metadata": normalized_metadata,
        }
        derivation_fingerprint = _fingerprint(fingerprint_payload)
        existing = self.db.execute(
            """
            SELECT * FROM representation WHERE derivation_fingerprint = ?
            """,
            (derivation_fingerprint,),
        ).fetchone()
        if existing is not None:
            return {
                "status": "ok",
                "deduplicated_content": content_deduplicated,
                "deduplicated_link": True,
                "artifact": artifact,
                "representation": _row_to_dict(existing),
            }

        cursor = self.db.execute(
            """
            INSERT INTO representation(
                representation_ref, parent_artifact_sha256, artifact_sha256,
                acquisition_id, parent_representation_id, representation_type,
                generated_at, recorded_at, ocr_engine, ocr_version, parser_name,
                parser_version, model_name, model_version, prompt_id,
                prompt_version, schema_id, schema_version, parameters_json,
                metadata_json, derivation_fingerprint
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                f"REP:{uuid.uuid4()}",
                parent["sha256"],
                artifact["sha256"],
                acquisition["acquisition_id"] if acquisition else None,
                (
                    parent_representation["representation_id"]
                    if parent_representation
                    else None
                ),
                fingerprint_payload["representation_type"],
                _normalize_timestamp(generated_at, "generated_at"),
                utc_now_iso(),
                *version_pairs["ocr"],
                *version_pairs["parser"],
                *version_pairs["model"],
                *version_pairs["prompt"],
                *version_pairs["schema"],
                _json_text(normalized_parameters),
                _json_text(normalized_metadata),
                derivation_fingerprint,
            ),
        )
        self.db.commit()
        return {
            "status": "ok",
            "deduplicated_content": content_deduplicated,
            "deduplicated_link": False,
            "artifact": artifact,
            "representation": self.get_representation(cursor.lastrowid),
        }

    def _require_evidence(self, identifier: int | str) -> sqlite3.Row:
        if isinstance(identifier, int) or str(identifier).isdigit():
            row = self.db.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?", (int(identifier),)
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM evidence WHERE evidence_ref = ?", (str(identifier),)
            ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"evidence not found: {identifier}")
        return row

    def get_evidence(self, identifier: int | str) -> dict[str, Any]:
        return _row_to_dict(self._require_evidence(identifier)) or {}

    def add_evidence(
        self,
        artifact_sha256: str,
        *,
        field_name: str,
        field_value: Any,
        validation_state: str,
        validator_name: str,
        validator_version: str,
        confidence: float,
        confidence_ceiling: float | None = None,
        acquisition_id: int | str | None = None,
        representation_id: int | str | None = None,
        page_number: int | None = None,
        page_label: str | None = None,
        region: Mapping[str, Any] | None = None,
        exact_quote: str | None = None,
        validation_details: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an extracted field with page/region/quote provenance."""

        artifact = self._require_artifact(artifact_sha256)
        acquisition = (
            self._require_acquisition(acquisition_id)
            if acquisition_id is not None
            else None
        )
        representation = (
            self._require_representation(representation_id)
            if representation_id is not None
            else None
        )
        if representation is not None and (
            representation["artifact_sha256"] != artifact["sha256"]
        ):
            raise ValueError(
                "representation_id must identify the evidence artifact"
            )
        if page_number is not None and (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            raise ValueError("page_number must be a positive integer")
        normalized_page_label = _optional_text(page_label, "page_label")
        normalized_region = _normalize_region(region)
        if exact_quote is not None:
            if not isinstance(exact_quote, str) or not exact_quote:
                raise ValueError("exact_quote must be a non-empty string")
            normalized_quote = exact_quote
        else:
            normalized_quote = None
        if (
            page_number is None
            and normalized_page_label is None
            and normalized_region is None
            and normalized_quote is None
        ):
            raise ValueError(
                "evidence requires a page number, page label, region, or quote"
            )

        normalized_confidence = _normalize_confidence(confidence, "confidence")
        normalized_ceiling = _normalize_confidence(
            confidence if confidence_ceiling is None else confidence_ceiling,
            "confidence_ceiling",
        )
        if normalized_confidence > normalized_ceiling:
            raise ValueError("confidence cannot exceed confidence_ceiling")
        normalized_value = _normalize_json_value(field_value, "field_value")
        normalized_validation = _normalize_mapping(
            validation_details, "validation_details"
        )
        normalized_metadata = _normalize_mapping(metadata, "metadata")
        payload = {
            "artifact_sha256": artifact["sha256"],
            "acquisition_id": acquisition["acquisition_id"] if acquisition else None,
            "representation_id": (
                representation["representation_id"] if representation else None
            ),
            "page_number": page_number,
            "page_label": normalized_page_label,
            "region": normalized_region,
            "exact_quote": normalized_quote,
            "field_name": _require_text(field_name, "field_name"),
            "field_value": normalized_value,
            "validation_state": _require_text(
                validation_state, "validation_state"
            ),
            "validator_name": _require_text(validator_name, "validator_name"),
            "validator_version": _require_text(
                validator_version, "validator_version"
            ),
            "validation_details": normalized_validation,
            "confidence": normalized_confidence,
            "confidence_ceiling": normalized_ceiling,
            "metadata": normalized_metadata,
        }
        evidence_fingerprint = _fingerprint(payload)
        existing = self.db.execute(
            "SELECT * FROM evidence WHERE evidence_fingerprint = ?",
            (evidence_fingerprint,),
        ).fetchone()
        if existing is not None:
            return {
                "status": "ok",
                "deduplicated_evidence": True,
                "evidence": _row_to_dict(existing),
            }

        cursor = self.db.execute(
            """
            INSERT INTO evidence(
                evidence_ref, evidence_fingerprint, artifact_sha256,
                acquisition_id, representation_id, page_number, page_label,
                region_json, exact_quote, quote_sha256, field_name,
                field_value_json, validation_state, validator_name,
                validator_version, validation_details_json, confidence,
                confidence_ceiling, metadata_json, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                f"EVID:{uuid.uuid4()}",
                evidence_fingerprint,
                artifact["sha256"],
                acquisition["acquisition_id"] if acquisition else None,
                representation["representation_id"] if representation else None,
                page_number,
                normalized_page_label,
                (
                    _json_text(normalized_region)
                    if normalized_region is not None
                    else None
                ),
                normalized_quote,
                (
                    hashlib.sha256(normalized_quote.encode("utf-8")).hexdigest()
                    if normalized_quote is not None
                    else None
                ),
                payload["field_name"],
                _json_text(normalized_value),
                payload["validation_state"],
                payload["validator_name"],
                payload["validator_version"],
                _json_text(normalized_validation),
                normalized_confidence,
                normalized_ceiling,
                _json_text(normalized_metadata),
                utc_now_iso(),
            ),
        )
        self.db.commit()
        return {
            "status": "ok",
            "deduplicated_evidence": False,
            "evidence": self.get_evidence(cursor.lastrowid),
        }

    def _normalize_restriction_target(
        self, target_type: str, target_id: str | int
    ) -> tuple[str, str]:
        normalized_type = _require_text(target_type, "target_type")
        if normalized_type not in _TARGET_TYPES:
            raise ValueError(
                f"target_type must be one of {', '.join(sorted(_TARGET_TYPES))}"
            )
        if normalized_type == "artifact":
            return normalized_type, self._require_artifact(str(target_id))["sha256"]
        if normalized_type == "acquisition":
            return (
                normalized_type,
                self._require_acquisition(target_id)["observation_ref"],
            )
        if normalized_type == "representation":
            return (
                normalized_type,
                self._require_representation(target_id)["representation_ref"],
            )
        if normalized_type == "evidence":
            return normalized_type, self._require_evidence(target_id)["evidence_ref"]
        return normalized_type, _require_text(str(target_id), "target_id")

    def _get_restriction_event(self, identifier: int | str) -> sqlite3.Row:
        if isinstance(identifier, int) or str(identifier).isdigit():
            row = self.db.execute(
                """
                SELECT * FROM restriction_event WHERE restriction_event_id = ?
                """,
                (int(identifier),),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM restriction_event WHERE restriction_ref = ?",
                (str(identifier),),
            ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(f"restriction event not found: {identifier}")
        return row

    def add_restriction(
        self,
        target_type: str,
        target_id: str | int,
        *,
        source_id: str,
        state: str,
        effective_at: str | datetime | None = None,
        reason: str | None = None,
        authority_ref: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a restriction-state event and refresh its latest projection."""

        normalized_type, normalized_id = self._normalize_restriction_target(
            target_type, target_id
        )
        normalized_effective = _normalize_timestamp(effective_at, "effective_at")
        normalized_details = _normalize_mapping(details, "details")
        current = self.db.execute(
            """
            SELECT current_event_id FROM restriction_projection
            WHERE target_type = ? AND target_id = ?
            """,
            (normalized_type, normalized_id),
        ).fetchone()
        payload = {
            "target_type": normalized_type,
            "target_id": normalized_id,
            "source_id": _require_text(source_id, "source_id"),
            "state": _require_text(state, "state"),
            "effective_at": normalized_effective,
            "reason": _optional_text(reason, "reason"),
            "authority_ref": _optional_text(authority_ref, "authority_ref"),
            "details": normalized_details,
            "supersedes_event_id": current["current_event_id"] if current else None,
        }
        event_fingerprint = _fingerprint(
            {
                key: value
                for key, value in payload.items()
                if key != "supersedes_event_id"
            }
        )
        existing = self.db.execute(
            """
            SELECT * FROM restriction_event WHERE event_fingerprint = ?
            """,
            (event_fingerprint,),
        ).fetchone()
        if existing is None:
            cursor = self.db.execute(
                """
                INSERT INTO restriction_event(
                    restriction_ref, event_fingerprint, target_type, target_id,
                    source_id, state, effective_at, recorded_at, reason,
                    authority_ref, details_json, supersedes_event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"RST:{uuid.uuid4()}",
                    event_fingerprint,
                    normalized_type,
                    normalized_id,
                    payload["source_id"],
                    payload["state"],
                    normalized_effective,
                    utc_now_iso(),
                    payload["reason"],
                    payload["authority_ref"],
                    _json_text(normalized_details),
                    payload["supersedes_event_id"],
                ),
            )
            event_id = cursor.lastrowid
            deduplicated = False
        else:
            event_id = existing["restriction_event_id"]
            deduplicated = True

        latest = self.db.execute(
            """
            SELECT * FROM restriction_event
            WHERE target_type = ? AND target_id = ?
            ORDER BY effective_at DESC, restriction_event_id DESC
            LIMIT 1
            """,
            (normalized_type, normalized_id),
        ).fetchone()
        assert latest is not None
        self.db.execute(
            """
            INSERT INTO restriction_projection(
                target_type, target_id, current_event_id, source_id, state,
                effective_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_type, target_id) DO UPDATE SET
                current_event_id = excluded.current_event_id,
                source_id = excluded.source_id,
                state = excluded.state,
                effective_at = excluded.effective_at,
                updated_at = excluded.updated_at
            """,
            (
                normalized_type,
                normalized_id,
                latest["restriction_event_id"],
                latest["source_id"],
                latest["state"],
                latest["effective_at"],
                utc_now_iso(),
            ),
        )
        self.db.commit()
        event = _row_to_dict(self._get_restriction_event(event_id))
        projection = _row_to_dict(
            self.db.execute(
                """
                SELECT * FROM restriction_projection
                WHERE target_type = ? AND target_id = ?
                """,
                (normalized_type, normalized_id),
            ).fetchone()
        )
        return {
            "status": "ok",
            "deduplicated_event": deduplicated,
            "event": event,
            "current": projection,
        }

    def show(self, kind: str, identifier: str | int) -> dict[str, Any]:
        """Return one artifact-store object and its current restriction state."""

        singular = kind.rstrip("s")
        if singular == "artifact":
            row = _row_to_dict(self._require_artifact(str(identifier))) or {}
            stable_id = row["sha256"]
            row["path"] = str(self.artifact_path(stable_id))
            row["exists"] = Path(row["path"]).is_file()
        elif singular == "acquisition":
            row = self.get_acquisition(identifier)
            stable_id = row["observation_ref"]
        elif singular == "representation":
            row = self.get_representation(identifier)
            stable_id = row["representation_ref"]
        elif singular == "evidence":
            row = self.get_evidence(identifier)
            stable_id = row["evidence_ref"]
        elif singular == "restriction":
            row = _row_to_dict(self._get_restriction_event(identifier)) or {}
            stable_id = row["target_id"]
            singular = row["target_type"]
        else:
            raise ValueError(f"unknown object kind: {kind}")

        row["current_restriction"] = _row_to_dict(
            self.db.execute(
                """
                SELECT * FROM restriction_projection
                WHERE target_type = ? AND target_id = ?
                """,
                (singular, stable_id),
            ).fetchone()
        )
        return row

    def list_records(
        self,
        kind: str,
        *,
        source_id: str | None = None,
        artifact_sha256: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List stored metadata with optional explicit filters."""

        normalized_kind = kind.rstrip("s")
        table_map = {
            "artifact": ("artifact", "created_at DESC"),
            "acquisition": ("acquisition_observation", "acquisition_id DESC"),
            "representation": ("representation", "representation_id DESC"),
            "evidence": ("evidence", "evidence_id DESC"),
            "restriction": ("restriction_event", "restriction_event_id DESC"),
        }
        if normalized_kind not in table_map:
            raise ValueError(f"unknown object kind: {kind}")
        if limit is not None and limit < 1:
            raise ValueError("limit must be a positive integer")
        table, order = table_map[normalized_kind]
        clauses: list[str] = []
        parameters: list[Any] = []
        columns = {
            row["name"] for row in self.db.execute(f"PRAGMA table_info({table})")
        }
        if source_id is not None:
            if "source_id" not in columns:
                raise ValueError(f"{normalized_kind} records have no source_id filter")
            clauses.append("source_id = ?")
            parameters.append(_require_text(source_id, "source_id"))
        if artifact_sha256 is not None:
            digest = _normalize_sha256(artifact_sha256)
            if normalized_kind == "artifact":
                clauses.append("sha256 = ?")
            elif "artifact_sha256" in columns:
                clauses.append("artifact_sha256 = ?")
            else:
                raise ValueError(
                    f"{normalized_kind} records have no artifact_sha256 filter"
                )
            parameters.append(digest)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM {table}{where} ORDER BY {order}"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        return [
            _row_to_dict(row) or {}
            for row in self.db.execute(query, parameters).fetchall()
        ]

    def verify(self, artifact_sha256: str | None = None) -> dict[str, Any]:
        """Recompute stored object hashes and sizes."""

        if artifact_sha256 is None:
            rows = self.db.execute("SELECT * FROM artifact ORDER BY sha256").fetchall()
        else:
            rows = [self._require_artifact(artifact_sha256)]
        results: list[dict[str, Any]] = []
        for row in rows:
            expected = row["sha256"]
            expected_relpath = str(self._relpath(expected))
            path = self.store_root / row["storage_relpath"]
            result: dict[str, Any] = {
                "sha256": expected,
                "path": str(path),
                "expected_size_bytes": row["size_bytes"],
            }
            if row["storage_relpath"] != expected_relpath:
                result["status"] = "path_mismatch"
            elif not path.is_file():
                result["status"] = "missing"
            else:
                actual_digest, actual_size = self._hash_file(path)
                result["actual_sha256"] = actual_digest
                result["actual_size_bytes"] = actual_size
                if actual_digest != expected:
                    result["status"] = "hash_mismatch"
                elif actual_size != row["size_bytes"]:
                    result["status"] = "size_mismatch"
                else:
                    result["status"] = "ok"
            results.append(result)
        status_counts: dict[str, int] = {}
        for result in results:
            status = result["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "status": "ok" if status_counts.get("ok", 0) == len(results) else "failed",
            "checked": len(results),
            "status_counts": status_counts,
            "results": results,
        }

    def stats(self) -> dict[str, Any]:
        """Return database and content-store counts."""

        counts = {
            "artifacts": self.db.execute(
                "SELECT COUNT(*) FROM artifact"
            ).fetchone()[0],
            "acquisitions": self.db.execute(
                "SELECT COUNT(*) FROM acquisition_observation"
            ).fetchone()[0],
            "representations": self.db.execute(
                "SELECT COUNT(*) FROM representation"
            ).fetchone()[0],
            "evidence": self.db.execute(
                "SELECT COUNT(*) FROM evidence"
            ).fetchone()[0],
            "restriction_events": self.db.execute(
                "SELECT COUNT(*) FROM restriction_event"
            ).fetchone()[0],
            "current_restrictions": self.db.execute(
                "SELECT COUNT(*) FROM restriction_projection"
            ).fetchone()[0],
        }
        total_bytes = self.db.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM artifact"
        ).fetchone()[0]
        restriction_states = {
            row["state"]: row["count"]
            for row in self.db.execute(
                """
                SELECT state, COUNT(*) AS count
                FROM restriction_projection
                GROUP BY state ORDER BY state
                """
            )
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "db_path": str(self.db_path),
            "store_root": str(self.store_root),
            "counts": counts,
            "content_bytes": total_bytes,
            "current_restriction_states": restriction_states,
        }


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Artifact metadata database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--store",
        default=str(DEFAULT_STORE),
        help=f"Content store directory (default: {DEFAULT_STORE})",
    )
    add_output_args(parser)


def _add_metadata_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--metadata-json",
        default="{}",
        help="JSON object or @FILE with source-specific metadata",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Content-addressed public-record artifact and evidence store"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the store")
    _add_common_arguments(init_parser)

    put_parser = subparsers.add_parser(
        "put", help="Store a file and append an acquisition observation"
    )
    put_parser.add_argument("file")
    put_parser.add_argument("--source-id", required=True)
    put_parser.add_argument("--canonical-ref", required=True)
    put_parser.add_argument("--source-url")
    put_parser.add_argument("--retrieved-at")
    put_parser.add_argument("--retrieval-method")
    put_parser.add_argument("--receipt-ref")
    put_parser.add_argument("--rights-state")
    put_parser.add_argument("--retention-state")
    put_parser.add_argument("--restriction-state")
    put_parser.add_argument("--media-type")
    for name in ("retrieval", "receipt", "rights", "retention", "restriction"):
        put_parser.add_argument(
            f"--{name}-json",
            default="{}",
            help=f"JSON object or @FILE with {name} metadata",
        )
    _add_metadata_arguments(put_parser)
    _add_common_arguments(put_parser)

    show_parser = subparsers.add_parser("show", help="Show one stored object")
    show_parser.add_argument(
        "kind",
        choices=(
            "artifact",
            "acquisition",
            "representation",
            "evidence",
            "restriction",
        ),
    )
    show_parser.add_argument("identifier")
    _add_common_arguments(show_parser)

    list_parser = subparsers.add_parser("list", help="List stored metadata")
    list_parser.add_argument(
        "kind",
        choices=(
            "artifacts",
            "acquisitions",
            "representations",
            "evidence",
            "restrictions",
        ),
    )
    list_parser.add_argument("--source-id")
    list_parser.add_argument("--artifact-sha256")
    list_parser.add_argument(
        "--limit", type=int, help="Maximum rows to return (default: all)"
    )
    _add_common_arguments(list_parser)

    rep_parser = subparsers.add_parser(
        "add-representation", help="Store and link a derived representation"
    )
    rep_parser.add_argument("file")
    rep_parser.add_argument("--parent-sha256", required=True)
    rep_parser.add_argument("--representation-type", required=True)
    rep_parser.add_argument("--media-type")
    rep_parser.add_argument("--generated-at")
    rep_parser.add_argument("--acquisition-id")
    rep_parser.add_argument("--parent-representation-id")
    rep_parser.add_argument("--ocr-engine")
    rep_parser.add_argument("--ocr-version")
    rep_parser.add_argument("--parser-name")
    rep_parser.add_argument("--parser-version")
    rep_parser.add_argument("--model-name")
    rep_parser.add_argument("--model-version")
    rep_parser.add_argument("--prompt-id")
    rep_parser.add_argument("--prompt-version")
    rep_parser.add_argument("--schema-id")
    rep_parser.add_argument("--schema-version")
    rep_parser.add_argument("--parameters-json", default="{}")
    _add_metadata_arguments(rep_parser)
    _add_common_arguments(rep_parser)

    evidence_parser = subparsers.add_parser(
        "add-evidence", help="Add page/region/quote evidence for a field"
    )
    evidence_parser.add_argument("--artifact-sha256", required=True)
    evidence_parser.add_argument("--acquisition-id")
    evidence_parser.add_argument("--representation-id")
    evidence_parser.add_argument("--page-number", type=int)
    evidence_parser.add_argument("--page-label")
    evidence_parser.add_argument("--region-json")
    evidence_parser.add_argument("--quote")
    evidence_parser.add_argument("--field-name", required=True)
    evidence_parser.add_argument("--field-value-json", required=True)
    evidence_parser.add_argument("--validation-state", required=True)
    evidence_parser.add_argument("--validator-name", required=True)
    evidence_parser.add_argument("--validator-version", required=True)
    evidence_parser.add_argument("--validation-details-json", default="{}")
    evidence_parser.add_argument("--confidence", type=float, required=True)
    evidence_parser.add_argument("--confidence-ceiling", type=float)
    _add_metadata_arguments(evidence_parser)
    _add_common_arguments(evidence_parser)

    restrict_parser = subparsers.add_parser(
        "restrict", help="Append a source-specific restriction-state event"
    )
    restrict_parser.add_argument(
        "--target-type", choices=tuple(sorted(_TARGET_TYPES)), required=True
    )
    restrict_parser.add_argument("--target-id", required=True)
    restrict_parser.add_argument("--source-id", required=True)
    restrict_parser.add_argument("--state", required=True)
    restrict_parser.add_argument("--effective-at")
    restrict_parser.add_argument("--reason")
    restrict_parser.add_argument("--authority-ref")
    restrict_parser.add_argument("--details-json", default="{}")
    _add_common_arguments(restrict_parser)

    verify_parser = subparsers.add_parser(
        "verify", help="Verify content hashes and sizes"
    )
    verify_parser.add_argument("--artifact-sha256")
    _add_common_arguments(verify_parser)

    stats_parser = subparsers.add_parser("stats", help="Show store statistics")
    _add_common_arguments(stats_parser)
    return parser


def _emit(data: Any, args: argparse.Namespace, summary: str) -> None:
    if write_output(data, args, summary=summary):
        return
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def _run(args: argparse.Namespace) -> tuple[Any, str]:
    with PublicRecordsArtifactStore(args.db, args.store) as store:
        if args.command == "init":
            return {
                "status": "ok",
                "schema_version": SCHEMA_VERSION,
                "db_path": str(store.db_path),
                "store_root": str(store.store_root),
            }, "artifact store initialized"
        if args.command == "put":
            payload = store.put_file(
                args.file,
                source_id=args.source_id,
                canonical_ref=args.canonical_ref,
                source_url=args.source_url,
                retrieved_at=args.retrieved_at,
                retrieval_method=args.retrieval_method,
                receipt_ref=args.receipt_ref,
                rights_state=args.rights_state,
                retention_state=args.retention_state,
                restriction_state=args.restriction_state,
                media_type=args.media_type,
                retrieval=_parse_json_argument(args.retrieval_json, "retrieval"),
                receipt=_parse_json_argument(args.receipt_json, "receipt"),
                rights=_parse_json_argument(args.rights_json, "rights"),
                retention=_parse_json_argument(args.retention_json, "retention"),
                restriction=_parse_json_argument(
                    args.restriction_json, "restriction"
                ),
                metadata=_parse_json_argument(args.metadata_json, "metadata"),
            )
            return payload, f"stored {payload['artifact']['sha256']}"
        if args.command == "show":
            return store.show(args.kind, args.identifier), f"show {args.kind}"
        if args.command == "list":
            records = store.list_records(
                args.kind,
                source_id=args.source_id,
                artifact_sha256=args.artifact_sha256,
                limit=args.limit,
            )
            return {
                "status": "ok",
                "kind": args.kind,
                "count": len(records),
                "records": records,
            }, f"listed {args.kind}"
        if args.command == "add-representation":
            payload = store.add_representation(
                args.parent_sha256,
                args.file,
                representation_type=args.representation_type,
                media_type=args.media_type,
                generated_at=args.generated_at,
                acquisition_id=args.acquisition_id,
                parent_representation_id=args.parent_representation_id,
                ocr_engine=args.ocr_engine,
                ocr_version=args.ocr_version,
                parser_name=args.parser_name,
                parser_version=args.parser_version,
                model_name=args.model_name,
                model_version=args.model_version,
                prompt_id=args.prompt_id,
                prompt_version=args.prompt_version,
                schema_id=args.schema_id,
                schema_version=args.schema_version,
                parameters=_parse_json_argument(args.parameters_json, "parameters"),
                metadata=_parse_json_argument(args.metadata_json, "metadata"),
            )
            return payload, "representation linked"
        if args.command == "add-evidence":
            payload = store.add_evidence(
                args.artifact_sha256,
                acquisition_id=args.acquisition_id,
                representation_id=args.representation_id,
                page_number=args.page_number,
                page_label=args.page_label,
                region=(
                    _parse_json_argument(args.region_json, "region")
                    if args.region_json is not None
                    else None
                ),
                exact_quote=args.quote,
                field_name=args.field_name,
                field_value=_parse_json_argument(
                    args.field_value_json, "field_value"
                ),
                validation_state=args.validation_state,
                validator_name=args.validator_name,
                validator_version=args.validator_version,
                validation_details=_parse_json_argument(
                    args.validation_details_json, "validation_details"
                ),
                confidence=args.confidence,
                confidence_ceiling=args.confidence_ceiling,
                metadata=_parse_json_argument(args.metadata_json, "metadata"),
            )
            return payload, "evidence added"
        if args.command == "restrict":
            payload = store.add_restriction(
                args.target_type,
                args.target_id,
                source_id=args.source_id,
                state=args.state,
                effective_at=args.effective_at,
                reason=args.reason,
                authority_ref=args.authority_ref,
                details=_parse_json_argument(args.details_json, "details"),
            )
            return payload, "restriction event added"
        if args.command == "verify":
            payload = store.verify(args.artifact_sha256)
            return payload, f"verified {payload['checked']} artifacts"
        if args.command == "stats":
            return store.stats(), "artifact store stats"
    raise ValueError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        data, summary = _run(args)
        _emit(data, args, summary)
        if args.command == "verify" and data["status"] != "ok":
            return 1
        return 0
    except (
        ArtifactStoreError,
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        sqlite3.Error,
    ) as exc:
        error = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _emit(error, args, f"{args.command} failed")
        return 2


if __name__ == "__main__":
    sys.exit(main())

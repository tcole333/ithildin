#!/usr/bin/env python3
"""Reconstruct the surviving first-page content of EFTA00597207.

The public DOJ file is a damaged, linearized PDF whose page tree and later
objects were overwritten.  Objects 387-397 remain byte-complete near the
beginning of the file.  This script:

* refuses input whose SHA-256 does not match the examined DOJ artifact;
* extracts and Flate-decodes the intact streams without modifying them;
* places the eight surviving page-content streams in a new one-page PDF;
* substitutes only the resources needed to make those streams render; and
* writes a provenance manifest that distinguishes recovered bytes from
  reconstruction scaffolding.

The result is a partial forensic reconstruction, not a repaired original.
Missing photograph/image objects are deliberately rendered as blank forms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
)

EXPECTED_SHA256 = "2e26567affd806b03b394821a15e6273108762cb21d43b8f9aa4b032b820ebd6"
EXPECTED_BYTES = 882_743
CONTENT_OBJECTS = (389, 390, 391, 392, 393, 394, 395, 397)
EXTRACT_OBJECTS = (387, 388, 396, *CONTENT_OBJECTS)


class ReconstructionError(ValueError):
    """Raised when the source does not match the verified damaged artifact."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def locate_flate_stream(data: bytes, object_number: int) -> dict[str, Any]:
    marker = f"{object_number} 0 obj".encode()
    object_offset = data.find(marker)
    if object_offset < 0:
        raise ReconstructionError(f"object {object_number} 0 not found")

    stream_keyword = data.find(b"stream", object_offset)
    if stream_keyword < 0:
        raise ReconstructionError(f"object {object_number} 0 has no stream")
    dictionary = data[object_offset:stream_keyword]
    if b"/FlateDecode" not in dictionary:
        raise ReconstructionError(
            f"object {object_number} 0 is not a FlateDecode stream"
        )
    length_match = re.search(rb"/Length\s+(\d+)", dictionary)
    if not length_match:
        raise ReconstructionError(f"object {object_number} 0 has no direct /Length")
    compressed_length = int(length_match.group(1))

    data_offset = stream_keyword + len(b"stream")
    if data[data_offset : data_offset + 2] == b"\r\n":
        data_offset += 2
    elif data[data_offset : data_offset + 1] in {b"\r", b"\n"}:
        data_offset += 1
    else:
        raise ReconstructionError(
            f"object {object_number} 0 stream has no line ending"
        )

    compressed = data[data_offset : data_offset + compressed_length]
    if len(compressed) != compressed_length:
        raise ReconstructionError(
            f"object {object_number} 0 stream is truncated"
        )
    try:
        decoded = zlib.decompress(compressed)
    except zlib.error as error:
        raise ReconstructionError(
            f"object {object_number} 0 does not decode cleanly: {error}"
        ) from error

    suffix = data[data_offset + compressed_length : data_offset + compressed_length + 16]
    if b"endstream" not in suffix:
        raise ReconstructionError(
            f"object {object_number} 0 lacks endstream at declared boundary"
        )

    return {
        "object_number": object_number,
        "object_offset": object_offset,
        "stream_data_offset": data_offset,
        "compressed_length": compressed_length,
        "compressed_sha256": sha256_bytes(compressed),
        "decoded_length": len(decoded),
        "decoded_sha256": sha256_bytes(decoded),
        "decoded": decoded,
    }


def number(value: int | float) -> NumberObject | FloatObject:
    if isinstance(value, int):
        return NumberObject(value)
    return FloatObject(value)


def array(*values: int | float) -> ArrayObject:
    return ArrayObject([number(value) for value in values])


def solid_pattern(red: float, green: float, blue: float) -> DecodedStreamObject:
    pattern = DecodedStreamObject()
    pattern.set_data(
        f"{red:.4f} {green:.4f} {blue:.4f} rg 0 0 1 1 re f\n".encode()
    )
    pattern.update(
        {
            NameObject("/Type"): NameObject("/Pattern"),
            NameObject("/PatternType"): NumberObject(1),
            NameObject("/PaintType"): NumberObject(1),
            NameObject("/TilingType"): NumberObject(1),
            NameObject("/BBox"): array(0, 0, 1, 1),
            NameObject("/XStep"): NumberObject(1),
            NameObject("/YStep"): NumberObject(1),
            NameObject("/Resources"): DictionaryObject(),
        }
    )
    return pattern


def blank_form() -> DecodedStreamObject:
    form = DecodedStreamObject()
    form.set_data(b"")
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/FormType"): NumberObject(1),
            NameObject("/BBox"): array(0, 0, 1, 1),
            NameObject("/Resources"): DictionaryObject(),
        }
    )
    return form


def rgb_image(raw_rgb: bytes) -> DecodedStreamObject:
    expected = 43 * 31 * 3
    if len(raw_rgb) != expected:
        raise ReconstructionError(
            f"object 396 decoded to {len(raw_rgb)} bytes, expected {expected}"
        )
    image = DecodedStreamObject()
    image.set_data(raw_rgb)
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(43),
            NameObject("/Height"): NumberObject(31),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/Interpolate"): BooleanObject(False),
        }
    )
    return image


def build_reconstruction(
    streams: dict[int, dict[str, Any]], output_path: Path
) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=780, height=540)

    identity_gstate = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/ExtGState"),
            NameObject("/BM"): NameObject("/Normal"),
            NameObject("/CA"): NumberObject(1),
            NameObject("/ca"): NumberObject(1),
        }
    )
    gstate_ref = writer._add_object(identity_gstate)

    substitute_font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    font_ref = writer._add_object(substitute_font)

    white_pattern_ref = writer._add_object(solid_pattern(1.0, 1.0, 1.0))
    black_pattern_ref = writer._add_object(solid_pattern(0.0, 0.0, 0.0))
    blank_image_ref = writer._add_object(blank_form())
    image8_ref = writer._add_object(rgb_image(streams[396]["decoded"]))

    resources = DictionaryObject(
        {
            NameObject("/ExtGState"): DictionaryObject(
                {
                    NameObject("/GS5"): gstate_ref,
                    NameObject("/GS20"): gstate_ref,
                }
            ),
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_ref}
            ),
            NameObject("/Pattern"): DictionaryObject(
                {
                    NameObject("/P6"): white_pattern_ref,
                    NameObject("/P13"): black_pattern_ref,
                    NameObject("/P15"): black_pattern_ref,
                    NameObject("/P17"): black_pattern_ref,
                }
            ),
            NameObject("/XObject"): DictionaryObject(
                {
                    NameObject("/Image7"): blank_image_ref,
                    NameObject("/Image8"): image8_ref,
                    NameObject("/Image10"): blank_image_ref,
                }
            ),
            NameObject("/ProcSet"): ArrayObject(
                [
                    NameObject("/PDF"),
                    NameObject("/Text"),
                    NameObject("/ImageB"),
                    NameObject("/ImageC"),
                    NameObject("/ImageI"),
                ]
            ),
        }
    )
    page[NameObject("/Resources")] = resources

    content_refs = ArrayObject()
    for object_number in CONTENT_OBJECTS:
        content = DecodedStreamObject()
        content.set_data(streams[object_number]["decoded"])
        content_refs.append(writer._add_object(content))
    page[NameObject("/Contents")] = content_refs

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    data = source.read_bytes()
    source_sha256 = sha256_bytes(data)
    if len(data) != EXPECTED_BYTES or source_sha256 != EXPECTED_SHA256:
        raise ReconstructionError(
            "source does not match verified EFTA00597207 artifact: "
            f"bytes={len(data)}, sha256={source_sha256}"
        )

    streams = {
        object_number: locate_flate_stream(data, object_number)
        for object_number in EXTRACT_OBJECTS
    }
    output_dir.mkdir(parents=True, exist_ok=True)

    for object_number in (*CONTENT_OBJECTS, 396, 387):
        suffix = "txt" if object_number != 396 else "rgb"
        target = output_dir / f"object-{object_number}-decoded.{suffix}"
        target.write_bytes(streams[object_number]["decoded"])

    reconstructed_pdf = output_dir / "EFTA00597207-partial-page-1.pdf"
    build_reconstruction(streams, reconstructed_pdf)

    reader = PdfReader(reconstructed_pdf, strict=True)
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    recovered_objects = []
    for object_number in EXTRACT_OBJECTS:
        record = {
            key: value
            for key, value in streams[object_number].items()
            if key != "decoded"
        }
        recovered_objects.append(record)

    manifest = {
        "schema_version": "epstein-partial-pdf-reconstruction/1.0",
        "created_at_utc": utc_now(),
        "efta_id": "EFTA00597207",
        "source": {
            "path": str(source),
            "public_url": (
                "https://www.justice.gov/epstein/files/"
                "DataSet%209/EFTA00597207.pdf"
            ),
            "bytes": len(data),
            "sha256": source_sha256,
        },
        "classification": "partial forensic reconstruction",
        "recovered_scope": {
            "page": 1,
            "page_count_claimed_by_damaged_header": 10,
            "original_page_box": [0, 0, 780, 540],
            "intact_content_stream_objects": list(CONTENT_OBJECTS),
            "supporting_stream_objects": [387, 388],
            "literal_text_extracted_from_reconstruction": extracted_text.strip(),
        },
        "recovered_objects": recovered_objects,
        "reconstruction": {
            "path": str(reconstructed_pdf),
            "bytes": reconstructed_pdf.stat().st_size,
            "sha256": sha256_bytes(reconstructed_pdf.read_bytes()),
            "substitutions": [
                "missing Image7 (object 399) replaced with a blank Form XObject",
                "missing Image10 (object 404) replaced with a blank Form XObject",
                "missing transparency mask for Image8 (object 400) omitted",
                "damaged embedded InterFace font (object 398) replaced by Helvetica",
                "missing gradient functions (objects 401 and 402) replaced by solid black patterns",
                "missing background image pattern P6 replaced by solid white",
                "missing ExtGState dictionaries replaced by identity ExtGState",
                "missing page tree rebuilt as a one-page container",
            ],
            "unchanged_evidence": [
                "all PDF drawing operators and coordinates in objects 389-397",
                "literal text operands in objects 389-397",
                "decoded RGB samples from intact object 396",
            ],
            "warning": (
                "This file is suitable for viewing surviving page-one vector "
                "content. It is not an authentic replacement for the original "
                "ten-page PDF, and substituted colors/fonts must not be treated "
                "as evidence."
            ),
        },
    }
    manifest_path = output_dir / "provenance.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "pdf": str(reconstructed_pdf),
                "manifest": str(manifest_path),
                "text": extracted_text.strip(),
                "sha256": manifest["reconstruction"]["sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

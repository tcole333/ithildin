#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import sys
from pathlib import Path

try:
    from warcio.archiveiterator import ArchiveIterator
except ImportError:
    ArchiveIterator = None

DEFAULT_WARC_DIR = Path("datasets/epstein_files_ds09_warc")
DEFAULT_OUT_DIR = Path("datasets/epstein_files_ds09_extracted")
DEFAULT_EXTENSIONS = "pdf,doc,docx,xls,xlsx,csv,ppt,pptx"


def shard_path(base_dir: Path, filename: str, ext: str, mode: str) -> Path:
    if mode == "none":
        return base_dir / filename
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()
    if mode == "hash2":
        return base_dir / digest[:2] / filename
    if mode == "ext-hash2":
        return base_dir / ext / digest[:2] / filename
    raise ValueError(f"Unknown shard mode: {mode}")


def iter_warc_files(warc_dir: Path):
    for path in sorted(warc_dir.glob("**/*.warc.gz")):
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract DS09 files from ArchiveTeam WARC downloads."
    )
    parser.add_argument(
        "--warc-dir",
        type=Path,
        default=DEFAULT_WARC_DIR,
        help=f"Directory with .warc.gz files (default: {DEFAULT_WARC_DIR})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Extraction output directory (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--extensions",
        default=DEFAULT_EXTENSIONS,
        help=f"Comma-separated extensions to keep (default: {DEFAULT_EXTENSIONS})",
    )
    parser.add_argument(
        "--shard",
        choices=["none", "hash2", "ext-hash2"],
        default="ext-hash2",
        help="Output sharding mode (default: ext-hash2).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Stop after extracting this many files (0 = no limit).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files if they already exist.",
    )

    args = parser.parse_args()

    if ArchiveIterator is None:
        print("Missing dependency: warcio", file=sys.stderr)
        print("Install with: python3 -m pip install warcio", file=sys.stderr)
        return 2

    exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    if not exts:
        print("No extensions specified.", file=sys.stderr)
        return 2

    if not args.warc_dir.exists():
        print(f"WARC dir not found: {args.warc_dir}", file=sys.stderr)
        return 2

    total_extracted = 0
    for warc_path in iter_warc_files(args.warc_dir):
        print(f"Reading: {warc_path}")
        with gzip.open(warc_path, "rb") as stream:
            for record in ArchiveIterator(stream):
                if record.rec_type != "response":
                    continue
                url = record.rec_headers.get_header("WARC-Target-URI")
                if not url:
                    continue
                if "/epstein/files/DataSet%209/" not in url:
                    continue
                filename = url.rsplit("/", 1)[-1]
                if "." not in filename:
                    continue
                ext = filename.rsplit(".", 1)[-1].lower()
                if ext not in exts:
                    continue

                out_path = shard_path(args.out_dir, filename, ext, args.shard)
                if out_path.exists() and not args.overwrite:
                    continue

                out_path.parent.mkdir(parents=True, exist_ok=True)
                payload = record.content_stream().read()
                with out_path.open("wb") as f:
                    f.write(payload)

                total_extracted += 1
                if args.max_files and total_extracted >= args.max_files:
                    print("Reached max files limit.")
                    return 0

    print(f"Extracted files: {total_extracted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

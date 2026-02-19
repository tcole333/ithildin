#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

DEFAULT_ITEMS_FILE = Path(__file__).with_name("ds09_warc_items.txt")
DEFAULT_OUT_DIR = Path("datasets/epstein_files_ds09_warc")


def load_items(path: Path) -> list[str]:
    items: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(line)
    return items


def fetch_metadata(identifier: str) -> dict:
    url = f"https://archive.org/metadata/{identifier}"
    with urlopen(url) as resp:
        return json.load(resp)


def iter_warc_entries(meta: dict) -> list[dict]:
    entries = []
    for f in meta.get("files", []):
        name = f.get("name", "")
        if not name.endswith(".warc.gz"):
            continue
        size = f.get("size")
        entries.append(
            {
                "name": name,
                "size": int(size) if size else None,
            }
        )
    return entries


def build_download_url(identifier: str, name: str) -> str:
    return f"https://archive.org/download/{identifier}/{name}"


def download_with_curl(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["curl", "-L", "-C", "-", "--output", str(dest), url]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch ArchiveTeam DS09 WARC files (PDF + office docs)."
    )
    parser.add_argument(
        "--items-file",
        type=Path,
        default=DEFAULT_ITEMS_FILE,
        help=f"Path to WARC identifier list (default: {DEFAULT_ITEMS_FILE})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Download directory (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download WARC files. Without this flag, only prints URLs.",
    )
    parser.add_argument(
        "--url-list",
        type=Path,
        help="Write WARC download URLs to a file.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Stop after this many WARC files (0 = no limit).",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help="Skip downloads when file already exists.",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Re-download files even if they already exist.",
    )

    args = parser.parse_args()

    if not args.items_file.exists():
        print(f"Items file not found: {args.items_file}", file=sys.stderr)
        return 2

    items = load_items(args.items_file)
    if not items:
        print("No identifiers found in items file.", file=sys.stderr)
        return 2

    all_entries = []
    for identifier in items:
        meta = fetch_metadata(identifier)
        entries = iter_warc_entries(meta)
        for entry in entries:
            url = build_download_url(identifier, entry["name"])
            all_entries.append(
                {
                    "identifier": identifier,
                    "name": entry["name"],
                    "size": entry["size"],
                    "url": url,
                }
            )

    total_size = sum(e["size"] or 0 for e in all_entries)
    print(f"WARC files: {len(all_entries)}")
    if total_size:
        print(f"Total size (bytes): {total_size}")

    if args.url_list:
        args.url_list.parent.mkdir(parents=True, exist_ok=True)
        with args.url_list.open("w") as f:
            for entry in all_entries:
                f.write(entry["url"] + "\n")
        print(f"Wrote URL list: {args.url_list}")

    if not args.download:
        if not args.url_list:
            for entry in all_entries:
                print(entry["url"])
        return 0

    downloaded = 0
    for entry in all_entries:
        dest = args.out_dir / entry["identifier"] / entry["name"]
        if args.skip_existing and dest.exists():
            if entry["size"] and dest.stat().st_size == entry["size"]:
                print(f"Skip (exists): {dest}")
                continue
            if args.skip_existing:
                print(f"Skip (exists, size unknown/mismatch): {dest}")
                continue

        print(f"Downloading: {entry['url']}")
        download_with_curl(entry["url"], dest)
        downloaded += 1
        if args.max_files and downloaded >= args.max_files:
            break

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

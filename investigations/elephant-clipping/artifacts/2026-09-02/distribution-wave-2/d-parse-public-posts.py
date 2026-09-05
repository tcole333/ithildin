import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_embed(path):
    raw = path.read_text()
    match = re.search(r'"contextJSON":"((?:\\.|[^"\\])*)"', raw)
    if not match:
        raise ValueError(f"No public contextJSON in {path.name}")
    context = json.loads(json.loads('"' + match.group(1) + '"'))
    return context["gql_data"]["shortcode_media"]


parser = argparse.ArgumentParser()
parser.add_argument("ids", nargs="+")
parser.add_argument("--download", action="store_true")
parser.add_argument("--input-dir")
parser.add_argument("--prefix", default="d")
parser.add_argument("--output", default="d-public-post-metadata.json")
args = parser.parse_args()
workdir = Path(__file__).resolve().parent
input_dir = Path(args.input_dir) if args.input_dir else workdir
records = []
for shortcode in args.ids:
    embed = input_dir / f"{args.prefix}-instagram-{shortcode}-embed.html"
    post = parse_embed(embed)
    caption = "\n".join(x["node"]["text"] for x in post.get("edge_media_to_caption", {}).get("edges", []))
    caption_path = workdir / f"d-instagram-{shortcode}-caption.txt"
    caption_path.write_text(caption)
    owner = post.get("owner", {})
    timestamp = post.get("taken_at_timestamp")
    headers_path = input_dir / f"{args.prefix}-instagram-{shortcode}-embed.headers"
    date_headers = re.findall(r"^date:\s*(.+)$", headers_path.read_text() if headers_path.exists() else "", re.M | re.I)
    response_date = parsedate_to_datetime(date_headers[-1]).isoformat() if date_headers else None
    page_path = input_dir / f"{args.prefix}-instagram-{shortcode}.html"
    record = {
        "shortcode": shortcode,
        "source_url": f"https://www.instagram.com/{owner.get('username', '')}/reel/{shortcode}/",
        "parsed_at_utc": datetime.now(timezone.utc).isoformat(),
        "response_date_header_utc": response_date,
        "raw_embed_sha256": sha256(embed),
        "raw_page_sha256": sha256(page_path) if page_path.exists() else None,
        "media_id": post.get("id"),
        "media_id_derived_generation_time_utc": datetime.fromtimestamp(((int(post["id"]) >> 23) + 1314220021721) / 1000, timezone.utc).isoformat(),
        "derived_time_caveat": "Historical Instagram media-ID generation scheme; not an explicit publication timestamp or proof of present-day scheme invariance.",
        "derived_time_method_source": "https://media.postgresql.org/sfpug/instagram_sfpug.pdf pp. 131-136",
        "owner_id": owner.get("id"),
        "owner_username": owner.get("username"),
        "explicit_taken_at_timestamp": timestamp,
        "explicit_taken_at_utc": datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None,
        "duration_seconds_metadata": post.get("video_duration"),
        "view_count_metadata": post.get("video_view_count"),
        "likes_metadata": post.get("edge_liked_by", post.get("edge_media_preview_like", {})).get("count"),
        "comments_metadata": post.get("edge_media_to_comment", {}).get("count"),
        "caption": caption,
        "caption_sha256_utf8": hashlib.sha256(caption.encode()).hexdigest(),
        "caption_length_characters": len(caption),
        "relevant_public_flags": {k: post[k] for k in post if any(t in k.lower() for t in ("sponsor", "paid", "ad_", "product", "commercial", "affiliate")) and not isinstance(post[k], (dict, list))},
        "public_field_names": sorted(post.keys()),
        "signed_media_url_retained": False,
    }
    media_path = workdir / f"d-instagram-{shortcode}.mp4"
    if args.download:
        url = post.get("video_url")
        if not url:
            raise ValueError(f"No public video_url for {shortcode}")
        subprocess.run(["curl", "-L", "--max-time", "60", "-sS", "--fail", "-o", str(media_path), url], check=True)
    if not media_path.exists():
        media_path = input_dir / f"{args.prefix}-instagram-{shortcode}-video.mp4"
    if media_path.exists():
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(media_path)]))
        record["media_file"] = media_path.name
        record["media_sha256"] = sha256(media_path)
        record["media_probe"] = probe
    records.append(record)
    print(json.dumps({k: record[k] for k in ("shortcode", "owner_username", "media_id", "explicit_taken_at_utc", "duration_seconds_metadata", "view_count_metadata", "caption_sha256_utf8", "relevant_public_flags")}))
(workdir / args.output).write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")

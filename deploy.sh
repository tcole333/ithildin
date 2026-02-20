#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ -d "$ROOT/site/.git" ]; then
  echo "ERROR: Nested git repo detected at $ROOT/site/.git"
  echo ""
  echo "This repository uses root-only canonical paths:"
  echo "  - content/"
  echo "  - pipeline/"
  echo "  - web/"
  echo ""
  echo "The nested site/.git metadata is legacy local state and can block root-level workflows."
  echo "If you do not need local-only history from that nested repo, remove it with:"
  echo "  rm -rf \"$ROOT/site/.git\""
  exit 1
fi

echo "==> Running data pipeline..."
cd "$ROOT"
uv run python pipeline/build_all.py

echo "==> Building Astro site..."
cd "$ROOT/web"
npm run build

echo "==> Deploying to Cloudflare Pages..."
BRANCH="${1:-main}"
npx wrangler pages deploy dist/ --project-name=ithildin --branch="$BRANCH" --commit-dirty=true

echo "==> Done."

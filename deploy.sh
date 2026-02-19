#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

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

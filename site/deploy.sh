#!/usr/bin/env bash
set -euo pipefail

SITE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SITE_DIR/.." && pwd)"

echo "==> Running data pipeline..."
cd "$ROOT"
uv run python site/pipeline/build_all.py

echo "==> Building Astro site..."
cd "$SITE_DIR/web"
npm run build

echo "==> Deploying to Cloudflare Pages..."
BRANCH="${1:-main}"
npx wrangler pages deploy dist/ --project-name=ithildin --branch="$BRANCH" --commit-dirty=true

echo "==> Done."

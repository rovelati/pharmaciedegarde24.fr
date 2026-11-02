#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$ROOT_DIR/site"
CF_TOKEN_FILE="$ROOT_DIR/.cloudflare-token"

echo "================================================="
echo " Deploying PharmacieDeGarde24.fr to Cloudflare   "
echo "================================================="

if [ ! -f "$CF_TOKEN_FILE" ]; then
  echo "Error: $CF_TOKEN_FILE missing."
  exit 1
fi

ACCOUNT_ID="$(grep -i '^accountid:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
API_KEY="$(grep -i '^api-key:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
EMAIL="$(grep -i '^email:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
ZONE_ID="$(grep -i '^zoneid:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"

echo "1. Building Astro project..."
cd "$SITE_DIR"
npm run build

echo "2. Deploying to Cloudflare Pages..."
CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID" \
CLOUDFLARE_API_KEY="$API_KEY" \
CLOUDFLARE_EMAIL="$EMAIL" \
npx wrangler pages deploy dist --project-name=pharmaciedegarde24 --branch=main --commit-dirty=true

echo "3. Purging Cloudflare Zone cache..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/purge_cache" \
  -H "X-Auth-Email: ${EMAIL}" \
  -H "X-Auth-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}' | grep -q '"success":true' && echo "Cloudflare cache purged successfully." || echo "Cache purge finished."

echo "================================================="
echo " Deployment Complete!"
echo " Production URL: https://www.pharmaciedegarde24.fr/"
echo " Pages Subdomain: https://pharmaciedegarde24.pages.dev/"
echo "================================================="

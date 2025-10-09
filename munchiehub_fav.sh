#!/usr/bin/env bash
set -euo pipefail

# List starred repos with sizes (no cloning).
# Requires: curl, jq; uses numfmt if available.

: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

GITHUB_USERNAME="${GITHUB_USERNAME:-}"   # If set, use /users/:username/starred; else /user/starred
PER_PAGE="${PER_PAGE:-100}"              # Max 100
API_VERSION="${API_VERSION:-2022-11-28}"
API_BASE="https://api.github.com"
USER_AGENT="${USER_AGENT:-starred-size-script}"

if [[ -n "$GITHUB_USERNAME" ]]; then
  ENDPOINT="${API_BASE}/users/${GITHUB_USERNAME}/starred"
else
  ENDPOINT="${API_BASE}/user/starred"
fi

headers=(
  -H "Accept: application/vnd.github+json"
  -H "Authorization: Bearer ${GITHUB_TOKEN}"
  -H "X-GitHub-Api-Version: ${API_VERSION}"
  -H "User-Agent: ${USER_AGENT}"
)

tmp="$(mktemp)"
trap 'rm -f "$tmp" "$tmp.headers" "$tmp.body"' EXIT
> "$tmp"

page=1
while :; do
  # Capture status and body for better diagnostics
  http_code="$(curl -sS -D "$tmp.headers" -o "$tmp.body" -w "%{http_code}" "${headers[@]}" \
    "${ENDPOINT}?per_page=${PER_PAGE}&page=${page}")" || http_code="000"

  if [[ "$http_code" != "200" ]]; then
    echo "GitHub API error on page ${page} (HTTP ${http_code}):" >&2
    sed -n '1,200p' "$tmp.body" >&2
    echo "Response headers:" >&2
    sed -n '1,50p' "$tmp.headers" >&2
    exit 1
  fi

  count="$(jq 'length' < "$tmp.body")"
  [[ "$count" -eq 0 ]] && break

  # Repo size appears in the repository JSON object; GitHub’s APIs expose size in KB units
  # (see REST repo object ‘size’ and GraphQL ‘diskUsage’ semantics).
  jq -r '.[] | [.full_name, ((.size // 0) * 1024)] | @tsv' < "$tmp.body" >> "$tmp"

  page=$((page + 1))
done

if [[ ! -s "$tmp" ]]; then
  echo "No starred repositories found."
  exit 0
fi

if command -v numfmt >/dev/null 2>&1; then
  humanize() { numfmt --to=iec --suffix=B --format="%.1f" "$1"; }
else
  humanize() {
    awk -v b="$1" 'function f(x){split("B KiB MiB GiB TiB PiB EiB",u," ");
      i=1; while (x>=1024 && i<7){x/=1024;i++} printf("%.1f %s", x, u[i])}
      BEGIN{f(b)}'
  }
fi

# Sort by size descending and align columns
sort -nr -k2,2 "$tmp" | while IFS=$'\t' read -r name bytes; do
  hr="$(humanize "$bytes")"
  printf "%-60s %12s\n" "$name" "$hr"
done

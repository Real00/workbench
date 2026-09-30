#!/usr/bin/env bash
# Immutable archives first; publish the discovery manifests only after all uploads succeed.
set -euo pipefail
: "${GITHUB_SHA:?}" "${GITHUB_REPOSITORY:?}"
TAG="server-${GITHUB_SHA}"
if ! gh release view "$TAG" >/dev/null 2>&1; then
  gh release create "$TAG" --target "$GITHUB_SHA" --title "Server ${GITHUB_SHA:0:12}" \
    --notes '服务端离线更新包，由 CI 生成。' --prerelease --draft
fi
# Retries may replace draft assets. Published immutable releases are never overwritten.
DRAFT="$(gh release view "$TAG" --json isDraft --jq .isDraft)"
if [[ "$DRAFT" == true ]]; then
  gh release upload "$TAG" server-dist/* --clobber
  gh release edit "$TAG" --draft=false
fi
mkdir -p channel-manifests
# Use the actual published manifests on reruns, not a newly rebuilt archive's digest.
gh release download "$TAG" --pattern '*.json' --dir channel-manifests --clobber
if ! gh release view server-latest >/dev/null 2>&1; then
  gh release create server-latest --target "$GITHUB_SHA" --title 'Server latest' \
    --notes '已完成构建与检查的最新服务端版本。' --prerelease
fi
gh release upload server-latest channel-manifests/*.json --clobber

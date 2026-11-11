#!/usr/bin/env bash
set -Eeuo pipefail

: "${CI:?Must run inside GitLab CI}"
: "${STORY_ID:?Set STORY_ID to an Azure DevOps User Story ID}"
: "${AZURE_DEVOPS_ORGANIZATION:?Missing AZURE_DEVOPS_ORGANIZATION}"
: "${AZURE_DEVOPS_PROJECT:?Missing AZURE_DEVOPS_PROJECT}"
: "${AZURE_DEVOPS_PAT:?Missing AZURE_DEVOPS_PAT}"
: "${OPENAI_API_KEY:?Missing OPENAI_API_KEY}"
: "${OPENAI_MODEL:?Missing OPENAI_MODEL}"

case "$STORY_ID" in
  ''|*[!0-9]*) echo 'STORY_ID must be a positive integer' >&2; exit 2 ;;
esac
if [ "$STORY_ID" -eq 0 ]; then
  echo 'STORY_ID must be a positive integer' >&2
  exit 2
fi

# These files are transient job artifacts; never commit a .env containing secrets.
# The Playwright container image ships Node, browser binaries and browser dependencies.
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3 python3-venv ca-certificates >/dev/null
python3 -m venv /tmp/testforge-uv
/tmp/testforge-uv/bin/python -m pip install --quiet 'uv==0.13.7'
export PATH="/tmp/testforge-uv/bin:$PATH"

uv sync --frozen --no-dev --python python3
npm --prefix runner ci --no-audit --no-fund

# Browser already installed in mcr.microsoft.com/playwright:v1.64.1-noble.
# Do not use 'npx playwright install' unless changing that base image.
uv run --frozen --no-dev python -m backend.ci_workflow \
  --story-id "$STORY_ID" --unattended

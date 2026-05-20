#!/usr/bin/env bash
# install-on-runner.sh — install cc-review-runner via uv tool on a GitLab Runner host
set -euo pipefail

VERSION="${1:?usage: $0 <version> [pypi-index-url]}"
INDEX_URL="${2:-https://nexus.internal.example.com/repository/pypi/simple/}"
RUNNER_USER="${RUNNER_USER:-gitlab-runner}"

if ! command -v uv >/dev/null 2>&1; then
    echo "[install] uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "[install] installing cc-review-runner==${VERSION} for user ${RUNNER_USER}"
sudo -u "${RUNNER_USER}" -H bash -lc "
    uv tool install \
        --index-url '${INDEX_URL}' \
        --index-strategy unsafe-best-match \
        --force \
        'cc-review-runner==${VERSION}'
"

# Validate installation
SHIM=$(sudo -u "${RUNNER_USER}" -H bash -lc 'command -v cc-review-runner')
echo "[install] shim path: ${SHIM}"
"${SHIM}" --version

echo ""
echo "Use this absolute path in /etc/gitlab-runner/config.toml:"
echo "    ${SHIM}"

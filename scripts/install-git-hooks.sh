#!/usr/bin/env sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/ and run this script again." >&2
    exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/commit-msg .githooks/pre-commit scripts/install-git-hooks.sh 2>/dev/null || true
echo "Git hooks installed. Commit messages and Ruff checks are now enforced locally."
echo "Run 'uv sync' if dependencies are not installed yet."

#!/usr/bin/env bash
# One-click development environment setup.
# Usage: cd Train-Pet-Pipeline && bash pet-infra/scripts/setup_dev.sh
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PARENT_DIR="$(dirname "$INFRA_DIR")"
ORG="Train-Pet-Pipeline"
REPOS=(pet-schema pet-infra pet-data pet-annotation pet-train pet-eval pet-quantize pet-ota)

echo "=== Train-Pet-Pipeline Development Setup ==="
echo ""

echo "--- Checking prerequisites ---"
python3 --version | grep -q "3.1[1-9]" || { echo "ERROR: Python 3.11+ required"; exit 1; }
echo "  Python: OK"
git --version >/dev/null 2>&1 || { echo "ERROR: git required"; exit 1; }
echo "  git: OK"
docker compose version >/dev/null 2>&1 && echo "  docker compose: OK" || echo "  docker compose: not found (optional)"

echo ""
echo "--- Cloning repos ---"
for repo in "${REPOS[@]}"; do
    if [ -d "$PARENT_DIR/$repo" ]; then
        echo "  $repo: already exists"
    else
        echo "  Cloning $repo..."
        git clone "https://github.com/$ORG/$repo.git" "$PARENT_DIR/$repo"
    fi
done

echo ""
echo "--- Setting up repos ---"
for repo in "${REPOS[@]}"; do
    echo "  Setting up $repo..."
    (cd "$PARENT_DIR/$repo" && make setup 2>&1 | tail -1) || echo "  WARNING: $repo setup had issues"
done

echo ""
echo "--- Environment configuration ---"
if [ ! -f "$PARENT_DIR/.env" ]; then
    cp "$INFRA_DIR/shared/.env.example" "$PARENT_DIR/.env"
    echo "  Created .env from template. Please edit with your actual values."
else
    echo "  .env already exists."
fi

echo ""
echo "--- Verification ---"
PASS=0
FAIL=0
for repo in "${REPOS[@]}"; do
    if (cd "$PARENT_DIR/$repo" && make lint >/dev/null 2>&1 && make test >/dev/null 2>&1); then
        echo "  $repo: PASS"
        PASS=$((PASS + 1))
    else
        echo "  $repo: FAIL"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=== Setup complete: $PASS passed, $FAIL failed ==="

#!/usr/bin/env bash
# Cross-repo dependency version checker.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PARENT_DIR="$(dirname "$INFRA_DIR")"

echo "=== Train-Pet-Pipeline Dependency Report ==="
echo ""
printf "%-16s %-14s %-14s %-14s %-14s\n" "REPO" "pet-schema" "latest-schema" "pet-infra" "latest-infra"
printf "%-16s %-14s %-14s %-14s %-14s\n" "----" "----------" "-------------" "---------" "------------"

SCHEMA_TAG=$(git -C "$PARENT_DIR/pet-schema" describe --tags --abbrev=0 2>/dev/null || echo "none")
INFRA_TAG=$(git -C "$PARENT_DIR/pet-infra" describe --tags --abbrev=0 2>/dev/null || echo "none")

for repo_dir in "$PARENT_DIR"/pet-*/; do
    repo_name=$(basename "$repo_dir")
    [ "$repo_name" = "pet-infra" ] && continue
    [ "$repo_name" = "pet-schema" ] && continue
    [ ! -f "$repo_dir/pyproject.toml" ] && continue

    schema_ver=$(python3 -c "
import re
with open('${repo_dir}pyproject.toml') as f:
    c = f.read()
m = re.search(r'pet.schema[^\"]*?([0-9]+\.[0-9]+\.[0-9]+)', c)
print(m.group(1) if m else 'n/a')
" 2>/dev/null || echo "n/a")

    infra_ver=$(python3 -c "
import re
with open('${repo_dir}pyproject.toml') as f:
    c = f.read()
m = re.search(r'pet.infra[^\"]*?([0-9]+\.[0-9]+\.[0-9]+)', c)
print(m.group(1) if m else 'n/a')
" 2>/dev/null || echo "n/a")

    printf "%-16s %-14s %-14s %-14s %-14s\n" "$repo_name" "$schema_ver" "$SCHEMA_TAG" "$infra_ver" "$INFRA_TAG"
done

echo ""
echo "=== Done ==="

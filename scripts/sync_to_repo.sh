#!/usr/bin/env bash
# Sync shared config from pet-infra to the current repo.
# Merges [tool.ruff] and [tool.mypy] base keys from pyproject-base.toml
# into the repo's pyproject.toml, preserving per-file-ignores and extend-select.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASE_TOML="$INFRA_DIR/shared/pyproject-base.toml"
REPO_TOML="$(pwd)/pyproject.toml"

echo "=== sync-infra: merging ruff/mypy config ==="

if [ ! -f "$REPO_TOML" ]; then
    echo "ERROR: No pyproject.toml found in $(pwd)" >&2
    exit 1
fi

# Use Python inline for TOML manipulation (tomli/tomllib + tomli_w)
python3 - "$BASE_TOML" "$REPO_TOML" <<'PYEOF'
import sys

# Try tomllib (Python 3.11+) then fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        print("ERROR: tomllib/tomli not available. Install tomli: pip install tomli", file=sys.stderr)
        sys.exit(1)

try:
    import tomli_w
except ImportError:
    print("ERROR: tomli_w not available. Install: pip install tomli_w", file=sys.stderr)
    sys.exit(1)

base_path, repo_path = sys.argv[1], sys.argv[2]

with open(base_path, "rb") as f:
    base = tomllib.load(f)

with open(repo_path, "rb") as f:
    repo = tomllib.load(f)

# Preserve per-file-ignores and extend-select from repo's ruff.lint section
preserved_lint_keys = {"per-file-ignores", "extend-select"}
repo_lint = repo.get("tool", {}).get("ruff", {}).get("lint", {})
preserved = {k: v for k, v in repo_lint.items() if k in preserved_lint_keys}

# Merge: overwrite base keys in [tool.ruff] and [tool.mypy]
repo.setdefault("tool", {})
repo["tool"]["ruff"] = base["tool"]["ruff"].copy()
repo["tool"]["ruff"]["lint"] = base["tool"]["ruff"]["lint"].copy()
repo["tool"]["ruff"]["lint"].update(preserved)
repo["tool"]["mypy"] = base["tool"]["mypy"].copy()

with open(repo_path, "wb") as f:
    tomli_w.dump(repo, f)

print("  Merged [tool.ruff] and [tool.mypy] into", repo_path)
PYEOF

echo ""
echo "=== Checking dependency versions ==="

# Check pet-schema and pet-infra dependency versions against latest git tags
PARENT_DIR="$(dirname "$INFRA_DIR")"

SCHEMA_TAG=$(git -C "$PARENT_DIR/pet-schema" describe --tags --abbrev=0 2>/dev/null || echo "none")
INFRA_TAG=$(git -C "$INFRA_DIR" describe --tags --abbrev=0 2>/dev/null || echo "none")

python3 - "$REPO_TOML" "$SCHEMA_TAG" "$INFRA_TAG" <<'PYEOF'
import sys, re

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

repo_path, schema_tag, infra_tag = sys.argv[1], sys.argv[2], sys.argv[3]

with open(repo_path, "rb") as f:
    repo = tomllib.load(f)

content = open(repo_path).read()

schema_m = re.search(r'pet[_-]schema[^"\']*?([0-9]+\.[0-9]+\.[0-9]+)', content)
infra_m = re.search(r'pet[_-]infra[^"\']*?([0-9]+\.[0-9]+\.[0-9]+)', content)

schema_ver = schema_m.group(1) if schema_m else "n/a"
infra_ver = infra_m.group(1) if infra_m else "n/a"

print(f"  pet-schema pinned: {schema_ver}  (latest tag: {schema_tag})")
print(f"  pet-infra  pinned: {infra_ver}  (latest tag: {infra_tag})")

if schema_ver != "n/a" and schema_tag != "none" and not schema_tag.endswith(schema_ver):
    print(f"  WARNING: pet-schema may be outdated ({schema_ver} vs {schema_tag})")
if infra_ver != "n/a" and infra_tag != "none" and not infra_tag.endswith(infra_ver):
    print(f"  WARNING: pet-infra may be outdated ({infra_ver} vs {infra_tag})")
PYEOF

echo ""
echo "=== Git diff (pyproject.toml) ==="
git diff -- pyproject.toml || true

echo ""
echo "=== sync-infra complete ==="

#!/usr/bin/env bash
# Unified lint script for all pet-pipeline repos.
set -euo pipefail

echo "=== ruff check ==="
ruff check src/ tests/

echo "=== mypy ==="
mypy src/

echo "=== All checks passed ==="

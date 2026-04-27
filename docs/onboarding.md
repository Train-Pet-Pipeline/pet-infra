# Onboarding Guide

## Prerequisites

- Python 3.11.x (use conda env `pet-pipeline`)
- git
- make
- docker compose (optional, for Label Studio local)

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Train-Pet-Pipeline/pet-infra.git
cd pet-infra

# 2. Run setup (creates conda env, installs deps, copies .env template)
bash scripts/setup_dev.sh

# 3. Configure secrets
cp .env.example .env
# Edit .env — set CLEARML_API_HOST/ACCESS_KEY/SECRET_KEY, LABEL_STUDIO_TOKEN, DB_URL, etc.

# 4. Verify
conda run -n pet-pipeline make test
```

Expected output: all tests green, no lint errors.

## Repository Overview

| Repo | Purpose |
|---|---|
| `pet-schema` | Schema and prompt definitions — upstream contract for all repos |
| `pet-data` | Data collection, cleaning, augmentation, weak supervision |
| `pet-annotation` | VLM labeling, QA, human review, DPO pair generation |
| `pet-train` | SFT + DPO training (LLaMA-Factory), audio CNN training |
| `pet-eval` | Evaluation pipeline (called by pet-train and pet-quantize) |
| `pet-quantize` | Quantization, on-device conversion, artifact packaging and signing |
| `pet-ota` | Differential updates, canary rollout, rollback |
| `pet-infra` | Docker, CI templates, shared Python utilities (this repo) |

## Key Concepts

### params.yaml

Every numeric constant lives in `params.yaml` in its repo. Never hardcode values in source.
Read them with:

```python
import yaml
with open("params.yaml") as f:
    params = yaml.safe_load(f)
threshold = params["annotation"]["confidence_threshold"]
```

### pet-schema contract

`pet-schema` is the single source of truth for all data schemas and prompt templates.
Install it pinned to a version tag — never `@main`:

```bash
pip install "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema.git@v1.0.0"
```

A push to `pet-schema` main triggers `repository_dispatch` to all downstream repos via the Schema Guard workflow (`ci/workflows/schema_guard.yml`).

### store.py

All database access goes through `pet_infra.store`. Never connect directly:

```python
from pet_infra.store import Store
store = Store(db_url=os.environ["DB_URL"])
records = store.get_pending(limit=100)
```

### pet_infra shared utilities

Import from `pet_infra` in any repo:

```python
from pet_infra.logging import get_logger          # structured JSON logger
from pet_infra.retry import retry_with_backoff    # tenacity wrapper
from pet_infra.device import get_device_info      # RK3576 / CUDA detection
from pet_infra.api_client import APIClient        # HTTP client with retry
```

Shared lint and mypy configs live in `pet-infra/shared/`. The `sync_to_repo.sh` script copies them to target repos.

## Further Reading

- `docs/DEVELOPMENT_GUIDE.md` — authoritative spec: branching, commit format, cross-repo deps, CI rules
  - **§11.8** — "Plugin-contract test 纪律：fixture-real 而非 mock-only" (F008-F027 retro guardrail, added 2026-04-27). Every PR that modifies a plugin contract must include a fixture-real test checkbox in the PR description.
- `docs/runbook.md` — common failure modes and emergency procedures

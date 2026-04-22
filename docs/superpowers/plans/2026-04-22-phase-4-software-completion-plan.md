# Phase 4 Software-Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the software loop of the Train-Pet-Pipeline by shipping OTA S3/HTTP backend plugins, rule-based cross-modal fusion evaluators, multi-axis recipe variations launcher, deterministic `pet run --replay`, complete W&B physical removal, BSL 1.1 license adoption, and matrix 2026.09 freeze — all in a hardware-free environment.

**Architecture:** 7 workstreams (W1 OTA backends / W2 fusion plugins / W3 variations launcher / W4 replay determinism / W5 W&B removal / W6 matrix-2026.09 freeze / W7 BSL 1.1) shipped through 38 PRs across 7 sub-phases (P0 / P1 / P2-A / P2-B / P2-C / P5-A / W7 / P6). Subagent-driven-development with auto-merge + Phase-level checkpoint + `gh pr merge --auto --squash`. Every PR follows TDD; every plugin uses mmengine.Registry contract; every cross-repo bump preserves the 4-step (or 6-step where applicable) peer-dep CI install order.

**Tech Stack:** Python 3.11.x · Pydantic v2 · mmengine.Registry · Hydra defaults-list + multirun · ProcessPoolExecutor · LocalStack (S3) + http.server (HTTP) for backend tests · click CLI · ClearML · DVC · ruff + mypy + pytest · BSL 1.1 license.

**Hard constraints (per project memory):**
- `feedback_refactor_no_legacy`: BREAKING bumps; do **not** keep compat shims.
- `feedback_pr_workflow`: every PR is `feature/* → dev → main` (final tag PRs are `dev → main`).
- `feedback_env_naming`: shared `pet-pipeline` conda env.
- `feedback_no_hardcode`: every numeric from `params.yaml` / config.
- `feedback_no_manual_workaround`: fix root cause, never bypass.
- `feedback_no_learned_fusion`: cross_modal fusion is rule-based only.
- `project_phase4_scope`: software loop only — hardware paths stay dry-run.
- `project_license_bsl`: BSL 1.1 with Change Date 2030-04-22 → Apache 2.0.

---

## Global PR Dependency Graph

```
P0-A (pet-schema 2.4.0-rc1: ModelCard.resolved_config_uri)
  │
  └──► P1-A..P1-G (pet-infra 2.5.0-rc1: storage S3+HTTP, launcher dump, variations,
                                          replay CLI, W&B removal, release)
            │
            ├──► P2-A-1..P2-A-5 (pet-ota 2.1.0-rc1: S3+HTTP backends, register, release)
            │
            └──► P2-B-1..P2-B-5 (pet-eval 2.2.0-rc1: 3 fusion evaluators, recipe, W&B clean, release)
                          │
                          ├──► P2-C-1 (pet-train W&B clean + pyproject drift fix → 2.0.1-rc1)
                          └──► P2-C-2 (pet-quantize W&B clean → 2.0.1-rc1)

P5-A-0 (matrix 2026.09 + DEVELOPMENT_GUIDE 同步)
  │
  └──► P5-A-1..P5-A-6 (per-repo final tag: schema 2.4.0, infra 2.5.0, ota 2.1.0,
                        eval 2.2.0, train 2.0.1, quantize 2.0.1)

W7-1..W7-10  (BSL 1.1 LICENSE per repo — runs in parallel with P5-A,
              independent of all functional PRs)

P6-A         (Phase 4 retrospective + DoD self-check — last PR)
```

**Branch naming convention:** `feature/phase-4-<short-tag>` for `feature/* → dev` PRs;
`release/<repo>-<version>` for the `dev → main` tag PRs.

**Auto-merge:** every PR uses `gh pr merge --auto --squash` after CI green; reviews are self/Claude.

---

## Cross-PR Preflight (run once before P0-A)

- [ ] **Step 1: Verify clean working state in all 10 repos**

```bash
for repo in pet-schema pet-data pet-annotation pet-train pet-eval \
            pet-quantize pet-ota pet-infra pet-id pet-demo; do
  echo "=== $repo ==="
  (cd /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo && git status --short && \
   git fetch origin && git checkout dev && git pull --ff-only)
done
```
Expected: all repos on `dev`, clean, up-to-date.

- [ ] **Step 2: Verify pet-pipeline conda env active**

Run: `conda env list | grep -E '\* pet-pipeline'`
Expected: pet-pipeline marked active. If not: `conda activate pet-pipeline`.

- [ ] **Step 3: Verify pyproject baselines (snapshot for drift detection)**

```bash
for repo in pet-schema pet-infra pet-data pet-annotation pet-train \
            pet-eval pet-quantize pet-ota pet-id; do
  v=$(grep -E '^version = ' /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo/pyproject.toml | head -1)
  echo "$repo: $v"
done
```
Expected snapshot:
- pet-schema: 2.3.1
- pet-infra: 2.4.0
- pet-data: 1.2.0
- pet-annotation: 2.0.0
- pet-train: **0.1.0** (drift — git tag is v2.0.0-rc1; fixed in P2-C-1 → 2.0.1-rc1)
- pet-eval: 2.1.0
- pet-quantize: 2.0.0
- pet-ota: 2.0.0
- pet-id: 0.1.0

If any value differs, STOP and surface to user — version drift breaks peer-dep order.

- [ ] **Step 4: Verify all 10 repos have NO LICENSE file (W7 starting state)**

```bash
for repo in pet-schema pet-data pet-annotation pet-train pet-eval \
            pet-quantize pet-ota pet-infra pet-id pet-demo; do
  if [ -f /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo/LICENSE ]; then
    echo "FOUND $repo/LICENSE"
  fi
done
```
Expected: empty output.

---

## Phase 0 — pet-schema 2.4.0-rc1 (1 PR)

Adds `ModelCard.resolved_config_uri: str | None = None` so launcher can record the per-variation resolved Hydra config (replay Tier 2). All consumers ignore the field until they upgrade in P1+.

### PR P0-A: pet-schema add `ModelCard.resolved_config_uri`

**Branch:** `feature/phase-4-resolved-config-uri` → `dev`
**Repo:** `pet-schema`
**Files:**
- Modify: `src/pet_schema/model_card.py:90-118` (add field after `dvc_exp_sha`)
- Modify: `pyproject.toml` (version 2.3.1 → 2.4.0-rc1)
- Modify: `CHANGELOG.md` (add 2.4.0-rc1 section)
- Test: `tests/test_model_card.py` (add `test_resolved_config_uri_default_none` and `test_resolved_config_uri_round_trip`)

- [ ] **Step 1: Branch from dev**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-resolved-config-uri
```

- [ ] **Step 2: Write failing test for default None**

Add to `tests/test_model_card.py`:

```python
def test_resolved_config_uri_default_none():
    card = ModelCard(
        id="m1", version="0.1.0", modality="vlm", task="caption",
        arch="qwen2-vl-2b", training_recipe="sft", hydra_config_sha="abc",
        git_shas={}, dataset_versions={}, checkpoint_uri="s3://x/ckpt",
        metrics={}, gate_status="pending",
        trained_at="2026-04-22T00:00:00Z", trained_by="ci",
    )
    assert card.resolved_config_uri is None


def test_resolved_config_uri_round_trip():
    card = ModelCard(
        id="m1", version="0.1.0", modality="vlm", task="caption",
        arch="qwen2-vl-2b", training_recipe="sft", hydra_config_sha="abc",
        git_shas={}, dataset_versions={}, checkpoint_uri="s3://x/ckpt",
        metrics={}, gate_status="pending",
        trained_at="2026-04-22T00:00:00Z", trained_by="ci",
        resolved_config_uri="s3://artifacts/runs/abc/resolved_config.yaml",
    )
    dumped = card.model_dump_json()
    restored = ModelCard.model_validate_json(dumped)
    assert restored.resolved_config_uri == "s3://artifacts/runs/abc/resolved_config.yaml"
```

- [ ] **Step 3: Run test — verify FAIL**

Run: `pytest tests/test_model_card.py::test_resolved_config_uri_default_none -xvs`
Expected: AttributeError or extra-field-forbidden error.

- [ ] **Step 4: Add field to ModelCard**

Edit `src/pet_schema/model_card.py` — insert after `dvc_exp_sha: str | None = None`:

```python
    resolved_config_uri: str | None = None
```

- [ ] **Step 5: Run tests — verify PASS**

Run: `pytest tests/test_model_card.py -xvs`
Expected: all tests pass including the two new ones.

- [ ] **Step 6: Bump pyproject + CHANGELOG**

Edit `pyproject.toml`: `version = "2.3.1"` → `version = "2.4.0-rc1"`.

Edit `CHANGELOG.md` — prepend:

```markdown
## 2.4.0-rc1 — 2026-04-22

### Added
- `ModelCard.resolved_config_uri: str | None = None` — URI of the per-run resolved
  Hydra config dump, enabling deterministic `pet run --replay <card-id>` (Phase 4 W4).
```

- [ ] **Step 7: Lint + full test**

```bash
ruff check src/ tests/
mypy src/
pytest -x
```
Expected: all green.

- [ ] **Step 8: Commit + push + PR**

```bash
git add src/pet_schema/model_card.py tests/test_model_card.py pyproject.toml CHANGELOG.md
git commit -m "feat(pet-schema): add ModelCard.resolved_config_uri for Phase 4 replay (#P0-A)"
git push -u origin feature/phase-4-resolved-config-uri
gh pr create --base dev --title "feat(pet-schema): add ModelCard.resolved_config_uri (P0-A)" \
  --body "Adds nullable resolved_config_uri so pet-infra launcher can record per-variation resolved Hydra config. Phase 4 P0-A. Bumps to 2.4.0-rc1."
gh pr merge --auto --squash
```

- [ ] **Step 9: Wait for merge + tag rc1 on dev**

```bash
gh pr view --json state --jq .state   # poll until MERGED
git checkout dev && git pull --ff-only
git tag v2.4.0-rc1 && git push origin v2.4.0-rc1
```
Final tag `v2.4.0` is cut in P5-A-1 after all consumers upgrade.

---

## Phase 1 — pet-infra 2.5.0-rc1 (7 PRs)

W1 (storage backends) + W3 (variations launcher) + W4 (replay CLI) + W5 (W&B physical removal in pet-infra) all land here. Order matters: P1-A and P1-B are independent and can run in parallel; P1-C depends on P0-A; P1-D depends on P1-C; P1-E depends on P1-D; P1-F is independent. P1-G is the rc1 tag.

### PR P1-A: pet-infra add `S3Storage` plugin (LocalStack-tested)

**Branch:** `feature/phase-4-storage-s3` → `dev`
**Repo:** `pet-infra`
**Files:**
- Create: `src/pet_infra/storage/s3.py`
- Modify: `src/pet_infra/storage/__init__.py` (re-export `S3Storage`)
- Modify: `src/pet_infra/_register.py` (register `s3` storage)
- Create: `tests/storage/test_s3.py`
- Create: `tests/storage/conftest.py` (LocalStack fixture if not yet present)
- Modify: `pyproject.toml` (add `boto3>=1.34`, `moto[s3]>=5.0` test extra)
- Modify: `Makefile` (add `localstack-up` / `localstack-down` targets)

- [ ] **Step 1: Branch + write failing tests**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-storage-s3
```

Create `tests/storage/test_s3.py`:

```python
import pytest
from pet_infra.storage.s3 import S3Storage


def test_s3_scheme_attr():
    assert S3Storage.scheme == "s3"


def test_s3_round_trip(s3_bucket):
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    uri = f"s3://{s3_bucket['bucket']}/runs/abc/manifest.json"
    payload = b'{"version":"0.1.0"}'
    storage.write(uri, payload)
    assert storage.exists(uri)
    assert storage.read(uri) == payload


def test_s3_iter_prefix(s3_bucket):
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    base = f"s3://{s3_bucket['bucket']}/runs/v1"
    for name in ("a.bin", "b.bin", "sub/c.bin"):
        storage.write(f"{base}/{name}", b"x")
    keys = sorted(storage.iter_prefix(base))
    assert keys == [f"{base}/a.bin", f"{base}/b.bin", f"{base}/sub/c.bin"]


def test_s3_rejects_wrong_scheme(s3_bucket):
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    with pytest.raises(ValueError, match="scheme"):
        storage.read("file:///tmp/x")
```

Create/extend `tests/storage/conftest.py` with a `moto`-backed `s3_bucket` fixture (no real AWS):

```python
import pytest
import boto3
from moto import mock_aws


@pytest.fixture
def s3_bucket():
    with mock_aws():
        endpoint_url = None  # moto patches boto3 transparently
        client = boto3.client("s3", region_name="us-east-1")
        bucket = "pet-infra-test"
        client.create_bucket(Bucket=bucket)
        yield {"bucket": bucket, "endpoint_url": endpoint_url}
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `pytest tests/storage/test_s3.py -xvs`
Expected: ImportError on `pet_infra.storage.s3`.

- [ ] **Step 3: Implement `S3Storage`**

Create `src/pet_infra/storage/s3.py`:

```python
"""S3-backed storage plugin (compatible with LocalStack / moto / real AWS)."""

from __future__ import annotations

from typing import ClassVar, Iterator
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from pet_infra.base.storage import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="s3", force=True)
class S3Storage(BaseStorage):
    scheme: ClassVar[str] = "s3"

    def __init__(self, endpoint_url: str | None = None, region_name: str = "us-east-1", **_: object):
        self._client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region_name)

    def _split(self, uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != self.scheme:
            raise ValueError(f"S3Storage requires scheme=s3, got {parsed.scheme!r} in {uri!r}")
        return parsed.netloc, parsed.path.lstrip("/")

    def read(self, uri: str) -> bytes:
        bucket, key = self._split(uri)
        return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def write(self, uri: str, data: bytes) -> None:
        bucket, key = self._split(uri)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def exists(self, uri: str) -> bool:
        bucket, key = self._split(uri)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def iter_prefix(self, prefix_uri: str) -> Iterator[str]:
        bucket, prefix = self._split(prefix_uri.rstrip("/") + "/")
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield f"s3://{bucket}/{item['Key']}"
```

- [ ] **Step 4: Wire into `_register.py` + `storage/__init__.py`**

In `src/pet_infra/storage/__init__.py` add:

```python
from .s3 import S3Storage  # noqa: F401
```

In `src/pet_infra/_register.py` ensure import side-effect runs (e.g. `from pet_infra.storage import s3 as _s3  # noqa: F401`).

- [ ] **Step 5: Add deps**

In `pyproject.toml`:
- main deps: add `"boto3>=1.34"`.
- `[project.optional-dependencies] test`: add `"moto[s3]>=5.0"`.
Run: `pip install -e ".[test]"`.

- [ ] **Step 6: Run tests — verify PASS**

Run: `pytest tests/storage/test_s3.py -xvs`
Expected: 4 tests pass.

- [ ] **Step 7: Lint + commit + PR**

```bash
ruff check src/ tests/ && mypy src/ && pytest -x
git add -A
git commit -m "feat(pet-infra): S3Storage plugin (P1-A)"
git push -u origin feature/phase-4-storage-s3
gh pr create --base dev --title "feat(pet-infra): S3Storage plugin (P1-A)" \
  --body "Adds S3Storage backed by boto3, tested with moto. Implements BaseStorage. Phase 4 W1."
gh pr merge --auto --squash
```

### PR P1-B: pet-infra add `HttpStorage` plugin

**Branch:** `feature/phase-4-storage-http` → `dev`
**Repo:** `pet-infra`
**Files:**
- Create: `src/pet_infra/storage/http.py`
- Modify: `src/pet_infra/storage/__init__.py`
- Modify: `src/pet_infra/_register.py`
- Create: `tests/storage/test_http.py` (uses Python `http.server` fixture)

- [ ] **Step 1: Branch + write failing tests**

Branch from dev. Create `tests/storage/test_http.py`:

```python
import http.server
import socketserver
import threading
import pytest
from pathlib import Path

from pet_infra.storage.http import HttpStorage


@pytest.fixture
def http_server(tmp_path):
    serve_dir = tmp_path / "www"
    serve_dir.mkdir()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(serve_dir), **kw)

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield {"base_url": f"http://127.0.0.1:{port}", "serve_dir": serve_dir}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_scheme(http_server):
    assert HttpStorage.scheme == "http"


def test_http_read_existing(http_server):
    (http_server["serve_dir"] / "manifest.json").write_bytes(b'{"v":"1"}')
    storage = HttpStorage()
    assert storage.read(f"{http_server['base_url']}/manifest.json") == b'{"v":"1"}'


def test_http_exists_404(http_server):
    storage = HttpStorage()
    assert storage.exists(f"{http_server['base_url']}/missing") is False


def test_http_write_raises_readonly(http_server):
    storage = HttpStorage()
    with pytest.raises(NotImplementedError, match="read-only"):
        storage.write(f"{http_server['base_url']}/x", b"x")
```

- [ ] **Step 2: Run tests — verify FAIL** (ImportError).

- [ ] **Step 3: Implement `HttpStorage`**

Create `src/pet_infra/storage/http.py`:

```python
"""HTTP(S) read-only storage plugin (CDN / static-file server compatible)."""

from __future__ import annotations

from typing import ClassVar, Iterator
from urllib.parse import urlparse

import requests

from pet_infra.base.storage import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="http", force=True)
class HttpStorage(BaseStorage):
    scheme: ClassVar[str] = "http"

    def __init__(
        self,
        timeout_s: float = 30.0,
        auth_token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        **_: object,
    ):
        self._timeout = timeout_s
        self._headers: dict[str, str] = {}
        self._auth = basic_auth
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

    def _check(self, uri: str) -> None:
        scheme = urlparse(uri).scheme
        if scheme not in {"http", "https"}:
            raise ValueError(f"HttpStorage requires http/https, got {scheme!r}")

    def read(self, uri: str) -> bytes:
        self._check(uri)
        r = requests.get(uri, timeout=self._timeout, headers=self._headers, auth=self._auth)
        r.raise_for_status()
        return r.content

    def write(self, uri: str, data: bytes) -> None:
        raise NotImplementedError("HttpStorage is read-only; use S3Storage for uploads.")

    def exists(self, uri: str) -> bool:
        self._check(uri)
        r = requests.head(uri, timeout=self._timeout, headers=self._headers, auth=self._auth)
        return r.status_code == 200

    def iter_prefix(self, prefix_uri: str) -> Iterator[str]:
        raise NotImplementedError("HttpStorage cannot list; use S3Storage for prefix iteration.")
```

- [ ] **Step 4: Wire register/import. Add `requests` to pyproject if not present.**

- [ ] **Step 5: Run tests — verify PASS** (4 tests).

- [ ] **Step 6: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-infra): HttpStorage read-only plugin (P1-B)"
git push -u origin feature/phase-4-storage-http
gh pr create --base dev --title "feat(pet-infra): HttpStorage plugin (P1-B)" \
  --body "Adds HttpStorage (read-only) for CDN / static-file artifact distribution. Phase 4 W1."
gh pr merge --auto --squash
```

### PR P1-C: pet-infra launcher dumps resolved Hydra config & writes `resolved_config_uri`

**Branch:** `feature/phase-4-launcher-resolved-config` → `dev`
**Repo:** `pet-infra` (depends on P0-A merged + pet-schema 2.4.0-rc1 tag)
**Files:**
- Modify: `src/pet_infra/launcher.py:_run_single` + `launch_multirun`
- Modify: `pyproject.toml` (bump `pet-schema` peer-dep to `>=2.4.0-rc1,<3`)
- Create: `tests/launcher/test_resolved_config.py`

- [ ] **Step 1: Branch + bump peer-dep**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-launcher-resolved-config
```

In `pyproject.toml` change `"pet-schema>=2.3.1,<3"` → `"pet-schema>=2.4.0-rc1,<3"`.

- [ ] **Step 2: Write failing test**

Create `tests/launcher/test_resolved_config.py`:

```python
import json
from pathlib import Path

from pet_infra.launcher import launch_multirun


def test_resolved_config_dumped_per_variation(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    output = tmp_path / "runs"
    summary = launch_multirun(
        recipe_path="tests/fixtures/recipe_minimal.yaml",
        overrides=["+ablation.lr=[1e-4,1e-3]"],
        output_dir=output,
    )
    assert len(summary["variations"]) == 2
    for v in summary["variations"]:
        cfg_path = Path(v["resolved_config_uri"].removeprefix("file://"))
        assert cfg_path.exists()
        cfg = cfg_path.read_text()
        assert "lr:" in cfg
```

- [ ] **Step 3: Run test — verify FAIL**.

- [ ] **Step 4: Implement dump in `_run_single`**

In `src/pet_infra/launcher.py` `_run_single`:
1. After Hydra composes `cfg`, write `OmegaConf.to_yaml(cfg, resolve=True)` to `<run_dir>/resolved_config.yaml`.
2. Set `result["resolved_config_uri"] = f"file://{abs_path}"` (or storage URI if `--storage s3` passed).
3. Propagate into `sweep_summary.json`.

- [ ] **Step 5: Run tests — verify PASS**.

- [ ] **Step 6: Commit + PR + merge**

```bash
git add -A
git commit -m "feat(pet-infra): launcher dumps resolved Hydra config per variation (P1-C)"
git push -u origin feature/phase-4-launcher-resolved-config
gh pr create --base dev --title "feat(pet-infra): launcher dumps resolved_config_uri (P1-C)" \
  --body "Each variation now writes resolved_config.yaml and exposes file/s3 URI in sweep_summary.json. Bumps pet-schema peer-dep to >=2.4.0-rc1. Phase 4 W4."
gh pr merge --auto --squash
```

### PR P1-D: pet-infra `ExperimentRecipe.variations` consumption + cartesian preflight + ClearML tags

**Branch:** `feature/phase-4-variations-launcher` → `dev`
**Repo:** `pet-infra` (depends on P1-C merged)
**Files:**
- Modify: `src/pet_infra/launcher.py:launch_multirun` (cartesian product over `recipe.variations`, `link_to` co-iteration, ClearML per-variation tag injection)
- Modify: `src/pet_infra/cli.py:_check_multirun_launcher` (call new `_check_cartesian_size`)
- Create: `src/pet_infra/sweep_preflight.py` (cartesian sizing + warn/fail + `PET_ALLOW_LARGE_SWEEP=1` override)
- Create: `tests/launcher/test_variations.py`
- Create: `tests/launcher/test_preflight.py`

- [ ] **Step 1: Branch + write failing tests**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-variations-launcher
```

Create `tests/launcher/test_variations.py`:

```python
import os
import pytest
from pet_infra.launcher import launch_multirun


def test_variations_cartesian(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    summary = launch_multirun(
        recipe_path="tests/fixtures/recipe_with_variations.yaml",  # 2 axes × 2 = 4
        output_dir=tmp_path,
    )
    assert len(summary["variations"]) == 4


def test_variations_link_to_co_iteration(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    summary = launch_multirun(
        recipe_path="tests/fixtures/recipe_with_link_to.yaml",  # axis B link_to=A; A has 3 values
        output_dir=tmp_path,
    )
    assert len(summary["variations"]) == 3  # NOT 9


def test_clearml_tag_injected(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    monkeypatch.setenv("PET_FORCE_CLEARML_OFFLINE", "1")
    summary = launch_multirun(
        recipe_path="tests/fixtures/recipe_with_variations.yaml",
        output_dir=tmp_path,
    )
    for v in summary["variations"]:
        assert any(t.startswith("variation:") for t in v["clearml_tags"])
```

Create `tests/launcher/test_preflight.py`:

```python
import pytest
from pet_infra.sweep_preflight import check_cartesian_size, CartesianTooLargeError


def test_under_16_silent():
    check_cartesian_size(8)  # no raise, no log


def test_over_16_warns(caplog):
    check_cartesian_size(20)
    assert any("WARN" in r.message or "warn" in r.message.lower() for r in caplog.records)


def test_over_64_fails():
    with pytest.raises(CartesianTooLargeError):
        check_cartesian_size(100)


def test_over_64_override(monkeypatch):
    monkeypatch.setenv("PET_ALLOW_LARGE_SWEEP", "1")
    check_cartesian_size(100)  # no raise
```

- [ ] **Step 2: Run tests — verify FAIL**.

- [ ] **Step 3: Implement `sweep_preflight.py`**

```python
"""Cartesian sweep size preflight per spec §1.3 / §3.3."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

WARN_THRESHOLD = 16
FAIL_THRESHOLD = 64
OVERRIDE_ENV = "PET_ALLOW_LARGE_SWEEP"


class CartesianTooLargeError(RuntimeError):
    pass


def check_cartesian_size(n: int) -> None:
    if n > FAIL_THRESHOLD and os.environ.get(OVERRIDE_ENV) != "1":
        raise CartesianTooLargeError(
            f"Sweep size {n} exceeds fail threshold {FAIL_THRESHOLD}; "
            f"set {OVERRIDE_ENV}=1 to override."
        )
    if n > WARN_THRESHOLD:
        logger.warning("Sweep size %d exceeds warn threshold %d.", n, WARN_THRESHOLD)
```

- [ ] **Step 4: Implement variations consumption in `launcher.py`**

Modify `launch_multirun`:
1. Load `ExperimentRecipe` from `recipe_path`.
2. Build cartesian product over `recipe.variations`, honoring `link_to` (co-iterated axes share a single index).
3. Compute total `n` and call `check_cartesian_size(n)` before scheduling.
4. For each variation, derive `variation_id = sha1(json.dumps(axis_values))[:8]` and inject ClearML tag `f"variation:{variation_id}"` (read existing tag list from `recipe.clearml_tags`, append).
5. Pass per-variation overrides to `_run_single`.

- [ ] **Step 5: Update `cli.py:_check_multirun_launcher`** to call `check_cartesian_size` for all multirun paths (including `+ablation.<axis>=[…]` overrides without recipe.variations).

- [ ] **Step 6: Add fixtures** under `tests/fixtures/`:
- `recipe_with_variations.yaml` — 2 axes (lr × batch_size), 2 values each → 4 variations
- `recipe_with_link_to.yaml` — axis B `link_to: A`, A has 3 values → 3 variations

- [ ] **Step 7: Run tests — verify PASS**.

- [ ] **Step 8: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-infra): variations launcher + cartesian preflight + ClearML tags (P1-D)"
git push -u origin feature/phase-4-variations-launcher
gh pr create --base dev --title "feat(pet-infra): variations + preflight + ClearML tags (P1-D)" \
  --body "Launcher consumes ExperimentRecipe.variations cartesian-style with link_to co-iteration; preflight warns at >16 and fails at >64 (PET_ALLOW_LARGE_SWEEP=1 override); ClearML gets per-variation tag. Phase 4 W3."
gh pr merge --auto --squash
```

### PR P1-E: pet-infra `pet run --replay <card-id>` CLI

**Branch:** `feature/phase-4-replay-cli` → `dev`
**Repo:** `pet-infra` (depends on P1-D + S3Storage from P1-A)
**Files:**
- Modify: `src/pet_infra/cli.py` (add `--replay` option to `run` command)
- Create: `src/pet_infra/replay.py` (load ModelCard → fetch resolved_config → execute)
- Create: `tests/cli/test_replay.py`

- [ ] **Step 1: Branch + write failing test**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-replay-cli
```

Create `tests/cli/test_replay.py`:

```python
from click.testing import CliRunner
from pet_infra.cli import cli


def test_replay_dispatches_with_resolved_config(tmp_path, monkeypatch, model_card_with_resolved_uri):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--replay", model_card_with_resolved_uri.id, "--dry-run"])
    assert result.exit_code == 0
    assert "resolved_config" in result.output
    assert model_card_with_resolved_uri.id in result.output


def test_replay_missing_resolved_config_errors(tmp_path, model_card_no_resolved):
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--replay", model_card_no_resolved.id])
    assert result.exit_code != 0
    assert "resolved_config_uri" in result.output
```

Add `model_card_with_resolved_uri` / `model_card_no_resolved` fixtures in `tests/cli/conftest.py` (write a ModelCard JSON to a fake registry dir; monkeypatch `pet_infra.replay._load_card` to read from that dir).

- [ ] **Step 2: Run tests — verify FAIL**.

- [ ] **Step 3: Implement `src/pet_infra/replay.py`**

```python
"""Tier 2 deterministic replay: ModelCard.resolved_config_uri → multirun re-execute."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pet_schema.model_card import ModelCard

from pet_infra.registry import STORAGE


def _load_card(card_id: str) -> ModelCard:
    """Read ModelCard JSON from $PET_CARD_REGISTRY/<card_id>.json (default ./model_cards)."""
    import os, json
    root = Path(os.environ.get("PET_CARD_REGISTRY", "./model_cards"))
    return ModelCard.model_validate_json((root / f"{card_id}.json").read_text())


def fetch_resolved_config(card: ModelCard) -> str:
    if not card.resolved_config_uri:
        raise ValueError(f"ModelCard {card.id} has no resolved_config_uri (pre-Phase-4 run, cannot replay deterministically)")
    scheme = urlparse(card.resolved_config_uri).scheme or "file"
    storage = STORAGE.build({"type": scheme})
    return storage.read(card.resolved_config_uri).decode("utf-8")


def replay(card_id: str, *, dry_run: bool = False) -> dict:
    card = _load_card(card_id)
    resolved_yaml = fetch_resolved_config(card)
    return {"card_id": card.id, "resolved_config": resolved_yaml, "dry_run": dry_run}
```

- [ ] **Step 4: Wire `--replay` into CLI**

Edit `src/pet_infra/cli.py`:

```python
@run_cmd.command(name="run")
@click.option("--replay", "replay_id", type=str, default=None,
              help="Replay a previous run by ModelCard.id (Tier 2 deterministic).")
@click.option("--dry-run", is_flag=True, default=False)
# ... existing options ...
def run(replay_id, dry_run, ...):
    if replay_id is not None:
        from pet_infra.replay import replay
        result = replay(replay_id, dry_run=dry_run)
        click.echo(f"resolved_config for {result['card_id']}:\n{result['resolved_config']}")
        if dry_run:
            return
        # Else: feed resolved YAML back into launcher as overrides
        ...
```

- [ ] **Step 5: Run tests — verify PASS**.

- [ ] **Step 6: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-infra): pet run --replay <card-id> Tier-2 deterministic CLI (P1-E)"
git push -u origin feature/phase-4-replay-cli
gh pr create --base dev --title "feat(pet-infra): pet run --replay (P1-E)" \
  --body "Adds Tier-2 deterministic replay: load ModelCard, fetch resolved_config_uri via STORAGE registry, re-execute. --dry-run prints config only. Phase 4 W4."
gh pr merge --auto --squash
```

### PR P1-F: pet-infra W&B physical removal + `no-wandb-residue` CI guard

**Branch:** `feature/phase-4-wandb-removal-infra` → `dev`
**Repo:** `pet-infra` (independent; can run parallel with P1-A..P1-E)
**Files:**
- Modify: `docker-compose.yml` (remove wandb service + wandb-data volume, lines ~25-40)
- Modify: `Makefile` (remove any `wandb-up` / `wandb-down` targets)
- Modify: `docs/DEVELOPMENT_GUIDE.md` (remove all W&B prose, replace pointer to ClearML)
- Modify: `.gitignore` (remove `wandb/` entries)
- Create: `.github/workflows/no-wandb-residue.yml` (or extend existing CI: `! grep -rE '^[^#]*wandb' --include='*.{py,yaml,yml,toml,sh,md}' .` returns 0 matches)
- Modify: `.pre-commit-config.yaml` (add same grep as a hook)

- [ ] **Step 1: Branch + remove wandb service**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-wandb-removal-infra
```

Edit `docker-compose.yml`: delete the wandb service block (≈ lines 25-40) and the `wandb-data:` entry under `volumes:`. Verify `docker compose config` parses.

- [ ] **Step 2: Add `no-wandb-residue` CI workflow**

Create `.github/workflows/no-wandb-residue.yml`:

```yaml
name: no-wandb-residue
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan for wandb references
        run: |
          set -e
          MATCHES=$(grep -rEn --include='*.py' --include='*.yaml' --include='*.yml' \
                              --include='*.toml' --include='*.sh' --include='*.md' \
                              --exclude-dir=.git --exclude-dir=node_modules \
                              --exclude='no-wandb-residue.yml' \
                              -e '\bwandb\b' . || true)
          if [ -n "$MATCHES" ]; then
            echo "::error::W&B residue found:"
            echo "$MATCHES"
            exit 1
          fi
```

- [ ] **Step 3: Sweep + remove all `wandb` mentions in pet-infra repo**

```bash
grep -rn 'wandb' --include='*.py' --include='*.yaml' --include='*.yml' \
                  --include='*.toml' --include='*.md' --include='*.sh' \
                  --exclude-dir=.git . | tee /tmp/wandb-residue.txt
```
Edit each match: remove block / replace with ClearML-equivalent prose.

- [ ] **Step 4: Update DEVELOPMENT_GUIDE.md**

Replace any "experiment tracking via W&B" / "wandb.init" content with the ClearML equivalents. Add a sentence: "W&B was removed in Phase 4 P1-F; ClearML is the sole experiment tracker."

- [ ] **Step 5: Run pre-commit + CI scan locally**

```bash
pre-commit run --all-files
bash -c "grep -rEn -e '\bwandb\b' --include='*.py' --include='*.yaml' \
         --exclude-dir=.git . || echo CLEAN"
```
Expected: `CLEAN`.

- [ ] **Step 6: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "chore(pet-infra): remove all W&B residue + add no-wandb-residue CI guard (P1-F)"
git push -u origin feature/phase-4-wandb-removal-infra
gh pr create --base dev --title "chore(pet-infra): W&B physical removal + CI guard (P1-F)" \
  --body "Removes wandb docker service, .gitignore entries, prose; adds no-wandb-residue CI workflow. Phase 4 W5 (pet-infra slice)."
gh pr merge --auto --squash
```

### PR P1-G: pet-infra 2.5.0-rc1 release tag (rc only — final tag in P5-A-2)

**Branch:** `release/pet-infra-2.5.0-rc1` → `dev` (NOT main yet — final cut at P5-A)
**Repo:** `pet-infra` (after P1-A..F all merged)
**Files:**
- Modify: `pyproject.toml` (2.4.0 → 2.5.0-rc1)
- Modify: `CHANGELOG.md` (add 2.5.0-rc1 section enumerating P1-A..F)

- [ ] **Step 1: Branch from up-to-date dev**

```bash
git checkout dev && git pull --ff-only
git checkout -b release/pet-infra-2.5.0-rc1
```

- [ ] **Step 2: Bump version + CHANGELOG**

Edit `pyproject.toml`: `2.4.0` → `2.5.0-rc1`.
Prepend `CHANGELOG.md`:

```markdown
## 2.5.0-rc1 — 2026-04-22

### Added
- `S3Storage` plugin (P1-A) — boto3-backed, scheme `s3`.
- `HttpStorage` plugin (P1-B) — read-only CDN/static-server, scheme `http`/`https`.
- Launcher dumps resolved Hydra config per variation; sweep_summary.json carries `resolved_config_uri` (P1-C).
- `ExperimentRecipe.variations` cartesian launcher with `link_to` co-iteration; ClearML per-variation tag injection (P1-D).
- Cartesian sweep preflight: warn at >16, fail at >64; `PET_ALLOW_LARGE_SWEEP=1` override (P1-D).
- `pet run --replay <card-id>` Tier-2 deterministic replay CLI (P1-E).
- `no-wandb-residue` CI guard (P1-F).

### Removed
- W&B docker service, .gitignore entries, all prose (P1-F).

### Changed
- `pet-schema` peer-dep bumped to `>=2.4.0-rc1,<3` (P1-C).
```

- [ ] **Step 3: Run full test + lint**

```bash
pip install -e ".[test]"
ruff check . && mypy src/ && pytest -x
```

- [ ] **Step 4: Commit + PR + merge + tag rc1**

```bash
git add -A
git commit -m "release(pet-infra): 2.5.0-rc1 (P1-G)"
git push -u origin release/pet-infra-2.5.0-rc1
gh pr create --base dev --title "release(pet-infra): 2.5.0-rc1 (P1-G)" \
  --body "RC tag for Phase 4 W1+W3+W4+W5 (pet-infra slice). Final 2.5.0 tag in P5-A-2."
gh pr merge --auto --squash
# wait for merge
git checkout dev && git pull --ff-only
git tag v2.5.0-rc1 && git push origin v2.5.0-rc1
```

---

## Phase 2-A — pet-ota 2.1.0-rc1 (5 PRs) — W1 OTA backends

Adds `S3BackendPlugin` (LocalStack-tested) and `HttpBackendPlugin` (3 auth modes), and bumps peer-dep to pick up pet-infra 2.5.0-rc1 + pet-schema 2.4.0-rc1. Independent of P2-B.

### PR P2-A-1: pet-ota peer-dep bump (pet-schema 2.4.0-rc1 + pet-infra 2.5.0-rc1)

**Branch:** `feature/phase-4-peer-dep-bump-ota` → `dev`
**Repo:** `pet-ota` (depends on P0-A and P1-G merged + rc1 tags pushed)
**Files:**
- Modify: `pyproject.toml` (peer-deps)
- Modify: `.github/workflows/ci.yml` (4-step install: pet-schema → pet-infra → pet-ota → tests)
- Create/Modify: `tests/peer_dep/test_smoke_versions.py`

- [ ] **Step 1: Branch + bump deps**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-ota
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-peer-dep-bump-ota
```

In `pyproject.toml`:
- `"pet-schema>=2.3.1,<3"` → `"pet-schema>=2.4.0-rc1,<3"`
- `"pet-infra>=2.4.0,<3"` → `"pet-infra>=2.5.0-rc1,<3"`

- [ ] **Step 2: Update CI 4-step install order**

In `.github/workflows/ci.yml` ensure:
```yaml
- run: pip install "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@v2.4.0-rc1"
- run: pip install "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.5.0-rc1"
- run: pip install -e ".[test]"
- run: pytest -x
```

- [ ] **Step 3: Add peer-dep smoke test**

Create `tests/peer_dep/test_smoke_versions.py`:

```python
def test_pet_schema_version():
    import pet_schema
    assert pet_schema.__version__.startswith("2.4")


def test_pet_infra_version():
    import pet_infra
    assert pet_infra.__version__.startswith("2.5")


def test_storage_registry_has_s3_http():
    from pet_infra.registry import STORAGE
    names = STORAGE._module_dict.keys()
    assert "s3" in names and "http" in names and "local" in names
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
pip install -U "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@v2.4.0-rc1"
pip install -U "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.5.0-rc1"
pip install -e ".[test]"
pytest -x
```

- [ ] **Step 5: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "chore(pet-ota): bump peer-deps to pet-schema 2.4.0-rc1 + pet-infra 2.5.0-rc1 (P2-A-1)"
git push -u origin feature/phase-4-peer-dep-bump-ota
gh pr create --base dev --title "chore(pet-ota): peer-dep bump (P2-A-1)" \
  --body "Bumps to pet-schema 2.4.0-rc1 (resolved_config_uri) + pet-infra 2.5.0-rc1 (S3/Http storage). Updates CI 4-step install order."
gh pr merge --auto --squash
```

### PR P2-A-2: pet-ota `S3BackendPlugin` (LocalStack-tested)

**Branch:** `feature/phase-4-ota-s3-backend` → `dev`
**Repo:** `pet-ota`
**Files:**
- Create: `src/pet_ota/plugins/backends/s3.py`
- Create: `tests/plugins/backends/test_s3_backend.py` (uses `moto` fixture from pet-infra pattern)
- Modify: `tests/conftest.py` (add `s3_bucket` moto fixture if not yet present)

- [ ] **Step 1: Branch + write failing tests**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-ota-s3-backend
```

Create `tests/plugins/backends/test_s3_backend.py`:

```python
import json
from datetime import datetime, timezone
import pytest
from pet_schema.model_card import ModelCard, EdgeArtifact
from pet_schema.recipe import ExperimentRecipe

from pet_ota.plugins.backends.s3 import S3BackendPlugin


@pytest.fixture
def passing_card(tmp_path):
    art = tmp_path / "edge.rknn"
    art.write_bytes(b"BINARY")
    return ModelCard(
        id="card-1", version="0.1.0", modality="vlm", task="caption", arch="qwen",
        training_recipe="sft", hydra_config_sha="abc", git_shas={}, dataset_versions={},
        checkpoint_uri="s3://x/ckpt", metrics={"acc": 0.9}, gate_status="passed",
        trained_at=datetime.now(timezone.utc), trained_by="ci",
        edge_artifacts=[EdgeArtifact(name="edge.rknn", path=str(art), sha256="d", size_bytes=6, format="rknn")],
    )


def test_s3_backend_uploads_artifacts(passing_card, s3_bucket, minimal_recipe):
    plugin = S3BackendPlugin(bucket=s3_bucket["bucket"], prefix="ota/", endpoint_url=s3_bucket["endpoint_url"])
    out_card = plugin.run(passing_card, minimal_recipe)
    assert out_card.deployment_history[-1].backend == "s3"
    assert out_card.deployment_history[-1].status == "deployed"
    # manifest exists
    from pet_infra.storage.s3 import S3Storage
    s = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    assert s.exists(f"s3://{s3_bucket['bucket']}/ota/card-1/manifest.json")


def test_s3_backend_rejects_unpassed_gate(passing_card, s3_bucket, minimal_recipe):
    passing_card = passing_card.model_copy(update={"gate_status": "pending"})
    plugin = S3BackendPlugin(bucket=s3_bucket["bucket"], prefix="ota/", endpoint_url=s3_bucket["endpoint_url"])
    with pytest.raises(ValueError, match="gate_status"):
        plugin.run(passing_card, minimal_recipe)
```

- [ ] **Step 2: Run — verify FAIL** (ImportError).

- [ ] **Step 3: Implement `S3BackendPlugin`**

Mirror the existing `LocalBackendPlugin` template at `src/pet_ota/plugins/backends/local.py`, but persist via `pet_infra.storage.s3.S3Storage`:

```python
"""S3 OTA backend — uploads edge artifacts + manifest to s3://<bucket>/<prefix>/<card_id>/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pet_schema.model_card import DeploymentStatus, ModelCard
from pet_schema.recipe import ExperimentRecipe

from pet_infra.registry import OTA
from pet_infra.storage.s3 import S3Storage


@OTA.register_module(name="s3_backend", force=True)
class S3BackendPlugin:
    def __init__(self, bucket: str, prefix: str = "ota/", endpoint_url: str | None = None, **_: object):
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/"
        self._storage = S3Storage(endpoint_url=endpoint_url)

    def _uri(self, key: str) -> str:
        return f"s3://{self._bucket}/{self._prefix}{key}"

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        if input_card.gate_status != "passed":
            raise ValueError(f"S3BackendPlugin requires gate_status=passed, got {input_card.gate_status!r}")
        manifest = {"card_id": input_card.id, "version": input_card.version, "edge_artifacts": []}
        for art in input_card.edge_artifacts:
            data = Path(art.path).read_bytes()
            uri = self._uri(f"{input_card.id}/{art.name}")
            self._storage.write(uri, data)
            manifest["edge_artifacts"].append({"name": art.name, "uri": uri, "sha256": art.sha256, "size_bytes": art.size_bytes})
        manifest_uri = self._uri(f"{input_card.id}/manifest.json")
        self._storage.write(manifest_uri, json.dumps(manifest, indent=2).encode())
        return input_card.model_copy(update={
            "deployment_history": [
                *input_card.deployment_history,
                DeploymentStatus(
                    backend="s3", target=self._uri(input_card.id),
                    status="deployed", deployed_at=datetime.now(timezone.utc),
                ),
            ]
        })
```

Note: `DeploymentStatus.backend` field — verify by reading `pet-schema/src/pet_schema/model_card.py`. If it does not allow free-form, update pet-schema first via a follow-up to P0-A. (Default assumption: `backend: str` accepts "s3" / "http" / "local".)

- [ ] **Step 4: Run tests — verify PASS**.

- [ ] **Step 5: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-ota): S3BackendPlugin for OTA artifact upload (P2-A-2)"
git push -u origin feature/phase-4-ota-s3-backend
gh pr create --base dev --title "feat(pet-ota): S3BackendPlugin (P2-A-2)" \
  --body "Adds S3BackendPlugin uploading edge artifacts + manifest.json to s3://<bucket>/<prefix>/<card_id>/. LocalStack/moto-tested. Phase 4 W1."
gh pr merge --auto --squash
```

### PR P2-A-3: pet-ota `HttpBackendPlugin` with 3 auth modes (none / bearer / basic)

**Branch:** `feature/phase-4-ota-http-backend` → `dev`
**Repo:** `pet-ota`
**Files:**
- Create: `src/pet_ota/plugins/backends/http.py`
- Create: `tests/plugins/backends/test_http_backend.py` (uses `http.server` fixture)

- [ ] **Step 1: Branch + write failing tests**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-ota-http-backend
```

Create `tests/plugins/backends/test_http_backend.py`:

```python
import http.server, socketserver, threading, base64, pytest
from datetime import datetime, timezone
from pathlib import Path
from pet_schema.model_card import ModelCard, EdgeArtifact

from pet_ota.plugins.backends.http import HttpBackendPlugin


class _AuthHandler(http.server.SimpleHTTPRequestHandler):
    expected_auth = None
    received = []

    def do_PUT(self):
        if self.expected_auth and self.headers.get("Authorization") != self.expected_auth:
            self.send_response(401); self.end_headers(); return
        length = int(self.headers["Content-Length"])
        self.received.append((self.path, self.rfile.read(length)))
        self.send_response(201); self.end_headers()


@pytest.fixture
def http_server(tmp_path):
    _AuthHandler.received.clear()
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _AuthHandler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield {"base_url": f"http://127.0.0.1:{port}", "handler": _AuthHandler}
    httpd.shutdown(); httpd.server_close()


@pytest.fixture
def passing_card(tmp_path):
    art = tmp_path / "edge.rknn"
    art.write_bytes(b"BIN")
    return ModelCard(
        id="card-1", version="0.1.0", modality="vlm", task="caption", arch="qwen",
        training_recipe="sft", hydra_config_sha="abc", git_shas={}, dataset_versions={},
        checkpoint_uri="s3://x/ckpt", metrics={"acc": 0.9}, gate_status="passed",
        trained_at=datetime.now(timezone.utc), trained_by="ci",
        edge_artifacts=[EdgeArtifact(name="edge.rknn", path=str(art), sha256="d", size_bytes=3, format="rknn")],
    )


def test_http_backend_no_auth(http_server, passing_card, minimal_recipe):
    plugin = HttpBackendPlugin(base_url=http_server["base_url"])
    plugin.run(passing_card, minimal_recipe)
    assert any(p == "/card-1/edge.rknn" for p, _ in http_server["handler"].received)


def test_http_backend_bearer(http_server, passing_card, minimal_recipe):
    http_server["handler"].expected_auth = "Bearer T0K3N"
    plugin = HttpBackendPlugin(base_url=http_server["base_url"], auth_token="T0K3N")
    plugin.run(passing_card, minimal_recipe)
    assert http_server["handler"].received


def test_http_backend_basic(http_server, passing_card, minimal_recipe):
    enc = base64.b64encode(b"u:p").decode()
    http_server["handler"].expected_auth = f"Basic {enc}"
    plugin = HttpBackendPlugin(base_url=http_server["base_url"], basic_auth=("u", "p"))
    plugin.run(passing_card, minimal_recipe)
    assert http_server["handler"].received
```

- [ ] **Step 2: Implement `HttpBackendPlugin`** (PUT-style upload):

```python
@OTA.register_module(name="http_backend", force=True)
class HttpBackendPlugin:
    def __init__(
        self, base_url: str, *,
        auth_token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        timeout_s: float = 30.0,
        **_: object,
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._auth = basic_auth
        self._headers: dict[str, str] = {}
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

    def run(self, input_card: ModelCard, recipe) -> ModelCard:
        if input_card.gate_status != "passed":
            raise ValueError(...)
        for art in input_card.edge_artifacts:
            data = Path(art.path).read_bytes()
            url = f"{self._base}/{input_card.id}/{art.name}"
            r = requests.put(url, data=data, timeout=self._timeout, headers=self._headers, auth=self._auth)
            r.raise_for_status()
        manifest_url = f"{self._base}/{input_card.id}/manifest.json"
        manifest = json.dumps({"card_id": input_card.id, "edge_artifacts": [a.model_dump() for a in input_card.edge_artifacts]}).encode()
        requests.put(manifest_url, data=manifest, headers={**self._headers, "Content-Type": "application/json"}, auth=self._auth, timeout=self._timeout).raise_for_status()
        return input_card.model_copy(update={"deployment_history": [
            *input_card.deployment_history,
            DeploymentStatus(backend="http", target=self._base + f"/{input_card.id}", status="deployed",
                             deployed_at=datetime.now(timezone.utc)),
        ]})
```

- [ ] **Step 3: Run tests — verify PASS** (3 auth modes).

- [ ] **Step 4: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-ota): HttpBackendPlugin with bearer/basic/no-auth (P2-A-3)"
git push -u origin feature/phase-4-ota-http-backend
gh pr create --base dev --title "feat(pet-ota): HttpBackendPlugin (P2-A-3)" \
  --body "Adds HttpBackendPlugin (PUT upload) with three auth modes; tested via in-process http.server. Phase 4 W1."
gh pr merge --auto --squash
```

### PR P2-A-4: pet-ota `_register.py` wiring + `peer-dep-smoke` CI job

**Branch:** `feature/phase-4-ota-register-wiring` → `dev`
**Repo:** `pet-ota`
**Files:**
- Modify: `src/pet_ota/plugins/_register.py` (import s3 + http modules so registration runs)
- Modify: `.github/workflows/ci.yml` (add `peer-dep-smoke` job that imports + lists OTA registry names)
- Modify: `tests/test_register.py` (assert all 3 backends registered)

- [ ] **Step 1: Branch + write failing test**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-ota-register-wiring
```

In `tests/test_register.py`:

```python
def test_three_backends_registered():
    from pet_ota.plugins import _register  # noqa: F401 (side-effect)
    from pet_infra.registry import OTA
    names = set(OTA._module_dict.keys())
    assert {"local_backend", "s3_backend", "http_backend"} <= names
```

- [ ] **Step 2: Update `_register.py`**

```python
from . import backends  # noqa: F401
from .backends import local, s3, http  # noqa: F401
```

- [ ] **Step 3: Add CI peer-dep-smoke job**

In `.github/workflows/ci.yml`:

```yaml
peer-dep-smoke:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11" }
    - run: pip install "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@v2.4.0-rc1"
    - run: pip install "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.5.0-rc1"
    - run: pip install -e .
    - run: |
        python -c "
        from pet_ota.plugins import _register
        from pet_infra.registry import OTA
        names = sorted(OTA._module_dict.keys())
        assert {'local_backend','s3_backend','http_backend'}.issubset(names), names
        print('OTA registry:', names)
        "
```

- [ ] **Step 4: Run + commit + PR + auto-merge**

```bash
pytest -x
git add -A
git commit -m "feat(pet-ota): wire S3 + HTTP backends into registry + peer-dep-smoke CI (P2-A-4)"
git push -u origin feature/phase-4-ota-register-wiring
gh pr create --base dev --title "feat(pet-ota): register wiring + peer-dep-smoke (P2-A-4)" \
  --body "Wires S3/HTTP backends into _register.py and adds peer-dep-smoke CI job that builds against tagged pet-schema 2.4.0-rc1 + pet-infra 2.5.0-rc1."
gh pr merge --auto --squash
```

### PR P2-A-5: pet-ota 2.1.0-rc1 release tag

**Branch:** `release/pet-ota-2.1.0-rc1` → `dev`
**Repo:** `pet-ota`
**Files:**
- Modify: `pyproject.toml` (2.0.0 → 2.1.0-rc1)
- Modify: `CHANGELOG.md` (add 2.1.0-rc1 section)

- [ ] **Step 1: Branch + bump + CHANGELOG**

```bash
git checkout dev && git pull --ff-only
git checkout -b release/pet-ota-2.1.0-rc1
```

Edit pyproject.toml `2.0.0` → `2.1.0-rc1`. Prepend CHANGELOG:

```markdown
## 2.1.0-rc1 — 2026-04-22

### Added
- `S3BackendPlugin` (P2-A-2) — LocalStack/moto-tested OTA upload to S3.
- `HttpBackendPlugin` (P2-A-3) — three auth modes (none / bearer / basic).
- `peer-dep-smoke` CI job verifying registration against tagged peer-deps (P2-A-4).

### Changed
- Peer-deps bumped: `pet-schema>=2.4.0-rc1`, `pet-infra>=2.5.0-rc1` (P2-A-1).
```

- [ ] **Step 2: Commit + PR + merge + tag**

```bash
git add -A
git commit -m "release(pet-ota): 2.1.0-rc1 (P2-A-5)"
git push -u origin release/pet-ota-2.1.0-rc1
gh pr create --base dev --title "release(pet-ota): 2.1.0-rc1 (P2-A-5)" \
  --body "RC for Phase 4 W1 (OTA backends slice). Final 2.1.0 in P5-A-3."
gh pr merge --auto --squash
git checkout dev && git pull --ff-only
git tag v2.1.0-rc1 && git push origin v2.1.0-rc1
```

---

## Phase 2-B — pet-eval 2.2.0-rc1 (5 PRs) — W2 cross-modal fusion + W5 W&B residue

Adds **rule-based** fusion evaluators (single_modal / and_gate / weighted) per spec §4.5/§7.6, ships `cross_modal_fusion_eval` recipe fixture, removes pet-eval W&B residue (generate_report.py shim, params.yaml block, .gitignore). **No learned fusion** (per `feedback_no_learned_fusion`).

### PR P2-B-1: pet-eval peer-dep bump

**Branch:** `feature/phase-4-peer-dep-bump-eval` → `dev`
**Repo:** `pet-eval`
**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml` (5-step install: pet-schema → pet-infra → pet-train → pet-quantize → pet-eval)
- Create: `tests/peer_dep/test_smoke_versions.py`

- [ ] **Step 1: Branch + bump deps**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-peer-dep-bump-eval
```

In `pyproject.toml`:
- `"pet-schema>=2.3.1,<3"` → `"pet-schema>=2.4.0-rc1,<3"`
- `"pet-infra>=2.4.0,<3"` → `"pet-infra>=2.5.0-rc1,<3"`
- (pet-train soft remains as-is until P2-C-1; pet-quantize soft as-is)

- [ ] **Step 2: Update CI install order + add smoke test**

5-step install order in CI; add `tests/peer_dep/test_smoke_versions.py` mirroring P2-A-1's pattern.

- [ ] **Step 3: Run + commit + PR + merge**

```bash
pytest -x
git add -A
git commit -m "chore(pet-eval): bump peer-deps to pet-schema 2.4.0-rc1 + pet-infra 2.5.0-rc1 (P2-B-1)"
git push -u origin feature/phase-4-peer-dep-bump-eval
gh pr create --base dev --title "chore(pet-eval): peer-dep bump (P2-B-1)" \
  --body "Bumps to pet-schema 2.4.0-rc1 + pet-infra 2.5.0-rc1; preserves 5-step CI install order."
gh pr merge --auto --squash
```

### PR P2-B-2: pet-eval 3 cross-modal fusion evaluator plugins (rule-based)

**Branch:** `feature/phase-4-fusion-evaluators` → `dev`
**Repo:** `pet-eval`
**Files:**
- Create: `src/pet_eval/plugins/fusion/__init__.py`
- Create: `src/pet_eval/plugins/fusion/single_modal.py`
- Create: `src/pet_eval/plugins/fusion/and_gate.py`
- Create: `src/pet_eval/plugins/fusion/weighted.py`
- Create: `src/pet_eval/plugins/fusion/base.py` (shared base)
- Modify: `src/pet_eval/plugins/_register.py` (import fusion modules)
- Create: `tests/plugins/fusion/test_single_modal.py`
- Create: `tests/plugins/fusion/test_and_gate.py`
- Create: `tests/plugins/fusion/test_weighted.py`

- [ ] **Step 1: Branch + write failing tests for all 3 evaluators**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-fusion-evaluators
```

Create `tests/plugins/fusion/test_single_modal.py`:

```python
import pytest
from pet_eval.plugins.fusion.single_modal import SingleModalFusionEvaluator


def test_single_modal_passes_through_modality():
    ev = SingleModalFusionEvaluator(modality="audio")
    score = ev.fuse({"audio": 0.8, "vlm": 0.3})
    assert score == 0.8


def test_single_modal_missing_raises():
    ev = SingleModalFusionEvaluator(modality="audio")
    with pytest.raises(KeyError):
        ev.fuse({"vlm": 0.3})
```

Create `tests/plugins/fusion/test_and_gate.py`:

```python
import pytest
from pet_eval.plugins.fusion.and_gate import AndGateFusionEvaluator


def test_and_gate_all_above_threshold_returns_min():
    ev = AndGateFusionEvaluator(threshold=0.5)
    assert ev.fuse({"audio": 0.6, "vlm": 0.7}) == 0.6


def test_and_gate_one_below_threshold_returns_zero():
    ev = AndGateFusionEvaluator(threshold=0.5)
    assert ev.fuse({"audio": 0.6, "vlm": 0.3}) == 0.0


def test_and_gate_empty_raises():
    ev = AndGateFusionEvaluator(threshold=0.5)
    with pytest.raises(ValueError):
        ev.fuse({})
```

Create `tests/plugins/fusion/test_weighted.py`:

```python
import pytest
from pet_eval.plugins.fusion.weighted import WeightedFusionEvaluator


def test_weighted_basic():
    ev = WeightedFusionEvaluator(weights={"audio": 0.7, "vlm": 0.3})
    assert ev.fuse({"audio": 1.0, "vlm": 0.0}) == pytest.approx(0.7)


def test_weighted_normalizes():
    ev = WeightedFusionEvaluator(weights={"audio": 2.0, "vlm": 2.0})
    assert ev.fuse({"audio": 0.6, "vlm": 0.4}) == pytest.approx(0.5)


def test_weighted_missing_modality_treated_as_zero():
    ev = WeightedFusionEvaluator(weights={"audio": 0.5, "vlm": 0.5})
    assert ev.fuse({"audio": 0.8}) == pytest.approx(0.4)
```

- [ ] **Step 2: Run tests — verify FAIL**.

- [ ] **Step 3: Implement `base.py`**

```python
"""Base for rule-based cross-modal fusion evaluators (Phase 4 W2)."""

from abc import ABC, abstractmethod


class BaseFusionEvaluator(ABC):
    @abstractmethod
    def fuse(self, modality_scores: dict[str, float]) -> float:
        """Combine per-modality scores into one fused score."""
```

- [ ] **Step 4: Implement `single_modal.py`**

```python
from pet_infra.registry import EVALUATORS
from .base import BaseFusionEvaluator


@EVALUATORS.register_module(name="single_modal_fusion", force=True)
class SingleModalFusionEvaluator(BaseFusionEvaluator):
    def __init__(self, modality: str, **_):
        self._modality = modality

    def fuse(self, modality_scores):
        return modality_scores[self._modality]
```

- [ ] **Step 5: Implement `and_gate.py`**

```python
from pet_infra.registry import EVALUATORS
from .base import BaseFusionEvaluator


@EVALUATORS.register_module(name="and_gate_fusion", force=True)
class AndGateFusionEvaluator(BaseFusionEvaluator):
    def __init__(self, threshold: float, **_):
        self._threshold = threshold

    def fuse(self, modality_scores):
        if not modality_scores:
            raise ValueError("AndGate requires at least one modality score")
        if all(s >= self._threshold for s in modality_scores.values()):
            return min(modality_scores.values())
        return 0.0
```

- [ ] **Step 6: Implement `weighted.py`**

```python
from pet_infra.registry import EVALUATORS
from .base import BaseFusionEvaluator


@EVALUATORS.register_module(name="weighted_fusion", force=True)
class WeightedFusionEvaluator(BaseFusionEvaluator):
    def __init__(self, weights: dict[str, float], **_):
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("WeightedFusionEvaluator requires positive weight sum")
        self._weights = {k: v / total for k, v in weights.items()}

    def fuse(self, modality_scores):
        return sum(self._weights.get(m, 0.0) * modality_scores.get(m, 0.0) for m in self._weights)
```

- [ ] **Step 7: Wire into `_register.py`**

```python
from .fusion import single_modal, and_gate, weighted  # noqa: F401
```

- [ ] **Step 8: Run tests — verify PASS** (8 tests).

- [ ] **Step 9: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-eval): 3 rule-based cross-modal fusion evaluators (P2-B-2)"
git push -u origin feature/phase-4-fusion-evaluators
gh pr create --base dev --title "feat(pet-eval): rule-based fusion evaluators (P2-B-2)" \
  --body "Adds single_modal_fusion, and_gate_fusion, weighted_fusion evaluators per spec §4.5/§7.6. NO learned fusion (per feedback_no_learned_fusion). Phase 4 W2."
gh pr merge --auto --squash
```

### PR P2-B-3: pet-eval `cross_modal_fusion_eval` recipe fixture

**Branch:** `feature/phase-4-fusion-recipe` → `dev`
**Repo:** `pet-eval`
**Files:**
- Create: `recipes/cross_modal_fusion_eval.yaml` (and_gate variant by default; demos all 3)
- Create: `tests/recipes/test_fusion_recipe.py`

- [ ] **Step 1: Branch + write failing test**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-fusion-recipe
```

Create `tests/recipes/test_fusion_recipe.py`:

```python
from pet_schema.recipe import ExperimentRecipe
import yaml
from pathlib import Path


def test_fusion_recipe_validates():
    raw = yaml.safe_load(Path("recipes/cross_modal_fusion_eval.yaml").read_text())
    rec = ExperimentRecipe.model_validate(raw)
    assert rec.id == "cross_modal_fusion_eval"
    # 3 variations across fusion strategies
    assert any(v.name == "fusion_strategy" for v in (rec.variations or []))


def test_fusion_recipe_has_all_three_strategies():
    raw = yaml.safe_load(Path("recipes/cross_modal_fusion_eval.yaml").read_text())
    rec = ExperimentRecipe.model_validate(raw)
    axis = next(v for v in rec.variations if v.name == "fusion_strategy")
    assert set(axis.values) == {"single_modal_fusion", "and_gate_fusion", "weighted_fusion"}
```

- [ ] **Step 2: Run — verify FAIL**.

- [ ] **Step 3: Implement recipe**

`recipes/cross_modal_fusion_eval.yaml`:

```yaml
id: cross_modal_fusion_eval
version: "0.1.0"
description: |
  Cross-modal fusion evaluation across 3 rule-based strategies
  (single_modal / and_gate / weighted). Phase 4 W2.
clearml_tags:
  - phase-4
  - cross-modal-fusion
defaults:
  evaluator:
    type: weighted_fusion
    weights:
      audio: 0.5
      vlm: 0.5
  threshold: 0.5
variations:
  - name: fusion_strategy
    stage: eval
    hydra_path: evaluator.type
    values: [single_modal_fusion, and_gate_fusion, weighted_fusion]
```

- [ ] **Step 4: Run tests — verify PASS**.

- [ ] **Step 5: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "feat(pet-eval): cross_modal_fusion_eval recipe with 3-strategy variations (P2-B-3)"
git push -u origin feature/phase-4-fusion-recipe
gh pr create --base dev --title "feat(pet-eval): fusion recipe (P2-B-3)" \
  --body "Adds cross_modal_fusion_eval recipe variating across single_modal/and_gate/weighted. Drives the launcher via ExperimentRecipe.variations. Phase 4 W2."
gh pr merge --auto --squash
```

### PR P2-B-4: pet-eval W&B residue removal (generate_report shim + params.yaml + .gitignore)

**Branch:** `feature/phase-4-wandb-removal-eval` → `dev`
**Repo:** `pet-eval`
**Files:**
- Modify: `src/pet_eval/report/generate_report.py` (lines 6,7,28,41 — remove `wandb_config` param entirely)
- Modify: `params.yaml:21` (remove `wandb:` block)
- Modify: `.gitignore` (remove `wandb/` entry)
- Modify: callers of `generate_report` if any pass `wandb_config=` (`grep -rn "wandb_config="`)

- [ ] **Step 1: Branch + locate all callers**

```bash
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-wandb-removal-eval
grep -rn "wandb_config\|wandb\." --include='*.py' --include='*.yaml' .
```

- [ ] **Step 2: Remove `wandb_config` param from `generate_report.py`**

Edit signature: drop `wandb_config: dict | None = None` parameter and any line that references `wandb_config`. Update docstring.

- [ ] **Step 3: Update callers** to drop `wandb_config=` kwarg.

- [ ] **Step 4: Strip `wandb:` block from `params.yaml`** + `.gitignore` `wandb/` line.

- [ ] **Step 5: Run full test + ensure no-wandb-residue grep is clean**

```bash
pytest -x
grep -rEn -e '\bwandb\b' --include='*.py' --include='*.yaml' --include='*.yml' \
                          --include='*.toml' --include='*.md' --exclude-dir=.git . || echo CLEAN
```
Expected: `CLEAN`.

- [ ] **Step 6: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "chore(pet-eval): remove all W&B residue (generate_report shim + params + .gitignore) (P2-B-4)"
git push -u origin feature/phase-4-wandb-removal-eval
gh pr create --base dev --title "chore(pet-eval): W&B residue removal (P2-B-4)" \
  --body "Drops wandb_config param from generate_report, removes params.yaml wandb block and .gitignore entry. Phase 4 W5 (pet-eval slice)."
gh pr merge --auto --squash
```

### PR P2-B-5: pet-eval 2.2.0-rc1 release tag

**Branch:** `release/pet-eval-2.2.0-rc1` → `dev`
**Repo:** `pet-eval`
**Files:**
- Modify: `pyproject.toml` (2.1.0 → 2.2.0-rc1)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Branch + bump + CHANGELOG**

Prepend CHANGELOG:

```markdown
## 2.2.0-rc1 — 2026-04-22

### Added
- 3 rule-based cross-modal fusion evaluators: single_modal / and_gate / weighted (P2-B-2).
- `recipes/cross_modal_fusion_eval.yaml` driving 3-strategy variations (P2-B-3).

### Removed
- `wandb_config` parameter from `generate_report` (P2-B-4); params.yaml wandb block; .gitignore wandb entry.

### Changed
- Peer-deps bumped: `pet-schema>=2.4.0-rc1`, `pet-infra>=2.5.0-rc1` (P2-B-1).

### Decision Note
- Learned fusion (spec §4.5 trainer + §7.6 strategy) deferred — current pet feeder business has no non-linear cross-modal need (per feedback_no_learned_fusion).
```

- [ ] **Step 2: Commit + PR + merge + tag**

```bash
git add -A
git commit -m "release(pet-eval): 2.2.0-rc1 (P2-B-5)"
git push -u origin release/pet-eval-2.2.0-rc1
gh pr create --base dev --title "release(pet-eval): 2.2.0-rc1 (P2-B-5)" \
  --body "RC for Phase 4 W2 + W5 (pet-eval slice). Final 2.2.0 in P5-A-4."
gh pr merge --auto --squash
git checkout dev && git pull --ff-only
git tag v2.2.0-rc1 && git push origin v2.2.0-rc1
```

---

## Phase 2-C — pet-train + pet-quantize W&B residue cleanup (2 PRs)

### PR P2-C-1: pet-train W&B residue removal + pyproject drift fix → 2.0.1-rc1

**Branch:** `feature/phase-4-wandb-removal-train` → `dev`
**Repo:** `pet-train` (currently pyproject 0.1.0 vs git tag v2.0.0-rc1 — fix drift here)
**Files:**
- Modify: `params.yaml:50` (remove `wandb:` block)
- Modify: `.gitignore` (remove `wandb/`)
- Modify: any source file referencing `wandb` (`grep -rn`)
- Modify: `pyproject.toml` (0.1.0 → 2.0.1-rc1 — fixes drift)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Branch + sweep**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-wandb-removal-train
grep -rEn -e '\bwandb\b' --include='*.py' --include='*.yaml' --include='*.yml' \
                          --include='*.toml' --include='*.md' --exclude-dir=.git . || echo CLEAN
```

- [ ] **Step 2: Remove all wandb references** (params.yaml block, .gitignore line, any python imports/calls).

- [ ] **Step 3: Fix pyproject drift**

In `pyproject.toml` change `version = "0.1.0"` → `version = "2.0.1-rc1"`.

- [ ] **Step 4: Update CHANGELOG**

Prepend:

```markdown
## 2.0.1-rc1 — 2026-04-22

### Removed
- All W&B references (params.yaml, .gitignore, source files) (Phase 4 W5 / P2-C-1).

### Fixed
- pyproject.toml version drift: bumped from `0.1.0` → `2.0.1-rc1` (git tag v2.0.0-rc1 had been ahead of pyproject since Phase 3A).
```

- [ ] **Step 5: Run + verify CLEAN + commit + PR + merge + tag**

```bash
pytest -x
grep -rEn -e '\bwandb\b' --include='*.py' --include='*.yaml' --exclude-dir=.git . || echo CLEAN
git add -A
git commit -m "chore(pet-train): remove W&B residue + fix pyproject drift (P2-C-1)"
git push -u origin feature/phase-4-wandb-removal-train
gh pr create --base dev --title "chore(pet-train): W&B removal + pyproject drift fix (P2-C-1)" \
  --body "Removes W&B params/gitignore/source refs; fixes pyproject 0.1.0 → 2.0.1-rc1 drift. Phase 4 W5."
gh pr merge --auto --squash
git checkout dev && git pull --ff-only
git tag v2.0.1-rc1 && git push origin v2.0.1-rc1
```

### PR P2-C-2: pet-quantize W&B residue removal → 2.0.1-rc1

**Branch:** `feature/phase-4-wandb-removal-quantize` → `dev`
**Repo:** `pet-quantize`
**Files:**
- Modify: `params.yaml:79-80` (remove `# === wandb ===` and `wandb:` block)
- Modify: `.gitignore` (remove `wandb/`)
- Modify: `pyproject.toml` (2.0.0 → 2.0.1-rc1)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Branch + sweep + remove**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-wandb-removal-quantize
```

Edit params.yaml and .gitignore.

- [ ] **Step 2: Bump version + CHANGELOG**

Prepend:

```markdown
## 2.0.1-rc1 — 2026-04-22

### Removed
- All W&B references (params.yaml block, .gitignore entry) (Phase 4 W5 / P2-C-2).
```

- [ ] **Step 3: Verify CLEAN + commit + PR + merge + tag**

```bash
pytest -x
grep -rEn -e '\bwandb\b' --include='*.py' --include='*.yaml' --exclude-dir=.git . || echo CLEAN
git add -A
git commit -m "chore(pet-quantize): remove W&B residue (P2-C-2)"
git push -u origin feature/phase-4-wandb-removal-quantize
gh pr create --base dev --title "chore(pet-quantize): W&B removal (P2-C-2)" \
  --body "Removes W&B params/gitignore. Phase 4 W5."
gh pr merge --auto --squash
git checkout dev && git pull --ff-only
git tag v2.0.1-rc1 && git push origin v2.0.1-rc1
```

---

## Phase 5-A — Matrix 2026.09 freeze + DEVELOPMENT_GUIDE sync + per-repo final tags (7 PRs)

Mirrors Phase 3B P5-A pattern. P5-A-0 lands first (matrix freeze + guide sync); P5-A-1..6 are per-repo final-tag PRs (`dev → main`) that cut `vX.Y.Z` from the rc1 commits. May overlap with W7 (BSL 1.1) PRs.

### PR P5-A-0: pet-infra matrix 2026.09 row + DEVELOPMENT_GUIDE sync

**Branch:** `feature/phase-4-matrix-2026-09` → `dev`
**Repo:** `pet-infra`
**Files:**
- Modify: `docs/compatibility_matrix.yaml` (append 2026.09 row using all rc1 versions)
- Modify: `docs/DEVELOPMENT_GUIDE.md` (Phase 4 section: storage backends, fusion plugins, replay, W&B removal)
- Modify: `docs/PHASE_DOD_TEMPLATE.md` if Phase 4 introduces new DoD items

- [ ] **Step 1: Branch + append matrix row**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-matrix-2026-09
```

In `docs/compatibility_matrix.yaml`, after the `2026.08` row:

```yaml
2026.09:
  released: 2026-04-22
  phase: phase-4-software-completion
  pet-schema: "2.4.0"
  pet-infra: "2.5.0"
  pet-data: "1.2.0"
  pet-annotation: "2.0.0"
  pet-train: "2.0.1"
  pet-eval: "2.2.0"
  pet-quantize: "2.0.1"
  pet-ota: "2.1.0"
  pet-id: "0.1.0"
  pet-demo: "1.0.1"
  rknn_toolkit2: "==2.0.0"   # carry forward (no hardware change in Phase 4)
  rkllm_toolkit: "==1.2.0"
  notes: |
    Phase 4 software-completion: OTA S3+HTTP backends, rule-based cross-modal
    fusion evaluators, ExperimentRecipe.variations launcher, pet run --replay,
    W&B physical removal (ClearML is sole experiment tracker), BSL 1.1 license.
    Hardware paths unchanged (Phase 5 will re-introduce real-device validation).
```

- [ ] **Step 2: Update DEVELOPMENT_GUIDE.md**

Add a Phase 4 section at the top of the changelog that:
1. Lists new plugin types (S3Storage, HttpStorage, S3BackendPlugin, HttpBackendPlugin, 3 fusion evaluators).
2. Documents `pet run --replay <card-id>` with the resolved-config Tier-2 contract.
3. Documents cartesian preflight thresholds (16 / 64) + `PET_ALLOW_LARGE_SWEEP=1` override.
4. Removes the W&B section (replace with a note "removed in Phase 4 — ClearML is sole tracker").
5. Adds BSL 1.1 license summary (with link to `LICENSE` and `NOTICE`).
6. Updates the matrix table to show `2026.09`.
7. Sync version table at top (pet-schema 2.4.0, pet-infra 2.5.0, etc.).

- [ ] **Step 3: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "docs(pet-infra): matrix 2026.09 + DEVELOPMENT_GUIDE Phase 4 sync (P5-A-0)"
git push -u origin feature/phase-4-matrix-2026-09
gh pr create --base dev --title "docs(pet-infra): matrix 2026.09 + DEV_GUIDE sync (P5-A-0)" \
  --body "Pins all repos to Phase 4 final versions in docs/compatibility_matrix.yaml; updates DEVELOPMENT_GUIDE with new plugin types, --replay, preflight thresholds, BSL 1.1, W&B removal note."
gh pr merge --auto --squash
```

### PR P5-A-1: pet-schema final v2.4.0 cut

**Branch:** `release/pet-schema-2.4.0` → `main`
**Repo:** `pet-schema` (after P0-A merged on dev)
**Files:**
- Modify: `pyproject.toml` (`2.4.0-rc1` → `2.4.0`)
- Modify: `CHANGELOG.md` (replace 2.4.0-rc1 heading with 2.4.0 + final date)

- [ ] **Step 1: Branch from up-to-date dev**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull --ff-only
git checkout -b release/pet-schema-2.4.0
```

- [ ] **Step 2: Bump rc → final**

In `pyproject.toml`: `2.4.0-rc1` → `2.4.0`. In CHANGELOG, rename `## 2.4.0-rc1 — 2026-04-22` to `## 2.4.0 — 2026-04-22`.

- [ ] **Step 3: PR dev→main + tag**

```bash
git add -A
git commit -m "release(pet-schema): v2.4.0 final (P5-A-1)"
git push -u origin release/pet-schema-2.4.0
# First merge release branch into dev:
gh pr create --base dev --title "release(pet-schema): v2.4.0 final (P5-A-1)" \
  --body "Final cut for Phase 4 P0-A. Removes -rc1 suffix."
gh pr merge --auto --squash
# Wait for merge into dev, then sync dev → main:
git checkout dev && git pull --ff-only
gh pr create --base main --head dev --title "release(pet-schema): v2.4.0 dev → main (P5-A-1)" \
  --body "Sync Phase 4 P0-A to main."
gh pr merge --auto --squash
git checkout main && git pull --ff-only
git tag v2.4.0 && git push origin v2.4.0
```

### PR P5-A-2: pet-infra final v2.5.0 cut

**Branch:** `release/pet-infra-2.5.0` → `main`
**Repo:** `pet-infra`
**Files:**
- Modify: `pyproject.toml` (2.5.0-rc1 → 2.5.0)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Branch + bump rc → final** (same pattern as P5-A-1)

- [ ] **Step 2: Bump pet-schema peer-dep to `>=2.4.0,<3`** (drop -rc1)

In `pyproject.toml`: `pet-schema>=2.4.0-rc1,<3` → `pet-schema>=2.4.0,<3`.

- [ ] **Step 3: PR dev→main + tag**

```bash
git add -A
git commit -m "release(pet-infra): v2.5.0 final + drop rc peer-dep (P5-A-2)"
git push -u origin release/pet-infra-2.5.0
gh pr create --base dev --title "release(pet-infra): v2.5.0 final (P5-A-2)" \
  --body "Final cut for Phase 4 W1+W3+W4+W5 (pet-infra). Drops rc suffix on pet-schema peer-dep."
gh pr merge --auto --squash
# dev → main:
git checkout dev && git pull --ff-only
gh pr create --base main --head dev --title "release(pet-infra): v2.5.0 dev → main (P5-A-2)" \
  --body "Sync Phase 4 pet-infra to main."
gh pr merge --auto --squash
git checkout main && git pull --ff-only
git tag v2.5.0 && git push origin v2.5.0
```

### PR P5-A-3: pet-ota final v2.1.0 cut

**Branch:** `release/pet-ota-2.1.0` → `main`
**Repo:** `pet-ota`
**Files:**
- Modify: `pyproject.toml` (2.1.0-rc1 → 2.1.0; peer-deps drop -rc1)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Branch + bump + drop -rc1 peer-deps**

In pyproject:
- `2.1.0-rc1` → `2.1.0`
- `pet-schema>=2.4.0-rc1,<3` → `pet-schema>=2.4.0,<3`
- `pet-infra>=2.5.0-rc1,<3` → `pet-infra>=2.5.0,<3`

- [ ] **Step 2: PR dev→main + tag** (same dual-PR pattern as P5-A-1).

```bash
git tag v2.1.0 && git push origin v2.1.0
```

### PR P5-A-4: pet-eval final v2.2.0 cut

**Branch:** `release/pet-eval-2.2.0` → `main`
**Repo:** `pet-eval`
**Files:**
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump 2.2.0-rc1 → 2.2.0 + drop -rc1 peer-deps**.

- [ ] **Step 2: PR dev→main + tag v2.2.0**.

### PR P5-A-5: pet-train final v2.0.1 cut

**Branch:** `release/pet-train-2.0.1` → `main`
**Repo:** `pet-train`
**Files:**
- Modify: `pyproject.toml` (2.0.1-rc1 → 2.0.1)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump rc → final + ensure pyproject drift no longer present** (verify pyproject is at 2.0.1-rc1 from P2-C-1, not 0.1.0).

- [ ] **Step 2: PR dev→main + tag v2.0.1**.

### PR P5-A-6: pet-quantize final v2.0.1 cut

**Branch:** `release/pet-quantize-2.0.1` → `main`
**Repo:** `pet-quantize`
**Files:**
- Modify: `pyproject.toml` (2.0.1-rc1 → 2.0.1)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump rc → final**.

- [ ] **Step 2: PR dev→main + tag v2.0.1**.

---

## Phase W7 — BSL 1.1 LICENSE (10 PRs, parallel with P5-A)

Per `project_license_bsl`: every repo gets `LICENSE` (full BSL 1.1 text + parameter block), `NOTICE` (third-party licenses where vendor/ exists), README license badge + paragraph, and `pyproject.toml` / `package.json` `license = "BUSL-1.1"`. Independent of every functional PR — can run concurrently with P5-A.

**Shared LICENSE template (used in all 10 repos):**

```
Business Source License 1.1

Parameters
----------
Licensor:             Train-Pet-Pipeline (TBD: replace with legal entity)
Licensed Work:        <repo-name>, <version> (e.g., pet-infra, 2.5.0)
Additional Use Grant: You may use the Licensed Work in non-production
                      environments (development, evaluation, academic
                      research). Production / commercial use requires a
                      separate commercial license from the Licensor.
Change Date:          2030-04-22
Change License:       Apache License, Version 2.0

[Full BSL 1.1 body — copy verbatim from https://mariadb.com/bsl11/]
```

> **Licensor placeholder note:** every PR uses literal string `"Train-Pet-Pipeline (TBD: replace with legal entity)"` as Licensor; user can do a 1-line sed across repos when the legal entity is finalized. Do not block on this.

### PR W7-1: pet-schema LICENSE + pyproject + README

**Branch:** `feature/phase-4-license-bsl-schema` → `dev`
**Repo:** `pet-schema`
**Files:**
- Create: `LICENSE` (full BSL 1.1 text)
- Modify: `pyproject.toml` (add `license = {text = "BUSL-1.1"}`)
- Modify: `README.md` (add License section + badge)

- [ ] **Step 1: Branch + write LICENSE**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-license-bsl-schema
```

Write `LICENSE` per shared template (Licensed Work: `pet-schema, 2.4.0`).

- [ ] **Step 2: Update pyproject.toml**

In `[project]` block add `license = {text = "BUSL-1.1"}`.
Remove any existing `license-file` references that point elsewhere.

- [ ] **Step 3: Update README.md**

Add at bottom:

```markdown
## License

This project is licensed under the [Business Source License 1.1](LICENSE) (BSL 1.1).
On **2030-04-22** it converts automatically to the Apache License, Version 2.0.

> Note: BSL 1.1 is **source-available**, not OSI-approved open source.
> Production / commercial use requires a separate commercial license.

![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1-blue.svg)
```

- [ ] **Step 4: Commit + PR + auto-merge**

```bash
git add LICENSE pyproject.toml README.md
git commit -m "chore(pet-schema): adopt BSL 1.1 license (W7-1)"
git push -u origin feature/phase-4-license-bsl-schema
gh pr create --base dev --title "chore(pet-schema): BSL 1.1 license (W7-1)" \
  --body "Adopts BSL 1.1 with Change Date 2030-04-22 → Apache 2.0. Phase 4 W7."
gh pr merge --auto --squash
```

### PR W7-2: pet-data LICENSE + pyproject + README

Same pattern as W7-1, repo `pet-data`, Licensed Work `pet-data, 1.2.0`. Branch `feature/phase-4-license-bsl-data`.

### PR W7-3: pet-annotation LICENSE + pyproject + README

Same pattern, repo `pet-annotation`, Licensed Work `pet-annotation, 2.0.0`. Branch `feature/phase-4-license-bsl-annotation`.

### PR W7-4: pet-train LICENSE + pyproject + NOTICE + README

**Repo:** `pet-train` (has `vendor/LLaMA-Factory` Apache 2.0 — needs NOTICE)
**Files:**
- Create: `LICENSE` (BSL 1.1)
- Create: `NOTICE`
- Modify: `pyproject.toml` (`license = {text = "BUSL-1.1"}`)
- Modify: `README.md`

`NOTICE` content:

```
Train-Pet-Pipeline / pet-train
Copyright 2026 Train-Pet-Pipeline

This product includes software developed at:

- LLaMA-Factory (vendor/LLaMA-Factory/)
  Licensed under the Apache License, Version 2.0
  https://github.com/hiyouga/LLaMA-Factory
  See vendor/LLaMA-Factory/LICENSE for full text.
```

Branch `feature/phase-4-license-bsl-train`. Same merge pattern.

### PR W7-5: pet-eval LICENSE + pyproject + NOTICE + README

**Repo:** `pet-eval` (has `vendor/lm-evaluation-harness` MIT, optionally `vendor/mmengine` Apache 2.0)

`NOTICE`:

```
Train-Pet-Pipeline / pet-eval
Copyright 2026 Train-Pet-Pipeline

This product includes software developed at:

- lm-evaluation-harness (vendor/lm-evaluation-harness/)
  Licensed under the MIT License
  https://github.com/EleutherAI/lm-evaluation-harness
  See vendor/lm-evaluation-harness/LICENSE for full text.

- mmengine (if vendored under vendor/mmengine/)
  Licensed under the Apache License, Version 2.0
  https://github.com/open-mmlab/mmengine
```

Verify vendor/ contents before generating NOTICE: `ls -la vendor/`.

Branch `feature/phase-4-license-bsl-eval`. Same merge pattern.

### PR W7-6: pet-quantize LICENSE + pyproject + README

Same as W7-1/2/3. Branch `feature/phase-4-license-bsl-quantize`. Licensed Work `pet-quantize, 2.0.1`.

### PR W7-7: pet-ota LICENSE + pyproject + README

Same. Branch `feature/phase-4-license-bsl-ota`. Licensed Work `pet-ota, 2.1.0`.

### PR W7-8: pet-infra LICENSE + pyproject + README

Same. Branch `feature/phase-4-license-bsl-infra`. Licensed Work `pet-infra, 2.5.0`.

Add a sentence to `docs/DEVELOPMENT_GUIDE.md` (already touched by P5-A-0): "All 10 repos are BSL 1.1 (source-available). See per-repo `LICENSE`. Change Date 2030-04-22 → Apache 2.0."

### PR W7-9: pet-id LICENSE + pyproject + README

Same. Branch `feature/phase-4-license-bsl-id`. Licensed Work `pet-id, 0.1.0`.

### PR W7-10: pet-demo LICENSE + license metadata (no package.json — adapt)

**Branch:** `feature/phase-4-license-bsl-demo` → `dev`
**Repo:** `pet-demo`
**Adaptation note:** spec line 485 prescribes `package.json "license": "BUSL-1.1"`, but pet-demo has **no package.json** (it is not an npm project — directory holds CLAUDE.md, README.md, configs, core, dist, docs, frontends, offline_bake, etc.). Since the spec is authoritative on intent (every repo must declare BSL in machine-readable metadata) but not on the exact file, comply via whichever metadata file pet-demo actually uses:
1. **If pet-demo/pyproject.toml exists:** add `license = {text = "BUSL-1.1"}`.
2. **Else if pet-demo/setup.py exists:** add `license="BUSL-1.1"` kwarg to `setup()`.
3. **Else (no Python packaging either):** add a top-level `LICENSE` + `LICENSE.metadata.json` containing `{"license": "BUSL-1.1", "change_date": "2030-04-22", "change_license": "Apache-2.0"}` so downstream tooling (and W7 audit script) can detect license declaratively.

**Files (Option 3 default — verify in Step 1):**
- Create: `LICENSE` (BSL 1.1, Licensed Work `pet-demo, 1.0.1`)
- Create: `LICENSE.metadata.json` (only if Option 3)
- Modify: `README.md`
- Modify: `pyproject.toml` if it exists (Option 1)

- [ ] **Step 1: Detect packaging mode**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-demo
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-license-bsl-demo
ls pyproject.toml setup.py package.json 2>/dev/null || echo "no python/npm packaging"
```

- [ ] **Step 2: Apply LICENSE + matching metadata strategy** (1, 2, or 3 above).

- [ ] **Step 3: Commit + PR + auto-merge**

```bash
git add -A
git commit -m "chore(pet-demo): adopt BSL 1.1 license (W7-10)"
git push -u origin feature/phase-4-license-bsl-demo
gh pr create --base dev --title "chore(pet-demo): BSL 1.1 license (W7-10)" \
  --body "Adopts BSL 1.1. pet-demo has no package.json so license is declared via $(detected mode). Phase 4 W7."
gh pr merge --auto --squash
```

**W7 final audit (run after all 10 W7 PRs merged):**

```bash
for repo in pet-schema pet-data pet-annotation pet-train pet-eval \
            pet-quantize pet-ota pet-infra pet-id pet-demo; do
  echo "=== $repo ==="
  test -f /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo/LICENSE \
    && grep -q "Business Source License 1.1" /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo/LICENSE \
    && echo OK || echo MISSING
done
```
Expected: 10×`OK`.

---

## Phase 6 — Retrospective + DoD self-check (1 PR)

### PR P6-A: Phase 4 retrospective + North Star §0.2.1 four-dim DoD

**Branch:** `feature/phase-4-retrospective` → `dev → main`
**Repo:** `pet-infra`
**Files:**
- Create: `docs/superpowers/retrospectives/2026-04-22-phase-4-retrospective.md`
- Modify: `docs/PHASE_DOD_TEMPLATE.md` if any DoD item changed during Phase 4

- [ ] **Step 1: Branch + write retrospective skeleton**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull --ff-only
git checkout -b feature/phase-4-retrospective
```

Create `docs/superpowers/retrospectives/2026-04-22-phase-4-retrospective.md`:

```markdown
# Phase 4 Software-Completion Retrospective — 2026-04-22

## §1 — What Shipped
- 38 PRs across 7 sub-phases (P0 / P1 / P2-A / P2-B / P2-C / P5-A / W7 / P6)
- 7 repos touched (pet-schema, pet-infra, pet-ota, pet-eval, pet-train, pet-quantize, pet-demo)
- 4 repos license-only touch (pet-data, pet-annotation, pet-id, pet-demo) + 6 functional + license

## §2 — Final version table
| Repo            | Before  | After   | Change     |
|-----------------|---------|---------|------------|
| pet-schema      | 2.3.1   | 2.4.0   | minor      |
| pet-infra       | 2.4.0   | 2.5.0   | minor      |
| pet-ota         | 2.0.0   | 2.1.0   | minor      |
| pet-eval        | 2.1.0   | 2.2.0   | minor      |
| pet-train       | 2.0.0-rc1 (drift to 0.1.0 in pyproject) | 2.0.1 | patch + drift fix |
| pet-quantize    | 2.0.0   | 2.0.1   | patch      |
| pet-data        | 1.2.0   | 1.2.0   | license-only |
| pet-annotation  | 2.0.0   | 2.0.0   | license-only |
| pet-id          | 0.1.0   | 0.1.0   | license-only |
| pet-demo        | 1.0.1   | 1.0.1   | license-only |
| matrix          | 2026.08 | 2026.09 | Phase 4 row |

## §3 — North Star §0.2.1 Four-Dimension DoD
For each dimension score 1–5 (target ≥3, <3 = rework):

### Pluggability (target ≥3)
- New plugin types: S3Storage, HttpStorage (W1) / S3BackendPlugin, HttpBackendPlugin (W1) / 3 fusion evaluators (W2)
- All registered via `mmengine.Registry` with `force=True`
- Score: ___ / 5  (justify with concrete observations)

### Flexibility (target ≥3)
- `ExperimentRecipe.variations` cartesian + `link_to` co-iteration
- 3 OTA backends (local/s3/http) usable interchangeably
- 3 fusion strategies switchable via recipe variation axis
- Score: ___ / 5

### Extensibility (target ≥3)
- Adding a 4th storage / OTA / fusion plugin = new file + register decorator only (no core edits)
- `pet run --replay` is plugin-agnostic
- Score: ___ / 5

### Comparability (target ≥3)
- ClearML per-variation tag injection enables side-by-side runs
- `resolved_config_uri` + `pet run --replay` make every prior run rerunnable bit-identically
- Cartesian preflight forces conscious sweep sizing
- Score: ___ / 5

> If any dim < 3 → open rework PR before declaring Phase 4 complete.

## §4 — Drift / Decisions Made During Execution
| When | Decision | Why | NS dim it serves |
|------|----------|-----|------------------|
| (fill in as PRs land) | | | |

## §5 — Hardware Items Deferred to Phase 5
- `pet validate --hardware` non-dry-run path
- Real RK3576 OTA flash + rollback
- Real GPU smoke runner + `smoke_small` GPU path
- Real-device latency on cross-modal fusion
- Trigger condition: hardware (RK3576 board + runner) procured.

## §6 — License Adoption Summary
- All 10 repos now BSL 1.1 (source-available; not OSI open source)
- Change Date 2030-04-22 → Apache 2.0
- Licensor field still `Train-Pet-Pipeline (TBD: replace with legal entity)` — user to finalize
- vendor/ subdirs preserve upstream LICENSEs; NOTICE files in pet-train + pet-eval

## §7 — Followups for Phase 5
1. Procure RK3576 hardware + runner setup
2. Re-enable `pet validate --hardware` non-dry-run path
3. Real OTA gray-release one matrix release
4. Re-evaluate learned fusion if business need emerges (per feedback_no_learned_fusion)
5. Finalize BSL Licensor legal entity name + 1-line sed across 10 repos
```

- [ ] **Step 2: Fill DoD scores honestly**

After all functional PRs merged, return to this file and fill in §3 scores with concrete observations from PRs (e.g. "P1-A added S3Storage in 1 file with 1 register call → Pluggability 5"). If any dim < 3, open rework PR before merging this retrospective.

- [ ] **Step 3: Fill §4 Drift table**

For each significant decision made during execution (e.g. "P2-A-2 used moto instead of LocalStack docker because moto integrates faster with pytest"), record: when, what, why, which NS dim it serves.

- [ ] **Step 4: Commit + PR dev→main + merge**

```bash
git add docs/superpowers/retrospectives/2026-04-22-phase-4-retrospective.md
git commit -m "docs: Phase 4 retrospective + DoD self-check (P6-A)"
git push -u origin feature/phase-4-retrospective
gh pr create --base dev --title "docs: Phase 4 retrospective + DoD (P6-A)" \
  --body "Phase 4 software-completion retrospective with North Star §0.2.1 four-dim DoD self-check, version table, drift log, Phase 5 followups."
gh pr merge --auto --squash
# Then dev → main sync:
git checkout dev && git pull --ff-only
gh pr create --base main --head dev --title "release: dev → main Phase 4 retrospective (P6-A)" \
  --body "Sync Phase 4 retrospective to main."
gh pr merge --auto --squash
```

- [ ] **Step 5: STOP**

Per `feedback_phase3_autonomy` rule "Phase 完成后停" — do **not** auto-start Phase 5. Wait for user to trigger Phase 5 brainstorming/spec/plan flow when hardware is ready.

---

## Plan Summary

| Sub-phase | Repo(s)       | PRs | Workstream(s)        | Depends on  |
|-----------|---------------|-----|----------------------|-------------|
| P0        | pet-schema    | 1   | W4 (replay schema)   | —           |
| P1        | pet-infra     | 7   | W1+W3+W4+W5          | P0          |
| P2-A      | pet-ota       | 5   | W1                   | P0+P1       |
| P2-B      | pet-eval      | 5   | W2+W5                | P0+P1       |
| P2-C      | pet-train + pet-quantize | 2 | W5                   | —           |
| P5-A      | all           | 7   | W6 (matrix + tags)   | P1+P2-A+P2-B+P2-C |
| W7        | all 10 repos  | 10  | W7 (BSL 1.1)         | — (parallel)|
| P6        | pet-infra     | 1   | retrospective        | all above   |
| **Total** |               | **38** |                  |             |

**End-to-end timing target:** matches Phase 3B template (~1 day with subagent-driven-development + auto-merge).

**Decision authority during execution:** per `feedback_phase3_autonomy` — no sub-phase checkpoint requires user approval; only true blockers (plan↔spec conflict, architecture fork, destructive-op scope unclear, external-resource limit) escalate. Decisions logged into retrospective §4 drift table.

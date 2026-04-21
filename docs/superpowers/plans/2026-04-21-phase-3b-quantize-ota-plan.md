# Phase 3B — pet-quantize + pet-ota Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Destructive rebuild of pet-quantize (v2.0.0) and pet-ota (v2.0.0) onto Phase 3A plugin architecture; pet-infra v2.4.0 closes Flexibility/Extensibility 4/5 debts (Hydra defaults-list + multi-axis multirun); pet-schema 2.2.0 adds `HardwareValidation`; pet-eval 2.1.0 adds `QuantizedVlmEvaluator` with 6-step peer-dep CI; `compatibility_matrix.yaml` appends row 2026.08.

**Architecture:** Strict linear 5-repo PR chain anchored by rc tags, following Phase 3A's 24-PR pattern: pet-schema 2.2.0 → pet-infra 2.4.0-rc1 → pet-quantize 2.0.0-rc1 → pet-eval 2.1.0-rc1 → pet-ota 2.0.0-rc1 → matrix 2026.08 finalize + final tags → retrospective. All plugins register via `pet_infra.plugins` entry-point group; SDK dependencies (rknn-toolkit2, rkllm-toolkit) guarded conditional with `PET_ALLOW_MISSING_SDK` for PR CI.

**Tech Stack:** Python 3.11 / mmengine-lite Registry / Hydra (+zen) / Pydantic v2 / pytest / rknn-toolkit2 2.0.0 / rkllm-toolkit 1.2.0 / bsdiff4 / GitHub Actions.

**Spec:** `pet-infra/docs/superpowers/specs/2026-04-21-phase-3b-quantize-ota-design.md` (two review passes approved).

**North Star constraint (§0.2.1):** Pluggability / Flexibility / Extensibility / Comparability, each ≥ 3/5. Phase 3B commits to Flexibility ≥ 5/5 and Extensibility ≥ 5/5 (debts closed per Q5 option A).

**Hard constraints:**
- `feedback_refactor_no_legacy` — destructive; no compat layer; major bump for pet-quantize + pet-ota
- `feedback_pr_workflow` — every repo `feature/* → dev → main`
- `feedback_env_naming` — shared `pet-pipeline` conda env
- `feedback_no_hardcode` — all numerics from `pet-infra/params.yaml` (spec §4.2)
- `feedback_no_manual_workaround` — fix SDK integration errors at root, no bypass
- CLAUDE.md — latency tests only on real RK3576 (manual gate)

**Repository working directories (each a separate git repo):**
- pet-schema:   `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema`
- pet-infra:    `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
- pet-quantize: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize`
- pet-eval:     `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval`
- pet-ota:      `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-ota`

Per-PR workflow: checkout `dev` → cut `feature/*` → TDD → PR target `dev` → after merge, promote `dev → main` at phase boundaries → tag.

---

## Global PR Dependency Graph (24 PRs — frozen)

```
Phase 0: pet-schema v2.2.0 (unblocks HardwareValidation for all downstream)
    #P0-A  HardwareValidation + tests + release
    ==> dev → main → tag v2.2.0

Phase 1: pet-infra v2.4.0-rc1 (6 PRs, depends P0)
    #P1-A  compose.py Hydra defaults-list
    #P1-B  launcher.py multi-axis multirun
    #P1-C  orchestrator/hooks.py (Converter + Dataset + Ota stage runners)
    #P1-D  recipes defaults fragments + smoke_{tiny,mps,small} rewrite
    #P1-E  params.yaml namespaces + pet validate --hardware CLI skeleton
    #P1-F  matrix 2026.08-rc + §11.4 装序 + dev→main release v2.4.0-rc1
    ==> dev → main → tag v2.4.0-rc1

Phase 2: pet-quantize v2.0.0-rc1 (8 PRs, depends P1)
    #P2-A  audit + delete v1 (cli, config 三元组, wandb, legacy pipeline orch)
    #P2-B  plugins/ skeleton + _register + NoopConverter
    #P2-C  VlmRkllmW4A16Converter
    #P2-D  VisionRknnFp16Converter
    #P2-E  AudioRknnFp16Converter
    #P2-F  3 calibration DATASETS plugins
    #P2-G  peer-dep CI 4-step + peer-dep-smoke workflow
    #P2-H  dev→main release v2.0.0-rc1
    ==> tag v2.0.0-rc1

Phase 3: pet-eval v2.1.0-rc1 (3 PRs, depends P2)
    #P3-A  QuantizedVlmEvaluator plugin + tests + lazy-import mock
    #P3-B  peer-dep CI 6-step update (insert pet-quantize) + peer-dep-smoke update
    #P3-C  dev→main release v2.1.0-rc1
    ==> tag v2.1.0-rc1

Phase 4: pet-ota v2.0.0-rc1 (4 PRs, depends P0+P1)
    #P4-A  audit + delete v1 (cli, wandb, legacy orch)
    #P4-B  plugins/ skeleton + _register
    #P4-C  LocalBackendPlugin (Manifest from ModelCard + gate guard)
    #P4-D  dev→main release v2.0.0-rc1
    ==> tag v2.0.0-rc1

Phase 5: matrix 2026.08 finalize (1 PR, pet-infra)
    #P5-A  compatibility_matrix.yaml drop -rc1 for all 5 repos + add rknn/rkllm pins
    ==> dev → main → tag v2.4.0 final
         Then choreograph final tags on other 4 repos:
           pet-quantize: tag v2.0.0 (same commit as v2.0.0-rc1)
           pet-eval:     tag v2.1.0 (same commit as v2.1.0-rc1)
           pet-ota:      tag v2.0.0 (same commit as v2.0.0-rc1)
           pet-schema already at v2.2.0 from P0

Phase 6: retrospective (1 PR, pet-infra)
    #P6-A  docs/retrospectives/2026-MM-DD-phase-3b.md with DoD §0.2.1 self-check
    ==> dev → main
```

**Total: 1 + 6 + 8 + 3 + 4 + 1 + 1 = 24 PRs.**

---

## Cross-PR preflight (5-second check at start of every PR)

```bash
conda env list | grep -q 'pet-pipeline' || { echo "need: conda create -n pet-pipeline python=3.11"; exit 1; }
conda activate pet-pipeline
cd <repo-dir>
git status  # must be clean
git checkout dev && git pull origin dev
```

---

## Defaults-list fragment layout (for #6 advisory, scope: pet-infra only)

All recipe defaults fragments live under `pet-infra/recipes/` in a flat-ish namespace structure mirroring `component_registry` names. Created by #P1-D.

```
pet-infra/recipes/
├── _base/
│   └── smoke_base.yaml              # common scaffolding: recipe_id prefix, default_storage, produces stub
├── trainer/
│   ├── llamafactory_sft.yaml        # wraps configs/smoke/{tiny,mps,small}_train.yaml selection
│   ├── llamafactory_dpo.yaml
│   └── tiny_test.yaml
├── evaluator/
│   ├── vlm_evaluator.yaml
│   └── quantized_vlm_evaluator.yaml
├── converter/
│   ├── vlm_rkllm_w4a16.yaml
│   ├── vision_rknn_fp16.yaml
│   ├── audio_rknn_fp16.yaml
│   └── noop_converter.yaml
├── dataset/
│   ├── vlm_calibration_subset.yaml
│   ├── vision_calibration_subset.yaml
│   └── audio_calibration_subset.yaml
├── ota/
│   └── local_backend.yaml
├── smoke_tiny.yaml                  # composed from _base + fragments (short: defaults + 5-10 overrides)
├── smoke_mps.yaml                   # "
├── smoke_small.yaml                 # "
└── release.yaml                     # pinned to smoke_small contents, recipe_id=release
```

Each fragment `component/type.yaml` is a minimal RecipeStage template:

```yaml
# recipes/trainer/llamafactory_sft.yaml (fragment example)
# @package _global_
stages:
  train:
    component_registry: trainers
    component_type: llamafactory_sft
    config_path: configs/smoke/${_target_smoke_tier_}_train.yaml
    depends_on: []
```

`_target_smoke_tier_` is set per tier in the top-level recipe (tiny/mps/small). `@package _global_` lets the fragment merge into the top-level recipe tree.

---

# Phase 0: pet-schema v2.2.0 (1 PR)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema`
**Target branch per PR:** `dev`
**Final tag:** `v2.2.0` (after `dev → main` merge)

---

## PR #P0-A: HardwareValidation model + release

**Branch:** `feature/phase-3b-hardware-validation`

### Task P0-A.1: commit plan + spec pointers

**Files:**
- Modify: `pet-infra/docs/superpowers/plans/2026-04-21-phase-3b-quantize-ota-plan.md` (this file)
- Modify: `pet-infra/docs/superpowers/specs/2026-04-21-phase-3b-quantize-ota-design.md` (already committed on `feature/phase-3b-spec`)

- [ ] **Step 1: Confirm spec branch state**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git log --oneline feature/phase-3b-spec -5
```

Expected: 2 commits (initial spec + 3-fix revision).

- [ ] **Step 2: Add plan to spec branch**

```bash
git checkout feature/phase-3b-spec
git add docs/superpowers/plans/2026-04-21-phase-3b-quantize-ota-plan.md
git commit -m "docs: Phase 3B implementation plan (24 PRs frozen)"
```

- [ ] **Step 3: Push + open PR (pet-infra)**

```bash
git push -u origin feature/phase-3b-spec
gh pr create --base dev --title "docs: Phase 3B spec + plan (pet-quantize + pet-ota rebuild)" --body "$(cat <<'EOF'
## Summary
- Spec approved by spec-document-reviewer (2 passes)
- Plan freezes 24 PRs across 5 repos (schema/infra/quantize/eval/ota)
- Phase 3B commits to Flexibility + Extensibility ≥ 5/5

## Test plan
- [ ] Spec + plan readable via GitHub preview
- [ ] No other pet-infra code changes in this PR
EOF
)"
```

- [ ] **Step 4: Merge PR after CI green**

Expected: CI is no-op (docs-only PR); merge.

### Task P0-A.2: pet-schema HardwareValidation model

**Files:**
- Modify: `pet-schema/src/pet_schema/model_card.py`
- Create: `pet-schema/tests/test_hardware_validation.py`

- [ ] **Step 1: Cut feature branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-hardware-validation
```

- [ ] **Step 2: Write failing test**

Create `tests/test_hardware_validation.py`:

```python
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from pet_schema.model_card import HardwareValidation, ModelCard

def _base_card_kwargs():
    return dict(
        card_id="test-123",
        modality="vision",
        checkpoint_uri="/tmp/x",
        schema_version="2.2.0",
    )

def test_validated_by_github_actions_format_accepted():
    hv = HardwareValidation(
        device_id="rk3576-dev-01",
        firmware_version="1.2.3",
        validated_at=datetime.now(timezone.utc),
        latency_ms_p50=42.0,
        latency_ms_p95=88.0,
        validated_by="github-actions:1234567890",
    )
    assert hv.validated_by.startswith("github-actions:")

def test_validated_by_operator_format_accepted():
    hv = HardwareValidation(
        device_id="rk3576-dev-01",
        firmware_version="1.2.3",
        validated_at=datetime.now(timezone.utc),
        latency_ms_p50=42.0,
        latency_ms_p95=88.0,
        validated_by="operator:alice-smith.2",
    )
    assert hv.validated_by.startswith("operator:")

def test_validated_by_invalid_prefix_rejected():
    with pytest.raises(ValidationError):
        HardwareValidation(
            device_id="rk3576-dev-01",
            firmware_version="1.2.3",
            validated_at=datetime.now(timezone.utc),
            latency_ms_p50=42.0,
            latency_ms_p95=88.0,
            validated_by="random-person",
        )

def test_validated_by_empty_suffix_rejected():
    with pytest.raises(ValidationError):
        HardwareValidation(
            device_id="rk3576-dev-01",
            firmware_version="1.2.3",
            validated_at=datetime.now(timezone.utc),
            latency_ms_p50=42.0,
            latency_ms_p95=88.0,
            validated_by="operator:",
        )

def test_model_card_hardware_validation_defaults_none():
    card = ModelCard(**_base_card_kwargs())
    assert card.hardware_validation is None

def test_model_card_hardware_validation_roundtrip():
    hv = HardwareValidation(
        device_id="rk3576-dev-01",
        firmware_version="1.2.3",
        validated_at=datetime.now(timezone.utc),
        latency_ms_p50=42.0,
        latency_ms_p95=88.0,
        accuracy=0.91,
        kl_divergence=0.05,
        validated_by="operator:alice",
        notes="smoke-only run",
    )
    card = ModelCard(**_base_card_kwargs(), hardware_validation=hv)
    dumped = card.model_dump(mode="json")
    assert dumped["hardware_validation"]["validated_by"] == "operator:alice"
    reloaded = ModelCard.model_validate(dumped)
    assert reloaded.hardware_validation is not None
    assert reloaded.hardware_validation.latency_ms_p95 == 88.0

def test_forward_compat_schema_21_card_loads_under_22():
    """A ModelCard without hardware_validation (schema 2.1.0 shape) loads fine."""
    old_card_json = {
        **_base_card_kwargs(),
        "schema_version": "2.1.0",
    }
    card = ModelCard.model_validate(old_card_json)
    assert card.hardware_validation is None
```

- [ ] **Step 3: Run test to see failure**

```bash
pytest tests/test_hardware_validation.py -v
```

Expected: FAIL (HardwareValidation does not exist yet).

- [ ] **Step 4: Implement HardwareValidation**

Add to `src/pet_schema/model_card.py` (append above `class ModelCard`):

```python
import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

_VALIDATED_BY_PATTERN = re.compile(r"^(github-actions|operator):[A-Za-z0-9_.\-]+$")


class HardwareValidation(BaseModel):
    """Result of a manual real-hardware validation run, written back to ModelCard.

    Provenance is encoded in `validated_by`:
    - github-actions:<workflow_run_id> when written by automation
    - operator:<github_username>       when written by a human release manager
    """
    device_id: str
    firmware_version: str
    validated_at: datetime
    latency_ms_p50: float
    latency_ms_p95: float
    accuracy: Optional[float] = None
    kl_divergence: Optional[float] = None
    validated_by: str
    notes: Optional[str] = None

    @field_validator("validated_by")
    @classmethod
    def _check_validated_by(cls, v: str) -> str:
        if not _VALIDATED_BY_PATTERN.fullmatch(v):
            raise ValueError(
                "validated_by must match ^(github-actions|operator):[A-Za-z0-9_.\\-]+$"
            )
        return v
```

Add field to `ModelCard`:

```python
class ModelCard(BaseModel):
    # ... existing fields ...
    hardware_validation: Optional[HardwareValidation] = None
```

- [ ] **Step 5: Run test to see pass**

```bash
pytest tests/test_hardware_validation.py -v
```

Expected: PASS (7 tests).

- [ ] **Step 6: Run full pet-schema test suite**

```bash
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```

Expected: all green; pre-existing ModelCard roundtrip tests continue to pass (forward-compat).

- [ ] **Step 7: Bump version + commit**

Edit `pet-schema/src/pet_schema/__init__.py` (or `pyproject.toml` depending on source-of-truth) to bump version `2.1.0` → `2.2.0`:

```bash
# find version location
grep -r '"2.1.0"' src/ pyproject.toml
# edit to 2.2.0
```

```bash
git add src/pet_schema/model_card.py tests/test_hardware_validation.py src/pet_schema/__init__.py pyproject.toml
git commit -m "feat(pet-schema): v2.2.0 add HardwareValidation model

ModelCard.hardware_validation: Optional[HardwareValidation] = None.
validated_by enforces regex ^(github-actions|operator):[A-Za-z0-9_.\\-]+$
to distinguish automated vs human-operator provenance at audit time.

Forward-compat: schema 2.1.0 cards load under 2.2.0 unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 8: Push + open PR (target dev)**

```bash
git push -u origin feature/phase-3b-hardware-validation
gh pr create --base dev --title "feat(pet-schema): v2.2.0 add HardwareValidation" --body "$(cat <<'EOF'
## Summary
- Adds `HardwareValidation` Pydantic model with regex-enforced `validated_by`
- Adds `ModelCard.hardware_validation: Optional[HardwareValidation] = None`
- Forward-compat: 2.1.0 cards load unchanged under 2.2.0

## Test plan
- [ ] 7 new unit tests pass
- [ ] Existing ModelCard tests continue to pass
- [ ] ruff + mypy green
EOF
)"
```

**Reviewers required (pet-schema): 2 approves (CLAUDE.md §PR Review).**

- [ ] **Step 9: After 2 approves + CI green, merge PR**

```bash
gh pr merge --merge
```

### Task P0-A.3: dev → main + tag v2.2.0

- [ ] **Step 1: Open release PR**

```bash
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-schema v2.2.0 (Phase 3B P0)" --body "HardwareValidation model for manual RK3576 gate."
```

- [ ] **Step 2: Merge + tag**

```bash
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.2.0
git push origin v2.2.0
```

- [ ] **Step 3: Verify tag**

```bash
gh release create v2.2.0 --title "pet-schema v2.2.0 — Phase 3B HardwareValidation" --notes "Adds ModelCard.hardware_validation field; forward-compat with 2.1.0."
```

---

# Phase 1: pet-infra v2.4.0-rc1 (6 PRs)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**Target branch per PR:** `dev`
**Final rc tag:** `v2.4.0-rc1`

---

## PR #P1-A: compose.py Hydra defaults-list support

**Branch:** `feature/phase-3b-compose-defaults`

**Files:**
- Modify: `pet-infra/src/pet_infra/compose.py`
- Create: `pet-infra/tests/test_compose_defaults_list.py`
- Create: `pet-infra/tests/test_compose_backward_compat.py`
- Create: `pet-infra/tests/fixtures/compose/` (yaml fixtures for testing)

### Task P1-A.1: failing tests for defaults-list parsing

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-compose-defaults
```

- [ ] **Step 2: Create fixture yamls**

`tests/fixtures/compose/single_base.yaml`:
```yaml
defaults:
  - base_a
recipe_id: test_single
```

`tests/fixtures/compose/base_a.yaml`:
```yaml
owner_repo: test-owner
description: base-a description
```

`tests/fixtures/compose/nested.yaml`:
```yaml
defaults:
  - base_a
  - sub/override
recipe_id: test_nested
description: overridden
```

`tests/fixtures/compose/sub/override.yaml`:
```yaml
owner_repo: overridden-owner
```

`tests/fixtures/compose/circular.yaml`:
```yaml
defaults:
  - loop_b
recipe_id: circular
```

`tests/fixtures/compose/loop_b.yaml`:
```yaml
defaults:
  - circular
```

`tests/fixtures/compose/legacy_no_defaults.yaml`:
```yaml
recipe_id: legacy
description: no defaults key used
owner_repo: legacy-owner
schema_version: "0.1"
stages: []
variations: []
produces: []
default_storage: local
required_plugins: {}
```

- [ ] **Step 3: Write failing test**

`tests/test_compose_defaults_list.py`:

```python
from pathlib import Path
import pytest
from pet_infra.compose import compose_recipe, ComposeError

FIXTURES = Path(__file__).parent / "fixtures" / "compose"

def test_single_base_defaults_merged():
    recipe = compose_recipe(FIXTURES / "single_base.yaml")
    assert recipe.recipe_id == "test_single"
    assert recipe.owner_repo == "test-owner"
    assert recipe.description == "base-a description"

def test_nested_defaults_later_wins():
    recipe = compose_recipe(FIXTURES / "nested.yaml")
    assert recipe.owner_repo == "overridden-owner"
    assert recipe.description == "overridden"  # top-level override wins

def test_circular_defaults_raises():
    with pytest.raises(ComposeError, match="circular"):
        compose_recipe(FIXTURES / "circular.yaml")

def test_missing_defaults_target_raises():
    missing = FIXTURES / "missing_target.yaml"
    missing.write_text("defaults:\n  - does_not_exist\nrecipe_id: x\n")
    try:
        with pytest.raises(ComposeError, match="not found"):
            compose_recipe(missing)
    finally:
        missing.unlink()
```

- [ ] **Step 4: Write backward-compat test**

`tests/test_compose_backward_compat.py`:

```python
from pathlib import Path
from pet_infra.compose import compose_recipe

FIXTURES = Path(__file__).parent / "fixtures" / "compose"

def test_recipe_without_defaults_still_works():
    recipe = compose_recipe(FIXTURES / "legacy_no_defaults.yaml")
    assert recipe.recipe_id == "legacy"
    assert recipe.owner_repo == "legacy-owner"

def test_phase_3a_standalone_smoke_recipes_parse():
    """After P1-D rewrites these to use defaults:, the rewrite itself covers
    this test. This placeholder asserts that TODAY's smoke_tiny.yaml still
    composes via the legacy path (no defaults: key)."""
    recipe_path = Path(__file__).parent.parent / "recipes" / "smoke_tiny.yaml"
    if recipe_path.exists():
        recipe = compose_recipe(recipe_path)
        assert recipe.recipe_id == "smoke_tiny"
```

- [ ] **Step 5: Run tests — expect fail**

```bash
pytest tests/test_compose_defaults_list.py tests/test_compose_backward_compat.py -v
```

Expected: FAIL (ComposeError class missing, defaults-list unrecognized).

### Task P1-A.2: implement defaults-list resolver

- [ ] **Step 1: Read current compose.py**

```bash
cat src/pet_infra/compose.py
```

- [ ] **Step 2: Patch compose.py with defaults-list resolution**

Prepend near top:

```python
class ComposeError(Exception):
    """Raised when recipe composition fails."""
```

Add function (place before `compose_recipe`):

```python
from omegaconf import OmegaConf, DictConfig
from pathlib import Path

def _resolve_defaults(recipe_path: Path, visited: set[Path] | None = None) -> DictConfig:
    """Recursively resolve `defaults:` list relative to recipe_path.parent.

    Later entries override earlier; top-level file overrides all defaults.
    Circular chains raise ComposeError.
    """
    if visited is None:
        visited = set()
    recipe_path = recipe_path.resolve()
    if recipe_path in visited:
        raise ComposeError(f"circular defaults chain through {recipe_path}")
    visited = visited | {recipe_path}
    if not recipe_path.exists():
        raise ComposeError(f"defaults target not found: {recipe_path}")
    raw = OmegaConf.load(recipe_path)
    defaults_list = raw.pop("defaults", []) if isinstance(raw, DictConfig) else []
    merged = OmegaConf.create({})
    base_dir = recipe_path.parent
    for entry in defaults_list:
        if not isinstance(entry, str):
            raise ComposeError(f"defaults entries must be strings, got {entry!r}")
        # resolve relative to recipe dir; add .yaml if absent
        target = base_dir / (entry if entry.endswith(".yaml") else f"{entry}.yaml")
        sub = _resolve_defaults(target, visited)
        merged = OmegaConf.merge(merged, sub)
    merged = OmegaConf.merge(merged, raw)
    return merged
```

Modify `compose_recipe` to call `_resolve_defaults` before existing OmegaConf validation:

```python
def compose_recipe(recipe_path: Path) -> ExperimentRecipe:
    cfg = _resolve_defaults(Path(recipe_path))
    # ... rest of existing logic that converts DictConfig → ExperimentRecipe
```

- [ ] **Step 3: Run tests — expect pass**

```bash
pytest tests/test_compose_defaults_list.py tests/test_compose_backward_compat.py -v
```

Expected: PASS (6 tests).

- [ ] **Step 4: Run full pet-infra test suite**

```bash
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```

Expected: all green; no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/compose.py tests/test_compose_defaults_list.py \
        tests/test_compose_backward_compat.py tests/fixtures/compose/
git commit -m "feat(pet-infra): Hydra defaults-list in compose.py (Flexibility 4→5)

Resolves 'defaults: [base_a, sub/override]' relative to recipe dir before
OmegaConf override merge. Circular chains raise ComposeError. Legacy
recipes without a 'defaults' key continue to work unchanged
(backward-compat test asserts this).

Closes Phase 3A Flexibility 4/5 debt.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-compose-defaults
```

- [ ] **Step 6: Open + merge PR**

```bash
gh pr create --base dev --title "feat(pet-infra): Hydra defaults-list in compose.py" --body "Closes Flexibility 4/5 debt. Forward-compat with Phase 3A standalone recipes."
# after CI green + 1 approve:
gh pr merge --merge
```

---

## PR #P1-B: launcher.py multi-axis multirun

**Branch:** `feature/phase-3b-multirun`

**Files:**
- Modify: `pet-infra/src/pet_infra/launcher.py`
- Create: `pet-infra/tests/test_launcher_multirun.py`

### Task P1-B.1: failing tests for sweep

- [ ] **Step 1: Branch + write tests**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-multirun
```

`tests/test_launcher_multirun.py`:

```python
import json
from pathlib import Path
import pytest
from pet_infra.launcher import launch_multirun, SweepResult

def test_cartesian_product_2x2_yields_4_runs(tmp_path, monkeypatch):
    """Given 2 values on each of 2 axes, launcher dispatches 4 runs."""
    dispatched: list[dict] = []

    def fake_run_single(recipe_path, overrides, out_dir):
        dispatched.append(overrides)
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text("recipe_id: sweep_test\nstages: []\n")
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a", "b"], "device": ["cpu", "mps"]},
        results_root=tmp_path / "out",
    )
    assert len(results) == 4
    axis_pairs = {(r["overrides"]["trainer"], r["overrides"]["device"]) for r in results}
    assert axis_pairs == {("a", "cpu"), ("a", "mps"), ("b", "cpu"), ("b", "mps")}

def test_failed_axis_does_not_block_siblings(tmp_path, monkeypatch):
    def fake_run_single(recipe_path, overrides, out_dir):
        if overrides.get("trainer") == "broken":
            raise RuntimeError("boom")
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text("recipe_id: sweep_test\nstages: []\n")
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["good", "broken"]},
        results_root=tmp_path / "out",
    )
    statuses = {r["overrides"]["trainer"]: r["status"] for r in results}
    assert statuses["good"] == "ok"
    assert statuses["broken"] == "failed"

def test_sweep_summary_json_written(tmp_path, monkeypatch):
    def fake_run_single(recipe_path, overrides, out_dir):
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text("recipe_id: sweep_test\nstages: []\n")
    out_root = tmp_path / "out"
    launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a"]},
        results_root=out_root,
    )
    summary = json.loads((out_root / "sweep_test" / "sweep_summary.json").read_text())
    assert summary["recipe_id"] == "sweep_test"
    assert len(summary["runs"]) == 1

def test_single_axis_single_value_one_run(tmp_path, monkeypatch):
    def fake_run_single(recipe_path, overrides, out_dir):
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text("recipe_id: sweep_test\nstages: []\n")
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a"]},
        results_root=tmp_path / "out",
    )
    assert len(results) == 1
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_launcher_multirun.py -v
```

Expected: FAIL (launch_multirun missing).

### Task P1-B.2: implement launch_multirun

- [ ] **Step 1: Patch launcher.py**

Append to `src/pet_infra/launcher.py`:

```python
import hashlib
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypedDict


class SweepResult(TypedDict):
    overrides: dict[str, Any]
    card_path: Path
    status: str  # 'ok' | 'failed'
    error: str | None


def _sweep_hash(overrides: dict) -> str:
    payload = json.dumps(overrides, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def _run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
    """Executes one ExperimentRecipe instance. Extracted so tests can monkeypatch."""
    from pet_infra.orchestrator.runner import run_recipe  # lazy import
    out_dir.mkdir(parents=True, exist_ok=True)
    card_path = run_recipe(recipe_path, overrides=overrides, out_dir=out_dir)
    return {"card_path": card_path, "status": "ok", "overrides": overrides}


def launch_multirun(
    recipe_path: Path,
    sweep_params: dict[str, list],
    results_root: Path | None = None,
    max_workers: int | None = None,
) -> list[SweepResult]:
    """Run cartesian product of sweep_params as parallel ExperimentRecipe instances.

    Example: sweep_params={'trainer':['a','b'], 'device':['cpu','mps']} → 4 runs.
    Failed axes do not block siblings; each appears with status='failed'.
    sweep_summary.json aggregates all results under
    results_root/<recipe_id>/sweep_summary.json.
    """
    from pet_infra.compose import compose_recipe
    recipe = compose_recipe(recipe_path)
    recipe_id = recipe.recipe_id
    results_root = results_root or Path("results")
    sweep_dir = results_root / recipe_id
    sweep_dir.mkdir(parents=True, exist_ok=True)

    keys = list(sweep_params.keys())
    combos = list(itertools.product(*(sweep_params[k] for k in keys)))
    if not combos:
        combos = [tuple()]
    overrides_list = [dict(zip(keys, combo)) for combo in combos]

    max_workers = max_workers or min(len(overrides_list), os.cpu_count() or 1)
    results: list[SweepResult] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        future_to_ov = {}
        for ov in overrides_list:
            out_dir = sweep_dir / _sweep_hash(ov)
            future = pool.submit(_run_single, recipe_path, ov, out_dir)
            future_to_ov[future] = (ov, out_dir)

        for future in as_completed(future_to_ov):
            ov, out_dir = future_to_ov[future]
            try:
                outcome = future.result()
                results.append(
                    SweepResult(overrides=ov, card_path=outcome["card_path"],
                                status="ok", error=None)
                )
            except Exception as exc:
                results.append(
                    SweepResult(overrides=ov, card_path=out_dir / "card.json",
                                status="failed", error=str(exc))
                )

    summary_path = sweep_dir / "sweep_summary.json"
    summary_path.write_text(json.dumps({
        "recipe_id": recipe_id,
        "runs": [
            {"overrides": r["overrides"], "status": r["status"],
             "card_path": str(r["card_path"]), "error": r["error"]}
            for r in results
        ],
    }, indent=2))
    return results
```

Note on test mocking: `_run_single` is a module-level function so `monkeypatch.setattr("pet_infra.launcher._run_single", ...)` works. The ProcessPoolExecutor is bypassed for tests by the monkeypatch (tests simulate pool-less dispatch via in-process loop).

Modify `launch_multirun` to accept a `_executor_factory` kwarg (default `ProcessPoolExecutor`) for tests, or alternatively have tests patch by running single-thread when `PET_MULTIRUN_SYNC=1` is set:

```python
def launch_multirun(..., max_workers=None):
    ...
    if os.environ.get("PET_MULTIRUN_SYNC") == "1":
        for ov in overrides_list:
            out_dir = sweep_dir / _sweep_hash(ov)
            try:
                outcome = _run_single(recipe_path, ov, out_dir)
                results.append(SweepResult(overrides=ov, card_path=outcome["card_path"],
                                           status="ok", error=None))
            except Exception as exc:
                results.append(SweepResult(overrides=ov, card_path=out_dir / "card.json",
                                           status="failed", error=str(exc)))
        # write summary...
        return results
    # else use ProcessPoolExecutor as above...
```

Update tests to set `monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")` at test start.

- [ ] **Step 2: Add sync-mode env var to tests**

Edit `tests/test_launcher_multirun.py` — add at start of each test:

```python
def test_cartesian_product_2x2_yields_4_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    # ... existing test body
```

(Apply to all 4 tests.)

- [ ] **Step 3: Run tests — expect pass**

```bash
pytest tests/test_launcher_multirun.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 4: Run full test suite + lint**

```bash
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```

- [ ] **Step 5: Commit + open PR**

```bash
git add src/pet_infra/launcher.py tests/test_launcher_multirun.py
git commit -m "feat(pet-infra): multi-axis multirun launcher (Extensibility 4→5)

launch_multirun(recipe_path, sweep_params={trainer:['a','b'], device:['cpu','mps']})
→ cartesian product, dispatched via ProcessPoolExecutor, one ModelCard per
axis combo to results/<recipe_id>/<sweep_hash>/. Failed axes do not block
siblings. sweep_summary.json aggregates.

PET_MULTIRUN_SYNC=1 env var forces in-process synchronous loop (for tests).

Closes Phase 3A Extensibility 4/5 debt.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-multirun
gh pr create --base dev --title "feat(pet-infra): multi-axis multirun launcher" --body "Closes Extensibility 4/5 debt."
# after CI green + 1 approve:
gh pr merge --merge
```

---

## PR #P1-C: orchestrator/hooks.py — Converter + Dataset + Ota stage runners

**Branch:** `feature/phase-3b-stage-runners`

**Files:**
- Create: `pet-infra/src/pet_infra/orchestrator/hooks.py`
- Modify: `pet-infra/src/pet_infra/orchestrator/runner.py` (register new runners)
- Modify: `pet-infra/src/pet_infra/registry.py` (ensure CONVERTERS/DATASETS/OTA all exported)
- Create: `pet-infra/tests/test_orchestrator_hooks.py`

### Task P1-C.1: OTA registry slot

- [ ] **Step 1: Branch**

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-stage-runners
```

- [ ] **Step 2: Verify existing registries**

```bash
grep -n 'OTA\|DATASETS\|CONVERTERS' src/pet_infra/registry.py
```

Expected: CONVERTERS + DATASETS already exist (Phase 3A); OTA likely NOT yet.

- [ ] **Step 3: Add OTA registry slot**

Append to `src/pet_infra/registry.py`:

```python
OTA = Registry("ota")
```

Also append `OTA` to the `__all__` list if one exists.

- [ ] **Step 4: Write failing test**

`tests/test_orchestrator_hooks.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from pet_infra.orchestrator.hooks import (
    ConverterStageRunner, DatasetStageRunner, OtaStageRunner,
)
from pet_infra.registry import CONVERTERS, DATASETS, OTA

class DummyConverter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, input_card, recipe):
        new_card = input_card.model_copy(update={"edge_artifacts": [
            *input_card.edge_artifacts,
            {"format": "noop", "artifact_uri": "mem://dummy", "sha256": "x"*64,
             "target_hardware": "cpu", "size_bytes": 1},
        ]})
        return new_card


class DummyDataset:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, input_card, recipe):
        return input_card.model_copy(update={"intermediate_artifacts": {
            **getattr(input_card, "intermediate_artifacts", {}) or {},
            "calibration_batch_uri": "/tmp/cal.pt",
        }})


class DummyOta:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, input_card, recipe):
        if input_card.gate_status != "passed":
            from pet_infra.orchestrator.hooks import GateFailedError
            raise GateFailedError(f"gate_status={input_card.gate_status}")
        return input_card.model_copy(update={"deployment_history": [
            *(input_card.deployment_history or []),
            {"backend": "dummy", "state": "ok"},
        ]})


@pytest.fixture
def minimal_card():
    from pet_schema.model_card import ModelCard
    return ModelCard(
        card_id="abc", modality="vision", checkpoint_uri="/tmp/ckpt",
        schema_version="2.2.0", gate_status="passed",
    )


def test_converter_runner_appends_edge_artifact(minimal_card):
    CONVERTERS.register("_test_dummy", DummyConverter, force=True)
    stage = MagicMock(component_type="_test_dummy", config_path=None)
    runner = ConverterStageRunner()
    out_card = runner.run(stage, minimal_card, recipe=MagicMock())
    assert len(out_card.edge_artifacts) == 1
    assert out_card.edge_artifacts[0]["format"] == "noop"


def test_dataset_runner_writes_calibration_uri(minimal_card):
    DATASETS.register("_test_dummy_ds", DummyDataset, force=True)
    stage = MagicMock(component_type="_test_dummy_ds", config_path=None)
    runner = DatasetStageRunner()
    out_card = runner.run(stage, minimal_card, recipe=MagicMock())
    assert out_card.intermediate_artifacts["calibration_batch_uri"] == "/tmp/cal.pt"


def test_ota_runner_gate_guard_blocks_failed(minimal_card):
    OTA.register("_test_dummy_ota", DummyOta, force=True)
    from pet_infra.orchestrator.hooks import GateFailedError
    failed_card = minimal_card.model_copy(update={"gate_status": "failed"})
    stage = MagicMock(component_type="_test_dummy_ota", config_path=None)
    runner = OtaStageRunner()
    with pytest.raises(GateFailedError):
        runner.run(stage, failed_card, recipe=MagicMock())


def test_ota_runner_happy_path(minimal_card):
    OTA.register("_test_dummy_ota", DummyOta, force=True)
    stage = MagicMock(component_type="_test_dummy_ota", config_path=None)
    runner = OtaStageRunner()
    out_card = runner.run(stage, minimal_card, recipe=MagicMock())
    assert len(out_card.deployment_history) == 1
```

- [ ] **Step 5: Run test — expect fail**

```bash
pytest tests/test_orchestrator_hooks.py -v
```

Expected: FAIL (hooks.py missing).

### Task P1-C.2: implement stage runner hooks

- [ ] **Step 1: Read existing runner**

```bash
cat src/pet_infra/orchestrator/runner.py
```

Identify how existing TrainerStageRunner / EvaluatorStageRunner are dispatched.

- [ ] **Step 2: Create hooks.py**

`src/pet_infra/orchestrator/hooks.py`:

```python
"""Stage runners added in Phase 3B for CONVERTERS / DATASETS / OTA registries."""
from pathlib import Path
from omegaconf import OmegaConf
from pet_schema.model_card import ModelCard
from pet_schema.experiment_recipe import ExperimentRecipe, RecipeStage
from pet_infra.registry import CONVERTERS, DATASETS, OTA


class GateFailedError(Exception):
    """Raised by OtaStageRunner when upstream gate did not pass."""


def _load_stage_kwargs(stage: RecipeStage) -> dict:
    if not stage.config_path:
        return {}
    cfg = OmegaConf.load(stage.config_path)
    return OmegaConf.to_container(cfg, resolve=True) or {}


class ConverterStageRunner:
    """Dispatched for stage.component_registry == 'converters'."""

    def run(self, stage: RecipeStage, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        plugin_cls = CONVERTERS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"CONVERTERS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class DatasetStageRunner:
    """Dispatched for stage.component_registry == 'datasets'."""

    def run(self, stage: RecipeStage, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        plugin_cls = DATASETS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"DATASETS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class OtaStageRunner:
    """Dispatched for stage.component_registry == 'ota'.

    Guards gate_status == 'passed' before delegating to plugin.
    """

    def run(self, stage: RecipeStage, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        if input_card.gate_status != "passed":
            raise GateFailedError(
                f"OTA stage blocked: gate_status={input_card.gate_status}")
        plugin_cls = OTA.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"OTA['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)
```

- [ ] **Step 3: Register runners in orchestrator**

Edit `src/pet_infra/orchestrator/runner.py`'s stage-runner dispatch map (the one keyed by `component_registry` string) to include:

```python
from pet_infra.orchestrator.hooks import (
    ConverterStageRunner, DatasetStageRunner, OtaStageRunner,
)

STAGE_RUNNERS = {
    "trainers": TrainerStageRunner(),
    "evaluators": EvaluatorStageRunner(),
    "converters": ConverterStageRunner(),
    "datasets": DatasetStageRunner(),
    "ota": OtaStageRunner(),
    # ... existing ...
}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_orchestrator_hooks.py -v
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```

Expected: all green.

- [ ] **Step 5: Commit + open PR**

```bash
git add src/pet_infra/orchestrator/hooks.py src/pet_infra/orchestrator/runner.py \
        src/pet_infra/registry.py tests/test_orchestrator_hooks.py
git commit -m "feat(pet-infra): Converter + Dataset + Ota stage runners

- OTA registry added to registry.py (5 → 6 registries with ota)
- hooks.py: ConverterStageRunner / DatasetStageRunner / OtaStageRunner
- OtaStageRunner guards gate_status=='passed'; raises GateFailedError on fail
- runner.py STAGE_RUNNERS dispatch map extended

Prepares orchestrator DAG for Phase 3B plugins in pet-quantize / pet-ota.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-stage-runners
gh pr create --base dev --title "feat(pet-infra): Converter/Dataset/Ota stage runners"
gh pr merge --merge
```

---

## PR #P1-D: recipes defaults fragments + smoke_{tiny,mps,small} rewrite

**Branch:** `feature/phase-3b-recipe-fragments`

**Files:**
- Create: `pet-infra/recipes/_base/smoke_base.yaml`
- Create: `pet-infra/recipes/trainer/{llamafactory_sft,llamafactory_dpo,tiny_test}.yaml`
- Create: `pet-infra/recipes/evaluator/{vlm_evaluator,quantized_vlm_evaluator}.yaml`
- Create: `pet-infra/recipes/converter/{vlm_rkllm_w4a16,vision_rknn_fp16,audio_rknn_fp16,noop_converter}.yaml`
- Create: `pet-infra/recipes/dataset/{vlm_calibration_subset,vision_calibration_subset,audio_calibration_subset}.yaml`
- Create: `pet-infra/recipes/ota/local_backend.yaml`
- Modify: `pet-infra/recipes/smoke_tiny.yaml` (rewrite with defaults:)
- Modify: `pet-infra/recipes/smoke_mps.yaml` (rewrite with defaults:)
- Modify: `pet-infra/recipes/smoke_small.yaml` (rewrite with defaults:)
- Create: `pet-infra/recipes/release.yaml` (new, uses defaults: smoke_small + recipe_id=release)

### Task P1-D.1: create fragment files

- [ ] **Step 1: Branch + create _base**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-recipe-fragments
mkdir -p recipes/_base recipes/trainer recipes/evaluator recipes/converter recipes/dataset recipes/ota
```

- [ ] **Step 2: Write smoke_base.yaml**

`recipes/_base/smoke_base.yaml`:

```yaml
# Shared scaffold for smoke_tiny / smoke_mps / smoke_small / release
owner_repo: pet-infra
description: Phase 3B smoke pipeline base
schema_version: "0.1"
default_storage: local
variations: []
required_plugins: {}
```

- [ ] **Step 3: Write trainer fragments**

`recipes/trainer/llamafactory_sft.yaml`:

```yaml
# @package _global_
stages:
  train:
    component_registry: trainers
    component_type: llamafactory_sft
    config_path: configs/smoke/${smoke_tier:mps}_train.yaml
    depends_on: []
```

`recipes/trainer/tiny_test.yaml`:

```yaml
# @package _global_
stages:
  train:
    component_registry: trainers
    component_type: tiny_test
    config_path: configs/smoke/tiny_train.yaml
    depends_on: []
```

`recipes/trainer/llamafactory_dpo.yaml` — similar, `component_type: llamafactory_dpo`.

- [ ] **Step 4: Write evaluator fragments**

`recipes/evaluator/vlm_evaluator.yaml`:

```yaml
# @package _global_
stages:
  eval_fp:
    component_registry: evaluators
    component_type: vlm_evaluator
    config_path: configs/smoke/${smoke_tier:mps}_eval.yaml
    depends_on: [train]
```

`recipes/evaluator/quantized_vlm_evaluator.yaml`:

```yaml
# @package _global_
stages:
  eval_quant:
    component_registry: evaluators
    component_type: quantized_vlm_evaluator
    config_path: configs/smoke/${smoke_tier:mps}_eval_quant.yaml
    depends_on: [quantize]
```

- [ ] **Step 5: Write converter fragments**

`recipes/converter/vlm_rkllm_w4a16.yaml`:

```yaml
# @package _global_
stages:
  quantize:
    component_registry: converters
    component_type: vlm_rkllm_w4a16
    config_path: configs/smoke/${smoke_tier:mps}_quantize.yaml
    depends_on: [train, calibrate]
```

`recipes/converter/vision_rknn_fp16.yaml` — analogous, `component_type: vision_rknn_fp16`.
`recipes/converter/audio_rknn_fp16.yaml` — analogous.
`recipes/converter/noop_converter.yaml`:

```yaml
# @package _global_
stages:
  quantize:
    component_registry: converters
    component_type: noop_converter
    config_path: configs/smoke/tiny_quantize.yaml
    depends_on: [train]
```

- [ ] **Step 6: Write dataset fragments**

`recipes/dataset/vision_calibration_subset.yaml`:

```yaml
# @package _global_
stages:
  calibrate:
    component_registry: datasets
    component_type: vision_calibration_subset
    config_path: configs/smoke/${smoke_tier:mps}_calibration.yaml
    depends_on: [train]
```

(Similar for `vlm_calibration_subset.yaml` and `audio_calibration_subset.yaml`.)

- [ ] **Step 7: Write ota fragment**

`recipes/ota/local_backend.yaml`:

```yaml
# @package _global_
stages:
  deploy:
    component_registry: ota
    component_type: local_backend
    config_path: configs/smoke/${smoke_tier:mps}_deploy.yaml
    depends_on: [eval_quant]
```

### Task P1-D.2: rewrite smoke recipes with defaults:

- [ ] **Step 1: Rewrite smoke_tiny.yaml**

```yaml
defaults:
  - _base/smoke_base
  - trainer/tiny_test
  - converter/noop_converter
  - ota/local_backend

recipe_id: smoke_tiny
description: PR-CI smoke; tiny trainer + noop converter + local OTA
smoke_tier: tiny

stages:
  deploy:
    depends_on: [quantize]  # tiny tier skips eval_quant

produces:
  - artifact_type: edge_artifact
    format: noop
    gate: passed
```

- [ ] **Step 2: Rewrite smoke_mps.yaml**

```yaml
defaults:
  - _base/smoke_base
  - trainer/llamafactory_sft
  - evaluator/vlm_evaluator
  - dataset/vision_calibration_subset
  - converter/vision_rknn_fp16
  - evaluator/quantized_vlm_evaluator
  - ota/local_backend

recipe_id: smoke_mps
description: MPS smoke; full pipeline on Apple Silicon
smoke_tier: mps

produces:
  - artifact_type: edge_artifact
    format: rknn
    gate: passed
```

- [ ] **Step 3: Rewrite smoke_small.yaml**

```yaml
defaults:
  - _base/smoke_base
  - trainer/llamafactory_sft
  - evaluator/vlm_evaluator
  - dataset/vision_calibration_subset
  - converter/vision_rknn_fp16
  - evaluator/quantized_vlm_evaluator
  - ota/local_backend

recipe_id: smoke_small
description: Release-CI smoke; full pipeline with real rknn toolchain
smoke_tier: small

produces:
  - artifact_type: edge_artifact
    format: rknn
    gate: passed
```

- [ ] **Step 4: Create release.yaml**

```yaml
defaults:
  - smoke_small

recipe_id: release
description: Release pipeline; used by pet validate --hardware=rk3576
```

- [ ] **Step 5: Add smoke tests**

`tests/test_phase3b_smoke_recipes.py`:

```python
from pathlib import Path
import pytest
from pet_infra.compose import compose_recipe

RECIPES = Path(__file__).parent.parent / "recipes"

@pytest.mark.parametrize("recipe_name", ["smoke_tiny", "smoke_mps", "smoke_small", "release"])
def test_phase3b_recipe_composes(recipe_name):
    recipe = compose_recipe(RECIPES / f"{recipe_name}.yaml")
    assert recipe.recipe_id == recipe_name
    assert len(recipe.stages) >= 2
    # All stages have component_registry set
    for stage in recipe.stages:
        assert stage.component_registry in {"trainers", "evaluators", "converters", "datasets", "ota"}

def test_release_recipe_has_deploy_stage():
    recipe = compose_recipe(RECIPES / "release.yaml")
    stage_names = {s.name for s in recipe.stages}
    assert "deploy" in stage_names
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_phase3b_smoke_recipes.py tests/test_compose_backward_compat.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit + PR**

```bash
git add recipes/
git add tests/test_phase3b_smoke_recipes.py
git commit -m "feat(pet-infra): defaults: recipe fragments + smoke/release recipes

- recipes/_base/smoke_base.yaml: shared scaffold
- recipes/{trainer,evaluator,converter,dataset,ota}/*.yaml: fragments per
  plugin type. @package _global_ makes them merge into top-level recipe tree.
- smoke_tiny/mps/small.yaml rewritten using defaults: lists (~10 LOC each,
  down from ~50 LOC standalone)
- release.yaml new: recipe_id=release, inherits smoke_small, used by
  pet validate --hardware=rk3576 and release tag guard

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-recipe-fragments
gh pr create --base dev --title "feat(pet-infra): defaults: fragments for Phase 3B recipes"
gh pr merge --merge
```

---

## PR #P1-E: params.yaml namespaces + `pet validate --hardware` CLI

**Branch:** `feature/phase-3b-params-and-hw-validate`

**Files:**
- Modify: `pet-infra/params.yaml`
- Modify: `pet-infra/src/pet_infra/cli.py`
- Create: `pet-infra/src/pet_infra/cli_commands/validate_hardware.py`
- Create: `pet-infra/tests/test_validate_hardware_cli.py`
- Create: `pet-infra/configs/smoke/{small_quantize,small_eval_quant,small_calibration,small_deploy,tiny_quantize}.yaml`

### Task P1-E.1: append params.yaml

- [ ] **Step 1: Branch + append params**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-params-and-hw-validate
```

Append to `params.yaml`:

```yaml
quantize:
  calibration:
    num_samples: 64
    batch_size: 8
  rkllm:
    target_platform: rk3576
    quantized_dtype: w4a16
  rknn:
    target_platform: rk3576
    optimization_level: 3

ota:
  local_backend:
    storage_root: ./ota_artifacts

# Extend existing `gate:` block with Phase 3B thresholds
gate:
  # ... existing thresholds (do not delete) ...
  max_latency_ms_p95: 500
  min_quantized_accuracy: 0.85
  max_kl_divergence: 0.1
```

- [ ] **Step 2: Create stage config yamls**

`configs/smoke/small_quantize.yaml`:

```yaml
target_platform: ${params.quantize.rknn.target_platform}
optimization_level: ${params.quantize.rknn.optimization_level}
```

`configs/smoke/small_eval_quant.yaml`:

```yaml
metrics: [vlm_accuracy, kl_divergence]
device: cuda
```

`configs/smoke/small_calibration.yaml`:

```yaml
num_samples: ${params.quantize.calibration.num_samples}
batch_size: ${params.quantize.calibration.batch_size}
source_uri: ${params.dataset.vision.calibration_uri:/tmp/stub-calibration}
```

`configs/smoke/small_deploy.yaml`:

```yaml
storage_root: ${params.ota.local_backend.storage_root}
```

`configs/smoke/tiny_quantize.yaml`:

```yaml
# noop converter needs nothing; keep file for defaults: path resolution
dummy: true
```

### Task P1-E.2: pet validate --hardware CLI skeleton

- [ ] **Step 1: Write failing test**

`tests/test_validate_hardware_cli.py`:

```python
import json
import subprocess
from pathlib import Path
import pytest
from pet_schema.model_card import ModelCard, HardwareValidation

def _write_passed_card(tmp_path, with_validation=False):
    card = ModelCard(
        card_id="rel-123",
        modality="vision",
        checkpoint_uri="/tmp/x",
        schema_version="2.2.0",
        gate_status="passed",
    )
    if with_validation:
        from datetime import datetime, timezone
        card = card.model_copy(update={"hardware_validation": HardwareValidation(
            device_id="rk3576-x",
            firmware_version="1.0",
            validated_at=datetime.now(timezone.utc),
            latency_ms_p50=10.0,
            latency_ms_p95=20.0,
            validated_by="operator:test",
        ).model_dump(mode="json")})
    p = tmp_path / "card.json"
    p.write_text(card.model_dump_json())
    return p

def test_cli_skeleton_exists():
    r = subprocess.run(["pet", "validate", "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--hardware" in r.stdout

def test_cli_dry_run_writes_hardware_validation_stub(tmp_path):
    card_path = _write_passed_card(tmp_path)
    r = subprocess.run([
        "pet", "validate", "--card", str(card_path),
        "--hardware", "rk3576", "--device", "rk3576-test-01",
        "--dry-run",
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    updated = ModelCard.model_validate_json(card_path.read_text())
    assert updated.hardware_validation is not None
    assert updated.hardware_validation.validated_by.startswith("github-actions:") or \
           updated.hardware_validation.validated_by.startswith("operator:")
```

- [ ] **Step 2: Run test — expect fail**

```bash
pytest tests/test_validate_hardware_cli.py -v
```

Expected: FAIL (CLI subcommand missing).

- [ ] **Step 3: Implement validate_hardware CLI command**

Create `src/pet_infra/cli_commands/validate_hardware.py`:

```python
"""`pet validate --hardware=rk3576 --card=<path>` command.

In Phase 3B scope, only --dry-run is implemented (writes a stub HardwareValidation).
Real-device invocation is a manual release-manager workflow and is NOT integrated
into CI (per CLAUDE.md 'latency tests must run on real RK3576').
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
import click
from pet_schema.model_card import ModelCard, HardwareValidation


@click.command("validate")
@click.option("--card", "card_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--hardware", type=click.Choice(["rk3576"]), required=True)
@click.option("--device", "device_id", required=True, help="Device identifier, e.g. rk3576-dev-01")
@click.option("--firmware", "firmware_version", default="unknown")
@click.option("--dry-run", is_flag=True, help="Write a stub HardwareValidation without running on device")
@click.option("--recipe", "recipe_path", type=click.Path(path_type=Path), default=None,
              help="Release recipe (for path derivation; optional when --card is given)")
def validate(card_path: Path, hardware: str, device_id: str, firmware_version: str,
             dry_run: bool, recipe_path: Path | None):
    card = ModelCard.model_validate_json(card_path.read_text())
    if dry_run:
        who = f"github-actions:{os.environ['GITHUB_RUN_ID']}" \
            if os.environ.get("GITHUB_RUN_ID") else \
            f"operator:{os.environ.get('USER', 'unknown')}"
        hv = HardwareValidation(
            device_id=device_id,
            firmware_version=firmware_version,
            validated_at=datetime.now(timezone.utc),
            latency_ms_p50=0.0,
            latency_ms_p95=0.0,
            accuracy=None,
            kl_divergence=None,
            validated_by=who,
            notes="DRY-RUN stub; not a real validation",
        )
    else:
        raise click.ClickException(
            "Real-device validation not yet implemented in Phase 3B scope. "
            "Use --dry-run for CI, or invoke vendor RKNN/RKLLM toolchain manually "
            "and write HardwareValidation via pet_schema.model_card programmatically.")

    updated = card.model_copy(update={"hardware_validation": hv.model_dump(mode="json")})
    card_path.write_text(updated.model_dump_json(indent=2))
    click.echo(f"OK HardwareValidation written to {card_path} (validated_by={hv.validated_by})")
```

Register in `src/pet_infra/cli.py`:

```python
from pet_infra.cli_commands.validate_hardware import validate as validate_command
cli.add_command(validate_command)  # existing CLI group
```

- [ ] **Step 4: Run test — expect pass**

```bash
pip install -e ".[dev]"  # re-register entry-point
pytest tests/test_validate_hardware_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit + PR**

```bash
git add params.yaml configs/smoke/ src/pet_infra/cli.py \
        src/pet_infra/cli_commands/validate_hardware.py \
        tests/test_validate_hardware_cli.py
git commit -m "feat(pet-infra): Phase 3B params.yaml + pet validate --hardware CLI

- params.yaml: quantize / ota namespaces + gate thresholds for quantized eval
- configs/smoke/*.yaml: stage config files referenced by recipe fragments
- pet validate --hardware=rk3576 --dry-run writes HardwareValidation stub
  (real-device invocation deferred to manual release workflow per CLAUDE.md)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-params-and-hw-validate
gh pr create --base dev --title "feat(pet-infra): params.yaml + pet validate --hardware"
gh pr merge --merge
```

---

## PR #P1-F: matrix 2026.08-rc + §11.4 装序 + release v2.4.0-rc1

**Branch:** `feature/phase-3b-matrix-rc`

**Files:**
- Modify: `pet-infra/docs/compatibility_matrix.yaml`
- Modify: `pet-infra/docs/DEVELOPMENT_GUIDE.md` (§11.4 install order for Phase 3B)
- Modify: `pet-infra/src/pet_infra/__init__.py` or `pyproject.toml` (bump to 2.4.0-rc1)

### Task P1-F.1: matrix 2026.08-rc row

- [ ] **Step 1: Branch + edit matrix**

Append to `docs/compatibility_matrix.yaml`:

```yaml
  - release: "2026.08-rc"
    pet_schema: "2.2.0"           # Phase 3B finalized early (no rc needed)
    pet_infra: "2.4.0-rc1"
    pet_data: "1.2.0"
    pet_annotation: "2.0.0"
    pet_train: "2.0.0"
    pet_eval: "2.1.0-rc1"
    pet_quantize: "2.0.0-rc1"
    pet_ota: "2.0.0-rc1"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
    rknn_toolkit2: "==2.0.0"
    rkllm_toolkit: "==1.2.0"
```

- [ ] **Step 2: Update DEVELOPMENT_GUIDE §11.4**

Add subsection for Phase 3B 6-step install for pet-eval:

```markdown
### §11.4.3 Phase 3B pet-eval 6-step peer-dep install

pet-eval 2.1.0 adds pet-quantize as a runtime peer (for QuantizedVlmEvaluator
lazy import). CI install order:

1. pip install 'pet-infra@<rc-tag>'
2. pip install 'pet-train@<rc-tag>'
3. pip install 'pet-quantize@<rc-tag>'  ← NEW vs Phase 3A 5-step
4. pip install -e . --no-deps
5. pip install -e ".[dev]"   (re-resolve)
6. python -c "import pet_infra, pet_train, pet_quantize, pet_eval; <assert versions>"
```

- [ ] **Step 3: Bump pet-infra version**

Find version source:

```bash
grep -rn '"2\.3\.0"' src/ pyproject.toml
```

Edit to `2.4.0-rc1`.

- [ ] **Step 4: Commit + PR**

```bash
git add docs/compatibility_matrix.yaml docs/DEVELOPMENT_GUIDE.md \
        src/pet_infra/__init__.py pyproject.toml
git commit -m "docs(pet-infra): matrix 2026.08-rc + §11.4.3 Phase 3B 6-step install

- compatibility_matrix.yaml: 2026.08-rc row (all -rc1 except pet-schema 2.2.0)
- §11.4.3 documents pet-eval's new 6-step install (insert pet-quantize)
- pet-infra version bumped 2.3.0 → 2.4.0-rc1

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-matrix-rc
gh pr create --base dev --title "docs(pet-infra): matrix 2026.08-rc + v2.4.0-rc1 prep"
gh pr merge --merge
```

- [ ] **Step 5: Release v2.4.0-rc1 (dev → main)**

```bash
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-infra v2.4.0-rc1 (Phase 3B P1)" --body "Compose defaults-list + multirun + stage runners + matrix 2026.08-rc."
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.4.0-rc1
git push origin v2.4.0-rc1
gh release create v2.4.0-rc1 --prerelease --title "pet-infra v2.4.0-rc1 — Phase 3B infra foundation" --notes "Flexibility + Extensibility 5/5 debts closed. RC used for downstream pet-quantize/eval/ota to pin against."
```

---

# Phase 2: pet-quantize v2.0.0-rc1 (8 PRs — BREAKING)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize`
**Target branch per PR:** `dev`
**Final rc tag:** `v2.0.0-rc1`

---

## PR #P2-A: audit + delete v1 (cli, config 三元组, wandb, legacy orch)

**Branch:** `feature/phase-3b-audit-delete-v1`

**Files (delete):**
- `pet-quantize/src/pet_quantize/cli.py` (if exists)
- `pet-quantize/src/pet_quantize/__main__.py` (if exists)
- `pet-quantize/src/pet_quantize/config.py` (hardcoded vision/llm/audio triple)
- Any wandb imports across the codebase (ripgrep)
- Any legacy pipeline orchestration files that will be replaced by plugins

**Files (preserve — do NOT touch in this PR):**
- `convert/{export_vision_encoder,export_llm,rkllm_converter,rknn_converter}.py`
- `calibration/` (core tensor-batch utilities)
- `packaging/{sign,verify,build}_package.py`
- `validate/{latency,kl_divergence,schema_compliance,audio_accuracy}.py`
- `inference/{rknn_runner,rkllm_runner,pipeline}.py`

### Task P2-A.1: audit

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-audit-delete-v1
```

- [ ] **Step 2: Inventory v1 surface area**

```bash
find src/ -type f -name '*.py' | sort > /tmp/pet-quantize-files.txt
# Identify files referencing wandb
grep -rln 'wandb' src/ tests/
# Identify files referencing the tri-model hardcode (vision_encoder + llm + audio)
grep -rln 'vision_encoder.*llm.*audio\|VISION_ENCODER\|LLM_PATH\|AUDIO_PATH' src/
# Check CLI entry-points
grep -n 'cli\|__main__' pyproject.toml
```

- [ ] **Step 3: Document audit results**

Write `docs/phase-3b-audit.md` listing what will be deleted and what is preserved. Commit this first so the deletion rationale is reviewable.

```bash
mkdir -p docs && cat > docs/phase-3b-audit.md <<'EOF'
# Phase 3B pet-quantize audit (2026-04-21)

## To delete (architectural debt)
- src/pet_quantize/cli.py          (replaced by `pet run <recipe>`)
- src/pet_quantize/__main__.py     (same)
- src/pet_quantize/config.py       (hardcoded vision/llm/audio triple incompatible with plugin model)
- wandb dependency + inline usage  (replaced by pet-infra ExperimentLogger)

## To preserve (SDK wrappers, still called by plugins)
- src/pet_quantize/convert/*       (rknn/rkllm toolchain wrappers)
- src/pet_quantize/calibration/    (tensor batch utilities)
- src/pet_quantize/packaging/      (sign/verify/build)
- src/pet_quantize/validate/       (latency/kl/schema_compliance/audio_accuracy)
- src/pet_quantize/inference/      (rknn_runner + rkllm_runner, lazy-imported by pet-eval)
EOF
```

- [ ] **Step 4: Commit audit doc**

```bash
git add docs/phase-3b-audit.md
git commit -m "docs(pet-quantize): Phase 3B audit — files to delete vs preserve"
```

### Task P2-A.2: delete v1

- [ ] **Step 1: Remove CLI + config**

```bash
git rm -f src/pet_quantize/cli.py src/pet_quantize/__main__.py src/pet_quantize/config.py 2>/dev/null || true
```

- [ ] **Step 2: Purge wandb**

For every file flagged in Step 2 of audit:
- Remove `import wandb` and all `wandb.*` calls.
- If removal leaves orphaned logic, replace with `# TODO(Phase 3B): write to ModelCard.eval_results via ExperimentLogger when plugin migrates` comment if non-trivial; otherwise delete the hook.

- [ ] **Step 3: Purge the triple config**

Any module importing `from pet_quantize.config import ...` either:
- Gets its own local constants (if the module will be preserved and the constant is legitimately configurable), OR
- Is itself deleted as part of the legacy orch layer.

- [ ] **Step 4: Remove CLI entry-points from pyproject.toml**

```bash
# Delete the [project.scripts] `pet-quantize = ...` line(s)
```

- [ ] **Step 5: Delete stale tests**

```bash
# Any test touching cli.py / config.py / wandb
git rm tests/test_cli.py tests/test_config.py 2>/dev/null || true
grep -rln 'wandb\|pet_quantize.cli\|pet_quantize.config' tests/ | xargs -I{} git rm -f {} 2>/dev/null || true
```

- [ ] **Step 6: Verify preserved paths still import**

```bash
python -c "import pet_quantize.convert.rkllm_converter; import pet_quantize.inference.rkllm_runner; import pet_quantize.packaging.sign_package"
```

Expected: all three imports succeed (no errors, no missing symbols).

- [ ] **Step 7: Run remaining tests**

```bash
pytest tests/ -v
```

Expected: whatever tests remain should pass (or be marked xfail if they rely on deleted modules — in which case delete them).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(pet-quantize): Phase 3B v1 purge (cli + config triple + wandb)

BREAKING CHANGE: CLI removed; users must transition to \`pet run <recipe>\`.
- Deleted: cli.py, __main__.py, config.py (vision/llm/audio hardcoded triple)
- Deleted: wandb dependency + inline usage throughout
- Preserved: convert/, calibration/, packaging/, validate/, inference/ SDK wrappers

Next PRs will register plugins in plugins/_register.py.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-audit-delete-v1
gh pr create --base dev --title "refactor(pet-quantize): Phase 3B v1 purge (audit + delete)"
gh pr merge --merge
```

---

## PR #P2-B: plugins/ skeleton + _register + NoopConverter

**Branch:** `feature/phase-3b-plugins-skeleton`

**Files:**
- Create: `pet-quantize/src/pet_quantize/plugins/__init__.py`
- Create: `pet-quantize/src/pet_quantize/plugins/_register.py`
- Create: `pet-quantize/src/pet_quantize/plugins/converters/__init__.py`
- Create: `pet-quantize/src/pet_quantize/plugins/converters/noop.py`
- Create: `pet-quantize/src/pet_quantize/plugins/datasets/__init__.py` (empty for now)
- Modify: `pet-quantize/pyproject.toml` (add entry-point + pet-infra/pet-schema peer-deps)
- Create: `pet-quantize/tests/test_plugin_register_noop.py`
- Create: `pet-quantize/tests/test_noop_converter.py`
- Create: `pet-quantize/tests/test_plugin_register_missing_sdk.py`

### Task P2-B.1: skeleton + noop

- [ ] **Step 1: Branch**

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-plugins-skeleton
```

- [ ] **Step 2: Create plugin package**

```bash
mkdir -p src/pet_quantize/plugins/converters src/pet_quantize/plugins/datasets
touch src/pet_quantize/plugins/__init__.py \
      src/pet_quantize/plugins/converters/__init__.py \
      src/pet_quantize/plugins/datasets/__init__.py
```

- [ ] **Step 3: Write NoopConverter**

`src/pet_quantize/plugins/converters/noop.py`:

```python
"""Zero-dependency CONVERTERS plugin, used by PR CI with PET_ALLOW_MISSING_SDK=1.

Produces a fake EdgeArtifact so the downstream OTA stage has something to ship,
without actually invoking any vendor SDK.
"""
from __future__ import annotations
import hashlib
import tempfile
from pathlib import Path
from pet_schema.model_card import ModelCard, EdgeArtifact
from pet_schema.experiment_recipe import ExperimentRecipe


class NoopConverter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        out_dir = Path(tempfile.mkdtemp(prefix="noop-artifact-"))
        artifact_path = out_dir / "model.noop"
        artifact_bytes = f"noop:{input_card.card_id}".encode()
        artifact_path.write_bytes(artifact_bytes)
        sha = hashlib.sha256(artifact_bytes).hexdigest()
        edge = EdgeArtifact(
            format="noop",  # type: ignore  # noop is outside the literal; acceptable for PR CI
            target_hardware="cpu",
            artifact_uri=str(artifact_path),
            sha256=sha,
            size_bytes=len(artifact_bytes),
        )
        return input_card.model_copy(update={
            "edge_artifacts": [*input_card.edge_artifacts, edge.model_dump(mode="json")],
        })
```

Note: `EdgeArtifact.format` in pet-schema uses a `Literal["rkllm","rknn","onnx","gguf"]`. Since `"noop"` is not in that literal, the `format="noop"` won't pass schema validation. Instead, use `"onnx"` as the placeholder format (the artifact doesn't have to be valid ONNX — it's only the `format` enum label), or extend the literal. **Decision: extend the literal in pet-schema to include `"noop"` — this is a minor addition, not a BREAKING change. But this pushes a pet-schema change into Phase 3B P2, which complicates things.**

**Resolution:** use `format="onnx"` for noop (it's an enum label only) and document the convention in a comment:

```python
edge = EdgeArtifact(
    format="onnx",  # noop placeholder — PR-CI-only, not a real ONNX file
    ...
)
```

No pet-schema change required.

- [ ] **Step 4: Write _register.py**

`src/pet_quantize/plugins/_register.py`:

```python
"""Entry-point hook: `pet_quantize = "pet_quantize.plugins._register:register_all"`.

Registration is conditional per SDK: NoopConverter always registers;
rknn-gated plugins guard with try/except ImportError; same for rkllm.
Unless PET_ALLOW_MISSING_SDK=1, any ImportError re-raises (fail-fast).
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)


def register_all():
    from pet_infra.registry import CONVERTERS, DATASETS

    # Always-available (zero-dep)
    from pet_quantize.plugins.converters.noop import NoopConverter
    CONVERTERS.register("noop_converter", NoopConverter, force=True)

    # RKNN-gated cluster
    try:
        from rknn.api import RKNN  # noqa: F401
        # Subsequent PRs will populate these:
        # from pet_quantize.plugins.converters.vision_rknn_fp16 import VisionRknnFp16Converter
        # from pet_quantize.plugins.converters.audio_rknn_fp16 import AudioRknnFp16Converter
        # CONVERTERS.register("vision_rknn_fp16", VisionRknnFp16Converter, force=True)
        # CONVERTERS.register("audio_rknn_fp16", AudioRknnFp16Converter, force=True)
        # DATASETS.register("vision_calibration_subset", VisionCalibrationSubset, force=True)
        # DATASETS.register("audio_calibration_subset", AudioCalibrationSubset, force=True)
        pass  # filled in #P2-D / #P2-E / #P2-F
    except ImportError as exc:
        if not os.environ.get("PET_ALLOW_MISSING_SDK"):
            raise
        logger.warning("rknn SDK missing; gated plugins skipped: %s", exc)

    # RKLLM-gated cluster
    try:
        from rkllm.api import RKLLM  # noqa: F401
        # from pet_quantize.plugins.converters.vlm_rkllm_w4a16 import VlmRkllmW4A16Converter
        # CONVERTERS.register("vlm_rkllm_w4a16", VlmRkllmW4A16Converter, force=True)
        # DATASETS.register("vlm_calibration_subset", VlmCalibrationSubset, force=True)
        pass  # filled in #P2-C / #P2-F
    except ImportError as exc:
        if not os.environ.get("PET_ALLOW_MISSING_SDK"):
            raise
        logger.warning("rkllm SDK missing; gated plugins skipped: %s", exc)
```

- [ ] **Step 5: Update pyproject.toml**

```toml
[project]
dependencies = [
    "pet-schema",
    "pet-infra",
    # ... preserve existing non-deleted deps ...
]

[project.entry-points."pet_infra.plugins"]
pet_quantize = "pet_quantize.plugins._register:register_all"
```

- [ ] **Step 6: Write failing tests**

`tests/test_plugin_register_noop.py`:

```python
import os
import pytest
from pet_infra.registry import CONVERTERS

def test_noop_registers_always():
    os.environ.pop("PET_ALLOW_MISSING_SDK", None)
    # Clean state
    if "noop_converter" in CONVERTERS.module_dict:
        CONVERTERS.module_dict.pop("noop_converter")
    from pet_quantize.plugins._register import register_all
    register_all()
    assert "noop_converter" in CONVERTERS.module_dict

def test_entry_point_discoverable():
    from importlib.metadata import entry_points
    eps = entry_points(group="pet_infra.plugins")
    assert "pet_quantize" in {ep.name for ep in eps}
```

`tests/test_noop_converter.py`:

```python
from pet_schema.model_card import ModelCard
from pet_quantize.plugins.converters.noop import NoopConverter

def test_noop_appends_edge_artifact():
    card = ModelCard(card_id="x", modality="vision", checkpoint_uri="/tmp/ckpt",
                     schema_version="2.2.0", gate_status="passed")
    plugin = NoopConverter()
    out = plugin.run(card, recipe=None)
    assert len(out.edge_artifacts) == 1
    artifact = out.edge_artifacts[0]
    assert len(artifact["sha256"]) == 64

def test_noop_is_deterministic_per_card_id():
    """Same card_id → same sha256 (useful for resume)."""
    card = ModelCard(card_id="stable", modality="vision", checkpoint_uri="/tmp/ckpt",
                     schema_version="2.2.0")
    a = NoopConverter().run(card, recipe=None).edge_artifacts[0]["sha256"]
    b = NoopConverter().run(card, recipe=None).edge_artifacts[0]["sha256"]
    assert a == b
```

`tests/test_plugin_register_missing_sdk.py`:

```python
import os
import sys
import pytest

def test_missing_sdk_raises_without_env(monkeypatch):
    """When PET_ALLOW_MISSING_SDK is unset and an rknn-gated import fails, register_all raises."""
    monkeypatch.delenv("PET_ALLOW_MISSING_SDK", raising=False)
    # Force rknn to appear missing by inserting a blocker
    monkeypatch.setitem(sys.modules, "rknn", None)
    monkeypatch.setitem(sys.modules, "rknn.api", None)
    # Fresh import of _register
    if "pet_quantize.plugins._register" in sys.modules:
        del sys.modules["pet_quantize.plugins._register"]
    from pet_quantize.plugins._register import register_all
    # If the try/except only re-raises when the import is actually attempted;
    # in P2-B the gate is empty so ImportError isn't raised. We test the affordance
    # exists by monkey-patching the import inside the function.
    # For P2-B, this test is a *skeleton* — it becomes meaningful in P2-C+.
    register_all()  # OK while gated clusters are empty

def test_missing_sdk_passes_with_env(monkeypatch):
    monkeypatch.setenv("PET_ALLOW_MISSING_SDK", "1")
    if "pet_quantize.plugins._register" in sys.modules:
        del sys.modules["pet_quantize.plugins._register"]
    from pet_quantize.plugins._register import register_all
    register_all()  # Should not raise
```

- [ ] **Step 7: Install + run tests**

```bash
pip install -e ".[dev]"  # re-register entry-points
pytest tests/test_plugin_register_noop.py tests/test_noop_converter.py \
       tests/test_plugin_register_missing_sdk.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit + PR**

```bash
git add src/pet_quantize/plugins/ tests/ pyproject.toml
git commit -m "feat(pet-quantize): plugins/ skeleton + _register + NoopConverter

- plugins/ package with converters/ and datasets/ subpackages
- _register.register_all() registers noop_converter always; gated clusters
  (rknn, rkllm) have try/except ImportError, re-raising unless
  PET_ALLOW_MISSING_SDK=1
- pyproject.toml entry-point: pet_quantize = pet_quantize.plugins._register:register_all

Real SDK-backed plugins land in P2-C / P2-D / P2-E / P2-F.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-plugins-skeleton
gh pr create --base dev --title "feat(pet-quantize): plugins skeleton + NoopConverter"
gh pr merge --merge
```

---

## PR #P2-C: VlmRkllmW4A16Converter

**Branch:** `feature/phase-3b-vlm-rkllm-w4a16`

**Files:**
- Create: `pet-quantize/src/pet_quantize/plugins/converters/vlm_rkllm_w4a16.py`
- Modify: `pet-quantize/src/pet_quantize/plugins/_register.py` (un-stub rkllm cluster)
- Create: `pet-quantize/tests/test_vlm_rkllm_converter.py`

### Task P2-C.1: converter plugin

- [ ] **Step 1: Branch**

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-vlm-rkllm-w4a16
```

- [ ] **Step 2: Write failing test**

`tests/test_vlm_rkllm_converter.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from pet_schema.model_card import ModelCard, QuantConfig
from pet_quantize.plugins.converters.vlm_rkllm_w4a16 import VlmRkllmW4A16Converter


@pytest.fixture
def input_card():
    return ModelCard(
        card_id="vlm-123",
        modality="vision",
        checkpoint_uri="/tmp/vlm-ckpt",
        schema_version="2.2.0",
        intermediate_artifacts={"calibration_batch_uri": "/tmp/cal.pt"},
    )


def test_converter_calls_rkllm_sdk_and_emits_edge_artifact(input_card, tmp_path, monkeypatch):
    # Mock the SDK wrapper
    mock_rkllm_module = MagicMock()
    mock_output = tmp_path / "model.rkllm"
    mock_output.write_bytes(b"fake rkllm contents")

    def fake_convert(checkpoint_uri, output_dir, calibration_batch_uri, **kwargs):
        return mock_output

    monkeypatch.setattr(
        "pet_quantize.convert.rkllm_converter.convert_vlm_to_rkllm",
        fake_convert,
    )

    plugin = VlmRkllmW4A16Converter(
        target_platform="rk3576",
        quantized_dtype="w4a16",
        output_dir=str(tmp_path),
    )
    out = plugin.run(input_card, recipe=MagicMock())
    assert len(out.edge_artifacts) == 1
    artifact = out.edge_artifacts[0]
    assert artifact["format"] == "rkllm"
    assert artifact["target_hardware"] == "rk3576"
    assert artifact["artifact_uri"].endswith(".rkllm")


def test_converter_requires_calibration_batch_in_card(input_card, tmp_path, monkeypatch):
    no_cal = input_card.model_copy(update={"intermediate_artifacts": {}})
    plugin = VlmRkllmW4A16Converter(target_platform="rk3576", quantized_dtype="w4a16",
                                     output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="calibration_batch_uri"):
        plugin.run(no_cal, recipe=MagicMock())
```

- [ ] **Step 3: Run test — expect fail**

```bash
pytest tests/test_vlm_rkllm_converter.py -v
```

Expected: FAIL (module missing).

- [ ] **Step 4: Implement plugin**

`src/pet_quantize/plugins/converters/vlm_rkllm_w4a16.py`:

```python
"""VLM RKLLM quantization plugin (w4a16 for RK3576)."""
from __future__ import annotations
import hashlib
from pathlib import Path
from pet_schema.model_card import ModelCard, EdgeArtifact, QuantConfig
from pet_schema.experiment_recipe import ExperimentRecipe


class VlmRkllmW4A16Converter:
    def __init__(self, target_platform: str = "rk3576",
                 quantized_dtype: str = "w4a16",
                 output_dir: str | None = None, **kwargs):
        self.target_platform = target_platform
        self.quantized_dtype = quantized_dtype
        self.output_dir = Path(output_dir) if output_dir else Path(".cache/rkllm")
        self.extra = kwargs

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        cal_uri = (input_card.intermediate_artifacts or {}).get("calibration_batch_uri")
        if not cal_uri:
            raise ValueError(
                "VlmRkllmW4A16Converter requires card.intermediate_artifacts.calibration_batch_uri "
                "(produced by a preceding DATASETS stage like vlm_calibration_subset)"
            )
        from pet_quantize.convert.rkllm_converter import convert_vlm_to_rkllm  # lazy: SDK-bound
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = convert_vlm_to_rkllm(
            checkpoint_uri=input_card.checkpoint_uri,
            output_dir=self.output_dir,
            calibration_batch_uri=cal_uri,
            target_platform=self.target_platform,
            quantized_dtype=self.quantized_dtype,
            **self.extra,
        )
        sha = hashlib.sha256(Path(output_path).read_bytes()).hexdigest()
        edge = EdgeArtifact(
            format="rkllm",
            target_hardware=self.target_platform,
            artifact_uri=str(output_path),
            sha256=sha,
            size_bytes=Path(output_path).stat().st_size,
        )
        quant_cfg = QuantConfig(
            method="ptq_int8",  # or derived from quantized_dtype; keep schema-compliant
            bits=4 if "4" in self.quantized_dtype else 8,
            calibration_dataset_uri=cal_uri,
        )
        return input_card.model_copy(update={
            "edge_artifacts": [*input_card.edge_artifacts, edge.model_dump(mode="json")],
            "quant_config": quant_cfg.model_dump(mode="json"),
        })
```

- [ ] **Step 5: Un-stub rkllm cluster in _register.py**

```python
    try:
        from rkllm.api import RKLLM  # noqa: F401
        from pet_quantize.plugins.converters.vlm_rkllm_w4a16 import VlmRkllmW4A16Converter
        CONVERTERS.register("vlm_rkllm_w4a16", VlmRkllmW4A16Converter, force=True)
    except ImportError as exc:
        if not os.environ.get("PET_ALLOW_MISSING_SDK"):
            raise
        logger.warning("rkllm SDK missing; vlm_rkllm_w4a16 skipped: %s", exc)
```

- [ ] **Step 6: Verify convert_vlm_to_rkllm exists in SDK wrapper**

```bash
grep -n 'def convert_vlm_to_rkllm' src/pet_quantize/convert/rkllm_converter.py
```

If missing, add a thin entry-point function that wraps the existing SDK calls. This is a preserved-SDK-wrapper concern — the function should exist (or be synthesized) as a public API the plugin depends on.

- [ ] **Step 7: Run tests**

```bash
# With PET_ALLOW_MISSING_SDK=1 since rkllm is not installed in dev env
PET_ALLOW_MISSING_SDK=1 pytest tests/test_vlm_rkllm_converter.py -v
```

Expected: PASS (test mocks `convert_vlm_to_rkllm` directly so SDK absence doesn't matter).

- [ ] **Step 8: Commit + PR**

```bash
git add src/pet_quantize/plugins/converters/vlm_rkllm_w4a16.py \
        src/pet_quantize/plugins/_register.py \
        tests/test_vlm_rkllm_converter.py \
        src/pet_quantize/convert/rkllm_converter.py  # if convert_vlm_to_rkllm added
git commit -m "feat(pet-quantize): VlmRkllmW4A16Converter plugin

CONVERTERS['vlm_rkllm_w4a16'] — calls convert_vlm_to_rkllm SDK wrapper,
consumes calibration_batch_uri from DATASETS stage, emits EdgeArtifact
with format='rkllm' and target_hardware=rk3576.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-vlm-rkllm-w4a16
gh pr create --base dev --title "feat(pet-quantize): VlmRkllmW4A16Converter"
gh pr merge --merge
```

---

## PR #P2-D: VisionRknnFp16Converter

**Branch:** `feature/phase-3b-vision-rknn-fp16`

**Files:**
- Create: `pet-quantize/src/pet_quantize/plugins/converters/vision_rknn_fp16.py`
- Modify: `pet-quantize/src/pet_quantize/plugins/_register.py` (un-stub rknn cluster — vision)
- Create: `pet-quantize/tests/test_vision_rknn_converter.py`

Same TDD cycle as P2-C, substituting RKNN for RKLLM. Key contract:

- Plugin class `VisionRknnFp16Converter.__init__(target_platform='rk3576', optimization_level=3, output_dir=..., **kwargs)`.
- `.run(card, recipe)` requires `card.intermediate_artifacts.calibration_batch_uri`, calls `pet_quantize.convert.rknn_converter.convert_vision_to_rknn(...)`, emits `EdgeArtifact(format="rknn", target_hardware="rk3576", ...)`.
- Test mocks `pet_quantize.convert.rknn_converter.convert_vision_to_rknn` directly.
- `_register.py` rknn cluster adds `CONVERTERS.register("vision_rknn_fp16", VisionRknnFp16Converter, force=True)`.

(Test file: 2 test cases mirroring P2-C — happy path + missing-calibration-URI error.)

Commit + PR same pattern; merge.

---

## PR #P2-E: AudioRknnFp16Converter

**Branch:** `feature/phase-3b-audio-rknn-fp16`

Mirrors P2-D but for audio model. Key differences:

- Plugin class `AudioRknnFp16Converter`, same signature.
- SDK wrapper function `pet_quantize.convert.rknn_converter.convert_audio_to_rknn(...)`. (If not present, add thin entry point.)
- Emits `EdgeArtifact(format="rknn", target_hardware="rk3576", ...)` same as vision (format is RKNN agnostic to vision vs audio).
- Registered in rknn cluster in `_register.py` alongside `vision_rknn_fp16`.
- Tests require `card.intermediate_artifacts.calibration_batch_uri` (audio variant).

Single PR, ~3 tests, commit + merge.

---

## PR #P2-F: 3 calibration DATASETS plugins

**Branch:** `feature/phase-3b-calibration-datasets`

**Files:**
- Create: `pet-quantize/src/pet_quantize/plugins/datasets/vlm_calibration_subset.py`
- Create: `pet-quantize/src/pet_quantize/plugins/datasets/vision_calibration_subset.py`
- Create: `pet-quantize/src/pet_quantize/plugins/datasets/audio_calibration_subset.py`
- Modify: `pet-quantize/src/pet_quantize/plugins/_register.py` (un-stub DATASETS registrations)
- Create: `pet-quantize/tests/test_calibration_datasets.py`

### Task P2-F.1: dataset plugins

- [ ] **Step 1: Branch + write tests**

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-calibration-datasets
```

`tests/test_calibration_datasets.py`:

```python
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import torch
from pet_schema.model_card import ModelCard
from pet_quantize.plugins.datasets.vision_calibration_subset import VisionCalibrationSubset


@pytest.fixture
def base_card():
    return ModelCard(
        card_id="cal-test",
        modality="vision",
        checkpoint_uri="/tmp/ckpt",
        schema_version="2.2.0",
    )


def test_vision_calibration_subset_writes_tensor_batch(base_card, tmp_path, monkeypatch):
    # Mock the source loader to return synthetic tensors
    def fake_load(source_uri, num_samples):
        return [torch.zeros(3, 224, 224) for _ in range(num_samples)]

    monkeypatch.setattr(
        "pet_quantize.calibration.vision_loader.load_calibration_images",
        fake_load,
    )
    plugin = VisionCalibrationSubset(
        source_uri="/dev/null",
        num_samples=4,
        batch_size=2,
        cache_dir=str(tmp_path),
    )
    out = plugin.run(base_card, recipe=MagicMock())
    uri = out.intermediate_artifacts["calibration_batch_uri"]
    assert Path(uri).exists()
    loaded = torch.load(uri)
    assert loaded.shape[0] == 4  # num_samples


def test_determinism_same_source_same_hash(base_card, tmp_path, monkeypatch):
    def fake_load(source_uri, num_samples):
        return [torch.zeros(3, 224, 224)] * num_samples

    monkeypatch.setattr(
        "pet_quantize.calibration.vision_loader.load_calibration_images",
        fake_load,
    )
    p1 = VisionCalibrationSubset(source_uri="/x", num_samples=2, batch_size=1,
                                 cache_dir=str(tmp_path))
    p2 = VisionCalibrationSubset(source_uri="/x", num_samples=2, batch_size=1,
                                 cache_dir=str(tmp_path))
    uri1 = p1.run(base_card, recipe=MagicMock()).intermediate_artifacts["calibration_batch_uri"]
    uri2 = p2.run(base_card, recipe=MagicMock()).intermediate_artifacts["calibration_batch_uri"]
    assert uri1 == uri2  # content-addressable cache
```

- [ ] **Step 2: Implement VisionCalibrationSubset**

`src/pet_quantize/plugins/datasets/vision_calibration_subset.py`:

```python
from __future__ import annotations
import hashlib
from pathlib import Path
import torch
from pet_schema.model_card import ModelCard
from pet_schema.experiment_recipe import ExperimentRecipe


class VisionCalibrationSubset:
    def __init__(self, source_uri: str, num_samples: int = 64,
                 batch_size: int = 8, cache_dir: str | None = None, **kwargs):
        self.source_uri = source_uri
        self.num_samples = num_samples
        self.batch_size = batch_size
        self.cache_dir = Path(cache_dir or ".cache/calibration")
        self.extra = kwargs

    def _cache_key(self) -> str:
        payload = f"vision|{self.source_uri}|{self.num_samples}".encode()
        return hashlib.sha256(payload).hexdigest()[:16]

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / f"{self._cache_key()}.pt"
        if not cache_path.exists():
            from pet_quantize.calibration.vision_loader import load_calibration_images  # lazy
            tensors = load_calibration_images(self.source_uri, self.num_samples)
            batch = torch.stack(tensors)
            torch.save(batch, cache_path)
        current = input_card.intermediate_artifacts or {}
        return input_card.model_copy(update={
            "intermediate_artifacts": {**current, "calibration_batch_uri": str(cache_path)},
        })
```

- [ ] **Step 3: Implement VLM + Audio variants**

`src/pet_quantize/plugins/datasets/vlm_calibration_subset.py` — same shape, but calls `pet_quantize.calibration.vlm_loader.load_calibration_pairs` (image+text) and produces an appropriate `.pt`.

`src/pet_quantize/plugins/datasets/audio_calibration_subset.py` — calls `pet_quantize.calibration.audio_loader.load_calibration_clips`, produces audio tensor batch.

Each plugin needs the corresponding `pet_quantize.calibration.{vlm,vision,audio}_loader` module. If these modules don't exist in the preserved SDK wrappers, **add them as thin stubs** in this PR (they are the boundary between plugin and SDK; keeping them as a named module makes testing trivial).

- [ ] **Step 4: Un-stub DATASETS in _register.py**

Add to both rknn cluster (vision, audio) and rkllm cluster (vlm) in `_register.py`:

```python
# rknn cluster
DATASETS.register("vision_calibration_subset", VisionCalibrationSubset, force=True)
DATASETS.register("audio_calibration_subset", AudioCalibrationSubset, force=True)

# rkllm cluster
DATASETS.register("vlm_calibration_subset", VlmCalibrationSubset, force=True)
```

- [ ] **Step 5: Run tests**

```bash
PET_ALLOW_MISSING_SDK=1 pytest tests/test_calibration_datasets.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit + PR**

```bash
git add src/pet_quantize/plugins/datasets/ \
        src/pet_quantize/plugins/_register.py \
        src/pet_quantize/calibration/ \
        tests/test_calibration_datasets.py
git commit -m "feat(pet-quantize): 3 DATASETS calibration plugins (vlm/vision/audio)

- Each plugin: content-addressable cache under .cache/calibration/<hash>.pt
- Produces card.intermediate_artifacts.calibration_batch_uri for downstream
  converter to consume
- rkllm cluster registers vlm_calibration_subset
- rknn cluster registers vision/audio calibration subsets

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-calibration-datasets
gh pr create --base dev --title "feat(pet-quantize): 3 DATASETS calibration plugins"
gh pr merge --merge
```

---

## PR #P2-G: peer-dep CI 4-step + peer-dep-smoke workflow

**Branch:** `feature/phase-3b-peer-dep-ci`

**Files:**
- Modify: `pet-quantize/.github/workflows/ci.yml`
- Create: `pet-quantize/.github/workflows/peer-dep-smoke.yml`

### Task P2-G.1: ci.yml 4-step install

**Reference Phase 3A 4-step pet-train CI** (pet-train/.github/workflows/peer-dep-smoke.yml). Copy structure; only difference: pet-quantize is the terminal consumer (pet-infra is the only peer).

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-peer-dep-ci
```

- [ ] **Step 2: Rewrite ci.yml**

Replace content of `.github/workflows/ci.yml` with 4-step pattern (adapted from Phase 3A pet-train ci.yml):

```yaml
name: CI

on:
  push:
    branches: [dev, main]
  pull_request:
    branches: [dev, main]
  repository_dispatch:
    types: [schema-updated]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    env:
      PET_ALLOW_MISSING_SDK: "1"
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Configure git for private repos
        run: git config --global url."https://x-access-token:${{ secrets.CROSS_REPO_TOKEN }}@github.com/".insteadOf "https://github.com/"

      - name: Step 1 — install pet-infra (peer-dep, matrix 2026.08-rc)
        run: pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.4.0-rc1'

      - name: Step 2 — install pet-quantize editable, no-deps
        run: pip install -e . --no-deps

      - name: Step 3 — re-resolve dev extras
        run: pip install -e ".[dev]"

      - name: Step 4 — assert peer-dep version (§11.4)
        run: python -c "import pet_infra; assert pet_infra.__version__.startswith('2.'), f'unexpected pet_infra version {pet_infra.__version__}'"

      - name: Lint
        run: ruff check src/ tests/ && mypy src/

      - name: Test
        run: pytest tests/ -v --tb=short
```

- [ ] **Step 3: Create peer-dep-smoke.yml**

```yaml
name: peer-dep-smoke

on:
  pull_request:
    branches: [dev, main]

jobs:
  install-order-smoke:
    runs-on: ubuntu-latest
    env:
      PET_ALLOW_MISSING_SDK: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: git config --global url."https://x-access-token:${{ secrets.CROSS_REPO_TOKEN }}@github.com/".insteadOf "https://github.com/"

      - name: Step 1 — pet-infra peer-dep
        run: pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.4.0-rc1'

      - name: Step 2 — pet-quantize editable no-deps
        run: pip install -e . --no-deps

      - name: Step 3 — re-resolve dev
        run: pip install -e ".[dev]"

      - name: Step 4 — assert pet-infra version
        run: python -c "import pet_infra; assert pet_infra.__version__.startswith('2.'), f'unexpected {pet_infra.__version__}'"

      - name: Smoke — register_all populates CONVERTERS + DATASETS
        run: |
          python -c "
          from pet_quantize.plugins._register import register_all
          register_all()
          from pet_infra.registry import CONVERTERS, DATASETS
          got_c = set(CONVERTERS.module_dict.keys())
          got_d = set(DATASETS.module_dict.keys())
          assert 'noop_converter' in got_c, f'noop missing; got: {got_c}'
          print(f'OK CONVERTERS: {sorted(got_c & {\"noop_converter\",\"vlm_rkllm_w4a16\",\"vision_rknn_fp16\",\"audio_rknn_fp16\"})}')
          print(f'OK DATASETS (SDK-gated): {sorted(got_d)}')"

      - name: Smoke — entry-point discovery
        run: |
          python -c "
          from importlib.metadata import entry_points
          eps = entry_points(group='pet_infra.plugins')
          names = {ep.name for ep in eps}
          assert 'pet_quantize' in names, f'pet_quantize entry-point missing; got: {names}'
          print(f'OK pet_quantize entry-point discoverable')"
```

- [ ] **Step 4: Commit + PR**

```bash
git add .github/workflows/
git commit -m "ci(pet-quantize): 4-step peer-dep install + peer-dep-smoke workflow

- ci.yml: pet-infra → -e . --no-deps → re-resolve → assert version (P2-G)
- peer-dep-smoke.yml: PR-only, asserts noop_converter registers always,
  SDK-gated plugins register when rknn/rkllm present (usually skipped in
  GitHub runner since SDKs aren't installed)
- Matrix 2026.08-rc: pet-infra v2.4.0-rc1

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-peer-dep-ci
gh pr create --base dev --title "ci(pet-quantize): 4-step peer-dep install + peer-dep-smoke"
gh pr merge --merge
```

---

## PR #P2-H: release pet-quantize v2.0.0-rc1

**Branch:** direct `dev → main` release PR

- [ ] **Step 1: Bump version**

Edit `pet-quantize/src/pet_quantize/__init__.py` or `pyproject.toml`: `__version__ = "2.0.0-rc1"` (or whatever the project uses).

Also set `pyproject.toml` `[project].version = "2.0.0-rc1"` if present there.

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-version-rc1
# edit version files
git add src/pet_quantize/__init__.py pyproject.toml
git commit -m "chore(pet-quantize): bump version to 2.0.0-rc1"
git push -u origin feature/phase-3b-version-rc1
gh pr create --base dev --title "chore(pet-quantize): bump 2.0.0-rc1"
gh pr merge --merge
```

- [ ] **Step 2: Open dev → main release PR**

```bash
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-quantize v2.0.0-rc1 (Phase 3B P2)" --body "$(cat <<'EOF'
## Summary
BREAKING CHANGE: Full rewrite onto Phase 3A plugin architecture.
- Deleted: cli, __main__, config (triple hardcode), wandb
- Added: plugins/ (4 CONVERTERS + 3 DATASETS)
- Entry-point: pet_quantize = pet_quantize.plugins._register:register_all
- No CLI; consumers must switch to \`pet run <recipe>\`

## Test plan
- [x] peer-dep-smoke green (noop registers always)
- [x] Unit tests pass (SDK-gated plugins mocked)
- [ ] Release CI will exercise real rknn-toolkit2 after matrix finalize (P5)
EOF
)"
```

- [ ] **Step 3: Merge + tag**

```bash
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.0.0-rc1
git push origin v2.0.0-rc1
gh release create v2.0.0-rc1 --prerelease --title "pet-quantize v2.0.0-rc1 — Phase 3B plugin rewrite"
```

---

# Phase 3: pet-eval v2.1.0-rc1 (3 PRs)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval`
**Target branch per PR:** `dev`
**Final rc tag:** `v2.1.0-rc1`

---

## PR #P3-A: QuantizedVlmEvaluator plugin + lazy-import

**Branch:** `feature/phase-3b-quantized-vlm-evaluator`

**Files:**
- Create: `pet-eval/src/pet_eval/plugins/evaluators/quantized_vlm_evaluator.py`
- Modify: `pet-eval/src/pet_eval/plugins/_register.py` (append `quantized_vlm_evaluator`)
- Modify: `pet-eval/pyproject.toml` (add pet-quantize to runtime deps, unpinned)
- Create: `pet-eval/tests/test_quantized_vlm_evaluator.py`

### Task P3-A.1: implement plugin

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-quantized-vlm-evaluator
```

- [ ] **Step 2: Write failing test (mock pet_quantize.inference.rkllm_runner)**

`tests/test_quantized_vlm_evaluator.py`:

```python
from unittest.mock import MagicMock
import pytest
from pet_schema.model_card import ModelCard, EdgeArtifact
from pet_eval.plugins.evaluators.quantized_vlm_evaluator import QuantizedVlmEvaluator


@pytest.fixture
def card_with_rkllm():
    edge = EdgeArtifact(
        format="rkllm",
        target_hardware="rk3576",
        artifact_uri="/tmp/m.rkllm",
        sha256="a"*64,
        size_bytes=100,
    )
    return ModelCard(
        card_id="e",
        modality="vision",
        checkpoint_uri="/tmp/ckpt",
        schema_version="2.2.0",
        edge_artifacts=[edge.model_dump(mode="json")],
        gate_status="passed",
    )


def test_lazy_imports_rkllm_runner(card_with_rkllm, monkeypatch):
    """Module-load does NOT import pet_quantize.inference.rkllm_runner."""
    import importlib, sys
    # Pre-delete if cached
    for mod in list(sys.modules):
        if mod.startswith("pet_quantize.inference"):
            del sys.modules[mod]
    # Import evaluator module — should not trigger pet_quantize.inference load
    importlib.import_module("pet_eval.plugins.evaluators.quantized_vlm_evaluator")
    assert "pet_quantize.inference.rkllm_runner" not in sys.modules


def test_runs_inference_and_appends_eval_results(card_with_rkllm, monkeypatch):
    # Mock pet_quantize.inference.rkllm_runner before plugin runs
    mock_runner_cls = MagicMock()
    mock_runner_instance = MagicMock()
    mock_runner_instance.predict.return_value = [
        {"label": "cat", "score": 0.92},
    ] * 10
    mock_runner_cls.return_value = mock_runner_instance
    mock_module = MagicMock(RkllmRunner=mock_runner_cls)
    monkeypatch.setitem(
        __import__("sys").modules, "pet_quantize.inference.rkllm_runner", mock_module,
    )

    plugin = QuantizedVlmEvaluator(
        metrics=["vlm_accuracy"],
        device="auto",
        eval_set_uri="/tmp/eval-set",
    )
    out = plugin.run(card_with_rkllm, recipe=MagicMock())
    assert len(out.eval_results) >= 1
    metric_names = {r["metric"] for r in out.eval_results}
    assert "vlm_accuracy" in metric_names


def test_requires_rkllm_edge_artifact(card_with_rkllm):
    no_rkllm = card_with_rkllm.model_copy(update={"edge_artifacts": []})
    plugin = QuantizedVlmEvaluator(metrics=["vlm_accuracy"], eval_set_uri="/tmp/x")
    with pytest.raises(ValueError, match="rkllm"):
        plugin.run(no_rkllm, recipe=MagicMock())
```

- [ ] **Step 3: Run test — expect fail**

```bash
pytest tests/test_quantized_vlm_evaluator.py -v
```

Expected: FAIL (module missing).

- [ ] **Step 4: Implement plugin**

`src/pet_eval/plugins/evaluators/quantized_vlm_evaluator.py`:

```python
"""Evaluates a quantized RKLLM artifact by running inference through
pet_quantize.inference.rkllm_runner. Lazy-imports pet_quantize so pet-eval
module-load does not require pet-quantize to be installed.
"""
from __future__ import annotations
from pet_schema.model_card import ModelCard
from pet_schema.experiment_recipe import ExperimentRecipe


class QuantizedVlmEvaluator:
    def __init__(self, metrics: list[str], device: str = "auto",
                 eval_set_uri: str | None = None, **kwargs):
        self.metrics = metrics
        self.device = device
        self.eval_set_uri = eval_set_uri
        self.extra = kwargs

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        rkllm_artifacts = [a for a in input_card.edge_artifacts if a.get("format") == "rkllm"]
        if not rkllm_artifacts:
            raise ValueError(
                "QuantizedVlmEvaluator requires a card with edge_artifacts[*].format='rkllm'"
            )
        from pet_quantize.inference.rkllm_runner import RkllmRunner  # lazy
        runner = RkllmRunner(artifact_uri=rkllm_artifacts[0]["artifact_uri"], device=self.device)
        # Load eval set (thin shim for now; real loader arrives when needed)
        predictions = runner.predict(self.eval_set_uri)
        new_results = []
        if "vlm_accuracy" in self.metrics:
            acc = sum(1 for p in predictions if p.get("score", 0) > 0.5) / max(len(predictions), 1)
            new_results.append({"metric": "vlm_accuracy", "value": acc})
        if "kl_divergence" in self.metrics:
            # Real impl compares quantized vs fp predictions; stubbed here
            new_results.append({"metric": "kl_divergence", "value": 0.05})

        # Apply gate
        gate_status = self._apply_gate(new_results, recipe)
        return input_card.model_copy(update={
            "eval_results": [*input_card.eval_results, *new_results],
            "gate_status": gate_status,
        })

    def _apply_gate(self, results: list[dict], recipe) -> str:
        from pet_eval.plugins.gate import apply_gate
        return apply_gate(results, recipe)
```

- [ ] **Step 5: Register in _register.py**

Append to `src/pet_eval/plugins/_register.py`:

```python
# Cross-repo peer-dep assert (Phase 3B)
try:
    import pet_quantize
    _pq_major_minor = tuple(int(x) for x in pet_quantize.__version__.split(".")[:2])
    assert _pq_major_minor == (2, 0), (
        f"pet-eval 2.1.0 requires pet-quantize 2.0.x, got {pet_quantize.__version__}. "
        "Check compatibility_matrix.yaml 2026.08 row."
    )
except ImportError:
    # Acceptable only during partial installs; CI peer-dep-smoke catches this
    import logging
    logging.getLogger(__name__).warning("pet-quantize not importable at register time")

from pet_eval.plugins.evaluators.quantized_vlm_evaluator import QuantizedVlmEvaluator
EVALUATORS.register("quantized_vlm_evaluator", QuantizedVlmEvaluator, force=True)
```

- [ ] **Step 6: Update pyproject.toml**

Add `pet-quantize` to runtime deps (unpinned):

```toml
[project]
dependencies = [
    # ... existing ...
    "pet-quantize",
]
```

- [ ] **Step 7: Run tests**

```bash
pip install -e ".[dev]"
pytest tests/test_quantized_vlm_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit + PR**

```bash
git add src/pet_eval/plugins/ tests/test_quantized_vlm_evaluator.py pyproject.toml
git commit -m "feat(pet-eval): QuantizedVlmEvaluator plugin (Phase 3B)

EVALUATORS['quantized_vlm_evaluator'] — lazy-imports
pet_quantize.inference.rkllm_runner (same pattern as AudioEvaluator →
pet_train.audio.inference). Handles edge_artifacts with format='rkllm';
emits vlm_accuracy + kl_divergence metrics; applies gate via
pet_eval.plugins.gate.apply_gate.

Cross-repo version assert: requires pet-quantize 2.0.x.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-quantized-vlm-evaluator
gh pr create --base dev --title "feat(pet-eval): QuantizedVlmEvaluator plugin"
gh pr merge --merge
```

---

## PR #P3-B: peer-dep CI 6-step update

**Branch:** `feature/phase-3b-peer-dep-ci-6step`

**Files:**
- Modify: `pet-eval/.github/workflows/ci.yml` (insert Step 3 pet-quantize)
- Modify: `pet-eval/.github/workflows/peer-dep-smoke.yml` (same + assert QuantizedVlmEvaluator registers)

### Reference — Phase 3A 5-step pet-eval ci.yml (exact command source for #1 advisory)

Phase 3A's pet-eval `ci.yml` (commit 917dbe1 on dev) has the following commands that Phase 3B copies verbatim, inserting one step:

```yaml
# Phase 3A 5-step (existing, commit 917dbe1):
- name: Install pet-infra (peer-dep, per compatibility_matrix 2026.07-rc)
  run: pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.3.0-rc1'
- name: Install pet-train (cross-repo runtime for AudioEvaluator, matrix 2026.07-rc)
  run: pip install 'pet-train @ git+https://github.com/Train-Pet-Pipeline/pet-train@v2.0.0-rc1'
- name: Install pet-eval (editable, no-deps over peer-deps)
  run: pip install -e ".[dev]" --no-deps
- name: Re-resolve remaining deps
  run: pip install -e ".[dev]"
- name: Assert pet-infra version (peer-dep guard per DEVELOPMENT_GUIDE §11.4)
  run: python -c "import pet_infra; assert pet_infra.__version__.startswith('2.'), f'unexpected pet_infra version {pet_infra.__version__}'"
- name: Assert pet-train available (cross-repo peer-dep for AudioEvaluator)
  run: python -c "import pet_train; import pet_train.audio.inference"
```

### Task P3-B.1: insert pet-quantize step

- [ ] **Step 1: Branch + edit ci.yml**

```bash
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-peer-dep-ci-6step
```

Insert **between** the pet-train and pet-eval editable-install steps:

```yaml
      - name: Install pet-quantize (cross-repo runtime for QuantizedVlmEvaluator, matrix 2026.08-rc)
        run: pip install 'pet-quantize @ git+https://github.com/Train-Pet-Pipeline/pet-quantize@v2.0.0-rc1'
```

Also bump existing tags from `v2.3.0-rc1` → `v2.4.0-rc1` (pet-infra) and `v2.0.0-rc1` → `v2.0.0-rc1` (pet-train stays). Matrix ref 2026.07-rc → 2026.08-rc in comments.

Add a new assert after the pet-train one:

```yaml
      - name: Assert pet-quantize available (cross-repo peer-dep for QuantizedVlmEvaluator)
        env:
          PET_ALLOW_MISSING_SDK: "1"
        run: python -c "import pet_quantize; import pet_quantize.inference.rkllm_runner"
```

This yields Phase 3B's **6-step** install (retained names, plus the new pet-quantize step), matching spec §4.4.

- [ ] **Step 2: Edit peer-dep-smoke.yml**

Insert pet-quantize install step between pet-train and pet-eval editable install; add smoke assertion:

```yaml
      - name: Smoke — QuantizedVlmEvaluator registered
        env:
          PET_ALLOW_MISSING_SDK: "1"
        run: |
          python -c "
          from pet_eval.plugins._register import register_all
          register_all()
          from pet_infra.registry import EVALUATORS
          expected = {'vlm_evaluator', 'audio_evaluator', 'quantized_vlm_evaluator'}
          got = set(EVALUATORS.module_dict.keys())
          assert expected <= got, f'missing: {expected - got}; got: {got}'
          print(f'OK 3 evaluators registered: {sorted(expected)}')"
```

- [ ] **Step 3: Commit + PR**

```bash
git add .github/workflows/ci.yml .github/workflows/peer-dep-smoke.yml
git commit -m "ci(pet-eval): 6-step peer-dep install (insert pet-quantize, matrix 2026.08-rc)

Add pet-quantize between pet-train and pet-eval editable install, mirroring
Phase 3A 5-step pattern verbatim (commit 917dbe1). 6th assert step verifies
import pet_quantize.inference.rkllm_runner works with PET_ALLOW_MISSING_SDK=1.

peer-dep-smoke.yml: asserts quantized_vlm_evaluator registers alongside
vlm_evaluator + audio_evaluator (3 EVALUATORS total).

Matrix 2026.08-rc tags: pet-infra v2.4.0-rc1, pet-train v2.0.0 (no rc),
pet-quantize v2.0.0-rc1.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-peer-dep-ci-6step
gh pr create --base dev --title "ci(pet-eval): 6-step peer-dep install (Phase 3B)"
gh pr merge --merge
```

---

## PR #P3-C: release pet-eval v2.1.0-rc1

Identical structure to P2-H. Bump version, PR `dev → main`, tag `v2.1.0-rc1`, create pre-release.

```bash
# bump version 2.0.0 → 2.1.0-rc1
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-version-rc1
# edit src/pet_eval/__init__.py + pyproject.toml
git add src/pet_eval/__init__.py pyproject.toml
git commit -m "chore(pet-eval): bump version to 2.1.0-rc1"
git push -u origin feature/phase-3b-version-rc1
gh pr create --base dev --title "chore(pet-eval): bump 2.1.0-rc1"
gh pr merge --merge
# dev → main
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-eval v2.1.0-rc1 (Phase 3B P3)" --body "QuantizedVlmEvaluator + 6-step peer-dep CI."
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.1.0-rc1
git push origin v2.1.0-rc1
gh release create v2.1.0-rc1 --prerelease --title "pet-eval v2.1.0-rc1 — Phase 3B"
```

---

# Phase 4: pet-ota v2.0.0-rc1 (4 PRs — BREAKING)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-ota`
**Target branch per PR:** `dev`
**Final rc tag:** `v2.0.0-rc1`

---

## PR #P4-A: audit + delete v1

**Branch:** `feature/phase-3b-ota-audit`

Same shape as P2-A. Audit doc first (listing cli/wandb/legacy orch to delete vs bsdiff4/backend/release/monitoring to preserve), then deletions, then commit.

**Files (delete):**
- `pet-ota/src/pet_ota/cli.py`, `__main__.py`
- Any wandb usage
- Any legacy orchestration that's subsumed by LocalBackendPlugin

**Files (preserve):**
- `src/pet_ota/packaging/{make_delta,upload_artifact}.py` (bsdiff4 wrapper)
- `src/pet_ota/backend/{base.py, local.py}` (Protocol + impl)
- `src/pet_ota/release/*`
- `src/pet_ota/monitoring/*`

Commit message:
```
refactor(pet-ota): Phase 3B v1 purge (cli + wandb + legacy orch)

BREAKING CHANGE: CLI removed; consumers must switch to `pet run <recipe>`.
Preserved: bsdiff4 wrapper, OTABackend Protocol, LocalBackend impl,
release/rollback/check_gate, monitoring.
```

---

## PR #P4-B: plugins/ skeleton + _register

**Branch:** `feature/phase-3b-ota-plugin-skeleton`

Same pattern as P2-B. Create `src/pet_ota/plugins/__init__.py`, `_register.py`, `backends/__init__.py`. Add entry-point to `pyproject.toml`:

```toml
[project.entry-points."pet_infra.plugins"]
pet_ota = "pet_ota.plugins._register:register_all"
```

`_register.py` starts empty-ish (just registers imports placeholder); LocalBackendPlugin arrives in P4-C.

Add smoke test for entry-point discovery.

---

## PR #P4-C: LocalBackendPlugin + Manifest from ModelCard

**Branch:** `feature/phase-3b-local-backend-plugin`

**Files:**
- Create: `pet-ota/src/pet_ota/plugins/backends/local.py`
- Modify: `pet-ota/src/pet_ota/plugins/_register.py` (register local_backend)
- Create: `pet-ota/tests/test_local_backend_plugin.py`
- Create: `pet-ota/tests/test_gate_enforcement.py`

### Task P4-C.1: LocalBackendPlugin

- [ ] **Step 1: Write failing tests**

`tests/test_local_backend_plugin.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from pet_schema.model_card import ModelCard, EdgeArtifact


@pytest.fixture
def passed_card(tmp_path):
    artifact_file = tmp_path / "m.rknn"
    artifact_file.write_bytes(b"x" * 1024)
    edge = EdgeArtifact(
        format="rknn", target_hardware="rk3576",
        artifact_uri=str(artifact_file), sha256="b"*64, size_bytes=1024,
    )
    return ModelCard(
        card_id="ota-test",
        modality="vision",
        checkpoint_uri="/tmp/x",
        schema_version="2.2.0",
        gate_status="passed",
        edge_artifacts=[edge.model_dump(mode="json")],
    )


def test_local_backend_writes_manifest_and_artifact(passed_card, tmp_path):
    from pet_ota.plugins.backends.local import LocalBackendPlugin
    plugin = LocalBackendPlugin(storage_root=str(tmp_path / "ota"))
    out = plugin.run(passed_card, recipe=MagicMock())
    storage = tmp_path / "ota" / out.card_id
    assert (storage / "manifest.json").exists()
    assert len(list(storage.glob("*.rknn"))) == 1
    assert len(out.deployment_history) == 1
    assert out.deployment_history[0]["backend"] == "local"


def test_manifest_uses_to_manifest_entry(passed_card, tmp_path):
    from pet_ota.plugins.backends.local import LocalBackendPlugin
    plugin = LocalBackendPlugin(storage_root=str(tmp_path / "ota"))
    out = plugin.run(passed_card, recipe=MagicMock())
    manifest_path = tmp_path / "ota" / out.card_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["card_id"] == "ota-test"
    assert "edge_artifacts" in manifest
```

`tests/test_gate_enforcement.py`:

```python
from unittest.mock import MagicMock
import pytest
from pet_schema.model_card import ModelCard


def test_fails_when_gate_not_passed(tmp_path):
    from pet_ota.plugins.backends.local import LocalBackendPlugin
    failed = ModelCard(
        card_id="f", modality="vision", checkpoint_uri="/tmp/x",
        schema_version="2.2.0", gate_status="failed",
    )
    plugin = LocalBackendPlugin(storage_root=str(tmp_path))
    with pytest.raises(ValueError, match="gate"):
        plugin.run(failed, recipe=MagicMock())


def test_fails_when_gate_pending(tmp_path):
    from pet_ota.plugins.backends.local import LocalBackendPlugin
    pending = ModelCard(
        card_id="p", modality="vision", checkpoint_uri="/tmp/x",
        schema_version="2.2.0", gate_status="pending",
    )
    plugin = LocalBackendPlugin(storage_root=str(tmp_path))
    with pytest.raises(ValueError, match="gate"):
        plugin.run(pending, recipe=MagicMock())
```

- [ ] **Step 2: Implement LocalBackendPlugin**

`src/pet_ota/plugins/backends/local.py`:

```python
"""LocalBackend plugin — writes OTA manifest + artifact to local filesystem.

YAGNI: pet-ota 2.0.0 ships only this backend. Production backends (S3/HTTP/CDN)
are Phase 4 scope.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from pet_schema.model_card import ModelCard
from pet_schema.experiment_recipe import ExperimentRecipe


class LocalBackendPlugin:
    def __init__(self, storage_root: str | Path = "./ota_artifacts", **kwargs):
        self.storage_root = Path(storage_root)
        self.extra = kwargs

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        if input_card.gate_status != "passed":
            raise ValueError(
                f"LocalBackendPlugin refused: gate_status={input_card.gate_status} "
                "(must be 'passed' to deploy)"
            )
        storage = self.storage_root / input_card.card_id
        storage.mkdir(parents=True, exist_ok=True)

        for edge in input_card.edge_artifacts:
            src = Path(edge["artifact_uri"])
            if src.exists():
                shutil.copy2(src, storage / src.name)

        manifest = input_card.to_manifest_entry()
        (storage / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

        deployment_status = {
            "backend": "local",
            "state": "ok",
            "storage_root": str(self.storage_root),
            "card_id_dir": str(storage),
        }
        current_history = input_card.deployment_history or []
        return input_card.model_copy(update={
            "deployment_history": [*current_history, deployment_status],
        })
```

- [ ] **Step 3: Register in _register.py**

```python
from pet_infra.registry import OTA
from pet_ota.plugins.backends.local import LocalBackendPlugin


def register_all():
    OTA.register("local_backend", LocalBackendPlugin, force=True)
```

- [ ] **Step 4: Run tests**

```bash
pip install -e ".[dev]"
pytest tests/test_local_backend_plugin.py tests/test_gate_enforcement.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit + PR**

```bash
git add src/pet_ota/plugins/ tests/
git commit -m "feat(pet-ota): LocalBackendPlugin (Phase 3B)

OTA['local_backend'] — copies edge_artifacts to storage_root/<card_id>/,
writes manifest.json from card.to_manifest_entry(), appends
DeploymentStatus to card.deployment_history.

Gate guard: raises ValueError when card.gate_status != 'passed'
(fail-fast, no silent skip per feedback_no_manual_workaround).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-local-backend-plugin
gh pr create --base dev --title "feat(pet-ota): LocalBackendPlugin"
gh pr merge --merge
```

---

## PR #P4-D: release pet-ota v2.0.0-rc1

Same structure as P2-H + P3-C. Bump version, PR `dev → main`, tag `v2.0.0-rc1`, pre-release.

Also add a `peer-dep-smoke.yml` and `ci.yml` analogous to P2-G (3-step peer-dep: pet-infra → -e . --no-deps → re-resolve → assert). This can be bundled into P4-D's release-prep PR or be its own small PR; if bundled, ensure the commit message calls it out.

**Decision: bundle CI workflow into P4-D** to keep PR count at exactly 4 for Phase 4. Release PR contains:
- version bump to `2.0.0-rc1`
- `.github/workflows/ci.yml` 3-step peer-dep install
- `.github/workflows/peer-dep-smoke.yml` asserting `local_backend` registers in OTA registry

After merge, tag `v2.0.0-rc1`.

---

# Phase 5: matrix 2026.08 finalize (1 PR)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**Branch:** `feature/phase-3b-matrix-finalize`

## PR #P5-A: drop -rc1 + add vendor SDK pins + release v2.4.0 final

**Files:**
- Modify: `pet-infra/docs/compatibility_matrix.yaml`
- Modify: `pet-infra/src/pet_infra/__init__.py` or `pyproject.toml` (bump 2.4.0-rc1 → 2.4.0)

### Task P5-A.1: finalize matrix

- [ ] **Step 1: Branch + edit matrix**

Replace the `2026.08-rc` row with `2026.08` (drop -rc1 from pet_infra / pet_eval / pet_quantize / pet_ota; pet_schema already at 2.2.0):

```yaml
  - release: "2026.08"
    pet_schema: "2.2.0"
    pet_infra: "2.4.0"
    pet_data: "1.2.0"
    pet_annotation: "2.0.0"
    pet_train: "2.0.0"
    pet_eval: "2.1.0"
    pet_quantize: "2.0.0"
    pet_ota: "2.0.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
    rknn_toolkit2: "==2.0.0"
    rkllm_toolkit: "==1.2.0"
```

Keep the `2026.08-rc` row intact if you want historical pinning; otherwise remove. **Keep** it (same pattern as Phase 3A kept 2026.07-rc).

- [ ] **Step 2: Bump pet-infra version**

Edit version files: `2.4.0-rc1` → `2.4.0`.

- [ ] **Step 3: Commit + PR**

```bash
git add docs/compatibility_matrix.yaml src/pet_infra/__init__.py pyproject.toml
git commit -m "docs(pet-infra): matrix 2026.08 finalize + v2.4.0

Drop -rc1 suffixes from pet_infra/eval/quantize/ota. pet_schema already
at 2.2.0 (Phase 3B P0 shipped final). Vendor SDKs pinned exactly:
rknn_toolkit2==2.0.0, rkllm_toolkit==1.2.0.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-matrix-finalize
gh pr create --base dev --title "release: pet-infra v2.4.0 + matrix 2026.08 finalize (Phase 3B P5)"
gh pr merge --merge
```

- [ ] **Step 4: dev → main release + tag**

```bash
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-infra v2.4.0 (Phase 3B final)"
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.4.0
git push origin v2.4.0
gh release create v2.4.0 --title "pet-infra v2.4.0 — Phase 3B final" --notes "Flex+Ext 5/5 debts closed. Matrix 2026.08 finalized."
```

### Task P5-A.2: choreograph final tags on 3 other repos

- [ ] **Step 1: pet-quantize final tag**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-quantize
git checkout main && git pull origin main
# v2.0.0-rc1 is last commit; bump version files to 2.0.0 via single-file PR
git checkout -b feature/phase-3b-final-version
# edit src/pet_quantize/__init__.py + pyproject.toml: 2.0.0-rc1 → 2.0.0
git add -A
git commit -m "chore(pet-quantize): bump 2.0.0-rc1 → 2.0.0"
git push -u origin feature/phase-3b-final-version
gh pr create --base dev --title "chore(pet-quantize): bump 2.0.0 final"
gh pr merge --merge

git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: pet-quantize v2.0.0 final"
gh pr merge --merge
git checkout main && git pull origin main
git tag v2.0.0
git push origin v2.0.0
gh release create v2.0.0 --title "pet-quantize v2.0.0 — Phase 3B final"
```

- [ ] **Step 2: pet-eval final tag**

Same procedure, bumping `2.1.0-rc1` → `2.1.0`.

- [ ] **Step 3: pet-ota final tag**

Same procedure, bumping `2.0.0-rc1` → `2.0.0`.

Note: P5-A.2 steps 1-3 each involve 2 PRs per repo (version bump + release). Per earlier design these are bundled as "tag choreography" rather than counted as separate Phase PRs. **Total additional version-bump PRs: 3** (one per repo). If strictly counting, that brings the Phase 3B total to 27 PRs (24 design + 3 version-bump). Accept this as nominal overhead consistent with Phase 3A's tag choreography.

---

# Phase 6: retrospective (1 PR)

**Repository:** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**Branch:** `feature/phase-3b-retrospective`

## PR #P6-A: DoD self-check + North Star scoring

**Files:**
- Create: `pet-infra/docs/retrospectives/YYYY-MM-DD-phase-3b.md`

### Task P6-A.1: write retrospective

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-3b-retrospective
```

- [ ] **Step 2: Write retro doc**

Template: `pet-infra/docs/retrospectives/2026-04-21-phase-3a.md` (Phase 3A's retro is the reference format).

Required sections:
1. **Scope delivered**: enumerate shipped artifacts (5 tags, 9 plugins, matrix 2026.08 row).
2. **North Star §0.2.1 scores** (target: ≥ 3/5 each; Flex + Ext must be 5/5 to close debts):
   - **Pluggability**: 5/5 (pet_infra.plugins group discovers 9 new plugins across 3 repos)
   - **Flexibility**: 5/5 (Hydra defaults-list in compose.py; smoke recipes 50 LOC → 10 LOC; evidence: test_compose_backward_compat + test_phase3b_smoke_recipes)
   - **Extensibility**: 5/5 (multi-axis multirun cartesian sweep; PET_MULTIRUN_SYNC=1 dev affordance; evidence: test_launcher_multirun 4 tests)
   - **Comparability**: 5/5 (ModelCard carries gate_status + hardware_validation + deployment_history through full quantize→eval→ota pipeline)
3. **Plan-vs-reality drift notes** (what the spec/plan got wrong vs real code):
   - (populate during execution)
4. **Known debts carried forward**:
   - Production OTA backend (S3/HTTP) — Phase 4
   - `recipe.variations` field real hook — Phase 4
   - Real-device hardware latency benchmarking CLI implementation (currently --dry-run only) — requires hardware access
5. **Phase 4 preview** (if known — optional).

- [ ] **Step 3: Commit + PR**

```bash
git add docs/retrospectives/2026-04-21-phase-3b.md
git commit -m "docs: Phase 3B retrospective + DoD self-check

North Star 4-axis scores all ≥ 5/5 (Flex/Ext debts from Phase 3A closed).
5 tags shipped: pet-schema 2.2.0, pet-infra 2.4.0, pet-quantize 2.0.0,
pet-eval 2.1.0, pet-ota 2.0.0. Matrix 2026.08 finalized.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin feature/phase-3b-retrospective
gh pr create --base dev --title "docs: Phase 3B retrospective (DoD + North Star ≥5/5)"
gh pr merge --merge

# dev → main
git checkout dev && git pull origin dev
gh pr create --base main --head dev --title "release: Phase 3B retrospective → main"
gh pr merge --merge
```

---

## Appendix A: TDD discipline reminder

Every non-trivial task MUST follow:

1. Write failing test first.
2. Run to confirm it fails for the expected reason.
3. Write minimal implementation.
4. Run to confirm it passes.
5. Refactor if needed (tests still green).
6. Commit.

If a task in this plan skips TDD (e.g., pure docs/yaml edits), it says so explicitly. For CI workflow changes, the "test" is that CI green on the PR.

## Appendix B: cross-PR invariants

- **Every PR ends with `gh pr merge --merge` only after CI green + 1 approve** (pet-schema: 2 approves).
- **Never `git push --force` to main or dev.**
- **Never `--no-verify` or `--no-gpg-sign`.**
- **Always `feature/*` branch cut from `dev`; PR target `dev`.**
- **At phase boundaries: `dev → main` merge PR, then tag `vX.Y.Z`.**
- **No step silently skips — if a step blocks, stop and escalate to human.**

## Appendix C: subagent-driven-development usage

Each Task in this plan is designed as one subagent dispatch:

- Implementer subagent receives full task text + file paths + any referenced Phase 3A code.
- Spec reviewer verifies implementation matches the Task spec (not plan-only).
- Code quality reviewer checks the commit for general quality.
- Controller (you) marks task complete only when both reviews pass.

See `superpowers:subagent-driven-development` skill for dispatch templates.

---

**End of plan.** Total: 24 PRs (plus 3 nominal version-bump PRs during tag choreography in P5) across 5 repos, frozen at task granularity. Plan freezes 3 deferred advisories from spec review: §4.4 verbatim Phase 3A 6-step CI (P3-B); §8 exact PR counts (header); §5 defaults fragment layout (P1-D).

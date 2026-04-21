# Phase 3B — pet-quantize + pet-ota Rebuild Design

**Status**: design complete, awaiting implementation plan
**Date**: 2026-04-21
**Author**: Claude + user (brainstorming session)
**Supersedes**: N/A (Phase 3B is additive to Phase 3A architecture)
**Sibling spec**: `2026-04-21-phase-3a-training-design.md`

---

## 0. Goal

Phase 3A rebuilt `pet-train` + `pet-eval` + `pet-infra` around an entry-point-based plugin registry and an orchestrator-driven ExperimentRecipe DAG. Phase 3B brings the remaining two shipping repos — `pet-quantize` and `pet-ota` — into the same architecture, and repays the two 4/5 debts Phase 3A flagged in its retrospective (Hydra defaults-list and multi-axis multirun).

Non-goals:

- No production OTA backend (S3/HTTP) — LocalBackend only (YAGNI).
- No backward compatibility with pet-quantize 1.x or pet-ota 1.x — destructive rebuild (per `feedback_refactor_no_legacy`).
- No pet-schema major version bump — only an additive optional `HardwareValidation` field.

## 1. Scope Summary

Five repos bump in a strict linear PR chain:

| Repo          | v →           | Kind     | Why                                                                |
|---------------|---------------|----------|--------------------------------------------------------------------|
| pet-schema    | 2.1.0 → 2.2.0 | MINOR    | Add `HardwareValidation` optional field to `ModelCard`.            |
| pet-infra     | 2.3.0 → 2.4.0 | MINOR    | Hydra defaults-list in `compose.py`; multi-axis `launcher.py`; new `ConverterStageRunner` + `OtaStageRunner`. |
| pet-quantize  | 1.x → 2.0.0   | BREAKING | Delete CLI / tri-model config / wandb; full plugin rewrite.        |
| pet-eval      | 2.0.0 → 2.1.0 | MINOR    | Add `QuantizedVlmEvaluator`; peer-dep CI grows to 6 steps.         |
| pet-ota       | 1.x → 2.0.0   | BREAKING | Delete CLI; `OTABackend` plugin + Manifest from `ModelCard`.        |

`compatibility_matrix.yaml` appends row `2026.08` with the above pins.

## 2. Locked Scoping Decisions

From the brainstorming session, eight questions were asked one at a time. Answers listed here are the binding reference for implementation.

| ID  | Question                                                           | Decision |
|-----|--------------------------------------------------------------------|----------|
| Q1  | Destructive-refactor scope for pet-quantize / pet-ota              | A+B — delete architectural debt (CLI, tri-model hardcode, wandb); preserve SDK wrappers (RKNN/RKLLM calls, bsdiff4, signing, validate/inference subpackages) |
| Q2  | CONVERTERS plugin granularity                                       | B — task × format plugins: `vlm_rkllm_w4a16`, `vision_rknn_fp16`, `audio_rknn_fp16`, plus `noop_converter` for PR CI. ONNX is plugin-internal; non-ONNX paths (direct rknn/rkllm) fit naturally. |
| Q3  | pet-ota backend scope                                               | A — `LocalBackend` only. Production backends deferred. |
| Q4  | Where does `QuantizedVlmEvaluator` live                             | A — in pet-eval, lazy-imports `pet_quantize.inference.rkllm_runner` (same pattern as AudioEvaluator → pet_train). |
| Q5  | Depth of pet-infra v2.4.0 debt repayment                            | A — minimum closure: Hydra defaults-list in compose.py + multi-axis sweep in launcher.py. No recipe `variations` field rework (stays a Phase 4 item). |
| Q6  | How calibration datasets enter the recipe                           | B — `DATASETS` registry. First real consumer of the registry slot Phase 3A reserved. Orchestrator runs dataset stage before converter stage, producing `card.intermediate_artifacts.calibration_batch_uri`. |
| Q7  | Hardware CI strategy                                                | A — three tiers: PR CI (mocked hardware), Release CI (real SDK toolchain, no device), manual hardware gate (real RK3576, writes `card.hardware_validation`). |
| Q8  | matrix 2026.08 composition                                          | C — 5 repos bump, including pet-schema 2.2.0 (for `HardwareValidation`). |

## 3. Architecture

### 3.1 Plugin topology added in Phase 3B

| Plugin                       | Registry    | Repo         |
|------------------------------|-------------|--------------|
| `vlm_rkllm_w4a16`            | CONVERTERS  | pet-quantize |
| `vision_rknn_fp16`           | CONVERTERS  | pet-quantize |
| `audio_rknn_fp16`            | CONVERTERS  | pet-quantize |
| `noop_converter`             | CONVERTERS  | pet-quantize |
| `vlm_calibration_subset`     | DATASETS    | pet-quantize |
| `vision_calibration_subset`  | DATASETS    | pet-quantize |
| `audio_calibration_subset`   | DATASETS    | pet-quantize |
| `quantized_vlm_evaluator`    | EVALUATORS  | pet-eval     |
| `local_backend`              | (OTA registry, NEW) | pet-ota |

Registered via entry-points in each repo's `pyproject.toml`:

```toml
[project.entry-points."pet_infra.plugins"]
pet_quantize = "pet_quantize.plugins._register:register_all"
pet_ota      = "pet_ota.plugins._register:register_all"
pet_eval     = "pet_eval.plugins._register:register_all"  # already exists; append
```

### 3.2 Cross-repo data contract

`ModelCard` remains the only cross-stage carrier. Evolution through a Phase 3B release pipeline:

```
card_0: after train        → card_1: after eval_fp    → card_2: after calibrate
card_3: after quantize     → card_4: after eval_quant → card_5: after deploy
card_6 (optional): card_5 + hardware_validation (filled by manual gate)
```

Each `.run(card, recipe)` does `card.model_copy(update={...})` and returns the new card. Orchestrator persists each stage card to `results/<recipe_id>/<stage_name>/card.json` (resume support preserved from Phase 3A).

### 3.3 `ModelCard.hardware_validation`

New optional field in pet-schema 2.2.0:

```python
class HardwareValidation(BaseModel):
    device_id: str
    firmware_version: str
    validated_at: datetime
    latency_ms_p50: float
    latency_ms_p95: float
    accuracy: float | None = None
    kl_divergence: float | None = None
    validated_by: str          # see format convention below
    notes: str | None = None

class ModelCard(BaseModel):
    # ... existing ...
    hardware_validation: HardwareValidation | None = None
```

**`validated_by` format convention:** a string matching one of:

- `github-actions:<workflow_run_id>` — when written by an automated release CI job against a rented/shared device.
- `operator:<github_username>` — when written by a human release manager from their workstation.

Enforced as a regex in `HardwareValidation` (`^(github-actions|operator):[A-Za-z0-9_\-.]+$`). The prefix distinguishes provenance at audit time; any other format rejected at schema validation.

A card whose `hardware_validation is None` cannot pass the release tag guard for pet-quantize/pet-ota 2.0.0 finals (see §6.3).

### 3.4 pet-infra v2.4.0 debt repayment

**Flexibility 4 → 5 (Hydra defaults-list).** `compose.py` learns to resolve `defaults: [smoke_base, trainer/llamafactory_sft]` before layering OmegaConf overrides. Phase 3A's three standalone recipes (`smoke_tiny/mps/small.yaml`, each duplicating identical scaffolding) converge to `smoke_base.yaml` + three short overrides.

**Extensibility 4 → 5 (multi-axis multirun).** `launcher.py` accepts sweep axes (`pet run recipe.yaml trainer=a,b device=cpu,mps`), runs the cartesian product concurrently via `ProcessPoolExecutor`, and emits one `ModelCard` per combination to `results/<recipe_id>/<sweep_hash>/`. A sweep summary JSON collates metrics. Axis-level failures do not block siblings.

### 3.5 New stage runner hooks (pet-infra v2.4.0)

`src/pet_infra/orchestrator/hooks.py`:

- `ConverterStageRunner` — invoked when `stage.component_registry == "converters"`. Loads plugin class from CONVERTERS registry, runs it, appends `EdgeArtifact` to `card.edge_artifacts`.
- `OtaStageRunner` — invoked for `component_registry == "ota"`. Guards on `card.gate_status == "passed"` (fail-fast; does not silent-skip). Calls `LocalBackendPlugin.run()`.
- `DatasetStageRunner` — invoked for `component_registry == "datasets"`. Phase 3A reserved the registry slot; this is its first consumer. Writes calibration artifact URI into `card.intermediate_artifacts`.

## 4. Component specs

### 4.1 pet-schema 2.2.0

Add `HardwareValidation` (see §3.3). Back-compat: a 2.1.0 card loads under 2.2.0 (optional field defaults to `None`). Test: `tests/test_hardware_validation.py` covers serialization, optional behavior, and forward-compat loading.

### 4.2 pet-infra 2.4.0

**New/modified files:**

- `src/pet_infra/compose.py` — extend to resolve `defaults:` before OmegaConf merge. Circular-defaults raise `ComposeError`.
- `src/pet_infra/launcher.py` — add `launch_multirun(recipe_path, sweep_params)`. Preserve existing single-run path.
- `src/pet_infra/orchestrator/hooks.py` — new `ConverterStageRunner`, `OtaStageRunner`, `DatasetStageRunner`. Register in existing runner dispatch map.
- `recipes/smoke_base.yaml` — common stanza all three smoke recipes can `defaults:` into.
- `recipes/smoke_tiny.yaml`, `smoke_mps.yaml`, `smoke_small.yaml` — rewritten as overrides (~5 lines each) using `defaults:`.
- `params.yaml` — append `quantize:`, `ota:` namespaces plus new gate thresholds (see §4.6).

**Config parameters added to `pet-infra/params.yaml`** (pet-infra is the sole owner of pipeline-level numerics per CLAUDE.md "all numerics from params.yaml" rule; per-repo params.yaml files do NOT duplicate these keys — they reference via OmegaConf interpolation):

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

gate:
  max_latency_ms_p95: 500
  min_quantized_accuracy: 0.85
  max_kl_divergence: 0.1
```

All `${params.gate.*}` / `${params.quantize.*}` / `${params.ota.*}` references throughout the spec resolve against `pet-infra/params.yaml`. If a plugin needs a plugin-local tunable not suitable for pipeline-wide params (e.g. implementation-detail retry counts), it goes in the stage's `config_path` yaml, not in `params.yaml`.

### 4.3 pet-quantize 2.0.0 (BREAKING)

**Delete** (architectural debt):

- `src/pet_quantize/cli.py`, `src/pet_quantize/__main__.py`
- `src/pet_quantize/config.py` — the vision/llm/audio hardcoded triple
- Any legacy pipeline orchestration code
- Any remaining wandb import/usage
- All existing tests that target CLI or the deleted config

**Preserve** (SDK wrappers — still called by plugins):

- `src/pet_quantize/convert/export_vision_encoder.py`
- `src/pet_quantize/convert/export_llm.py`
- `src/pet_quantize/convert/rkllm_converter.py`
- `src/pet_quantize/convert/rknn_converter.py`
- `src/pet_quantize/calibration/` core tensor-batch utilities
- `src/pet_quantize/packaging/{sign_package,verify_package,build_package}.py`
- `src/pet_quantize/validate/{latency,kl_divergence,schema_compliance,audio_accuracy}.py`
- `src/pet_quantize/inference/{rknn_runner,rkllm_runner,pipeline}.py` — required as lazy-import targets by pet-eval

**Add** `src/pet_quantize/plugins/`:

```
plugins/
├── __init__.py
├── _register.py                      # entry-point: register_all()
├── converters/
│   ├── vlm_rkllm_w4a16.py             # VlmRkllmW4A16Converter
│   ├── vision_rknn_fp16.py            # VisionRknnFp16Converter
│   ├── audio_rknn_fp16.py             # AudioRknnFp16Converter
│   └── noop.py                        # NoopConverter (PR CI-only)
└── datasets/
    ├── vlm_calibration_subset.py      # VlmCalibrationSubset
    ├── vision_calibration_subset.py
    └── audio_calibration_subset.py
```

**Converter plugin contract:**

```python
class BaseConverter:
    def __init__(self, **kwargs) -> None: ...

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        """
        1. Read input_card.checkpoint_uri.
        2. Pull calibration batch iterator via card.intermediate_artifacts.calibration_batch_uri.
        3. Call pet_quantize.convert.* SDK wrappers to execute quantization.
        4. Produce EdgeArtifact(format=..., artifact_uri=..., sha256=..., target_hardware=...).
        5. Append to card.edge_artifacts; return new card.
        """
```

**Dataset plugin contract:**

```python
class BaseCalibrationDataset:
    def __init__(self, **kwargs) -> None: ...

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        """
        Produce calibration tensor batch → write to .cache/calibration/<hash>.pt.
        Append URI to card.intermediate_artifacts.calibration_batch_uri;
        return new card.
        """
```

**`_register.py` pattern (conditional SDK plugins):**

```python
import os
from pet_infra.registry import CONVERTERS, DATASETS

def register_all():
    from pet_quantize.plugins.converters.noop import NoopConverter
    CONVERTERS.register("noop_converter", NoopConverter)

    try:
        from rknn.api import RKNN  # noqa: F401
        from pet_quantize.plugins.converters.vision_rknn_fp16 import VisionRknnFp16Converter
        from pet_quantize.plugins.converters.audio_rknn_fp16 import AudioRknnFp16Converter
        from pet_quantize.plugins.datasets.vision_calibration_subset import VisionCalibrationSubset
        from pet_quantize.plugins.datasets.audio_calibration_subset import AudioCalibrationSubset
        CONVERTERS.register("vision_rknn_fp16", VisionRknnFp16Converter)
        CONVERTERS.register("audio_rknn_fp16", AudioRknnFp16Converter)
        DATASETS.register("vision_calibration_subset", VisionCalibrationSubset)
        DATASETS.register("audio_calibration_subset", AudioCalibrationSubset)
    except ImportError as exc:
        if not os.environ.get("PET_ALLOW_MISSING_SDK"):
            raise
        import logging
        logging.getLogger(__name__).warning("rknn SDK missing; conditional plugins skipped: %s", exc)

    try:
        from rkllm.api import RKLLM  # noqa: F401
        from pet_quantize.plugins.converters.vlm_rkllm_w4a16 import VlmRkllmW4A16Converter
        from pet_quantize.plugins.datasets.vlm_calibration_subset import VlmCalibrationSubset
        CONVERTERS.register("vlm_rkllm_w4a16", VlmRkllmW4A16Converter)
        DATASETS.register("vlm_calibration_subset", VlmCalibrationSubset)
    except ImportError as exc:
        if not os.environ.get("PET_ALLOW_MISSING_SDK"):
            raise
        import logging
        logging.getLogger(__name__).warning("rkllm SDK missing; conditional plugins skipped: %s", exc)
```

`PET_ALLOW_MISSING_SDK=1` is a PR-CI-only affordance; Release CI and tag workflows explicitly unset it.

### 4.4 pet-eval 2.1.0

**Add** `src/pet_eval/plugins/evaluators/quantized_vlm_evaluator.py`:

```python
class QuantizedVlmEvaluator:
    def __init__(self, metrics: list[str], device: str = "auto", **kwargs) -> None: ...

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        """
        1. Locate input_card.edge_artifacts entries with format == 'rkllm'.
        2. Lazy import pet_quantize.inference.rkllm_runner (same pattern as AudioEvaluator).
        3. Run inference on eval set; collect metric results.
        4. Apply gate (min_<metric> / max_<metric> from params.yaml).
        5. Append eval_results, set gate_status; return new card.
        """
```

**Modify** `src/pet_eval/plugins/_register.py` — append `quantized_vlm_evaluator` registration and the version assert:

```python
import pet_quantize
_expected_major_minor = (2, 0)
_actual = tuple(int(x) for x in pet_quantize.__version__.split(".")[:2])
assert _actual == _expected_major_minor, (
    f"pet-eval 2.1.0 requires pet-quantize 2.0.x, got {pet_quantize.__version__}. "
    "Check compatibility_matrix.yaml 2026.08 row."
)
```

**Modify** `pyproject.toml` — add `pet-quantize` to runtime deps (unpinned; matrix pins it).

**Modify** `.github/workflows/ci.yml` — 5-step install becomes 6-step:

```
1. pip install pet-infra@v2.4.0
2. pip install pet-train@v2.0.0
3. pip install pet-quantize@v2.0.0
4. pip install -e .[dev] --no-deps
5. pip install -r requirements-resolved.txt  # re-resolve
6. python -c "import pet_eval, pet_quantize, pet_train, pet_infra; assert all versions match matrix 2026.08"
```

### 4.5 pet-ota 2.0.0 (BREAKING)

**Delete** (architectural debt):

- `src/pet_ota/cli.py`, `src/pet_ota/__main__.py`
- Any legacy SDK-only orchestration wrappers that duplicate what the plugin will do
- Any remaining wandb usage

**Preserve** (SDK wrappers):

- `src/pet_ota/packaging/make_delta.py` (bsdiff4 invocation)
- `src/pet_ota/packaging/upload_artifact.py`
- `src/pet_ota/backend/base.py` — `OTABackend` Protocol + `DeploymentStatus` model
- `src/pet_ota/backend/local.py` — `LocalBackend` implementation
- `src/pet_ota/release/{canary_rollout,rollback,check_gate}.py`
- `src/pet_ota/monitoring/`

**Add** `src/pet_ota/plugins/`:

```
plugins/
├── __init__.py
├── _register.py                # register_all registers local_backend only
└── backends/
    └── local.py                # LocalBackendPlugin wraps backend/local.py
```

**`LocalBackendPlugin` contract:**

```python
class LocalBackendPlugin:
    def __init__(self, storage_root: Path, **kwargs) -> None: ...

    def run(self, input_card: ModelCard, recipe: ExperimentRecipe) -> ModelCard:
        """
        1. Guard: assert input_card.gate_status == 'passed' (raise GateFailedError if not).
        2. For each edge_artifact in card, build Manifest entry via card.to_manifest_entry().
        3. If recipe specifies prev_card path, run make_delta(old, new) → .delta file.
        4. Call LocalBackend.deploy(artifact, manifest) → writes storage_root.
        5. Append DeploymentStatus to card.deployment_history; persist card before returning.
        """
```

`recipe.required_plugins` declares `ota: local_backend` so orchestrator fails preflight if the plugin isn't installed.

**`pyproject.toml`** — add entry-point `pet_ota = "pet_ota.plugins._register:register_all"`.

### 4.6 compatibility_matrix.yaml 2026.08

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
  rknn_toolkit2: "==2.0.0"   # pin; release CI re-verifies on bump
  rkllm_toolkit: "==1.2.0"
```

rknn/rkllm are pinned exactly in the matrix row to avoid vendor-side silent breakage in Release CI. Bumping either vendor SDK is a matrix 2026.09 concern.

## 5. Reference recipe: `smoke_small.yaml`

Target environment: Release CI (GPU runner, no NPU).

```yaml
# pet-infra/recipes/smoke_small.yaml
defaults:
  - smoke_base
  - trainer/llamafactory_sft
  - evaluator/vlm_evaluator
  - converter/vision_rknn_fp16
  - dataset/vision_calibration_subset
  - evaluator/quantized_vlm_evaluator
  - ota/local_backend

recipe_id: smoke_small
description: Release-CI smoke, full pipeline, no real RK3576.

stages:
  - { name: train,       component_registry: trainers,   component_type: llamafactory_sft,         config_path: configs/smoke/small_train.yaml,        depends_on: [] }
  - { name: eval_fp,     component_registry: evaluators, component_type: vlm_evaluator,            config_path: configs/smoke/small_eval.yaml,         depends_on: [train] }
  - { name: calibrate,   component_registry: datasets,   component_type: vision_calibration_subset, config_path: configs/smoke/small_calibration.yaml, depends_on: [train] }
  - { name: quantize,    component_registry: converters, component_type: vision_rknn_fp16,         config_path: configs/smoke/small_quantize.yaml,     depends_on: [train, calibrate] }
  - { name: eval_quant,  component_registry: evaluators, component_type: quantized_vlm_evaluator,  config_path: configs/smoke/small_eval_quant.yaml,   depends_on: [quantize] }
  - { name: deploy,      component_registry: ota,        component_type: local_backend,            config_path: configs/smoke/small_deploy.yaml,       depends_on: [eval_quant] }

produces:
  - { artifact_type: edge_artifact, format: rknn, gate: passed }

required_plugins:
  trainers:   [llamafactory_sft]
  evaluators: [vlm_evaluator, quantized_vlm_evaluator]
  converters: [vision_rknn_fp16]
  datasets:   [vision_calibration_subset]
  ota:        [local_backend]
```

`smoke_tiny.yaml` keeps the same DAG structure with `tiny_test` trainer, `noop_converter`, and a minimal calibration dataset — runs under `PET_ALLOW_MISSING_SDK=1` in 3 minutes.

## 6. Error handling

### 6.1 Plugin-load failures

Fail-fast, no silent fallback. SDK-dependent plugin branches guard with `try/except ImportError` and re-raise unless `PET_ALLOW_MISSING_SDK=1`. The `noop_converter` must register successfully in any environment (zero external deps).

### 6.2 Stage runtime failures

| Stage type             | Failure mode                            | Behavior                                                                 |
|------------------------|-----------------------------------------|--------------------------------------------------------------------------|
| DATASETS               | calibration URI unreachable             | Raise, orchestrator halts, write `error.json`. `pet run --resume` continues after fix. |
| CONVERTERS (SDK error) | rknn/rkllm toolchain returns nonzero     | Raise with stderr + log path. **No auto-retry** — toolchain errors are config bugs. |
| EVALUATORS (gate fail) | metric below threshold                  | Set `card.gate_status = "failed"`; short-circuit subsequent stages. Not an exception — normal release block. |
| OTA                    | LocalBackend write fails                | Persist `DeploymentStatus(state='failed', error=...)` in card, then raise. Resume-safe. |
| Manual hardware gate   | `pet validate --hardware=rk3576` fails   | CLI exits nonzero; `card.hardware_validation` not written. Release tag guard then blocks tag. |

### 6.3 Release tag guard

pet-quantize and pet-ota `release-*.yml` workflows (tag-triggered) assert against a parameterized card path. The workflow reads the release recipe's `recipe_id` and final-stage name, then loads the card:

```python
recipe = compose_recipe(Path(os.environ["RELEASE_RECIPE_PATH"]))
final_stage_name = recipe.stages[-1].name  # typically 'deploy'
card_path = Path(f"results/{recipe.recipe_id}/{final_stage_name}/card.json")
card = ModelCard.model_validate_json(card_path.read_text())

assert card.hardware_validation is not None, (
    f"release blocked: manual hardware gate not run for recipe {recipe.recipe_id}"
)
assert card.gate_status == "passed", "release blocked: gate failed"
```

The `RELEASE_RECIPE_PATH` workflow env defaults to `recipes/release.yaml` but is parameterizable per repo. A future rename of the release recipe does not break the guard — the path is derived from `recipe.recipe_id`, not hardcoded.

Fail-closed; tags without a completed manual gate never ship.

### 6.4 Cross-repo peer-dep mismatch

Each consumer's `_register.py` runs a `major.minor` version assert at import time against every declared peer. The 6-step pet-eval CI verifies the full matrix 2026.08 resolve end-to-end.

### 6.5 Logger failures

Phase 3A's `ClearMLLogger` already has offline-default + retry. Phase 3B does not add new logger code. Converter/OTA stage artifacts are not pushed to ClearML — they go through `backend.deploy()`.

## 7. Testing strategy

### 7.1 Pyramid

| Tier               | Trigger             | Scenarios | Runtime               | SDK |
|--------------------|---------------------|-----------|-----------------------|-----|
| Unit               | Every commit        | 100+      | < 30 s per repo       | Mocked |
| Integration (PR)   | PR to `dev`/`main`  | 1 (`smoke_tiny`) | ≤ 3 min      | `PET_ALLOW_MISSING_SDK=1` |
| Release CI         | cron daily + tag    | 1 (`smoke_small`) | ~20 min      | Real rknn-toolkit2 |
| Manual hardware    | Release manager     | 2 (gate, diagnostic) | human-paced | Real RK3576 |

### 7.2 Key unit tests

- `pet-schema`: `test_hardware_validation.py` covers optional, serialization, 2.1.0→2.2.0 forward compat.
- `pet-infra`: `test_compose_defaults_list.py` (single/nested/circular/override precedence); `test_launcher_multirun.py` (cartesian, failed-axis isolation, summary JSON); `test_orchestrator_hooks.py` (stage runner dispatch using `noop_converter`).
- `pet-quantize`: per-plugin tests with `monkeypatch` of `rknn.api.RKNN` and `rkllm.api.RKLLM`; `test_noop_converter.py` (no external deps, linchpin for PR CI); `test_register_missing_sdk.py` (fail-fast vs `PET_ALLOW_MISSING_SDK=1`).
- `pet-eval`: `test_quantized_vlm_evaluator.py` mocks `pet_quantize.inference.rkllm_runner`; `test_register_cross_repo_assert.py` verifies version guard.
- `pet-ota`: `test_local_backend_plugin.py` (card → Manifest → disk); `test_gate_enforcement.py` (`gate_status='failed'` → raise); `test_make_delta.py` (real bsdiff4).

### 7.3 Integration (PR CI)

Single scenario: `smoke_tiny.yaml`. Asserts cross-repo plugin discovery + DAG walks + final card has `deployment_history` and `gate_status='passed'`. Runs under `PET_ALLOW_MISSING_SDK=1`.

### 7.4 Release CI

Single scenario: `smoke_small.yaml`. Installs matrix 2026.08 full pins including `rknn_toolkit2==2.0.0`. Asserts `.rknn` artifact produced, `sha256` non-empty, both fp and quantized eval results present, `gate_status='passed'`. Does not measure latency (no NPU available).

### 7.5 Manual hardware gate

CLI: `pet validate --card=<path> --hardware=rk3576 --device=<device_id>`.

Two scenarios:

- **Gate**: asserts `latency_ms_p95 < params.gate.max_latency_ms_p95`, `accuracy > params.gate.min_quantized_accuracy`. On pass, writes `card.hardware_validation`.
- **Diagnostic**: samples latency/accuracy with no thresholds, writes notes for triage.

Not in CI. CLAUDE.md's "latency tests must run on real RK3576" is enforced as a human gate.

### 7.6 Regression protection

Phase 3A's 8-metric regression fixture in pet-eval extends by 2 quantized-metric fixtures. Phase 3A's three standalone smoke recipes become `defaults:`-based, and a `test_compose_backward_compat.py` guards that Phase 3A recipes loaded under 2.4.0 still compose identically.

### 7.7 Out of scope

- No pet-quantize 1.x → 2.0.0 compat tests (destructive rebuild).
- No production OTA backend tests (Q3: LocalBackend only).
- No sweep-axis tests beyond 2-axis cartesian (YAGNI).
- No ModelCard 2.2.0 → 2.0.0 back-load tests (schema 2.0.0 retired in Phase 2).

## 8. PR chain (strict linear)

Approach 1 from brainstorming — same topology as Phase 3A's 24-PR chain.

```
P0 pet-schema 2.2.0               (1 PR: add HardwareValidation + tests + release tag)
      ↓
P1 pet-infra 2.4.0                (5-6 PRs: compose defaults-list, launcher multirun, hooks,
                                    smoke_base.yaml + recipe rewrites, release tag)
      ↓
P2 pet-quantize 2.0.0             (7-9 PRs: delete debt, plugins/ skeleton, 3 converters,
                                    3 calibration datasets, noop, peer-dep CI, release tag)
      ↓
P3 pet-eval 2.1.0                 (2-3 PRs: QuantizedVlmEvaluator, 6-step CI, release tag)
      ↓
P4 pet-ota 2.0.0                  (3-4 PRs: delete debt, plugins/ skeleton, local_backend plugin,
                                    release tag)
      ↓
P5 pet-infra matrix 2026.08 finalize (1 PR: drop -rc suffixes, add rknn/rkllm pins)
      ↓
P6 Phase 3B retrospective         (1 PR: DoD self-check, North Star ≥3 per axis)
```

Each P* is a sub-chain merged fully (feature/* → dev → main → tag) before the next P* starts. Inside a P*, tasks run sequentially via subagent-driven-development.

## 9. Definition of Done

- [ ] All 5 repos tagged with target version.
- [ ] `compatibility_matrix.yaml` 2026.08 row finalized (no -rc suffixes).
- [ ] PR CI passes for `smoke_tiny.yaml` on all repos.
- [ ] Release CI green on `smoke_small.yaml` at 2026.08 matrix pins.
- [ ] `pet list-plugins --json` shows all 9 new plugins.
- [ ] `pet validate --recipe=release.yaml` preflight passes (manual hardware gate may remain pending).
- [ ] Retrospective written to `pet-infra/docs/retrospectives/2026-MM-DD-phase-3b.md`; North Star ≥ 3/5 on all four axes; Flexibility + Extensibility ≥ 5/5 (debts closed).

## 10. Migration notes

- Downstream users of pet-quantize CLI must switch to `pet run` with a recipe. No CLI shim provided.
- Downstream users of pet-ota CLI must switch to `pet run` with an OTA stage. No CLI shim.
- Any recipe referencing Phase 3A standalone smoke recipes continues to work (compose.py is backward-compatible with non-`defaults:` recipes).
- CONVERTERS and DATASETS plugin registrations require pet-infra 2.4.0 — earlier infra versions will fail preflight with "unknown registry 'converters'".

## 11. Risks and mitigations

| Risk                                                    | Mitigation                                                                 |
|---------------------------------------------------------|----------------------------------------------------------------------------|
| rknn-toolkit2 wheel incompatible with GitHub runner     | Matrix pin `rknn_toolkit2==2.0.0`; Release CI validates daily.              |
| pet-quantize SDK wrappers have hidden state from CLI era| P2's first PR audits and isolates pure-function boundaries before plugins. |
| LocalBackend path collisions in concurrent multirun     | `storage_root / <run_id>` subdirectory per run; enforce in plugin init.    |
| pet-eval lazy-import pet_quantize version skew          | `_register.py` version assert; 6-step CI enforces matrix resolve.          |
| Manual hardware gate step gets skipped                  | Release workflow tag guard hard-fails if `card.hardware_validation is None`.|

## 12. Phase 3B follow-ups (out of scope)

- Production OTA backends (S3, HTTP, CDN) — Phase 4.
- `recipe.variations` field hook into orchestrator — Phase 4.
- Recipe composition inheritance (`_base_: ../base.yaml`) beyond defaults-list — Phase 4.
- Multi-device hardware matrix (RK3588, etc.) — out of scope until hardware exists.
- pet-quantize ONNX export path as a separate plugin — current approach keeps ONNX plugin-internal; revisit only if a non-RK consumer materializes.

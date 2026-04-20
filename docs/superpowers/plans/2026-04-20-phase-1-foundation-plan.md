# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the Phase 1 Foundation for the multi-model pipeline refactor — put the pet-schema Pydantic contracts and the pet-infra Plugin Registry + Base ABCs + CLI skeleton in place, so all downstream phases (data, train, eval, quantize, ota) have a stable contract and dispatch layer to plug into.

**Architecture:** Two-repo deliverable. `pet-schema` gains seven new contract modules (samples / annotations / model_card / recipe / metric / configs / adapters) and flips its dependency direction (no longer depends on pet-infra). `pet-infra` gains the 6-registry plugin system, 6 Base ABCs, a `LocalStorage` implementation, a Hydra `ConfigStore` bridge, a recipe resolver (compose → validate → DAG → preflight → content-addressed id precompute), and the `pet` CLI (`list-plugins`, `validate`, `run --dry-run`). A smoke recipe proves the machinery end-to-end without touching any other repo.

**Tech Stack:** Python 3.11, Pydantic v2 (discriminated unions), mmengine-lite Registry, Hydra 1.3 (ConfigStore + compose), click (CLI), networkx (DAG), huggingface-datasets + webdataset (adapters), pytest + mypy + ruff.

**Spec:** `pet-infra/docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md` — cross-reference Section 3 (pet-schema contracts), Section 2 (Plugin Registry), Section 4.7 (Structured Configs), Section 5.1/5.4 (execution + preflight), Section 7.2 (Phase 1 DoD).

**Branch strategy:** Two feature branches, one per repo, opened against each repo's `dev` branch (per CLAUDE.md). pet-schema PR must merge first, then pet-infra PR updates its pet-schema pin to the new tag.

- pet-schema: `feature/phase-1-foundation-contracts` → `dev` → `main` (tag `v2.0.0`)
- pet-infra: `feature/phase-1-foundation-runtime` → `dev` → `main` (tag `v2.0.0`)

---

## File Structure

### pet-schema changes

```
pet-schema/
├── pyproject.toml                      MODIFY  remove pet-infra dep; bump to 2.0.0; add datasets/webdataset extras
├── src/pet_schema/
│   ├── __init__.py                     MODIFY  re-export new types
│   ├── version.py                      CREATE  SCHEMA_VERSION = "2.0.0"
│   ├── enums.py                        CREATE  Modality, SourceInfo, PetSpecies/BowlType/Lighting re-exports, EdgeFormat
│   ├── samples.py                      CREATE  BaseSample / VisionSample / AudioSample / SensorSample / Sample
│   ├── annotations.py                  CREATE  BaseAnnotation / VisionAnnotation / AudioAnnotation / DpoPair / Annotation
│   ├── model_card.py                   CREATE  QuantConfig / EdgeArtifact / ResourceSpec / ModelCard
│   ├── recipe.py                       CREATE  ArtifactRef / RecipeStage / AblationAxis / ExperimentRecipe
│   ├── metric.py                       CREATE  MetricResult / GateCheck / EvaluationReport
│   ├── configs.py                      CREATE  ResourcesSection / TrainerConfig / EvaluatorConfig / ConverterConfig / DatasetConfig
│   ├── models.py                       KEEP    PetFeederEvent (now referenced by VisionAnnotation.parsed)
│   ├── renderer.py / validator.py      KEEP
│   ├── prompts/                        KEEP
│   ├── versions/                       KEEP
│   └── adapters/
│       ├── __init__.py                 CREATE
│       ├── hf_features.py              CREATE  Sample → huggingface datasets Features dict
│       ├── webdataset.py               CREATE  Sample → wds-style key→bytes/str dict
│       └── manifest.py                 CREATE  list[ModelCard] → manifest.json (pet-ota)
└── tests/
    ├── test_samples.py                 CREATE
    ├── test_annotations.py             CREATE
    ├── test_model_card.py              CREATE
    ├── test_recipe.py                  CREATE
    ├── test_metric_report.py           CREATE
    ├── test_configs.py                 CREATE
    ├── test_adapters_hf.py             CREATE
    ├── test_adapters_webdataset.py     CREATE
    └── test_adapters_manifest.py       CREATE
```

### pet-infra changes

```
pet-infra/
├── pyproject.toml                      MODIFY  add pet-schema + mmengine-lite + hydra-core + click + networkx;
│                                                add [project.scripts] pet; add [project.entry-points] self-registration
├── Makefile                            KEEP
├── src/pet_infra/
│   ├── __init__.py                     MODIFY  __version__ = "2.0.0"
│   ├── registry.py                     CREATE  6 Registry objects (TRAINERS/EVALUATORS/CONVERTERS/METRICS/DATASETS/STORAGE)
│   ├── _register.py                    CREATE  entry_points target — register LocalStorage
│   ├── base/
│   │   ├── __init__.py                 CREATE  re-export Base* ABCs
│   │   ├── trainer.py                  CREATE  BaseTrainer
│   │   ├── evaluator.py                CREATE  BaseEvaluator
│   │   ├── converter.py                CREATE  BaseConverter (uses pet_schema.EdgeFormat)
│   │   ├── metric.py                   CREATE  BaseMetric
│   │   ├── dataset.py                  CREATE  BaseDataset
│   │   └── storage.py                  CREATE  BaseStorage
│   ├── storage/
│   │   ├── __init__.py                 CREATE
│   │   └── local.py                    CREATE  LocalStorage (scheme=local://)
│   ├── hydra_plugins/
│   │   ├── __init__.py                 CREATE
│   │   └── structured.py               CREATE  ConfigStore registrations (recipe/trainer/evaluator/converter/dataset)
│   ├── plugins/
│   │   ├── __init__.py                 CREATE
│   │   └── discover.py                 CREATE  entry_points loader (+ required-filter)
│   ├── recipe/
│   │   ├── __init__.py                 CREATE
│   │   ├── compose.py                  CREATE  Hydra compose + Pydantic validate → ResolvedRecipe
│   │   ├── dag.py                      CREATE  ExperimentRecipe.to_dag helper + topo sort + cycle check
│   │   ├── card_id.py                  CREATE  precompute ModelCard.id = f"{recipe_id}_{stage}_{cfg_sha[:8]}"
│   │   └── preflight.py                CREATE  fail-fast checks (plugin registered, URI scheme, resources, upstream card)
│   └── cli.py                          CREATE  click-based `pet list-plugins|validate|run --dry-run`
├── recipes/
│   ├── smoke_foundation.yaml           CREATE  single-stage trivial recipe (fake trainer plugin registered in tests)
│   └── ablation/                       CREATE  placeholder .gitkeep
├── docs/
│   ├── DEVELOPMENT_GUIDE.md            MODIFY  add §Phase 1 section (Plugin Registry / CLI / Recipe)
│   └── compatibility_matrix.yaml       CREATE  release 2026.05 — pet_schema 2.0.0 / pet_infra 2.0.0
├── .github/workflows/
│   ├── ci.yml                          MODIFY  keep lint/test; add new jobs below
│   ├── schema-validation.yml           CREATE  assemble compatibility_matrix + cross-check versions
│   ├── plugin-discovery.yml            CREATE  install pet-infra, run `pet list-plugins`, assert LocalStorage registered
│   └── recipe-dry-run.yml              CREATE  for each file in recipes/, run `pet validate --recipe=<path>`
└── tests/
    ├── test_registry.py                CREATE
    ├── test_base_abcs.py               CREATE
    ├── test_storage_local.py           CREATE
    ├── test_hydra_plugins.py           CREATE
    ├── test_plugins_discover.py        CREATE
    ├── test_recipe_compose.py          CREATE
    ├── test_recipe_dag.py              CREATE
    ├── test_recipe_card_id.py          CREATE
    ├── test_recipe_preflight.py        CREATE
    ├── test_cli_list_plugins.py        CREATE
    ├── test_cli_validate.py            CREATE
    └── test_smoke_recipe.py            CREATE
```

**Decomposition rule followed:** one file = one responsibility, tests colocated, sub-packages (`base/`, `storage/`, `hydra_plugins/`, `plugins/`, `recipe/`) keep each file under ~120 LOC.

---

## Part A — pet-schema contracts

Work in the `pet-schema/` repo on branch `feature/phase-1-foundation-contracts` off `dev`. Run all Part A commands from `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema/`.

### Task A0: Branch setup and dep cleanup

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Create branch off dev**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull origin dev
git checkout -b feature/phase-1-foundation-contracts
```

- [ ] **Step 2: Remove circular pet-infra dep and add new optional extras**

Open `pyproject.toml`, delete the `pet-infra @ git+...` line from `dependencies`. Add `datasets>=2.19,<3.0` and `webdataset>=0.2,<0.3` under a new extra `adapters`. Bump `version = "2.0.0"`.

- [ ] **Step 3: Verify existing tests still pass with the dep removal**

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
Expected: existing 79 tests still green (renderer/validator/models).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(pet-schema): drop pet-infra dep and bump to 2.0.0 pre-release"
```

---

### Task A1: `version.py` — SCHEMA_VERSION

**Files:**
- Create: `src/pet_schema/version.py`
- Test: `tests/test_version.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_version.py
from pet_schema.version import SCHEMA_VERSION

def test_schema_version_is_semver_2_0_0():
    assert SCHEMA_VERSION == "2.0.0"
```

- [ ] **Step 2: Run test → FAIL (module missing)**

```bash
pytest tests/test_version.py -v
```

- [ ] **Step 3: Implement minimum module**

```python
# src/pet_schema/version.py
SCHEMA_VERSION = "2.0.0"
```

- [ ] **Step 4: Run test → PASS**

```bash
pytest tests/test_version.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/version.py tests/test_version.py
git commit -m "feat(pet-schema): add SCHEMA_VERSION constant"
```

---

### Task A2: `enums.py` — shared Literal types and EdgeFormat

**Files:**
- Create: `src/pet_schema/enums.py`
- Test: `tests/test_enums.py`

Spec reference: Section 3.2 Modality/SourceInfo; Section 2.4 EdgeFormat.

- [ ] **Step 1: Write failing test**

```python
# tests/test_enums.py
import pytest
from pet_schema.enums import EdgeFormat, Modality, PetSpecies, BowlType, Lighting

def test_edge_format_values():
    assert EdgeFormat.RKLLM.value == "rkllm"
    assert {m.value for m in EdgeFormat} == {"rkllm", "rknn", "onnx", "gguf"}

def test_modality_literal_members():
    # Modality is a Literal, not an Enum — assert via typing introspection
    from typing import get_args
    assert set(get_args(Modality)) == {"vision", "audio", "sensor", "multimodal"}

def test_petspecies_members_cover_cat_dog():
    assert "cat" in {s.value for s in PetSpecies}
    assert "dog" in {s.value for s in PetSpecies}
```

- [ ] **Step 2: Run test → FAIL (module missing)**

```bash
pytest tests/test_enums.py -v
```

- [ ] **Step 3: Implement `enums.py`**

```python
# src/pet_schema/enums.py
from __future__ import annotations
from enum import Enum
from typing import Literal

Modality = Literal["vision", "audio", "sensor", "multimodal"]


class EdgeFormat(str, Enum):
    RKLLM = "rkllm"
    RKNN  = "rknn"
    ONNX  = "onnx"
    GGUF  = "gguf"


class PetSpecies(str, Enum):
    CAT = "cat"
    DOG = "dog"
    OTHER = "other"


class BowlType(str, Enum):
    METAL = "metal"
    CERAMIC = "ceramic"
    PLASTIC = "plastic"
    UNKNOWN = "unknown"


class Lighting(str, Enum):
    BRIGHT = "bright"
    DIM = "dim"
    DARK = "dark"


SourceType = Literal["youtube", "community", "device", "synthetic"]
```

- [ ] **Step 4: Run test → PASS**

```bash
pytest tests/test_enums.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/enums.py tests/test_enums.py
git commit -m "feat(pet-schema): add shared enums and EdgeFormat"
```

---

### Task A3: `samples.py` — BaseSample + subclasses + discriminated union

**Files:**
- Create: `src/pet_schema/samples.py`
- Test: `tests/test_samples.py`

Spec reference: Section 3.2.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_samples.py
from datetime import datetime
import pytest
from pydantic import TypeAdapter, ValidationError
from pet_schema.samples import (
    BaseSample, VisionSample, AudioSample, SensorSample, Sample, SourceInfo,
)


def _src():
    return SourceInfo(source_type="device", source_id="feeder-001", license=None)


def test_vision_sample_roundtrip():
    s = VisionSample(
        sample_id="abc",
        storage_uri="local:///tmp/a.jpg",
        captured_at=datetime(2026, 4, 20),
        source=_src(),
        pet_species=None,
        frame_width=1280, frame_height=720,
        lighting="bright",
        bowl_type="metal",
        blur_score=0.1, brightness_score=0.7,
    )
    as_dict = s.model_dump(mode="json")
    assert as_dict["modality"] == "vision"
    assert VisionSample.model_validate(as_dict) == s


def test_sample_union_discriminator():
    adapter = TypeAdapter(Sample)
    vision_dict = {
        "sample_id": "v1",
        "modality": "vision",
        "storage_uri": "local:///tmp/a.jpg",
        "captured_at": "2026-04-20T00:00:00",
        "source": {"source_type": "device", "source_id": "feeder-001", "license": None},
        "pet_species": None,
        "frame_width": 1280, "frame_height": 720,
        "lighting": "bright", "bowl_type": "metal",
        "blur_score": 0.1, "brightness_score": 0.7,
    }
    audio_dict = {
        "sample_id": "a1",
        "modality": "audio",
        "storage_uri": "local:///tmp/a.wav",
        "captured_at": "2026-04-20T00:00:00",
        "source": {"source_type": "device", "source_id": "feeder-001", "license": None},
        "pet_species": None,
        "duration_s": 2.3, "sample_rate": 16000, "num_channels": 1,
        "snr_db": None, "clip_type": "bark",
    }
    assert isinstance(adapter.validate_python(vision_dict), VisionSample)
    assert isinstance(adapter.validate_python(audio_dict), AudioSample)


def test_vision_sample_rejects_wrong_modality_literal():
    with pytest.raises(ValidationError):
        VisionSample(
            sample_id="x", modality="audio",  # mismatch
            storage_uri="local:///tmp/a.jpg",
            captured_at=datetime(2026, 4, 20),
            source=_src(), pet_species=None,
            frame_width=1, frame_height=1,
            lighting="bright", bowl_type=None,
            blur_score=0.0, brightness_score=0.5,
        )


def test_sample_is_frozen():
    s = VisionSample(
        sample_id="abc", storage_uri="local://x", captured_at=datetime(2026, 4, 20),
        source=_src(), pet_species=None, frame_width=1, frame_height=1,
        lighting="bright", bowl_type=None, blur_score=0.0, brightness_score=0.5,
    )
    with pytest.raises(ValidationError):
        s.sample_id = "mutated"
```

- [ ] **Step 2: Run tests → FAIL**

```bash
pytest tests/test_samples.py -v
```

- [ ] **Step 3: Implement `samples.py`**

```python
# src/pet_schema/samples.py
from __future__ import annotations
from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator

from pet_schema.enums import BowlType, Lighting, Modality, PetSpecies, SourceType


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: SourceType
    source_id: str
    license: Optional[str]


class BaseSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    modality: Modality
    storage_uri: str
    captured_at: datetime
    source: SourceInfo
    pet_species: Optional[PetSpecies] = None
    schema_version: str = "2.0.0"


class VisionSample(BaseSample):
    modality: Literal["vision"] = "vision"
    frame_width: int
    frame_height: int
    lighting: Lighting
    bowl_type: Optional[BowlType] = None
    blur_score: float
    brightness_score: float


class AudioSample(BaseSample):
    modality: Literal["audio"] = "audio"
    duration_s: float
    sample_rate: int
    num_channels: int
    snr_db: Optional[float] = None
    clip_type: Optional[Literal["bark", "meow", "purr", "silence", "ambient"]] = None


class SensorSample(BaseSample):
    modality: Literal["sensor"] = "sensor"
    sensor_type: str
    readings: dict[str, float]
    ambient_temp_c: Optional[float] = None
    ambient_humidity: Optional[float] = None


Sample = Annotated[
    Union[VisionSample, AudioSample, SensorSample],
    Discriminator("modality"),
]
```

- [ ] **Step 4: Run tests → PASS**

```bash
pytest tests/test_samples.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/samples.py tests/test_samples.py
git commit -m "feat(pet-schema): add BaseSample + vision/audio/sensor subclasses"
```

---

### Task A4: `annotations.py` — BaseAnnotation + subclasses + DpoPair

**Files:**
- Create: `src/pet_schema/annotations.py`
- Test: `tests/test_annotations.py`

Spec reference: Section 3.3.

- [ ] **Step 1a: Add three fixtures to `tests/conftest.py`**

Append (do not overwrite existing fixtures):

```python
# tests/conftest.py (append)
import pytest


@pytest.fixture
def vision_event_dict() -> dict:
    """Minimal valid PetFeederEvent dict — matches schema v1.0 examples/eating.json shape."""
    return {
        "schema_version": "1.0",
        "pet_species": "cat",
        "action": {
            "primary": "eating",
            "distribution": {
                "eating": 1.0, "drinking": 0.0, "sniffing_only": 0.0,
                "leaving_bowl": 0.0, "sitting_idle": 0.0, "other": 0.0,
            },
        },
        "eating": {
            "speed": {"fast": 0.0, "normal": 1.0, "slow": 0.0},
            "engagement": 0.8,
            "abandoned_midway": 0.0,
        },
        "mood": {"alertness": 0.7, "anxiety": 0.1, "engagement": 0.8},
        "posture": "relaxed",
        "narrative": "a cat eating from a metal bowl",
    }


@pytest.fixture
def vision_annotation_dict(vision_event_dict) -> dict:
    return {
        "annotation_id": "ann-v1",
        "sample_id": "s1",
        "annotator_type": "vlm",
        "annotator_id": "qwen2_vl_1b_pretrained",
        "modality": "vision",
        "created_at": "2026-04-20T00:00:00",
        "schema_version": "2.0.0",
        "raw_response": '{"action": "eating"}',
        "parsed": vision_event_dict,
        "prompt_hash": "sha256:deadbeef",
    }


@pytest.fixture
def audio_annotation_dict() -> dict:
    return {
        "annotation_id": "ann-a1",
        "sample_id": "s2",
        "annotator_type": "cnn",
        "annotator_id": "audio_cnn_v1",
        "modality": "audio",
        "created_at": "2026-04-20T00:00:00",
        "schema_version": "2.0.0",
        "predicted_class": "bark",
        "class_probs": {"bark": 0.9, "meow": 0.1},
        "logits": None,
    }
```

If the repo's `tests/conftest.py` already defines a fixture with one of these names, adjust the name in the fixture + corresponding test. Do NOT refactor existing fixtures.

- [ ] **Step 1b: Write failing tests**

```python
# tests/test_annotations.py
from datetime import datetime
import pytest
from pydantic import TypeAdapter, ValidationError
from pet_schema.annotations import (
    Annotation, AudioAnnotation, DpoPair, VisionAnnotation,
)
from pet_schema.models import PetFeederEvent  # existing v1.0 model


def test_vision_annotation_wraps_pet_feeder_event(vision_annotation_dict):
    a = VisionAnnotation.model_validate(vision_annotation_dict)
    assert a.modality == "vision"
    assert isinstance(a.parsed, PetFeederEvent)


def test_audio_annotation_requires_probs_dict():
    with pytest.raises(ValidationError):
        AudioAnnotation(
            annotation_id="a1", sample_id="s1", annotator_type="cnn",
            annotator_id="audio_cnn_v1", created_at=datetime(2026, 4, 20),
            schema_version="2.0.0",
            predicted_class="bark",
            class_probs="not-a-dict",  # type: ignore[arg-type]
        )


def test_annotation_union_discriminator(vision_annotation_dict, audio_annotation_dict):
    adapter = TypeAdapter(Annotation)
    assert isinstance(adapter.validate_python(vision_annotation_dict), VisionAnnotation)
    assert isinstance(adapter.validate_python(audio_annotation_dict), AudioAnnotation)


def test_dpo_pair_validates():
    p = DpoPair(pair_id="p1", chosen_annotation_id="a1", rejected_annotation_id="a2",
                preference_source="human", reason="chosen is cleaner")
    assert p.preference_source == "human"
```

- [ ] **Step 2: Run tests → FAIL**

```bash
pytest tests/test_annotations.py -v
```

- [ ] **Step 3: Implement `annotations.py`**

```python
# src/pet_schema/annotations.py
from __future__ import annotations
from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator

from pet_schema.enums import Modality
from pet_schema.models import PetFeederEvent


class BaseAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_id: str
    sample_id: str
    annotator_type: Literal["vlm", "cnn", "human", "rule"]
    annotator_id: str
    modality: Modality
    created_at: datetime
    schema_version: str


class VisionAnnotation(BaseAnnotation):
    modality: Literal["vision"] = "vision"
    raw_response: str
    parsed: PetFeederEvent
    prompt_hash: str


class AudioAnnotation(BaseAnnotation):
    modality: Literal["audio"] = "audio"
    predicted_class: str
    class_probs: dict[str, float]
    logits: Optional[list[float]] = None


Annotation = Annotated[
    Union[VisionAnnotation, AudioAnnotation],
    Discriminator("modality"),
]


class DpoPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pair_id: str
    chosen_annotation_id: str
    rejected_annotation_id: str
    preference_source: Literal["human", "rule", "auto"]
    reason: Optional[str] = None
```

- [ ] **Step 4: Run tests → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/annotations.py tests/test_annotations.py tests/conftest.py
git commit -m "feat(pet-schema): add BaseAnnotation + vision/audio + DpoPair"
```

---

### Task A5: `model_card.py` — ModelCard and quant/edge/resource helpers

**Files:**
- Create: `src/pet_schema/model_card.py`
- Test: `tests/test_model_card.py`

Spec reference: Section 3.4.

- [ ] **Step 1: Write failing tests**

Test cases:
1. `QuantConfig` requires `method` literal and accepts optional bits.
2. `EdgeArtifact` validates `format` against `EdgeFormat` values.
3. `ResourceSpec` all fields required.
4. `ModelCard.to_manifest_entry()` returns a dict with `id`, `version`, `checkpoint_uri`, `edge_artifact`.
5. `ModelCard` rejects extra fields (`extra="forbid"`).
6. `ModelCard.parent_models` defaults to `[]` and accepts a list of ids.
7. `ModelCard.lineage_role` must be one of the 5 literal values or `None`.

```python
# tests/test_model_card.py (excerpt)
from datetime import datetime
import pytest
from pydantic import ValidationError
from pet_schema.model_card import EdgeArtifact, ModelCard, QuantConfig, ResourceSpec


def _mc(**overrides):
    base = dict(
        id="recipe1_train_abc12345", version="1.0.0", modality="vision",
        task="classification", arch="qwen2_vl", training_recipe="vlm_sft_baseline",
        recipe_id="vlm_sft_baseline", hydra_config_sha="sha123",
        git_shas={}, dataset_versions={},
        checkpoint_uri="local:///ckpts/1",
        quantization=None, edge_artifact=None,
        parent_models=[], lineage_role=None,
        metrics={"accuracy": 0.9}, gate_status="passed",
        trained_at=datetime(2026, 4, 20), trained_by="tester",
        clearml_task_id=None, dvc_exp_sha=None, notes=None,
    )
    base.update(overrides)
    return ModelCard(**base)


def test_model_card_to_manifest_entry_has_required_keys():
    mc = _mc(edge_artifact=EdgeArtifact(
        format="rkllm", target_hardware=["rk3576"],
        artifact_uri="local:///edge/a.rkllm", sha256="abc", size_bytes=1234,
        min_firmware=None, input_shape={"input": [1, 3, 224, 224]},
    ))
    entry = mc.to_manifest_entry()
    assert entry["id"] == mc.id
    assert entry["edge_artifact"]["format"] == "rkllm"

def test_model_card_rejects_extra_field():
    with pytest.raises(ValidationError):
        _mc(surprise="field")
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement `model_card.py`** — follow spec §3.4 exactly. `to_manifest_entry` returns `self.model_dump(mode="json", exclude_none=False)`.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/model_card.py tests/test_model_card.py
git commit -m "feat(pet-schema): add ModelCard contract with lineage + manifest export"
```

---

### Task A6: `recipe.py` — ArtifactRef / RecipeStage / AblationAxis / ExperimentRecipe

**Files:**
- Create: `src/pet_schema/recipe.py`
- Test: `tests/test_recipe.py`

Spec reference: Section 3.5. `to_dag` returns `networkx.DiGraph`.

- [ ] **Step 0 (prerequisite): Add `networkx>=3.2,<4.0` to base deps in `pyproject.toml`**, then re-install so the test imports can resolve:

```bash
# edit pyproject.toml — add "networkx>=3.2,<4.0" to [project].dependencies
pip install -e ".[dev,adapters]"
```

- [ ] **Step 1: Write failing tests**

Assertions to cover:
1. `ArtifactRef(ref_type="recipe_stage_output", ref_value="train")` validates; unknown ref_type rejected.
2. `RecipeStage` requires `component_registry` one of the 3 active registries; rejects `"datasets"` / `"metrics"` / `"storage"`.
3. `AblationAxis.values` accepts mixed str/int/float/bool.
4. `ExperimentRecipe.to_dag()` returns a DAG with an edge from `sft → dpo` when `dpo.depends_on = ["sft"]`.
5. `ExperimentRecipe` raises on cyclic `depends_on`.
6. `AblationAxis.stage` must match some `stages[].name` (model_validator).
7. `scope="single_repo"` vs `"cross_repo"` both accepted.

```python
# tests/test_recipe.py (excerpt)
import pytest
from pydantic import ValidationError
import networkx as nx
from pet_schema.recipe import (
    AblationAxis, ArtifactRef, ExperimentRecipe, RecipeStage,
)


def _stage(name, depends_on=None):
    return RecipeStage(
        name=name, component_registry="trainers", component_type="pet_train.vlm_sft",
        inputs={}, config_path=f"trainer/{name}", depends_on=depends_on or [],
    )


def test_recipe_stage_rejects_passive_registry():
    with pytest.raises(ValidationError):
        RecipeStage(
            name="x", component_registry="datasets",
            component_type="ds", inputs={}, config_path="p", depends_on=[],
        )


def test_to_dag_has_depends_on_edge():
    r = ExperimentRecipe(
        recipe_id="r1", description="d", scope="single_repo", owner_repo="pet-train",
        schema_version="2.0.0",
        stages=[_stage("sft"), _stage("dpo", ["sft"])],
        variations=[], produces=["m1"],
        default_storage="local", required_plugins=["pet_train"],
    )
    g: nx.DiGraph = r.to_dag()
    assert g.has_edge("sft", "dpo")
    assert list(nx.topological_sort(g)) == ["sft", "dpo"]


def test_to_dag_raises_on_cycle():
    r = ExperimentRecipe(
        recipe_id="r1", description="d", scope="single_repo", owner_repo="pet-train",
        schema_version="2.0.0",
        stages=[_stage("a", ["b"]), _stage("b", ["a"])],
        variations=[], produces=[],
        default_storage="local", required_plugins=[],
    )
    with pytest.raises(ValueError, match="cycle"):
        r.to_dag()


def test_ablation_axis_must_reference_known_stage():
    with pytest.raises(ValidationError):
        ExperimentRecipe(
            recipe_id="r1", description="d", scope="single_repo", owner_repo="pet-train",
            schema_version="2.0.0",
            stages=[_stage("sft")],
            variations=[AblationAxis(name="x", stage="unknown", hydra_path="a.b", values=[1, 2])],
            produces=[], default_storage="local", required_plugins=[],
        )
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement `recipe.py`**

Key implementation notes:
- `RecipeStage.component_registry: Literal["trainers", "evaluators", "converters"]` (exactly the active trio per spec §3.5).
- `ExperimentRecipe` uses `@model_validator(mode="after")` to cross-validate `variations[].stage in {stages[].name}` and to call `self.to_dag()` eagerly so cycles surface at construction.
- `to_dag()` builds `nx.DiGraph` with `add_node(stage.name)` and `add_edge(dep, stage.name)` for each dep; call `nx.find_cycle` to validate.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_schema/recipe.py tests/test_recipe.py pyproject.toml
git commit -m "feat(pet-schema): add ExperimentRecipe + DAG validation"
```

---

### Task A7: `metric.py` — MetricResult / GateCheck / EvaluationReport

**Files:**
- Create: `src/pet_schema/metric.py`
- Test: `tests/test_metric_report.py`

Spec reference: Section 3.8.

**`report_id` construction rule** (so tests + implementation agree):
`report_id = hashlib.sha256(f"{model_card_id}|{evaluator_type}|{dataset_uri}|{evaluated_at.isoformat()}".encode()).hexdigest()[:16]`
— pure function of already-required fields, deterministic, content-addressed. Implement as a Pydantic `@model_validator(mode="before")` that fills `report_id` when the caller omits it, and validates the regex when supplied.

- [ ] **Step 1: Write failing tests**

1. `MetricResult(name, value, higher_is_better)` instantiates.
2. `GateCheck.evaluate(actual, threshold, comparator)` classmethod computes `passed` and returns a `GateCheck` instance; covers all 3 comparators (ge/le/eq — `eq` uses `math.isclose`).
3. `EvaluationReport` with empty `gate_checks` has `gate_status = "passed"`; with one failing check has `gate_status = "failed"`; with one pending check has `gate_status = "pending"`.
4. `EvaluationReport.report_id` omitted by caller → auto-computed deterministic 16-char lowercase hex (matches `^[a-f0-9]{16}$`); passing the same args twice yields the same id.
5. `EvaluationReport(report_id="not-hex!", ...)` raises ValidationError (regex check).

- [ ] **Step 2–5:** Implement, test, commit.

```bash
git add src/pet_schema/metric.py tests/test_metric_report.py
git commit -m "feat(pet-schema): add MetricResult / GateCheck / EvaluationReport"
```

---

### Task A8: `configs.py` — Structured Hydra target types

**Files:**
- Create: `src/pet_schema/configs.py`
- Test: `tests/test_configs.py`

Spec reference: Section 3.9.

- [ ] **Step 1: Write failing tests**

1. `TrainerConfig(type="pet_train.vlm_sft", args={"lora_r": 128}, resources=ResourcesSection(...))` validates.
2. `TrainerConfig` rejects missing `type`.
3. `EvaluatorConfig.gates` defaults to `[]`.
4. `DatasetConfig.modality` is a Modality literal.
5. Outer-shell validation does NOT dive into `args` content.

- [ ] **Step 2–5:** Implement per spec §3.9, test, commit.

---

### Task A9: `adapters/hf_features.py` — HuggingFace `datasets.Features` mapping

**Files:**
- Create: `src/pet_schema/adapters/__init__.py` (empty)
- Create: `src/pet_schema/adapters/hf_features.py`
- Test: `tests/test_adapters_hf.py`

Purpose: convert a `Sample` subclass into a `datasets.Features` spec for HF dataset construction. Scope is minimal — only support the three currently-defined Sample subclasses.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_adapters_hf.py
import pytest

datasets = pytest.importorskip("datasets")  # gated on adapters extra

from pet_schema.adapters.hf_features import sample_to_hf_features
from pet_schema.samples import AudioSample, VisionSample


def test_vision_sample_maps_to_image_features():
    feats = sample_to_hf_features(VisionSample)
    assert "sample_id" in feats and "frame_width" in feats
    assert str(feats["sample_id"]).startswith("Value")  # string


def test_audio_sample_maps_to_audio_features():
    feats = sample_to_hf_features(AudioSample)
    assert "duration_s" in feats
```

- [ ] **Step 2–5:** Implement by walking `model_fields` and mapping Pydantic types → `datasets.Value("string"|"int64"|"float")` / `datasets.Audio()` / `datasets.Image()`. Raise `TypeError` on unknown field type (fail-fast). Test, commit.

---

### Task A10: `adapters/webdataset.py` — WDS key→bytes-or-str mapping

**Files:**
- Create: `src/pet_schema/adapters/webdataset.py`
- Test: `tests/test_adapters_webdataset.py`

Purpose: convert a single `Sample` instance into `{".json": <metadata_json>, ".jpg"/".wav": <uri>}` dict consumed by `webdataset.ShardWriter`.

- [ ] **Step 1: Write failing test**

Given a `VisionSample` with `storage_uri="local:///tmp/a.jpg"`, `sample_to_wds_dict(s)` returns `{"__key__": s.sample_id, ".jpg": "local:///tmp/a.jpg", ".json": <dump>}`. For `AudioSample`, key `.wav` maps to storage_uri.

- [ ] **Step 2–5:** Implement, test, commit.

---

### Task A11: `adapters/manifest.py` — `list[ModelCard]` → manifest.json for pet-ota

**Files:**
- Create: `src/pet_schema/adapters/manifest.py`
- Test: `tests/test_adapters_manifest.py`

- [ ] **Step 1: Write failing test**

`build_manifest(cards: list[ModelCard]) -> dict` returns:
```json
{
  "schema_version": "2.0.0",
  "generated_at": "<iso8601>",
  "models": [<ModelCard.to_manifest_entry() for each>]
}
```
Given 0 cards, `models == []`. Given 2 cards, order preserved. Signature is pure (no I/O).

- [ ] **Step 2–5:** Implement, test, commit.

---

### Task A12: `__init__.py` re-exports + final package lint/test

**Files:**
- Modify: `src/pet_schema/__init__.py`
- Modify: `tests/test_public_api.py` (new — guards downstream imports)

- [ ] **Step 1: Update re-exports**

```python
"""pet-schema 2.0.0 public API."""
from pet_schema.annotations import (
    Annotation, AudioAnnotation, BaseAnnotation, DpoPair, VisionAnnotation,
)
from pet_schema.configs import (
    ConverterConfig, DatasetConfig, EvaluatorConfig, ResourcesSection, TrainerConfig,
)
from pet_schema.enums import (
    BowlType, EdgeFormat, Lighting, Modality, PetSpecies, SourceType,
)
from pet_schema.metric import EvaluationReport, GateCheck, MetricResult
from pet_schema.model_card import EdgeArtifact, ModelCard, QuantConfig, ResourceSpec
from pet_schema.models import PetFeederEvent  # keep 1.0 downstream users importing from top-level
from pet_schema.recipe import (
    AblationAxis, ArtifactRef, ExperimentRecipe, RecipeStage,
)
from pet_schema.renderer import render_prompt
from pet_schema.samples import (
    AudioSample, BaseSample, Sample, SensorSample, SourceInfo, VisionSample,
)
from pet_schema.validator import validate_output
from pet_schema.version import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "render_prompt", "validate_output",
    # legacy v1 model (downstream depend on this import path)
    "PetFeederEvent",
    # samples
    "BaseSample", "Sample", "VisionSample", "AudioSample", "SensorSample", "SourceInfo",
    # annotations
    "Annotation", "BaseAnnotation", "VisionAnnotation", "AudioAnnotation", "DpoPair",
    # model card
    "ModelCard", "QuantConfig", "EdgeArtifact", "ResourceSpec",
    # recipe
    "ArtifactRef", "RecipeStage", "AblationAxis", "ExperimentRecipe",
    # metric
    "MetricResult", "GateCheck", "EvaluationReport",
    # configs
    "TrainerConfig", "EvaluatorConfig", "ConverterConfig", "DatasetConfig", "ResourcesSection",
    # enums
    "Modality", "EdgeFormat", "PetSpecies", "BowlType", "Lighting", "SourceType",
]
```

- [ ] **Step 1b: Add public-API guard test**

```python
# tests/test_public_api.py
def test_all_exports_importable_from_top_level():
    import pet_schema
    for name in pet_schema.__all__:
        assert hasattr(pet_schema, name), f"__all__ lists {name!r} but it's missing"


def test_petfeederevent_stays_top_level_importable_for_downstream():
    # pet-annotation / pet-train / pet-data pin to v1 and use this import path.
    from pet_schema import PetFeederEvent  # noqa: F401
```

- [ ] **Step 2: Run the whole test suite + lint**

```bash
pip install -e ".[dev,adapters]"
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```
Expected: all tests pass, no lint errors.

- [ ] **Step 3: Commit**

```bash
git add src/pet_schema/__init__.py
git commit -m "feat(pet-schema): re-export all new 2.0.0 types"
```

---

### Task A13: Open PR pet-schema → dev, merge, tag `v2.0.0`

- [ ] **Step 1: Push branch and open PR**

```bash
git push -u origin feature/phase-1-foundation-contracts
gh pr create --base dev --title "feat(pet-schema): Phase 1 Foundation contracts (2.0.0)" \
  --body "$(cat <<'EOF'
## Summary
- New contract modules: samples / annotations / model_card / recipe / metric / configs / adapters
- Drops circular pet-infra dep; bumps to 2.0.0
- Spec: pet-infra/docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md §3

## Test plan
- [ ] 79 legacy renderer/validator tests still green
- [ ] New type tests all green (samples / annotations / model_card / recipe / metric / configs / adapters)
- [ ] ruff + mypy clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Wait for CI green + 2 reviewer approvals (pet-schema rule per CLAUDE.md) → merge squash into dev**

- [ ] **Step 3: Open dev → main PR, merge, tag**

```bash
git checkout main && git pull origin main
gh pr create --base main --head dev --title "release(pet-schema): 2.0.0" --body "Phase 1 Foundation contracts"
# after merge:
git pull origin main
git tag v2.0.0
git push origin v2.0.0
```

- [ ] **Step 4: Confirm tag exists on GitHub**

```bash
gh release view v2.0.0 --repo Train-Pet-Pipeline/pet-schema || true
```

---

## Part B — pet-infra runtime

Work in `pet-infra/` on branch `feature/phase-1-foundation-runtime` off `dev`. All Part B commands run from `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/`.

### Task B0: Branch setup + pyproject deps

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/pet_infra/__init__.py`

- [ ] **Step 1: Branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull origin dev
git checkout -b feature/phase-1-foundation-runtime
```

- [ ] **Step 2: Update pyproject deps**

Add to `dependencies`:
```toml
"pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema.git@v2.0.0",
"mmengine-lite>=0.10,<0.12",   # PyPI package name is mmengine-lite, but imports as `mmengine`
"hydra-core>=1.3,<1.4",
"click>=8.1,<9.0",
"networkx>=3.2,<4.0",
```

**Import note:** `mmengine-lite` is the slim PyPI distribution, but the module path stays `mmengine` (`from mmengine.registry import Registry`). Do NOT try `from mmengine_lite import ...`.

Add `[project.scripts]`:
```toml
[project.scripts]
pet = "pet_infra.cli:main"
```

Add self-registration entry point:
```toml
[project.entry-points."pet_infra.plugins"]
pet_infra = "pet_infra._register:register_all"
```

Bump `version = "2.0.0"` and `requires-python = ">=3.11,<3.12"` (align with pet-schema).

- [ ] **Step 3: Bump `__init__.__version__ = "2.0.0"`**

- [ ] **Step 4: Install and smoke-run existing tests**

```bash
pip install -e ".[dev,api,sync]"
pytest tests/ -v
```
Expected: existing pet-infra tests still green (api_client / device / logging / retry / store).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/pet_infra/__init__.py
git commit -m "chore(pet-infra): declare Phase 1 deps (pet-schema 2.0.0, mmengine-lite, hydra, click)"
```

---

### Task B1: `registry.py` — 6 Registry objects

**Files:**
- Create: `src/pet_infra/registry.py`
- Test: `tests/test_registry.py`

Spec reference: Section 2.2.

- [ ] **Step 1: Write failing test**

```python
# tests/test_registry.py
from pet_infra.registry import (
    CONVERTERS, DATASETS, EVALUATORS, METRICS, STORAGE, TRAINERS,
)


def test_six_registries_with_unique_names():
    regs = [TRAINERS, EVALUATORS, CONVERTERS, METRICS, DATASETS, STORAGE]
    names = {r.name for r in regs}
    assert names == {"trainer", "evaluator", "converter", "metric", "dataset", "storage"}


def test_registry_decorator_works():
    @TRAINERS.register_module(name="__fake_trainer__")
    class FakeTrainer: pass

    assert TRAINERS.get("__fake_trainer__") is FakeTrainer
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/registry.py
from mmengine.registry import Registry

TRAINERS   = Registry("trainer",   scope="pet_infra")
EVALUATORS = Registry("evaluator", scope="pet_infra")
CONVERTERS = Registry("converter", scope="pet_infra")
METRICS    = Registry("metric",    scope="pet_infra")
DATASETS   = Registry("dataset",   scope="pet_infra")
STORAGE    = Registry("storage",   scope="pet_infra")

__all__ = ["TRAINERS", "EVALUATORS", "CONVERTERS", "METRICS", "DATASETS", "STORAGE"]
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/registry.py tests/test_registry.py
git commit -m "feat(pet-infra): add 6 plugin registries on top of mmengine-lite"
```

---

### Task B2: Base ABCs (trainer/evaluator/converter/metric/dataset/storage)

**Files:**
- Create: `src/pet_infra/base/__init__.py`
- Create: `src/pet_infra/base/trainer.py`
- Create: `src/pet_infra/base/evaluator.py`
- Create: `src/pet_infra/base/converter.py`
- Create: `src/pet_infra/base/metric.py`
- Create: `src/pet_infra/base/dataset.py`
- Create: `src/pet_infra/base/storage.py`
- Test: `tests/test_base_abcs.py`

Spec reference: Section 2.4.

- [ ] **Step 1: Write failing tests**

One test per ABC — each asserts that (a) the abstract method set is exactly the spec's methods, (b) instantiating the bare ABC raises `TypeError`, (c) a minimal concrete subclass that overrides all abstracts can be instantiated.

```python
# tests/test_base_abcs.py (excerpt)
import inspect
import pytest
from pathlib import Path
from pet_infra.base import (
    BaseConverter, BaseDataset, BaseEvaluator, BaseMetric, BaseStorage, BaseTrainer,
)
from pet_schema import EdgeFormat


def test_base_trainer_has_three_abstracts():
    abstracts = BaseTrainer.__abstractmethods__
    assert abstracts == {"fit", "validate_config", "estimate_resources"}


def test_cannot_instantiate_bare_abc():
    with pytest.raises(TypeError):
        BaseTrainer()


def test_base_converter_target_format_returns_edgeformat():
    class Fake(BaseConverter):
        def convert(self, source_card, convert_config, calibration_data_uri, output_dir): ...
        def target_format(self) -> EdgeFormat: return EdgeFormat.RKLLM
    assert Fake().target_format() is EdgeFormat.RKLLM
```

Similar short tests for BaseEvaluator (`evaluate`, `supports`), BaseMetric (`compute`, ClassVar `name` + `higher_is_better`), BaseDataset (`build`, `to_hf_dataset`, `modality`), BaseStorage (`read`, `write`, `exists`, `iter_prefix`).

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement each file**

Follow spec §2.4 signatures literally. Example:

```python
# src/pet_infra/base/trainer.py
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from pet_schema import ExperimentRecipe, ModelCard, ResourceSpec


class BaseTrainer(ABC):
    @abstractmethod
    def fit(
        self, recipe: ExperimentRecipe, resolved_config: dict, output_dir: Path,
    ) -> ModelCard: ...

    @abstractmethod
    def validate_config(self, resolved_config: dict) -> None: ...

    @abstractmethod
    def estimate_resources(self, resolved_config: dict) -> ResourceSpec: ...
```

```python
# src/pet_infra/base/__init__.py
from pet_infra.base.converter import BaseConverter
from pet_infra.base.dataset import BaseDataset
from pet_infra.base.evaluator import BaseEvaluator
from pet_infra.base.metric import BaseMetric
from pet_infra.base.storage import BaseStorage
from pet_infra.base.trainer import BaseTrainer

__all__ = [
    "BaseTrainer", "BaseEvaluator", "BaseConverter", "BaseMetric",
    "BaseDataset", "BaseStorage",
]
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/base/ tests/test_base_abcs.py
git commit -m "feat(pet-infra): add 6 Base ABCs (trainer/evaluator/converter/metric/dataset/storage)"
```

---

### Task B3: `LocalStorage` implementation (scheme `local://`)

**Files:**
- Create: `src/pet_infra/storage/__init__.py`
- Create: `src/pet_infra/storage/local.py`
- Test: `tests/test_storage_local.py`

- [ ] **Step 1: Write failing tests**

Use `tmp_path` fixture:
1. `LocalStorage().write("local:///abs/path/foo.bin", b"xyz")` returns absolute path string, writes bytes, mkdirs parents.
2. `.read(same_uri)` returns `b"xyz"`.
3. `.exists(same_uri)` is True; `.exists("local:///nonexistent")` is False.
4. `.iter_prefix("local:///abs/path/")` yields files under prefix, sorted.
5. Non-`local://` scheme raises `ValueError`.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/storage/local.py
from __future__ import annotations
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from pet_infra.base import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="local")
class LocalStorage(BaseStorage):
    scheme = "local"

    def _path(self, uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme != self.scheme:
            raise ValueError(f"LocalStorage cannot handle scheme={parsed.scheme!r}")
        return Path(parsed.path)

    def read(self, uri: str) -> bytes:
        return self._path(uri).read_bytes()

    def write(self, uri: str, data: bytes) -> str:
        p = self._path(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    def exists(self, uri: str) -> bool:
        return self._path(uri).exists()

    def iter_prefix(self, prefix: str) -> Iterator[str]:
        root = self._path(prefix)
        if root.is_file():
            yield f"{self.scheme}://{root}"
            return
        for p in sorted(root.rglob("*")):
            if p.is_file():
                yield f"{self.scheme}://{p}"
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/storage/ tests/test_storage_local.py
git commit -m "feat(pet-infra): add LocalStorage backend registered on scheme=local"
```

---

### Task B4: Self-registration entry point (`_register.py`)

**Files:**
- Create: `src/pet_infra/_register.py`

- [ ] **Step 1: Implement**

```python
# src/pet_infra/_register.py
def register_all() -> None:
    """Triggered via the `pet_infra.plugins` entry point.

    Imports every first-party plugin module so @register_module side-effects
    populate the registries before pet-infra hands control to the caller.
    """
    from pet_infra.storage import local  # noqa: F401
```

- [ ] **Step 2: Verify entry point works**

```bash
pip install -e ".[dev,api,sync]"
python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='pet_infra.plugins'):
    print(ep.name, '->', ep.load)
    ep.load()()
from pet_infra.registry import STORAGE
print('registered:', list(STORAGE.module_dict))
"
```
Expected: `registered: ['local']`.

- [ ] **Step 3: Commit**

```bash
git add src/pet_infra/_register.py
git commit -m "feat(pet-infra): register first-party plugins via entry_points"
```

---

### Task B5: Plugin discovery with required-filter

**Files:**
- Create: `src/pet_infra/plugins/__init__.py`
- Create: `src/pet_infra/plugins/discover.py`
- Test: `tests/test_plugins_discover.py`

Spec reference: Section 2.3.

- [ ] **Step 1: Write failing tests**

1. `discover_plugins()` loads all entry_points under group `pet_infra.plugins` and returns a sorted list of registered keys per registry (dict).
2. `discover_plugins(required=["pet_infra"])` only loads named entry_points.
3. `discover_plugins(required=["__missing__"])` raises `RuntimeError` listing missing names.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/plugins/discover.py
from __future__ import annotations
from importlib.metadata import entry_points
from typing import Iterable

GROUP = "pet_infra.plugins"


def discover_plugins(required: Iterable[str] | None = None) -> dict[str, list[str]]:
    eps = list(entry_points(group=GROUP))
    ep_names = {ep.name for ep in eps}
    if required is not None:
        missing = set(required) - ep_names
        if missing:
            raise RuntimeError(f"required plugins not installed: {sorted(missing)}")
        eps = [ep for ep in eps if ep.name in set(required)]
    for ep in eps:
        ep.load()()
    from pet_infra.registry import (
        CONVERTERS, DATASETS, EVALUATORS, METRICS, STORAGE, TRAINERS,
    )
    return {
        "trainers":   sorted(TRAINERS.module_dict.keys()),
        "evaluators": sorted(EVALUATORS.module_dict.keys()),
        "converters": sorted(CONVERTERS.module_dict.keys()),
        "metrics":    sorted(METRICS.module_dict.keys()),
        "datasets":   sorted(DATASETS.module_dict.keys()),
        "storage":    sorted(STORAGE.module_dict.keys()),
    }
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/plugins/ tests/test_plugins_discover.py
git commit -m "feat(pet-infra): plugin discovery with required-filter"
```

---

### Task B6: Hydra ConfigStore bridge

**Files:**
- Create: `src/pet_infra/hydra_plugins/__init__.py`
- Create: `src/pet_infra/hydra_plugins/structured.py`
- Test: `tests/test_hydra_plugins.py`

Spec reference: Section 4.7.

- [ ] **Step 1: Write failing test**

```python
# tests/test_hydra_plugins.py
from hydra.core.config_store import ConfigStore

def test_structured_configs_registered():
    from pet_infra.hydra_plugins.structured import register
    register()
    cs = ConfigStore.instance()
    assert "recipe" in cs.repo
    assert "trainer" in cs.repo
    assert "dataset" in cs.repo
    assert "evaluator" in cs.repo
    assert "converter" in cs.repo
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/hydra_plugins/structured.py
from hydra.core.config_store import ConfigStore
from pet_schema import (
    ConverterConfig, DatasetConfig, EvaluatorConfig, ExperimentRecipe, TrainerConfig,
)


def register() -> None:
    cs = ConfigStore.instance()
    cs.store(group="recipe",    name="base", node=ExperimentRecipe)
    cs.store(group="trainer",   name="base", node=TrainerConfig)
    cs.store(group="evaluator", name="base", node=EvaluatorConfig)
    cs.store(group="converter", name="base", node=ConverterConfig)
    cs.store(group="dataset",   name="base", node=DatasetConfig)
```

Wire `register()` into `_register.py` so it also fires on plugin discovery.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/hydra_plugins/ tests/test_hydra_plugins.py src/pet_infra/_register.py
git commit -m "feat(pet-infra): register pet-schema types with Hydra ConfigStore"
```

---

### Task B7: Recipe compose — Hydra compose + Pydantic validate

**Files:**
- Create: `src/pet_infra/recipe/__init__.py`
- Create: `src/pet_infra/recipe/compose.py`
- Test: `tests/test_recipe_compose.py`

Spec reference: Section 5.1 steps [1]–[3].

- [ ] **Step 1: Write failing test**

Given `tests/fixtures/recipe/minimal.yaml` (committed) that conforms to `ExperimentRecipe`, `compose_recipe(path, overrides=[])` returns `(recipe: ExperimentRecipe, resolved_config: dict, config_sha: str)`. `overrides=["recipe.description=override"]` changes the description. Malformed yaml → `pydantic.ValidationError`.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/recipe/compose.py
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Sequence

import yaml
from omegaconf import OmegaConf
from pet_schema import ExperimentRecipe


def compose_recipe(
    path: str | Path, overrides: Sequence[str] = (),
) -> tuple[ExperimentRecipe, dict, str]:
    cfg = OmegaConf.load(path)
    for ov in overrides:
        key, _, val = ov.partition("=")
        OmegaConf.update(cfg, key, yaml.safe_load(val))
    resolved = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(resolved, dict)
    recipe_section = resolved["recipe"] if "recipe" in resolved else resolved
    recipe = ExperimentRecipe.model_validate(recipe_section)
    config_sha = hashlib.sha256(
        json.dumps(resolved, sort_keys=True).encode()
    ).hexdigest()
    return recipe, resolved, config_sha
```

**Capability gap — deferred to Phase 3** (when pet-train first needs per-repo `configs/`):
- No `defaults:` list resolution (single-file yaml only)
- No Hydra config search paths across repos
- No multirun / sweep compilation from `AblationAxis`
- Override syntax limited to `key.path=<yaml-literal>` via `OmegaConf.update`

Task B7 delivers enough to validate a single-file recipe end-to-end, which is all Phase 1's smoke recipe needs.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/recipe/ tests/test_recipe_compose.py tests/fixtures/recipe/
git commit -m "feat(pet-infra): recipe compose → ExperimentRecipe + config sha"
```

---

### Task B8: Recipe DAG builder and topo order

**Files:**
- Create: `src/pet_infra/recipe/dag.py`
- Test: `tests/test_recipe_dag.py`

(Note: recipe.py in pet-schema already has `to_dag`; this module wraps it with execution-plan helpers.)

- [ ] **Step 1: Write failing test**

1. `build_execution_plan(recipe)` returns list of stage names in a valid topological order.
2. For a recipe with stages `distill → sft → dpo → eval_trained → quantize → eval_quantized`, the plan visits them in dependency order.
3. Cyclic recipe → `ValueError` (propagates from pet-schema).

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/recipe/dag.py
from __future__ import annotations
import networkx as nx
from pet_schema import ExperimentRecipe


def build_execution_plan(recipe: ExperimentRecipe) -> list[str]:
    g: nx.DiGraph = recipe.to_dag()
    return list(nx.topological_sort(g))
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/recipe/dag.py tests/test_recipe_dag.py
git commit -m "feat(pet-infra): topological execution plan"
```

---

### Task B9: ModelCard.id precomputation (content-addressed)

**Files:**
- Create: `src/pet_infra/recipe/card_id.py`
- Test: `tests/test_recipe_card_id.py`

Spec reference: Section 3.4 ModelCard.id docstring; Section 5.6 Idempotence.

- [ ] **Step 1: Write failing test**

1. `precompute_card_id(recipe_id="r1", stage_name="train", config_sha="abcdef1234")` returns `"r1_train_abcdef12"` (first 8 chars of sha).
2. Deterministic: same inputs → same id.
3. Rejects empty/None inputs (ValueError).

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/recipe/card_id.py
def precompute_card_id(recipe_id: str, stage_name: str, config_sha: str) -> str:
    if not (recipe_id and stage_name and config_sha):
        raise ValueError("all three inputs required to precompute card id")
    return f"{recipe_id}_{stage_name}_{config_sha[:8]}"
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/recipe/card_id.py tests/test_recipe_card_id.py
git commit -m "feat(pet-infra): content-addressed ModelCard.id precompute"
```

---

### Task B10: Preflight — fail-fast checks

**Files:**
- Create: `src/pet_infra/recipe/preflight.py`
- Test: `tests/test_recipe_preflight.py`

Spec reference: Section 5.4. Within Phase 1 scope, implement the four checks that don't require external systems (ClearML / DVC / GPU probe deferred):
- Every `stage.component_type` is registered in the right registry.
- Every `storage_uri` scheme in `inputs` is registered in STORAGE.
- DAG acyclic (re-uses B8).
- Every `ArtifactRef(ref_type="recipe_stage_output")` points to an upstream stage.

- [ ] **Step 1: Write failing tests** (one per check; each constructs a deliberately broken recipe and asserts `PreflightError` with a specific message prefix).

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/recipe/preflight.py
from __future__ import annotations
from urllib.parse import urlparse
from pet_schema import ExperimentRecipe
from pet_infra.registry import (
    CONVERTERS, EVALUATORS, STORAGE, TRAINERS,
)


class PreflightError(RuntimeError):
    pass


_REGISTRY_BY_NAME = {
    "trainers":   TRAINERS,
    "evaluators": EVALUATORS,
    "converters": CONVERTERS,
}


def preflight(recipe: ExperimentRecipe) -> None:
    for stage in recipe.stages:
        reg = _REGISTRY_BY_NAME[stage.component_registry]
        if stage.component_type not in reg.module_dict:
            raise PreflightError(
                f"stage {stage.name!r}: plugin {stage.component_type!r} "
                f"not registered in {stage.component_registry!r}"
            )
        for input_name, ref in stage.inputs.items():
            if ref.ref_type == "recipe_stage_output":
                upstream = {s.name for s in recipe.stages}
                if ref.ref_value not in upstream:
                    raise PreflightError(
                        f"stage {stage.name!r}: input {input_name!r} points to "
                        f"unknown upstream stage {ref.ref_value!r}"
                    )
            if ref.ref_type == "dvc_path":
                scheme = urlparse(ref.ref_value).scheme or "local"
                if scheme not in STORAGE.module_dict:
                    raise PreflightError(
                        f"stage {stage.name!r}: storage scheme {scheme!r} not registered"
                    )
    # DAG cycle already caught by ExperimentRecipe model_validator
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/recipe/preflight.py tests/test_recipe_preflight.py
git commit -m "feat(pet-infra): recipe preflight fail-fast checks"
```

---

### Task B11: CLI — `pet list-plugins`

**Files:**
- Create: `src/pet_infra/cli.py`
- Test: `tests/test_cli_list_plugins.py`

- [ ] **Step 1: Write failing test**

Use `click.testing.CliRunner`:
1. `runner.invoke(main, ["list-plugins"])` exit_code == 0, stdout contains "storage" and "local".
2. `--json` flag outputs valid JSON with the 6 registry keys.

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/cli.py
from __future__ import annotations
import json as jsonlib
from pathlib import Path

import click


@click.group()
def main() -> None:
    """pet-infra CLI."""


@main.command("list-plugins")
@click.option("--json", "as_json", is_flag=True, help="emit JSON")
def list_plugins(as_json: bool) -> None:
    from pet_infra.plugins.discover import discover_plugins
    tree = discover_plugins()
    if as_json:
        click.echo(jsonlib.dumps(tree, indent=2))
        return
    for reg, keys in tree.items():
        click.echo(f"[{reg}]")
        for k in keys:
            click.echo(f"  - {k}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/cli.py tests/test_cli_list_plugins.py
git commit -m "feat(pet-infra): pet list-plugins CLI"
```

---

### Task B12: CLI — `pet validate --recipe=<path>`

**Files:**
- Modify: `src/pet_infra/cli.py`
- Test: `tests/test_cli_validate.py`

- [ ] **Step 1: Write failing test**

1. Given a well-formed smoke recipe yaml and a registered fake trainer fixture, `pet validate --recipe=<path>` returns exit 0 and prints "preflight: OK".
2. Given a recipe with unregistered component_type, exit != 0 and stderr contains "PreflightError".
3. `--override recipe.description=hello` applies the override (verified by `--dump-resolved` flag).

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** — wire `compose_recipe` + `preflight` behind `validate` subcommand.

```python
# src/pet_infra/cli.py (additions)

@main.command("validate")
@click.option("--recipe", "recipe_path", required=True, type=click.Path(exists=True))
@click.option("--override", "overrides", multiple=True)
@click.option("--dump-resolved", is_flag=True)
def validate_cmd(recipe_path, overrides, dump_resolved):
    from pet_infra.plugins.discover import discover_plugins
    from pet_infra.recipe.compose import compose_recipe
    from pet_infra.recipe.preflight import PreflightError, preflight

    discover_plugins()
    try:
        recipe, resolved, sha = compose_recipe(recipe_path, list(overrides))
        preflight(recipe)
    except PreflightError as e:
        click.secho(f"PreflightError: {e}", fg="red", err=True)
        raise SystemExit(2)
    if dump_resolved:
        import json as jsonlib
        click.echo(jsonlib.dumps(resolved, indent=2))
    click.secho(f"preflight: OK  (sha={sha[:8]})", fg="green")
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_infra/cli.py tests/test_cli_validate.py
git commit -m "feat(pet-infra): pet validate --recipe CLI"
```

---

### Task B13: Smoke recipe + `test_smoke_recipe.py`

**Files:**
- Create: `recipes/smoke_foundation.yaml`
- Test: `tests/test_smoke_recipe.py`

- [ ] **Step 1: Write smoke recipe**

```yaml
# recipes/smoke_foundation.yaml
recipe:
  recipe_id: smoke_foundation
  description: "Phase 1 smoke — single fake trainer stage, no real compute"
  scope: single_repo
  owner_repo: pet-infra
  schema_version: "2.0.0"
  stages:
    - name: train
      component_registry: trainers
      component_type: pet_infra.fake_trainer
      inputs: {}
      config_path: trainer/fake_trainer
      depends_on: []
  variations: []
  produces:
    - fake_model_v1
  default_storage: local
  required_plugins:
    - pet_infra
```

- [ ] **Step 2: Write failing test**

The test (a) registers a fake trainer `pet_infra.fake_trainer` within a fixture, (b) runs `pet validate --recipe=recipes/smoke_foundation.yaml` via `CliRunner`, (c) asserts exit 0 and preflight OK.

- [ ] **Step 3: Run → FAIL** (fails because fake trainer not registered by default)

- [ ] **Step 4: Implement — fixture-only registration**

Register the fake trainer inside the test fixture (not in the production package):

```python
# tests/test_smoke_recipe.py
import pytest
from click.testing import CliRunner
from pathlib import Path
from pet_infra.base import BaseTrainer
from pet_infra.registry import TRAINERS
from pet_infra.cli import main


@pytest.fixture
def fake_trainer_registered():
    @TRAINERS.register_module(name="pet_infra.fake_trainer", force=True)
    class _FakeTrainer(BaseTrainer):
        def fit(self, recipe, resolved_config, output_dir): ...
        def validate_config(self, resolved_config): ...
        def estimate_resources(self, resolved_config): ...
    yield
    TRAINERS.module_dict.pop("pet_infra.fake_trainer", None)


def test_smoke_recipe_preflight_passes(fake_trainer_registered):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["validate", "--recipe", "recipes/smoke_foundation.yaml"],
    )
    assert result.exit_code == 0, result.output
    assert "preflight: OK" in result.output
```

Production code **must not** ship a fake trainer — Phase 1 deliberately has no real TRAINERS plugin; downstream repos (pet-train) add them in Phase 3.

- [ ] **Step 5: Run → PASS**

- [ ] **Step 6: Commit**

```bash
git add recipes/smoke_foundation.yaml recipes/ablation/.gitkeep tests/test_smoke_recipe.py
git commit -m "feat(pet-infra): smoke foundation recipe + end-to-end preflight test"
```

---

### Task B14: CI workflows

> **Ordering note:** Task B15 (`compatibility_matrix.yaml`) must be committed **before** this task's `schema-validation.yml` pushes to CI, because `schema-validation.yml` reads that file. Implement B15 first, then B14. The numbering is kept for spec readability but execution order is B15 → B14.



**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `.github/workflows/schema-validation.yml`
- Create: `.github/workflows/plugin-discovery.yml`
- Create: `.github/workflows/recipe-dry-run.yml`

Spec reference: Section 6.3.

- [ ] **Step 1: Write `plugin-discovery.yml`**

```yaml
name: plugin-discovery
on:
  pull_request: { branches: [dev, main] }
  push:         { branches: [dev, main] }
jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - name: pet list-plugins
        run: |
          pet list-plugins --json > plugins.json
          cat plugins.json
          python -c "import json; d=json.load(open('plugins.json')); assert 'local' in d['storage'], d"
```

- [ ] **Step 2: Write `recipe-dry-run.yml`**

```yaml
name: recipe-dry-run
on:
  pull_request: { branches: [dev, main] }
  push:         { branches: [dev, main] }
jobs:
  dryrun:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - name: validate every recipe
        run: |
          shopt -s nullglob
          for r in recipes/*.yaml recipes/**/*.yaml; do
            echo "::group::$r"
            pet validate --recipe="$r"
            echo "::endgroup::"
          done
```

- [ ] **Step 3: Write `schema-validation.yml`** (assembles compatibility_matrix; full impl matures with later Phases but Phase 1 checks the file parses + lists expected keys)

```yaml
name: schema-validation
on:
  pull_request: { branches: [dev, main] }
  push:         { branches: [dev, main] }
jobs:
  matrix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pyyaml
      - name: check compatibility_matrix schema
        run: |
          python - <<'PY'
          import yaml, sys
          m = yaml.safe_load(open('docs/compatibility_matrix.yaml'))
          assert 'releases' in m, m
          for r in m['releases']:
              for k in ['release','pet_schema','pet_infra','pet_data','pet_annotation',
                       'pet_train','pet_eval','pet_quantize','pet_ota']:
                  assert k in r, f'missing {k} in {r}'
          PY
```

- [ ] **Step 4: Keep existing `ci.yml` (lint + test) untouched**

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/schema-validation.yml .github/workflows/plugin-discovery.yml .github/workflows/recipe-dry-run.yml
git commit -m "ci(pet-infra): add schema-validation / plugin-discovery / recipe-dry-run jobs"
```

---

### Task B15: `compatibility_matrix.yaml`

**Files:**
- Create: `docs/compatibility_matrix.yaml`

- [ ] **Step 1: Write matrix**

```yaml
releases:
  - release: "2026.05-phase1"
    pet_schema: "2.0.0"
    pet_infra: "2.0.0"
    # Phases 2-5 still on 1.x until migrated
    pet_data: "1.4.0"
    pet_annotation: "1.2.0"
    pet_train: "1.1.0"
    pet_eval: "1.3.0"
    pet_quantize: "1.1.0"
    pet_ota: "1.1.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
```

- [ ] **Step 2: Commit**

```bash
git add docs/compatibility_matrix.yaml
git commit -m "docs(pet-infra): initial compatibility_matrix for 2026.05-phase1"
```

---

### Task B16: Update DEVELOPMENT_GUIDE

**Files:**
- Modify: `docs/DEVELOPMENT_GUIDE.md`

- [ ] **Step 1: Add Phase 1 section** covering the 6 registries, Base ABCs, `pet` CLI commands, Hydra ConfigStore, recipe layout (`pet-infra/recipes/*.yaml`, `pet-{repo}/configs/experiment/*.yaml`), preflight checks, compatibility matrix. Cross-link to the spec.

- [ ] **Step 2: Commit**

```bash
git add docs/DEVELOPMENT_GUIDE.md
git commit -m "docs(pet-infra): document Phase 1 Foundation runtime (registry/CLI/recipe)"
```

---

### Task B17: Full-suite lint/test + open PR pet-infra → dev

- [ ] **Step 1: Run full suite**

```bash
pip install -e ".[dev,api,sync]"
pytest tests/ -v
ruff check src/ tests/ && mypy src/
```
Expected: all green.

- [ ] **Step 2: Push branch + open PR**

```bash
git push -u origin feature/phase-1-foundation-runtime
gh pr create --base dev --title "feat(pet-infra): Phase 1 Foundation runtime (2.0.0)" \
  --body "$(cat <<'EOF'
## Summary
- 6 Plugin Registries + 6 Base ABCs + LocalStorage
- Hydra ConfigStore bridge (pet-schema structured configs)
- Recipe compose / DAG / card_id / preflight
- pet CLI: list-plugins, validate
- Smoke recipe + 3 new CI jobs (schema-validation / plugin-discovery / recipe-dry-run)
- Depends on pet-schema 2.0.0

## Test plan
- [ ] All existing pet-infra tests pass
- [ ] New Phase 1 tests green (registry, base, storage, hydra, plugins, recipe/*, cli/*, smoke)
- [ ] `pet list-plugins` shows LocalStorage
- [ ] `pet validate --recipe=recipes/smoke_foundation.yaml` passes
- [ ] CI schema-validation / plugin-discovery / recipe-dry-run green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: After CI green + 1 reviewer approval → merge into dev**

- [ ] **Step 4: Open `dev → main` PR, merge, tag**

```bash
git checkout main && git pull origin main
gh pr create --base main --head dev --title "release(pet-infra): 2.0.0" --body "Phase 1 Foundation runtime"
# after merge:
git pull origin main
git tag v2.0.0
git push origin v2.0.0
```

---

## Part C — Phase 1 Definition-of-Done verification

### Task C1: `pet list-plugins` end-to-end

- [ ] In a clean venv, `pip install "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.0.0"` then run `pet list-plugins` — expect `local` under `storage`.

### Task C2: smoke recipe preflight over the tag

- [ ] Clone `pet-infra@v2.0.0` fresh, `pet validate --recipe=recipes/smoke_foundation.yaml` → PASS.

### Task C3: pet-schema tagged + downstream pin workable

- [ ] Confirm GitHub tag `pet-schema v2.0.0` exists.
- [ ] Create a one-off scratch project `pip install "pet-schema @ git+...@v2.0.0"`; `python -c "from pet_schema import ModelCard, ExperimentRecipe, VisionSample; print('ok')"` → prints `ok`.

### Task C4: Update project memory

- [ ] After both PRs merge, update `project_multi_model_refactor.md` (Status section) to record Phase 1 shipped + tag refs. Keep other memory files unchanged.

---

## Reference map — where each spec section is exercised

| Spec § | Delivered by task |
|---|---|
| 2.1, 2.2 | B1 |
| 2.3 | B4, B5 |
| 2.4 | B2 |
| 3.2 | A3 |
| 3.3 | A4 |
| 3.4 | A5 |
| 3.5 | A6 |
| 3.8 | A7 |
| 3.9 | A8 |
| 4.7 | B6 |
| 5.1 [1]–[3] | B7, B12 |
| 5.4 | B10, B12 |
| 5.6 | B9 |
| 6.3 | B14 |
| 6.2 (matrix) | B15 |
| 7.2 DoD | C1–C3 |

## Out of scope for Phase 1 (deferred to later phases per spec §7.9)

- S3 / WebDataset storage real implementations (ABC + LocalStorage only)
- ClearML Task runtime (OfflineMode plumbing defers to Phase 3)
- DVC `dvc.yaml` generation / `dvc repro` integration (defers to Phase 3)
- GPU / Kubernetes resource preflight probing
- `pet run` actual execution (Phase 1 ships `--dry-run` equivalent via `pet validate`)

---

## Remember
- Exact file paths always ✓
- Complete code in plan (not "add validation") ✓
- Exact commands with expected output ✓
- Reference to @spec at the top ✓
- DRY, YAGNI, TDD, frequent commits ✓

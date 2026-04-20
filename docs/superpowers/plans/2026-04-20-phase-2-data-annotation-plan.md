# Phase 2 Data & Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `pet-data` and `pet-annotation` onto the Phase 1 Foundation — introduce `modality` + `storage_uri` columns, split the monolithic `FrameRecord` / `AnnotationRecord` into modality-aware sibling types aligned with `pet-schema` v2.0.0 (`VisionSample` / `AudioSample` / `VisionAnnotation` / `AudioAnnotation`), Hydra-ify both CLIs, register each repo's dataset loader as a `@DATASETS.register_module()` plugin, and prove the wiring with one cross-repo smoke recipe `pet run recipe=pet_data_ingest` (cross-repo scope, exercised from pet-infra but not yet executing training).

**Architecture:** Additive DB migrations (CLAUDE.md: 已提交的迁移只允许新增，不允许修改). `002_add_modality_storage_uri.{py,sql}` adds non-null columns with defaults to existing `frames` / `annotations` tables; `003_add_audio_samples.{py,sql}` creates `audio_samples` + `audio_annotations` tables. Python code introduces `VisionSample` / `AudioSample` adapter dataclasses over the DB rows (subclassing `pet_schema.samples.VisionSample` / `AudioSample`), the adapter lives in each repo's `storage/adapter.py`. CLI is Hydra-ified using pet-infra's `ConfigStore` bridge and registered via the `pet_infra` plugin entry-point group (`pet_infra.plugins` for pet-data / pet-annotation), so `pet list-plugins` surfaces the new `pet_data.*` and `pet_annotation.*` keys. A new smoke recipe in pet-infra (`recipes/pet_data_ingest_smoke.yaml`) drives the `ingest → dedup → quality` pipeline end-to-end against a fixture local source, proving the dataset plugin dispatch and `VisionSample` round-trip.

**Tech Stack:** Python 3.11, sqlite3 stdlib (hand-written migrations, not Alembic — matching existing pattern), Pydantic v2 discriminated unions (from pet-schema v2.0.0), mmengine-lite Registry (from pet-infra v2.0.0), Hydra 1.3 (ConfigStore + compose), click ≥ 8.1 (retained for pet-annotation; pet-data migrates argparse → click for consistency), pytest + mypy + ruff.

**Spec:** `pet-infra/docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md` — cross-reference §3.2/3.3 (Sample/Annotation contracts), §3.9 (Structured Configs), §4.1/4.2 (Hydra layout), §6.1 (Plugin discovery), §7.3 (Phase 2 deliverables / DoD), §7.7 (risk register).

**Branch strategy** (CLAUDE.md PR workflow, strict):

- pet-data:       `feature/phase-2-modality-refactor` → `dev` → `main` (tag `v1.1.0`)
- pet-annotation: `feature/phase-2-modality-refactor` → `dev` → `main` (tag `v1.1.0`)
- pet-infra:      `feature/phase-2-smoke-recipe`      → `dev` → `main` (tag `v2.1.0`, compatibility matrix bump)

pet-data and pet-annotation can be worked on in parallel (Part A and Part B). Both must merge before pet-infra Part C (smoke recipe + matrix bump).

**Deviations from spec (flagged for DEVELOPMENT_GUIDE sync):**

1. Spec §7.3 says "Alembic migration", but neither repo uses Alembic — they use hand-written SQL+Python migrations (pet-data `storage/migrations/NNN_init.py`, pet-annotation `migrations/NNN_*.sql`). We stay with the existing pattern (no new infrastructure) and surface this deviation in DEVELOPMENT_GUIDE Phase 2 section. CLAUDE.md's "已提交的 Alembic 迁移文件不允许修改" rule applies semantically to *any* committed migration; we add new files, never edit existing ones.
2. Spec §7.3 says "`FrameRecord` 迁移为 `VisionSample`" — taken literally, this would drop pet-data domain columns (`phash`, `quality_flag`, `anomaly_score`, `annotation_status`, etc.). We interpret pragmatically: the **external contract** exposed to downstream repos is `VisionSample` (pet-schema v2.0.0), while pet-data's DB retains its internal state columns. A `to_vision_sample()` adapter on the row dataclass produces the public contract; downstream consumers (pet-train, pet-annotation) only see `VisionSample`. This is called out in `docs/DEVELOPMENT_GUIDE.md` §10 update.

---

## Phase 1 v2.0.0 contracts (verified — do not redesign)

These signatures and names were read directly from the installed v2.0.0 packages on 2026-04-21. Every task below assumes them. If any differ when a subagent starts, stop and surface the discrepancy rather than adapting the plan.

**pet-infra v2.0.0 — `src/pet_infra/base/dataset.py`:**

```python
class BaseDataset(ABC):
    @abstractmethod
    def build(self, dataset_config: dict) -> Iterable[BaseSample]: ...
    @abstractmethod
    def to_hf_dataset(self, dataset_config: dict) -> "datasets.Dataset": ...
    @abstractmethod
    def modality(self) -> Literal["vision", "audio", "sensor", "multimodal"]: ...
```

All three are `@abstractmethod`. `modality` is a method, **not** a class attribute. Plugins MUST implement all three; a class attribute `modality = "vision"` will NOT satisfy the ABC (instantiation raises `TypeError`).

**pet-infra v2.0.0 — `src/pet_infra/plugins/discover.py`:**

```python
def discover_plugins(required: Iterable[str] | None = None) -> dict[str, list[str]]: ...
```

The function name is `discover_plugins` (not `load_all`). It returns a dict with six keys (`trainers`, `evaluators`, `converters`, `metrics`, `datasets`, `storage`).

**pet-infra v2.0.0 — `src/pet_infra/cli.py`:**

```
pet list-plugins [--json]
pet validate --recipe <path> [--override k=v ...] [--dump-resolved]
```

`pet validate` takes `--recipe <path>` (required option, NOT positional). `pet list-plugins` has NO `--group` flag — filter downstream with `jq` or `grep` over `--json`.

**pet-infra v2.0.0 — `src/pet_infra/_register.py`:** the entry-point target function is `register_all`. Downstream plugins (pet-data, pet-annotation) MUST expose a callable named `register_all` under `[project.entry-points."pet_infra.plugins"]` for consistency:

```toml
[project.entry-points."pet_infra.plugins"]
pet_data = "pet_data._register:register_all"
```

**pet-infra v2.0.0 — `src/pet_infra/registry.py`:** all six registries expose `module_dict` as the public attribute. Do NOT use `_module_dict` in tests — it works today but is private.

**pet-infra v2.0.0 — `src/pet_infra/recipe/preflight.py`:** preflight validates `stage.component_type` against the stage's registry (trainers / evaluators / converters only). It does NOT validate `ref_type: dataset` inputs against `DATASETS.module_dict`. Therefore the smoke recipe needs a real `component_type` registered in EVALUATORS (see Task C1.5: `pet_infra.noop_evaluator`).

**pet-data v1.0.0 — `src/pet_data/storage/store.py`:** `FrameStore.insert_frame(frame: FrameRecord) -> str` (named `insert_frame`, not `insert`). Tests that INSERT rows must use `insert_frame`. `FrameStore.__init__` directly executes `schema.sql`; the numbered migrations under `storage/migrations/` are NOT auto-run — they're only applied by the test suite. Phase 2 must extend `FrameStore.__init__` to apply migrations 002 + 003 *after* `schema.sql` (see Task A5 addendum).

**pet-annotation v1.0.0 — `src/pet_annotation/store.py`:** `AnnotationStore.insert_annotation(rec: AnnotationRecord)` is the insert method (not `insert`). `_apply_migration()` reads a single file (`migrations/001_create_annotation_tables.sql`); Phase 2 extends this to glob `migrations/*.sql` sorted, tolerating duplicate-apply via `sqlite3.OperationalError` catch around each `ALTER TABLE ADD COLUMN`.

**pet-schema v2.0.0 — `samples.py` VisionSample required fields:** `frame_width: int`, `frame_height: int`, `lighting: Lighting`, `blur_score: float`, `brightness_score: float` are all REQUIRED (no defaults). Therefore migration 002 adds nullable columns for back-compat of existing rows, but the `VisionFramesDataset.build()` MUST filter `WHERE frame_width IS NOT NULL AND frame_height IS NOT NULL AND brightness_score IS NOT NULL` and skip rows that fail the filter. New rows inserted by `sources/base.py` (Task A11) MUST populate all three.

---

## File Structure

### Part A — pet-data changes

```
pet-data/
├── pyproject.toml                                          MODIFY  bump v1.1.0; pin pet-schema v2.0.0 + pet-infra v2.0.0; add hydra-core + mmengine-lite + click; add [project.entry-points."pet_infra.plugins"] self-register
├── params.yaml                                             MODIFY  add `modality` default ("vision") and `storage_scheme` ("local") under new top-level `sample` key (no hardcoding in code)
├── src/pet_data/
│   ├── __init__.py                                         MODIFY  __version__ = "1.1.0"
│   ├── _register.py                                        CREATE  entry_points target — registers VisionFramesDataset + AudioClipsDataset plugins
│   ├── cli.py                                              MODIFY  argparse → click + Hydra (hydra.main on new command group `pet-data run` + retain legacy subcommands as @hydra_decorated commands during transition)
│   ├── configs/                                            CREATE  Hydra config group
│   │   ├── _global_/defaults.yaml                          CREATE
│   │   ├── dataset/vision_frames.yaml                      CREATE
│   │   ├── dataset/audio_clips.yaml                        CREATE
│   │   └── experiment/pet_data_ingest.yaml                 CREATE  single-repo recipe
│   ├── storage/
│   │   ├── store.py                                        MODIFY  add `modality` + `storage_uri` columns to INSERT/UPDATE/SELECT in FrameStore; add AudioStore; FrameRecord → VisionFrameRow dataclass with `to_vision_sample()` adapter
│   │   ├── adapter.py                                      CREATE  Row → pet_schema.VisionSample / AudioSample conversion (single place)
│   │   ├── schema.sql                                      KEEP    do not edit (CLAUDE.md: committed migrations immutable)
│   │   └── migrations/
│   │       ├── 001_init.py                                 KEEP    immutable
│   │       ├── 002_add_modality_storage_uri.py             CREATE  adds `modality TEXT NOT NULL DEFAULT 'vision'`, `storage_uri TEXT NOT NULL DEFAULT ''` to `frames` (backfills from frame_path + data_root); adds `frame_width`, `frame_height`, `brightness_score` columns
│   │       └── 003_add_audio_samples.py                    CREATE  creates `audio_samples` table matching pet_schema.AudioSample + `audio_annotations` placeholder (Part B owns writes; pet-data only defines the shape)
│   ├── datasets/                                           CREATE  dataset plugin package
│   │   ├── __init__.py                                     CREATE
│   │   ├── vision_frames.py                                CREATE  @DATASETS.register_module("pet_data.vision_frames") — iterates VisionFrameRow, yields pet_schema.VisionSample
│   │   └── audio_clips.py                                  CREATE  @DATASETS.register_module("pet_data.audio_clips") — iterates AudioSampleRow, yields pet_schema.AudioSample
│   └── sources/base.py                                     MODIFY  source classes emit modality-tagged rows (vision default for existing 7 sources; placeholder unused kwarg for future audio sources)
└── tests/
    ├── test_store.py                                       MODIFY  assert new columns, modality filtering in query
    ├── test_store_audio.py                                 CREATE  AudioStore CRUD
    ├── test_migrations.py                                  MODIFY  upgrade 001→002→003 then downgrade 003→002→001 round-trip
    ├── test_adapter.py                                     CREATE  VisionFrameRow.to_vision_sample() round-trips through Pydantic
    ├── test_datasets_vision.py                             CREATE  VisionFramesDataset plugin iterates & yields VisionSample
    ├── test_datasets_audio.py                              CREATE  AudioClipsDataset plugin iterates & yields AudioSample
    ├── test_cli_hydra.py                                   CREATE  hydra override at CLI: `pet-data run dataset=vision_frames`
    └── test_plugin_registration.py                         CREATE  import pet_data triggers entry_points; DATASETS.get("pet_data.vision_frames") returns class
```

### Part B — pet-annotation changes

```
pet-annotation/
├── pyproject.toml                                          MODIFY  bump v1.1.0; pin pet-schema v2.0.0 + pet-infra v2.0.0; add hydra-core + mmengine-lite; add [project.entry-points."pet_infra.plugins"] self-register
├── params.yaml                                             MODIFY  add `annotation.modality_default: "vision"` (no hardcoding)
├── src/pet_annotation/
│   ├── __init__.py                                         MODIFY  __version__ = "1.1.0"
│   ├── _register.py                                        CREATE  entry_points target — registers VisionAnnotationsDataset + AudioAnnotationsDataset + cross-repo exports
│   ├── cli.py                                              MODIFY  click → click-over-hydra (retain click subcommand shape, inject Hydra resolved config per command via pet-infra compose helper); all subcommands accept `--modality {vision|audio}`
│   ├── configs/                                            CREATE
│   │   ├── _global_/defaults.yaml                          CREATE
│   │   ├── dataset/vision_annotations.yaml                 CREATE
│   │   ├── dataset/audio_annotations.yaml                  CREATE
│   │   └── experiment/pet_annotation_vision.yaml           CREATE
│   ├── store.py                                            MODIFY  AnnotationRecord → VisionAnnotationRow + AudioAnnotationRow with to_vision_annotation() / to_audio_annotation() adapters; queries filter by modality
│   ├── adapter.py                                          CREATE  Row ↔ pet_schema.VisionAnnotation / AudioAnnotation
│   ├── human_review/
│   │   ├── templates/
│   │   │   ├── __init__.py                                 CREATE
│   │   │   ├── vision.xml                                  CREATE  (content moved from import_to_ls.py hardcoded block)
│   │   │   └── audio.xml                                   CREATE  (waveform + audio-appropriate label layout)
│   │   ├── templates.py                                    CREATE  template_for(modality: Modality) -> str; loads resource from templates/*.xml
│   │   └── import_to_ls.py                                 MODIFY  dispatch template by modality; `import_needs_review(modality=...)`
│   ├── export/
│   │   ├── to_sharegpt.py                                  MODIFY  modality filter; only vision
│   │   ├── to_audio_labels.py                              MODIFY  replace NotImplementedError with real JSONL writer (class + probs)
│   │   └── to_dpo_pairs.py                                 MODIFY  modality filter; only vision (audio DPO is out-of-scope Phase 2)
│   ├── dpo/generate_pairs.py                               MODIFY  `generate_cross_model_pairs(modality="vision")` — default preserves behaviour
│   └── datasets/                                           CREATE  dataset plugin package
│       ├── __init__.py                                     CREATE
│       ├── vision_annotations.py                           CREATE  @DATASETS.register_module("pet_annotation.vision_annotations")
│       └── audio_annotations.py                            CREATE  @DATASETS.register_module("pet_annotation.audio_annotations")
├── migrations/
│   ├── 001_create_annotation_tables.sql                    KEEP    immutable
│   ├── 002_add_modality.sql                                CREATE  ALTER TABLE annotations ADD modality TEXT NOT NULL DEFAULT 'vision'; same for model_comparisons; add storage_uri in annotations (references sample.storage_uri)
│   └── 003_create_audio_annotations.sql                    CREATE  CREATE TABLE audio_annotations (annotation_id PK, sample_id, annotator_type, annotator_id, modality='audio' CHECK, predicted_class, class_probs JSON, logits JSON, created_at, schema_version)
└── tests/
    ├── test_store.py                                       MODIFY  AnnotationRecord split assertions
    ├── test_store_audio.py                                 CREATE
    ├── test_adapter.py                                     CREATE
    ├── test_templates.py                                   CREATE  template_for(vision|audio) returns expected XML skeleton
    ├── test_export_audio.py                                CREATE  to_audio_labels emits valid JSONL (class, probs, sample_id)
    ├── test_datasets_plugins.py                            CREATE
    ├── test_plugin_registration.py                         CREATE
    └── test_cli_modality_dispatch.py                       CREATE
```

### Part C — pet-infra changes

```
pet-infra/
├── pyproject.toml                                          MODIFY  bump v2.1.0
├── docs/
│   ├── DEVELOPMENT_GUIDE.md                                MODIFY  add §10 "Phase 2 Data & Annotation runtime" (modality discriminator, LS template dispatch, Dataset plugin contract, migration path from FrameRecord)
│   └── compatibility_matrix.yaml                           MODIFY  add release 2026.05 (or bump existing) with pet_data 1.1.0 + pet_annotation 1.1.0
├── recipes/
│   ├── pet_data_ingest_smoke.yaml                          CREATE  cross-repo smoke recipe that loads VisionFramesDataset + runs a no-op eval stage to prove dispatch
│   └── .gitkeep                                            KEEP
├── src/pet_infra/
│   └── base/dataset.py                                     KEEP    (contract already exists; no change needed — audited for completeness at start of Part C)
├── .github/workflows/
│   ├── plugin-discovery.yml                                MODIFY  add pet-data + pet-annotation to the install matrix; assert 4 new plugin keys registered
│   └── recipe-dry-run.yml                                  MODIFY  pick up new smoke recipe automatically (glob already matches); no edit if glob is `recipes/*.yaml` — CONFIRM
└── tests/
    └── integration/
        └── test_phase2_smoke.py                            CREATE  end-to-end: install pet-data & pet-annotation into an editable venv, run `pet validate --recipe recipes/pet_data_ingest_smoke.yaml`, assert preflight passes, assert DATASETS.get(...) resolves 4 keys
```

**Decomposition rule followed:** one file = one responsibility; new files stay < 180 LOC; tests colocated with code; each migration is independent and atomic.

---

## Execution order & dependency map

```
Part A (pet-data)          Part B (pet-annotation)
     │                              │
     ├── A0 branch                   ├── B0 branch
     ├── A1 pin v2.0.0 deps          ├── B1 pin v2.0.0 deps
     ├── A2 migration 002            ├── B2 migration 002
     ├── A3 migration 003            ├── B3 migration 003
     ├── A4 store adapter            ├── B4 store adapter + Row split
     ├── A5 FrameRecord → Row        ├── B5 LS templates extracted
     ├── A6 VisionFramesDataset      ├── B6 template dispatch + tests
     ├── A7 AudioClipsDataset        ├── B7 VisionAnnotationsDataset
     ├── A8 _register.py + entry-pt  ├── B8 AudioAnnotationsDataset
     ├── A9 Hydra configs            ├── B9 _register.py + entry-pt
     ├── A10 CLI Hydra-ify           ├── B10 Hydra configs
     ├── A11 sources.base modality   ├── B11 CLI modality dispatch
     ├── A12 params.yaml             ├── B12 export audio impl
     ├── A13 CI + ruff + mypy        ├── B13 dpo modality filter
     └── A14 PR dev → main           ├── B14 params.yaml + CI
                                     └── B15 PR dev → main
     (PR must merge to main)         (PR must merge to main)
                     │                           │
                     └────────── both merged ────┘
                                  │
                             Part C (pet-infra)
                                  │
                                  ├── C0 branch
                                  ├── C1 smoke-verify Phase 1 contracts
                                  ├── C1.5 add pet_infra.noop_evaluator
                                  ├── C2 smoke recipe yaml
                                  ├── C3 integration test
                                  ├── C4 plugin-discovery.yml
                                  ├── C5 DEVELOPMENT_GUIDE §10
                                  ├── C6 compatibility_matrix bump
                                  └── C7 PR dev → main, tag v2.1.0
```

Part A and Part B are independent — they touch different repos and do not share code. Part C depends on both. **Execute A and B in parallel subagents; serialize C.**

---

## Part A — pet-data refactor

Work in `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-data/` on branch `feature/phase-2-modality-refactor` off `dev`.

### Task A0: Branch setup

**Files:**
- (no edits)

- [ ] **Step 1: Create branch off dev**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-data
git fetch origin
git checkout dev && git pull origin dev
git checkout -b feature/phase-2-modality-refactor
```

- [ ] **Step 2: Verify existing tests pass on clean checkout**

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

Expected: 79 tests pass (per memory).

---

### Task A1: Bump deps — pet-schema v2.0.0 + pet-infra v2.0.0

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing test**

```python
# tests/test_version.py  (CREATE)
import pet_data
import pet_schema
import pet_infra

def test_pet_data_version():
    assert pet_data.__version__ == "1.1.0"

def test_pet_data_pins_phase1_foundation():
    assert pet_schema.version.SCHEMA_VERSION == "2.0.0"
    assert pet_infra.__version__.startswith("2.")
```

- [ ] **Step 2: Run → FAIL**

```bash
pytest tests/test_version.py -v
```

- [ ] **Step 3: Update `pyproject.toml`**

Replace the two `@v1.0.0` lines with `@v2.0.0`; bump `version = "1.1.0"`; add new runtime deps:

```toml
dependencies = [
    "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema.git@v2.0.0",
    "pet-infra  @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v2.0.0",
    "Pillow>=10.0,<13.0",
    "imagehash>=4.3,<5.0",
    "albumentations>=1.3,<3.0",
    "torch>=2.1,<3.0",
    "torchvision>=0.16,<1.0",
    "scipy>=1.11,<2.0",
    "tenacity>=8.0,<9.0",
    "pyyaml>=6.0,<7.0",
    "dvc>=3.40,<4.0",
    "requests>=2.31,<3.0",
    "hydra-core>=1.3,<1.4",
    "mmengine-lite>=0.10,<0.12",
    "click>=8.1,<9.0",
]

[project.entry-points."pet_infra.plugins"]
pet_data = "pet_data._register:register_all"
```

Bump `src/pet_data/__init__.py` to `__version__ = "1.1.0"`.

- [ ] **Step 4: Reinstall + rerun**

```bash
pip install -e ".[dev]"
pytest tests/test_version.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/pet_data/__init__.py tests/test_version.py
git commit -m "chore(pet-data): pin pet-schema v2.0.0 + pet-infra v2.0.0; bump to 1.1.0"
```

---

### Task A2: Migration `002_add_modality_storage_uri.py`

**Files:**
- Create: `src/pet_data/storage/migrations/002_add_modality_storage_uri.py`
- Create: `tests/conftest_migrations.py` (shared loader helper — see Step 0)
- Test: `tests/test_migrations.py` (extend)

**Requirement:** Add columns to `frames`:
- `modality TEXT NOT NULL DEFAULT 'vision'` (matches pet_schema Modality literal; CHECK constraint for vision|audio|sensor|multimodal)
- `storage_uri TEXT NOT NULL DEFAULT ''` (backfilled from `'local://' || data_root || '/' || frame_path`)
- `frame_width INTEGER` (nullable — existing rows can't be backfilled without opening files)
- `frame_height INTEGER` (nullable)
- `brightness_score REAL` (nullable)

New rows emitted by `sources/base.py` (Task A11) MUST populate all three vision-specific columns so they satisfy `VisionSample`. Existing rows remain NULL until a separate backfill job runs (out of scope).

- [ ] **Step 0: Create shared migration loader helper**

Python identifiers cannot start with digits, so `001_init.py` / `002_*.py` are NOT regular importable modules — they must be loaded via `importlib.util`. Create `tests/conftest_migrations.py` once:

```python
# tests/conftest_migrations.py
"""Shared helper to load numbered migration modules by filename."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import ModuleType

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "pet_data" / "storage" / "migrations"


def load_migration(n: int) -> ModuleType:
    """Load migrations/NNN_*.py by its leading 3-digit number."""
    matches = list(MIGRATIONS_DIR.glob(f"{n:03d}_*.py"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one migration file for {n:03d}, got {matches}")
    path = matches[0]
    spec = importlib.util.spec_from_file_location(f"migration_{n:03d}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

- [ ] **Step 1: Write failing migration round-trip test**

```python
# tests/test_migrations.py  (append)
import sqlite3
from tests.conftest_migrations import load_migration

def test_002_upgrade_adds_columns(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    load_migration(1).upgrade(conn)
    load_migration(2).upgrade(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(frames)").fetchall()}
    assert {"modality", "storage_uri", "frame_width", "frame_height", "brightness_score"} <= cols
    conn.close()

def test_002_downgrade_drops_columns(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    m001 = load_migration(1); m002 = load_migration(2)
    m001.upgrade(conn); m002.upgrade(conn); m002.downgrade(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(frames)").fetchall()}
    assert "modality" not in cols and "storage_uri" not in cols

def test_002_backfills_storage_uri_for_existing_rows(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    load_migration(1).upgrade(conn)
    conn.execute(
        "INSERT INTO frames (frame_id, video_id, source, frame_path, data_root) "
        "VALUES ('f1', 'v1', 'youtube', 'frames/a.jpg', '/data')"
    )
    conn.commit()
    load_migration(2).upgrade(conn)
    row = conn.execute("SELECT modality, storage_uri FROM frames WHERE frame_id='f1'").fetchone()
    assert row[0] == "vision"
    assert row[1] == "local:///data/frames/a.jpg"
```

- [ ] **Step 2: Run → FAIL (module missing)**

```bash
pytest tests/test_migrations.py -v
```

- [ ] **Step 3: Write migration**

```python
# src/pet_data/storage/migrations/002_add_modality_storage_uri.py
"""Add modality + storage_uri + vision-specific columns to `frames`.

Part of Phase 2 multi-model refactor. Existing rows get modality='vision'
and a backfilled storage_uri derived from data_root + frame_path.
"""
from __future__ import annotations
import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        ALTER TABLE frames ADD COLUMN modality TEXT NOT NULL DEFAULT 'vision'
            CHECK (modality IN ('vision', 'audio', 'sensor', 'multimodal'));
        ALTER TABLE frames ADD COLUMN storage_uri TEXT NOT NULL DEFAULT '';
        ALTER TABLE frames ADD COLUMN frame_width INTEGER;
        ALTER TABLE frames ADD COLUMN frame_height INTEGER;
        ALTER TABLE frames ADD COLUMN brightness_score REAL;

        UPDATE frames
           SET storage_uri = 'local://' || data_root || '/' || frame_path
         WHERE storage_uri = '';

        CREATE INDEX IF NOT EXISTS idx_frames_modality ON frames(modality);
        """
    )
    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    # sqlite does not support DROP COLUMN < 3.35; rebuild via SELECT-INTO.
    conn.executescript(
        """
        DROP INDEX IF EXISTS idx_frames_modality;
        CREATE TABLE frames_tmp AS SELECT
            frame_id, video_id, source, frame_path, data_root, timestamp_ms,
            species, breed, lighting, bowl_type, quality_flag, blur_score,
            phash, aug_quality, aug_seed, parent_frame_id, is_anomaly_candidate,
            anomaly_score, annotation_status, created_at
        FROM frames;
        DROP TABLE frames;
        ALTER TABLE frames_tmp RENAME TO frames;
        """
    )
    conn.commit()
```

- [ ] **Step 4: Run → PASS**

```bash
pytest tests/test_migrations.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/storage/migrations/002_add_modality_storage_uri.py tests/test_migrations.py
git commit -m "feat(pet-data): migration 002 adds modality + storage_uri columns"
```

---

### Task A3: Migration `003_add_audio_samples.py`

**Files:**
- Create: `src/pet_data/storage/migrations/003_add_audio_samples.py`
- Test: `tests/test_migrations.py` (extend)

**Schema (matches pet_schema.AudioSample):**

```sql
CREATE TABLE audio_samples (
    sample_id TEXT PRIMARY KEY,
    modality TEXT NOT NULL DEFAULT 'audio' CHECK (modality = 'audio'),
    storage_uri TEXT NOT NULL,
    captured_at TIMESTAMP NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('youtube','community','device','synthetic')),
    source_id TEXT NOT NULL,
    source_license TEXT,
    pet_species TEXT,
    duration_s REAL NOT NULL,
    sample_rate INTEGER NOT NULL,
    num_channels INTEGER NOT NULL,
    snr_db REAL,
    clip_type TEXT CHECK (clip_type IN ('bark','meow','purr','silence','ambient')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audio_source ON audio_samples(source_id);
CREATE INDEX idx_audio_clip_type ON audio_samples(clip_type);
```

- [ ] **Step 1: Write failing test**

```python
def test_003_upgrade_creates_audio_table(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    load_migration(1).upgrade(conn)
    load_migration(2).upgrade(conn)
    load_migration(3).upgrade(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "audio_samples" in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(audio_samples)").fetchall()}
    assert {"sample_id","modality","storage_uri","duration_s","sample_rate","num_channels","clip_type"} <= cols

def test_003_downgrade_drops_audio_table(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    m1 = load_migration(1); m2 = load_migration(2); m3 = load_migration(3)
    m1.upgrade(conn); m2.upgrade(conn); m3.upgrade(conn); m3.downgrade(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "audio_samples" not in tables
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Write migration**

```python
# src/pet_data/storage/migrations/003_add_audio_samples.py
from __future__ import annotations
import sqlite3

AUDIO_SCHEMA = """
CREATE TABLE IF NOT EXISTS audio_samples (
    sample_id     TEXT PRIMARY KEY,
    modality      TEXT NOT NULL DEFAULT 'audio' CHECK (modality = 'audio'),
    storage_uri   TEXT NOT NULL,
    captured_at   TIMESTAMP NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN ('youtube','community','device','synthetic')),
    source_id     TEXT NOT NULL,
    source_license TEXT,
    pet_species   TEXT,
    duration_s    REAL NOT NULL,
    sample_rate   INTEGER NOT NULL,
    num_channels  INTEGER NOT NULL,
    snr_db        REAL,
    clip_type     TEXT CHECK (clip_type IN ('bark','meow','purr','silence','ambient')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audio_source ON audio_samples(source_id);
CREATE INDEX IF NOT EXISTS idx_audio_clip_type ON audio_samples(clip_type);
"""

def upgrade(conn: sqlite3.Connection) -> None:
    conn.executescript(AUDIO_SCHEMA)
    conn.commit()

def downgrade(conn: sqlite3.Connection) -> None:
    conn.executescript("DROP INDEX IF EXISTS idx_audio_clip_type; DROP INDEX IF EXISTS idx_audio_source; DROP TABLE IF EXISTS audio_samples;")
    conn.commit()
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/storage/migrations/003_add_audio_samples.py tests/test_migrations.py
git commit -m "feat(pet-data): migration 003 creates audio_samples table"
```

---

### Task A4: `storage/adapter.py` — Row → pet_schema Sample

**Files:**
- Create: `src/pet_data/storage/adapter.py`
- Test: `tests/test_adapter.py`

**Value-domain mismatch note (lighting):** pet-data's `schema.sql` CHECK constraint allows `{"bright","dim","infrared_night","unknown"}` and 6 of the 7 source classes hardcode `lighting="unknown"`. `pet_schema.Lighting` v2.0.0 accepts only `{"bright","dim","dark"}`. The adapter MUST normalize before constructing `VisionSample`, otherwise every existing row raises `ValidationError` on read. Normalization policy (this plan — document the choice, then apply it in the adapter):

| DB value         | pet_schema value |
|------------------|------------------|
| `bright`         | `bright`         |
| `dim`            | `dim`            |
| `infrared_night` | `dark`           |
| `unknown`        | `dim`            |  *(conservative default; matches "neither bright nor dark")*

Same adapter normalizes `lighting`; `VisionFramesDataset.build()` still runs the NULL-field filter documented in Phase 1 contracts. If the mapping needs to change, update this table and the adapter in lockstep — do NOT silently reinterpret.

- [ ] **Step 1: Failing test**

```python
# tests/test_adapter.py
from datetime import datetime
import pytest
from pet_schema.samples import VisionSample, AudioSample
from pet_data.storage.adapter import frame_row_to_vision_sample, audio_row_to_audio_sample

def test_frame_row_to_vision_sample_roundtrip():
    row = {
        "frame_id": "sha256:abc",
        "source": "youtube",
        "video_id": "vid1",
        "frame_path": "frames/a.jpg",
        "data_root": "/data",
        "storage_uri": "local:///data/frames/a.jpg",
        "timestamp_ms": 123456,
        "species": "dog",
        "lighting": "bright",
        "bowl_type": "ceramic",
        "blur_score": 120.5,
        "brightness_score": 0.6,
        "frame_width": 1920,
        "frame_height": 1080,
    }
    vs = frame_row_to_vision_sample(row)
    assert isinstance(vs, VisionSample)
    assert vs.sample_id == "sha256:abc"
    assert vs.storage_uri.startswith("local://")
    assert vs.modality == "vision"
    # Pydantic round-trip
    assert VisionSample.model_validate(vs.model_dump()) == vs

def test_audio_row_to_audio_sample_roundtrip():
    row = {
        "sample_id": "sha256:def",
        "storage_uri": "local:///data/audio/bark.wav",
        "captured_at": "2026-04-21T12:00:00Z",
        "source_type": "community",
        "source_id": "esc50",
        "source_license": "CC-BY",
        "pet_species": "dog",
        "duration_s": 5.0,
        "sample_rate": 44100,
        "num_channels": 1,
        "snr_db": 22.5,
        "clip_type": "bark",
    }
    a = audio_row_to_audio_sample(row)
    assert isinstance(a, AudioSample)
    assert a.modality == "audio"
    assert AudioSample.model_validate(a.model_dump()) == a


def _frame_row(**overrides):
    base = {
        "frame_id": "sha256:abc", "source": "youtube", "video_id": "vid1",
        "frame_path": "a.jpg", "data_root": "/d",
        "storage_uri": "local:///d/a.jpg", "timestamp_ms": 1,
        "species": "dog", "lighting": "bright", "bowl_type": "ceramic",
        "blur_score": 120.0, "brightness_score": 0.5,
        "frame_width": 1920, "frame_height": 1080,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("db_val,schema_val", [
    ("bright", "bright"),
    ("dim", "dim"),
    ("infrared_night", "dark"),
    ("unknown", "dim"),
])
def test_lighting_normalization(db_val, schema_val):
    vs = frame_row_to_vision_sample(_frame_row(lighting=db_val))
    assert vs.lighting == schema_val


def test_lighting_unknown_raises():
    with pytest.raises(ValueError, match="no mapping to pet_schema.Lighting"):
        frame_row_to_vision_sample(_frame_row(lighting="strobe"))
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement adapter**

```python
# src/pet_data/storage/adapter.py
"""Pure data mappers: sqlite rows -> pet_schema discriminated union types.

Keeping all mapping in one file ensures future schema changes touch a single adapter.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Mapping, Any

from pet_schema.samples import VisionSample, AudioSample, SourceInfo


def _parse_timestamp_ms(ts_ms: int | None) -> datetime:
    if ts_ms is None:
        raise ValueError("timestamp_ms is NULL; cannot derive captured_at")
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


# DB → pet_schema.Lighting normalization (see Task A4 policy table).
_LIGHTING_MAP = {
    "bright": "bright",
    "dim": "dim",
    "infrared_night": "dark",
    "unknown": "dim",
}


def _normalize_lighting(db_value: str) -> str:
    try:
        return _LIGHTING_MAP[db_value]
    except KeyError as e:
        raise ValueError(
            f"lighting={db_value!r} has no mapping to pet_schema.Lighting; "
            f"update _LIGHTING_MAP in adapter.py and document in Task A4 table"
        ) from e


def frame_row_to_vision_sample(row: Mapping[str, Any]) -> VisionSample:
    return VisionSample(
        sample_id=row["frame_id"],
        storage_uri=row["storage_uri"],
        captured_at=_parse_timestamp_ms(row["timestamp_ms"]),
        source=SourceInfo(
            source_type=row["source"],
            source_id=row.get("video_id") or row["frame_id"],
            license=row.get("source_license"),
        ),
        pet_species=row.get("species"),
        frame_width=row["frame_width"],
        frame_height=row["frame_height"],
        lighting=_normalize_lighting(row["lighting"]),
        bowl_type=row.get("bowl_type"),
        blur_score=row["blur_score"],
        brightness_score=row["brightness_score"],
    )


def audio_row_to_audio_sample(row: Mapping[str, Any]) -> AudioSample:
    captured = row["captured_at"]
    if isinstance(captured, str):
        captured = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    return AudioSample(
        sample_id=row["sample_id"],
        storage_uri=row["storage_uri"],
        captured_at=captured,
        source=SourceInfo(
            source_type=row["source_type"],
            source_id=row["source_id"],
            license=row.get("source_license"),
        ),
        pet_species=row.get("pet_species"),
        duration_s=row["duration_s"],
        sample_rate=row["sample_rate"],
        num_channels=row["num_channels"],
        snr_db=row.get("snr_db"),
        clip_type=row.get("clip_type"),
    )
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/storage/adapter.py tests/test_adapter.py
git commit -m "feat(pet-data): storage adapter maps DB rows to pet_schema Sample types"
```

---

### Task A5: Extend `FrameStore` for new columns; add `AudioStore`; apply migrations in production

**Files:**
- Modify: `src/pet_data/storage/store.py`
- Test: `tests/test_store.py` (modify), `tests/test_store_audio.py` (create)

**Scope:**
1. Extend `FrameRecord` dataclass with 5 new fields (modality, storage_uri, frame_width, frame_height, brightness_score), all with safe defaults for back-compat with existing callers.
2. Extend `FrameStore._record_to_params()` and `FrameStore.insert_frame()` INSERT statement to include the 5 new columns.
3. Extend `FrameFilter` with `modality: str | None = None` and thread it into `query_frames`.
4. Make `FrameStore.__init__` apply migrations 002 + 003 after `schema.sql` (so production databases actually have the new columns/tables, not just test DBs).
5. Add `AudioStore` class + `AudioSampleRow` dataclass with `insert()` / `query()` / `count()`.

Do NOT rename `FrameRecord` to `VisionFrameRow` — keep the dataclass name; downstream consumers get `VisionSample` via the adapter (Task A4), so the internal name is unobservable.

- [ ] **Step 1: Failing tests**

```python
# tests/test_store.py  (append)
from pet_data.storage.store import FrameStore, FrameRecord, FrameFilter

def test_framestore_insert_and_query_with_modality(tmp_path):
    store = FrameStore(tmp_path / "db.sqlite")
    store.insert_frame(FrameRecord(
        frame_id="f1", video_id="v1", source="youtube",
        frame_path="a.jpg", data_root="/data",
        timestamp_ms=1000, species="dog",
        lighting="bright", bowl_type="ceramic",
        quality_flag="normal", blur_score=120.0,
        modality="vision", storage_uri="local:///data/a.jpg",
        frame_width=1920, frame_height=1080, brightness_score=0.5,
    ))
    rows = store.query_frames(FrameFilter(modality="vision"))
    assert len(rows) == 1
    assert rows[0].modality == "vision"
    assert rows[0].storage_uri == "local:///data/a.jpg"
    store.close()

def test_framestore_production_db_has_phase2_columns(tmp_path):
    """FrameStore.__init__ must apply migrations 002+003 so production DBs match tests."""
    store = FrameStore(tmp_path / "db.sqlite")
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(frames)").fetchall()}
    assert {"modality", "storage_uri", "frame_width", "frame_height", "brightness_score"} <= cols
    tables = {r[0] for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "audio_samples" in tables
    store.close()
```

```python
# tests/test_store_audio.py
import sqlite3
from pet_data.storage.store import AudioStore, AudioSampleRow
from tests.conftest_migrations import load_migration

def _conn(tmp_path):
    c = sqlite3.connect(str(tmp_path/"db.sqlite"))
    load_migration(1).upgrade(c); load_migration(2).upgrade(c); load_migration(3).upgrade(c)
    c.row_factory = sqlite3.Row
    return c

def test_audio_store_insert_roundtrip(tmp_path):
    conn = _conn(tmp_path)
    store = AudioStore(conn)
    row = AudioSampleRow(
        sample_id="sha256:a", storage_uri="local:///audio/a.wav",
        captured_at="2026-04-21T12:00:00+00:00",
        source_type="community", source_id="esc50", source_license="CC-BY",
        pet_species="dog", duration_s=5.0, sample_rate=44100, num_channels=1,
        snr_db=22.5, clip_type="bark",
    )
    store.insert(row)
    got = store.query(clip_type="bark")
    assert len(got) == 1 and got[0].sample_id == "sha256:a"

def test_audio_store_count(tmp_path):
    conn = _conn(tmp_path)
    store = AudioStore(conn)
    assert store.count() == 0
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement additions to `store.py`**

**3a. Add migration driver to `FrameStore.__init__`:**

```python
# after self._conn.executescript(schema_path.read_text()) in __init__:
self._apply_subsequent_migrations()

def _apply_subsequent_migrations(self) -> None:
    """Apply numbered migrations after 001_init (which replays schema.sql).

    ALTER TABLE / CREATE TABLE statements use idempotent patterns where
    possible; anything else is wrapped in a try/except that tolerates
    OperationalError for duplicate-column-name (sqlite's only signal that
    a migration has already been applied).
    """
    import importlib.util
    from pathlib import Path

    mig_dir = Path(__file__).parent / "migrations"
    for path in sorted(mig_dir.glob("[0-9][0-9][0-9]_*.py")):
        # 001_init is handled by schema.sql — skip
        if path.name.startswith("001_"):
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        try:
            mod.upgrade(self._conn)
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                continue  # already applied
            raise
```

**3b. Extend `FrameRecord` dataclass:**

```python
@dataclass
class FrameRecord:
    frame_id: str
    video_id: str | None
    source: str
    frame_path: str
    data_root: str
    timestamp_ms: int | None = None
    # ... existing fields ...
    # NEW in Phase 2
    modality: str = "vision"
    storage_uri: str = ""
    frame_width: int | None = None
    frame_height: int | None = None
    brightness_score: float | None = None
```

Extend `FrameFilter` with `modality: str | None = None` and thread it into `query_frames`.

Extend `FrameStore._record_to_params()` to include the 5 new keys, and extend `FrameStore.insert_frame()` INSERT statement column list and VALUES clause. (Method is `insert_frame`, NOT `insert` — verified in Phase 1 contracts section above.)

Append `AudioStore` + `AudioSampleRow` at the bottom of `store.py`:

```python
@dataclass
class AudioSampleRow:
    sample_id: str
    storage_uri: str
    captured_at: str
    source_type: str
    source_id: str
    source_license: str | None = None
    pet_species: str | None = None
    duration_s: float = 0.0
    sample_rate: int = 0
    num_channels: int = 1
    snr_db: float | None = None
    clip_type: str | None = None


class AudioStore:
    """Thin wrapper over `audio_samples` table. Parallels FrameStore."""
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, row: AudioSampleRow) -> None:
        self.conn.execute(
            "INSERT INTO audio_samples (sample_id, storage_uri, captured_at, "
            "source_type, source_id, source_license, pet_species, duration_s, "
            "sample_rate, num_channels, snr_db, clip_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.sample_id, row.storage_uri, row.captured_at, row.source_type,
             row.source_id, row.source_license, row.pet_species, row.duration_s,
             row.sample_rate, row.num_channels, row.snr_db, row.clip_type),
        )
        self.conn.commit()

    def query(self, *, clip_type: str | None = None) -> list[AudioSampleRow]:
        sql = "SELECT * FROM audio_samples"
        params: list = []
        if clip_type is not None:
            sql += " WHERE clip_type = ?"
            params.append(clip_type)
        cur = self.conn.execute(sql, params)
        return [AudioSampleRow(**{k: r[k] for k in r.keys() if k in AudioSampleRow.__dataclass_fields__}) for r in cur.fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM audio_samples").fetchone()[0]
```

- [ ] **Step 4: Run → PASS**

```bash
pytest tests/test_store.py tests/test_store_audio.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/storage/store.py tests/test_store.py tests/test_store_audio.py
git commit -m "feat(pet-data): extend FrameStore with modality cols; add AudioStore"
```

---

### Task A6: `datasets/vision_frames.py` — `@DATASETS.register_module` plugin

**Files:**
- Create: `src/pet_data/datasets/__init__.py`, `src/pet_data/datasets/vision_frames.py`
- Test: `tests/test_datasets_vision.py`, `tests/conftest.py` (add fixture)

**ABC conformance** (Phase 1 contracts — see top of plan): `BaseDataset` has three `@abstractmethod`s — `build(self, dataset_config: dict)`, `to_hf_dataset(self, dataset_config: dict)`, `modality(self)`. Implement all three. `modality` is a **method** (returning a `Literal`), not a class attribute.

**Dataset config shape:** `dataset_config: dict` arrives via the Hydra-composed `DatasetConfig.args` (Phase 1 structured config). For vision frames we accept:

```yaml
dataset:
  type: pet_data.vision_frames
  modality: vision
  args:
    db_path: /data/pet-data/pet_data.db
    modality_filter: vision   # optional; defaults to "vision"
```

- [ ] **Step 1: Fixture — add `fresh_db_with_frames` to `tests/conftest.py`**

```python
# tests/conftest.py  (append)
import pytest
from pathlib import Path
from pet_data.storage.store import FrameStore, FrameRecord

@pytest.fixture
def fresh_db_with_frames(tmp_path) -> Path:
    """FrameStore DB with 3 VisionSample-compliant rows (all required fields populated)."""
    db_path = tmp_path / "db.sqlite"
    store = FrameStore(db_path)
    for i in range(3):
        store.insert_frame(FrameRecord(
            frame_id=f"sha256:f{i}", video_id=f"v{i}", source="youtube",
            frame_path=f"frames/{i}.jpg", data_root="/data",
            timestamp_ms=1000 * i, species="dog",
            lighting="bright", bowl_type="ceramic",
            quality_flag="normal", blur_score=120.0,
            modality="vision",
            storage_uri=f"local:///data/frames/{i}.jpg",
            frame_width=1920, frame_height=1080, brightness_score=0.6,
        ))
    store.close()
    return db_path
```

- [ ] **Step 2: Failing test**

```python
# tests/test_datasets_vision.py
from pet_infra.registry import DATASETS
import pet_data.datasets.vision_frames  # noqa: F401  (trigger registration)

def test_vision_frames_dataset_registered():
    cls = DATASETS.get("pet_data.vision_frames")
    assert cls is not None

def test_vision_frames_build_yields_vision_samples(fresh_db_with_frames):
    from pet_schema.samples import VisionSample
    cls = DATASETS.get("pet_data.vision_frames")
    ds = cls()
    samples = list(ds.build({"db_path": str(fresh_db_with_frames), "modality_filter": "vision"}))
    assert len(samples) == 3
    assert all(isinstance(s, VisionSample) for s in samples)

def test_vision_frames_modality_method(fresh_db_with_frames):
    cls = DATASETS.get("pet_data.vision_frames")
    ds = cls()
    assert ds.modality() == "vision"

def test_vision_frames_skips_rows_missing_required_fields(tmp_path):
    """VisionSample requires frame_width/height/brightness_score; rows with NULL must be skipped, not raise."""
    from pet_data.storage.store import FrameStore, FrameRecord
    store = FrameStore(tmp_path / "db.sqlite")
    store.insert_frame(FrameRecord(
        frame_id="incomplete", video_id="v", source="youtube",
        frame_path="x.jpg", data_root="/data",
        timestamp_ms=0, species="dog", lighting="bright",
        bowl_type=None, quality_flag="normal", blur_score=50.0,
        modality="vision", storage_uri="local:///data/x.jpg",
        frame_width=None, frame_height=None, brightness_score=None,  # incomplete
    ))
    store.close()
    cls = DATASETS.get("pet_data.vision_frames")
    ds = cls()
    assert list(ds.build({"db_path": str(tmp_path/"db.sqlite")})) == []
```

- [ ] **Step 3: Run → FAIL**

- [ ] **Step 4: Implement plugin**

```python
# src/pet_data/datasets/__init__.py
# (empty or re-exports for discovery ergonomics)

# src/pet_data/datasets/vision_frames.py
"""Dataset plugin exposing pet_data's vision frames as pet_schema.VisionSample iterator."""
from __future__ import annotations
import sqlite3
from collections.abc import Iterable
from typing import Literal, TYPE_CHECKING

from pet_infra.registry import DATASETS
from pet_infra.base.dataset import BaseDataset
from pet_schema import BaseSample
from pet_schema.samples import VisionSample

from pet_data.storage.store import FrameStore, FrameFilter
from pet_data.storage.adapter import frame_row_to_vision_sample

if TYPE_CHECKING:
    import datasets as hf_datasets


@DATASETS.register_module("pet_data.vision_frames", force=True)
class VisionFramesDataset(BaseDataset):
    """VisionSample iterator over the pet-data frames table.

    `dataset_config` keys (see Hydra dataset/vision_frames.yaml):
        db_path: str        — required, path to pet-data sqlite file
        modality_filter: str — optional, defaults to "vision"
    """

    def modality(self) -> Literal["vision", "audio", "sensor", "multimodal"]:
        return "vision"

    def build(self, dataset_config: dict) -> Iterable[BaseSample]:
        db_path = dataset_config["db_path"]
        mfilter = dataset_config.get("modality_filter", "vision")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # We bypass FrameStore to avoid re-running migrations on a connection
            # we opened ourselves — schema is assumed current.
            cur = conn.execute(
                "SELECT * FROM frames WHERE modality = ? "
                "AND frame_width IS NOT NULL "
                "AND frame_height IS NOT NULL "
                "AND brightness_score IS NOT NULL",
                (mfilter,),
            )
            for row in cur.fetchall():
                yield frame_row_to_vision_sample(dict(row))
        finally:
            conn.close()

    def to_hf_dataset(self, dataset_config: dict) -> "hf_datasets.Dataset":
        import datasets as hf_datasets
        records = [s.model_dump(mode="json") for s in self.build(dataset_config)]
        return hf_datasets.Dataset.from_list(records)
```

**`force=True`** on `@DATASETS.register_module` prevents `KeyError` if the module is re-imported (e.g. by `_register_all()` after a test already imported it). Matches Phase 1's guard pattern.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/datasets/ tests/test_datasets_vision.py tests/conftest.py
git commit -m "feat(pet-data): VisionFramesDataset plugin registered in DATASETS"
```

---

### Task A7: `datasets/audio_clips.py`

**Files:**
- Create: `src/pet_data/datasets/audio_clips.py`
- Test: `tests/test_datasets_audio.py`

Follow the exact ABC-conformant shape from Task A6 — three `@abstractmethod`s must all be implemented: `build(self, dataset_config: dict)`, `to_hf_dataset(self, dataset_config: dict)`, `modality(self)`. `modality` is a method returning `"audio"`, NOT a class attribute. `@DATASETS.register_module(..., force=True)`.

- [ ] **Step 1: Failing test**

```python
# tests/test_datasets_audio.py
import sqlite3, pytest
from pet_infra.registry import DATASETS
from pet_infra.base.dataset import BaseDataset
from pet_schema.samples import AudioSample

from tests.conftest_migrations import load_migration


@pytest.fixture
def fresh_db_with_audio(tmp_path):
    db = tmp_path / "db.sqlite"
    conn = sqlite3.connect(str(db))
    load_migration(1).upgrade(conn)
    load_migration(2).upgrade(conn)
    load_migration(3).upgrade(conn)
    # Insert via AudioStore so columns + NOT-NULL constraints are respected in one place.
    from pet_data.storage.store import AudioStore, AudioSampleRow
    store = AudioStore(conn)
    store.insert(AudioSampleRow(
        sample_id="a1", storage_uri="local:///tmp/a1.wav",
        captured_at="2026-04-21T12:00:00+00:00",
        source_type="community", source_id="esc50", source_license="CC-BY",
        pet_species="dog", duration_s=2.5, sample_rate=16000, num_channels=1,
        snr_db=20.0, clip_type="bark",
    ))
    conn.close()
    return db


def test_audio_clips_registered_and_ABC():
    from pet_data.datasets import audio_clips  # noqa: F401
    cls = DATASETS.get("pet_data.audio_clips")
    assert cls is not None
    inst = cls()
    assert isinstance(inst, BaseDataset)
    assert inst.modality() == "audio"


def test_audio_clips_build_yields_AudioSample(fresh_db_with_audio):
    from pet_data.datasets import audio_clips  # noqa: F401
    cls = DATASETS.get("pet_data.audio_clips")
    ds = cls()
    samples = list(ds.build({"db_path": str(fresh_db_with_audio)}))
    assert len(samples) == 1
    assert isinstance(samples[0], AudioSample)
    assert samples[0].modality == "audio"
    # pet_schema.AudioSample field is `duration_s` — verified in Phase 1 contracts
    assert samples[0].duration_s == 2.5
```

- [ ] **Step 2: Run → FAIL** — `pytest tests/test_datasets_audio.py -v` → module not found.

- [ ] **Step 3: Implement**

```python
# src/pet_data/datasets/audio_clips.py
"""AudioClipsDataset plugin — mirrors VisionFramesDataset for the audio modality."""
from __future__ import annotations
import sqlite3
from typing import Iterable, Literal

from pet_infra.base.dataset import BaseDataset
from pet_infra.registry import DATASETS
from pet_schema.samples import AudioSample

from pet_data.storage.store import AudioStore
from pet_data.storage.adapter import audio_row_to_audio_sample


@DATASETS.register_module(name="pet_data.audio_clips", force=True)
class AudioClipsDataset(BaseDataset):
    """Iterate the pet-data `audio_samples` table and yield `pet_schema.AudioSample`."""

    def modality(self) -> Literal["audio"]:
        return "audio"

    def build(self, dataset_config: dict) -> Iterable[AudioSample]:
        from dataclasses import asdict
        db_path = dataset_config["db_path"]
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            store = AudioStore(conn)
            # AudioStore.query() returns AudioSampleRow dataclasses; the adapter
            # expects a Mapping, so convert with dataclasses.asdict. (Don't change
            # AudioStore.query() — test_audio_store_insert_roundtrip depends on
            # the dataclass return shape.)
            for row in store.query():
                yield audio_row_to_audio_sample(asdict(row))
        finally:
            conn.close()

    def to_hf_dataset(self, dataset_config: dict):
        import datasets as hfds
        rows = list(self.build(dataset_config))
        return hfds.Dataset.from_list([r.model_dump() for r in rows])
```

- [ ] **Step 4: Run → PASS** — `pytest tests/test_datasets_audio.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/datasets/audio_clips.py tests/test_datasets_audio.py
git commit -m "feat(pet-data): AudioClipsDataset plugin registered in DATASETS"
```

---

### Task A8: `_register.py` + entry-point wiring

**Files:**
- Create: `src/pet_data/_register.py`
- Modify: `pyproject.toml` (entry-point target uses `register_all` — matching Phase 1 pet-infra contract, see top-of-plan contracts section)
- Test: `tests/test_plugin_registration.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_plugin_registration.py
import importlib.metadata as md
from pet_infra.registry import DATASETS

def test_pet_data_entry_point_discoverable():
    eps = md.entry_points(group="pet_infra.plugins")
    names = {ep.name for ep in eps}
    assert "pet_data" in names

def test_register_all_registers_both_datasets():
    # Simulate pet-infra discovery invoking register_all()
    DATASETS.module_dict.pop("pet_data.vision_frames", None)
    DATASETS.module_dict.pop("pet_data.audio_clips", None)
    from pet_data import _register
    _register.register_all()
    assert DATASETS.get("pet_data.vision_frames") is not None
    assert DATASETS.get("pet_data.audio_clips") is not None
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_data/_register.py
"""Entry-point target for pet-infra's plugin discovery.

pet-infra scans [project.entry-points."pet_infra.plugins"] and calls
the registered callable (named `register_all`, matching pet-infra's own
convention) at CLI startup to trigger @DATASETS.register_module side-effects.
"""
from __future__ import annotations


def register_all() -> None:
    # Imports trigger @DATASETS.register_module decorators.
    from pet_data.datasets import vision_frames  # noqa: F401
    from pet_data.datasets import audio_clips    # noqa: F401
```

Confirm Task A1 pinned the pyproject entry in the correct form:

```toml
[project.entry-points."pet_infra.plugins"]
pet_data = "pet_data._register:register_all"
```

- [ ] **Step 4: Reinstall + run → PASS**

```bash
pip install -e . --force-reinstall --no-deps
pytest tests/test_plugin_registration.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/_register.py tests/test_plugin_registration.py
git commit -m "feat(pet-data): _register entry-point wires VisionFrames+AudioClips plugins"
```

---

### Task A9: Hydra config group

**Files:**
- Create: `src/pet_data/configs/_global_/defaults.yaml`, `src/pet_data/configs/dataset/vision_frames.yaml`, `src/pet_data/configs/dataset/audio_clips.yaml`, `src/pet_data/configs/experiment/pet_data_ingest.yaml`

Use pet-schema's `DatasetConfig` structured config as the base (Phase 1 registered it under group `dataset`, name `base`). Each concrete yaml sets `type:`, `args:`, `modality:`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli_hydra.py
from hydra import compose, initialize_config_dir
from pathlib import Path

CFG_DIR = str((Path(__file__).parent.parent / "src" / "pet_data" / "configs").resolve())

def test_compose_dataset_vision_frames():
    with initialize_config_dir(CFG_DIR, version_base="1.3"):
        cfg = compose(config_name="experiment/pet_data_ingest",
                      overrides=["dataset=vision_frames"])
    assert cfg.dataset.type == "pet_data.vision_frames"
    assert cfg.dataset.modality == "vision"

def test_compose_override_audio():
    with initialize_config_dir(CFG_DIR, version_base="1.3"):
        cfg = compose(config_name="experiment/pet_data_ingest",
                      overrides=["dataset=audio_clips"])
    assert cfg.dataset.type == "pet_data.audio_clips"
    assert cfg.dataset.modality == "audio"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Create yamls**

```yaml
# src/pet_data/configs/_global_/defaults.yaml
hydra:
  run:
    dir: outputs/${now:%Y-%m-%d}/${now:%H-%M-%S}
```

```yaml
# src/pet_data/configs/dataset/vision_frames.yaml
type: pet_data.vision_frames
modality: vision
args:
  db_path: ${oc.env:PET_DATA_DB,/data/pet-data/pet_data.db}
```

```yaml
# src/pet_data/configs/dataset/audio_clips.yaml
type: pet_data.audio_clips
modality: audio
args:
  db_path: ${oc.env:PET_DATA_DB,/data/pet-data/pet_data.db}
```

```yaml
# src/pet_data/configs/experiment/pet_data_ingest.yaml
defaults:
  - /_global_/defaults
  - /dataset: vision_frames
  - _self_

recipe:
  recipe_id: pet_data_ingest
  description: "pet-data smoke recipe — just loads the dataset plugin"
  scope: single_repo
  owner_repo: pet-data
  schema_version: "2.0.0"
  stages:
    - name: load
      component_registry: evaluators  # no-op eval stage — dataset loaded via inputs
      component_type: pet_infra.noop_evaluator
      inputs:
        dataset: {ref_type: dataset, ref_value: ${dataset.type}}
      config_path: experiment/pet_data_ingest
      depends_on: []
  variations: []
  produces: []
  default_storage: local
  required_plugins:
    - pet_data
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/configs/ tests/test_cli_hydra.py
git commit -m "feat(pet-data): add Hydra config group (dataset + experiment/pet_data_ingest)"
```

---

### Task A10: CLI Hydra-ify

**Files:**
- Modify: `src/pet_data/cli.py`

Replace argparse with Click + Hydra. Keep all 6 existing subcommands for back-compat (`ingest`, `dedup`, `quality`, `augment`, `train-ae`, `score-anomaly`). Add a new `pet-data run` command that takes Hydra overrides.

**Strategy:** the pet-infra spec's authoritative CLI is `pet run recipe=...` (from pet-infra, not per-repo). pet-data's CLI stays as legacy direct invocation for DVC `cmd:` lines, but internally now loads Hydra config for `--config-name` dispatch. Don't rewrite all 6 subcommands in this task — only migrate the top-level entry + add `run`.

- [ ] **Step 1: Failing test**

```python
# tests/test_cli_hydra.py (append)
from click.testing import CliRunner
from pet_data.cli import cli

def test_cli_run_smokes_without_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_DATA_DB", str(tmp_path/"db.sqlite"))
    # init db — load migrations via the importlib helper (digit-prefixed filenames
    # like 001_init.py are not regular importable modules). See tests/conftest_migrations.py.
    import sqlite3
    from tests.conftest_migrations import load_migration
    conn = sqlite3.connect(str(tmp_path/"db.sqlite"))
    load_migration(1).upgrade(conn)
    load_migration(2).upgrade(conn)
    load_migration(3).upgrade(conn)
    conn.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--config-name=experiment/pet_data_ingest", "--dry-run"])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Rewrite `cli.py`**

```python
# src/pet_data/cli.py
"""pet-data CLI.

Legacy subcommands (ingest/dedup/quality/augment/train-ae/score-anomaly) are
retained for DVC compatibility; new `run` command dispatches via Hydra +
pet-infra's Recipe resolver.
"""
from __future__ import annotations
import os
from pathlib import Path

import click
from hydra import compose, initialize_config_dir


CFG_DIR = str((Path(__file__).parent / "configs").resolve())


@click.group()
def cli() -> None:
    """pet-data CLI."""


# --- legacy commands (unchanged behaviour, keep for DVC) ---

@cli.command()
@click.option("--source", required=True)
@click.option("--params", "params_path", default=None)
def ingest(source: str, params_path: str | None) -> None:
    from pet_data.cli_legacy import run_ingest
    run_ingest(source=source, params_path=params_path)


@cli.command()
@click.option("--params", "params_path", default=None)
def dedup(params_path: str | None) -> None:
    from pet_data.cli_legacy import run_dedup
    run_dedup(params_path=params_path)


# ... (repeat for quality / augment / train-ae / score-anomaly, each delegating
#      to a same-named function in cli_legacy.py — see Step 3b) ...


# --- new Hydra-backed command ---

@cli.command()
@click.option("--config-name", required=True, help="Hydra config name, e.g. experiment/pet_data_ingest")
@click.option("--dry-run/--no-dry-run", default=True, help="Compose + validate, do not execute")
@click.argument("overrides", nargs=-1)
def run(config_name: str, dry_run: bool, overrides: tuple[str, ...]) -> None:
    """Hydra-composed run. Dry-run only composes; real execution goes via `pet run`."""
    with initialize_config_dir(CFG_DIR, version_base="1.3"):
        cfg = compose(config_name=config_name, overrides=list(overrides))
    click.echo(f"Composed: {cfg.recipe.recipe_id}")
    if dry_run:
        return
    raise click.UsageError(
        "Non-dry-run execution is owned by pet-infra's `pet run`. "
        "Use: pet run recipe=<recipe-name>"
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
```

**Step 3b:** move the bodies of the current 6 argparse handlers in `cli.py` into a new `src/pet_data/cli_legacy.py` (functions `run_ingest(source, params_path)`, etc.), so the click wrapper delegates. Keep function bodies byte-identical — this is a pure move + wrap.

- [ ] **Step 4: Run → PASS**

```bash
pytest tests/test_cli_hydra.py -v
pet-data ingest --help  # sanity
```

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/cli.py src/pet_data/cli_legacy.py tests/test_cli_hydra.py
git commit -m "feat(pet-data): Hydra-backed `pet-data run`; legacy subcommands retained"
```

---

### Task A11: `sources/base.py` tag emissions with modality

**Files:**
- Modify: `src/pet_data/sources/base.py`

All existing 7 source classes emit `FrameRecord`. Add `modality="vision"` default in the emission path, and compute `storage_uri = "local://" + data_root + "/" + frame_path` at the point of `FrameStore.insert_frame()`. Also populate VisionSample-required fields (`frame_width`, `frame_height`, `brightness_score`) — since sources already decode frames to read them, thread the values through without extra IO. Rows where those cannot be computed (e.g. partial ingest) stay NULL and are skipped by `VisionFramesDataset.build()` per Phase 1 contracts section.

- [ ] **Step 1: Failing test**

```python
# tests/test_sources_base.py  (extend existing)
def test_base_source_emits_modality_and_storage_uri(tmp_path, fake_source):
    # fake_source is an existing fixture from test_base.py
    ...
    fake_source.run()
    with fake_source.store.conn as c:
        row = c.execute("SELECT modality, storage_uri FROM frames LIMIT 1").fetchone()
    assert row["modality"] == "vision"
    assert row["storage_uri"].startswith("local://")
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Edit `sources/base.py`**

Locate the single place where `FrameStore.insert_frame(FrameRecord(...))` is called (method name is `insert_frame`, verified in Phase 1 contracts section). Pass `modality="vision"`, `storage_uri=f"local://{data_root}/{frame_path}"`, and the `frame_width` / `frame_height` / `brightness_score` values computed during decoding.

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add src/pet_data/sources/base.py tests/test_sources_base.py
git commit -m "feat(pet-data): sources tag FrameRecord with modality + storage_uri"
```

---

### Task A12: `params.yaml` — add `sample` top-level key

**Files:**
- Modify: `params.yaml`

- [ ] **Step 1: Failing test**

```python
# tests/test_config.py
import yaml
from pathlib import Path

def test_params_has_sample_defaults():
    params = yaml.safe_load((Path(__file__).parent.parent / "params.yaml").read_text())
    assert params["sample"]["default_modality"] == "vision"
    assert params["sample"]["storage_scheme"] == "local"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Add to `params.yaml`**

```yaml
sample:
  default_modality: vision
  storage_scheme: local
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add params.yaml tests/test_config.py
git commit -m "feat(pet-data): params.yaml adds sample.default_modality + storage_scheme"
```

---

### Task A13: CI lint + type-check pass

**Files:**
- (potentially) `pyproject.toml` mypy section

- [ ] **Step 1**: `ruff check src tests --fix` — fix violations

- [ ] **Step 2**: `ruff format src tests`

- [ ] **Step 3**: `mypy src` — add type hints where mypy complains; add `# type: ignore[...]` only with a trailing comment explaining why

- [ ] **Step 4**: `pytest -q` — full suite green

- [ ] **Step 5**: Commit lint-only changes

```bash
git add -u
git commit -m "chore(pet-data): ruff + mypy clean for Phase 2 additions"
```

---

### Task A14: Open PR `feature/phase-2-modality-refactor` → `dev`

- [ ] **Step 1: Push branch**

```bash
git push -u origin feature/phase-2-modality-refactor
```

- [ ] **Step 2: Create PR via gh**

```bash
gh pr create --base dev --title "feat(pet-data): Phase 2 modality + dataset plugins" --body "$(cat <<'EOF'
## Summary
- Migrations 002 (modality + storage_uri on frames) and 003 (new audio_samples table)
- VisionFramesDataset + AudioClipsDataset registered via pet-infra DATASETS registry
- CLI: argparse → click + Hydra; `pet-data run --config-name ...`; legacy subcommands retained
- Pinned pet-schema v2.0.0 + pet-infra v2.0.0

## Test plan
- [ ] migration upgrade/downgrade round-trip
- [ ] VisionSample / AudioSample adapter round-trip
- [ ] DATASETS.get returns plugin class after `import pet_data._register; _register.register_all()`
- [ ] `pet-data run --config-name=experiment/pet_data_ingest --dry-run` exits 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3:** Wait for CI green + 1 reviewer approve → merge → Part A done.

- [ ] **Step 4:** After `dev` merge, follow-up PR `dev → main` with tag `v1.1.0`.

```bash
git fetch origin
git checkout main && git pull
git checkout dev && git pull
gh pr create --base main --head dev --title "release(pet-data): v1.1.0 — Phase 2 modality refactor" --body "Phase 2 deliverables per plan 2026-04-20-phase-2-data-annotation-plan.md"
# after merge:
git checkout main && git pull
git tag v1.1.0 && git push origin v1.1.0
```

---

## Part B — pet-annotation refactor

Work in `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-annotation/` on branch `feature/phase-2-modality-refactor` off `dev`.

Part B structure parallels Part A. Each task below is written tersely since the pattern is established; follow the same 5-step TDD rhythm. If any task exceeds 180 LOC of new code, split it.

### Task B0: Branch setup

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-annotation
git fetch origin
git checkout dev && git pull origin dev
git checkout -b feature/phase-2-modality-refactor
pip install -e ".[dev]"
pytest tests/ -q   # baseline green
```

---

### Task B1: Pin deps + bump version

**Files:** `pyproject.toml`, `src/pet_annotation/__init__.py`

- [ ] **Step 1: Failing test** — `tests/test_version.py` asserts `pet_annotation.__version__ == "1.1.0"` + pet-schema 2.0.0 + pet-infra 2.0.0.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Update `pyproject.toml`** — pin both to `@v2.0.0`, bump to `1.1.0`, add `hydra-core>=1.3,<1.4`, `mmengine-lite>=0.10,<0.12`. Add:
  ```toml
  [project.entry-points."pet_infra.plugins"]
  pet_annotation = "pet_annotation._register:register_all"
  ```
- [ ] **Step 4: Reinstall + run → PASS**
- [ ] **Step 5: Commit** — `chore(pet-annotation): pin pet-schema+pet-infra v2.0.0; bump to 1.1.0`

---

### Task B2: Migration `002_add_modality.sql` + extend `_apply_migration`

**Files:**
- Create: `migrations/002_add_modality.sql`
- Modify: `src/pet_annotation/store.py` — `_apply_migration` currently reads a single file (see top-of-plan contracts). Extend it to glob `migrations/*.sql` sorted by filename, and tolerate duplicate-apply on `ALTER TABLE ADD COLUMN` via `try/except sqlite3.OperationalError` around each statement when the error message contains `"duplicate column name"`.
- Test: `tests/test_migrations.py` (create if missing) + extend `tests/test_store.py`

**Schema:**

```sql
ALTER TABLE annotations        ADD COLUMN modality TEXT NOT NULL DEFAULT 'vision';
ALTER TABLE annotations        ADD COLUMN storage_uri TEXT;
ALTER TABLE model_comparisons  ADD COLUMN modality TEXT NOT NULL DEFAULT 'vision';
CREATE INDEX IF NOT EXISTS idx_annotations_modality ON annotations(modality);
```

**`_apply_migration` sketch:**

```python
# src/pet_annotation/store.py
def _apply_migration(self) -> None:
    mig_dir = Path(__file__).parent.parent.parent / "migrations"
    for sql_file in sorted(mig_dir.glob("*.sql")):
        sql = sql_file.read_text()
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                self._conn.execute(stmt)
            except sqlite3.OperationalError as e:
                # idempotent: tolerate already-applied ALTER TABLE ADD COLUMN
                if "duplicate column name" in str(e).lower():
                    continue
                raise
    self._conn.commit()
```

- [ ] **Step 1**: Write failing test asserting both migrations apply cleanly against a fresh DB and again against an already-migrated DB (idempotent).
- [ ] **Step 2**: Run → FAIL.
- [ ] **Step 3**: Create `002_add_modality.sql` + rewrite `_apply_migration` as above.
- [ ] **Step 4**: Run → PASS.
- [ ] **Step 5: Commit**: `feat(pet-annotation): migration 002 adds modality; _apply_migration globs all migrations idempotently`

---

### Task B3: Migration `003_create_audio_annotations.sql`

**Files:** `migrations/003_create_audio_annotations.sql`, `tests/test_store_audio.py` (create)

**Schema** (maps to `pet_schema.AudioAnnotation`):

```sql
CREATE TABLE audio_annotations (
    annotation_id  TEXT PRIMARY KEY,
    sample_id      TEXT NOT NULL,
    annotator_type TEXT NOT NULL CHECK (annotator_type IN ('vlm','cnn','human','rule')),
    annotator_id   TEXT NOT NULL,
    modality       TEXT NOT NULL DEFAULT 'audio' CHECK (modality = 'audio'),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_version TEXT NOT NULL DEFAULT '2.0.0',
    predicted_class TEXT NOT NULL,
    class_probs    TEXT NOT NULL,    -- JSON {class: prob}
    logits         TEXT              -- JSON list[float] | null
);
CREATE INDEX idx_audio_ann_sample ON audio_annotations(sample_id);
CREATE INDEX idx_audio_ann_class  ON audio_annotations(predicted_class);
```

- [ ] **Step 1-5** TDD; verify round-trip via JSON serialization of `class_probs` / `logits`.
- [ ] **Commit**: `feat(pet-annotation): migration 003 creates audio_annotations table`

---

### Task B4: Row split + adapter

**Files:**
- Modify: `src/pet_annotation/store.py` — rename `AnnotationRecord` → `VisionAnnotationRow`; add `AudioAnnotationRow`; add `modality` to dataclass defaults; extend `AnnotationStore.insert_annotation` / `insert_comparison` / fetch paths to route by modality (method name is `insert_annotation`, verified at top-of-plan contracts)
- Create: `src/pet_annotation/adapter.py` — `vision_row_to_annotation()`, `audio_row_to_annotation()` (analogous to pet-data Task A4)
- Test: `tests/test_store.py` (rename assertions), `tests/test_adapter.py` (create)

**Back-compat note:** retain a `AnnotationRecord = VisionAnnotationRow` alias at end of `store.py` so existing callers (orchestrator.py, export/*) do not break in this task. Follow-up tasks remove the alias once call sites are updated.

**Routing:** `insert_annotation(rec)` inspects `rec.modality`. For `"vision"` → INSERT INTO `annotations` (existing path + new `modality`/`storage_uri` columns). For `"audio"` → INSERT INTO `audio_annotations` (new table from migration 003). No separate `insert_audio_annotation` — single polymorphic entry point.

- [ ] **Step 1-5** TDD; verify:
  - vision rows land in `annotations` with `modality='vision'`
  - audio rows land in `audio_annotations`
  - adapter functions round-trip each row type to the corresponding pet_schema type (`VisionAnnotation` / `AudioAnnotation`) and back
- [ ] **Commit**: `feat(pet-annotation): split AnnotationRecord into Vision/Audio rows + modality-aware insert_annotation`

---

### Task B5: Extract LS templates to files

**Files:**
- Create: `src/pet_annotation/human_review/templates/vision.xml`, `.../audio.xml`, `.../__init__.py`, `src/pet_annotation/human_review/templates.py`
- Modify: `src/pet_annotation/human_review/import_to_ls.py` (remove hardcoded XML)
- Test: `tests/test_templates.py` (create)

**`vision.xml`:** identical content to the current hardcoded XML block in `import_to_ls.py:19-39`.

**`audio.xml`** (new):

```xml
<View>
  <Audio name="audio" value="$audio_uri"/>
  <Header value="Predicted: $predicted_class"/>
  <Choices name="correction" toName="audio" choice="single">
    <Choice value="bark"/>
    <Choice value="meow"/>
    <Choice value="purr"/>
    <Choice value="silence"/>
    <Choice value="ambient"/>
  </Choices>
  <TextArea name="notes" toName="audio" placeholder="optional reviewer notes"/>
</View>
```

**`templates.py`:**

```python
from pathlib import Path
from pet_schema.enums import Modality

_TEMPLATE_DIR = Path(__file__).parent / "templates"

def template_for(modality: Modality) -> str:
    path = _TEMPLATE_DIR / f"{modality}.xml"
    if not path.exists():
        raise ValueError(f"No LS template for modality={modality!r}")
    return path.read_text()
```

- [ ] **Step 1-5** TDD: test that `template_for("vision")` returns a string containing `<Image name=`, and `template_for("audio")` returns one containing `<Audio name=`.
- [ ] **Commit**: `feat(pet-annotation): extract LS templates to files; add audio template`

---

### Task B6: `import_to_ls.py` dispatches by modality

**Files:**
- Modify: `src/pet_annotation/human_review/import_to_ls.py`
- Test: `tests/test_import_to_ls.py` (modify or create) — mock LS client; assert `template_for(modality)` is consulted

- [ ] **Step 1-5** TDD:
  - `import_needs_review(modality="vision")` → uses `vision.xml`
  - `import_needs_review(modality="audio")` → uses `audio.xml`
  - Default modality when omitted: `"vision"` (back-compat)
- [ ] **Commit**: `feat(pet-annotation): LS import dispatches template by modality`

---

### Task B7: `datasets/vision_annotations.py` plugin

**Files:**
- Create: `src/pet_annotation/datasets/__init__.py`, `src/pet_annotation/datasets/vision_annotations.py`
- Test: `tests/test_datasets_plugins.py`

Mirror pet-data A6 **exactly on ABC conformance** (see top-of-plan contracts: `BaseDataset` has three `@abstractmethod`s — `build(self, dataset_config: dict)`, `to_hf_dataset(self, dataset_config: dict)`, `modality(self)`; `modality` is a method, NOT a class attribute). Emit `pet_schema.VisionAnnotation` from the `annotations` table (filter `modality='vision'`). `@DATASETS.register_module(name="pet_annotation.vision_annotations", force=True)`.

- [ ] **Step 1: Failing test** — assert `isinstance(ds, BaseDataset)`, `ds.modality() == "vision"`, `next(iter(ds.build({"db_path": ...})))` returns a `VisionAnnotation`.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** with all 3 methods (no class attribute shortcut).
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**: `feat(pet-annotation): VisionAnnotationsDataset plugin`

---

### Task B8: `datasets/audio_annotations.py` plugin

Mirror B7 structure against `audio_annotations` table. Key: `"pet_annotation.audio_annotations"`. Same ABC guardrails: implement all 3 methods, `modality()` returns `"audio"`, `force=True`.

- [ ] **Steps 1-5** TDD.
- [ ] **Commit**: `feat(pet-annotation): AudioAnnotationsDataset plugin`

---

### Task B9: `_register.py` + entry-point

**Files:**
- Create: `src/pet_annotation/_register.py`
- Modify: `pyproject.toml` — `pet_annotation = "pet_annotation._register:register_all"` (Phase 1 contract: function name is `register_all`, not `register`)
- Test: `tests/test_plugin_registration.py`

Same pattern as pet-data A8. Function is `register_all()`, imports both `datasets.vision_annotations` and `datasets.audio_annotations`. Use public `DATASETS.module_dict` (not `_module_dict`) in any test assertions.

- [ ] **Steps 1-5** TDD; `register_all()` triggers both dataset imports.
- [ ] **Commit**: `feat(pet-annotation): _register entry-point wires both dataset plugins`

---

### Task B10: Hydra configs

**Files:**
- Create: `src/pet_annotation/configs/_global_/defaults.yaml`, `configs/dataset/{vision,audio}_annotations.yaml`, `configs/experiment/pet_annotation_vision.yaml`

- [ ] **Steps 1-5** TDD: compose config, assert overrides.
- [ ] **Commit**: `feat(pet-annotation): Hydra config group`

---

### Task B11: CLI modality dispatch

**Files:** `src/pet_annotation/cli.py`

Add `--modality {vision|audio}` to `annotate`, `check`, `export`, `ls-import`, `ls-export`. Default = `vision`. Route to modality-specific store/query paths.

For `export --format audio`, wire up `to_audio_labels.py` (Task B12 provides the impl).

- [ ] **Steps 1-5** TDD: invoke `cli.main(["export", "--format=audio", "--modality=audio", ...])`, assert JSONL written.
- [ ] **Commit**: `feat(pet-annotation): CLI accepts --modality; dispatches to modality-aware store paths`

---

### Task B12: Implement `export/to_audio_labels.py`

**Files:** `src/pet_annotation/export/to_audio_labels.py`, `tests/test_export_audio.py`

Replace `NotImplementedError` with a real writer: for each `AudioAnnotationRow` (approved), emit a JSONL line:

```json
{"sample_id":"...","storage_uri":"local://...","label":"bark","class_probs":{"bark":0.9,"meow":0.1},"annotator_id":"audio_cnn_v1"}
```

- [ ] **Steps 1-5** TDD.
- [ ] **Commit**: `feat(pet-annotation): implement to_audio_labels JSONL export`

---

### Task B13: DPO modality filter

**Files:** `src/pet_annotation/dpo/generate_pairs.py`

Add `modality: Modality = "vision"` kwarg to `generate_cross_model_pairs`. Filter comparisons + annotations by modality. Audio DPO remains out-of-scope Phase 2 — default `modality="vision"` preserves current behaviour.

- [ ] **Steps 1-5** TDD.
- [ ] **Commit**: `feat(pet-annotation): DPO pair generation filters by modality`

---

### Task B14: params.yaml + CI lint + mypy

- [ ] Add `annotation.modality_default: vision` to `params.yaml`
- [ ] `ruff check src tests --fix && ruff format src tests`
- [ ] `mypy src`
- [ ] `pytest -q` green
- [ ] **Commit**: `chore(pet-annotation): params.yaml + ruff/mypy clean`

---

### Task B15: PR + release

Mirror Part A Task A14. PR `feature/phase-2-modality-refactor` → `dev`, then `dev → main`, tag `v1.1.0`.

---

## Part C — pet-infra smoke recipe + matrix bump

**Pre-condition:** Parts A and B merged to their respective `main` branches; tags `pet-data@v1.1.0` and `pet-annotation@v1.1.0` pushed.

Work in `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/` on branch `feature/phase-2-smoke-recipe` off `dev`.

### Task C0: Branch setup

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git fetch origin && git checkout dev && git pull
git checkout -b feature/phase-2-smoke-recipe
pip install -e ".[dev]"
pytest tests/ -q   # baseline green
```

---

### Task C1: Smoke-verify Phase 1 contracts are still correct

**Files:** read-only check

Phase 1 contracts are already documented at the top of this plan (see "Phase 1 v2.0.0 contracts"). The top-of-plan section is the source of truth the subagents used to design Parts A and B. This task is a defensive re-verification that the installed-from-main versions still match; any drift must halt Part C and cycle back.

- [ ] **Step 1**: In a scratch venv, `pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.0.0'` (already installed on CI).
- [ ] **Step 2**: Run these one-liners and compare against the contracts section verbatim:
  ```bash
  python -c "from pet_infra.base.dataset import BaseDataset; import inspect; print([m for m in ('build','to_hf_dataset','modality') if m in BaseDataset.__abstractmethods__])"
  # expect: ['build', 'to_hf_dataset', 'modality']
  python -c "from pet_infra.plugins.discover import discover_plugins; print(callable(discover_plugins))"
  # expect: True
  python -c "from pet_infra.registry import DATASETS; print(hasattr(DATASETS,'module_dict'))"
  # expect: True
  python -c "from pet_infra import cli; print('--recipe' in cli.validate.params[0].opts if hasattr(cli,'validate') else 'n/a')"
  # expect: True, or verify via `pet validate --help` manually
  ```
- [ ] **Step 3**: If any check fails, STOP Part C. File an issue and surface to the user: either the plan is stale or pet-infra v2.0.0 drifted. Do NOT "patch around" by mutating Parts A/B tasks without halting.
- [ ] **Exit criterion:** all checks PASS → proceed to C1.5.
- [ ] **No commit** (read-only audit).

---

### Task C1.5: Create `pet_infra.noop_evaluator` plugin (pet-infra patch `v2.0.1`)

**Why:** The smoke recipe in C2 uses `component_type: pet_infra.noop_evaluator` because `preflight.py` validates `component_type` against the EVALUATORS registry — Phase 1 shipped the registry but no concrete evaluator. A 10-line no-op plugin unblocks the smoke recipe without leaking Phase 3 training concerns.

**Files:**
- Create: `src/pet_infra/evaluators/__init__.py` (empty)
- Create: `src/pet_infra/evaluators/noop.py`
- Modify: `src/pet_infra/_register.py` — add `from pet_infra.evaluators import noop  # noqa: F401` inside `register_all()`
- Test: `tests/test_noop_evaluator.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_noop_evaluator.py
from pet_infra.registry import EVALUATORS
from pet_infra import _register

def test_noop_evaluator_registered():
    _register.register_all()
    cls = EVALUATORS.get("pet_infra.noop_evaluator")
    assert cls is not None
    inst = cls()
    # evaluate must return a mapping compatible with EvaluationReport
    out = inst.evaluate(model=None, dataset=[])
    assert isinstance(out, dict)
    assert out.get("report_type") == "noop"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# src/pet_infra/evaluators/noop.py
"""No-op evaluator — used by Phase 2 smoke recipe to exercise preflight/DAG
without running real evaluation logic. Phase 3 replaces with real evaluators.
"""
from __future__ import annotations
from pet_infra.registry import EVALUATORS


@EVALUATORS.register_module(name="pet_infra.noop_evaluator", force=True)
class NoopEvaluator:
    """Returns an empty report; ignores model and dataset."""

    def evaluate(self, model, dataset) -> dict:
        return {"report_type": "noop", "metrics": {}}
```

Append to `src/pet_infra/_register.py`'s `register_all()`:

```python
from pet_infra.evaluators import noop  # noqa: F401  (triggers @EVALUATORS.register_module)
```

- [ ] **Step 4: Run → PASS** — `pytest tests/test_noop_evaluator.py -v`.

- [ ] **Step 5: Commit + patch-tag**

```bash
git add src/pet_infra/evaluators/ src/pet_infra/_register.py tests/test_noop_evaluator.py
git commit -m "feat(pet-infra): add pet_infra.noop_evaluator for Phase 2 smoke recipe"
```

Part C wraps with a single tag bump — this commit lands on the `feature/phase-2-smoke-recipe` branch alongside C2-C6 and is released together in C7 as `v2.1.0`. No standalone `v2.0.1` tag needed.

---

### Task C2: Smoke recipe yaml

**Files:** `recipes/pet_data_ingest_smoke.yaml`

```yaml
recipe:
  recipe_id: pet_data_ingest_smoke
  description: "Phase 2 smoke — load vision frames via plugin; no-op eval stage"
  scope: cross_repo
  schema_version: "2.0.0"
  required_plugins:
    - pet_data
    - pet_annotation
  stages:
    - name: load_vision
      component_registry: evaluators
      component_type: pet_infra.noop_evaluator
      inputs:
        dataset: {ref_type: dataset, ref_value: pet_data.vision_frames}
      config_path: evaluator/noop
      depends_on: []
  variations: []
  produces: []
  default_storage: local
```

**Pre-condition:** Task C1.5 must have created and registered `pet_infra.noop_evaluator`; otherwise preflight fails (`preflight.py` checks `component_type in EVALUATORS.module_dict`). See Phase 1 contracts section — preflight does NOT validate dataset refs, so `pet_data.vision_frames` availability is proved instead by C3's integration test.

- [ ] **Step 1**: Create the yaml above.
- [ ] **Step 2**: Run `pet validate --recipe recipes/pet_data_ingest_smoke.yaml` — expect exit 0 with stdout listing compose/DAG/card_id OK. (Phase 1 contract: `--recipe` is a required option, NOT positional.)
- [ ] **Step 3**: Commit: `feat(pet-infra): Phase 2 smoke recipe pet_data_ingest_smoke.yaml`

---

### Task C3: Integration test

**Files:** `tests/integration/test_phase2_smoke.py`

- [ ] **Step 1: Failing test**

```python
# tests/integration/test_phase2_smoke.py
"""Integration: install pet-data @ v1.1.0 + pet-annotation @ v1.1.0 into the test
venv, then verify `pet validate --recipe recipes/pet_data_ingest_smoke.yaml` succeeds and
DATASETS has 4 Phase 2 keys."""
import subprocess
import pytest

def test_phase2_smoke_preflight():
    # Assumes CI has already pip-installed the two repos at v1.1.0.
    from pet_infra.registry import DATASETS
    from pet_infra import cli as pet_cli

    expected = {
        "pet_data.vision_frames",
        "pet_data.audio_clips",
        "pet_annotation.vision_annotations",
        "pet_annotation.audio_annotations",
    }
    # Trigger entry_points discovery — Phase 1 contract: function is `discover_plugins`
    from pet_infra.plugins.discover import discover_plugins
    discovered = discover_plugins()
    assert "datasets" in discovered
    assert expected <= set(DATASETS.module_dict.keys())

    result = subprocess.run(
        ["pet", "validate", "--recipe", "recipes/pet_data_ingest_smoke.yaml"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2**: Run → FAIL until entry-points flow is verified.
- [ ] **Step 3**: Install both repos locally from `main` tags:
  ```bash
  pip install 'pet-data @ git+https://github.com/Train-Pet-Pipeline/pet-data@v1.1.0'
  pip install 'pet-annotation @ git+https://github.com/Train-Pet-Pipeline/pet-annotation@v1.1.0'
  ```
- [ ] **Step 4**: Run → PASS.
- [ ] **Step 5**: Commit: `test(pet-infra): Phase 2 integration smoke (4 plugins + recipe preflight)`

---

### Task C4: CI `plugin-discovery.yml` matrix

**Files:** `.github/workflows/plugin-discovery.yml`

Extend the install step to include both new repos:

```yaml
      - name: Install downstream plugin packages
        run: |
          pip install 'pet-data @ git+https://github.com/Train-Pet-Pipeline/pet-data@v1.1.0'
          pip install 'pet-annotation @ git+https://github.com/Train-Pet-Pipeline/pet-annotation@v1.1.0'

      - name: Assert Phase 2 plugins registered
        run: |
          # Phase 1 contract: `pet list-plugins` has NO --group flag; use --json + jq
          pet list-plugins --json | tee /tmp/plugins.json
          jq -e '.datasets | index("pet_data.vision_frames")'              /tmp/plugins.json
          jq -e '.datasets | index("pet_data.audio_clips")'                /tmp/plugins.json
          jq -e '.datasets | index("pet_annotation.vision_annotations")'   /tmp/plugins.json
          jq -e '.datasets | index("pet_annotation.audio_annotations")'    /tmp/plugins.json
```

- [ ] **Steps 1-5** TDD (via `act` or manual CI observation; if `act` is unavailable, push a draft PR to trigger CI and verify the job passes).
- [ ] **Commit**: `ci(pet-infra): plugin-discovery asserts Phase 2 keys`

---

### Task C5: DEVELOPMENT_GUIDE §10 update

**Files:** `docs/DEVELOPMENT_GUIDE.md`

Append a new top-level section:

```markdown
## 10. Phase 2 Data & Annotation runtime (pet-data 1.1.0, pet-annotation 1.1.0)

### 10.1 Modality discriminator

All samples and annotations carry a `modality` field (Literal: `vision | audio | sensor | multimodal`).
Pydantic uses this as a discriminator via `pet_schema.samples.Sample` / `pet_schema.annotations.Annotation` unions.

### 10.2 Storage scheme

Every `BaseSample.storage_uri` resolves through `pet_infra.storage.STORAGE.build(uri)`.
Phase 1 ships `local://`; S3 / WebDataset are future work (spec §7.9 YAGNI).

### 10.3 Dataset plugins registered Phase 2

| Registry key                           | Package         | Yields             |
|----------------------------------------|-----------------|--------------------|
| `pet_data.vision_frames`               | pet-data        | `VisionSample`     |
| `pet_data.audio_clips`                 | pet-data        | `AudioSample`      |
| `pet_annotation.vision_annotations`    | pet-annotation  | `VisionAnnotation` |
| `pet_annotation.audio_annotations`     | pet-annotation  | `AudioAnnotation`  |

### 10.4 LS template dispatch

`pet_annotation.human_review.templates.template_for(modality)` loads `vision.xml` or `audio.xml`.
Never hardcode LS XML in code; add new templates under `templates/<modality>.xml`.

### 10.5 Migration path from FrameRecord

pet-data's `FrameRecord` dataclass retains all domain-internal fields (phash, quality_flag, anomaly_score, annotation_status);
the **public contract** exported to downstream repos is `pet_schema.VisionSample` (via `storage.adapter.frame_row_to_vision_sample`).
Consumers (pet-train, pet-annotation) must consume `VisionSample`, never import `FrameRecord` directly.

### 10.6 Migration infrastructure

pet-data uses hand-written Python migrations (`storage/migrations/NNN_*.py`) — NOT Alembic.
pet-annotation uses `.sql` files (`migrations/NNN_*.sql`).
New migrations append; committed migrations are immutable (CLAUDE.md).
Introducing Alembic is not planned in Phase 2 (YAGNI).
```

- [ ] **Commit**: `docs: DEVELOPMENT_GUIDE §10 Phase 2 runtime`

---

### Task C6: `compatibility_matrix.yaml` bump

**Files:** `docs/compatibility_matrix.yaml`

Add/update the release entry:

```yaml
releases:
  - release: "2026.05"
    pet_schema: "2.0.0"
    pet_infra: "2.1.0"
    pet_data: "1.1.0"
    pet_annotation: "1.1.0"
    pet_train: "0.1.0"     # pre-Phase-3 placeholder
    pet_eval: "0.1.0"
    pet_quantize: "0.1.0"
    pet_ota: "0.1.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
```

- [ ] **Test**: `tests/test_compat_matrix.py` — asserts latest release has `pet_data == 1.1.0` and `pet_annotation == 1.1.0`.
- [ ] **Commit**: `chore(pet-infra): compatibility_matrix release 2026.05 includes Phase 2 versions`

---

### Task C7: PR + tag

Mirror Part A Task A14. Open PR → dev → main; tag `pet-infra v2.1.0`.

- [ ] Confirm all three repos at their target tags (`pet-data v1.1.0`, `pet-annotation v1.1.0`, `pet-infra v2.1.0`).
- [ ] Update `project_multi_model_refactor.md` auto-memory on completion.

---

## Definition of Done (Phase 2)

Referenced from spec §7.3 and §7.8.

- [ ] pet-data `v1.1.0` tag on main; migrations 002 + 003 round-trip; `select count(*)` on `frames` before/after 002 = same non-zero count (via manual QA on a prod-like DB dump)
- [ ] pet-annotation `v1.1.0` tag on main; migrations 002 + 003 round-trip; LS templates dispatch by modality verified with 1 vision + 1 audio task round-trip
- [ ] 4 new dataset plugins discoverable: `pet list-plugins --json | jq .datasets` shows all 4 keys
- [ ] `pet validate --recipe recipes/pet_data_ingest_smoke.yaml` exits 0 (preflight passes)
- [ ] `pet-infra v2.1.0` tag on main; compatibility_matrix release 2026.05 published
- [ ] DEVELOPMENT_GUIDE §10 merged and aligned with actual impl
- [ ] CI green on all three repos' `main` branches (ruff + mypy + pytest + plugin-discovery)
- [ ] Auto-memory `project_pet_data_status.md`, `project_pet_annotation_status.md`, `project_multi_model_refactor.md` updated

---

## Out of scope (YAGNI, per spec §7.9)

- Audio DPO pair generation (Phase 3+)
- Backfill of `frame_width`, `frame_height`, `brightness_score` for historical rows (separate data job)
- Audio source classes (no ingest path yet; audio rows are populated manually or via future ingest — Phase 3 responsibility)
- Label Studio audio plugin verification on a live LS 1.23 instance beyond smoke — deferred to Phase 3 integration test
- Alembic migration (current hand-written pattern retained)
- Real storage adapters beyond `local://`
- ClearML integration (Phase 3+)
- `pet-data run` non-dry-run execution (deferred to Phase 3 once trainers / evaluators land — for Phase 2, `pet run` smoke is the authoritative entry)

# Phase 2 债务还清 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 γ 顺序破坏性还清 Phase 2 的两条欠债（DEBT-1 按 annotator 范式重建 annotation 4 表、DEBT-2 pet-data/pet-annotation peer-dep 化），4 仓 5 PR 发布 2026.06 release。

**Architecture:** pet-schema 加 4 Pydantic 子类（LLM/Classifier/Rule/Human，discriminator 由 `modality` → `annotator_type`）+ pet-annotation 整仓 drop+rebuild 4 张 SQL 表 + pet-data/pet-annotation 从 pyproject 删 pet-infra pin（fail-fast import guard 兜底）+ pet-infra 出 peer-dep 文档约定 + compatibility_matrix 2026.06 行。

**Tech Stack:** Python 3.11 / Pydantic v2 (Discriminator) / SQLite + 原生 migration / mmengine-lite Registry / Hydra / pytest / pip + git-URL pin / GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-04-21-phase-2-debt-repayment-design.md`（North Star §0.2.1：灵活性/可插拔/可扩展/可对比）

**工作目录约定（每个仓库 git 独立）：**
- pet-schema: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema`
- pet-data: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-data`
- pet-annotation: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-annotation`
- pet-infra: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`

每个 PR 必须从 `dev` 切 `feature/*`；PR 目标分支 `dev`；merge 后再提 `dev → main` 同步 PR。所有 commit 用 `feat|fix|refactor|test|docs(仓库名): 说明` 格式。

**全局依赖图：**

```
#0 design+spec+plan (pet-infra)       ← 本仓库当前分支，先 merge
    ├── #1 pet-infra peer-dep docs/CI  ← 依赖 #0
    ├── #2 pet-data peer-dep           ← 依赖 #1（装序模板）
    ├── #3 pet-schema 4 paradigms      ← 独立，可并行 #2
    ├── #4 pet-annotation v2.0.0       ← 依赖 #1 + #3
    └── #5 pet-infra matrix v2.2.0     ← 依赖 #2/#3/#4
```

---

## PR #0: design + spec + plan（本分支 merge 前置）

**当前分支：** `feature/phase-2-debt-repayment-design`（已 commit 设计文档 + 主 spec §2.6/§3.3/§3.7/§7.3 修订）

### Task 0.1: 把本 plan 加进设计 PR

**Files:**
- Create: `pet-infra/docs/superpowers/plans/2026-04-21-phase-2-debt-repayment-plan.md`（当前文件）

- [ ] **Step 1: Commit plan on existing branch**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout feature/phase-2-debt-repayment-design
git add docs/superpowers/plans/2026-04-21-phase-2-debt-repayment-plan.md
git commit -m "docs(pet-infra): Phase 2 还债 implementation plan（5 PR × TDD）"
git push
```

- [ ] **Step 2: Open PR `feature/phase-2-debt-repayment-design → dev`**

```bash
gh pr create --base dev --title "docs: Phase 2 还债 design + implementation plan" --body "设计文档 + 实施 plan + 主 spec §2.6/§3.3/§3.7/§7.3 修订。见 docs/superpowers/specs/2026-04-21-phase-2-debt-repayment-design.md。"
```

- [ ] **Step 3: Wait for CI green, merge to dev; then open `dev → main` PR and merge**

### Task 0.2: Merge 后本地同步

- [ ] **Step 1: 切回 dev + pull**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull
git checkout main && git pull
```

---

## PR #1: pet-infra peer-dep convention（docs + smoke workflow）

**依赖：** PR #0 已 merge 到 pet-infra/main（design doc + plan 在 main）。
**仓库：** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**分支：** `feature/peer-dep-convention`（base `dev`）
**版本：** 不 bump（#5 统一 bump 到 2.2.0）
**注意：** 本 PR **暂不** 删 `plugin-discovery.yml` 里 `--force-reinstall --no-deps`（下游老 tag 还有 pin，#5 才清理）。

### Task 1.1: 切分支

- [ ] **Step 1: From dev**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull
git checkout -b feature/peer-dep-convention
```

### Task 1.2: DEVELOPMENT_GUIDE.md 新增 §11 peer-dep 约定

**Files:**
- Modify: `docs/DEVELOPMENT_GUIDE.md`（当前 2465 行；heading 用 `## 1.` / `## 2.` … 不加 `§`；现有 `## 11. 附录`）

**约定说明**：保持现有 Arabic-numeral heading 风格（`## 11.` 不是 `## §11`），在 spec/plan 正文里写 "§11" 仍然指代同一小节（§ 是 spec 的引用风格）。

- [ ] **Step 1: 找到附录的标题位置**

```bash
grep -nE "^## 11\. " docs/DEVELOPMENT_GUIDE.md
```
Expected: 定位到当前 `## 11. 附录`（约 2374 行）。

- [ ] **Step 2: 把原 `## 11. 附录` 改为 `## 12. 附录`，并在其上插入新 `## 11. 依赖治理与 peer-dep 约定`**

新节内容必须含以下小节（heading 用 `### 11.1` 等，与文件现有风格一致）：
1. **11.1 为什么 peer-dep** — compatibility_matrix 是唯一真理源；下游不 pin pet-infra；pet-infra 自由演进。
2. **11.2 下游 `pyproject.toml` 写法** — `[project.dependencies]` 里**不**声明 pet-infra；README 加 Prerequisites 段。
3. **11.3 `_register.py` fail-fast guard 模板** — 含 spec §3 的 try/except 片段。
4. **11.4 统一 CI 装序模板** — 含下面 3 行 bash：

```bash
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<matrix_tag>'
pip install -e . --no-deps
python -c "import pet_infra; assert pet_infra.__version__.startswith(('2.',))"
```

5. **11.5 开发环境** — conda env `pet-pipeline` 已预装 pet-infra（cite `feedback_env_naming`）；CI 每次全新装。

- [ ] **Step 3: Commit**

```bash
git add docs/DEVELOPMENT_GUIDE.md
git commit -m "docs(pet-infra): §11 peer-dep 约定（compatibility_matrix 作真理源 + fail-fast 模板 + CI 装序）"
```

### Task 1.3: 新增 install-order-smoke workflow

**Files:**
- Create: `.github/workflows/install-order-smoke.yml`

- [ ] **Step 1: 写 workflow 验装序**

```yaml
name: install-order-smoke
on:
  pull_request:
    paths:
      - 'docs/DEVELOPMENT_GUIDE.md'
      - '.github/workflows/install-order-smoke.yml'
  workflow_dispatch:

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install pet-infra (editable, current PR code)
        run: pip install -e ".[dev]"
      - name: Assert import + version
        run: |
          python -c "import pet_infra; print(pet_infra.__version__)"
          python -c "import pet_infra; assert pet_infra.__version__.startswith('2.')"
      - name: Smoke: list-plugins
        run: pet list-plugins --json
```

- [ ] **Step 2: Trigger manually**

```bash
git add .github/workflows/install-order-smoke.yml
git commit -m "ci(pet-infra): install-order-smoke workflow（§11 peer-dep 装序自测）"
git push -u origin feature/peer-dep-convention
gh workflow run install-order-smoke.yml --ref feature/peer-dep-convention
```

Expected: green。

### Task 1.4: Open PR 并 merge

- [ ] **Step 1: `feature/peer-dep-convention → dev`**

```bash
gh pr create --base dev --title "docs(pet-infra): §11 peer-dep convention + install-order-smoke CI" --body "PR #1 of Phase 2 debt-repayment chain. 只加文档和 smoke CI，不动 plugin-discovery.yml（下游老 tag pin 还在）。"
```

- [ ] **Step 2: CI 绿后 merge dev**；再提 `dev → main` PR + merge。

---

## PR #2: pet-data peer-dep（v1.2.0）

**依赖：** PR #1 已 merge（§11 约定是权威来源）。
**仓库：** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-data`
**分支：** `feature/pet-infra-peer-dep`（base `dev`）
**版本：** bump `1.1.0` → `1.2.0`

### Task 2.1: 切分支

- [ ] **Step 1:**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-data
git checkout dev && git pull
git checkout -b feature/pet-infra-peer-dep
```

### Task 2.2: Write failing fail-fast guard test

**Files:**
- Create: `tests/test_peer_dep_fail_fast.py`

- [ ] **Step 1: Write test**

```python
import sys
import importlib
import pytest


def test_register_raises_friendly_error_if_pet_infra_missing(monkeypatch):
    """没装 pet-infra 时 import pet_data._register 必须抛带安装指引的 ImportError。"""
    # 强制让 'import pet_infra' 失败
    monkeypatch.setitem(sys.modules, "pet_infra", None)
    if "pet_data._register" in sys.modules:
        del sys.modules["pet_data._register"]

    with pytest.raises(ImportError) as excinfo:
        importlib.import_module("pet_data._register")

    msg = str(excinfo.value)
    assert "pet-infra" in msg
    assert "git+https://github.com/Train-Pet-Pipeline/pet-infra" in msg
    assert "compatibility_matrix" in msg
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_peer_dep_fail_fast.py -v
```
Expected: FAIL（当前 `_register.py` 没有 guard，要么无报错直接 import 要么错误消息不含所需字符串）。

### Task 2.3: 加 fail-fast guard 到 `_register.py`

**Files:**
- Modify: `src/pet_data/_register.py`

- [ ] **Step 1: 在文件最顶部（任何其它 import 之前）加 guard**

```python
try:
    import pet_infra  # noqa: F401
except ImportError as e:
    raise ImportError(
        "pet-data requires pet-infra to be installed first. "
        "Install via 'pip install pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<tag>' "
        "using the tag pinned in pet-infra/docs/compatibility_matrix.yaml."
    ) from e
```

- [ ] **Step 2: Run test to verify it passes**

```bash
pytest tests/test_peer_dep_fail_fast.py -v
```
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add tests/test_peer_dep_fail_fast.py src/pet_data/_register.py
git commit -m "feat(pet-data): _register.py fail-fast 守卫 + 测试"
```

### Task 2.4: 删 pyproject.toml 的 pet-infra pin + bump 1.2.0

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Grep 当前 pin**

```bash
grep -n "pet-infra" pyproject.toml
```
Expected: 一行 `"pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v2.0.0"`。

- [ ] **Step 2: 删掉那一行 + bump version**

- [ ] **Step 3: Verify**

```bash
grep -n "pet-infra" pyproject.toml
```
Expected: 无输出。

```bash
grep "^version" pyproject.toml
```
Expected: `version = "1.2.0"`。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "refactor(pet-data): 去 pet-infra 硬 pin + bump v1.2.0（peer-dep 模式）"
```

### Task 2.5: 更新 CI workflow 装序

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 找到当前装 pet-data 的步骤**

```bash
grep -n "pip install" .github/workflows/ci.yml
```

- [ ] **Step 2: 在装 pet-data 之前先装 pet-infra 的 compat 版本**

替换相关 step 为：

```yaml
      - name: Install pet-infra (peer-dep, per compatibility_matrix)
        run: pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.1.0'
      - name: Install pet-data (editable, no-deps over pet-infra)
        run: pip install -e ".[dev]" --no-deps
      - name: Re-resolve remaining deps
        run: pip install -e ".[dev]"
```

（装序思路：先装 peer-dep 锚定 pet-infra → editable pet-data 拉 pet-schema 等其它依赖）

- [ ] **Step 3: Verify YAML**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: 无错。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(pet-data): 装序改为 pet-infra 先装 + editable --no-deps"
```

### Task 2.6: README Prerequisites 段

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 Installation 段前加 Prerequisites**

```markdown
## Prerequisites

pet-data depends on `pet-infra` as a peer dependency. Install it first using the tag pinned in
[`pet-infra/docs/compatibility_matrix.yaml`](https://github.com/Train-Pet-Pipeline/pet-infra/blob/main/docs/compatibility_matrix.yaml):

```bash
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<matrix_tag>'
```

Then install pet-data:
```bash
pip install -e . --no-deps
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(pet-data): README Prerequisites 段（peer-dep install order）"
```

### Task 2.7: Push + PR

- [ ] **Step 1:**

```bash
git push -u origin feature/pet-infra-peer-dep
gh pr create --base dev --title "refactor(pet-data): peer-dep 化 + v1.2.0" --body "PR #2 of Phase 2 debt-repayment chain."
```

- [ ] **Step 2: CI 绿后 merge dev → main → tag `v1.2.0`**

```bash
gh release create v1.2.0 --target main --title "pet-data v1.2.0 — peer-dep" --notes "去 pet-infra 硬 pin；改用 peer-dep + fail-fast guard。compatibility_matrix 成为唯一真理源。"
```

---

## PR #3: pet-schema 4 Annotation 范式子类（v2.1.0）

**依赖：** 无（可与 PR #2 并行）。
**仓库：** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema`
**分支：** `feature/annotation-four-paradigms`（base `dev`）
**版本：** bump `2.0.0` → `2.1.0`

### Task 3.1: 切分支

- [ ] **Step 1:**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-schema
git checkout dev && git pull
git checkout -b feature/annotation-four-paradigms
```

### Task 3.2: Write failing tests for 4 paradigms

**Files:**
- Modify: `tests/test_annotations.py`（整体改写；不保留旧 case）

- [ ] **Step 1: 覆盖式重写 tests/test_annotations.py**

```python
from datetime import datetime
import pytest
from pydantic import ValidationError

from pet_schema import (
    BaseAnnotation,
    LLMAnnotation,
    ClassifierAnnotation,
    RuleAnnotation,
    HumanAnnotation,
    Annotation,
)


BASE_KW = dict(
    annotation_id="a1",
    target_id="f1",
    annotator_id="qwen2vl-7b",
    modality="vision",
    schema_version="2.1.0",
    created_at=datetime(2026, 4, 21),
    storage_uri=None,
)


# LLMAnnotation
def test_llm_roundtrip():
    src = LLMAnnotation(
        **BASE_KW,
        prompt_hash="abc",
        raw_response="...",
        parsed_output={"event": "eat"},
    )
    rt = LLMAnnotation.model_validate_json(src.model_dump_json())
    assert rt == src


def test_llm_missing_required():
    with pytest.raises(ValidationError):
        LLMAnnotation(**BASE_KW, prompt_hash="a", raw_response="b")  # 缺 parsed_output


def test_llm_modality_enum():
    with pytest.raises(ValidationError):
        LLMAnnotation(
            **{**BASE_KW, "modality": "infrared"},
            prompt_hash="a",
            raw_response="b",
            parsed_output={},
        )


# ClassifierAnnotation
def test_classifier_roundtrip():
    src = ClassifierAnnotation(
        **{**BASE_KW, "modality": "audio", "annotator_id": "audio-cnn-v1"},
        predicted_class="bark",
        class_probs={"bark": 0.9, "meow": 0.1},
        logits=[1.2, -0.3],
    )
    rt = ClassifierAnnotation.model_validate_json(src.model_dump_json())
    assert rt == src


def test_classifier_logits_optional():
    ClassifierAnnotation(
        **BASE_KW,
        predicted_class="x",
        class_probs={"x": 1.0},
        logits=None,
    )


def test_classifier_missing_required():
    with pytest.raises(ValidationError):
        ClassifierAnnotation(**BASE_KW, predicted_class="x")  # 缺 class_probs


# RuleAnnotation
def test_rule_roundtrip():
    src = RuleAnnotation(**BASE_KW, rule_id="threshold_v1", rule_output={"passed": True})
    rt = RuleAnnotation.model_validate_json(src.model_dump_json())
    assert rt == src


# HumanAnnotation
def test_human_roundtrip():
    src = HumanAnnotation(
        **{**BASE_KW, "annotator_id": "alice"},
        reviewer="alice",
        decision="accept",
        notes=None,
    )
    rt = HumanAnnotation.model_validate_json(src.model_dump_json())
    assert rt == src


# Discriminator routing
def test_annotation_discriminator_routes_llm():
    from pydantic import TypeAdapter

    ta = TypeAdapter(Annotation)
    obj = ta.validate_python(
        {
            **BASE_KW,
            "annotator_type": "llm",
            "prompt_hash": "h",
            "raw_response": "r",
            "parsed_output": {},
            "created_at": "2026-04-21T00:00:00",
        }
    )
    assert isinstance(obj, LLMAnnotation)


def test_annotation_discriminator_routes_classifier():
    from pydantic import TypeAdapter

    ta = TypeAdapter(Annotation)
    obj = ta.validate_python(
        {
            **BASE_KW,
            "annotator_type": "classifier",
            "predicted_class": "x",
            "class_probs": {"x": 1.0},
            "logits": None,
            "created_at": "2026-04-21T00:00:00",
        }
    )
    assert isinstance(obj, ClassifierAnnotation)


def test_annotation_discriminator_unknown_type_rejected():
    from pydantic import TypeAdapter

    ta = TypeAdapter(Annotation)
    with pytest.raises(ValidationError):
        ta.validate_python({**BASE_KW, "annotator_type": "vlm"})  # 旧名应被拒
```

- [ ] **Step 2: Run to verify FAIL**

```bash
pytest tests/test_annotations.py -v
```
Expected: FAIL（旧 `VisionAnnotation/AudioAnnotation` 还在，`LLMAnnotation` 等未定义，ImportError）。

### Task 3.3: 重写 annotations.py

**Files:**
- Modify: `src/pet_schema/annotations.py`

- [ ] **Step 1: 整体替换为 spec §2 的 Pydantic 定义**

```python
"""Annotation contracts — discriminator 按 annotator_type（非 modality）。

Spec: docs/superpowers/specs/2026-04-21-phase-2-debt-repayment-design.md §2
"""
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Discriminator

from pet_schema.enums import Modality


class BaseAnnotation(BaseModel):
    annotation_id: str
    target_id: str
    annotator_type: Literal["llm", "classifier", "rule", "human"]
    annotator_id: str
    modality: Modality
    schema_version: str
    created_at: datetime
    storage_uri: Optional[str] = None


class LLMAnnotation(BaseAnnotation):
    annotator_type: Literal["llm"] = "llm"
    prompt_hash: str
    raw_response: str
    parsed_output: dict


class ClassifierAnnotation(BaseAnnotation):
    annotator_type: Literal["classifier"] = "classifier"
    predicted_class: str
    class_probs: dict[str, float]
    logits: Optional[list[float]] = None


class RuleAnnotation(BaseAnnotation):
    annotator_type: Literal["rule"] = "rule"
    rule_id: str
    rule_output: dict


class HumanAnnotation(BaseAnnotation):
    annotator_type: Literal["human"] = "human"
    reviewer: str
    decision: str
    notes: Optional[str] = None


Annotation = Annotated[
    LLMAnnotation | ClassifierAnnotation | RuleAnnotation | HumanAnnotation,
    Discriminator("annotator_type"),
]


class DpoPair(BaseModel):
    """A chosen/rejected annotation pair for DPO training."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str
    chosen_annotation_id: str
    rejected_annotation_id: str
    target_id: str
    modality: Modality
    # 保留 preference_source/reason（method-source tracking — comparability）
    preference_source: Literal["human", "rule", "auto"]
    reason: Optional[str] = None
    created_at: datetime
    schema_version: str
```

- [ ] **Step 2: Run test to verify PASS**

```bash
pytest tests/test_annotations.py -v
```
Expected: PASS。

### Task 3.4: Update `__init__.py` 再导出

**Files:**
- Modify: `src/pet_schema/__init__.py`

- [ ] **Step 1: 替换 `VisionAnnotation`, `AudioAnnotation` 导入/导出**

```bash
grep -n "VisionAnnotation\|AudioAnnotation" src/pet_schema/__init__.py
```

- [ ] **Step 2: 编辑 — 将
`from pet_schema.annotations import BaseAnnotation, VisionAnnotation, AudioAnnotation, Annotation, DpoPair`
改为
`from pet_schema.annotations import BaseAnnotation, LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation, Annotation, DpoPair`**

同步更新 `__all__` list（如果有）。

- [ ] **Step 3: Verify 旧符号不再导出**

```bash
python -c "from pet_schema import VisionAnnotation" 2>&1 | grep -q "ImportError" && echo OK
python -c "from pet_schema import LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation; print('OK')"
```
Expected: 两行都输出 `OK`。

### Task 3.5: Update SCHEMA_VERSION constant

**Files:**
- Modify: `src/pet_schema/__init__.py`（或 `version.py` — grep 找）

- [ ] **Step 1: Locate**

```bash
grep -rn "SCHEMA_VERSION" src/pet_schema/
```

- [ ] **Step 2: 改为 `"2.1.0"`**

### Task 3.6: Bump pyproject.toml version

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1:** 把 `version = "2.0.0"` 改为 `version = "2.1.0"`。

### Task 3.7: Delete/rewrite 仍引用旧符号的测试

**Files:**
- Modify: `tests/test_public_api.py`, `tests/test_pydantic_sync.py`（如果引用旧符号）

- [ ] **Step 1: Grep 残留**

```bash
grep -rn "VisionAnnotation\|AudioAnnotation" tests/ src/
```
Expected: 无残留。

- [ ] **Step 2: 若有残留，就地替换为 4 新符号；若该测试整体无意义直接删整段**

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```
Expected: 全绿。

### Task 3.8: Commit + push + PR + tag

- [ ] **Step 1:**

```bash
git add -A
git commit -m "refactor(pet-schema): Annotation 按 annotator_type 换 4 子类（LLM/Classifier/Rule/Human）+ SCHEMA_VERSION 2.1.0 + bump v2.1.0"
git push -u origin feature/annotation-four-paradigms
gh pr create --base dev --title "refactor(pet-schema): Annotation 4 paradigms + v2.1.0" --body "PR #3 of Phase 2 debt-repayment chain. spec §3.3 / 本仓 v2.1.0。注意：此 PR merge 后下游 pet-annotation 的 CI 预期会红，直到 PR #4 merge。"
```

- [ ] **Step 2: 2 位 reviewer（pet-schema 规则）+ CI 绿 → merge dev → main → tag**

```bash
gh release create v2.1.0 --target main --title "pet-schema v2.1.0 — 4 annotator paradigms" --notes "BREAKING: VisionAnnotation/AudioAnnotation 删除；新增 LLM/Classifier/Rule/Human 4 子类；Annotation discriminator 由 modality → annotator_type。"
```

---

## PR #4: pet-annotation v2.0.0 major（4 tables + peer-dep）

**依赖：** PR #1（装序模板）+ PR #3（import pet_schema.LLMAnnotation 等）。
**仓库：** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-annotation`
**分支：** `feature/four-paradigm-tables`（base `dev`）
**版本：** bump `1.1.0` → `2.0.0`（**破坏性**：DB schema drop+rebuild，无迁移脚本）

### Task 4.1: 切分支 + 更新 pet-schema pin

- [ ] **Step 1: 切分支**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-annotation
git checkout dev && git pull
git checkout -b feature/four-paradigm-tables
```

- [ ] **Step 2: pyproject.toml — 更新 pet-schema pin 到 v2.1.0 + 删 pet-infra 硬 pin + bump 版本**

```bash
grep -n "pet-schema\|pet-infra\|^version" pyproject.toml
```
Edit：
- `pet-schema @ git+…@v2.0.0` → `pet-schema @ git+…@v2.1.0`
- 删 `pet-infra @ git+…@v2.0.0` 整行
- `version = "1.1.0"` → `version = "2.0.0"`

- [ ] **Step 3: Verify**

```bash
grep -n "pet-infra" pyproject.toml  # 应无输出
grep -n "pet-schema" pyproject.toml  # 应只含 v2.1.0
grep "^version" pyproject.toml       # 应 = "2.0.0"
```

- [ ] **Step 4: Commit (1st of many)**

```bash
git add pyproject.toml
git commit -m "refactor(pet-annotation): pyproject 去 pet-infra pin + pet-schema 拉到 v2.1.0 + bump v2.0.0"
```

### Task 4.2: Add fail-fast guard + failing test

**Files:**
- Create: `tests/test_peer_dep_fail_fast.py`
- Modify: `src/pet_annotation/_register.py`

- [ ] **Step 1: Write test**（同 pet-data task 2.2 逻辑，换包名）

```python
import sys, importlib, pytest

def test_register_raises_friendly_error_if_pet_infra_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "pet_infra", None)
    if "pet_annotation._register" in sys.modules:
        del sys.modules["pet_annotation._register"]
    with pytest.raises(ImportError) as excinfo:
        importlib.import_module("pet_annotation._register")
    msg = str(excinfo.value)
    assert "pet-infra" in msg
    assert "compatibility_matrix" in msg
```

- [ ] **Step 2: Run → FAIL**

```bash
pytest tests/test_peer_dep_fail_fast.py -v
```

- [ ] **Step 3: 在 `_register.py` 最顶加 guard**（同 pet-data task 2.3 的 try/except）

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/test_peer_dep_fail_fast.py src/pet_annotation/_register.py
git commit -m "feat(pet-annotation): _register.py fail-fast 守卫 + 测试"
```

### Task 4.3: 写 4 表 roundtrip 失败测试

**Files:**
- Create: `tests/test_four_paradigm_tables.py`

- [ ] **Step 1: Write failing test**

```python
"""4 annotator-paradigm 表 insert / select / CHECK 约束。

Spec: 2026-04-21-phase-2-debt-repayment-design.md §2 + §5
"""
from datetime import datetime
import sqlite3
import pytest

from pet_annotation.store import AnnotationStore
from pet_schema import LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "ann.db"
    s = AnnotationStore(str(db))
    s.init_schema()  # 跑到 migration 004
    return s


def _base():
    return dict(
        target_id="t1",
        annotator_id="ann-1",
        modality="vision",
        schema_version="2.1.0",
        created_at=datetime(2026, 4, 21),
        storage_uri=None,
    )


def test_insert_llm_roundtrip(store):
    ann = LLMAnnotation(annotation_id="a1", **_base(),
                        prompt_hash="h", raw_response="r", parsed_output={"ev": "eat"})
    store.insert_llm(ann)
    rows = store.fetch_llm_by_target("t1")
    assert len(rows) == 1
    assert rows[0].parsed_output == {"ev": "eat"}


def test_insert_classifier_roundtrip(store):
    ann = ClassifierAnnotation(annotation_id="c1", **{**_base(), "modality": "audio"},
                               predicted_class="bark",
                               class_probs={"bark": 0.9, "meow": 0.1},
                               logits=[1.2, -0.3])
    store.insert_classifier(ann)
    rows = store.fetch_classifier_by_target("t1")
    assert len(rows) == 1


def test_insert_rule_roundtrip(store):
    ann = RuleAnnotation(annotation_id="r1", **_base(),
                         rule_id="rule1", rule_output={"passed": True})
    store.insert_rule(ann)
    assert len(store.fetch_rule_by_target("t1")) == 1


def test_insert_human_roundtrip(store):
    ann = HumanAnnotation(annotation_id="h1", **{**_base(), "annotator_id": "alice"},
                          reviewer="alice", decision="accept", notes=None)
    store.insert_human(ann)
    assert len(store.fetch_human_by_target("t1")) == 1


def test_modality_check_rejects_invalid(store):
    # Use private _conn intentionally to bypass Pydantic validation and poke
    # an invalid modality directly at the SQL layer — verifies CHECK constraint.
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO llm_annotations(annotation_id, target_id, annotator_id, annotator_type, "
            "modality, schema_version, created_at, prompt_hash, raw_response, parsed_output) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("x", "t", "a", "llm", "infrared", "2.1.0", "now", "h", "r", "{}"),
        )
        store._conn.commit()


def test_unique_on_target_annotator_prompt_hash(store):
    ann = LLMAnnotation(annotation_id="a1", **_base(),
                        prompt_hash="h", raw_response="r", parsed_output={})
    store.insert_llm(ann)
    with pytest.raises(sqlite3.IntegrityError):
        # 同 target + annotator_id + prompt_hash 再插一次
        dup = LLMAnnotation(annotation_id="a2", **_base(),
                            prompt_hash="h", raw_response="r2", parsed_output={})
        store.insert_llm(dup)
```

- [ ] **Step 2: Run → FAIL**

```bash
pytest tests/test_four_paradigm_tables.py -v
```
Expected: FAIL（migration 004 不存在；`store.insert_llm` 等方法不存在）。

### Task 4.4: Write migration 004（drop old + create 4）

**Files:**
- Create: `migrations/004_four_paradigm_tables.sql`（**repo 顶层 `migrations/` 目录**，不是 `src/pet_annotation/migrations/`——与现存 001/002/003 同目录；`store.py` 里 `_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"`）

- [ ] **Step 1: Write migration**

```sql
-- Phase 2 还债：annotation 表按 annotator 范式拆 4 张（从 modality 换轴为 annotator_type）
-- Spec: 2026-04-21-phase-2-debt-repayment-design.md §2

-- Drop 旧表（破坏性，无数据迁移；历史靠 git checkout <v1.1.0>）
DROP TABLE IF EXISTS annotations;
DROP TABLE IF EXISTS audio_annotations;
DROP TABLE IF EXISTS model_comparisons;

CREATE TABLE llm_annotations (
    annotation_id   TEXT    PRIMARY KEY,
    target_id       TEXT    NOT NULL,
    annotator_id    TEXT    NOT NULL,
    annotator_type  TEXT    NOT NULL CHECK (annotator_type = 'llm'),
    modality        TEXT    NOT NULL CHECK (modality IN ('vision','audio','sensor','multimodal')),
    schema_version  TEXT    NOT NULL DEFAULT '2.1.0',
    created_at      TEXT    NOT NULL,
    storage_uri     TEXT,
    prompt_hash     TEXT    NOT NULL,
    raw_response    TEXT    NOT NULL,
    parsed_output   TEXT    NOT NULL,
    UNIQUE (target_id, annotator_id, prompt_hash)
);
CREATE INDEX idx_llm_target ON llm_annotations(target_id);
CREATE INDEX idx_llm_modality ON llm_annotations(modality);

CREATE TABLE classifier_annotations (
    annotation_id   TEXT    PRIMARY KEY,
    target_id       TEXT    NOT NULL,
    annotator_id    TEXT    NOT NULL,
    annotator_type  TEXT    NOT NULL CHECK (annotator_type = 'classifier'),
    modality        TEXT    NOT NULL CHECK (modality IN ('vision','audio','sensor','multimodal')),
    schema_version  TEXT    NOT NULL DEFAULT '2.1.0',
    created_at      TEXT    NOT NULL,
    storage_uri     TEXT,
    predicted_class TEXT    NOT NULL,
    class_probs     TEXT    NOT NULL,
    logits          TEXT,
    UNIQUE (target_id, annotator_id)
);
CREATE INDEX idx_cls_target ON classifier_annotations(target_id);
CREATE INDEX idx_cls_modality ON classifier_annotations(modality);

CREATE TABLE rule_annotations (
    annotation_id   TEXT    PRIMARY KEY,
    target_id       TEXT    NOT NULL,
    annotator_id    TEXT    NOT NULL,
    annotator_type  TEXT    NOT NULL CHECK (annotator_type = 'rule'),
    modality        TEXT    NOT NULL CHECK (modality IN ('vision','audio','sensor','multimodal')),
    schema_version  TEXT    NOT NULL DEFAULT '2.1.0',
    created_at      TEXT    NOT NULL,
    storage_uri     TEXT,
    rule_id         TEXT    NOT NULL,
    rule_output     TEXT    NOT NULL,
    UNIQUE (target_id, annotator_id, rule_id)
);
CREATE INDEX idx_rule_target ON rule_annotations(target_id);

CREATE TABLE human_annotations (
    annotation_id   TEXT    PRIMARY KEY,
    target_id       TEXT    NOT NULL,
    annotator_id    TEXT    NOT NULL,
    annotator_type  TEXT    NOT NULL CHECK (annotator_type = 'human'),
    modality        TEXT    NOT NULL CHECK (modality IN ('vision','audio','sensor','multimodal')),
    schema_version  TEXT    NOT NULL DEFAULT '2.1.0',
    created_at      TEXT    NOT NULL,
    storage_uri     TEXT,
    reviewer        TEXT    NOT NULL,
    decision        TEXT    NOT NULL,
    notes           TEXT,
    UNIQUE (target_id, annotator_id)
);
CREATE INDEX idx_human_target ON human_annotations(target_id);
```

- [ ] **Step 2: （不运行测试——等 store.py 改完一起跑）**

- [ ] **Step 3: Commit**

```bash
git add migrations/004_four_paradigm_tables.sql
git commit -m "feat(pet-annotation): migration 004 drop 旧 3 表 + 建 4 范式表（CHECK + UNIQUE 约束）"
```

### Task 4.5: Rewrite `store.py` for 4 tables

**Files:**
- Modify: `src/pet_annotation/store.py`（当前 740 行；整仓重写；旧 `VisionAnnotationRow` / `AudioAnnotationRow` / `ComparisonRecord` 全删）

- [ ] **Step 1: 明确重写目标**

保留：`AnnotationStore` 类名、`__init__(db_path)`、`init_schema()`（必须跑到 migration 004）、migration 幂等 executor。

新加方法（每 paradigm 一对）：
- `insert_llm(LLMAnnotation)` / `fetch_llm_by_target(target_id) -> list[LLMAnnotation]`
- `insert_classifier(ClassifierAnnotation)` / `fetch_classifier_by_target(target_id) -> list[ClassifierAnnotation]`
- `insert_rule(RuleAnnotation)` / `fetch_rule_by_target(target_id) -> list[RuleAnnotation]`
- `insert_human(HumanAnnotation)` / `fetch_human_by_target(target_id) -> list[HumanAnnotation]`

通用序列化 helper：`_serialize_json(dict) -> str`、`_parse_json(str) -> dict`。

删除：
- `class VisionAnnotationRow` / `class AudioAnnotationRow` / `class ComparisonRecord` 整段
- 所有引用 `annotations` / `audio_annotations` / `model_comparisons` 旧表名的 SQL
- 所有 `_recover_stuck_frames` 等老方法（Phase 2 流程里不再需要）

- [ ] **Step 2: 实现 store.py**

文件骨架（完整签名）：

```python
"""Annotation store — 4 annotator-paradigm tables.

Spec: docs/superpowers/specs/2026-04-21-phase-2-debt-repayment-design.md §2
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from pet_schema import (
    LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"
_APPLIED_MIGRATIONS_TABLE = "_applied_migrations"


def _dumps(d) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False)

def _loads(s: str | None):
    return json.loads(s) if s else None


class AnnotationStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_migrations_table()

    def init_schema(self) -> None:
        """顺序跑 migrations/ 下所有 .sql（跳过已 applied）。"""
        for mig_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            name = mig_path.name
            if self._already_applied(name):
                continue
            self._apply_migration(name, mig_path.read_text())

    def _ensure_migrations_table(self) -> None: ...
    def _already_applied(self, name: str) -> bool: ...
    def _apply_migration(self, name: str, sql: str) -> None: ...

    # ---- LLM ----
    def insert_llm(self, ann: LLMAnnotation) -> None:
        self._conn.execute(
            "INSERT INTO llm_annotations(annotation_id, target_id, annotator_id, annotator_type, "
            "modality, schema_version, created_at, storage_uri, prompt_hash, raw_response, parsed_output) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ann.annotation_id, ann.target_id, ann.annotator_id, ann.annotator_type,
             ann.modality, ann.schema_version, ann.created_at.isoformat(),
             ann.storage_uri, ann.prompt_hash, ann.raw_response, _dumps(ann.parsed_output)),
        )
        self._conn.commit()

    def fetch_llm_by_target(self, target_id: str) -> list[LLMAnnotation]:
        cur = self._conn.execute(
            "SELECT annotation_id, target_id, annotator_id, annotator_type, modality, "
            "schema_version, created_at, storage_uri, prompt_hash, raw_response, parsed_output "
            "FROM llm_annotations WHERE target_id = ?",
            (target_id,),
        )
        return [
            LLMAnnotation(
                annotation_id=r[0], target_id=r[1], annotator_id=r[2], annotator_type=r[3],
                modality=r[4], schema_version=r[5], created_at=r[6], storage_uri=r[7],
                prompt_hash=r[8], raw_response=r[9], parsed_output=_loads(r[10]),
            ) for r in cur.fetchall()
        ]

    # ---- Classifier ----
    def insert_classifier(self, ann: ClassifierAnnotation) -> None:
        self._conn.execute(
            "INSERT INTO classifier_annotations(annotation_id, target_id, annotator_id, annotator_type, "
            "modality, schema_version, created_at, storage_uri, predicted_class, class_probs, logits) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ann.annotation_id, ann.target_id, ann.annotator_id, ann.annotator_type,
             ann.modality, ann.schema_version, ann.created_at.isoformat(),
             ann.storage_uri, ann.predicted_class, _dumps(ann.class_probs),
             _dumps(ann.logits) if ann.logits is not None else None),
        )
        self._conn.commit()

    def fetch_classifier_by_target(self, target_id: str) -> list[ClassifierAnnotation]:
        ...  # 对称实现

    # ---- Rule ----
    def insert_rule(self, ann: RuleAnnotation) -> None: ...
    def fetch_rule_by_target(self, target_id: str) -> list[RuleAnnotation]: ...

    # ---- Human ----
    def insert_human(self, ann: HumanAnnotation) -> None: ...
    def fetch_human_by_target(self, target_id: str) -> list[HumanAnnotation]: ...
```

**JSON 约定**：SQL TEXT 列存 `json.dumps` 结果（`parsed_output` / `class_probs` / `logits` / `rule_output`）；读出时 `json.loads`。`sort_keys=True` 保证幂等。

**删除**：旧 `VisionAnnotationRow` / `AudioAnnotationRow` / `ComparisonRecord` 整段；旧 `_recover_stuck_frames`、旧 fetch-by-frame 方法——全删。

- [ ] **Step 3: Run test_four_paradigm_tables.py → PASS**

```bash
pytest tests/test_four_paradigm_tables.py -v
```
Expected: 全 PASS。

- [ ] **Step 4: Commit**

```bash
git add src/pet_annotation/store.py tests/test_four_paradigm_tables.py
git commit -m "refactor(pet-annotation): store.py 整仓重写为 4 范式表 API + 删 VisionAnnotationRow/AudioAnnotationRow/ComparisonRecord"
```

### Task 4.6: Rewrite `adapter.py`（按 annotator_type 路由）

**Files:**
- Create: `tests/test_adapter_routing.py`
- Modify: `src/pet_annotation/adapter.py`

- [ ] **Step 1: Write failing routing test**

```python
import pytest
from pet_annotation.adapter import route_annotation_to_store
from pet_schema import LLMAnnotation, HumanAnnotation
from datetime import datetime


def _base(**kw):
    return dict(
        annotation_id="a", target_id="t", annotator_id="x", modality="vision",
        schema_version="2.1.0", created_at=datetime(2026, 4, 21), storage_uri=None,
        **kw,
    )


def test_route_llm(store):
    ann = LLMAnnotation(**_base(prompt_hash="h", raw_response="r", parsed_output={}))
    route_annotation_to_store(ann, store)
    assert len(store.fetch_llm_by_target("t")) == 1


def test_route_human(store):
    ann = HumanAnnotation(**_base(annotator_id="alice"), reviewer="alice", decision="accept", notes=None)
    route_annotation_to_store(ann, store)
    assert len(store.fetch_human_by_target("t")) == 1


def test_route_unknown_type_fails(store):
    class FakeAnn:
        annotator_type = "vlm"  # 旧名应 fail-fast
    with pytest.raises(ValueError, match="unknown annotator_type"):
        route_annotation_to_store(FakeAnn(), store)
```

（复用 Task 4.3 的 `store` fixture，可提取到 `conftest.py`；见 Task 4.10。）

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: 重写 adapter.py**

```python
"""按 annotator_type 路由到对应 store 方法 — 不 branch 在 modality。"""
from pet_schema import Annotation, LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation


_ROUTES = {
    "llm": "insert_llm",
    "classifier": "insert_classifier",
    "rule": "insert_rule",
    "human": "insert_human",
}


def route_annotation_to_store(ann, store) -> None:
    t = getattr(ann, "annotator_type", None)
    method_name = _ROUTES.get(t)
    if method_name is None:
        raise ValueError(f"unknown annotator_type: {t!r} (valid: {list(_ROUTES)})")
    getattr(store, method_name)(ann)
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/test_adapter_routing.py src/pet_annotation/adapter.py
git commit -m "refactor(pet-annotation): adapter.py 按 annotator_type 路由 + fail-fast unknown type"
```

### Task 4.7: 4 dataset plugins + `_register.py` 重写

**Files:**
- Create: `src/pet_annotation/datasets/llm_annotations.py`, `classifier_annotations.py`, `rule_annotations.py`, `human_annotations.py`
- Delete: `src/pet_annotation/datasets/vision_annotations.py`, `audio_annotations.py`
- Modify: `src/pet_annotation/_register.py`
- Create: `tests/test_plugin_keys.py`

- [ ] **Step 1: Write failing plugin key test**

```python
from pet_annotation._register import register_all
from pet_infra.registries import DATASETS


def test_four_paradigm_keys_discoverable():
    register_all()
    expected = {
        "pet_annotation.llm",
        "pet_annotation.classifier",
        "pet_annotation.rule",
        "pet_annotation.human",
    }
    got = set(DATASETS.module_dict.keys())
    assert expected <= got, f"missing: {expected - got}"


def test_old_keys_not_registered():
    register_all()
    forbidden = {"pet_annotation.vision_annotations", "pet_annotation.audio_annotations"}
    got = set(DATASETS.module_dict.keys())
    assert forbidden.isdisjoint(got), f"stale keys still present: {forbidden & got}"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: 对每个 paradigm 创建一个 plugin 模块**

模板（`llm_annotations.py`）：
```python
"""DATASETS plugin: pet_annotation.llm"""
from pet_infra.registries import DATASETS
from pet_infra.abcs import BaseDataset


@DATASETS.register_module(name="pet_annotation.llm", force=True)
class LLMAnnotationDataset(BaseDataset):
    def build(self, dataset_config: dict):
        ...  # 最小实现：从 store 查 llm_annotations 表返回行

    def to_hf_dataset(self, dataset_config: dict):
        ...  # 占位即可

    def modality(self) -> str:
        return "multimodal"  # 4 表横跨 modality，返回 multimodal 标识
```

其它 3 个范式 plugin 照搬，换 key、表名、类名。

- [ ] **Step 4: 删 vision_annotations.py / audio_annotations.py**

```bash
git rm src/pet_annotation/datasets/vision_annotations.py src/pet_annotation/datasets/audio_annotations.py
```

- [ ] **Step 5: 重写 `_register.py` — 引入 4 个新 plugin，删旧 2**

```python
try:
    import pet_infra  # noqa: F401
except ImportError as e:
    raise ImportError(
        "pet-annotation requires pet-infra to be installed first. "
        "Install via 'pip install pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<tag>' "
        "using the tag pinned in pet-infra/docs/compatibility_matrix.yaml."
    ) from e


def register_all() -> None:
    from pet_annotation.datasets import (
        llm_annotations,       # noqa: F401
        classifier_annotations, # noqa: F401
        rule_annotations,       # noqa: F401
        human_annotations,      # noqa: F401
    )
```

- [ ] **Step 6: Run plugin key test → PASS**

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(pet-annotation): 4 paradigm dataset plugins（pet_annotation.llm/classifier/rule/human） + 删旧 vision/audio_annotations"
```

### Task 4.8: CLI —— `--annotator` dispatch

**Files:**
- Create: `tests/test_cli_annotator_dispatch.py`
- Modify: `src/pet_annotation/cli.py`（当前 291 行，`annotate --modality` 改为 `annotate --annotator`）

- [ ] **Step 1: Write failing CLI test**

```python
from click.testing import CliRunner
from pet_annotation.cli import cli


def test_cli_annotate_llm_audio_routes_to_llm_table(tmp_path, monkeypatch):
    runner = CliRunner()
    db = tmp_path / "t.db"
    # 模拟调用：--annotator=llm --modality=audio
    result = runner.invoke(cli, ["annotate", "--annotator", "llm", "--modality", "audio",
                                  "--db", str(db), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dispatch=llm" in result.output.lower()


def test_cli_rejects_unknown_annotator():
    runner = CliRunner()
    result = runner.invoke(cli, ["annotate", "--annotator", "vlm", "--modality", "vision"])
    assert result.exit_code != 0
    assert "invalid choice" in result.output.lower() or "unknown" in result.output.lower()
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: 在 `cli.py` 改 `annotate` 子命令：**
  - `--modality` 仍保留（描述被标注对象）
  - 新增 `--annotator` choice `["llm", "classifier", "rule", "human"]`，**required=True，无默认值**（feedback_refactor_no_legacy：不留隐式兼容路径，让调用方显式声明范式）
  - dispatch 逻辑按 annotator_type 分支到对应 pipeline；不认识的值 click 会自动拒绝（test `test_cli_rejects_unknown_annotator` 覆盖）

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_annotator_dispatch.py src/pet_annotation/cli.py
git commit -m "feat(pet-annotation): CLI --annotator dispatch（llm/classifier/rule/human）"
```

### Task 4.9: 删除全部引用旧符号的老测试 + 添加 fixture factory

**Files:**
- Rewrite: `tests/test_store.py`（原 447 行 — 整仓重写）
- Modify: `tests/conftest.py`
- Delete: `tests/test_store_audio.py`（整个文件，spec §5 明示）
- Potentially affected（grep 检查）: `tests/test_adapter.py`, `tests/test_migrations.py`, `tests/test_datasets_plugins.py`, `tests/test_plugin_registration.py`

- [ ] **Step 1: Grep 残留旧符号**

```bash
# 旧 row/record 类
grep -rn "VisionAnnotationRow\|AudioAnnotationRow\|ComparisonRecord" src/ tests/
# 旧 dataset 模块 + 旧 plugin key
grep -rn "pet_annotation\.vision_annotations\|pet_annotation\.audio_annotations" src/ tests/
# 旧 Pydantic 类名
grep -rn "VisionAnnotation\|AudioAnnotation" src/ tests/
```
Expected after Task 4.5-4.7：仅 `tests/test_store.py` / `tests/test_store_audio.py` / `tests/test_adapter.py` / `tests/test_datasets_plugins.py` / `tests/test_plugin_registration.py` 等老测试残留；以上每个文件都要在本 Task 扫清或重写。

- [ ] **Step 2: 整仓重写 tests/test_store.py**

保留骨架但全部 case 指向新 4 表 API（insert_llm/classifier/rule/human、fetch 对应、UNIQUE 约束、JSONB 字段 dump/load）。

- [ ] **Step 3: `git rm tests/test_store_audio.py`**

- [ ] **Step 4: `tests/conftest.py` 加 fixture factories**

```python
import pytest
from datetime import datetime
from pet_schema import LLMAnnotation, ClassifierAnnotation, RuleAnnotation, HumanAnnotation


def _base_kw(**overrides):
    base = dict(
        annotation_id="a", target_id="t", annotator_id="x", modality="vision",
        schema_version="2.1.0", created_at=datetime(2026, 4, 21), storage_uri=None,
    )
    base.update(overrides)
    return base


@pytest.fixture
def llm_annotation_factory():
    def make(**kw):
        return LLMAnnotation(
            **_base_kw(**kw),
            prompt_hash=kw.pop("prompt_hash", "h"),
            raw_response=kw.pop("raw_response", "r"),
            parsed_output=kw.pop("parsed_output", {}),
        )
    return make


@pytest.fixture
def classifier_annotation_factory():
    def make(**kw):
        return ClassifierAnnotation(
            **_base_kw(**kw),
            predicted_class=kw.pop("predicted_class", "x"),
            class_probs=kw.pop("class_probs", {"x": 1.0}),
            logits=kw.pop("logits", None),
        )
    return make


@pytest.fixture
def rule_annotation_factory():
    def make(**kw):
        return RuleAnnotation(
            **_base_kw(**kw),
            rule_id=kw.pop("rule_id", "r1"),
            rule_output=kw.pop("rule_output", {}),
        )
    return make


@pytest.fixture
def human_annotation_factory():
    def make(**kw):
        return HumanAnnotation(
            **_base_kw(**kw),
            reviewer=kw.pop("reviewer", "alice"),
            decision=kw.pop("decision", "accept"),
            notes=kw.pop("notes", None),
        )
    return make


@pytest.fixture
def store(tmp_path):
    from pet_annotation.store import AnnotationStore
    db = tmp_path / "ann.db"
    s = AnnotationStore(str(db))
    s.init_schema()
    return s
```

- [ ] **Step 5: 修复其它仍绿的老测试文件里的残留 import**

- [ ] **Step 6: Run full suite**

```bash
pytest -v
```
Expected: 全绿（旧用例删干净 + 新用例通过）。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "test(pet-annotation): 整仓重写 test_store.py + 删 test_store_audio.py + 新 conftest factories"
```

### Task 4.10: CI workflow 装序

**Files:**
- Modify: `.github/workflows/ci.yml`（同 Task 2.5 的 3 步装序）

- [ ] **Step 1: 替换装 pet-annotation 的 step**

```yaml
      - name: Install pet-infra (peer-dep)
        run: pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.1.0'
      - name: Install pet-annotation (editable, no-deps)
        run: pip install -e ".[dev]" --no-deps
      - name: Re-resolve remaining deps
        run: pip install -e ".[dev]"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(pet-annotation): 装序改为 pet-infra 先装 + editable --no-deps"
```

### Task 4.11: README + reset_db.sh

**Files:**
- Modify: `README.md`（加 Prerequisites 段 + v2.0.0 DB 破坏性说明）
- Create: `scripts/reset_db.sh`

- [ ] **Step 1: README**

加 Prerequisites 段（同 pet-data Task 2.6）；并加 **Breaking Changes in v2.0.0**：

```markdown
## Breaking Changes in v2.0.0

Annotation tables 按 annotator 范式重建（LLMAnnotation/ClassifierAnnotation/RuleAnnotation/HumanAnnotation）。
旧 `annotations` / `audio_annotations` / `model_comparisons` 表 drop + 重建，**无数据迁移脚本**。
历史数据靠 `git checkout v1.1.0` 回溯。本地 `.db` 文件需重建：

```bash
./scripts/reset_db.sh
```
```

- [ ] **Step 2: scripts/reset_db.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
DB_PATH="${1:-data/annotation.db}"
if [ -f "$DB_PATH" ]; then
  mv "$DB_PATH" "${DB_PATH}.v1backup.$(date +%s)"
  echo "Backed up old DB to ${DB_PATH}.v1backup.*"
fi
python -c "from pet_annotation.store import AnnotationStore; AnnotationStore('$DB_PATH').init_schema()"
echo "Fresh DB initialized at $DB_PATH (4 paradigm tables)."
```

```bash
chmod +x scripts/reset_db.sh
```

- [ ] **Step 3: Commit**

```bash
git add README.md scripts/reset_db.sh
git commit -m "docs(pet-annotation): README Prerequisites + BREAKING v2.0.0 说明 + scripts/reset_db.sh"
```

### Task 4.12: Grep 终态残留 → DoD check

**关键**：pet-annotation 旧表实际名为 `annotations` / `audio_annotations` / `model_comparisons`（**没有** `vision_annotations` 这张表，spec 的 "vision_annotations" 是类名 / plugin key，不是表名）。Python 源码里还会有 **旧 plugin key** `pet_annotation.vision_annotations` / `pet_annotation.audio_annotations` 残留。下面的 pattern 覆盖这三类残留。

- [ ] **Step 1: Grep 全面残留**

```bash
# 旧 Pydantic 类名 + 旧 row dataclass 名 + 旧 dataset 模块名 + 旧 plugin key
grep -rn "VisionAnnotation\|AudioAnnotation\|VisionAnnotationRow\|AudioAnnotationRow\|ComparisonRecord" src/ tests/
# 旧 plugin key
grep -rn "pet_annotation\.vision_annotations\|pet_annotation\.audio_annotations" src/ tests/
# 旧表名（audio_annotations / model_comparisons 是被 drop 的老表；注意 `annotations` 单独 grep 会误报子串，用 word boundary）
grep -rEn "\b(audio_annotations|model_comparisons)\b" src/ tests/ migrations/
grep -rEn "FROM annotations\b|INTO annotations\b|TABLE annotations\b" src/ tests/ migrations/
```
Expected: 除 migration 004 的 `DROP TABLE` 行外，**无输出**。若有残留，修改相应文件并 amend 提交。

### Task 4.13: Push + PR + merge + tag v2.0.0

- [ ] **Step 1:**

```bash
git push -u origin feature/four-paradigm-tables
gh pr create --base dev --title "refactor(pet-annotation): 4 范式表重建 + peer-dep + v2.0.0（BREAKING）" --body "PR #4 of Phase 2 debt-repayment chain. 破坏性升级：drop 旧 2 表 + 建 4 表 + annotator_type discriminator + peer-dep。需先 merge pet-schema v2.1.0 (#3) 才能绿。"
```

- [ ] **Step 2: CI 绿（依赖 PR #3 已 merge 到 main）→ merge dev → main → tag**

```bash
gh release create v2.0.0 --target main --title "pet-annotation v2.0.0 — 4 annotator paradigms" --notes "BREAKING: DB schema 整仓 drop + rebuild 为 4 annotator 范式表。无迁移脚本。旧数据靠 git checkout v1.1.0 回溯。详见 spec 2026-04-21-phase-2-debt-repayment-design.md §2。"
```

---

## PR #5: pet-infra matrix + plugin-discovery 清理（v2.2.0）

**依赖：** PR #2/#3/#4 全 merge 到 main。
**仓库：** `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**分支：** `feature/matrix-2026.06`（base `dev`）
**版本：** bump `2.1.0` → `2.2.0`

### Task 5.1: 切分支

- [ ] **Step 1:**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull
git checkout -b feature/matrix-2026.06
```

### Task 5.2: Write failing matrix test

**Files:**
- Modify: `tests/test_compat_matrix.py`（若不存在则 create）

- [ ] **Step 1:**

```python
import yaml
from pathlib import Path


def test_matrix_has_2026_06_release():
    path = Path(__file__).parents[1] / "docs" / "compatibility_matrix.yaml"
    data = yaml.safe_load(path.read_text())
    releases = {r["release"]: r for r in data["releases"]}
    assert "2026.06" in releases
    row = releases["2026.06"]
    assert row["pins"]["pet_schema"] == "2.1.0"
    assert row["pins"]["pet_infra"] == "2.2.0"
    assert row["pins"]["pet_data"] == "1.2.0"
    assert row["pins"]["pet_annotation"] == "2.0.0"
```

- [ ] **Step 2: Run → FAIL**（2026.06 行还没加）

### Task 5.3: 加 2026.06 row 到 compatibility_matrix.yaml

**Files:**
- Modify: `docs/compatibility_matrix.yaml`

- [ ] **Step 1: 在现有 releases 列表末尾追加**

```yaml
  - release: "2026.06"
    date: "2026-06-01"
    phase: "Phase 2 debt-repayment"
    pins:
      pet_schema: "2.1.0"
      pet_infra: "2.2.0"
      pet_data: "1.2.0"
      pet_annotation: "2.0.0"
      pet_train: "0.1.0"      # 占位，Phase 3 重建
      pet_eval: "0.1.0"       # 占位
      pet_quantize: "0.1.0"   # 占位
      pet_ota: "0.1.0"        # 占位
    notes: "Annotation 4 范式表 + peer-dep 模式。见 specs/2026-04-21-phase-2-debt-repayment-design.md。"
```

- [ ] **Step 2: Run test → PASS**

- [ ] **Step 3: Commit**

```bash
git add docs/compatibility_matrix.yaml tests/test_compat_matrix.py
git commit -m "feat(pet-infra): compatibility_matrix 2026.06 row + test 断言 4 仓 pin"
```

### Task 5.4: `plugin-discovery.yml` 删 workaround + 改装序

**Files:**
- Modify: `.github/workflows/plugin-discovery.yml`

- [ ] **Step 1: 读当前 33 行，确认 `--force-reinstall --no-deps` 步骤**

```bash
grep -n "force-reinstall\|no-deps" .github/workflows/plugin-discovery.yml
```

- [ ] **Step 2: 整体重写（~15 行）**

```yaml
name: plugin-discovery
on:
  pull_request:
  push:
    branches: [dev, main]

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install pet-infra (editable, this PR)
        run: pip install -e ".[dev]"
      - name: Install downstream (peer-dep, matrix 2026.06 tags, full deps)
        # 注意：pet-data / pet-annotation 不发 PyPI — 必须用 git+URL 安装，并让 pip 解析其 transitive deps。
        # 但它们的 pyproject 里已经不 pin pet-infra（peer-dep），所以不会覆盖上一步 editable pet-infra。
        run: |
          pip install 'pet-data @ git+https://github.com/Train-Pet-Pipeline/pet-data@v1.2.0'
          pip install 'pet-annotation @ git+https://github.com/Train-Pet-Pipeline/pet-annotation@v2.0.0'
      - name: Sanity: pet-infra still editable (not clobbered)
        run: python -c "import pet_infra, inspect; p=inspect.getfile(pet_infra); assert 'site-packages' not in p, p; print('editable OK:', p)"
      - name: Assert 4 new plugin keys present
        run: |
          pet list-plugins --json | python -c "
          import json, sys
          data = json.load(sys.stdin)
          keys = set(data['datasets'])
          expected = {
            'pet_data.vision_frames',
            'pet_data.audio_clips',
            'pet_annotation.llm',
            'pet_annotation.classifier',
            'pet_annotation.rule',
            'pet_annotation.human',
          }
          missing = expected - keys
          assert not missing, f'missing: {missing}'
          forbidden = {'pet_annotation.vision_annotations', 'pet_annotation.audio_annotations'}
          assert forbidden.isdisjoint(keys), f'stale keys: {forbidden & keys}'
          print('OK')
          "
```

- [ ] **Step 3: Verify YAML parses**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/plugin-discovery.yml'))"
```

- [ ] **Step 4: Grep 确认 workaround 不再存在**

```bash
grep -rn "force-reinstall" .github/
```
Expected: 无输出。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/plugin-discovery.yml
git commit -m "ci(pet-infra): plugin-discovery.yml 删 --force-reinstall workaround + 改装序 peer-dep + 断言 4 新 plugin key"
```

### Task 5.5: Integration smoke expected key 更新

**Files:**
- Modify: `tests/integration/test_phase2_smoke.py`

- [ ] **Step 1: 找到 expected dataset keys 集合**

```bash
grep -n "pet_annotation" tests/integration/test_phase2_smoke.py
```

- [ ] **Step 2: 替换旧 2 key 为新 4 key**

旧：
```python
assert "pet_annotation.vision_annotations" in DATASETS.module_dict
assert "pet_annotation.audio_annotations" in DATASETS.module_dict
```

新：
```python
for key in ("pet_annotation.llm", "pet_annotation.classifier", "pet_annotation.rule", "pet_annotation.human"):
    assert key in DATASETS.module_dict, f"missing {key}"
```

- [ ] **Step 3: Run**

```bash
pytest tests/integration/test_phase2_smoke.py -v
```
Expected: PASS（本地装了 pet-annotation v2.0.0 前提下；CI 里 matrix 2026.06 会自动拉）。

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_phase2_smoke.py
git commit -m "test(pet-infra): integration smoke 期望值更新为 4 范式 plugin key"
```

### Task 5.6: DEVELOPMENT_GUIDE.md §10 同步 4 范式

**Files:**
- Modify: `docs/DEVELOPMENT_GUIDE.md`

- [ ] **Step 1: 定位 `## 10.` Phase 2 runtime 段**

```bash
grep -nE "^## 10\. " docs/DEVELOPMENT_GUIDE.md
```
Expected: 定位到 `## 10. Phase 2 Data & Annotation 运行时（pet-data 1.1.0, pet-annotation 1.1.0）` 约 2314 行。**注意** heading 用纯 Arabic numeral（`## 10.`），不加 `§`。

- [ ] **Step 2: 把 §10 里列举的 annotation dataset key 从 `vision_annotations/audio_annotations` 改为 4 新 key，并在小节结尾加一段（heading 用 `### 10.X`，与文件既有风格一致）：**

```markdown
### 10.X Phase 2 债务还清（2026.06 release）

Annotation 表按 annotator 范式拆为 4 张（LLMAnnotation/ClassifierAnnotation/RuleAnnotation/HumanAnnotation），
discriminator 由 `modality` 改为 `annotator_type`。详见 `specs/2026-04-21-phase-2-debt-repayment-design.md`。
新 plugin key：`pet_annotation.{llm,classifier,rule,human}`。
```

- [ ] **Step 3: Commit**

```bash
git add docs/DEVELOPMENT_GUIDE.md
git commit -m "docs(pet-infra): §10 同步 4 范式 plugin key + 债务还清说明"
```

### Task 5.7: bump pyproject → 2.2.0

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: `version = "2.1.0"` → `"2.2.0"`**

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore(pet-infra): bump v2.2.0"
```

### Task 5.8: Push + PR + merge + tag v2.2.0

- [ ] **Step 1:**

```bash
git push -u origin feature/matrix-2026.06
gh pr create --base dev --title "release(pet-infra): matrix 2026.06 + plugin-discovery 清理 + v2.2.0" --body "PR #5 (final) of Phase 2 debt-repayment chain. 见 docs/superpowers/specs/2026-04-21-phase-2-debt-repayment-design.md。DoD 11 项：当本 PR merge 到 main + tag 推出，全部完成。"
```

- [ ] **Step 2: CI 绿 → merge dev → main → tag**

```bash
gh release create v2.2.0 --target main --title "pet-infra v2.2.0 — Phase 2 debt repaid" --notes "compatibility_matrix 2026.06 release (schema 2.1.0 / data 1.2.0 / annotation 2.0.0)。plugin-discovery workaround 删除。DEVELOPMENT_GUIDE §11 peer-dep 约定。"
```

---

## 收尾（memory + DoD）

### Task 收尾.1: 更新 memory

**Files:**
- Modify: `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/project_multi_model_refactor.md`
- Modify: `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/project_pet_infra_status.md`
- Modify: `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/project_pet_data_status.md`
- Modify: `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/project_pet_annotation_status.md`

- [ ] **Step 1: 在 refactor memory 标注**

"Phase 2 债务还清完成 2026-04-??（release 2026.06）：pet-schema v2.1.0 / pet-data v1.2.0 / pet-annotation v2.0.0（破坏性）/ pet-infra v2.2.0。Annotation 4 范式化 + peer-dep。下一步 Phase 3 Training。"

### Task 收尾.2: DoD checkbox

对照 spec §7 11 项 DoD 逐条勾选：

- [ ] design doc 在 pet-infra main（PR #0 merged）
- [ ] spec §3.3 / §7.3 / §2.6 修订在 main（同 #0）
- [ ] 5 条 PR 链（#1-#5）全部 merge 到各自 main
- [ ] pet-schema `v2.1.0` / pet-data `v1.2.0` / pet-annotation `v2.0.0` / pet-infra `v2.2.0` 四 tag 已发
- [ ] compatibility_matrix `2026.06` 行已提交 + 被 `test_compat_matrix.py` 断言
- [ ] pet-infra `plugin-discovery.yml` 里不再有 `--force-reinstall --no-deps`
- [ ] pet-annotation 源码里不再引用旧表名 (`annotations` / `audio_annotations` / `model_comparisons`) 和旧 plugin key (`pet_annotation.vision_annotations` / `pet_annotation.audio_annotations`) — 除 migration 004 的 `DROP TABLE` 行
- [ ] pet-schema 源码里不再导出 `VisionAnnotation` / `AudioAnnotation` 符号
- [ ] pet-data / pet-annotation `pyproject.toml` 里不再声明 `pet-infra` 依赖
- [ ] DEVELOPMENT_GUIDE `## 10` 已更新到 4 范式表；新增 `## 11. 依赖治理与 peer-dep 约定`（原附录重编号为 `## 12`）
- [ ] memory `project_multi_model_refactor.md` 标注还债完成

### Task 收尾.3: Phase 3 启动前执行 DEBT-4（North Star 自检条目）

- [ ] **Step 1: 在 Phase 3 plan 模板 DoD section 末尾加一行**：

```markdown
- [ ] North Star 自检：本 Phase 的每个主要决策都能回答「让未来加模型/模态/消融对比变简单还是变难」，若后者则须在 spec 有明确豁免理由
```

（这是 Phase 3 开始前的准备动作，不在本次还债 scope 内，但 plan 里提醒保留。）

---

## 通用提示

**每个 PR 要求：**
- 用 TDD：先写 failing test、再实现、再跑绿、再 commit。小步提交。
- 所有 commit 用 `feat|fix|refactor|test|docs|ci|chore(仓库名): 说明` 格式。
- 每个 PR 独立 green CI 才进下一条；跨 PR 依赖图遵守 #0 → (#1‖#3) → (#2 depends #1; #4 depends #1+#3) → #5。
- 破坏性改动 (#3 #4) merge 后下游 CI 短暂红是预期——不要慌，等链上一条 merge 即会修复。
- 本 plan 终点 = #5 merge + tag → Phase 2 还债清帐；memory 更新；Phase 3 可启。

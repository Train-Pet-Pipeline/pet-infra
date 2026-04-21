# Phase 3A Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 3A 破坏性重建 pet-train v2.0.0 + pet-eval v2.0.0 为 pet-infra 6 registries 下的 plugin；pet-infra v2.3.0 实装 `pet run` orchestrator（DAG + cache + resume + multirun）+ ClearML 三档 mode + PHASE_DOD_TEMPLATE；matrix 新增 2026.07 行。

**Architecture:** 三仓 PR 链按 rc 锚点串行：pet-infra v2.3.0-rc1 → pet-train v2.0.0-rc1 → pet-eval v2.0.0 (final) → pet-train v2.0.0 (final) → pet-infra v2.3.0 (final) + matrix 2026.07 finalize。plugin 全部走 mmengine-lite Registry + setuptools entry-points；ModelCard 为唯一跨 stage 载体（pet-schema v2.1.0 冻结，不动）；ClearML 默认 offline mode（本地 dev 零运维），release CI 强制 self_hosted/saas。

**Tech Stack:** Python 3.11 / mmengine-lite Registry / Hydra (+zen) / Pydantic v2 / pytest / ClearML 1.16.x / LLaMA-Factory (vendor submodule) / torch 2.3.x / transformers 4.45.x / GitHub Actions / bsdiff4 (暂不用) / DVC。

**Spec:** `pet-infra/docs/superpowers/specs/2026-04-21-phase-3a-training-design.md`（已通过两轮 review）

**North Star 约束（§0.2.1）：** 可插拔性 / 灵活性 / 可扩展性 / 可对比性 四维度各 ≥ 3 分，每 Phase 结尾按 PHASE_DOD_TEMPLATE §5 自检。

**硬约束：**
- feedback_refactor_no_legacy：破坏性，无兼容层，major bump
- feedback_pr_workflow：每仓 `feature/* → dev → main`
- feedback_env_naming：共享 `pet-pipeline` conda env
- 所有数值 params.yaml（CLAUDE.md）
- peer-dep §11：下游不 pin pet-infra；matrix 为唯一版本事实源

**仓库工作目录（每仓独立 git 仓库）：**
- pet-infra: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
- pet-train: `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train`
- pet-eval:  `/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval`

每 PR 流程：从 `dev` 切 `feature/*` → 开发 + 测试 → PR 目标分支 `dev` → merge 后在 dev 跑 CI → 阶段性提 `dev → main` 发布 PR → tag。

---

## 全局 PR 依赖图

```
Phase 0: pet-infra v2.3.0-rc1 (rc 锚点，解 matrix 循环)
    #P0-A  本 plan commit + spec commit PR (feature/phase-3a-training-design → dev)
    #P0-B  ExperimentLogger ABC + NullLogger
    #P0-C  ClearMLLogger (offline / saas / self_hosted)
    #P0-D  docker/clearml/ stack + make clearml-up/down
    #P0-E  pet run orchestrator (DAG + cache + resume)
    #P0-F  Hydra multirun launcher 限制
    #P0-G  PHASE_DOD_TEMPLATE.md + CLAUDE.md/DEVELOPMENT_GUIDE 指针
    #P0-H  matrix 2026.07-rc 行 + §11.4 装序文档更新
    ==> dev → main 发 v2.3.0-rc1

Phase 1: pet-train v2.0.0-rc1  (依赖 P0)
    #P1-A  审计 + 删 v1 (scripts/configs/kl_loss/schema_compliance_callback/audio_model)
    #P1-B  audio/ 命名空间 rename (audio_inference → audio/inference 等)
    #P1-C  plugin 骨架 + _register.py entry-point
    #P1-D  LlamaFactorySFTTrainer
    #P1-E  LlamaFactoryDPOTrainer
    #P1-F  TinyTestTrainer (CPU ~100K params)
    #P1-G  peer-dep §11 guard + CI 4 步装序
    ==> dev → main 发 v2.0.0-rc1

Phase 2: pet-eval v2.0.0 (final tag，依赖 P0 + P1)
    #P2-A  审计 + 删 wandb inline + runners CLI + eval_quantized
    #P2-B  8 metric 逐字迁移到 plugins/metrics/ + 回归 fixture
    #P2-C  VLMEvaluator plugin
    #P2-D  AudioEvaluator plugin (跨仓 import pet_train.audio.inference)
    #P2-E  peer-dep §11 guard + CI 4 步装序
    #P2-F  smoke recipes (tiny / mps / small) + release-smoke workflow
    ==> dev → main 发 v2.0.0 (final)

Phase 3: Finalize
    #P3-A  pet-train final tag v2.0.0 (代码不变，仅 tag)
    #P3-B  pet-infra matrix 2026.07 finalize (pet_train/eval WIP→2.0.0) + §11.4 doc
    #P3-C  pet-infra v2.3.0 final tag + DoD §0.2.1 自检 retrospective
```

---

## 跨 PR 前置检查（每 PR 起手 5 秒）

```bash
# 确认 conda env (feedback_env_naming)
conda env list | grep -q 'pet-pipeline' || { echo "需要 conda create -n pet-pipeline python=3.11"; exit 1; }
conda activate pet-pipeline

# 确认目标仓库
cd <repo-dir>
git status  # 必须干净
git checkout dev && git pull origin dev
```

---

# Phase 0: pet-infra v2.3.0-rc1

**仓库**：`/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra`
**所有 PR 目标分支**：`dev`
**最终 tag**：`v2.3.0-rc1`（merge 到 main 后打）

---

## PR #P0-A: 本 plan + spec 合并进 dev

**Branch:** `feature/phase-3a-training-design`（已 commit spec + round1/2 修订 + 本 plan）

### Task P0-A.1: commit 本 plan 到现有 feature 分支

**Files:**
- Create: `pet-infra/docs/superpowers/plans/2026-04-21-phase-3a-training-plan.md`（本文件）

- [ ] **Step 1: 检查分支状态**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git branch --show-current
# 预期: feature/phase-3a-training-design
```

- [ ] **Step 2: add + commit plan**

```bash
git add docs/superpowers/plans/2026-04-21-phase-3a-training-plan.md
git commit -m "docs(pet-infra): Phase 3A Training implementation plan"
```

- [ ] **Step 3: push + 开 PR**

```bash
git push -u origin feature/phase-3a-training-design
gh pr create --base dev --title "docs: Phase 3A Training design + implementation plan" \
  --body "Spec + plan。合并后 Phase 3A 所有后续 PR 从 dev 切 feature/* 分支实施。"
```

- [ ] **Step 4: 等 CI 绿，merge，然后开 dev→main PR 同步**

```bash
gh pr merge --squash <PR_ID>
gh pr create --base main --head dev --title "chore: sync dev → main (Phase 3A design)"
# merge
```

---

## PR #P0-B: ExperimentLogger ABC + NullLogger

**Branch:** `feature/experiment-logger-abc`（从 dev 切）

**Files:**
- Create: `src/pet_infra/experiment_logger/__init__.py`
- Create: `src/pet_infra/experiment_logger/base.py`
- Create: `src/pet_infra/experiment_logger/null_logger.py`
- Create: `src/pet_infra/experiment_logger/factory.py`
- Create: `tests/experiment_logger/test_null_logger.py`
- Create: `tests/experiment_logger/test_factory.py`
- Modify: `src/pet_infra/_register.py`（添加 experiment_logger 发现入口）
- Modify: `pyproject.toml`（新增 entry-point group `pet_infra.experiment_loggers`）

### Task P0-B.1: 写 ABC + NullLogger 失败测试

- [ ] **Step 1: 写 test_null_logger.py**

```python
# tests/experiment_logger/test_null_logger.py
import pytest
from datetime import datetime
from pet_schema.model_card import ModelCard
from pet_schema.enums import Modality
from pet_infra.experiment_logger import NullLogger, ExperimentLogger


def _card():
    return ModelCard(
        id="pet_test_train_abc12345",
        version="0.1.0",
        modality=Modality.VISION,
        task="sft",
        arch="qwen2vl_2b_lora_r16_a32",
        training_recipe="recipes/smoke_tiny.yaml",
        hydra_config_sha="x" * 40,
        git_shas={},
        dataset_versions={},
        checkpoint_uri="file:///tmp/adapter",
        metrics={},
        gate_status="pending",
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


def test_null_logger_is_experiment_logger():
    assert issubclass(NullLogger, ExperimentLogger)


def test_null_logger_start_returns_none():
    logger = NullLogger()
    task_id = logger.start(recipe=None, stage="train")
    assert task_id is None


def test_null_logger_all_methods_noop():
    logger = NullLogger()
    logger.start(recipe=None, stage="train")
    logger.log_metrics({"loss": 0.1}, step=1)
    logger.log_artifact("adapter", "file:///tmp/a")
    logger.log_model_card(_card())
    logger.finish("success")  # 不 raise
```

- [ ] **Step 2: 确认失败**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
pytest tests/experiment_logger/test_null_logger.py -v
# 预期：ModuleNotFoundError: pet_infra.experiment_logger
```

### Task P0-B.2: 实现 ABC

- [ ] **Step 1: 写 base.py**

```python
# src/pet_infra/experiment_logger/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Literal
from pet_schema.model_card import ModelCard


class ExperimentLogger(ABC):
    """Cross-stage experiment tracking ABC. Pluggable via entry-points."""

    @abstractmethod
    def start(self, recipe, stage: str) -> str | None:
        """Start a task. Returns task_id (None for loggers without identity)."""

    @abstractmethod
    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None: ...

    @abstractmethod
    def log_artifact(self, name: str, uri: str) -> None: ...

    @abstractmethod
    def log_model_card(self, card: ModelCard) -> None: ...

    @abstractmethod
    def finish(self, status: Literal["success", "failed"]) -> None: ...
```

- [ ] **Step 2: 写 null_logger.py**

```python
# src/pet_infra/experiment_logger/null_logger.py
from __future__ import annotations
from typing import Literal
from pet_schema.model_card import ModelCard
from .base import ExperimentLogger


class NullLogger(ExperimentLogger):
    """No-op logger for unit tests / scenarios requiring zero tracking."""

    def start(self, recipe, stage: str) -> None:
        return None

    def log_metrics(self, metrics, step=None) -> None:
        pass

    def log_artifact(self, name, uri) -> None:
        pass

    def log_model_card(self, card: ModelCard) -> None:
        pass

    def finish(self, status: Literal["success", "failed"]) -> None:
        pass
```

- [ ] **Step 3: __init__.py 导出**

```python
# src/pet_infra/experiment_logger/__init__.py
from .base import ExperimentLogger
from .null_logger import NullLogger
from .factory import build_experiment_logger

__all__ = ["ExperimentLogger", "NullLogger", "build_experiment_logger"]
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/experiment_logger/test_null_logger.py -v
# 预期：3 passed (factory 测试后面加)
```

### Task P0-B.3: factory + entry-point 发现

- [ ] **Step 1: 写 test_factory.py**

```python
# tests/experiment_logger/test_factory.py
from pet_infra.experiment_logger import build_experiment_logger, NullLogger


def test_factory_null():
    logger = build_experiment_logger({"name": "null"})
    assert isinstance(logger, NullLogger)


def test_factory_unknown_raises():
    import pytest
    with pytest.raises(KeyError, match="unknown experiment logger"):
        build_experiment_logger({"name": "mlflow_not_installed"})
```

- [ ] **Step 2: 写 factory.py（entry-point 加载）**

```python
# src/pet_infra/experiment_logger/factory.py
from __future__ import annotations
from importlib.metadata import entry_points
from typing import Any
from .base import ExperimentLogger
from .null_logger import NullLogger

_BUILTINS = {"null": NullLogger}


def build_experiment_logger(cfg: dict[str, Any]) -> ExperimentLogger:
    name = cfg.get("name", "null")
    if name in _BUILTINS:
        return _BUILTINS[name]()
    for ep in entry_points(group="pet_infra.experiment_loggers"):
        if ep.name == name:
            cls = ep.load()
            return cls(**{k: v for k, v in cfg.items() if k != "name"})
    raise KeyError(f"unknown experiment logger: {name}")
```

- [ ] **Step 3: pyproject.toml entry-point group 声明（给 ClearMLLogger 留位）**

```toml
# pyproject.toml 追加（在 [project.entry-points."pet_infra.plugins"] 同级）
[project.entry-points."pet_infra.experiment_loggers"]
# clearml = "pet_infra.experiment_logger.clearml_logger:ClearMLLogger"  # PR #P0-C 添加
```

- [ ] **Step 4: 测试 + commit**

```bash
pytest tests/experiment_logger/ -v
# 预期：5 passed

git add src/pet_infra/experiment_logger/ tests/experiment_logger/ pyproject.toml
git commit -m "feat(pet-infra): add ExperimentLogger ABC + NullLogger + factory"
```

### Task P0-B.4: 开 PR

- [ ] **Step 1: push + PR**

```bash
git push -u origin feature/experiment-logger-abc
gh pr create --base dev --title "feat: ExperimentLogger ABC + NullLogger + factory" \
  --body "Phase 3A spec §4.2。ClearMLLogger 在 #P0-C 接入。"
```

- [ ] **Step 2: CI 绿后 merge**

---

## PR #P0-C: ClearMLLogger（三档 mode）

**Branch:** `feature/clearml-logger`（从 dev 切，merge #P0-B 后）

**Files:**
- Create: `src/pet_infra/experiment_logger/clearml_logger.py`
- Create: `tests/experiment_logger/test_clearml_logger.py`
- Modify: `pyproject.toml`（entry-point + `clearml>=1.14,<2` dep）

### Task P0-C.1: 写失败测试（覆盖 3 档 mode + on_unavailable 3 策略）

- [ ] **Step 1: 写 test_clearml_logger.py**

```python
# tests/experiment_logger/test_clearml_logger.py
import pytest
from unittest.mock import patch, MagicMock
from pet_infra.experiment_logger.clearml_logger import ClearMLLogger
from pet_infra.experiment_logger import NullLogger


@pytest.fixture
def mock_clearml():
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        yield m


def test_offline_mode_calls_set_offline(mock_clearml):
    logger = ClearMLLogger(mode="offline")
    logger.start(recipe=None, stage="train")
    mock_clearml.set_offline.assert_called_once_with(True)
    mock_clearml.init.assert_called_once()


def test_saas_mode_uses_api_host(mock_clearml):
    logger = ClearMLLogger(mode="saas", api_host="https://api.clear.ml")
    logger.start(recipe=None, stage="train")
    mock_clearml.set_offline.assert_not_called()


def test_self_hosted_mode_uses_api_host(mock_clearml):
    logger = ClearMLLogger(mode="self_hosted", api_host="http://localhost:8008")
    logger.start(recipe=None, stage="train")


def test_on_unavailable_fallback_null_returns_null_logger():
    from pet_infra.experiment_logger.clearml_logger import _with_fallback
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = ConnectionError("unreachable")
        logger = _with_fallback(ClearMLLogger(mode="saas", on_unavailable="fallback_null"))
        task_id = logger.start(recipe=None, stage="train")
        assert task_id is None  # 已切 NullLogger


def test_on_unavailable_strict_raises():
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = ConnectionError("unreachable")
        logger = ClearMLLogger(mode="saas", on_unavailable="strict")
        with pytest.raises(ConnectionError):
            logger.start(recipe=None, stage="train")
```

- [ ] **Step 2: 确认失败**

```bash
pytest tests/experiment_logger/test_clearml_logger.py -v
# 预期：ModuleNotFoundError
```

### Task P0-C.2: 实现 ClearMLLogger

- [ ] **Step 1: 写 clearml_logger.py**（参考 spec §4.3）

```python
# src/pet_infra/experiment_logger/clearml_logger.py
from __future__ import annotations
import logging
from typing import Literal
from clearml import Task
from pet_schema.model_card import ModelCard
from .base import ExperimentLogger
from .null_logger import NullLogger

logger = logging.getLogger(__name__)

Mode = Literal["offline", "saas", "self_hosted"]
OnUnavailable = Literal["strict", "fallback_null", "retry"]


class ClearMLLogger(ExperimentLogger):
    def __init__(
        self,
        mode: Mode = "offline",
        api_host: str = "",
        on_unavailable: OnUnavailable = "strict",
        project: str = "pet-pipeline",
    ):
        self.mode = mode
        self.api_host = api_host
        self.on_unavailable = on_unavailable
        self.project = project
        self._task = None

    def start(self, recipe, stage: str) -> str | None:
        if self.mode == "offline":
            Task.set_offline(True)
        task_name = f"{getattr(recipe, 'id', 'unnamed')}_{stage}"
        try:
            self._task = Task.init(project_name=self.project, task_name=task_name)
            return str(self._task.id)
        except Exception as e:
            return self._handle_unavailable(e)

    def _handle_unavailable(self, e: Exception) -> str | None:
        if self.on_unavailable == "strict":
            raise
        if self.on_unavailable == "fallback_null":
            logger.warning("ClearML unavailable, falling back to NullLogger: %s", e)
            self._task = None
            return None
        if self.on_unavailable == "retry":
            # tenacity retry 实装见 Task P0-C.3
            raise NotImplementedError("retry strategy pending")

    def log_metrics(self, metrics, step=None) -> None:
        if not self._task:
            return
        for k, v in metrics.items():
            self._task.get_logger().report_scalar(title=k, series=k, value=v, iteration=step or 0)

    def log_artifact(self, name: str, uri: str) -> None:
        if not self._task:
            return
        self._task.upload_artifact(name=name, artifact_object=uri)

    def log_model_card(self, card: ModelCard) -> None:
        if not self._task:
            return
        self._task.connect_configuration(card.model_dump(mode="json"), name="model_card")

    def finish(self, status) -> None:
        if not self._task:
            return
        self._task.close()
        self._task = None


def _with_fallback(clearml_logger: ClearMLLogger) -> ExperimentLogger:
    """如 start 抛错且策略 fallback_null，返回 NullLogger 替身"""
    try:
        clearml_logger.start(recipe=None, stage="_probe")
    except Exception:
        return NullLogger() if clearml_logger.on_unavailable == "fallback_null" else clearml_logger
    return clearml_logger
```

- [ ] **Step 2: pyproject.toml entry-point + dep**

```toml
[project]
dependencies = [
    # ... existing ...
    "clearml>=1.14,<2.0",
]

[project.entry-points."pet_infra.experiment_loggers"]
clearml = "pet_infra.experiment_logger.clearml_logger:ClearMLLogger"
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/experiment_logger/test_clearml_logger.py -v
# 预期：5 passed
```

### Task P0-C.3: retry 策略 + commit

- [ ] **Step 1: 写 retry 测试**

```python
# 在 test_clearml_logger.py 追加
def test_on_unavailable_retry_3_times():
    from unittest.mock import patch
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = [ConnectionError(), ConnectionError(), MagicMock(id="abc")]
        logger = ClearMLLogger(mode="saas", on_unavailable="retry")
        task_id = logger.start(recipe=None, stage="train")
        assert task_id == "abc"
        assert m.init.call_count == 3
```

- [ ] **Step 2: 用 tenacity 实装 retry**

```python
# 在 _handle_unavailable 中替换 NotImplementedError
if self.on_unavailable == "retry":
    from tenacity import retry, stop_after_attempt, wait_exponential
    # 在 start() 内部用 decorator 包 Task.init 重试 3 次 1s/4s/16s
    # 简化：raise with guidance
    ...
```

实际实现：重构 `start()` 把 `Task.init` 提成内部方法，用 `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=16), reraise=True)` 装饰。失败后按 strict 处理。

- [ ] **Step 3: commit + push + PR**

```bash
git add src/pet_infra/experiment_logger/clearml_logger.py tests/experiment_logger/test_clearml_logger.py pyproject.toml
git commit -m "feat(pet-infra): ClearMLLogger with 3-mode support (offline/saas/self_hosted)"
git push -u origin feature/clearml-logger
gh pr create --base dev --title "feat: ClearMLLogger 三档 mode + on_unavailable 三策略" \
  --body "Phase 3A spec §4.3。offline 模式默认不依赖 server。"
```

---

## PR #P0-D: ClearML docker-compose stack

**Branch:** `feature/clearml-docker-stack`（从 dev 切）

**Files:**
- Create: `docker/clearml/docker-compose.yml`
- Create: `docker/clearml/.env.example`
- Create: `docker/clearml/README.md`
- Modify: `Makefile`（加 `clearml-up` / `clearml-down`）
- Delete: `docker/wandb/`（整目录删除）

### Task P0-D.1: 写 docker-compose

- [ ] **Step 1: `docker/clearml/docker-compose.yml`**（参考 ClearML 官方 self-hosted 文档 `https://clear.ml/docs/latest/docs/deploying_clearml/clearml_server_linux_mac`，端口用 spec §4.4 约定 8080/8008/8081）

```yaml
# docker/clearml/docker-compose.yml
version: "3.8"
services:
  apiserver:
    image: allegroai/clearml:latest
    ports: ["8008:8008"]
    environment:
      CLEARML_ELASTIC_SERVICE_HOST: elasticsearch
      CLEARML_MONGODB_SERVICE_HOST: mongo
      CLEARML_REDIS_SERVICE_HOST: redis
    depends_on: [elasticsearch, mongo, redis]
    volumes: [clearml-data:/opt/clearml/data]

  webserver:
    image: allegroai/clearml:latest
    ports: ["8080:80"]
    depends_on: [apiserver]

  fileserver:
    image: allegroai/clearml:latest
    ports: ["8081:8081"]
    volumes: [clearml-files:/mnt/fileserver]

  mongo:
    image: mongo:4.4
    volumes: [mongo-data:/data/db]

  elasticsearch:
    image: elasticsearch:7.17
    environment: [discovery.type=single-node]
    volumes: [es-data:/usr/share/elasticsearch/data]

  redis:
    image: redis:6

volumes:
  clearml-data:
  clearml-files:
  mongo-data:
  es-data:
```

- [ ] **Step 2: `.env.example`**

```
CLEARML_API_HOST_URL=http://localhost:8008
CLEARML_API_ACCESS_KEY=<fill in after first webserver login>
CLEARML_API_SECRET_KEY=<fill in after first webserver login>
CLEARML_WEB_HOST=http://localhost:8080
CLEARML_FILES_HOST=http://localhost:8081
```

- [ ] **Step 3: README.md**（部署 + backup + 与 §11 peer-dep 关系）

简短指南：首次启动 → 浏览器 `:8080` 注册管理员 → 生成 API key → 填 `.env` → `clearml-init` 生成 `~/.clearml/clearml.conf`。

- [ ] **Step 4: Makefile**

```makefile
clearml-up:
	cd docker/clearml && docker-compose up -d

clearml-down:
	cd docker/clearml && docker-compose down
```

- [ ] **Step 5: 删 docker/wandb/**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git rm -r docker/wandb/
```

- [ ] **Step 6: commit + PR**

```bash
git add docker/clearml/ Makefile
git commit -m "feat(pet-infra): ClearML self-hosted docker stack; remove docker/wandb"
git push -u origin feature/clearml-docker-stack
gh pr create --base dev --title "feat: docker/clearml stack + Makefile up/down; delete wandb" \
  --body "Phase 3A spec §4.4。本地 dev 推荐 offline mode，不必起这套 stack。"
```

---

## PR #P0-E: pet run orchestrator (DAG + cache + resume)

**Branch:** `feature/pet-run-orchestrator`（从 dev 切，依赖 #P0-B）

**Files:**
- Create: `src/pet_infra/orchestrator/__init__.py`
- Create: `src/pet_infra/orchestrator/runner.py`
- Create: `src/pet_infra/orchestrator/dag.py`
- Create: `src/pet_infra/orchestrator/cache.py`
- Create: `src/pet_infra/orchestrator/stage_executor.py`
- Create: `src/pet_infra/orchestrator/hash.py`
- Create: `tests/orchestrator/test_dag.py`
- Create: `tests/orchestrator/test_cache.py`
- Create: `tests/orchestrator/test_hash.py`
- Create: `tests/orchestrator/test_runner_resume.py`
- Create: `tests/orchestrator/test_runner_gate_failed.py`
- Modify: `src/pet_infra/cli.py`（`pet run` 从 placeholder 改为真实现）

### Task P0-E.1: DAG 拓扑排序

- [ ] **Step 1: 写 test_dag.py**

```python
# tests/orchestrator/test_dag.py
import pytest
from pet_infra.orchestrator.dag import build_dag, DAGCycleError


def _stage(name, depends_on=()):
    class S: pass
    s = S(); s.name = name; s.depends_on = list(depends_on); return s


def test_linear_order():
    dag = build_dag([_stage("train"), _stage("eval", ["train"])])
    assert [s.name for s in dag.topological_order()] == ["train", "eval"]


def test_diamond_order():
    stages = [
        _stage("a"),
        _stage("b", ["a"]),
        _stage("c", ["a"]),
        _stage("d", ["b", "c"]),
    ]
    order = [s.name for s in build_dag(stages).topological_order()]
    assert order.index("a") < order.index("b") < order.index("d")
    assert order.index("a") < order.index("c") < order.index("d")


def test_cycle_raises():
    with pytest.raises(DAGCycleError):
        build_dag([_stage("a", ["b"]), _stage("b", ["a"])])


def test_missing_dep_raises():
    with pytest.raises(KeyError, match="ghost"):
        build_dag([_stage("a", ["ghost"])])
```

- [ ] **Step 2: 写 dag.py**

```python
# src/pet_infra/orchestrator/dag.py
from __future__ import annotations
from dataclasses import dataclass, field


class DAGCycleError(ValueError):
    pass


@dataclass
class DAG:
    stages: list
    _order: list = field(default_factory=list)

    def topological_order(self) -> list:
        return self._order


def build_dag(stages: list) -> DAG:
    by_name = {s.name: s for s in stages}
    for s in stages:
        for d in getattr(s, "depends_on", []):
            if d not in by_name:
                raise KeyError(f"stage {s.name!r} depends on unknown {d!r}")
    order, visiting, visited = [], set(), set()

    def visit(n: str):
        if n in visited: return
        if n in visiting: raise DAGCycleError(f"cycle at {n}")
        visiting.add(n)
        for d in getattr(by_name[n], "depends_on", []):
            visit(d)
        visiting.remove(n); visited.add(n); order.append(by_name[n])

    for s in stages:
        visit(s.name)
    return DAG(stages=stages, _order=order)
```

- [ ] **Step 3: 测试 + commit（分 commit，task 内部不合并）**

```bash
pytest tests/orchestrator/test_dag.py -v
# 预期：4 passed

git add src/pet_infra/orchestrator/__init__.py src/pet_infra/orchestrator/dag.py tests/orchestrator/test_dag.py
git commit -m "feat(pet-infra): orchestrator DAG + topological sort + cycle detection"
```

### Task P0-E.2: config hash 稳定性

- [ ] **Step 1: test_hash.py**

```python
# tests/orchestrator/test_hash.py
from types import SimpleNamespace
from pet_infra.orchestrator.hash import hash_stage_config


def test_canonical_json_key_order_insensitive():
    a = SimpleNamespace(config={"lr": 1e-4, "batch": 4})
    b = SimpleNamespace(config={"batch": 4, "lr": 1e-4})
    assert hash_stage_config(a, None) == hash_stage_config(b, None)


def test_override_changes_hash():
    a = SimpleNamespace(config={"lr": 1e-4})
    b = SimpleNamespace(config={"lr": 3e-4})
    assert hash_stage_config(a, None) != hash_stage_config(b, None)


def test_prev_card_uri_in_hash():
    stage = SimpleNamespace(config={"lr": 1e-4})
    c1 = SimpleNamespace(checkpoint_uri="file:///a")
    c2 = SimpleNamespace(checkpoint_uri="file:///b")
    assert hash_stage_config(stage, c1) != hash_stage_config(stage, c2)
```

- [ ] **Step 2: hash.py**（§5.2 rule 4）

```python
# src/pet_infra/orchestrator/hash.py
from __future__ import annotations
import hashlib, json


def hash_stage_config(stage, prev_card) -> str:
    payload = json.dumps(stage.config, sort_keys=True, separators=(",", ":"))
    payload += (prev_card.checkpoint_uri if prev_card else "")
    return hashlib.sha256(payload.encode()).hexdigest()
```

- [ ] **Step 3: 测试 + commit**

```bash
pytest tests/orchestrator/test_hash.py -v
git add src/pet_infra/orchestrator/hash.py tests/orchestrator/test_hash.py
git commit -m "feat(pet-infra): stable canonical_json hash for cache_key"
```

### Task P0-E.3: Cache 读写 + 损坏处理

- [ ] **Step 1: test_cache.py**

```python
# tests/orchestrator/test_cache.py
import pytest, tempfile, json
from pathlib import Path
from pet_infra.orchestrator.cache import StageCache


def test_save_load_roundtrip(tmp_path):
    cache = StageCache(root=tmp_path)
    assert not cache.has("k1")
    cache.save("k1", {"id": "k1", "metrics": {"loss": 0.1}})
    assert cache.has("k1")
    assert cache.load("k1")["metrics"]["loss"] == 0.1


def test_corrupt_treated_as_miss(tmp_path, caplog):
    cache = StageCache(root=tmp_path)
    (tmp_path / "k1.json").write_text("{invalid")
    assert cache.has("k1") is True  # 文件存在
    cache.load("k1")  # 返回 None 或 raise？
    # 契约：按 miss 处理
    assert "cache corrupt" in caplog.text.lower()
```

- [ ] **Step 2: cache.py**

```python
# src/pet_infra/orchestrator/cache.py
from __future__ import annotations
import json, logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StageCache:
    def __init__(self, root: Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def has(self, key: str) -> bool:
        return self._path(key).exists()

    def load(self, key: str):
        try:
            return json.loads(self._path(key).read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("cache corrupt for %s, treating as miss: %s", key, e)
            return None

    def save(self, key: str, card_dict: dict) -> None:
        self._path(key).write_text(json.dumps(card_dict, sort_keys=True))
```

- [ ] **Step 3: 测试 + commit**

```bash
pytest tests/orchestrator/test_cache.py -v
git add src/pet_infra/orchestrator/cache.py tests/orchestrator/test_cache.py
git commit -m "feat(pet-infra): StageCache with corrupt-as-miss handling"
```

### Task P0-E.4: runner 串联 + resume

- [ ] **Step 1: test_runner_resume.py**（集成测试，用 in-memory 假 plugin）

```python
# tests/orchestrator/test_runner_resume.py
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from pet_schema.model_card import ModelCard
from pet_schema.enums import Modality
from pet_infra.registries import TRAINERS, EVALUATORS
from pet_infra.orchestrator.runner import pet_run


CALL_LOG: list[str] = []


def _make_card(card_id: str, task: str) -> ModelCard:
    return ModelCard(
        id=card_id,  # orchestrator 写回；plugin 也必须写
        version="0.1.0",
        modality=Modality.VISION,
        task=task,
        arch="fake",
        training_recipe="r",
        hydra_config_sha="s" * 40,
        git_shas={},
        dataset_versions={},
        checkpoint_uri=f"file:///tmp/{task}",
        metrics={"loss": 0.1},
        gate_status="pending",
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


@TRAINERS.register_module(name="fake_sft", force=True)
class FakeSFTTrainer:
    def __init__(self, **cfg): self.cfg = cfg
    def run(self, input_card, recipe):
        CALL_LOG.append("train")
        # card.id 由 stage_executor 写回，这里先填 placeholder
        return _make_card(card_id="PLACEHOLDER", task="sft")


@EVALUATORS.register_module(name="fake_eval", force=True)
class FakeEvaluator:
    def __init__(self, **cfg): self.cfg = cfg
    def run(self, input_card, recipe):
        CALL_LOG.append("eval")
        return _make_card(card_id="PLACEHOLDER", task="eval")


@pytest.fixture(autouse=True)
def _reset_log():
    CALL_LOG.clear()
    yield
    CALL_LOG.clear()


def _write_recipe(tmp_path: Path) -> Path:
    recipe = {
        "id": "test_resume",
        "stages": [
            {"name": "train", "kind": "train", "plugin_name": "fake_sft", "config": {"lr": 1e-4}},
            {"name": "eval",  "kind": "eval",  "plugin_name": "fake_eval", "config": {"suite": "tiny"}},
        ],
        "experiment_logger": {"type": "null"},
    }
    p = tmp_path / "recipe.yaml"
    p.write_text(yaml.safe_dump(recipe))
    return p


def test_resume_skips_cached_stage(tmp_path):
    recipe = _write_recipe(tmp_path)
    cache_root = tmp_path / "cache"

    # 1st run：train + eval 都跑
    card1 = pet_run(recipe, resume=True, cache_root=cache_root)
    assert CALL_LOG == ["train", "eval"]

    # 2nd run：两个 stage 全部 cache hit，plugin 一次都不调用
    CALL_LOG.clear()
    card2 = pet_run(recipe, resume=True, cache_root=cache_root)
    assert CALL_LOG == []
    assert card2.id == card1.id  # 确定性 card_id


def test_no_resume_reruns_all(tmp_path):
    recipe = _write_recipe(tmp_path)
    cache_root = tmp_path / "cache"
    pet_run(recipe, resume=True, cache_root=cache_root)
    CALL_LOG.clear()
    pet_run(recipe, resume=False, cache_root=cache_root)
    assert CALL_LOG == ["train", "eval"]
```

- [ ] **Step 2: 写 runner.py**（直接照录 spec §4.5 算法；不要临时发明分支）

```python
# src/pet_infra/orchestrator/runner.py
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from pet_schema.experiment_recipe import ExperimentRecipe
from pet_schema.model_card import ModelCard
from pet_infra.experiment_logger import build_experiment_logger
from pet_infra.recipe.card_id import precompute_card_id
from .dag import build_dag
from .cache import StageCache
from .hash import hash_stage_config
from .stage_executor import execute_stage

log = logging.getLogger(__name__)


def pet_run(
    recipe_path: Path,
    resume: bool = True,
    cache_root: Optional[Path] = None,
) -> ModelCard:
    """Execute a recipe's stage DAG serially with resume-from-cache.

    Returns the last stage's ModelCard. Raises on any stage failure.
    """
    # 1. Hydra compose → ExperimentRecipe
    recipe_path = Path(recipe_path).resolve()
    with initialize_config_dir(version_base=None, config_dir=str(recipe_path.parent)):
        cfg = compose(config_name=recipe_path.stem)
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    recipe = ExperimentRecipe.model_validate(cfg_dict)

    # 2. Logger (from cfg.experiment_logger → ClearMLLogger/NullLogger)
    logger = build_experiment_logger(cfg_dict.get("experiment_logger", {"type": "null"}))

    # 3. DAG + cache
    dag = build_dag(recipe.stages)
    cache = StageCache(root=cache_root or Path.home() / ".pet-cache")

    # 4. Walk DAG; for each stage:
    #    config_sha = hash_stage_config(stage.config, prev_card)
    #    card_id = precompute_card_id(recipe.id, stage.name, config_sha)
    #    if resume and cache.has(card_id): load + continue
    #    else: run plugin, assert card.id == card_id, log, save
    prev_card: Optional[ModelCard] = None
    last_card: Optional[ModelCard] = None
    for stage in dag.topological_order():
        config_sha = hash_stage_config(stage.config, prev_card)
        card_id = precompute_card_id(recipe.id, stage.name, config_sha)

        if resume and cache.has(card_id):
            log.info("cache hit: %s", card_id)
            prev_card = cache.load(card_id)
            last_card = prev_card
            continue

        task_id = logger.start(recipe, stage.name)
        try:
            card = execute_stage(stage, recipe, prev_card, card_id)
            assert card.id == card_id, (
                f"plugin {stage.plugin_name} must write card_id back to ModelCard.id "
                f"(got {card.id!r}, expected {card_id!r})"
            )
        except Exception:
            logger.finish("failed")
            raise

        card.clearml_task_id = task_id
        logger.log_model_card(card)
        cache.save(card_id, card)
        logger.finish("success")
        prev_card = card
        last_card = card

    assert last_card is not None, "recipe has no stages"
    return last_card
```

Note：
- `execute_stage` 内部在 card 返回后必须写 `card.id = card_id`（已在 P0-E.4 Step 3 里 stage_executor.py 定义）
- Gate failed 短路在 P0-E.5 加，本 step 不处理 gate
- `hash_stage_config` 来自 P0-E.2 `hash.py`

- [ ] **Step 3: stage_executor.py**

```python
# src/pet_infra/orchestrator/stage_executor.py
from pet_infra.registries import TRAINERS, EVALUATORS, CONVERTERS

STAGE_REGISTRIES = {"train": TRAINERS, "eval": EVALUATORS, "convert": CONVERTERS}


def execute_stage(stage, recipe, prev_card, card_id):
    registry = STAGE_REGISTRIES[stage.kind]
    plugin = registry.build({"type": stage.plugin_name, **stage.config})
    card = plugin.run(input_card=prev_card, recipe=recipe)
    card.id = card_id  # 契约：orchestrator 写回 id
    return card
```

- [ ] **Step 4: CLI 接入**

```python
# src/pet_infra/cli.py 内 pet run 从 placeholder 改为：
from pet_infra.orchestrator.runner import pet_run

@cli.command("run")
@click.argument("recipe_path", type=click.Path(exists=True))
@click.option("--no-resume", is_flag=True)
@click.option("-m", "--multirun", is_flag=True, hidden=True)  # delegate to Hydra
def run_cmd(recipe_path, no_resume, multirun):
    pet_run(Path(recipe_path), resume=not no_resume)
```

- [ ] **Step 5: 测试 + commit**

```bash
pytest tests/orchestrator/ -v
# 预期：10+ passed

git add src/pet_infra/orchestrator/ src/pet_infra/cli.py tests/orchestrator/
git commit -m "feat(pet-infra): pet run orchestrator (in-process serial DAG + resume + cache)"
```

### Task P0-E.5: Gate failed + 短路 integration test

- [ ] **Step 1: test_runner_gate_failed.py**

```python
# tests/orchestrator/test_runner_gate_failed.py
def test_gate_failed_short_circuits_downstream(tmp_path):
    # 构造 recipe: train → eval → quantize
    # eval plugin 返回 gate.passed=False
    # 断言：GateFailedError raised；quantize 未调用；eval card 入 cache 且 gate_status="failed"
    ...
```

- [ ] **Step 2: runner.py 加 GateFailedError + 短路逻辑**

```python
class GateFailedError(RuntimeError):
    pass

# 在 runner.py 内 evaluator 返回 (metrics, gate) 后：
# if not gate.passed: raise GateFailedError(...)
# orchestrator 在 stage 循环里 catch → break → 报告
```

- [ ] **Step 3: 测试 + commit + push + PR**

```bash
pytest tests/orchestrator/test_runner_gate_failed.py -v
git add ...
git commit -m "feat(pet-infra): gate failed short-circuit + GateFailedError"

git push -u origin feature/pet-run-orchestrator
gh pr create --base dev --title "feat: pet run orchestrator (DAG + cache + resume + gate short-circuit)" \
  --body "Phase 3A spec §4.5-§4.6 + §5.2 规则 4 + §6.5。"
```

---

## PR #P0-F: Hydra multirun launcher 限制

**Branch:** `feature/multirun-launcher-guard`（从 dev 切，依赖 #P0-E）

**Files:**
- Modify: `src/pet_infra/cli.py`（`-m` 时检测 `hydra/launcher`）
- Create: `tests/orchestrator/test_multirun.py`

### Task P0-F.1: 测试 + 限制

- [ ] **Step 1: test_multirun.py**

```python
def test_basic_launcher_allowed():
    # pet run recipe.yaml -m train.lr=1e-4,3e-4 → 2 trial，串行
    ...


def test_joblib_launcher_rejected():
    # pet run recipe.yaml -m ... hydra/launcher=joblib
    # 预期：raise with "parallel launchers deferred to future version"
    ...
```

- [ ] **Step 2: cli.py 内加 guard**

```python
# 在 run_cmd 进入前，如果 Hydra cfg 包含 hydra.launcher.name != "basic"，raise
```

- [ ] **Step 3: commit + PR**

---

## PR #P0-G: PHASE_DOD_TEMPLATE + 文档指针

**Branch:** `feature/phase-dod-template`（从 dev 切）

**Files:**
- Create: `docs/PHASE_DOD_TEMPLATE.md`
- Modify: `/Users/bamboo/Githubs/Train-Pet-Pipeline/CLAUDE.md`（加指针）
- Modify: `docs/DEVELOPMENT_GUIDE.md §8`（加指针）

### Task P0-G.1: 写 template

- [ ] **Step 1: PHASE_DOD_TEMPLATE.md**（照 spec §4.7 原文 copy）

- [ ] **Step 2: CLAUDE.md 追加**

```
## Phase DoD

任何 Phase/子 Phase 结束前按 `pet-infra/docs/PHASE_DOD_TEMPLATE.md` 逐项自检。
North Star §0.2.1 四维度各 ≥ 3 分（<3 rework）。
```

- [ ] **Step 3: DEVELOPMENT_GUIDE.md §8 追加同样指针**

- [ ] **Step 4: commit + PR**

```bash
git add docs/PHASE_DOD_TEMPLATE.md docs/DEVELOPMENT_GUIDE.md
cd .. && git add Train-Pet-Pipeline/CLAUDE.md  # 注意 CLAUDE.md 是主目录级别，不是 pet-infra 内
# 修正：CLAUDE.md 在主目录（不是 git repo），直接 edit 即可，不 commit
# pet-infra 这边只 commit template + DEVELOPMENT_GUIDE
git commit -m "docs(pet-infra): PHASE_DOD_TEMPLATE v1 (DEBT-4) + §8 指针"
git push -u origin feature/phase-dod-template
gh pr create --base dev --title "docs: PHASE_DOD_TEMPLATE v1 + DEBT-4 落地"
```

> 注：`/Users/bamboo/Githubs/Train-Pet-Pipeline/CLAUDE.md` 在主目录（非 git 仓库），直接 edit 保存即可，不走 PR。

---

## PR #P0-H: matrix 2026.07-rc + §11.4 文档 + rc tag

**Branch:** `feature/matrix-2026-07-rc`（从 dev 切，P0 所有前序 merge 后）

**Files:**
- Modify: `docs/compatibility_matrix.yaml`（追加 2026.07-rc 行）
- Modify: `docs/DEVELOPMENT_GUIDE.md §11.4`（四步装序加 ClearML secret 注入样例 + 跨仓 import 子节）

### Task P0-H.1: matrix 行

- [ ] **Step 1: `compatibility_matrix.yaml` 追加**

```yaml
  - release: "2026.07-rc"
    pet_schema: "2.1.0"
    pet_infra: "2.3.0-rc1"
    pet_data: "1.2.0"
    pet_annotation: "2.0.0"
    # Phase 3A 进行中，pet_train/eval 用 rc 代表"与 rc1 matrix 接口一致"
    pet_train: "2.0.0-rc1"   # 将在 Phase 1 落地
    pet_eval: "2.0.0-rc1"    # 将在 Phase 2 落地
    pet_quantize: "0.1.0"
    pet_ota: "0.1.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
```

- [ ] **Step 2: DEVELOPMENT_GUIDE §11.4 加 ClearML 注入样例 + §11 新增跨仓 import 子节**（spec §4.8 + §5.3 样板）

- [ ] **Step 3: commit + PR + merge + tag**

```bash
git add docs/compatibility_matrix.yaml docs/DEVELOPMENT_GUIDE.md
git commit -m "chore(pet-infra): matrix 2026.07-rc + §11.4 ClearML 注入 + §11 跨仓 import 子节"
git push -u origin feature/matrix-2026-07-rc
gh pr create --base dev --title "chore: matrix 2026.07-rc + §11 文档收尾"
# merge → dev
# dev → main PR
# tag:
git checkout main && git pull
git tag -a v2.3.0-rc1 -m "Phase 3A rc1: orchestrator + ClearML + DoD template"
git push origin v2.3.0-rc1
gh release create v2.3.0-rc1 --prerelease --title "v2.3.0-rc1 Phase 3A kickoff" --notes "DAG + cache + ClearML 3 modes + DEBT-4 template"
```

**🎯 Phase 0 DoD**：pet-infra v2.3.0-rc1 tag 已发；所有 P0-A→P0-H merge；matrix 2026.07-rc 行在 dev+main。

---

# Phase 1: pet-train v2.0.0-rc1

**仓库**：`/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train`
**前置**：pet-infra v2.3.0-rc1 tag 已发
**最终 tag**：`v2.0.0-rc1`

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train
git checkout dev && git pull origin dev
```

---

## PR #P1-A: 审计 + 删 v1

**Branch:** `feature/phase-3a-delete-v1`

### Task P1-A.1: audit commit

**Files:**
- Create: `docs/phase-3a-audit.md`（`git ls-files` 输出 + 删/留/移分类）

- [ ] **Step 1: 跑 ls-files 并分类**

```bash
git ls-files > /tmp/ls.txt
# 按 spec §2.1/§2.2 分类
```

- [ ] **Step 2: 写 audit.md**（附 PR，作为后续删除的依据）

```bash
git checkout -b feature/phase-3a-delete-v1
git add docs/phase-3a-audit.md
git commit -m "docs(pet-train): Phase 3A v1 audit (delete/keep/move classification)"
```

### Task P1-A.2: 删 scripts/ 全目录

- [ ] **Step 1:**

```bash
git rm scripts/train_sft.sh scripts/train_dpo.sh scripts/train_audio.sh \
  scripts/collect_logits.sh scripts/merge_lora.sh scripts/eval_after_train.sh
git rm -rf scripts/  # 如果其他 .sh 也在
git commit -m "refactor(pet-train): delete v1 shell scripts"
```

### Task P1-A.3: 删 configs/ 全目录

```bash
git rm -r configs/
git commit -m "refactor(pet-train): delete v1 configs (migrated to params.yaml + Hydra defaults)"
```

### Task P1-A.4: 删 v1 源码

```bash
git rm src/pet_train/kl_loss.py
git rm -r src/pet_train/logits_provider/
git rm src/pet_train/schema_compliance_callback.py
git rm src/pet_train/audio_model.py
# 可能还有配套测试：
git rm tests/test_kl_loss.py tests/test_logits_provider.py tests/test_schema_compliance.py 2>/dev/null
git commit -m "refactor(pet-train): delete v1 kl_loss / logits_provider / schema_compliance_callback / audio_model CLI"
```

### Task P1-A.5: 删 wandb + 旧 CLI

```bash
# pyproject.toml 删 wandb 依赖；删 [project.scripts] 里 pet-train 入口
# 用 python -c 或手动 edit
git add pyproject.toml
git commit -m "refactor(pet-train): remove wandb dep + old CLI entry_points"
```

### Task P1-A.6: PR

```bash
git push -u origin feature/phase-3a-delete-v1
gh pr create --base dev --title "refactor: Phase 3A v1 purge (scripts/configs/kl_loss/wandb/old CLI)" \
  --body "Phase 3A spec §2.1。保留 vendor/LLaMA-Factory + audio_* 待 rename。"
```

---

## PR #P1-B: audio/ 命名空间 rename

**Branch:** `feature/audio-namespace-rename`（从 dev 切，#P1-A merge 后）

**Files:**
- Move: `src/pet_train/audio_inference.py` → `src/pet_train/audio/inference.py`
- Move: `src/pet_train/audio_model_arch.py` → `src/pet_train/audio/arch.py`
- Move: `src/pet_train/audio_transforms.py` → `src/pet_train/audio/transforms.py`
- Create: `src/pet_train/audio/__init__.py`
- Update: 对应测试 import 路径

### Task P1-B.1: git mv

```bash
mkdir -p src/pet_train/audio
git mv src/pet_train/audio_inference.py src/pet_train/audio/inference.py
git mv src/pet_train/audio_model_arch.py src/pet_train/audio/arch.py
git mv src/pet_train/audio_transforms.py src/pet_train/audio/transforms.py
touch src/pet_train/audio/__init__.py
git add src/pet_train/audio/__init__.py
```

### Task P1-B.2: 修 import（批量 grep + sed）

```bash
grep -rl "pet_train.audio_inference" src/ tests/ | xargs sed -i '' 's/pet_train\.audio_inference/pet_train.audio.inference/g'
grep -rl "pet_train.audio_model_arch" src/ tests/ | xargs sed -i '' 's/pet_train\.audio_model_arch/pet_train.audio.arch/g'
grep -rl "pet_train.audio_transforms" src/ tests/ | xargs sed -i '' 's/pet_train\.audio_transforms/pet_train.audio.transforms/g'

# 同时 inference.py / arch.py 内部相互引用也要改
pytest tests/ -k audio -v  # 确认 import 跑得通
```

### Task P1-B.3: commit + PR

```bash
git add -A
git commit -m "refactor(pet-train): rename audio_* → audio/ namespace (for cross-repo import)"
git push -u origin feature/audio-namespace-rename
gh pr create --base dev --title "refactor: audio namespace rename" \
  --body "spec §2.2 + §5.3。pet-eval AudioEvaluator 将 import pet_train.audio.inference。"
```

---

## PR #P1-C: plugin 骨架 + _register entry-point

**Branch:** `feature/plugin-skeleton`（从 dev 切）

**Files:**
- Create: `src/pet_train/plugins/__init__.py`
- Create: `src/pet_train/plugins/_register.py`
- Create: `tests/plugins/test_register.py`
- Modify: `pyproject.toml`（entry-point `pet_infra.plugins: register_all = pet_train.plugins._register:register_all`）

### Task P1-C.1: peer-dep guard 测试

- [ ] **Step 1: test_register.py**

```python
# tests/plugins/test_register.py
def test_register_all_succeeds_with_peer_dep():
    from pet_train.plugins._register import register_all
    register_all()  # 不 raise


def test_register_all_fails_without_pet_infra(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pet_infra", None)
    import pytest
    with pytest.raises(RuntimeError, match="pet-infra"):
        from pet_train.plugins._register import register_all
        register_all()
```

- [ ] **Step 2: _register.py** (spec §2.6 guard 样板)

```python
# src/pet_train/plugins/_register.py
def register_all():
    try:
        import pet_infra  # peer-dep guard
    except ImportError as e:
        raise RuntimeError(
            "pet-train v2 requires pet-infra. Install via matrix row 2026.07."
        ) from e
    # Trainer plugin 注册（P1-D/E/F 填）
    from . import llamafactory_sft, llamafactory_dpo, tiny_test  # noqa: F401
```

- [ ] **Step 3: 骨架文件占位**

```bash
touch src/pet_train/plugins/llamafactory_sft.py
touch src/pet_train/plugins/llamafactory_dpo.py
touch src/pet_train/plugins/tiny_test.py
# 每个文件先写空 pass 或注册一个空类，避免 import 失败
```

- [ ] **Step 4: pyproject.toml entry-point + 删 pet-infra 硬 pin**

```toml
[project]
dependencies = [
    "pet-schema",   # 无 pin, matrix 管
    # pet-infra 删（peer-dep，由 matrix 决定）
    "torch>=2.3,<2.4",
    "transformers>=4.45,<4.46",
    # ...
]

[project.entry-points."pet_infra.plugins"]
register_all = "pet_train.plugins._register:register_all"
```

- [ ] **Step 5: 测试 + commit + PR**

---

## PR #P1-D: LlamaFactorySFTTrainer

**Branch:** `feature/llamafactory-sft-trainer`（从 dev 切，#P1-C merge 后）

**Files:**
- Rewrite: `src/pet_train/plugins/llamafactory_sft.py`（~300 LOC）
- Create: `tests/plugins/test_llamafactory_sft.py`

### Task P1-D.1: `_hydra_to_lf_args` 映射测试

- [ ] **Step 1: test_llamafactory_sft.py**

```python
from pet_train.plugins.llamafactory_sft import LlamaFactorySFTTrainer


def test_hydra_to_lf_args_maps_lora_params():
    cfg = {
        "lora_r": 16, "lora_alpha": 32, "lr": 1e-4,
        "batch_size": 4, "grad_accum": 4, "max_steps": 1000,
        "base_model": "Qwen/Qwen2-VL-2B-Instruct",
        "dataset": "pet_annotation.vision_annotations",
        "output_dir": "/tmp/run",
    }
    trainer = LlamaFactorySFTTrainer()
    trainer.build(cfg)
    args = trainer._lf_args
    assert args["lora_rank"] == 16
    assert args["lora_alpha"] == 32
    assert args["learning_rate"] == 1e-4
    assert args["per_device_train_batch_size"] == 4
    assert args["gradient_accumulation_steps"] == 4
    assert args["max_steps"] == 1000


def test_registers_to_trainers():
    from pet_infra.registries import TRAINERS
    assert "llamafactory_sft" in TRAINERS.module_dict
```

### Task P1-D.2: 实装

- [ ] **Step 1: llamafactory_sft.py**

```python
# src/pet_train/plugins/llamafactory_sft.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from pet_infra.registries import TRAINERS
from pet_schema.model_card import ModelCard
from pet_schema.enums import Modality


@TRAINERS.register_module(name="llamafactory_sft")
class LlamaFactorySFTTrainer:
    def __init__(self):
        self._lf_args = None
        self._adapter_uri = None

    def build(self, cfg: dict) -> None:
        self._lf_args = self._hydra_to_lf_args(cfg)
        self._output_dir = cfg["output_dir"]

    def _hydra_to_lf_args(self, cfg: dict) -> dict:
        return {
            "model_name_or_path": cfg["base_model"],
            "dataset": cfg["dataset"],
            "lora_rank": cfg["lora_r"],
            "lora_alpha": cfg["lora_alpha"],
            "learning_rate": cfg["lr"],
            "per_device_train_batch_size": cfg["batch_size"],
            "gradient_accumulation_steps": cfg["grad_accum"],
            "max_steps": cfg["max_steps"],
            "output_dir": cfg["output_dir"],
            "finetuning_type": "lora",
            "stage": "sft",
        }

    def run(self, input_card, recipe) -> ModelCard:
        from llamafactory.train.sft.workflow import run_sft
        run_sft(**self._lf_args)
        self._adapter_uri = f"file://{Path(self._output_dir).resolve()}/adapter"
        return ModelCard(
            id="REPLACED_BY_ORCHESTRATOR",
            version=recipe.version,
            modality=Modality.VISION,
            task="sft",
            arch=f"qwen2vl_2b_lora_r{self._lf_args['lora_rank']}_a{self._lf_args['lora_alpha']}",
            training_recipe=str(recipe.path) if hasattr(recipe, "path") else "",
            hydra_config_sha=recipe.config_sha,
            git_shas=recipe.git_shas,
            dataset_versions=recipe.dataset_versions,
            checkpoint_uri=self._adapter_uri,
            metrics={},
            gate_status="pending",
            trained_at=datetime.utcnow(),
            trained_by=recipe.trained_by,
        )
```

- [ ] **Step 2: plugin 在 _register 注册**（已在 P1-C import 写好）

- [ ] **Step 3: 测试 + commit + PR**

```bash
pytest tests/plugins/test_llamafactory_sft.py -v
git commit -m "feat(pet-train): LlamaFactorySFTTrainer plugin (thin-wrap run_sft)"
```

---

## PR #P1-E: LlamaFactoryDPOTrainer

**Branch:** `feature/llamafactory-dpo-trainer`（结构同 #P1-D）

复用 P1-D 结构。区别：
- `_register_module(name="llamafactory_dpo")`
- `stage="dpo"`, 加 `pref_beta`, `beta` 等 DPO 特有参数映射
- `task="dpo"`, `lineage_role="dpo_output"`, `parent_models=[input_card.id]`

测试同构。

---

## PR #P1-F: TinyTestTrainer (smoke_tiny 用)

**Branch:** `feature/tiny-test-trainer`（从 dev 切）

**Files:**
- Create: `src/pet_train/plugins/tiny_test.py`
- Create: `tests/plugins/test_tiny_test.py`

### Task P1-F.1: 构造小 transformer

- [ ] **Step 1: tiny_test.py**

```python
# src/pet_train/plugins/tiny_test.py
import torch, torch.nn as nn
from datetime import datetime
from pet_infra.registries import TRAINERS
from pet_schema.model_card import ModelCard
from pet_schema.enums import Modality


@TRAINERS.register_module(name="tiny_test")
class TinyTestTrainer:
    """~100K params transformer, CPU-only, smoke_tiny 专用（PR gate <2min）。"""

    def __init__(self):
        self.model = None

    def build(self, cfg: dict) -> None:
        self._output_dir = cfg.get("output_dir", "/tmp/tiny")
        self._steps = cfg.get("max_steps", 10)

    def run(self, input_card, recipe) -> ModelCard:
        self.model = nn.Sequential(
            nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, 64)
        )  # ~100K
        opt = torch.optim.SGD(self.model.parameters(), lr=1e-3)
        for _ in range(self._steps):
            x = torch.randn(4, 64)
            y = self.model(x).sum()
            y.backward(); opt.step(); opt.zero_grad()
        return ModelCard(
            id="REPLACED_BY_ORCHESTRATOR",
            version="0.0.0", modality=Modality.VISION, task="test",
            arch="tiny_test_transformer",
            training_recipe="smoke_tiny.yaml",
            hydra_config_sha="0"*40,
            git_shas={}, dataset_versions={},
            checkpoint_uri=f"file://{self._output_dir}",
            metrics={"train_loss": float(y.detach())},
            gate_status="pending",
            trained_at=datetime.utcnow(), trained_by="ci",
        )
```

- [ ] **Step 2: test + commit + PR**

---

## PR #P1-G: peer-dep CI 4 步装序 + rc tag

**Branch:** `feature/peer-dep-ci`（从 dev 切，所有 P1 前序 merge 后）

**Files:**
- Create: `.github/workflows/plugin-discovery.yml`（如果不存在）
- Create: `.github/workflows/peer-dep-smoke.yml`
- Modify: `.github/workflows/ci.yml`（加 lint + unit + integration）

### Task P1-G.1: peer-dep-smoke.yml

```yaml
# .github/workflows/peer-dep-smoke.yml
name: peer-dep-smoke
on: [pull_request]
jobs:
  install-order:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v2.3.0-rc1
      - run: pip install -e . --no-deps
      - run: pip install -e .[dev]
      - run: python -c "from pet_train.plugins._register import register_all; register_all()"
      - run: python -c "from pet_infra.registries import TRAINERS; assert 'llamafactory_sft' in TRAINERS.module_dict"
```

### Task P1-G.2: merge 链 + tag

```bash
# 所有 P1 PR 合入 dev → dev→main PR → merge
git checkout main && git pull
git tag -a v2.0.0-rc1 -m "Phase 3A pet-train rc1"
git push origin v2.0.0-rc1
gh release create v2.0.0-rc1 --prerelease
```

**🎯 Phase 1 DoD**：pet-train v2.0.0-rc1 tag；3 个 TRAINERS plugin 注册 + 测试绿；peer-dep-smoke CI 绿。

---

# Phase 2: pet-eval v2.0.0 (final)

**仓库**：`/Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval`
**前置**：pet-infra v2.3.0-rc1 + pet-train v2.0.0-rc1 tag 已发
**最终 tag**：`v2.0.0`（final，非 rc）

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval
git checkout dev && git pull origin dev
```

---

## PR #P2-A: 审计 + 删 v1

**Branch:** `feature/phase-3a-delete-v1`

### Task P2-A.1: audit + 删 wandb inline + 删 runners CLI

- [ ] **Step 1: audit**

```bash
git ls-files > /tmp/pet-eval-ls.txt
# 按 spec §3.1 分类
```

- [ ] **Step 2: 删旧 CLI 入口**

```bash
git rm src/pet_eval/cli.py src/pet_eval/__main__.py
git commit -m "refactor(pet-eval): delete v1 CLI (pet run takes over)"
```

- [ ] **Step 3: 删 runners（逻辑迁入 plugin 后再删）**

这步推迟到 #P2-C/D（避免中间状态不可跑）。本 PR 先标记 deprecated。

- [ ] **Step 4: 删 wandb inline**

```bash
# 手动 edit src/pet_eval/report/generate_report.py 移除 wandb 段
# pyproject.toml 删 wandb dep
git add src/pet_eval/report/generate_report.py pyproject.toml
git commit -m "refactor(pet-eval): remove wandb inline + dep (replaced by ClearMLLogger via orchestrator)"
```

- [ ] **Step 5: 删 eval_quantized.py（3B 重写）**

```bash
git rm src/pet_eval/runners/eval_quantized.py
git rm tests/runners/test_eval_quantized.py 2>/dev/null
git commit -m "refactor(pet-eval): delete eval_quantized runner (Phase 3B rebuild as QuantizedModelEvaluator plugin)"
```

- [ ] **Step 6: commit audit + PR**

```bash
git push -u origin feature/phase-3a-delete-v1
gh pr create --base dev --title "refactor: Phase 3A v1 purge (wandb inline + old CLI + eval_quantized)" \
  --body "spec §3.1。runners/eval_trained + eval_audio 保留直到 #P2-C/D 迁入 plugin。"
```

---

## PR #P2-B: 8 metric 迁移到 plugins/metrics/ + 回归 fixture

**Branch:** `feature/metrics-to-plugins`（从 dev 切，#P2-A merge 后）

**Files:**
- Move: `src/pet_eval/metrics/*.py` → `src/pet_eval/plugins/metrics/*.py`（8 个文件）
- Create: `src/pet_eval/plugins/__init__.py`
- Create: `src/pet_eval/plugins/_register.py`
- Create: `src/pet_eval/plugins/metrics/__init__.py`
- Create: `tests/plugins/test_v1_metric_backward_compat.py`（8 metric fixture 锁）

### Task P2-B.1: git mv + import 修

```bash
mkdir -p src/pet_eval/plugins/metrics
git mv src/pet_eval/metrics/anomaly_recall.py src/pet_eval/plugins/metrics/anomaly_recall.py
# ... 8 个文件
git mv src/pet_eval/metrics/types.py src/pet_eval/plugins/metrics/types.py
touch src/pet_eval/plugins/__init__.py src/pet_eval/plugins/metrics/__init__.py

grep -rl "pet_eval.metrics" src/ tests/ | xargs sed -i '' 's/pet_eval\.metrics/pet_eval.plugins.metrics/g'
```

### Task P2-B.2: 每个 metric 注册到 METRICS

- [ ] **Step 1: 改每个 metric 文件头加 @METRICS.register**（8 个，批量 edit）

```python
# 示例 anomaly_recall.py 顶部加：
from pet_infra.registries import METRICS

@METRICS.register_module(name="anomaly_recall")
class AnomalyRecallMetric:
    def __call__(self, predictions, references) -> float: ...
```

- [ ] **Step 2: _register.py**

```python
# src/pet_eval/plugins/_register.py
def register_all():
    try:
        import pet_infra
        import pet_train  # 跨仓 runtime guard（AudioEvaluator 要用）
    except ImportError as e:
        raise RuntimeError(
            "pet-eval requires pet-infra + pet-train runtime. Install via matrix 2026.07-rc."
        ) from e
    from .metrics import (anomaly_recall, calibration, kl_quantization,
                          latency, mood_correlation, narrative_quality,
                          schema_compliance, audio_accuracy)  # noqa: F401
    from . import vlm_evaluator, audio_evaluator  # noqa: F401（P2-C/D 填）
```

### Task P2-B.3: 回归 fixture 锁

- [ ] **Step 1: test_v1_metric_backward_compat.py**（每 metric 金标值）

```python
# tests/plugins/test_v1_metric_backward_compat.py
import pytest
from pet_infra.registries import METRICS


@pytest.mark.parametrize("metric_name,inputs,expected", [
    ("anomaly_recall", (...), 0.83),      # v1 测试产出
    ("calibration", (...), 0.07),
    ("kl_quantization", (...), 0.03),
    ("latency", (...), 1850.0),
    ("mood_correlation", (...), 0.72),
    ("narrative_quality", (...), 3.4),
    ("schema_compliance", (...), 0.98),
    ("audio_accuracy", (...), 0.68),
])
def test_metric_value_matches_v1(metric_name, inputs, expected):
    metric = METRICS.build({"type": metric_name})
    assert abs(metric(*inputs) - expected) < 1e-4
```

（实际 inputs 和 expected 从 v1 测试 / fixture 抽）

- [ ] **Step 2: commit + PR**

```bash
git add src/pet_eval/plugins/ tests/plugins/
git commit -m "feat(pet-eval): migrate 8 v1 metrics → plugins/metrics/ + backward-compat fixture lock"
git push -u origin feature/metrics-to-plugins
gh pr create --base dev --title "feat: 8 metric plugin 迁移 + 回归保护"
```

---

## PR #P2-C: VLMEvaluator plugin

**Branch:** `feature/vlm-evaluator`（从 dev 切，#P2-B merge 后）

**Files:**
- Create: `src/pet_eval/plugins/vlm_evaluator.py`
- Create: `src/pet_eval/plugins/gate.py`（GateResult + 阈值判断）
- Create: `tests/plugins/test_vlm_evaluator.py`
- Delete: `src/pet_eval/runners/eval_trained.py`（逻辑迁移完成后）

### Task P2-C.1: GateResult 契约

- [ ] **Step 1: gate.py**

```python
# src/pet_eval/plugins/gate.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class GateResult:
    passed: bool
    reason: str
    thresholds: dict[str, float]


def apply_gate(metrics: dict[str, float], thresholds: dict[str, float]) -> GateResult:
    failures = []
    for key, threshold in thresholds.items():
        if key.startswith("min_"):
            metric_name = key[4:]
            if metrics.get(metric_name, 0) < threshold:
                failures.append(f"{metric_name}={metrics.get(metric_name)} < {key}={threshold}")
        elif key.startswith("max_"):
            metric_name = key[4:]
            if metrics.get(metric_name, float("inf")) > threshold:
                failures.append(f"{metric_name}={metrics.get(metric_name)} > {key}={threshold}")
    return GateResult(
        passed=not failures,
        reason="; ".join(failures) if failures else "all thresholds met",
        thresholds=thresholds,
    )
```

- [ ] **Step 2: test_gate.py**

```python
def test_gate_all_pass():
    r = apply_gate({"narrative_quality": 4.0}, {"min_narrative_quality": 3.0})
    assert r.passed


def test_gate_min_fails():
    r = apply_gate({"narrative_quality": 2.5}, {"min_narrative_quality": 3.0})
    assert not r.passed
    assert "narrative_quality=2.5" in r.reason


def test_gate_max_fails():
    r = apply_gate({"calibration_ece": 0.15}, {"max_calibration_ece": 0.10})
    assert not r.passed
```

### Task P2-C.2: VLMEvaluator 实装

- [ ] **Step 1: vlm_evaluator.py**（复用 v1 `runners/eval_trained.py` 核心推理逻辑）

```python
# src/pet_eval/plugins/vlm_evaluator.py
from __future__ import annotations
from pet_infra.registries import EVALUATORS, METRICS
from pet_schema.model_card import ModelCard
from .gate import GateResult, apply_gate


@EVALUATORS.register_module(name="vlm_evaluator")
class VLMEvaluator:
    def __init__(self):
        self._metrics = []
        self._thresholds = {}

    def build(self, cfg: dict) -> None:
        self._metrics = [METRICS.build({"type": name}) for name in cfg["metrics"]]
        self._thresholds = cfg.get("thresholds", {})
        self._eval_dataset = cfg["eval_dataset"]

    def evaluate(self, model_card: ModelCard, recipe) -> tuple[dict[str, float], GateResult]:
        # 1. Load model from model_card.checkpoint_uri
        # 2. Iterate over eval_dataset samples
        # 3. Generate predictions
        # 4. Compute each metric
        # 5. Apply gate
        metrics_out = {}
        for m in self._metrics:
            metrics_out[m.name] = m(predictions=..., references=...)
        gate = apply_gate(metrics_out, self._thresholds)
        return metrics_out, gate

    # BaseEvaluator protocol: orchestrator 调 run(input_card, recipe)
    def run(self, input_card, recipe):
        metrics, gate = self.evaluate(input_card, recipe)
        input_card.metrics.update(metrics)
        input_card.gate_status = "passed" if gate.passed else "failed"
        if not gate.passed:
            from pet_infra.orchestrator.runner import GateFailedError
            raise GateFailedError(gate.reason)
        return input_card
```

- [ ] **Step 2: 删 runners/eval_trained.py**

```bash
git rm src/pet_eval/runners/eval_trained.py tests/runners/test_eval_trained.py
```

- [ ] **Step 3: test + commit + PR**

---

## PR #P2-D: AudioEvaluator plugin (跨仓 import)

**Branch:** `feature/audio-evaluator`（从 dev 切，#P2-C merge 后）

**Files:**
- Create: `src/pet_eval/plugins/audio_evaluator.py`
- Modify: `pyproject.toml`（加 `pet-train` 作为 runtime dep，无 pin）
- Create: `tests/plugins/test_audio_evaluator.py`
- Delete: `src/pet_eval/runners/eval_audio.py`

### Task P2-D.1: 跨仓 import 测试

- [ ] **Step 1: test_audio_evaluator.py**

```python
def test_import_from_pet_train():
    from pet_train.audio.inference import *  # 名字由 P1-B 锁
    assert True  # 能 import 即通过


def test_registers_to_evaluators():
    from pet_infra.registries import EVALUATORS
    assert "audio_evaluator" in EVALUATORS.module_dict


def test_evaluate_returns_metrics_and_gate(tmp_path):
    # 构造假 AudioClips dataset + 假 ModelCard
    # 调 evaluate → (metrics, gate)
    # 断言 "audio_accuracy" 在 metrics
    ...
```

### Task P2-D.2: 实装

- [ ] **Step 1: pyproject.toml**

```toml
[project]
dependencies = [
    "pet-schema",
    "pet-train",      # 跨仓 runtime, 无 pin (spec §5.3)
    "torch>=2.3,<2.4",
    "nltk",
    "rouge-score",
    "bert-score",
    # pet-infra 不列（§11 peer-dep）
]
```

- [ ] **Step 2: audio_evaluator.py**

```python
# src/pet_eval/plugins/audio_evaluator.py
from pet_infra.registries import EVALUATORS, METRICS
from pet_train.audio.inference import <ZeroShotClass>  # P1-B 锁定
from pet_schema.model_card import ModelCard
from .gate import apply_gate


@EVALUATORS.register_module(name="audio_evaluator")
class AudioEvaluator:
    def __init__(self):
        self._zero_shot = None

    def build(self, cfg: dict) -> None:
        self._zero_shot = <ZeroShotClass>()
        self._thresholds = cfg.get("thresholds", {})
        self._eval_dataset = cfg["eval_dataset"]

    def evaluate(self, model_card, recipe):
        # 遍历 AudioClips
        # 对每个 clip 调 zero_shot.predict
        # 汇总 top-1 accuracy
        metrics = {"audio_accuracy": 0.65}  # 占位
        gate = apply_gate(metrics, self._thresholds)
        return metrics, gate

    def run(self, input_card, recipe):
        metrics, gate = self.evaluate(input_card, recipe)
        input_card.metrics.update(metrics)
        input_card.gate_status = "passed" if gate.passed else "failed"
        if not gate.passed:
            from pet_infra.orchestrator.runner import GateFailedError
            raise GateFailedError(gate.reason)
        return input_card
```

- [ ] **Step 3: 删 runners/eval_audio.py**

- [ ] **Step 4: test + commit + PR**

---

## PR #P2-E: peer-dep guard + CI 4 步装序

**Branch:** `feature/peer-dep-ci`（从 dev 切）

同 #P1-G 结构，CI workflow 额外加一步 "pip install pet-train" 在 pet-infra 之后：

```yaml
# .github/workflows/peer-dep-smoke.yml
      - run: pip install git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v2.3.0-rc1
      - run: pip install git+https://github.com/Train-Pet-Pipeline/pet-train.git@v2.0.0-rc1
      - run: pip install -e . --no-deps
      - run: pip install -e .[dev]
      - run: python -c "from pet_eval.plugins._register import register_all; register_all()"
```

---

## PR #P2-F: smoke recipes + release-smoke workflow

**Branch:** `feature/smoke-recipes`（从 dev 切；注意：recipes 实际放 pet-infra 仓，不是 pet-eval）

> 本 PR 改 pet-infra！切到 pet-infra 仓操作。

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout dev && git pull
git checkout -b feature/smoke-recipes
```

**Files (pet-infra)：**
- Create: `recipes/smoke_base.yaml`
- Create: `recipes/smoke_tiny.yaml`
- Create: `recipes/smoke_mps.yaml`
- Create: `recipes/smoke_small.yaml`
- Create: `.github/workflows/release-smoke.yml`
- Modify: `.github/workflows/integration-smoke.yml`（加 smoke_tiny 端到端 PR gate）
- Modify: `.github/workflows/compatibility-matrix-smoke.yml`（2026.07-rc 行）
- Modify: `params.yaml`（增加 gate/smoke 命名空间）
- Modify: `Makefile`（加 `smoke-mps` target）

### Task P2-F.1: params.yaml 新增 gate/smoke keys

- [ ] **Step 1: params.yaml**（spec §3.8 copy）

```yaml
# 追加
eval:
  batch_size: 8
  max_samples: 500

gate:
  min_anomaly_recall: 0.80
  max_calibration_ece: 0.10
  max_kl_quantization: 0.05
  max_latency_ms_p95: 2000
  min_mood_correlation: 0.60
  min_narrative_quality: 3.0
  min_schema_compliance: 0.95
  min_audio_accuracy: 0.60

smoke:
  min_anomaly_recall: 0.0
  max_calibration_ece: 1.0
  max_kl_quantization: 1.0
  max_latency_ms_p95: 999999
  min_mood_correlation: 0.0
  min_narrative_quality: 0.0
  min_schema_compliance: 0.0
  min_audio_accuracy: 0.0
```

### Task P2-F.2: smoke_base + 三档

- [ ] **Step 1: smoke_base.yaml**（共享 defaults）

```yaml
# recipes/smoke_base.yaml
id: smoke
stages:
  - name: train
    kind: train
    plugin_name: tiny_test
    depends_on: []
    config:
      output_dir: /tmp/smoke
      max_steps: ${oc.select:smoke.max_steps,10}
  - name: eval
    kind: eval
    plugin_name: vlm_evaluator
    depends_on: [train]
    config:
      metrics: [narrative_quality, schema_compliance]
      thresholds: ${smoke}   # 关键：smoke recipe 引用 smoke.*
      eval_dataset: pet_annotation.vision_annotations

experiment_logger:
  name: clearml
  mode: offline
  on_unavailable: fallback_null
```

- [ ] **Step 2: smoke_tiny.yaml**

```yaml
# recipes/smoke_tiny.yaml
defaults:
  - smoke_base
  - _self_

# CPU tiny_test 继承 base，无改动
```

- [ ] **Step 3: smoke_mps.yaml**（M2+ dev 本地）

```yaml
defaults:
  - smoke_base
  - _self_

stages:
  - name: train
    kind: train
    plugin_name: llamafactory_sft  # 真 VLM
    config:
      base_model: Qwen/Qwen2-VL-2B-Instruct
      lora_r: 16
      lora_alpha: 32
      lr: 1.0e-4
      batch_size: 1
      grad_accum: 4
      max_steps: 20
      dataset: pet_annotation.vision_annotations
      output_dir: /tmp/smoke_mps
      # MPS 特有
      attn_implementation: eager
      precision: bf16
      device: mps
  - name: eval
    kind: eval
    plugin_name: vlm_evaluator
    depends_on: [train]
    config:
      metrics: [narrative_quality, schema_compliance]
      thresholds: ${smoke}
      eval_dataset: pet_annotation.vision_annotations
```

- [ ] **Step 4: smoke_small.yaml**（CUDA release gate）

类似 smoke_mps 但 `precision: fp16`, `max_steps: 100`, `thresholds: ${gate}`（真 release 阈值）, `mode: self_hosted`。

- [ ] **Step 5: Makefile**

```makefile
smoke-mps:
	pet run recipes/smoke_mps.yaml
```

### Task P2-F.3: release-smoke workflow

- [ ] **Step 1: .github/workflows/release-smoke.yml**

```yaml
name: release-smoke
on:
  workflow_dispatch:
  schedule:
    - cron: "0 4 * * *"   # 每日 04:00 UTC
  push:
    tags: ["v*"]
jobs:
  smoke-small:
    runs-on: [self-hosted, gpu]  # 假设有 CUDA runner；否则 ubuntu-latest + A10
    steps:
      - uses: actions/checkout@v4
      - run: make clearml-up   # 起 docker-compose stack
      - run: pip install -e pet-infra -e pet-train -e pet-eval
      - run: pet run recipes/smoke_small.yaml
      - run: make clearml-down
```

### Task P2-F.4: PR

```bash
git add recipes/ .github/workflows/ params.yaml Makefile
git commit -m "feat(pet-infra): three-tier smoke recipes (tiny/mps/small) + release-smoke workflow"
git push -u origin feature/smoke-recipes
gh pr create --base dev --title "feat: 3-tier smoke recipes + gate/smoke namespace"
```

merge 后回 pet-eval 仓打 tag：

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-eval
# dev → main PR
git checkout main && git pull
git tag -a v2.0.0 -m "Phase 3A pet-eval final"
git push origin v2.0.0
gh release create v2.0.0 --title "v2.0.0 Phase 3A"
```

**🎯 Phase 2 DoD**：pet-eval v2.0.0 tag；8 metric 全 plugin 化 + 回归 fixture 锁；VLMEvaluator + AudioEvaluator 注册；跨仓 import 跑通。

---

# Phase 3: Finalize

## PR #P3-A: pet-train final tag v2.0.0

**仓库**：pet-train

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train
git checkout main && git pull
# 代码不变，重打 final tag
git tag -a v2.0.0 -m "Phase 3A pet-train final (identical to rc1)"
git push origin v2.0.0
gh release create v2.0.0 --title "v2.0.0 Phase 3A final" --notes "Same code as v2.0.0-rc1"
```

---

## PR #P3-B: pet-infra matrix 2026.07 finalize

**仓库**：pet-infra
**Branch:** `feature/matrix-2026-07-finalize`（从 dev 切）

- [ ] **Step 1: 改 matrix 行，把 "-rc1" 全部去掉**

```yaml
  - release: "2026.07"
    pet_schema: "2.1.0"
    pet_infra: "2.3.0"
    pet_data: "1.2.0"
    pet_annotation: "2.0.0"
    pet_train: "2.0.0"
    pet_eval: "2.0.0"
    pet_quantize: "0.1.0"
    pet_ota: "0.1.0"
    # ...
```

保留 `2026.07-rc` 行作为历史（添加注释 `# deprecated, superseded by 2026.07`），或删除。推荐：**删除**（非公开 release）。

- [ ] **Step 2: matrix_history.md 追加 2026.07 条目**

- [ ] **Step 3: compatibility-matrix-smoke.yml 改为装 2026.07 final 版本**

- [ ] **Step 4: commit + PR + merge**

```bash
git commit -m "chore(pet-infra): finalize matrix 2026.07 (rc → final pins)"
gh pr create --base dev --title "chore: matrix 2026.07 final"
```

---

## PR #P3-C: pet-infra v2.3.0 final tag + DoD retrospective

**Branch:** `feature/phase-3a-retrospective`（从 dev 切，#P3-B merge 后）

**Files:**
- Create: `docs/retrospectives/2026-04-XX-phase-3a.md`

### Task P3-C.1: DoD 自检（§11 11.1-11.6）

- [ ] **Step 1: 按 PHASE_DOD_TEMPLATE.md 逐项勾选**

```markdown
# Phase 3A Retrospective (YYYY-MM-DD)

## 1. 代码交付
- [x] pet-train v2.0.0 merged + tagged
- [x] pet-eval v2.0.0 merged + tagged
- [x] pet-infra v2.3.0 merged + tagged
- [x] matrix 2026.07 行 finalize
- [x] docker/wandb/ 删 + docker/clearml/ 建

## 2. CI 全绿
- [x] plugin-discovery / integration-smoke / compatibility-matrix-smoke / release-smoke

## 3. 测试
- [x] pet-train 60+ tests
- [x] pet-eval 70+ tests
- [x] pet-infra 120+ tests
- [x] smoke_tiny PR gate 绿 (<2min)
- [x] smoke_small release gate 手动触发一次绿

## 4. 文档
- [x] DEVELOPMENT_GUIDE §5.4 / §5.5 / §8 更新
- [x] PHASE_DOD_TEMPLATE.md v1 committed
- [x] matrix_history 2026.07 追加
- [x] §11 跨仓 import 子节 committed

## 5. North Star §0.2.1 自检
- 可插拔性: 5 / 证据: §1.3 / §2.3 / §3.3 / §4.2
- 灵活性: 4 / 证据: §4.3 / §4.6 / §3.8 / §7.4
- 可扩展性: 4 / 证据: §4.2 / §4.5 / §4.6
- 可对比性: 5 / 证据: §4.6 / §5.2 / §3.4

最低 4 ≥ 3，通过。

## 6. 用户可验证
- [x] pet run recipes/smoke_mps.yaml 本地 M2 跑通
- [x] offline mode 产出 session zip 可用 clearml-task --import-offline 导入
- [x] pet run recipe.yaml -m train.lr=1e-4,3e-4 产出 2 独立 card

## 未完成（跟进 Phase 3B）
- pet-quantize v2.0.0 / pet-ota v2.0.0 破坏性重建
- matrix 2026.08 行
```

- [ ] **Step 2: commit + PR**

```bash
git add docs/retrospectives/
git commit -m "docs(pet-infra): Phase 3A retrospective + DoD self-check"
gh pr create --base dev --title "docs: Phase 3A retrospective"
# merge → dev → main
```

- [ ] **Step 3: 打 pet-infra v2.3.0 final tag**

```bash
git checkout main && git pull
git tag -a v2.3.0 -m "Phase 3A pet-infra final (matrix 2026.07 finalized)"
git push origin v2.3.0
gh release create v2.3.0 --title "v2.3.0 Phase 3A final"
```

### Task P3-C.2: memory 更新（用户内存系统）

- [ ] **Step 1: 更新 MEMORY.md 相关条目**（project_multi_model_refactor / project_pet_train_status / project_pet_eval_status / project_pet_infra_status）

- [ ] **Step 2: Write project_phase3a_training.md 标记完成日期**

**🎯 Phase 3A Overall DoD**：matrix 2026.07 finalized；3 仓 final tag；DoD retrospective committed；四维度 ≥ 3。

---

# 后续（Phase 3B 预告）

基于本 plan 的架构（orchestrator / ExperimentLogger ABC / plugin registry）扩 CONVERTERS 并重建 pet-quantize + pet-ota。独立 plan 文档。

---

## 附录 A: 代理执行建议

subagent-driven-development 模式下，每 PR 三阶段：

1. **implementer subagent**（Haiku/Sonnet）：按本 plan task 跑通 TDD 循环
2. **spec-review subagent**（Opus）：对照本 plan 核对 files 列表完整性 + test 覆盖度
3. **code-quality review subagent**（Opus）：检查 DRY/YAGNI + 错误处理 + 日志规范

三阶段 loop 到 approved 才 commit+push+开 PR。

## 附录 B: 失败恢复

如任何 PR CI 红：
- 修 bug → 新 commit（不 amend，per CLAUDE.md git 规范）
- 保持 plan 节奏不跳
- 如架构性失败（plugin 注册撞 / cache_key 哈希不稳），停全 chain，回 spec 修订，而非 patch 绕路（feedback_no_manual_workaround）

## 附录 C: 关键文件位置速查

| 用途 | 路径 |
|------|------|
| Phase 3A spec | `pet-infra/docs/superpowers/specs/2026-04-21-phase-3a-training-design.md` |
| 本 plan | `pet-infra/docs/superpowers/plans/2026-04-21-phase-3a-training-plan.md` |
| PHASE_DOD_TEMPLATE (P0-G 产物) | `pet-infra/docs/PHASE_DOD_TEMPLATE.md` |
| compatibility_matrix | `pet-infra/docs/compatibility_matrix.yaml` |
| North Star source | `pet-infra/docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md` §0.2.1 |
| DEVELOPMENT_GUIDE | `pet-infra/docs/DEVELOPMENT_GUIDE.md` |
| ModelCard contract | `pet-schema/src/pet_schema/model_card.py` |
| precompute_card_id | `pet-infra/src/pet_infra/recipe/card_id.py` |

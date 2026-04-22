# pet-infra 架构文档

> 维护说明：模块结构 / 扩展点 / 已知复杂点变更时同步本文档
> 最后对齐：v2.6.0 / 2026-04-23 (Phase 2 ecosystem optimization)

---

## 1. 职责

pet-infra 是 Train-Pet-Pipeline 的**共享运行时基础设施**。其他 8 个仓库将 pet-infra 作为 peer-dep（见 §6），通过注册表、插件发现、配置组合、CLI 和 Orchestrator 驱动整个管线。

核心能力模块：

| 模块 | 路径 | 功能 |
|------|------|------|
| Registry | `registry.py` | 7 个全局注册表（TRAINERS / EVALUATORS / CONVERTERS / METRICS / DATASETS / STORAGE / OTA） |
| Plugin Discovery | `plugins/discover.py` | entry-point 发现 `pet_infra.plugins` group，加载外部 plugin |
| Config Composition | `compose.py` | `compose_recipe()` 规范入口，Hydra defaults-list 解析 + override |
| CLI | `cli.py` + `cli_commands/` | `pet run / replay / sweep` 命令 |
| Orchestrator | `orchestrator/` | BaseStageRunner + 5 concrete runners，`pet_run()` 串行执行 |
| Storage | `storage/` | Local / S3 / HTTP 三后端，可通过 STORAGE registry 扩展 |
| ExperimentLogger | `experiment_logger/` | ClearML logger（W&B 已于 Phase 4 完全移除） |
| Replay | `replay.py` | 从 ModelCard 确定性重放训练 run |

---

## 2. I/O 合同

### 上游依赖

- **pet-schema**：提供 `ExperimentRecipe`、`ModelCard`、`RecipeStage` 等数据模型。pet-infra 在 `__init__.py` 顶部用 `ImportError` 检查 pet-schema 是否已装（β peer-dep，见 §6）。

### 下游消费者

以下 7 个仓库将 pet-infra 作为 peer-dep：

```
pet-data / pet-annotation / pet-train / pet-eval / pet-quantize / pet-ota / pet-id（实际不依赖）
```

各仓通过 `entry-point pet_infra.plugins` 将自己的 plugin 注册到 pet-infra 的 Registry，然后由 Orchestrator 按 `stage.component_registry` 调度。

---

## 3. 模块结构

```
src/pet_infra/
├── __init__.py              # peer-dep guard + __version__
├── _register.py             # 本仓 plugin 注册（storage / noop_evaluator / hydra）
├── registry.py              # 7 个 Registry 对象
├── compose.py               # compose_recipe() 规范入口（Phase 3B merge 后唯一来源）
├── plugins/
│   └── discover.py          # entry-point discovery
├── orchestrator/
│   ├── hooks.py             # BaseStageRunner + 5 concrete + STAGE_RUNNERS
│   ├── runner.py            # pet_run() — 串行执行 stages
│   └── stage_executor.py    # 单 stage 执行，分发到 STAGE_RUNNERS
├── experiment_logger/
│   ├── base.py              # ExperimentLogger ABC
│   ├── clearml_logger.py    # ClearML 实现
│   └── null_logger.py       # 离线 / 测试用无操作实现
├── storage/
│   ├── local.py             # LocalStorage（@register_module "local" + "file"）
│   ├── s3.py                # S3Storage（Phase 4 P1-E）
│   └── http.py              # HTTPStorage（Phase 4 P1-E）
├── cli.py                   # click 入口 + subcommand group
├── cli_commands/            # run / replay / sweep 子命令
├── replay.py                # 从 ModelCard 确定性重放
├── launcher.py              # multirun / variations launcher
├── hydra_plugins/           # Hydra structured config
├── recipe/                  # (Phase 3B 遗留目录，核心逻辑已 merge 到 compose.py)
├── base/                    # BasePlugin ABC
├── retry.py                 # tenacity 重试工具
├── logging.py               # 结构化 JSON 日志初始化
├── store.py                 # 数据库操作单点（下游通过此文件访问 DB）
├── device.py                # 设备检测（CPU / GPU / RK3576）
└── sweep_preflight.py       # sweep 前置校验
```

---

## 4. 核心模块详解

### 4.1 `registry.py` — 7 个全局注册表

**文件**：`src/pet_infra/registry.py`

**实现**：

```python
from mmengine.registry import Registry

TRAINERS   = Registry("trainer",   scope="pet_infra")
EVALUATORS = Registry("evaluator", scope="pet_infra")
CONVERTERS = Registry("converter", scope="pet_infra")
METRICS    = Registry("metric",    scope="pet_infra")
DATASETS   = Registry("dataset",   scope="pet_infra")
STORAGE    = Registry("storage",   scope="pet_infra")
OTA        = Registry("ota",       scope="pet_infra")
```

**为什么**：mmengine.Registry 提供线程安全的 `@register_module` 装饰器 + `get()` / `module_dict` API，是整个管线的 plugin 发现机制。7 个注册表对应 7 种 stage type，与 `STAGE_RUNNERS` dict key 一一对应。

**权衡**：强依赖 mmengine-lite（`>=0.10,<0.11`）。如未来切换 plugin 系统，7 个 Registry 对象是替换点。

**陷阱**：mmengine Registry 不允许重复注册同名 key（会 raise `KeyError`）。`_register.py` 中所有模块导入均有 `if key not in registry.module_dict` 守卫，避免测试并发时的重复注册问题。

---

### 4.2 `compose.py` — 规范配方组合入口

**文件**：`src/pet_infra/compose.py`

**规范签名**：

```python
def compose_recipe(
    path: str | Path,
    overrides: Sequence[str] = (),
) -> tuple[ExperimentRecipe, dict, str]:
```

返回 `(validated_recipe, resolved_dict, config_sha256)`。

**为什么**：Phase 3B 之前存在两个入口：顶层 `compose.py`（简单路径）和 `recipe/compose.py`（完整路径含 overrides + sha）。Subagent B（Phase 2）将两者 merge 为单一规范入口，消除二义性。`recipe/compose.py` 路径成为遗留目录，不再持有逻辑。

**权衡**：Hydra-style `defaults:` 列表解析是递归的，允许循环依赖。通过 `visited: set[Path]` 集合检测并抛出 `ComposeError`。

**陷阱**：`defaults:` 条目相对于**配方文件所在目录**解析（非 CWD），这是刻意设计，让配方可移动。调试时注意路径基准。

---

### 4.3 `orchestrator/hooks.py` — BaseStageRunner + 5 具体 runner

**文件**：`src/pet_infra/orchestrator/hooks.py`

**层次**：

```
BaseStageRunner
├── TrainerStageRunner    (registry=TRAINERS,   key="trainers")
├── EvaluatorStageRunner  (registry=EVALUATORS, key="evaluators")
├── ConverterStageRunner  (registry=CONVERTERS, key="converters")
├── DatasetStageRunner    (registry=DATASETS,   key="datasets")
└── OtaStageRunner        (registry=OTA,        key="ota")   ← 覆盖 run() 加 gate 检查
```

`STAGE_RUNNERS: dict[str, BaseStageRunner]` 是 Orchestrator 的分发字典。

**为什么**：Phase 2 Subagent C（StageRunner DRY）将 5 个 runner 原本重复的 registry lookup + plugin instantiate 逻辑统一到 `BaseStageRunner.run()`。只有 `OtaStageRunner` 覆盖 `run()`（加 `gate_status` 检查），其余 4 个完全继承基类。

**权衡**：`_registry_label: ClassVar[str]` 是下划线前缀的 ClassVar，约定子类 MUST 设置（无运行时 enforce，靠代码审查）。未来可改为 `@abstractmethod` 或 `__init_subclass__` 检查（见 §9 followup）。

**陷阱**：`_load_stage_kwargs()` 优先使用 `stage.config`（orchestrator 预注入），回退到磁盘加载 `stage.config_path`。单元测试绕过磁盘时依赖此回退。

---

### 4.4 `plugins/discover.py` — entry-point 插件发现

**文件**：`src/pet_infra/plugins/discover.py`

**核心函数**：

```python
def discover_plugins(required: Iterable[str] | None = None) -> dict[str, list[str]]:
```

扫描 `pet_infra.plugins` entry-point group，加载每个 ep 的 callable（通常是 `register_all`），副作用填充 7 个 Registry。返回每个 registry 当前已注册名的 summary dict。

**为什么**：使用标准 `importlib.metadata.entry_points` API，外部仓库只需在 `pyproject.toml` 声明 entry-point 即可被 pet-infra 发现，无需修改 pet-infra 本身。

**权衡**：discovery 是懒加载——只在调用 `discover_plugins()` 时触发，不在 import time 自动执行。CI 的 `plugin-discovery.yml` 显式调用以验证所有已注册 plugin。

**陷阱**：`entry_points(group=...)` 返回顺序不保证。`required` 参数用于 CI 断言特定 plugin 必须存在；缺失时抛 `RuntimeError`（不是 ImportError，因为这是配置错误而非 import 错误）。

---

### 4.5 `experiment_logger/clearml_logger.py` — ClearML 实验追踪

**文件**：`src/pet_infra/experiment_logger/clearml_logger.py`

**关键参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `mode` | `"offline" \| "saas" \| "self_hosted"` | 连接模式 |
| `on_unavailable` | `"strict" \| "fallback_null" \| "retry"` | 不可达策略 |
| `retry_wait` | tenacity wait | retry 模式的等待策略（测试传 `wait_none()`）|

**为什么**：W&B 已于 Phase 4 P1-F（2026-04-22）按 spec §1.5 完全移除，ClearML 是唯一实验追踪器。`ClearMLLogger` 通过 `ExperimentLogger` ABC 与 Orchestrator 解耦，`NullLogger` 用于离线 CI。

**权衡**：`retry` 模式的 tenacity decorator 在 `_init_task()` 内**每次调用 `start()` 时重新创建**（见 §8 已知复杂点 #1）。

**陷阱**：`on_unavailable="retry"` 且所有重试耗尽后，`_handle_unavailable()` 会 re-raise（等效于 strict），不会静默失败。

---

## 5. Extension Points

### 5.1 添加新 storage 后端

1. 新建 `src/pet_infra/storage/mybackend.py`，定义实现 `BaseStorage` 接口的类并用 `@STORAGE.register_module("mybackend")` 装饰。
2. 在 `_register.py` 的 `register_all()` 里加 `if "mybackend" not in STORAGE.module_dict: from pet_infra.storage import mybackend`.
3. 无需修改 Orchestrator、CLI 或 compose。通过 recipe yaml 的 `component_type: mybackend` 即可调用。

```python
# src/pet_infra/storage/mybackend.py
from pet_infra.registry import STORAGE
from pet_infra.base import BaseStorage

@STORAGE.register_module("mybackend")
class MyBackendStorage(BaseStorage):
    def __init__(self, bucket: str, **kwargs): ...
    def upload(self, local_path, remote_path): ...
    def download(self, remote_path, local_path): ...
```

### 5.2 添加新 trainer plugin（从外部仓库）

Trainers 不是 pet-infra 内部类——它们由 pet-train 等仓库提供，通过 entry-point 注册：

1. 在 `pet-train/pyproject.toml` 声明：
   ```toml
   [project.entry-points."pet_infra.plugins"]
   pet_train = "pet_train._register:register_all"
   ```
2. 在 `pet_train/_register.py` 的 `register_all()` 里导入 trainer 类：
   ```python
   from pet_infra.registry import TRAINERS
   if "sft_trainer" not in TRAINERS.module_dict:
       from pet_train.trainers import sft  # @TRAINERS.register_module("sft_trainer")
   ```
3. 无需修改 pet-infra。`discover_plugins()` 调用后自动可见。

### 5.3 添加新 stage type

如需新的 stage type（如 `"postprocess"`）：

1. 在 `registry.py` 添加新 Registry：
   ```python
   POSTPROCESSORS = Registry("postprocessor", scope="pet_infra")
   ```
2. 在 `orchestrator/hooks.py` 添加 runner：
   ```python
   class PostprocessStageRunner(BaseStageRunner):
       registry = POSTPROCESSORS
       _registry_label = "POSTPROCESSORS"
   ```
3. 在 `STAGE_RUNNERS` dict 加一行：
   ```python
   "postprocess": PostprocessStageRunner(),
   ```
4. 更新 `plugins/discover.py` 的 `_REGISTRY_MAP` 加 `"postprocess": POSTPROCESSORS`。
5. 更新 `_register.py` 的 `registry.py` import list（`__all__`）。

---

## 6. 依赖管理

### β peer-dep 模式（2026-04-23 决策）

pet-infra 和 pet-schema 均为 peer-dep。下游仓库：
- `pyproject.toml [project.dependencies]` 不声明 `pet-schema` 和 `pet-infra`
- `compatibility_matrix.yaml releases[-1]` 是版本锁定源
- CI 和开发者按 3-step（pet-infra 自身）或 4-step（下游）装序

### pet-infra 自身 3-step 装序

```bash
# Step 1: 装 pet-schema peer
pip install 'pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@v<matrix_tag>'

# Step 2: 装 pet-infra（含 dev extras）
pip install -e ".[dev,api,sync]"

# Step 3: 版本断言
python -c "import pet_schema, pet_infra; print(pet_schema.__version__, pet_infra.__version__)"
```

### pet-infra `__init__.py` guard

```python
try:
    import pet_schema
except ImportError as e:
    raise ImportError("pet-infra requires pet-schema ...") from e

__version__ = "2.6.0"
```

使用 `ImportError`（非 `RuntimeError`），因为这发生在模块 import 时，不在 `register_all()` 内（见 §8 guard pattern 说明）。

---

## 7. 开发 / 测试

### 环境

```bash
conda activate pet-pipeline   # 共享环境，不创建 per-repo env
cd pet-infra
make setup   # pip install -e ".[dev,api,sync]"
make test    # pytest tests/ -v
make lint    # ruff check + mypy
```

### PET_ALLOW_MISSING_SDK

Phase 2 Subagent A 将 `PET_ALLOW_MISSING_SDK=1` 设置改为**自动**——`ci.yml` 不再需要显式 export，相关代码内部已处理。本地开发也不需要手动设置。

### 测试覆盖

```
tests/
├── test_version.py         # __version__ 一致性（pyproject.toml vs __init__.py）
├── test_registry.py        # 7 个 Registry 注册 / 查找
├── test_compose.py         # compose_recipe() 多场景
├── test_discover.py        # entry-point discovery
├── test_orchestrator/      # hooks.py + stage_executor + runner
├── test_experiment_logger/ # ClearML + NullLogger
├── test_storage/           # local + s3（moto mock）+ http（respx mock）
├── test_replay.py          # sha256 验证 + git drift warn
└── ...
```

---

## 8. 已知复杂点

### 8.1 ClearML retry object 每次 start() 重建

**位置**：`experiment_logger/clearml_logger.py` `_init_task()`

**现象**：`on_unavailable="retry"` 时，每次调用 `start()` 都重新用 `@retry(...)` 装饰 `_inner`，产生新的 tenacity 包装对象。在高频短 stage 场景（如 sweep 中每个 trial 调一次）会有轻微对象分配开销。

**评估**：微优化，当前业务场景下调用频率低，不影响正确性。如有性能需求，可将 `_inner` 提升到 `__init__` 中一次性构建，但会让 `retry_wait` 不可注入（影响可测试性）。**结论**：不值得修复。

### 8.2 `replay.py` git walk via `parents[4]`

**位置**：`replay.py` `_current_git_shas()`（内部辅助函数）

**现象**：通过 `subprocess` 调用 `git log` 获取 repo HEAD sha，在 site-packages install（非 editable）场景下无法定位 .git 目录，会产生 `subprocess.CalledProcessError`。

**评估**：代码有 graceful fallback——异常时返回 `{}`（空 dict），`check_git_drift()` 收到空 dict 直接 return `[]`（无 drift warning）。功能正确，只是 site-packages 场景无法做 drift check，这符合预期（site-packages 安装不做开发调试）。**结论**：保持现状，已文档说明。

---

## 9. Phase 5+ Followups

以下内容为 Phase 2 代码审查发现的技术债，计划在后续 Phase 修复：

| 项 | 优先级 | 说明 |
|---|---|---|
| `__all__` 缺失声明 | MEDIUM | pet-infra 顶层 `__init__.py` 未声明 `__all__`，外部 `from pet_infra import *` 行为未定义。Phase 5 补充。|
| `_registry_label` 约定 vs 合同 | LOW | `BaseStageRunner._registry_label` 是 ClassVar[str]，子类 MUST 设置但无运行时 enforce。可改为 `__init_subclass__` 检查或 `@abstractmethod`。|
| pet-quantize peer-dep 硬 pin 残留 | MEDIUM | pet-quantize 当前仍有 pet-infra 硬 pin，Phase 7 修复（见 OVERVIEW.md §4 表注）。|
| pet-ota peer-dep 硬 pin 残留 | MEDIUM | pet-ota 当前仍有 pet-infra / pet-quantize 硬 pin，Phase 8 修复。|

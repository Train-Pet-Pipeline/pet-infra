---
name: 多模型后训练管线重构设计
description: Train-Pet-Pipeline 全链路重构为 plugin-registry 驱动的多模型后训练基础设施，支持 VLM / 音频 CNN / 未来传感器模型的统一训练、评估、量化、端侧部署
type: spec
status: draft
date: 2026-04-20
owner: pet-infra
scope: cross-repo (pet-schema, pet-infra, pet-data, pet-annotation, pet-train, pet-eval, pet-quantize, pet-ota)
---

# 多模型后训练管线重构设计

## 0. 背景与动机

### 0.1 现状

Train-Pet-Pipeline 目前已经上线 v1（2026-04-15 完成全链 E2E 集成测试），管线面向"单一 VLM 模型 + 蒸馏 + DPO + 量化"场景设计，同时 pet-train 中已并存一个独立的 Audio CNN 训练入口。

审计（Section 0.3）表明：
- 现有管线对**单一 VLM 的消融实验**是可插拔的（Qwen2-VL 架构、LoRA 参数、DPO beta 等都已参数化）。
- 但**多模型形态**下存在显著耦合：
  - `pet-eval/cli.py` 有 3 个独立 subcommand（`eval-trained` / `eval-audio` / `eval-quantized`），不是同一抽象
  - `pet-quantize/config.py` 硬编码 `vision / llm / audio` 三元组
  - `pet-schema` 的 `PetFeederEvent` 是单一 VLM 叙事输出，没有 `modality` 字段
  - 没有统一的 Trainer / Evaluator / Converter / Metric / Dataset registry
  - 模型之间的关联（蒸馏教师-学生、跨模态融合）没有 first-class 抽象

### 0.2 目标

将管线重构为 **plugin-registry 驱动的多模型后训练基础设施**，使：

1. **新增模型家族**（如化学传感器 CNN、多模态融合模型）= 写一个 Python plugin 类 + decorator 注册 + 一个 Hydra recipe 文件，**不改任何 infra 代码**。
2. **实验可控变量**：单模型消融（扫 LoRA rank）、多模型对比（VLM vs. 音频）、模型关联实验（视觉-听觉 cross-attention 融合）都通过 recipe 声明。
3. **配置驱动、类型安全、记录清晰**：Hydra 组合配置，Pydantic（pet-schema）校验，ClearML 统一可视化，DVC 保证离线可复现。
4. **工程性**：fail-fast preflight、幂等重试、跨仓 CI 验证、版本治理。

### 0.2.1 North Star —— 所有决策的唯一标尺

**每一个实现决策都要回答同一个问题：这让以下场景更容易，还是更难？**

| 未来场景 | 期望的实现路径 | 反面教材（不该出现的路径） |
|---|---|---|
| 新增模型家族（VLM-v3、化学传感器 CNN） | 写 plugin + 写 recipe，**infra 零改动** | 改 ABC / 改 registry / 改 schema 结构 |
| 新增 modality（嗅觉、生理信号） | 加 `Modality` enum 值 + 写对应 Sample/Annotation Pydantic 子类 + 写 plugin，**schema 表结构零变更** | 新增 `OlfactoryAnnotationRow` 表 / 新增 migration / 改 adapter 分支 |
| 新增只预训练的模型（只 pretrain，不 fine-tune） | recipe 只声明 pretrain stage，后续 capability 自动跳过 | 加 if/else 判断某模型是否走 finetune |
| 模型架构消融（Qwen2-VL vs. InternVL） | `pet run recipe=vlm_sft -m trainer=qwen,internvl` 一条命令 | 复制 recipe / 改 hardcode / 改 CLI |
| 模型间对比（VLM vs. Audio CNN） | 同一 recipe 改 `trainer._target_` | 走两条独立 CLI |
| **业务侧多模型综合判断**（生产推理时 VLM + Audio 等多模型输出联合决策） | fusion plugin 注册进 EVALUATORS，recipe 声明 `fusion._target_`；多策略（`single_modal` / `and_gate` / `weighted` / `learned_fusion`）可互换 | 在应用代码或网关里 hard-code 多模型调用与合并逻辑 |
| 模型间交叉监督（训练时一个模型产弱标喂另一个） | recipe 串 stage：`vlm_infer → audio_weak_label → audio_train` | 手工中间脚本串流 |
| 跨模态融合消融扫描 | `pet run recipe=prod -m fusion=vlm_only,audio_only,and_gate,weighted` 一条命令 | 复制 4 份 recipe |

**核心断言**：**capability 边界稳定 + 数据契约可扩展 + recipe 声明组合 = 新实验不需要写新 infra。**

**决策反模式清单**（违反 North Star 的常见陷阱）：
- ❌ 把 modality/model 差异写进表 schema 或文件结构 → 新 modality 要改 schema
- ❌ 下游 repo 硬 pin 上游 exact git tag → compatibility_matrix 失去治理权，上游无法自由演进
- ❌ 在 infra 代码里 `if modality == "vision": ... elif "audio": ...` → 新 modality 要改 infra
- ❌ 为"跳过 stage"特判，而不是提供 noop/fallback plugin → capability 抽象被破坏
- ❌ 默认 required 的消融相关参数 → 每次做对比实验都要显式声明，阻碍扫描
- ❌ 复制 recipe 代替参数化 → 配置漂移、对比实验不可信

**每个 Phase 的 DoD 必须包含这一条自检**：回看本 Phase 引入的新类/新表/新字段/新 CLI，问"下一个 modality/下一个模型家族出现时，这会不会变成必改点？"如果答案是"会"，立即重构为 plugin/discriminator/recipe。

### 0.3 调研依据

#### 现有管线审计（决策依据）

- 已存在的可复用抽象：`MetricResult` dataclass、`logits_provider` 模式、`gate checker`、OTA backend（model-agnostic）、SQLite migration 模式、Pydantic 配置模式
- 主要耦合点：见 0.1；详细映射见 Section 1.3
- VLM 与 audio 两套训练代码物理隔离但**没有统一接口**

#### 外部最佳实践（决策依据）

| 领域 | 参考方案 | 选型结论 |
|---|---|---|
| 多模型训练平台 | Kubeflow / TorchX / Ray Train / TRL Trainer 层级 | 不采用完整平台；借鉴"抽象单元是 capability 而非 model"的洞察 |
| Plugin / Registry | MMEngine Registry / setuptools entry_points / LLaMA-Factory constants | **选 MMEngine Registry + entry_points**，放在 capability 边界 |
| 配置组合 | Hydra + Pydantic structured configs | **选 Hydra + pet-schema Pydantic** |
| 实验追踪 / 模型 registry | W&B vs. ClearML vs. MLflow vs. 自建 | **替换 W&B 为 ClearML**（用户决策：沉默成本不计入）+ **pet-schema 承载 ModelCard contract** |
| 数据契约 | HF Features / WebDataset / LeRobot | **选 Pydantic BaseSample ABC + HF/WebDataset 导出适配器** |
| 管线编排 | DVC foreach/matrix / ClearML Pipelines / sub-dvc.yaml | **每仓 dvc.yaml + pet-infra 顶层编排**，Hydra → DVC → ClearML 三层职责分离 |
| OTA 多模型 registry | MLflow alias / ClearML label / 自建 manifest | **pet-schema ModelCard 为 truth + pet-ota 读 manifest**（不依赖外部服务） |

---

## 1. 5 层架构

### 1.1 层级总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 5 │ pet-schema: Pydantic 契约                                  │
│          │   BaseSample / BaseAnnotation / ModelCard                  │
│          │   ExperimentRecipe / RecipeStage / AblationAxis            │
│          │   → 所有数据、模型、实验的"真理源"                         │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 4 │ 运行时：DVC（执行 & cache）+ ClearML（可观测 & registry）  │
│          │   → DVC 负责确定性复现；ClearML 负责血统图 / 对比 UI       │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 3 │ Experiment Recipe (Hydra config group)                     │
│          │   pet-infra/recipes/  (跨仓)                               │
│          │   pet-{repo}/configs/experiment/  (单仓)                   │
│          │   → 声明"这个实验包含哪些 stage、怎么串、怎么消融"         │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 2 │ Hydra: config 组合 / override / multirun                   │
│          │   → 单个组件的参数化与变体扫描                             │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 1 │ Plugin Registry (6 个)                                     │
│          │   TRAINERS / EVALUATORS / CONVERTERS / METRICS / DATASETS  │
│          │   + STORAGE (适配器 registry)                              │
│          │   → 组件目录，decorator 注册，config 驱动实例化            │
└──────────────────────────────────────────────────────────────────────┘
```

**核心信条**：每一层只做一件它最擅长的事，换掉任意一层不影响其他层。

### 1.2 仓库职责映射（重构后）

| 仓库 | 承载的层 | 主要变化 |
|---|---|---|
| **pet-schema** | Layer 5 全部 | **重大**：新增 BaseSample 家族、ModelCard、ExperimentRecipe 等 Pydantic 契约；新增 `to_hf_features()` / `to_manifest_entry()` 适配器 |
| **pet-infra** | Layer 1 的 ABC + Layer 3 跨仓 recipe + 编排入口 | **重大**：新增 `Registry` 类、6 个 Base ABC、`BaseStorage` ABC、`pet run` CLI、`recipes/` 跨仓编排、顶层 dvc.yaml |
| **pet-data** | Layer 1 (Dataset plugin) + Layer 5 消费 | **中**：`store.py` 改 modality 分表；新增 `@DATASETS.register_module()` dataset plugin；去掉 `FrameRecord` 硬编码 |
| **pet-annotation** | Layer 1 (Dataset plugin) + Layer 5 消费 | **中**：`AnnotationRecord` 改 modality-aware；LS 模板按 modality dispatch |
| **pet-train** | Layer 1 (Trainer plugins) + Layer 3 单仓 recipe | **重大**：VLM 和 audio 训练代码改 `@TRAINERS.register_module()` plugin；CLI Hydra 化；删硬编码分叉 |
| **pet-eval** | Layer 1 (Evaluator/Metric plugins) + Layer 3 单仓 recipe | **重大**：3 个 subcommand 合并为 `pet-eval run`；metric 全部 `@METRICS.register_module()`；Evaluator 拆 plugin |
| **pet-quantize** | Layer 1 (Converter plugins) | **中**：`convert/` 下每种转换改 `@CONVERTERS.register_module()`；`ConvertConfig` 三元组删除 |
| **pet-ota** | 消费 Layer 5 ModelCard | **小**：打包从 ModelCard/manifest 读（本身已 model-agnostic） |

### 1.3 跨仓依赖关系

- ✅ 新增：pet-infra ← pet-schema；所有仓 ← pet-infra
- ❌ 删除：W&B 在所有仓
- ➕ 新增第三方依赖：`mmengine-lite`（仅 Registry 部分）、`hydra-core`、`clearml`

---

## 2. Plugin Registry 机制

### 2.1 Registry 实现（复用 mmengine）

不自研，直接依赖 `mmengine.Registry`（通过 `mmengine-lite` 包，~200KB，无 CV 依赖），使用它的核心能力：
- `@REGISTRY.register_module(name="xxx")` decorator 注册
- `REGISTRY.build(config_dict)` 根据 `type` 字段 dispatch 实例化
- `REGISTRY.get("xxx")` 取类、不实例化
- 支持 parent/child scope 跨仓查找

### 2.2 6 个 Registry 定义

```python
# pet-infra/src/pet_infra/registry.py
from mmengine.registry import Registry

TRAINERS   = Registry("trainer",   scope="pet_infra")
EVALUATORS = Registry("evaluator", scope="pet_infra")
CONVERTERS = Registry("converter", scope="pet_infra")
METRICS    = Registry("metric",    scope="pet_infra")
DATASETS   = Registry("dataset",   scope="pet_infra")
STORAGE    = Registry("storage",   scope="pet_infra")
```

各子仓的 registry 通过 scope 继承：

```python
# pet-train/src/pet_train/registry.py
from pet_infra.registry import TRAINERS as _PARENT
from mmengine.registry import Registry

TRAINERS = Registry("trainer", parent=_PARENT, scope="pet_train")
```

跨仓 build 时用 `type="pet_train.vlm_sft"` 的命名空间语法，避免命名冲突。

### 2.3 Plugin 发现机制

两级：

1. **生产（setuptools `entry_points`）**：

```toml
# pet-train/pyproject.toml
[project.entry-points."pet_infra.plugins"]
register = "pet_train._register:register_all"
```

```python
# pet-train/src/pet_train/_register.py
def register_all() -> None:
    from pet_train.trainers import vlm_sft, vlm_dpo, vlm_distill, audio_cnn_finetune  # noqa
```

pet-infra CLI 启动：

```python
from importlib.metadata import entry_points

def _load_plugins(required: list[str] | None = None) -> None:
    for ep in entry_points(group="pet_infra.plugins"):
        if required is None or ep.name in required:
            ep.load()()
```

2. **开发 / CI（显式 `required_plugins` 列表）**：recipe 声明，CLI 只 import 声明的 plugin。

### 2.4 6 个 Base ABC

```python
# pet-infra/src/pet_infra/base/trainer.py
class BaseTrainer(ABC):
    """一个完整的训练作业 wrapper（封装 LLaMA-Factory / Lightning / etc）."""

    @abstractmethod
    def fit(
        self,
        recipe: ExperimentRecipe,
        resolved_config: dict,
        output_dir: Path,
    ) -> ModelCard: ...

    @abstractmethod
    def validate_config(self, resolved_config: dict) -> None: ...

    @abstractmethod
    def estimate_resources(self, resolved_config: dict) -> ResourceSpec: ...


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        model_card: ModelCard,
        eval_config: dict,
        output_dir: Path,
    ) -> EvaluationReport:                   # EvaluationReport 定义见 Section 3.8
        ...

    @abstractmethod
    def supports(self, model_card: ModelCard) -> bool: ...


class EdgeFormat(str, Enum):
    RKLLM = "rkllm"
    RKNN  = "rknn"
    ONNX  = "onnx"
    GGUF  = "gguf"
    # 新增格式：往枚举里加，不用改签名

class BaseConverter(ABC):
    @abstractmethod
    def convert(
        self,
        source_card: ModelCard,
        convert_config: dict,
        calibration_data_uri: Optional[str],
        output_dir: Path,
    ) -> ModelCard: ...

    @abstractmethod
    def target_format(self) -> EdgeFormat: ...


class BaseMetric(ABC):
    name: ClassVar[str]
    higher_is_better: ClassVar[bool]

    @abstractmethod
    def compute(
        self,
        predictions: list,
        references: list,
        **kwargs,
    ) -> MetricResult: ...


class BaseDataset(ABC):
    @abstractmethod
    def build(self, dataset_config: dict) -> Iterable[BaseSample]: ...

    @abstractmethod
    def to_hf_dataset(self, dataset_config: dict) -> "datasets.Dataset": ...

    @abstractmethod
    def modality(self) -> Literal["vision", "audio", "sensor", "multimodal"]: ...


class BaseStorage(ABC):
    @abstractmethod
    def read(self, uri: str) -> bytes: ...

    @abstractmethod
    def write(self, uri: str, data: bytes) -> str: ...

    @abstractmethod
    def exists(self, uri: str) -> bool: ...

    @abstractmethod
    def iter_prefix(self, prefix: str) -> Iterator[str]: ...
```

URI scheme 约定：`local://` / `s3://` / `wds://` — `STORAGE.build({"type": uri.scheme})` 自动 dispatch。

### 2.5 Plugin 注册示例

```python
# pet-train/src/pet_train/trainers/vlm_sft.py
from pet_train.registry import TRAINERS
from pet_infra.base import BaseTrainer, ResourceSpec
from pet_schema import ModelCard, ExperimentRecipe

@TRAINERS.register_module(name="vlm_sft")
class VLMSftTrainer(BaseTrainer):
    """Wrap LLaMA-Factory's SFT training."""

    def fit(self, recipe, resolved_config, output_dir) -> ModelCard:
        # 现有 LLaMA-Factory 调用逻辑搬进来
        # 训练完写 ModelCard 落盘
        return ModelCard(...)

    def validate_config(self, resolved_config): ...
    def estimate_resources(self, resolved_config) -> ResourceSpec: ...
```

### 2.6 依赖治理与 peer-dep 约定

**所有 plugin-provider 仓库**（pet-data / pet-annotation / pet-train / pet-eval / pet-quantize / pet-ota）**不在 `[project.dependencies]` 里声明 pet-infra 或 pet-schema**。

**为什么**：

- 下游硬 pin 上游 git tag（`pet-infra @ git+…@v2.0.0`）会让每次 pet-infra / pet-schema 升级都必须连锁改所有下游 pyproject——上游无法自由演进
- `compatibility_matrix.yaml` 失去版本治理权：真理源被拆到 N 个下游 pyproject 里
- pip 以硬 pin 版本替换 editable 安装，导致 CI 必须 `--force-reinstall --no-deps` workaround

**统一约定**：

- pet-infra / pet-schema 是 **peer dependencies**，由环境预先提供（conda env `pet-pipeline` 已预装；CI 第一步装 matrix 指定 tag）
- `_register.py` 开头 `import pet_infra` fail-fast，错误信息带 install 命令
- compatibility_matrix.yaml 是唯一 pin 真理源
- 标准 CI 装序：

```bash
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<matrix_tag>'
pip install -e . --no-deps
python -c "import pet_infra; assert pet_infra.__version__.startswith('2.')"
```

（详见 `pet-infra/docs/DEVELOPMENT_GUIDE.md §11`）

---

## 3. pet-schema Pydantic 契约

### 3.0 本节定义的类型一览（Phase 1 planner 核对清单）

| 类型 | 所在子节 | 归属文件 |
|---|---|---|
| `Modality` / `SourceInfo` | 3.2 | `samples.py` / `enums.py` |
| `BaseSample` / `VisionSample` / `AudioSample` / `SensorSample` / `Sample` | 3.2 | `samples.py` |
| `BaseAnnotation` / `LLMAnnotation` / `ClassifierAnnotation` / `RuleAnnotation` / `HumanAnnotation` / `Annotation` / `DpoPair` | 3.3 | `annotations.py` |
| `QuantConfig` / `EdgeArtifact` / `ResourceSpec` / `ModelCard` | 3.4 | `model_card.py` |
| `ArtifactRef` / `RecipeStage` / `AblationAxis` / `ExperimentRecipe` | 3.5 | `recipe.py` |
| `MetricResult` | 保留现有 | `metric.py` |
| `EvaluationReport` | 3.8 | `metric.py` |
| `TrainerConfig` / `EvaluatorConfig` / `ConverterConfig` / `DatasetConfig` | 3.9 | `configs.py` |

### 3.1 模块组织

```
pet-schema/src/pet_schema/
├── __init__.py           ← re-export 所有公共契约
├── samples.py            ← BaseSample / VisionSample / AudioSample / SensorSample
├── annotations.py        ← BaseAnnotation / LLMAnnotation / ClassifierAnnotation / RuleAnnotation / HumanAnnotation
├── model_card.py         ← ModelCard / QuantConfig / EdgeArtifact
├── recipe.py             ← ExperimentRecipe / RecipeStage / AblationAxis
├── metric.py             ← MetricResult（保留现有） / EvaluationReport
├── configs.py            ← TrainerConfig / EvaluatorConfig / ConverterConfig / DatasetConfig（Structured Configs）
├── enums.py              ← 共享 Literal / Enum / EdgeFormat
├── adapters/
│   ├── hf_features.py
│   ├── webdataset.py
│   └── manifest.py
├── prompts/              ← 保留（VLM 训练用的 prompt 模板）
└── version.py            ← SCHEMA_VERSION
```

### 3.2 Sample 契约（数据侧）

```python
Modality = Literal["vision", "audio", "sensor", "multimodal"]

class SourceInfo(BaseModel):
    source_type: Literal["youtube", "community", "device", "synthetic"]
    source_id: str
    license: Optional[str]

class BaseSample(BaseModel):
    sample_id: str                        # content-addressed (sha256 of content)
    modality: Modality
    storage_uri: str                      # local://... / s3://... / wds://...
    captured_at: datetime
    source: SourceInfo
    pet_species: Optional[PetSpecies]
    model_config = {"frozen": True}

class VisionSample(BaseSample):
    modality: Literal["vision"] = "vision"
    frame_width: int
    frame_height: int
    lighting: Lighting
    bowl_type: Optional[BowlType]
    blur_score: float
    brightness_score: float

class AudioSample(BaseSample):
    modality: Literal["audio"] = "audio"
    duration_s: float
    sample_rate: int
    num_channels: int
    snr_db: Optional[float]
    clip_type: Optional[Literal["bark","meow","purr","silence","ambient"]]

class SensorSample(BaseSample):
    modality: Literal["sensor"] = "sensor"
    sensor_type: str                      # "chem_voc" / "chem_nh3" / ...
    readings: dict[str, float]
    ambient_temp_c: Optional[float]
    ambient_humidity: Optional[float]

Sample = Annotated[
    VisionSample | AudioSample | SensorSample,
    Discriminator("modality"),
]
```

### 3.3 Annotation 契约

**设计轴**：按 **annotator 范式**（capability）discriminator，**不按 modality**。

理由：同一 modality 可被多种 annotator 范式标注（例如 audio 既可被 CNN 分类器也可被 Whisper+LLM 打标），若按 modality 拆表会让"audio + LLM 标注"无位可放。按 annotator 范式拆则 modality 自然降级为 attribute，新 modality = 加 enum 值，零 schema 变更。

```python
class BaseAnnotation(BaseModel):
    annotation_id: str
    target_id: str                        # 被标注对象 ID（frame_id / audio_sample_id / sensor_sample_id 通用）
    annotator_type: Literal["llm", "classifier", "rule", "human"]
    annotator_id: str                     # ModelCard.id 或 human reviewer id
    modality: Modality                    # 被标注对象的模态；attribute 而非 discriminator
    created_at: datetime
    schema_version: str
    storage_uri: Optional[str]

class LLMAnnotation(BaseAnnotation):
    """LLM / VLM / Whisper+LLM 等生成式标注。"""
    annotator_type: Literal["llm"] = "llm"
    prompt_hash: str
    raw_response: str
    parsed_output: dict                   # JSONB — 各 modality 的结构化输出
                                          # vision 用 PetFeederEvent；audio 用 AudioCaption 等

class ClassifierAnnotation(BaseAnnotation):
    """分类器风格标注（audio CNN / image classifier / sensor NN）。"""
    annotator_type: Literal["classifier"] = "classifier"
    predicted_class: str
    class_probs: dict[str, float]
    logits: Optional[list[float]]

class RuleAnnotation(BaseAnnotation):
    """启发式、阈值等规则标注。"""
    annotator_type: Literal["rule"] = "rule"
    rule_id: str
    rule_output: dict                     # JSONB

class HumanAnnotation(BaseAnnotation):
    """人工审核 / DPO 选择。"""
    annotator_type: Literal["human"] = "human"
    reviewer: str
    decision: str
    notes: Optional[str]

Annotation = Annotated[
    LLMAnnotation | ClassifierAnnotation | RuleAnnotation | HumanAnnotation,
    Discriminator("annotator_type"),
]

class DpoPair(BaseModel):
    pair_id: str
    chosen_annotation_id: str
    rejected_annotation_id: str
    preference_source: Literal["human", "rule", "auto"]
    reason: Optional[str]
```

**注意**：本节于 2026-04-21 Phase 2 债务还清期间从"按 modality 拆"改为"按 annotator 范式拆"。迁移详情见 `2026-04-21-phase-2-debt-repayment-design.md`。消费端（Phase 3 Trainer / Phase 4 Evaluator）应按 annotator_type 分流，而非按 modality 分流。

### 3.4 ModelCard 契约（模型 & 血统）

```python
class QuantConfig(BaseModel):
    method: Literal["gptq", "awq", "ptq_int8", "qat", "fp16", "none"]
    bits: Optional[int]
    group_size: Optional[int]
    calibration_dataset_uri: Optional[str]

class EdgeArtifact(BaseModel):
    format: Literal["rkllm", "rknn", "onnx", "gguf"]
    target_hardware: list[str]
    artifact_uri: str
    sha256: str
    size_bytes: int
    min_firmware: Optional[str]
    input_shape: dict[str, list[int]]

class ResourceSpec(BaseModel):
    gpu_count: int
    gpu_memory_gb: int
    cpu_count: int
    estimated_hours: float

class ModelCard(BaseModel):
    # 身份
    #
    # id 的产生权威：
    #   - pet-infra CLI 在每个 stage 启动前（Section 5 时序 [9]）根据
    #     f"{recipe_id}_{stage_name}_{resolved_config_sha[:8]}" 预计算
    #   - 通过 BaseTrainer.fit 的 resolved_config["_target_card_id"] 字段注入给 plugin
    #   - plugin 必须使用注入的 id（不允许自造），以保证 content-addressed 不变量
    #   - 不是 Pydantic computed_field（因为 resolved_config_sha 需要 pet-infra 计算）
    #
    #   这保证 parent_models / ArtifactRef(ref_type="recipe_stage_output") 在
    #   上游 stage 执行之前就能被下游 stage 引用并解析。
    id: str
    version: str
    modality: Modality
    task: str
    arch: str

    # 如何产生（可复现）
    training_recipe: str
    recipe_id: Optional[str]
    hydra_config_sha: str
    git_shas: dict[str, str]
    dataset_versions: dict[str, str]

    # 产物位置
    checkpoint_uri: str

    # 量化 & 端侧（可选）
    quantization: Optional[QuantConfig]
    edge_artifact: Optional[EdgeArtifact]

    # 血统
    parent_models: list[str]
    lineage_role: Optional[Literal["teacher","student","sft_base","dpo_output","fused"]]

    # 指标
    metrics: dict[str, float]
    gate_status: Literal["pending","passed","failed"]

    # 追溯
    trained_at: datetime
    trained_by: str
    clearml_task_id: Optional[str]
    dvc_exp_sha: Optional[str]
    notes: Optional[str]

    def to_manifest_entry(self) -> dict: ...
```

### 3.5 ExperimentRecipe 契约（编排侧）

```python
class ArtifactRef(BaseModel):
    """Stage 间 / stage-to-dataset 的引用。各 ref_type 的解析规则：

    - dataset              → ref_value 是 DATASETS registry key；CLI 调 DATASETS.build(...)
    - model_card           → ref_value 是已存在 ModelCard.id；CLI 从 ClearML registry 或
                             本地 modelcards/ 目录读取该 ModelCard 并传给 plugin
    - dvc_path             → ref_value 是 DVC 追踪的任意路径；plugin 自行处理语义
    - recipe_stage_output  → ref_value 是同一 recipe 内的上游 stage.name；解析为
                             **该 stage 的 fit/evaluate/convert 返回的 ModelCard**
                             （与 ref_type="model_card" 效果相同，但 id 在 recipe 执行前不存在，
                             由 pet-infra 预计算 id 后回填到下游 stage 的 inputs）
    """
    ref_type: Literal["dataset", "model_card", "dvc_path", "recipe_stage_output"]
    ref_value: str

class RecipeStage(BaseModel):
    name: str
    # component_registry 有意只枚举这三个 — stage 必须是产出 artifact 的能力（"主动"）。
    # DATASETS / METRICS / STORAGE 是 "被动" 依赖，通过 ArtifactRef 或 plugin 内部引用，
    # 不作为独立 stage 出现。
    component_registry: Literal["trainers","evaluators","converters"]
    component_type: str
    inputs: dict[str, ArtifactRef]
    config_path: str
    depends_on: list[str]
    condition: Optional[str]
    on_failure: Literal["stop","continue","abort"] = "stop"

class AblationAxis(BaseModel):
    """声明一个消融轴。pet-infra 在执行时把 variations 编译为 Hydra 的
    sweeper 参数（等价于命令行 --multirun + param.path=v1,v2,v3），不需要用户
    在 recipe 里同时手写 hydra.sweeper.params —— 如果同时写了，以 variations 为准。
    `stage` 必须指向一个 RecipeStage.name。"""
    name: str
    stage: str
    hydra_path: str
    values: list[Union[str,int,float,bool]]
    link_to: Optional[str]                  # 联动另一个 axis，pairwise 而非笛卡尔积

class ExperimentRecipe(BaseModel):
    recipe_id: str
    description: str
    scope: Literal["single_repo","cross_repo"]
    owner_repo: Optional[str]
    schema_version: str

    stages: list[RecipeStage]
    variations: list[AblationAxis]
    produces: list[str]

    default_storage: str
    required_plugins: list[str]

    def to_dag(self) -> "networkx.DiGraph": ...
```

### 3.6 版本策略

- `pet_schema.version.SCHEMA_VERSION` 单一 SemVer 来源
- **Minor bump** = 向后兼容新增字段
- **Major bump** = 破坏性改动
- 所有下游通过 `pet-schema @ git+...@v1.3.0` 固定版本
- `BaseSample.schema_version` 每条记录都存，便于灾难恢复

### 3.7 迁移路径

- `PetFeederEvent` **保留**，挂在 `LLMAnnotation.parsed_output` 下（视觉 VLM 宠物事件解析走 LLM 范式）
- DB 通过 Alembic migration 渐进改造，已提交的 migration 不改，只新增（CLAUDE.md 约束）
- **Phase 2 债务还清**（2026.06 release）：Annotation 按 annotator_type 四表重建为破坏性 major bump（pet-schema v2.1.0 / pet-annotation v2.0.0），不写数据迁移脚本，旧 `vision_annotations` / `audio_annotations` 表整仓 drop + rebuild；历史快照靠 `git checkout <old-tag>` 可回溯

### 3.8 EvaluationReport（评估输出契约）

```python
# metric.py
class GateCheck(BaseModel):
    metric_name: str
    threshold: float
    comparator: Literal["ge", "le", "eq"]   # metric value vs threshold
    passed: bool
    actual_value: float

class EvaluationReport(BaseModel):
    report_id: str                          # content-addressed
    model_card_id: str                      # 被评估的模型
    evaluator_type: str                     # registry key
    dataset_uri: str
    metrics: list[MetricResult]             # 复用现有 MetricResult（Section 3 模块组织中声明保留）
    gate_checks: list[GateCheck]
    gate_status: Literal["passed", "failed", "pending"]
    artifacts: dict[str, str]               # 附加文件 uri（confusion matrix png / per-sample csv 等）
    evaluated_at: datetime
    clearml_task_id: Optional[str]
```

Gate 逻辑（pet-eval）消费 `gate_checks`，根据 `gate_status` 决定 recipe 是否继续。

### 3.9 Structured Config 契约（Hydra 目标类型）

```python
# configs.py
class ResourcesSection(BaseModel):
    gpu_count: int = 0
    gpu_memory_gb: int = 0
    cpu_count: int = 1
    estimated_hours: float = 1.0

class TrainerConfig(BaseModel):
    """Hydra `trainer/*.yaml` 组复合后的目标类型。"""
    type: str                               # registry key（跨仓 FQN，如 "pet_train.vlm_sft"）
    args: dict                              # plugin-specific；plugin 内部自己用 Pydantic 再校验
    resources: ResourcesSection

class EvaluatorConfig(BaseModel):
    type: str
    args: dict
    gates: list[GateCheck] = []             # recipe 可预先声明门限

class ConverterConfig(BaseModel):
    type: str
    args: dict
    calibration: Optional[ArtifactRef] = None

class DatasetConfig(BaseModel):
    type: str
    args: dict
    modality: Modality
```

**注意**：这一层做**外壳校验**（字段存在、类型、必填），不校验 `args` 内部语义 — 每个 plugin 在 `validate_config()` 里用自己的 Pydantic 做二次校验。两级校验避免了 pet-schema 和 plugin 实现的紧耦合。

---

## 4. Hydra 配置组合 & Recipe 实例

### 4.1 目录结构

```
pet-{repo}/
├── configs/
│   ├── _global_/defaults.yaml
│   ├── trainer/*.yaml
│   ├── dataset/*.yaml
│   ├── model/*.yaml
│   ├── metric/*.yaml
│   └── experiment/*.yaml          # 单仓 recipe

pet-infra/
└── recipes/                        # 跨仓 recipe
    ├── vlm_full_pipeline.yaml
    ├── audio_cnn_full_pipeline.yaml
    ├── cross_modal_fusion.yaml
    └── ablation/
        └── vlm_lora_sweep.yaml
```

### 4.2 组件级 config 示例

```yaml
# pet-train/configs/trainer/vlm_sft.yaml
type: pet_train.vlm_sft
args:
  base_model: Qwen/Qwen2-VL-1.8B-Instruct
  lora_r: 128
  lora_alpha: 32
  batch_size: 4
  gradient_accumulation_steps: 8
  learning_rate: 2e-5
  num_epochs: 3
  max_seq_length: 2048
resources:
  gpu_count: 1
  gpu_memory_gb: 24
```

### 4.3 单仓 Recipe 示例

```yaml
# pet-train/configs/experiment/vlm_sft_baseline.yaml
defaults:
  - /_global_/defaults
  - /trainer: vlm_sft
  - /dataset: pet_frames_sft
  - /model: qwen2_vl_1b
  - /metric: vlm_default
  - _self_

recipe:
  recipe_id: vlm_sft_baseline
  description: "VLM SFT baseline"
  scope: single_repo
  owner_repo: pet-train
  stages:
    - name: train
      component_registry: trainers
      component_type: ${trainer.type}
      inputs:
        dataset: {ref_type: dataset, ref_value: ${dataset.type}}
        base_model: {ref_type: model_card, ref_value: "qwen2_vl_1b_pretrained"}
      config_path: trainer/vlm_sft
      depends_on: []
  produces:
    - vlm_sft_v1
```

### 4.4 跨仓 Recipe 示例

```yaml
# pet-infra/recipes/vlm_full_pipeline.yaml
recipe:
  recipe_id: vlm_full_pipeline
  description: "完整 VLM 蒸馏 → SFT → DPO → 评估 → 量化 → 打包"
  scope: cross_repo
  required_plugins: [pet_train.trainers, pet_eval.evaluators, pet_quantize.converters]
  stages:
    - name: distill
      component_registry: trainers
      component_type: pet_train.vlm_distill
      inputs:
        dataset: {ref_type: dataset, ref_value: pet_frames_distill}
        teacher: {ref_type: model_card, ref_value: gpt4o_teacher_v1}
      config_path: trainer/vlm_distill
      depends_on: []
    - name: sft
      component_type: pet_train.vlm_sft
      inputs:
        dataset: {ref_type: dataset, ref_value: pet_frames_sft}
        base_model: {ref_type: recipe_stage_output, ref_value: distill}
      config_path: trainer/vlm_sft
      depends_on: [distill]
    - name: dpo
      component_type: pet_train.vlm_dpo
      inputs:
        dataset: {ref_type: dataset, ref_value: pet_pairs_dpo}
        sft_base: {ref_type: recipe_stage_output, ref_value: sft}
      config_path: trainer/vlm_dpo
      depends_on: [sft]
    - name: eval_trained
      component_registry: evaluators
      component_type: pet_eval.vlm_trained
      inputs:
        model: {ref_type: recipe_stage_output, ref_value: dpo}
      config_path: evaluator/vlm_trained
      depends_on: [dpo]
    - name: quantize
      component_registry: converters
      component_type: pet_quantize.vlm_rkllm_w4a16
      inputs:
        source: {ref_type: recipe_stage_output, ref_value: dpo}
        calibration: {ref_type: dataset, ref_value: pet_frames_calib}
      config_path: converter/vlm_rkllm_w4a16
      depends_on: [eval_trained]
    - name: eval_quantized
      component_type: pet_eval.vlm_quantized
      inputs:
        model: {ref_type: recipe_stage_output, ref_value: quantize}
      config_path: evaluator/vlm_quantized
      depends_on: [quantize]
  produces:
    - vlm_distill_v1
    - vlm_sft_v1
    - vlm_dpo_v1
    - vlm_dpo_v1_rkllm_w4a16
```

### 4.5 跨模态融合 Recipe

```yaml
# pet-infra/recipes/cross_modal_fusion.yaml
recipe:
  recipe_id: cross_modal_fusion
  description: "视觉×听觉 cross-attention 融合；上游两个已训练模型"
  scope: cross_repo
  stages:
    - name: fuse_train
      component_type: pet_train.cross_modal_fusion
      inputs:
        vision_backbone: {ref_type: model_card, ref_value: vlm_dpo_v1}
        audio_backbone: {ref_type: model_card, ref_value: audio_cnn_v2}
        dataset: {ref_type: dataset, ref_value: pet_synced_av_clips}
      config_path: trainer/cross_modal_fusion
      depends_on: []
```

### 4.6 消融 Recipe

```yaml
# pet-infra/recipes/ablation/vlm_lora_sweep.yaml
# variations 是唯一声明源；pet-infra 编译成等价的 Hydra --multirun 调用
# （不要在同文件再写 hydra.sweeper.params，会被覆盖）
defaults:
  - /vlm_full_pipeline
  - _self_

recipe:
  variations:
    - name: lora_r_sweep
      stage: sft
      hydra_path: trainer.args.lora_r
      values: [32, 64, 128, 256]
    - name: lora_alpha_sweep
      stage: sft
      hydra_path: trainer.args.lora_alpha
      values: [16, 32, 64]
      link_to: lora_r_sweep                 # pairwise — 不做笛卡尔积
```

### 4.7 Structured Configs（Hydra × Pydantic 桥）

```python
# pet-infra/src/pet_infra/hydra_plugins/structured.py
from hydra.core.config_store import ConfigStore
from pet_schema import ExperimentRecipe, TrainerConfig, DatasetConfig

cs = ConfigStore.instance()
cs.store(group="recipe", name="base", node=ExperimentRecipe)
cs.store(group="trainer", name="base", node=TrainerConfig)
cs.store(group="dataset", name="base", node=DatasetConfig)
```

---

## 5. 执行流、数据流与错误处理

### 5.1 端到端执行时序

```
[1] pet-infra CLI: 解析 args，定位 recipe 文件
[2] Hydra compose: 合成 recipe + defaults + overrides → resolved_config
[3] Pydantic validate: fail-fast 校验
[4] Plugin discovery: 按 required_plugins 触发 entry_points
[5] Resource preflight: 累加 ResourceSpec vs. 环境
[6] DAG 生成 + 拓扑排序
[7] DVC 顶层 dvc.yaml 生成/更新
[8] ClearML Pipeline Task 建立
[9] 逐 stage dvc repro → REGISTRY.build → component.fit/eval/convert → ModelCard 落盘
[10] 聚合所有 ModelCard → manifest.json → pet-ota 消费
[11] ClearML Pipeline Task 完成
```

### 5.2 数据流不变量

- 每个仓只读上游 schema，写下游 schema + 自己域内 DB
- ModelCard 是训练 / 量化的必产物，没有 ModelCard 的 checkpoint 不能进入下一 stage
- 所有 artifact URI 必须能被 `STORAGE.build(uri)` 解析

### 5.3 三工具职责边界

| 职责 | 归属 | 不做的事 |
|---|---|---|
| 配置组合 / override / multirun | Hydra | 不执行、不 cache |
| 类型校验 | Pydantic (pet-schema) | 不做 config 组合 |
| 依赖追踪 / cache / 离线复现 | DVC | 不做 UI |
| 实验对比 UI / 血统图 / registry | ClearML | 不做 cache |
| Plugin dispatch | Registry (mmengine) | 不做配置解析 |
| 跨仓编排 / CLI / recipe 解析 | pet-infra | 不碰模型代码 |

### 5.4 Fail Fast 原则

preflight 阶段（< 10 秒）必须拦截：
- Hydra config 语法错
- 字段类型 / 缺失（Pydantic）
- 未注册的 plugin type
- 资源不足
- 上游 ModelCard 不存在
- DVC 依赖图有环
- storage_uri scheme 未注册

### 5.5 Stage 级失败策略

- 默认 **fail-stop**
- ClearML Task 标记 failed，父 Pipeline 保留部分状态
- DVC cache 不污染
- Recipe 可声明 `on_failure: stop | continue | abort`

### 5.6 Idempotence & Resume

- `pet run --resume` 读 `.dvc/tmp/recipe_state.json`
- ModelCard `id = {recipe_id}_{stage}_{resolved_config_sha[:8]}` — content-addressed 天然幂等

### 5.7 外部依赖容错

- API 调用走 `pet-infra/retry.py` 的 tenacity 重试
- ClearML 不可达 → offline 模式，事后补传
- DVC remote 不可达 → 本地 cache 可继续

### 5.8 日志 & 追溯

- 结构化 JSON 日志（CLAUDE.md 约束）
- 每条日志带 `trace_id = clearml_task_id`
- 失败自动 dump `resolved_config.yaml` + 100 条日志 + stack trace 到 `.dvc/tmp/failure_<timestamp>/`

---

## 6. 跨仓 CI、Plugin 发现、版本治理

### 6.1 Plugin 发现分层

| 场景 | 机制 | 触发 |
|---|---|---|
| 生产运行 | setuptools entry_points | CLI 启动时 |
| 开发 / CI 测试 | 显式 required_plugins 列表 | recipe 声明 |
| 单元测试 | fixture 手动 register | 测试 setup |

### 6.2 版本治理

#### pet-schema SemVer 规则

| 变更类型 | 版本号 | 下游动作 |
|---|---|---|
| 增加可选字段 | Patch/Minor | 无动作 |
| 新增必填字段 | Minor（带 default）/ Major（无 default） | 重新 pin + 可能迁移 |
| 删除 / 改类型 | Major | 强制升级 |
| 改 enum 值 | Major | 数据迁移 |

#### 依赖 pin 规则

所有下游 `pyproject.toml`：

```toml
dependencies = [
    "pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@v1.3.0",
    "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.1.0",
]
```

**禁止 `@main` / `@dev`**（CLAUDE.md 已约束）。

#### 兼容性矩阵

`pet-infra/docs/compatibility_matrix.yaml` 作为单一 truth：

```yaml
releases:
  - release: "2026.05"
    pet_schema: "1.3.0"
    pet_infra: "2.1.0"
    pet_data: "1.4.0"
    pet_annotation: "1.2.0"
    pet_train: "2.0.0"
    pet_eval: "1.5.0"
    pet_quantize: "1.3.0"
    pet_ota: "1.2.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
```

`pet run` 启动时自检：版本 vs. 矩阵，不匹配 warn（可配置 fail）。

### 6.3 CI 拓扑

继承现有：`pet-schema → pet-data → pet-annotation → pet-train → pet-eval → pet-quantize → pet-ota`，`repository_dispatch` 触发全链 CI。

新增 pet-infra CI job：
- `schema-validation`：组装 compatibility_matrix，校验跨仓版本兼容
- `plugin-discovery`：安装所有仓 → `pet list-plugins` → 校验注册 / 无冲突 / ABC 实现
- `recipe-dry-run`：对 `pet-infra/recipes/` 下每个 recipe 跑 preflight
- `smoke-e2e`：最小 recipe 跨 3 仓跑通（1 步 SFT / tiny 数据集 / 1 epoch）→ 产出 ModelCard → pet-ota 消费

各子仓共享的 `plugin-contract` job：
- 安装本仓 + pet-infra + pet-schema
- `pet list-plugins --package=<repo>`
- 对每个 plugin：实例化 / 检查 ABC 签名 / 跑 validate_config unit test

强制规则：任何新 plugin 必须随附 `tests/plugins/test_<name>.py`。

### 6.4 Release 流程

```
feature/* → dev (单仓) → CI schema-validation + plugin-contract
pet-schema dev → main (触发 repository_dispatch)
pet-infra integration + smoke-e2e → [Phase 5 起自动化] 自动 open PR 更新下游 pin
(Phase 1-4 期间：人工执行下游 pin 更新，CI 只做校验)
下游仓 feature → dev → main
全部 main 对齐 → pet-infra 更新 compatibility_matrix.yaml
打 release tag: release-2026.05
```

**release tag 不是单仓 tag，而是 compatibility_matrix 快照**。`pet run --release=2026.05` 锁定快照。

### 6.5 测试策略分层

| 层级 | 位置 | 范围 |
|---|---|---|
| 单元 | 各仓 `tests/unit/` | 单 plugin / 单 metric / 单 converter |
| 契约 | 各仓 `tests/contract/` | plugin 实例化 + ABC 方法存在性 + Pydantic 序列化 |
| 集成 | pet-infra `tests/integration/` | 2~3 仓组合：`fit() → eval()` / `convert() → manifest` |
| E2E smoke | pet-infra `tests/e2e/smoke/` | 最小 recipe 跑通 |
| E2E 完整 | pet-infra `tests/e2e/full/` | 真实完整 recipe（夜间 / 手动） |
| 硬件 | pet-quantize `tests/rk3576/` | 真机延迟 / 精度（CLAUDE.md 约束） |

**关键约束**：
- 契约测试**禁止 mock Registry**（用户 "No Manual Workaround" memory 的落实）
- 集成测试必须用真实 Pydantic 序列化 / 反序列化，不手写 dict
- E2E smoke 每 PR 都跑，是 merge 到 dev 的最低门槛

### 6.6 依赖管理

- `pet-infra/requirements/base.in` 是"运行时根依赖"的 single source
- 下游仓 `requirements.in` 通过 `-r ../pet-infra/requirements/base.in` 共享根依赖
- CI 检查 requirements.txt 的 pet-infra / pet-schema 版本必须 match compatibility_matrix

---

## 7. 迁移分期、风险控制与验收

### 7.1 迁移总策略

**Strangler Pattern**：新旧架构不并存运行，按**单仓单向切换**推进。Contract 先行 → 风险最小仓先做 → 核心生产仓中期 → 端侧 / 部署仓最后。

**沉默成本不计入**（用户决策）：不做新旧并存长跑，clean break 推进。

### 7.2 Phase 1: Foundation（根基）

**仓库**：pet-schema + pet-infra

**交付**：
- pet-schema 新增 BaseSample / BaseAnnotation / ModelCard / ExperimentRecipe / 适配器
- pet-infra 新增 Registry / 6 个 Base ABC / BaseStorage + LocalStorage / `pet run` CLI 骨架 / Hydra plugin
- pet-infra `recipes/` 建立 + 1 个 smoke recipe
- CI：pet-infra integration / schema-validation / recipe-dry-run

**验收**：
- `pet list-plugins` 跑通
- smoke recipe 过 preflight
- pet-schema 打 `v2.0.0` tag

**风险**：不影响现有生产流程

### 7.3 Phase 2: Data & Annotation

**仓库**：pet-data + pet-annotation（并行）

**状态**：shipped 2026-04-21（release `2026.05`：pet-data v1.1.0 / pet-annotation v1.1.0 / pet-infra v2.1.0）→ **债务还清归 release `2026.06`**（见 `2026-04-21-phase-2-debt-repayment-design.md`）

**交付（债务还清后最终形态）**：
- 手写 SQL migration 增加 `modality` / `storage_uri` 列（pet-data 用 glob+sort 驱动，非 Alembic）
- `FrameRecord` 迁移为 `VisionSample`；新增 `AudioSample` 建表
- AnnotationRecord **按 annotator 范式拆 4 张表**（`llm_annotations` / `classifier_annotations` / `rule_annotations` / `human_annotations`），详见 §3.3；**不按 modality 拆**
- CLI Hydra 化 + 注册 4 个 Dataset plugin（`pet_annotation.llm` / `classifier` / `rule` / `human`）+ pet-data 的 `vision_frames` / `audio_clips`
- peer-dep 约定落地：下游 pet-data / pet-annotation 不在 pyproject 声明 pet-infra，`_register.py` fail-fast（详见 §2.6）

**验收**：
- 破坏性 rebuild（fixture-only，无生产数据迁移脚本）；pet-annotation bump 为 major version `v2.0.0`
- 每个 Sample / Annotation 字段能往返 Pydantic serialize / deserialize（Discriminator 按 `annotator_type` 路由）
- 新 CLI 能用 Hydra override
- `pet run recipe=pet_data_ingest_smoke` 跑通
- `compatibility_matrix.yaml` 登记 `2026.06` release

**风险**：schema drop + rebuild 破坏本地 dbfile → README 明示"v2.0.0 需重建 DB"；LS 模板同步

### 7.4 Phase 3: Training

**仓库**：pet-train

**交付**：
- VLM SFT / DPO / distill 改 `@TRAINERS.register_module()` plugin（内部仍用 LLaMA-Factory）
- audio CNN 改 plugin（内部仍用 Lightning）
- 硬编码模型名从 plugin args 拿
- W&B → ClearML
- `pet-train/configs/` 建立

**验收**：
- `pet run recipe=vlm_sft_baseline` 在小数据集跑通，指标对齐历史
- `pet run recipe=audio_cnn_finetune` 跑通
- ClearML UI lineage + metrics 可见
- 旧 CLI 入口删除

**风险**：LLaMA-Factory 参数语义 1:1 覆盖；替换前后 baseline 指标对比作验收门

### 7.5 Phase 4: Eval + Quantize

**仓库**：pet-eval + pet-quantize（并行）

**交付**：
- pet-eval 3 subcommand 合并为 `pet-eval run`
- Metric / Evaluator 全部 plugin 化
- Gate 消费 `EvaluationReport` + recipe 声明门限
- pet-quantize 的三元组硬编码删除；每种 convert 变 plugin
- 真机验收 gate 保持（CLAUDE.md）

**验收**：
- `pet run recipe=vlm_full_pipeline` 跨仓跑通
- ModelCard 血统图在 ClearML 完整呈现
- 量化后真机延迟 / 精度与老 pipeline 对齐（≤2% 公差）

**风险**：RKLLM / RKNN SDK 版本封装；老 params.yaml 不再兼容

### 7.6 Phase 5: OTA + E2E + W&B 下线

**仓库**：pet-ota + pet-infra（收官）

**交付**：
- pet-ota 打包改为纯读 `ModelCard.to_manifest_entry()`
- `compatibility_matrix.yaml` 首个 release 发布
- W&B 依赖从所有仓移除，项目归档
- 跨模态融合 recipe 作为"第二模型家族"示例跑通
- **融合策略走 plugin**：在现有 `EVALUATORS` 注册表上增加 fusion 策略 plugin（如 `single_modal` / `and_gate` / `weighted` / `learned_fusion`），recipe 通过 `fusion._target_` 字段声明使用哪一种；跨模态消融通过 `pet run recipe=prod -m fusion=vlm_only,audio_only,and_gate,weighted` 一条命令覆盖

**验收**：
- 跨仓 full E2E 全链绿
- RK3576 真机灰度部署一次 release（VLM + Audio CNN 同 manifest）
- `pet run recipe=cross_modal_fusion` 成功
- **至少 2 个 fusion plugin 可互换**（如 `single_modal` 和 `and_gate`），ClearML 跨模态消融实验一次跑通
- `DEVELOPMENT_GUIDE.md` 更新（CLAUDE.md "Sync DEVELOPMENT_GUIDE" memory）

### 7.7 风险登记册

| 风险 | 影响 | 缓解 |
|---|---|---|
| pet-schema 接口 Phase 2-4 期间二次调整 | 下游返工 | Phase 1 结束设 schema freeze，后续改动 Major bump + compatibility matrix |
| LLaMA-Factory 升级破坏 Trainer plugin 内部 | 训练出错 | plugin 内部 pin LLaMA-Factory 版本 |
| ClearML 自部署服务宕机 | 实验记录丢 | offline mode + S3 备份 ClearML fileserver |
| Hydra + DVC edge case | 奇怪 bug | Phase 1 引入最小 recipe smoke test，每 CI push 跑 |
| 多仓 PR 顺序错 | 版本错乱 | compatibility_matrix CI job 强制校验 |
| 切换期间生产 release 需求 | 老架构维护成本 | Phase 1-4 允许老路径 hotfix，不允许加新功能；Phase 5 后物理删除老代码 |
| Alembic migration 数据丢失 | 历史数据不可读 | migration 前 dump full DB → S3；migration 后 select count(*) diff |
| Audio CNN 新架构精度回退 | plugin 实现不忠实 | Phase 3 验收门：相同 config 替换前后 top-1 精度 ≤0.5% |
| 真机延迟回退 | 量化 plugin 实现偏差 | Phase 4 验收：RK3576 相同 input 延迟 ±2% |

### 7.8 每阶段 Definition of Done

- PR 按 CLAUDE.md 流程：`feature/* → dev → main`
- CI 全绿（含新增 contract / plugin-discovery / recipe-dry-run）
- `DEVELOPMENT_GUIDE.md` 对应章节同步更新
- `compatibility_matrix.yaml` 更新（版本 bump 时）
- 至少一个 smoke e2e 跑通并落 ClearML 记录
- 迁移的功能在 ClearML / `pet list-plugins` 可见

### 7.9 YAGNI — 不在本次重构范围

- ❌ Kubernetes / ClearML Queue 调度（单机足够，`estimate_resources` 留接口即可）
- ❌ S3 / WebDataset 真实实现（BaseStorage ABC 留接口，LocalStorage 外仅占位）
- ❌ 第三方 plugin 包机制（entry_points 支持，不主动发展生态）
- ❌ ClearML Pipeline 自动触发 / scheduler（人工 `pet run` 足够）
- ❌ 多租户 / 权限隔离

---

## 8. 决策溯源

### 8.1 关键决策

| 决策 | 选项 | 选择 | 依据 |
|---|---|---|---|
| Registry 范式 | A 收敛 / B 完整 plugin registry / C 折中 | **B** | 用户希望一步到位，可扩展 + yaml 控制 |
| 实验追踪 | 现状 / MLflow / ClearML / 自建 | **ClearML 全替换 + pet-schema ModelCard contract** | 用户要求跨管线可视化对比；沉默成本不计入 |
| 配置系统 | Hydra+Pydantic / params.yaml+DVC exp / ClearML HPO | **Hydra + pet-schema Pydantic + DVC 执行 + ClearML 可观测** | 用户要求便于控制变量实验 / 面向工程 |
| 数据契约 | ABC / 扁平 / HF Features / 混合 | **D: BaseSample ABC + 子类 + HF/WebDataset 适配器 + ModelCard + ExperimentRecipe** | 类型安全 + HF 生态兼容 + 未来扩展 |
| 编排入口 | 每仓自治 / pet-infra 中心化 / 新增 orchestrator 仓 | **B: pet-infra 中心化 + 单仓/跨仓两级 recipe** | pet-infra 已是横切仓；避免新增仓；两级分离支持开发与生产场景 |

### 8.2 Registry 层级（Architecture Rule）

**核心架构规则**：抽象单元是 **capability**（train / eval / quantize / deploy / load），**不是 model**。每个 capability 有一个接口 ABC；每个模型家族提供一个实现 plugin。基础设施代码只调用接口，不 branch 在 model type。

Registry 放在能力边界，不穿透训练引擎内部：
- LLaMA-Factory / PyTorch Lightning 是 Trainer plugin 的**内部实现**
- Registry 层只暴露 Trainer 接口，不暴露框架细节

### 8.3 参考资料

- [MMEngine Registry](https://mmengine.readthedocs.io/en/latest/advanced_tutorials/registry.html)
- [Hydra Structured Configs](https://hydra.cc/docs/tutorials/structured_config/intro/)
- [DVC Pipelines](https://dvc.org/doc/user-guide/pipelines/defining-pipelines)
- [ClearML Pipelines](https://clear.ml/docs/latest/docs/pipelines/pipelines/)
- [HuggingFace Dataset Features](https://huggingface.co/docs/datasets/about_dataset_features)
- [Python Packaging entry_points](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Pydantic v2 Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)

---

## 9. 下一步

本 spec 通过审阅并存档后，进入 writing-plans，按 5 个 Phase 分别产出实施计划：

1. `2026-04-20-phase-1-foundation-plan.md`
2. `2026-04-20-phase-2-data-annotation-plan.md`
3. `2026-04-20-phase-3-training-plan.md`
4. `2026-04-20-phase-4-eval-quantize-plan.md`
5. `2026-04-20-phase-5-ota-e2e-plan.md`

每个 Phase plan 产出后按单仓 PR 策略（`feature/* → dev → main`）推进实施。

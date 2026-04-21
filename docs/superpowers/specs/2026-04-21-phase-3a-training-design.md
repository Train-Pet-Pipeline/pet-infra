# Phase 3A Training — Design Spec

**状态**: draft → pending-review
**日期**: 2026-04-21
**范围**: Phase 3A（train + eval + orchestrator 实装 + ClearML）
**不含**: Phase 3B（quantize + ota，另立 spec）
**北极星**: `pet-infra/docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md` §0.2.1
**前置完成**: Phase 1 Foundation + Phase 2 Data/Annotation + Phase 2 Debt Repayment

---

## 0. 目标与约束

### 0.1 目标

1. 把 pet-train / pet-eval 从 v1 shell 脚本 + wandb 的形态重构为 pet-infra 6 registries 下的 plugin
2. 把 pet-infra 的 `pet run` 从 placeholder 实装为真串行 DAG 执行器（含 resume + cache + multirun）
3. 用 ClearML 替换 wandb，支持 offline / SaaS / self-hosted 三档
4. 落地 DEBT-4（Phase 2 遗留）：PHASE_DOD_TEMPLATE + 四维北极星自检
5. matrix 新增 `2026.07` 行锁全链 Phase 3A 发布版本

### 0.2 硬约束

- 破坏性重构（feedback_refactor_no_legacy）：v1 代码全删，无兼容层，major bump
- PR workflow（feedback_pr_workflow）：feature/* → dev → main，每仓独立链
- 共享 conda env（feedback_env_naming）：`pet-pipeline`，不建 per-repo env
- 所有数值从 params.yaml（CLAUDE.md）
- pet-schema 是 schema 唯一来源（CLAUDE.md）
- peer-dep §11 约定（Phase 2 Debt Repayment 已建立）

### 0.3 决策标尺

任何架构岔路在四个维度上打分（1-5）：**可插拔性 / 灵活性 / 可扩展性 / 可对比性**（详见 §0.2.1 source spec）。低于 3 分 rework。

---

## 1. 架构概览与仓库边界

### 1.1 交付仓库

| 仓库 | 版本 | 变更性质 | 说明 |
|------|------|---------|------|
| pet-train | v2.0.0 | BREAKING | 删 v1 shell / kl_distill / wandb；plugin 化 TRAINERS + METRICS |
| pet-eval | v2.0.0 | BREAKING | 删 v1 shell / wandb；plugin 化 EVALUATORS + METRICS；引 AudioEvaluator |
| pet-infra | v2.3.0 | minor | matrix 2026.07 + ClearML stack + pet run 实装 + PHASE_DOD_TEMPLATE |
| pet-schema | (未动) | - | ModelCard v2.1.0 冻结 |

### 1.2 非目标（Non-Goals）

- pet-quantize / pet-ota v2 重构（归 Phase 3B）
- AudioTrainer（无训练数据 driver）
- AudioHumanReview（归 pet-annotation scope，driver 未到）
- 分布式训练（LLaMA-Factory 内置 DDP 够用，orchestrator 不负责）
- Hydra parallel launcher（joblib / submitit，v2.3 显式拒绝，未来版本考虑）
- W&B 双轨或兼容层

### 1.3 Plugin 注册总览

| Registry（pet-infra） | Plugin（3A 新增） | 所属仓库 |
|----------------------|-------------------|---------|
| TRAINERS | LlamaFactorySFTTrainer / LlamaFactoryDPOTrainer / TinyTestTrainer | pet-train |
| EVALUATORS | VLMEvaluator / AudioEvaluator | pet-eval |
| METRICS | bleu / rouge_l / meteor / bertscore / hallucination_rate / instruction_adherence / safety_score / mos / audio_accuracy | pet-eval |
| CONVERTERS | (Phase 3B) | - |
| DATASETS | (复用 Phase 2) | pet-data / pet-annotation |
| STORAGE | (复用 Phase 1) | pet-infra |
| experiment_logger (新 ABC) | ClearMLLogger / NullLogger | pet-infra |

### 1.4 核心执行路径

```
recipe.yaml
  → Hydra compose
  → ExperimentRecipe Pydantic 校验（pet-schema）
  → build_dag (train → eval → [quantize 3B])
  → 串行 in-process 执行每个 stage
      ↳ precompute_card_id = id_stage_sha[:8]
      ↳ cache.has(card_id) ? load : run plugin
      ↳ ClearMLLogger 同步 task
      ↳ cache.save(card)
  → 汇总 + exit code
```

### 1.5 层职责

| 层 | 职责 |
|----|------|
| Hydra | 配置组合 + multirun `-m` |
| pet-schema | Pydantic 校验 ModelCard / ExperimentRecipe |
| pet-infra | registry 解析 + DAG 串行 + cache + DVC stage 写入 |
| ClearML | experiment 可观测 + artifact 镜像 |

---

## 2. pet-train v2.0.0 组件设计

> **基线审计**：本节的删除/保留/移动清单基于 2026-04-21 pet-train main HEAD 真实文件结构。PR #A 首步需 `git ls-files` 做最终审计并把清单 commit 为 PR 附件。

### 2.1 删除清单（破坏性）

**scripts/**（全目录删）
- `scripts/train_sft.sh` / `scripts/train_dpo.sh` / `scripts/train_audio.sh`
- `scripts/collect_logits.sh` / `scripts/merge_lora.sh` / `scripts/eval_after_train.sh`

**src/pet_train/**（v1 实现）
- `kl_loss.py`（v1 KL 蒸馏 loss，3A 无蒸馏需求）
- `logits_provider/`（配套 kl_loss 的 teacher logits 提供器）
- `schema_compliance_callback.py`（Transformer callback 形式的 schema 校验；v2 由 pet-eval `schema_compliance` metric 在评估侧负责，不在训练 callback 里做）
- `audio_model.py`（audio 训练 CLI 顶层入口，v2 仅保留零样本推理路径）

**configs/**（顶层）
- `configs/base/sft_base.yaml` / `configs/base/dpo_base.yaml`
- `configs/experiments/sft_lora_r16_lr2e4_ep3.yaml` / `configs/experiments/dpo_user_feedback_v1.yaml`
- `configs/audio/mobilenetv2_transfer_v1.yaml`
  → 这些 YAML 的数值约定迁入 `params.yaml` + Hydra `pet_train/plugins/<name>/conf/` defaults

**pyproject.toml**
- 删 `wandb` 依赖
- 删旧 CLI entry_points（`pet-train` 入口改为由 `pet run` 取代，不保留独立 CLI）

### 2.2 保留与迁移

| 项 | 现路径 | v2 去向 |
|----|--------|---------|
| LLaMA-Factory submodule | `vendor/LLaMA-Factory` | 原地不动 |
| PANNs 零样本推理 | `src/pet_train/audio_inference.py` | 移入 `src/pet_train/audio/inference.py`（命名空间化，供 AudioEvaluator 跨仓 import） |
| PANNs 模型架构定义 | `src/pet_train/audio_model_arch.py` | 移入 `src/pet_train/audio/arch.py` |
| 音频前处理 | `src/pet_train/audio_transforms.py` | 移入 `src/pet_train/audio/transforms.py` |

迁移后 `pet-eval/plugins/audio_evaluator.py` 从 `pet_train.audio.inference import ...`（§5.3 样板）。

### 2.3 新增 plugin 结构

```
src/pet_train/plugins/
├── _register.py              # entry-point: register_all
├── llamafactory_sft.py       # LlamaFactorySFTTrainer (BaseTrainer)
├── llamafactory_dpo.py       # LlamaFactoryDPOTrainer
├── tiny_test.py              # TinyTestTrainer (CPU smoke, ~100K params)
└── metrics/                  # train 侧 metrics（loss/grad_norm/lr 透传 ClearML）
```

### 2.4 LlamaFactorySFTTrainer 骨架（~300 LOC）

```python
@TRAINERS.register_module()
class LlamaFactorySFTTrainer(BaseTrainer):
    def build(self, cfg: TrainerConfig) -> None:
        self._lf_args = self._hydra_to_lf_args(cfg)

    def train(self, recipe: ExperimentRecipe) -> ModelCard:
        from llamafactory.train.sft.workflow import run_sft
        run_sft(**self._lf_args)
        return self._build_model_card(recipe, checkpoint_uri=self._adapter_uri)
```

### 2.5 ModelCard 产出约定

- `arch` string：`qwen2vl_2b_lora_r16_a32` 格式
- `checkpoint_uri`：LoRA adapter 目录 URI（HF/PEFT 约定），如 `s3://...` / `file:///...`
- `gate_status`：Trainer 落 `pending`，Evaluator 回写
- `parent_models`：list；DPO 场景填 SFT base card id

### 2.6 peer-dep §11 合规

- `pyproject.toml` 不 pin pet-infra
- `_register.py` fail-fast guard（import pet-infra / pet-train 失败给 matrix 提示）
- CI 四步装序

### 2.7 matrix 2026.07 依赖锁

- `pet-schema==2.1.0`
- `torch==2.3.x`（LLaMA-Factory 兼容线）
- `transformers==4.45.x`（Qwen2-VL 支持线）
- `clearml==1.16.x`

### 2.8 params.yaml 新增

```yaml
train:
  lora_r: 16
  lora_alpha: 32
  lr: 1.0e-4
  batch_size: 4
  grad_accum: 4
  max_steps: 1000
```

> Gate 阈值见 §3.8（统一放 pet-eval 管辖的 gate namespace，避免 train/eval 分两处维护）。

---

## 3. pet-eval v2.0.0 组件设计

> **基线审计**：本节对照 2026-04-21 pet-eval main HEAD 真实结构（`src/pet_eval/{metrics,runners,gate,inference,report}/`，无顶层 `scripts/` 或 `configs/`）。PR #A 首步同 pet-train：`git ls-files` 审计 commit 为附件。

### 3.1 删除清单

**src/pet_eval/**（v1 实现）
- `cli.py` + `__main__.py`（旧 CLI 入口，被 `pet run` 取代）
- `runners/eval_trained.py` / `runners/eval_audio.py`（顶层 runner 入口，逻辑融入 VLMEvaluator / AudioEvaluator plugin）
- `runners/eval_quantized.py`（整文件删；Phase 3B 在 pet-quantize + pet-eval 之间按 QuantizedModelEvaluator plugin 重建）
- `report/generate_report.py` 中的 wandb inline 调用段（整文件保留但抽掉 wandb，改由 ClearMLLogger 推送；v2 或直接删除本文件若不再需要独立 report）
- `pyproject.toml` 的 `wandb` 依赖

**scoped-in（分支）**
- `fix/eval-prompt-alignment` 分支功能合入 v2.0.0 首 PR（不单独留存）

> `src/pet_eval/{gate,inference}/` 两目录如被 plugin 内化后成为空壳，同步删除（由 PR 审计决定）。

### 3.2 保留（移入 plugin 内部）

- **8 个现有 metric**（pet feeder 业务特定，非通用 VLM 基准）：
  - `anomaly_recall` — 喂食异常事件召回率
  - `calibration` — 置信度校准（ECE / brier）
  - `kl_quantization` — 量化前后输出分布 KL 距离
  - `latency` — 端到端推理延迟（RK3576 实测）
  - `mood_correlation` — 生成情绪描述与人工标注相关性
  - `narrative_quality` — 叙事质量（多维 rubric）
  - `schema_compliance` — 输出 JSON 结构符合 pet-schema 比例
  - `audio_accuracy` — PANNs 零样本分类 top-1（保留新增形态）
- `runners/eval_audio.py` 核心逻辑 → AudioEvaluator plugin 内部方法
- `runners/eval_trained.py` 核心逻辑（除 wandb 记录段）→ VLMEvaluator plugin 内部方法

### 3.3 新增 plugin 结构

```
src/pet_eval/plugins/
├── _register.py
├── vlm_evaluator.py          # VLMEvaluator (BaseEvaluator)
├── audio_evaluator.py        # AudioEvaluator (BaseEvaluator)
└── metrics/                  # 8 metric 逐文件（与 v1 同名，逐字迁移）
    ├── anomaly_recall.py
    ├── calibration.py
    ├── kl_quantization.py
    ├── latency.py
    ├── mood_correlation.py
    ├── narrative_quality.py
    ├── schema_compliance.py
    └── audio_accuracy.py
```

### 3.4 Evaluator 接口合同

```python
class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        model_card: ModelCard,
        recipe: ExperimentRecipe,
    ) -> tuple[dict[str, float], GateResult]:
        """
        Returns:
            metrics: 指标 dict（合并入 card.metrics）
            gate: GateResult(passed, reason, thresholds)
        """
```

Orchestrator 拿到 `(metrics, gate)` 后：
- `card.metrics.update(metrics)`
- `card.gate_status = "passed" if gate.passed else "failed"`
- 覆盖写入 stage cache（替换 Trainer 落的 pending card）

### 3.5 AudioEvaluator 设计

- 零样本 PANNs（5 类：eating / drinking / vomiting / ambient / other）
- 从 pet-train `pet_train.audio.inference` import（v2 迁移后路径；v1 位于 `pet_train.audio_inference`，pet-train PR 先做文件 rename，见 §2.2）
- 输入：`AudioClips` dataset plugin（pet-data v1.2.0 提供）
- 指标：`audio_accuracy`（top-1）+ per-class precision/recall
- 独立 gate：`min_audio_accuracy: 0.60`

### 3.6 Metric plugin 粒度

- 每个 metric 单文件，注册到 METRICS
- Evaluator 用 `METRICS.module_dict[name]` 按 recipe `evaluator.metrics: [...]` 查表
- 允许 recipe 自定义 metric 组合

### 3.7 peer-dep §11 合规

同 pet-train。另：pet-eval 声明 `pet-train` 作为 runtime dep（§5.3 样板）。

### 3.8 params.yaml 新增

```yaml
eval:
  batch_size: 8
  max_samples: 500

gate:                              # release 默认（严苛）— 由 pet-eval 统一拥有
  min_anomaly_recall: 0.80
  max_calibration_ece: 0.10
  max_kl_quantization: 0.05
  max_latency_ms_p95: 2000
  min_mood_correlation: 0.60
  min_narrative_quality: 3.0       # 0-5 rubric 平均
  min_schema_compliance: 0.95
  min_audio_accuracy: 0.60

smoke:                             # smoke_tiny 专用放宽（§7.4）
  min_anomaly_recall: 0.0
  max_calibration_ece: 1.0
  max_kl_quantization: 1.0
  max_latency_ms_p95: 999999
  min_mood_correlation: 0.0
  min_narrative_quality: 0.0
  min_schema_compliance: 0.0
  min_audio_accuracy: 0.0
```

> 具体阈值数值由 pet-eval v1 历史数据 + 业务团队签核确定；本 spec 只锁 key 名与命名空间。

---

## 4. pet-infra v2.3.0 组件设计

### 4.1 matrix 2026.07

对齐现 `compatibility_matrix.yaml` 结构（list of release objects）：

```yaml
releases:
  # ... 2026.05-phase1 / 2026.05 / 2026.06 保持不动 ...

  - release: "2026.07"
    pet_schema: "2.1.0"
    pet_infra: "2.3.0"
    pet_data: "1.2.0"
    pet_annotation: "2.0.0"
    pet_train: "2.0.0"
    pet_eval: "2.0.0"
    # pet_quantize / pet_ota 延 Phase 3B 重构，2026.07 维持 placeholder
    pet_quantize: "0.1.0"
    pet_ota: "0.1.0"
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
```

> 2026.07 为 Phase 3A 发布锚。`clearml / mmengine_lite / hydra_core` 约束沿用 2026.06。

### 4.2 experiment_logger ABC + plugin

```
src/pet_infra/experiment_logger/
├── __init__.py              # 导出 ABC + factory
├── base.py                  # ExperimentLogger ABC
├── clearml_logger.py        # ClearMLLogger (支持 offline / saas / self_hosted)
└── null_logger.py           # NullLogger (unit test / 完全不记)
```

```python
class ExperimentLogger(ABC):
    @abstractmethod
    def start(self, recipe: ExperimentRecipe, stage: str) -> str | None:
        """Returns task_id (None for NullLogger)."""

    @abstractmethod
    def log_metrics(self, metrics: dict[str, float], step: int | None = None): ...

    @abstractmethod
    def log_artifact(self, name: str, uri: str): ...

    @abstractmethod
    def log_model_card(self, card: ModelCard): ...

    @abstractmethod
    def finish(self, status: Literal["success", "failed"]): ...
```

### 4.3 ClearML 三档 mode

```yaml
experiment_logger:
  name: clearml
  mode: offline | saas | self_hosted     # 默认 offline（本地 dev 友好）
  api_host: ${oc.env:CLEARML_API_HOST,""}
  on_unavailable: strict | fallback_null | retry
```

| mode | 行为 | 适用场景 |
|------|------|---------|
| offline | `Task.set_offline(True)`，数据写 `~/.clearml/offline/{task_id}/`，可后续 `clearml-task --import-offline` | 本地 dev 默认 / PR smoke |
| saas | api_host → `https://api.clear.ml` | 零运维协作 |
| self_hosted | api_host → docker-compose 暴露端口 | release CI / 内网强要求 |

Release recipe CI 扫描禁止 `mode: offline`（和禁止 gate override 同一套校验）。

### 4.4 ClearML self-hosted stack

```
docker/clearml/
├── docker-compose.yml       # apiserver / webserver / fileserver / mongo / elastic / redis
├── .env.example
└── README.md

docker/wandb/                # 删除
```

默认端口：web `:8080` / api `:8008` / files `:8081`
本地 dev：`make clearml-up` / `make clearml-down`

### 4.5 pet run 实装

```
src/pet_infra/orchestrator/
├── runner.py                # pet run 入口
├── dag.py                   # stage 依赖解析 + 拓扑排序
├── cache.py                 # content-addressed card_id + lookup
└── stage_executor.py        # in-process 调 Trainer/Evaluator/Converter
```

**执行算法伪码**（复用 Phase 2 shipped `precompute_card_id(recipe_id, stage_name, config_sha)`）：

```python
from pet_infra.recipe.card_id import precompute_card_id

def pet_run(recipe_path: Path, resume: bool = True):
    cfg = hydra_compose(recipe_path)
    recipe = ExperimentRecipe.model_validate(cfg)
    logger = build_experiment_logger(cfg.experiment_logger)
    dag = build_dag(recipe.stages)

    prev_card = None
    for stage in dag.topological_order():
        config_sha = _hash_stage_config(stage, prev_card)  # §5.2 规则 4
        card_id = precompute_card_id(recipe.id, stage.name, config_sha)

        if resume and cache.has(card_id):
            prev_card = cache.load(card_id)
            continue

        task_id = logger.start(recipe, stage.name)
        plugin = registry_for(stage).build(stage.plugin_name, stage.config)
        try:
            card = plugin.run(input_card=prev_card, recipe=recipe)
            assert card.id == card_id, "plugin 必须把 card_id 写回 ModelCard.id"
        except Exception:
            logger.finish("failed")
            raise
        card.clearml_task_id = task_id
        logger.log_model_card(card)
        cache.save(card_id, card)
        logger.finish("success")
        prev_card = card


def _hash_stage_config(stage, prev_card) -> str:
    """sha256(canonical_json(stage_recipe_subtree) + prev_card.checkpoint_uri)"""
    import hashlib, json
    payload = json.dumps(stage.config, sort_keys=True, separators=(",", ":"))
    payload += (prev_card.checkpoint_uri if prev_card else "")
    return hashlib.sha256(payload.encode()).hexdigest()
```

**关键点**：
- `card_id` 在 stage 执行**前**由 orchestrator 算出，plugin 必须把它写回 `ModelCard.id`（非循环，因为 recipe_id + stage_name + config_sha 都在执行前已知）
- 保留 Phase 2 已发布的 `precompute_card_id(recipe_id, stage_name, config_sha)` 签名不动（向前兼容）
- `_hash_stage_config` 是 v2.3 新增的 helper，不改 card_id.py

### 4.6 Hydra multirun（-m）

- `pet run recipe.yaml -m train.lr=1e-4,3e-4,1e-3` delegate 给 Hydra sweeper
- 只允许 `basic` launcher（sequential）
- `joblib` / `submitit` 显式拒绝，error 消息指向"defer to future version"
- 每 trial 独立 card_id（sha 含所有 override）

### 4.7 PHASE_DOD_TEMPLATE.md

位置：`pet-infra/docs/PHASE_DOD_TEMPLATE.md`

```markdown
# Phase DoD Template v1

任何 Phase/子 Phase 结束前必须逐项勾选：

## 1. 代码交付
- [ ] 所有 PR merged 到 main
- [ ] 所有仓库 tag 到 matrix 行锁定版本
- [ ] compatibility_matrix.yaml 新行已提交

## 2. CI 全绿
- [ ] plugin-discovery / integration-smoke / compatibility-matrix-smoke

## 3. 测试
- [ ] 单测覆盖新 plugin
- [ ] smoke recipe 三档（tiny/mps/small）至少 tiny 在 PR gate 绿

## 4. 文档同步
- [ ] DEVELOPMENT_GUIDE.md 对应章节更新
- [ ] matrix_history 追加发布条目

## 5. North Star §0.2.1 自检（DEBT-4）
四维度各打分（1-5）并给证据：
- [ ] 可插拔性（Pluggability）：新模型/新 modality 是否只加 plugin 不改核心？
- [ ] 灵活性（Flexibility）：配置能否纯 Hydra override 不改代码？
- [ ] 可扩展性（Extensibility）：新增 registry 成员是否无需改 orchestrator？
- [ ] 可对比性（Comparability）：同一 recipe 切不同 plugin 指标同格式？

任一维度 < 3 分本 Phase 不通过，必须 rework。
```

- `CLAUDE.md` 追加指针（任何 Phase 结尾按此自检）
- `DEVELOPMENT_GUIDE.md §8` 追加指针

### 4.8 §11 peer-dep 文档微调

- §11.4 四步装序增加 ClearML secret 注入样例
- §11 新增"跨仓插件依赖"子节（pet-eval → pet-train.audio.panns_zero_shot 为样板）

---

## 5. 数据流与跨 stage 契约

### 5.1 端到端数据流

```
recipe.yaml
  └→ Hydra compose → ExperimentRecipe 校验
        └→ DAG: [train] → [eval]
              ├→ Stage 1: train
              │    inputs:  DATASETS["pet_annotation.vision_annotations"]
              │             base_model: Qwen/Qwen2-VL-2B-Instruct
              │    plugin:  TRAINERS["llamafactory_sft"]
              │    output:  ModelCard { id: "{recipe_id}_train_{sha8}",
              │                         gate_status: "pending",
              │                         checkpoint_uri: "s3://.../adapter/",
              │                         clearml_task_id: "7a3f..." }
              │    cache:   recipe.id = "{recipe_id}_train_{sha8}"
              │
              └→ Stage 2: eval
                   inputs:  ModelCard(from stage 1) + eval dataset
                   plugin:  EVALUATORS["vlm_evaluator"]
                   returns: (metrics, gate)
                   orchestrator:
                     card.id = "{recipe_id}_eval_{sha8}"   # 同一公式，不同 stage_name
                     card.metrics.update(metrics)
                     card.gate_status = passed/failed
                     cache.save(card.id, card)
                   logger.log_model_card(card)
```

### 5.2 契约硬规则（5 条）

**规则 1：ModelCard 是唯一跨 stage 载体**
- 禁止 stage 之间传 dict/pickle/临时 JSON
- 保证任何 stage 独立复跑 + cache 只哈希 card

**规则 2：checkpoint_uri 是 URI 不是本地路径**
- 合法：`s3://...` / `file:///abs/...` / `hf://org/repo`
- 非法：相对路径 / `~/...`
- 保证跨机器 CI / resume 可靠

**规则 3：gate_status 状态机单向**
- `pending`（Trainer）→ `passed | failed`（Evaluator）
- 禁止 `passed` 退回 `pending`
- 禁止 Trainer 直接落 `passed`
- 保证 pet-ota 只认 passed

**规则 4：cache_key 构成公式固定**

沿用 Phase 2 shipped `pet_infra.recipe.card_id.precompute_card_id(recipe_id, stage_name, config_sha)` 签名，config_sha 构成在 v2.3 明确定义：

```python
card_id = precompute_card_id(
    recipe_id=recipe.id,
    stage_name=stage.name,
    config_sha=sha256(
        canonical_json(stage.config)                        # 该 stage 完整 Hydra 配置
        + (prev_card.checkpoint_uri if prev_card else "")   # 上游产物 URI
    ).hexdigest(),
)
# 形式：{recipe_id}_{stage_name}_{sha[:8]}
```

- 任何 override 变化 → stage.config canonical_json 变化 → sha 变化 → 必 miss
- Plugin 必须把 orchestrator 算出的 `card_id` 写回 `ModelCard.id`（非循环：orchestrator 在 plugin 执行前就能算）
- `canonical_json` = `json.dumps(..., sort_keys=True, separators=(",", ":"))` 保证跨进程稳定

**规则 5：ClearML task_id 可选**
- NullLogger / offline 场景 `task_id` 可为 None
- 下游消费方不得强依赖此字段
- 保证本地 dev / smoke 不被 ClearML 服务存活绑架

### 5.3 跨仓 runtime import 样板

**代码**：
```python
# pet-eval/src/pet_eval/plugins/audio_evaluator.py
from pet_train.audio.inference import <ZeroShotClass>  # runtime dep
```
（具体 class 名由 pet-train v2 rename PR 锁定；目前 v1 文件 `pet_train/audio_inference.py` 内含 PANNs MobileNetV2 AudioSet→5 类映射逻辑）

**pyproject.toml**（pet-eval）：
```toml
dependencies = [
    "pet-schema",      # 无 pin（matrix）
    "pet-train",       # 跨仓 runtime dep，无 pin
    # pet-infra 按 §11 peer-dep 不列
    ...
]
```

**_register.py guard**（pet-eval）：
```python
def register_all():
    try:
        import pet_infra  # peer-dep guard
        import pet_train  # 跨仓 runtime guard
    except ImportError as e:
        raise RuntimeError(
            f"pet-eval requires pet-infra + pet-train runtime. "
            f"Install via matrix row 2026.07. Missing: {e.name}"
        ) from e
```

**CI 装序**（§11.4 四步 + 1）：
```
1. pip install pet-infra==<matrix>
2. pip install pet-train==<matrix>   ← 先装被依赖 plugin 仓
3. pip install -e . --no-deps
4. pip install -e .[dev]
5. version assertion
```

### 5.4 Multirun 数据流

```
pet run recipe.yaml -m train.lr=1e-4,3e-4,1e-3
  → Hydra 展开 3 个 trial
  → orchestrator 串行 pet_run(trial_cfg) × 3
  → 每 trial cache_key 含 lr override 的 sha → 独立 card
  → ClearML 3 个 task 挂同一 experiment parent
  → 汇总 sweep report（stdout + 可选 log_artifact CSV）
```

### 5.5 Resume 语义

- 默认 `resume=True`；`--no-resume` 全量重跑
- Resume 只检查 cache hit/miss，不检查 plugin 版本
- 约束（写入 DoD "可对比性" 自检）：升 plugin 必同步升 recipe 的显式字段（如 `plugin_version: 2.0.0`），触发 sha 变化
- Gate failed 的 card 也进 cache → resume 会跳过；强制重跑需 `--no-resume` 或删 card

---

## 6. 错误处理与失败语义

### 6.1 错误分类表

| 错误类别 | 触发位置 | 处理动作 | 用户感知 |
|---------|---------|---------|---------|
| Recipe 校验失败 | Hydra compose 后 Pydantic 验证 | 立即 raise，不启动 stage | Pydantic 错误路径 + 字段 |
| Plugin 未注册 | `TRAINERS.build(name)` | fail-fast，列已注册 plugin | "TRAINERS 无 'foo'，可用：[...]" |
| Peer-dep 缺失 | `_register.py` import | fail-fast with matrix 提示 | "pet-eval 需 pet-train，装 matrix 2026.07" |
| 上游 card 缺失 | stage 执行前 cache lookup | raise；提示先跑上游 | "stage 'eval' 需 'train' 输出，未找到 card" |
| Stage 执行异常 | plugin.train/evaluate 内部 | 不落 cache；logger.finish("failed")；raise | 完整 traceback；ClearML task 标 failed |
| Gate 失败 | Evaluator 返回 `gate.passed=False` | card 落 cache（`gate_status="failed"`）；raise GateFailedError | 阈值对比；下游 stage 不执行 |
| ClearML 不可达 | Logger.start() 网络失败 | 按 `on_unavailable` 决策（见 §6.2） | - |
| Cache 损坏 | load 反序列化失败 | warn，按 miss 处理 | "cache corrupt, recomputing stage X" |

### 6.2 ClearML 不可达 3 策略

```yaml
experiment_logger:
  on_unavailable: strict | fallback_null | retry
```

- `strict`（release 默认 + CI 强制）：raise 立即失败
- `fallback_null`（smoke / dev 默认）：自动切 NullLogger，warn，`clearml_task_id=None`
- `retry`：tenacity 3 次指数退避（1s/4s/16s），仍失败按 strict

Release recipe CI 强制 `strict`。

### 6.3 Stage 失败 → Resume

```
第一次：train 成功 / eval 失败 → 只 train 落 cache
第二次 pet run（resume=True）：
  train → cache hit，跳过
  eval  → 无 cache，重跑
```

- 失败 stage 绝不污染 cache
- Gate failed card 进 cache → 下次 resume 会跳过（需 --no-resume 或删 card）

### 6.4 Multirun 容错

```
pet run recipe.yaml -m train.lr=1e-4,3e-4,1e-3
  → trial 1 成功 / trial 2 失败 / trial 3 成功
  → 汇总：2/3 成功，trial 2 错误摘要
exit code: 0（有成功 trial）| 1（全失败）
```

单 trial 失败不中止 sweep（Hydra basic launcher 默认）。

### 6.5 DAG 短路

- 上游 failed / gate-failed → 下游不执行
- 失败报告格式：
```
DAG execution failed:
  ✓ train (45min, card: pet_sft_qwen2vl_2b_abc123)
  ✗ eval (2min, GateFailedError)
      bleu=0.22 < min_bleu=0.30
      hallucination_rate=0.18 > max_hallucination=0.15
  ∅ [quantize] skipped (upstream failed)
```

### 6.6 结构化日志

所有错误走 CLAUDE.md 约定的 JSON 日志：
```json
{"ts": "...", "stage": "eval", "level": "ERROR", "err_type": "GateFailedError",
 "metrics": {"bleu": 0.22}, "thresholds": {"min_bleu": 0.30}, "card_id": "..."}
```
ClearML 自动捕获 stdout 到 task log。

### 6.7 显式不做（YAGNI）

- 不做自动重试训练（OOM / 超时让用户手动 resume）
- 不做 partial cache（step 级 resume 由 LlamaFactory 负责）
- 不做分布式错误聚合（单机 multirun sequential）
- 不做 W&B 双轨
- 不做 v1 shell 脚本兼容层

---

## 7. 测试策略

### 7.1 三档 smoke recipes

共享 Hydra defaults 基座：

```
pet-infra/recipes/
├── smoke_base.yaml          # 共享 defaults（pipeline 结构 / metric 组 / gate 结构）
├── smoke_tiny.yaml          # CPU, tiny_test_transformer (~100K params), 10 steps
├── smoke_mps.yaml           # MPS Apple Silicon, qwen2vl_2b LoRA, bf16, attn=eager, 20 steps
└── smoke_small.yaml         # CUDA, qwen2vl_2b LoRA, fp16, 100 steps
```

| 档 | 触发器 | 时长 | 目的 |
|----|--------|-----|------|
| tiny | 每 PR（必 gate） | <2 min | plugin 注册 + DAG + cache + gate 流全通 |
| mps | `make smoke-mps` 本地 | ~10 min | M2+ 用户冒烟真实 VLM 路径 |
| small | workflow_dispatch + 每日 cron + release tag | ~45 min | 真 CUDA + 真 gate，release 前必绿 |

### 7.2 测试金字塔

**pet-train**（目标 60+ tests）
- Unit：TRAINERS/METRICS 注册；LlamaFactorySFTTrainer `_hydra_to_lf_args` 映射；TinyTestTrainer 1 step 真跑（CPU 秒级）；ModelCard 字段完备性
- Integration：tiny smoke 端到端；peer-dep guard 触发

**pet-eval**（目标 70+ tests，保留 v1 核心 metric 测试）
- Unit：8 VLM metric 正确性（复用）；audio_accuracy；`evaluate` 返回签名；GateResult 阈值矩阵
- Integration：fake ModelCard + fake dataset 跑 evaluator；AudioEvaluator 跨仓 import 烟雾

**pet-infra**（扩到 120+ tests）
- Unit：build_dag 拓扑 + 缺依赖；precompute_card_id 哈希稳定；Cache round-trip + 损坏；Logger ABC 合同；on_unavailable 3 策略
- Integration：tiny smoke 完整 DAG；Resume（删 eval cache 只跑 eval）；Gate failed（`min_bleu: 0.99` 确认 GateFailedError + 短路）；Multirun（`-m` 两 trial 独立 card）；Parallel launcher 拒绝

### 7.3 CI workflow

```
pet-infra/.github/workflows/
├── plugin-discovery.yml          # 保持
├── integration-smoke.yml         # 扩 3A recipe
├── compatibility-matrix-smoke.yml# matrix 2026.07 行跑 tiny
└── release-smoke.yml             # 新增：workflow_dispatch + daily cron + tag → small
```

pet-train / pet-eval 各自 CI：
- lint（ruff + mypy）
- unit + integration（tiny only）
- peer-dep guard 测试
- smoke_tiny 端到端 gate（PR 合并条件）

### 7.4 Gate params 分命名空间

见 §3.8 的 `gate:` + `smoke:` 两块 key 集。规则：

- smoke recipe 引用 `smoke.*`
- release recipe 引用 `gate.*`
- CI 扫描 release recipe **禁止**出现 `smoke.*` 或 `experiment_logger.mode: offline`

### 7.5 ClearML 测试策略

- Unit：Mock ClearMLLogger（pytest-mock）
- Integration：`on_unavailable=fallback_null` 或 `mode=offline`，不起真服务
- Release smoke：起 docker-compose ClearML stack，真连真写

**PR gate 绝不依赖 ClearML 服务存活。**

### 7.6 回归保护

- pet-eval v1 的 8 个 metric（`anomaly_recall / calibration / kl_quantization / latency / mood_correlation / narrative_quality / schema_compliance / audio_accuracy`）测试逐字迁移到 v2 plugin 目录，确保数值无漂移
- 新增 `test_v1_metric_backward_compat.py` 对每个 metric 固定一份 fixture 金标值（从 v1 测试产出取）
- pet-train v1 `audio_inference.py` 在 v2 `pet_train/audio/inference.py` 新路径下产出一致（同 fixture 同 top-1 预测）

### 7.7 执行时长预算

| 层级 | 目标 | 3A 交付线 |
|------|------|-----------|
| Unit（单仓） | <30s | 必须 |
| Integration（单仓） | <3min | 必须 |
| tiny smoke（PR gate） | <2min | 必须 |
| mps smoke（本地） | <10min | 目标 |
| small smoke（nightly） | <45min | 目标 |
| 全链 matrix smoke | <5min（tiny） | 必须 |

---

## 8. PR 拓扑与发布顺序

### 8.1 依赖顺序（带 rc 锁避免 matrix 循环）

pet-train `_register.py` guard 需指向 matrix 某一行，而 matrix 最终行需 pet-train tag 才能填。用 **rc 锚点**解循环：

```
Step 1  pet-infra v2.3.0-rc1  (PR chain merge)
        + matrix "2026.07-rc" 行 (pet_train/eval 占位 "rc")
        tag: v2.3.0-rc1

Step 2  pet-train v2.0.0-rc1 (PR chain merge)
        _register.py guard 指向 "matrix 2026.07-rc 或更高"
        tag: v2.0.0-rc1

Step 3  pet-eval v2.0.0 (PR chain merge)     ← pet-train rc 够用
        依赖 pet-infra 2.3.0-rc1 + pet-train 2.0.0-rc1
        tag: v2.0.0

Step 4  pet-train v2.0.0  (打 final tag，代码不变)
Step 5  pet-infra v2.3.0  (打 final tag + matrix "2026.07" 正式行 finalize)
```

Rc 与 final 之间代码**必须**相同（只是 tag 名不同）；否则 rc 阶段测过的 CI 对 final 无效。

### 8.2 简化版本（如 rc 阻力大）

如不愿走 rc 流程，替代方案：
- pet-infra v2.3.0 合并时 matrix 2026.07 行先填 `pet_train/eval: "WIP"`（字符串占位，非 SemVer）
- `_register.py` guard 对 "WIP" 识别为"开发中，放行 editable 本地安装，禁 wheel"
- 全链 tag 后补 PR 把 "WIP" 改成 "2.0.0" finalize

**PR planner 选择权**：选方案 1（rc）或方案 2（WIP）在 plan 阶段决定。

### 8.3 单仓 PR chain 模式

每仓按 feedback_pr_workflow：`feature/* → dev → main`

典型 3A 单仓 PR 链（示例 pet-train）：
1. PR #A：删 v1 + plugin 骨架 + _register.py
2. PR #B：LlamaFactorySFTTrainer 实装
3. PR #C：LlamaFactoryDPOTrainer 实装
4. PR #D：TinyTestTrainer + tests
5. PR #E：peer-dep §11 + CI 装序
6. dev → main 发布 PR + tag v2.0.0

pet-infra / pet-eval 同构。

### 8.4 Rollback 策略

- 任一仓 PR failed gate → 不阻塞其他仓前置 PR；但发 tag 必须在 matrix 行完整前滚完
- matrix 2026.07 行只在**全部三仓 tag 到位**后提交
- 若中途发现架构不对：destroy PR chain，重开，不做兼容层（feedback_refactor_no_legacy）

---

## 9. North Star §0.2.1 自检（本 spec 预检）

**及格线：每维 ≥ 3 分（与 §0.3 和 PHASE_DOD_TEMPLATE §5 一致）。<3 rework。**

| 维度 | 自评 | 具体证据（section 引用）|
|------|------|------|
| 可插拔性（Pluggability） | 5 | §1.3 registry 表（Trainer/Evaluator/Metric/Logger 全 plugin）；§2.3 pet-train plugin 目录；§3.3 pet-eval plugin 目录；§4.2 experiment_logger ABC；§5.3 跨仓 import 样板。新模型家族只加 1 plugin 文件 + `_register.py` entry 即可，不改 orchestrator 代码。 |
| 灵活性（Flexibility） | 4 | §4.3 ClearML 三档 mode 纯 config；§4.6 Hydra `-m` sweep 无代码改；§3.8 gate/smoke 分命名空间；§7.4 CI 扫描禁 release 用 smoke key。减 1 分：params.yaml vs recipe override 双轨，用户仍需记住 "三层优先级"（params 默认 → params smoke → recipe override）。 |
| 可扩展性（Extensibility） | 4 | §4.2 experiment_logger 新 ABC 为 MLflow/TensorBoard/自研 logger 留口；§4.5 DAG 拓扑排序支持任意 stage 数；§4.6 sequential launcher 留未来 joblib/submitit 替换位。减 1 分：CONVERTERS / STORAGE registry 3A 不触碰，Phase 3B 可能撞出 orchestrator 接口改动。 |
| 可对比性（Comparability） | 5 | §4.6 `pet run -m train.lr=...` 一行扫 N trial；§5.2 rule 4 cache_key 含全部 override 保证独立 card；§3.4 Evaluator 返回统一 `(metrics, gate)` 格式；§5.4 ClearML 3 个 task 挂同 experiment parent；§7.6 v1→v2 metric 数值无漂移 fixture 锁。 |

**最低分 4 ≥ 3，通过。**Phase 3A 结束时按 PHASE_DOD_TEMPLATE §5 再自检一次并附实证。

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LlamaFactory API 变更破坏 thin-wrap | 中 | 高 | vendor submodule pin commit；`_hydra_to_lf_args` 单测矩阵覆盖关键参数 |
| ClearML self-hosted 运维成本高 | 低 | 中 | offline mode 默认；SaaS 作为 fallback；self_hosted 仅 release |
| cache_key 哈希不稳定（跨进程） | 中 | 高 | 单测固定 recipe → 固定 sha；哈希基于 sorted JSON serialization |
| PANNs 跨仓 import 在 pet-eval 装不上 pet-train | 中 | 中 | peer-dep §11 guard + 四步装序 + CI 装序测试 |
| Hydra multirun sweep 中单 trial OOM 污染下游 | 低 | 中 | 每 trial 独立进程空间（LlamaFactory run_sft 入口保证）；失败 trial 不写 cache |
| v1 → v2 metric 数值漂移 | 中 | 高 | `test_v1_metric_backward_compat.py` fixture 金标值锁定（覆盖 §3.2 八个 metric）|
| MPS LoRA float32 fallback（smoke_mps 路径） | 中 | 中 | smoke_mps 显式 `attn_implementation=eager` + bf16 要求 M2+；失败时降级为"该档 CI 仅供本地开发，非 PR gate"（与 §7.1 定位一致）|
| self-hosted ClearML CI 资源限制 | 中 | 中 | release-smoke 在 cron 跑（非 PR gate），单次起停；若 GitHub Actions 资源不够，退到 SaaS 档 |
| Phase 2 `precompute_card_id` 签名被扩改破坏 | 低 | 中 | v2.3 只新增 `_hash_stage_config` helper；`precompute_card_id` 签名冻结，单测锁定 |

---

## 11. 验收标准（DoD）

完成 Phase 3A 必须满足：

### 11.1 代码交付
- [ ] pet-train v2.0.0 / pet-eval v2.0.0 / pet-infra v2.3.0 全部 merged + tagged
- [ ] compatibility_matrix.yaml `2026.07` 行提交
- [ ] `docker/wandb/` 已删，`docker/clearml/` 已建

### 11.2 CI 全绿
- [ ] plugin-discovery / integration-smoke / compatibility-matrix-smoke / release-smoke 4 条 workflow
- [ ] release-smoke 至少一次跑通 self-hosted ClearML stack（docker-compose 起 Server+Mongo+Elastic+Redis+File Server，真连真写）

### 11.3 测试
- [ ] pet-train 60+ tests / pet-eval 70+ tests / pet-infra 120+ tests 通过
- [ ] smoke_tiny 端到端 PR gate 绿
- [ ] smoke_small release gate 手动触发一次绿

### 11.4 文档
- [ ] DEVELOPMENT_GUIDE §5.4 / §5.5 / §8 更新
- [ ] PHASE_DOD_TEMPLATE.md v1 commit
- [ ] matrix_history 追加 `2026.07` 条目
- [ ] §11 peer-dep 新增跨仓 import 样板子节

### 11.5 North Star §0.2.1 自检
- [ ] 四维度各 **≥ 3** 分（<3 为 rework，与 §0.3 一致），证据附于 Phase 3A retrospective

### 11.6 用户可验证
- [ ] `pet run recipes/sft_qwen2vl_2b.yaml` 本地 MPS 可跑通
- [ ] ClearML offline 模式 `~/.clearml/offline/` 产出 session zip 可用 `clearml-task --import-offline` 导入
- [ ] Multirun `pet run recipe.yaml -m train.lr=1e-4,3e-4` 产出 3 个独立 card

---

## 12. 后续（Phase 3B 预告）

- pet-quantize v2.0.0：CONVERTERS 注册 RKLLMConverter / RKNNConverter；ModelCard.edge_artifact 填充
- pet-ota v2.0.0：消费 `gate_status="passed"` 的 card；manifest.json 生成
- matrix 2026.08 行

Phase 3B 立独立 spec，依赖 3A 完成。

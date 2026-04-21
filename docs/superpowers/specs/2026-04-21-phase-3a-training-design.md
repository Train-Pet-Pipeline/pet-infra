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

### 2.1 删除清单（破坏性）

- `scripts/train_sft.sh` / `scripts/train_dpo.sh`
- `configs/llamafactory_*.yaml`（旧入口）
- `src/pet_train/kl_distill/*`（v1 stub）
- `wandb` 依赖及所有 `wandb.init/.log` 调用
- 旧 CLI 入口 `pet-train sft/dpo`（被 `pet run` 取代）

### 2.2 保留

- `vendor/LLaMA-Factory`（submodule）
- `src/pet_train/audio/panns_zero_shot.py`（3A 内仅供 AudioEvaluator 间接调用；AudioTrainer 暂不启用）

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
gate:
  min_bleu: 0.30
  max_hallucination: 0.15
```

---

## 3. pet-eval v2.0.0 组件设计

### 3.1 删除清单

- `scripts/eval_*.sh`
- `src/pet_eval/wandb_logger.py`
- `configs/eval_*.yaml`
- 旧 CLI `pet-eval run`
- `fix/eval-prompt-alignment` 分支功能合入 v2.0.0 首 PR

### 3.2 保留（移入 plugin 内部）

- 8 VLM metrics（bleu / rouge-l / meteor / bertscore / hallucination_rate / instruction_adherence / safety_score / mos）
- audio_accuracy metric
- 3 个 runner 核心逻辑（改写为 Evaluator plugin 内部方法）

### 3.3 新增 plugin 结构

```
src/pet_eval/plugins/
├── _register.py
├── vlm_evaluator.py          # VLMEvaluator (BaseEvaluator)
├── audio_evaluator.py        # AudioEvaluator
└── metrics/                  # 9 metric 条目
    ├── bleu.py
    ├── rouge_l.py
    ├── meteor.py
    ├── bertscore.py
    ├── hallucination_rate.py
    ├── instruction_adherence.py
    ├── safety_score.py
    ├── mos.py
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
- 从 pet-train `audio/panns_zero_shot.py` import（跨仓 runtime dep，见 §5.3）
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
gate:
  min_audio_accuracy: 0.60
```

---

## 4. pet-infra v2.3.0 组件设计

### 4.1 matrix 2026.07

```yaml
releases:
  "2026.07":
    pet_schema: "2.1.0"
    pet_infra:  "2.3.0"
    pet_data:   "1.2.0"
    pet_annotation: "2.0.0"
    pet_train:  "2.0.0"
    pet_eval:   "2.0.0"
    pet_quantize: "0.1.0"  # 3B 占位
    pet_ota:      "0.1.0"  # 3B 占位
```

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

**执行算法伪码**：

```python
def pet_run(recipe_path: Path, resume: bool = True):
    cfg = hydra_compose(recipe_path)
    recipe = ExperimentRecipe.model_validate(cfg)
    logger = build_experiment_logger(cfg.experiment_logger)
    dag = build_dag(recipe.stages)

    prev_card = None
    for stage in dag.topological_order():
        card_id = precompute_card_id(stage, recipe, prev_card)
        if resume and cache.has(card_id):
            prev_card = cache.load(card_id)
            continue

        task_id = logger.start(recipe, stage.name)
        plugin = registry_for(stage).build(stage.plugin_name, stage.config)
        try:
            card = plugin.run(input_card=prev_card, recipe=recipe)
        except Exception:
            logger.finish("failed")
            raise
        card.clearml_task_id = task_id
        logger.log_model_card(card)
        cache.save(card_id, card)
        logger.finish("success")
        prev_card = card
```

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
              │    output:  ModelCard { gate_status: "pending",
              │                         checkpoint_uri: "s3://.../adapter/",
              │                         clearml_task_id: "7a3f..." }
              │    cache:   {id}_train_{sha[:8]}
              │
              └→ Stage 2: eval
                   inputs:  ModelCard(from stage 1) + eval dataset
                   plugin:  EVALUATORS["vlm_evaluator"]
                   returns: (metrics, gate)
                   orchestrator:
                     card.metrics.update(metrics)
                     card.gate_status = passed/failed
                     cache.save({id}_eval_{sha[:8]}, card)
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
```
card_id = f"{card.id}_{stage_name}_{sha256(recipe_subtree + input_card.checkpoint_uri)[:8]}"
```
- 任何 override 变化 → sha 变化 → 必 miss
- 保证 resume 正确性

**规则 5：ClearML task_id 可选**
- NullLogger / offline 场景 `task_id` 可为 None
- 下游消费方不得强依赖此字段
- 保证本地 dev / smoke 不被 ClearML 服务存活绑架

### 5.3 跨仓 runtime import 样板

**代码**：
```python
# pet-eval/src/pet_eval/plugins/audio_evaluator.py
from pet_train.audio.panns_zero_shot import PANNsZeroShot  # runtime dep
```

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

```yaml
# params.yaml
gate:
  min_bleu: 0.30              # release 默认
  max_hallucination: 0.15
  min_audio_accuracy: 0.60

smoke:
  min_bleu: 0.01              # smoke_tiny 专用
  max_hallucination: 0.99
  min_audio_accuracy: 0.10
```

- smoke recipe 引用 `smoke.*`
- release recipe 引用 `gate.*`
- CI 扫描 release recipe 禁止出现 `smoke.*` 或 `mode: offline`

### 7.5 ClearML 测试策略

- Unit：Mock ClearMLLogger（pytest-mock）
- Integration：`on_unavailable=fallback_null` 或 `mode=offline`，不起真服务
- Release smoke：起 docker-compose ClearML stack，真连真写

**PR gate 绝不依赖 ClearML 服务存活。**

### 7.6 回归保护

- pet-eval v1 的 8 个 metric 测试逐字迁移到 v2 plugin，确保数值无漂移
- 新增 `test_v1_metric_backward_compat.py` 固定 fixture 金标值
- pet-train v1 PANNs zero-shot 推理在 AudioEvaluator 新包装下产出一致（同 fixture 同 top-1）

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

### 8.1 依赖顺序

```
pet-infra v2.3.0 (PR chain)
    ↓ release tag
pet-train v2.0.0 (PR chain) ← 依赖 pet-infra v2.3.0 在 matrix
    ↓ release tag
pet-eval v2.0.0 (PR chain)  ← 依赖 pet-infra v2.3.0 + pet-train v2.0.0
    ↓ release tag
pet-infra matrix 2026.07 行最终提交（full version pins）
```

### 8.2 单仓 PR chain 模式

每仓按 feedback_pr_workflow：`feature/* → dev → main`

典型 3A 单仓 PR 链（示例 pet-train）：
1. PR #A：删 v1 + plugin 骨架 + _register.py
2. PR #B：LlamaFactorySFTTrainer 实装
3. PR #C：LlamaFactoryDPOTrainer 实装
4. PR #D：TinyTestTrainer + tests
5. PR #E：peer-dep §11 + CI 装序
6. dev → main 发布 PR + tag v2.0.0

pet-infra / pet-eval 同构。

### 8.3 Rollback 策略

- 任一仓 PR failed gate → 不阻塞其他仓前置 PR；但发 tag 必须在 matrix 行完整前滚完
- matrix 2026.07 行只在**全部三仓 tag 到位**后提交
- 若中途发现架构不对：destroy PR chain，重开，不做兼容层（feedback_refactor_no_legacy）

---

## 9. North Star §0.2.1 自检（本 spec 预检）

| 维度 | 自评 | 证据 |
|------|------|------|
| 可插拔性 | 5 | Trainer / Evaluator / Metric / Logger 全 plugin；新模型只加 plugin 不改 orchestrator |
| 灵活性 | 4 | Hydra override + params.yaml 分 gate/smoke 命名空间；release recipe CI 约束 |
| 可扩展性 | 4 | experiment_logger 为新 ABC，为未来 MLflow/TensorBoard 留口；DAG 未来可加 parallel launcher |
| 可对比性 | 5 | 同 recipe -m sweep / 切不同 plugin 跑对比；metrics 格式统一；cache_key 含所有 override |

Phase 3A 结束时按 PHASE_DOD_TEMPLATE §5 再次逐项勾选 + 给证据。

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LlamaFactory API 变更破坏 thin-wrap | 中 | 高 | vendor submodule pin commit；`_hydra_to_lf_args` 单测矩阵覆盖关键参数 |
| ClearML self-hosted 运维成本高 | 低 | 中 | offline mode 默认；SaaS 作为 fallback；self_hosted 仅 release |
| cache_key 哈希不稳定（跨进程） | 中 | 高 | 单测固定 recipe → 固定 sha；哈希基于 sorted JSON serialization |
| PANNs 跨仓 import 在 pet-eval 装不上 pet-train | 中 | 中 | peer-dep §11 guard + 四步装序 + CI 装序测试 |
| Hydra multirun sweep 中单 trial OOM 污染下游 | 低 | 中 | 每 trial 独立进程空间（LlamaFactory run_sft 入口保证）；失败 trial 不写 cache |
| v1 → v2 metric 数值漂移 | 中 | 高 | `test_v1_metric_backward_compat.py` fixture 金标值锁定 |

---

## 11. 验收标准（DoD）

完成 Phase 3A 必须满足：

### 11.1 代码交付
- [ ] pet-train v2.0.0 / pet-eval v2.0.0 / pet-infra v2.3.0 全部 merged + tagged
- [ ] compatibility_matrix.yaml `2026.07` 行提交
- [ ] `docker/wandb/` 已删，`docker/clearml/` 已建

### 11.2 CI 全绿
- [ ] plugin-discovery / integration-smoke / compatibility-matrix-smoke / release-smoke 4 条 workflow

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
- [ ] 四维度各 ≥ 3 分，证据附于 Phase 3A retrospective

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

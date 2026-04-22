# Train-Pet-Pipeline 系统技术设计总览

> 维护说明：`compatibility_matrix.yaml` 加行 / 依赖治理规则改动必须同步本文档
> 最后对齐：matrix row 2026.09 / 2026-04-23 (Phase 2 ecosystem optimization)

---

## 1. Pipeline 全景

### 仓库职责

| 仓库 | 一句话职责 | 架构文档 |
|------|-----------|---------|
| `pet-schema` | Schema / Prompt 定义，所有仓库的上游合同 | `docs/architecture.md` |
| `pet-infra` | 共享运行时——Registry、Plugin Discovery、Config、CLI、Orchestrator、Storage、ExperimentLogger、Replay | [本仓 docs/architecture.md](../architecture.md) |
| `pet-data` | 数据采集、清洗、增强、弱监督 | `docs/architecture.md` |
| `pet-annotation` | VLM 打标、质检、人工审核、DPO 对生成 | `docs/architecture.md` |
| `pet-train` | SFT + DPO 训练，音频 CNN 训练 | `docs/architecture.md` |
| `pet-eval` | 评估管线，被 pet-train 和 pet-quantize 共同调用 | `docs/architecture.md` |
| `pet-quantize` | 量化、端侧转换、制品打包签名 | `docs/architecture.md` |
| `pet-ota` | 差分更新、灰度分发、回滚 | `docs/architecture.md` |
| `pet-id` | PetCard 宠物身份注册与识别（独立工具，无 pet-* peer dep） | `docs/architecture.md` |
| `pet-demo` | 对外演示站（另一 agent 负责） | — |

### 数据流

```
raw → clean → labeled → trained → evaluated → quantized → OTA
```

```mermaid
graph TD
    A[raw data] --> B[pet-data: clean + augment]
    B --> C[pet-annotation: VLM label + DPO]
    C --> D[pet-train: SFT + DPO]
    D --> E[pet-eval: evaluate]
    E --> F[pet-quantize: quantize + sign]
    F --> G[pet-ota: OTA deploy]
    H[pet-schema] -->|contract| B
    H -->|contract| C
    H -->|contract| D
    H -->|contract| E
    H -->|contract| F
    H -->|contract| G
    I[pet-infra] -->|runtime| B
    I -->|runtime| C
    I -->|runtime| D
    I -->|runtime| E
    I -->|runtime| F
    I -->|runtime| G
    J[pet-id] -.->|standalone tool| A
```

---

## 2. 依赖关系图

```mermaid
graph TD
    schema[pet-schema]
    infra[pet-infra]
    data[pet-data]
    ann[pet-annotation]
    train[pet-train]
    eval[pet-eval]
    quant[pet-quantize]
    ota[pet-ota]
    petid[pet-id\n独立工具]
    demo[pet-demo\n另一 agent]

    schema -->|peer-dep| infra
    schema -->|peer-dep| data
    schema -->|peer-dep| ann
    schema -->|peer-dep| train
    schema -->|peer-dep| eval
    schema -->|peer-dep| quant
    schema -->|peer-dep| ota

    infra -->|peer-dep| data
    infra -->|peer-dep| ann
    infra -->|peer-dep| train
    infra -->|peer-dep| eval
    infra -->|peer-dep| quant
    infra -->|peer-dep| ota

    train -->|cross-repo runtime| eval
    quant -->|cross-repo runtime| eval
    quant -->|cross-repo runtime| ota
```

---

## 3. 依赖治理约定（peer-dep + matrix 模型）

### β 决策（2026-04-23）

Python 无原生 peer-dep 概念，项目通过以下约定模拟：

- **pet-schema 和 pet-infra 均为 peer-dep**：下游 6 个仓（pet-data / pet-annotation / pet-train / pet-eval / pet-quantize / pet-ota）的 `pyproject.toml [project.dependencies]` 不声明 pet-schema 和 pet-infra。
- **matrix = 唯一版本真理源**：`pet-infra/docs/compatibility_matrix.yaml` 的 `releases[-1]` 行是当前所有仓库的版本锁定。
- **安装者负责提供 peers**：CI 和开发者按 §4 装序先装 peer，再装目标仓，使用 `--no-deps` 防止 pip 重解析。
- **fail-fast guard**：每个下游仓库的 `_register.py` 在 `register_all()` 内 / 模块顶部检查 peer 是否已安装，未安装时给出含安装指令的友好错误（见 DEVELOPMENT_GUIDE §11.3）。

### 约定细节

| 约定 | 说明 |
|------|------|
| `pyproject.toml` | 下游不写 `pet-schema` / `pet-infra` 行 |
| `compatibility_matrix.yaml` | 每次 release 新增一行，历史行降级为 archive |
| matrix 格式 | 无 `-rc` 后缀；`releases[-1]` 是最新行 |
| `_register.py` guard | pet-infra 本身在 `__init__.py` 用 `ImportError`；下游在 `register_all()` 内用 `RuntimeError` |
| 跨仓 plugin dep | pet-eval 依赖 pet-train + pet-quantize 作为 runtime peer（无 pin，matrix 行锁定）；见 §4 6-step 装序 |
| Phase 7/8 债务 | pet-quantize / pet-ota 当前仍有硬 pin 残留，Phase 7/8 修复 |

---

## 4. 装序矩阵表 ★依赖集中一处核心落点

> 此表是所有仓库安装顺序的唯一权威来源。CI workflow 从 `compatibility_matrix.yaml releases[-1]` 行取版本号。

| 仓 | peer-dep 列表 | 装序步数 | CI workflow | version assertion |
|---|---|---|---|---|
| pet-schema | （链首，无）| 1 步 (`pip install -e .`) | `pet-schema/.github/workflows/ci.yml` | `pet_schema.__version__ == X.Y.Z` |
| pet-infra | pet-schema (β peer) | 3 步 (① pet-schema peer → ② `pip install -e ".[dev]"` → ③ version assert) | `pet-infra/.github/workflows/ci.yml` | `pet_infra.__version__` matches |
| pet-data | pet-schema, pet-infra | 4 步 (① schema → ② infra → ③ `-e . --no-deps` → ④ `-e .[dev]` + assert) | `pet-data/.github/workflows/ci.yml` | `pet_data.__version__` matches |
| pet-annotation | pet-schema, pet-infra | 4 步 | `pet-annotation/.github/workflows/ci.yml` | `pet_annotation.__version__` matches |
| pet-train | pet-schema, pet-infra | 4 步 | `pet-train/.github/workflows/ci.yml` | `pet_train.__version__` matches |
| pet-eval | pet-schema, pet-infra, pet-train, pet-quantize | 6 步 (① schema → ② infra → ③ train → ④ quantize → ⑤ `-e . --no-deps` → ⑥ `-e .[dev]` + assert) | `pet-eval/.github/workflows/ci.yml` | 4 模块版本断言 |
| pet-quantize | pet-schema, pet-infra | 4 步（Phase 7 将清理硬 pin 残留） | `pet-quantize/.github/workflows/ci.yml` | `pet_quantize.__version__` matches |
| pet-ota | pet-schema, pet-infra, pet-quantize | 5 步（Phase 8 将修复 peer-dep 硬 pin 残留） | `pet-ota/.github/workflows/ci.yml` | `pet_ota.__version__` matches |
| pet-id | 无 pet-* 依赖（独立工具） | 1 步 (`pip install -e ".[dev]"`) | `pet-id/.github/workflows/ci.yml` | `pet_id.__version__` matches |

### cross-repo-smoke-install.yml

新增于 pet-infra Phase 2（本次）。每次 `compatibility_matrix.yaml` 变更时触发，对上表 7 个下游仓（除 pet-schema 和 pet-infra 自身）按矩阵最新行安装并 import assert。文件路径：`pet-infra/.github/workflows/cross-repo-smoke-install.yml`。

---

## 5. 跨仓 CI guard 清单

| workflow | 仓 | 触发条件 | 作用 |
|---|---|---|---|
| `schema_guard.yml` | pet-schema | push/PR to dev/main | 派发 `repository_dispatch` 给 8 个下游仓触发全链 CI |
| `cross-repo-smoke-install.yml` | pet-infra | matrix.yaml 变更（push to dev/main）| 新增：按最新 row 装 7 仓 + import assert，确保矩阵与实际 wheel 匹配 |
| `no-wandb-residue.yml` | pet-infra | push/PR | 确保代码中无 W&B 残留（Phase 4 移除 W&B）|
| `ci.yml` | 所有仓 | push/PR + repository_dispatch | 标准 lint + test，3-step 装序（schema peer → `-e .[dev]` → lint+test）|
| `no-wandb-residue.yml` | pet-train, pet-eval, pet-quantize | push/PR | Phase 5/6/7 将补充 |

---

## 6. 北极星四维度映射表 ★CTO 仪表盘

四维度定义：Pluggability（插件化程度）/ Flexibility（配置灵活性）/ Extensibility（扩展容易程度）/ Comparability（实验可比性）

| 仓 | Pluggability | Flexibility | Extensibility | Comparability |
|---|---|---|---|---|
| pet-schema | ExperimentRecipe + 4-paradigm Annotation discriminator | DpoPair modality/target_id 扩展 | BSL open-core，pydantic strict 验证 | Schema 版本化，全链合同 |
| pet-infra | 7-slot Registry + entry-point discovery | compose_recipe + Hydra defaults-list + overrides | BaseStageRunner 继承树 + STAGE_RUNNERS dict | ClearML ExperimentLogger + replay cli |
| pet-data | 弱监督 label 策略可替换 | params.yaml 驱动清洗参数 | store.py 单点扩展 | dedup.py 保证数据集无重叠 |
| pet-annotation | 4 范式表 per annotator_type | LS 1.23 import/export 可配置 | 新增 annotator_type 只加一张表 | DPO pair 版本化 + modality 标注 |
| pet-train | 3 plugin 体系（SFT/DPO/Audio）| LLaMA-Factory vendor 可替换 | audio namespace 独立 | ClearML 实验追踪 + model card sha |
| pet-eval | 8 metric plugins + 2 evaluators | cross-modal fusion rule-based 可配置 | 新增 metric = 1 plugin file | ExperimentRecipe variations 对比 |
| pet-quantize | RKNN/RKLLM 双 target | rknn_toolkit2 版本 pin | 制品打包签名可替换 | 量化前后精度对比 via pet-eval |
| pet-ota | S3 + HTTP 双后端 | 灰度分发策略可配置 | 新增后端 = 1 storage plugin | 差分包 sha256 校验 + rollback |
| pet-id | CLI register/identify/list/show/delete | PetCard registry JSON 可迁移 | 独立工具，无 pet-* 耦合 | — |

---

## 7. 新人上手路径

### Day 0

1. 读 `pet-infra/docs/DEVELOPMENT_GUIDE.md` — 规范源（怎么做 / 禁止什么 / 约定）
2. 读本文档 — 架构源（是什么 / 为什么 / 依赖关系）
3. 理解 §3 依赖治理约定 + §4 装序矩阵表

### Day 1（选定目标仓库后）

```bash
git clone https://github.com/Train-Pet-Pipeline/<target-repo>
conda activate pet-pipeline
# 按 §4 装序安装 peers 再装目标仓
make setup
make test
# 读本仓 docs/architecture.md
```

### Day 2–3（扩展练习）

按本仓 `docs/architecture.md §5 Extension points` 跑一次"添加新 plugin"练手：
- pet-infra：添加新 storage 后端（STORAGE registry via entry-point）
- pet-train：添加新 trainer plugin（TRAINERS registry）
- pet-eval：添加新 metric plugin（METRICS registry）

### 跨仓贡献

回到本文档 §2（依赖图）/ §3（治理约定）/ §4（装序矩阵），确认：
- 变更是否影响 pet-schema（需 ≥ 2 reviewer approve）
- 变更是否影响 compatibility_matrix.yaml（需同步本文档 §4）
- 变更是否跨仓（需通知下游仓负责人）

---

## 8. 本文档与 DEVELOPMENT_GUIDE.md 的分工

| 文档 | 定位 | 内容 |
|------|------|------|
| `DEVELOPMENT_GUIDE.md` | **规范源** | 怎么做 / 禁止什么 / 约定 / CI 模板 / 代码风格 |
| 本文档（OVERVIEW.md） | **架构源（系统级）** | 是什么 / 为什么 / 9 仓依赖关系 / 装序矩阵 |
| `pet-infra/docs/architecture.md` | **架构源（本仓级）** | pet-infra 模块设计 / 扩展点 / 已知复杂点 |
| 各仓 `docs/architecture.md` | **架构源（本仓级）** | 各仓自己的模块设计 |

两者交叉引用，不复制内容：
- DEVELOPMENT_GUIDE §11 引用本文档 §4 作为装序矩阵落点
- 本文档 §3 引用 DEVELOPMENT_GUIDE §11 作为 guard 模板来源
- 修改 matrix 时，`compatibility_matrix.yaml` + 本文档 §4 + DEVELOPMENT_GUIDE §11.4 需同步更新

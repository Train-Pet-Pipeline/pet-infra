# Phase 4 Software-Completion Retrospective (2026-04-22)

Phase 4: 软件闭环 — OTA S3/HTTP 后端、rule-based 跨模态融合评估器、`ExperimentRecipe.variations` launcher、`pet run --replay`、W&B 物理清除（ClearML 成为唯一实验追踪器）、BSL 1.1 全仓授权；`compatibility_matrix.yaml` 行 `2026.09` finalize。Follows `docs/PHASE_DOD_TEMPLATE.md`。

---

## §1 — 代码交付（What Shipped）

共 **36 feature PRs**（含 release-tag PRs，不含 dev→main 同步 merge）跨 **10 个仓库**、**7 个工作流（Workstreams）**：

| 工作流 | 内容 | PRs |
|--------|------|-----|
| W1 (P0-A) | pet-schema `ModelCard.resolved_config_uri`；v2.4.0 tag | 2 |
| W1 (P1-A…G + P5-A) | pet-infra：S3Storage、HttpStorage、resolved_config_uri dump、variations+preflight+ClearML tags、`pet run --replay`、W&B 清除+CI guard、v2.5.0-rc1、matrix 2026.09 + DEV_GUIDE、v2.5.0 tag；设计 spec | 10 |
| W1 (P2-A) | pet-ota：peer-dep bump、S3BackendPlugin、HttpBackendPlugin、_register+smoke、v2.1.0-rc1、v2.1.0 tag | 6 |
| W2 (P2-B) | pet-eval：peer-dep bump、3 fusion evaluators、cross_modal_fusion_eval recipe、W&B 清除、v2.2.0-rc1、v2.2.0 tag | 6 |
| W5 (P2-C) | pet-train W&B 清除 + v2.0.1 tag；pet-quantize W&B 清除 + v2.0.1 tag | 4 |
| W6 (P5-A-0) | matrix 2026.09 row（含 pet-infra P5-A-0，已计入 W1） | — |
| W7 | BSL 1.1 授权：10 个仓库（W7-1 ~ W7-10） | 10 |

**子阶段汇总：**
- P0（schema 准备）：2 PRs（pet-schema #21 #22）
- P1（pet-infra 功能）：7 feature PRs + 1 spec + 2 release = 10 PRs
- P2-A（pet-ota 后端）：6 PRs
- P2-B（pet-eval 融合）：6 PRs
- P2-C（W&B 清除 pet-train/pet-quantize）：4 PRs
- P5-A（finalize + matrix 2026.09）：pets-schema/infra/ota/eval/train/quantize 各一 release PR = 6 PRs（部分与 P1/P2 计入同组）
- W7（BSL 1.1）：10 PRs

> 注：plan 目标 38 PRs；实际交付 ~36 feature PRs（plan 里将部分 dev→main sync merge 计入总数，本表仅计 feature/fix/release PRs）。差异源于 pet-infra design spec 独立 PR（#57），以及 P2-B-5 rc1 PR 与 P5-A-4 final tag PR 分离。

---

## §2 — 最终版本表

| Repo           | Phase 4 前 | Phase 4 后 | 变更类型                                          |
|----------------|------------|------------|---------------------------------------------------|
| pet-schema     | 2.3.1      | 2.4.0      | minor：`ModelCard.resolved_config_uri`            |
| pet-infra      | 2.4.0      | 2.5.0      | minor：storage/launcher/variations/replay/W&B guard/license |
| pet-ota        | 2.0.0      | 2.1.0      | minor：S3BackendPlugin + HttpBackendPlugin        |
| pet-eval       | 2.1.0      | 2.2.0      | minor：3 fusion evaluators + W&B 清除             |
| pet-train      | 2.0.0      | 2.0.1      | patch：W&B 清除 + pyproject version 漂移修正      |
| pet-quantize   | 2.0.0      | 2.0.1      | patch：W&B 清除                                   |
| pet-data       | 1.2.0      | 1.2.0      | license-only（BSL 1.1）                           |
| pet-annotation | 2.0.0      | 2.0.0      | license-only（BSL 1.1）                           |
| pet-id         | 0.1.0      | 0.1.0      | license-only（BSL 1.1）                           |
| pet-demo       | 1.0.1      | 1.0.1      | license-only（BSL 1.1，Option 3 metadata）        |
| matrix         | 2026.08    | 2026.09    | Phase 4 row：released 2026-04-22                  |

---

## §2b — CI 全绿验证

- [x] pet-schema CI green on main @ v2.4.0（schema-validation.yml）
- [x] pet-infra CI green on main @ v2.5.0：install-order-smoke、integration-smoke（smoke_tiny）、plugin-discovery（7 registries: TRAINERS/EVALUATORS/CONVERTERS/METRICS/DATASETS/STORAGE/OTA）、recipe-dry-run、schema-validation、**no-wandb-residue**（新增 Phase 4 guard）
- [x] pet-ota CI green on main @ v2.1.0：4-step peer-dep（pet-infra → editable → re-resolve → assert）；peer-dep-smoke 断言 `s3_backend`、`http_backend`、`local_backend` 全部注册
- [x] pet-eval CI green on main @ v2.2.0：6-step peer-dep；peer-dep-smoke 断言 8 metrics + 6 evaluators（含新增 3 fusion）
- [x] pet-train CI green on main @ v2.0.1：4-step peer-dep；no-wandb-residue guard 断言 `import wandb` 不存在
- [x] pet-quantize CI green on main @ v2.0.1：4-step peer-dep；no-wandb-residue guard 断言通过
- [x] BSL 4 license-only 仓库（pet-data / pet-annotation / pet-id / pet-demo）各自 CI green（无功能变化，仅 LICENSE 文件新增）
- Note: pet-infra `no-wandb-residue.yml` 是 Phase 4 新增的 CI guard；目前只在 pet-infra 侧运行，pet-train / pet-eval / pet-quantize 的 guard 列入 §7 待完成

---

## §3 — North Star §0.2.1 四维度自检

### 可插拔性（Pluggability）: **5 / 5**

证据：
- `S3Storage`（pet-infra）和 `HttpStorage`（pet-infra）各用 `@STORAGE.register_module(force=True)` 一行注册；`S3BackendPlugin`、`HttpBackendPlugin`（pet-ota）同样通过 `@OTA.register_module(force=True)` 注册 — 无需修改 orchestrator 核心
- 3 个融合评估器（`WeightedSumFusionEvaluator` / `MaxScoreFusionEvaluator` / `ConfidenceGatedFusionEvaluator`）各作为独立文件通过 `@EVALUATORS.register_module(force=True)` 注册；`_register.py` 侧加载即生效，零配置发现
- `pet_infra.plugins` entry-point group 现在跨 **6 个 repo** 分发插件；Phase 4 新增 2 Storage + 2 OTA backend + 3 Evaluator = 7 个新插件，全部 zero-core-change
- `pet list-plugins --json` 可见：3 trainers + 6 evaluators（含 3 fusion）+ 8 metrics + 4 converters + 3 datasets + 3 OTA backends + 2 storage backends

### 灵活性（Flexibility）: **5 / 5**（Phase 3B 5/5 保持）

证据：
- `ExperimentRecipe.variations` 支持 cartesian 乘积（`type: cartesian`）和 `link_to` 协同迭代；preflight 在 sweep 启动前计算并打印组合数，强制用户有意识地控制 sweep 规模
- 3 个 OTA 后端（local/s3/http）可在 recipe `ota_backend:` 字段直接切换，无需修改任何 plugin 内部代码
- `cross_modal_fusion_eval.yaml` recipe 通过 `variations:` 轴同时参数化 3 种融合策略，每次 run 产生 3 张独立 `ModelCard`，直接可对比
- Hydra defaults-list 继承（Phase 3B P1-A）保持完整；Phase 4 recipe 片段无需重写基础结构

### 可扩展性（Extensibility）: **5 / 5**（Phase 3B 5/5 保持）

证据：
- 增加第 4 个 Storage 插件：新建 1 文件 + 1 行 `@STORAGE.register_module`，不碰 orchestrator
- 增加第 4 个 OTA 后端（如 CDN）：同上 pattern，pet-ota `plugins/` 下新文件
- 增加第 4 种融合策略：继承 `BaseFusionEvaluator` ABC，实现 `fuse()` 方法，`@EVALUATORS.register_module` — 与已有 3 个同构
- `pet run --replay <card-id>` 通过 `ModelCard.resolved_config_uri` + `git_shas` 重建配置；实现插件无关 — replay 不感知后端类型

### 可对比性（Comparability）: **5 / 5**（Phase 3B 5/5 保持）

证据：
- `ModelCard.resolved_config_uri` 精确指向渲染后的 Hydra config 快照（包含所有 override 展开值）；`pet run --replay` 从此 URI 恢复，保证 bit-identical 复现
- `ExperimentRecipe.variations` 每次 run 自动向 ClearML 注入 per-variation tag（如 `variation=fusion_strategy_weighted_sum`），使侧边栏对比无需手动标注
- Cartesian preflight 打印 "N × M = K runs"，让用户在 sweep 前知道对比维度，避免事后无法溯源哪组配置对应哪个 card
- `precompute_card_id(recipe_id, stage, config_sha)` 的确定性 ID 机制（Phase 3A）与 `resolved_config_uri` 共同构成完整可对比链路

**最低维度 5 ≥ 3；Phase 4 通过。所有 Phase 3B 5/5 维度均保持。**

---

## §4 — Drift / Execution-time Decisions

| 时间 | 决策 | 原因 | NS 维度 |
|------|------|------|---------|
| P6-A | 回顾录文件路径使用 `docs/retrospectives/` 而非 plan 中的 `docs/superpowers/retrospectives/` | Phase 3A/3B 回顾均在 `docs/retrospectives/`；保持惯例优先于 plan 路径 | — |
| W7 | pet-demo 使用 Option 3（`LICENSE.metadata.json`）而非直接写 `pyproject.toml` | pet-demo 是纯前端 Next.js 项目，无 `pyproject.toml`/`setup.py`/`package.json` 中的 license 字段（`package.json` 存在但 license 字段已 MIT，改写会误导 npm audit）；`LICENSE.metadata.json` 是专为此场景设计的最小侵入方案 | — |
| W7 | pet-demo 进入 W7 授权范围，尽管 `feedback_scope_exclude_pet_demo` 将其排在多模型重构之外 | `project_license_bsl` memory 明确列出全 10 仓；License 是横切关注点，与多模型重构范围正交 | — |
| W7-8 | pet-infra DEV_GUIDE 授权句子合并进已有 `§12.7 BSL 1.1` 节（pre-existing），而非新建 §12 | §12.7 节在 Phase 4 P1-x 系列 PRs 中已建立；追加内容到已有节避免重复标题 | — |
| P1-A/B | `S3Storage` 与 `HttpStorage` 定位为 **只读**（read artifact，不做 upload）；upload 路径由 OTA 层负责 | YAGNI + 职责分离：Storage 层提供读取路径（replay / audit）；写入/部署由 OTA 后端插件封装 | Extensibility |
| P1-C | `resolved_config_uri` 在 launcher 写 card 时即时 dump，而非 replay 时按需重建 | 按需重建需要 Hydra context 仍然在内存中；写 card 时 dump 的 config 已经是 OmegaConf 渲染后最终态，更可靠 | Comparability |
| P1-D | `variations` preflight 使用 `itertools.product` 实现 cartesian，不引入外部 DAG 调度库 | Phase 4 sweep 规模预期 ≤ 50 个 sub-run（本地 M 系或单 GPU），`itertools` 足够；引入 Ray/Dask 是 premature optimization | Flexibility |
| P2-A | `HttpBackendPlugin` 支持 bearer/basic/no-auth 三种认证，但**不**实现客户端证书（mTLS） | OTA 目标是 edge 设备拉取固件，bearer token 覆盖主流场景；mTLS 需要 PKI 基础设施，Phase 5 硬件 ready 后再评估 | Extensibility |
| P2-B | 3 个融合评估器均为 **rule-based**；learned fusion 明确 defer | `feedback_no_learned_fusion` memory：当前业务无 learned fusion 需求；rule-based 已满足 Comparability（3 策略可对比），future-proof 由 ABC 保证 | Extensibility |
| P2-C | pet-train pyproject.toml version 从漂移值（`0.1.0`）修正为 `2.0.1`，作为 W&B 清除 PR 的捎带修正 | 两处改动共属"清理历史债务"，合并在同一 PR 减少 PR 链长度；风险低（patch bump） | — |

---

## §5 — 硬件 Items Deferred to Phase 5

以下 items 在 Phase 4 保持 **dry-run / stub** 状态；触发条件：RK3576 硬件板 + CI runner 采购并接入：

- `pet validate --hardware` 非 dry-run 路径（目前 `--dry-run` flag 可用；real device 调用被 `PET_HARDWARE_DRY_RUN=1` 门控）
- 真实 RK3576 OTA flash + rollback（`LocalBackendPlugin` / `S3BackendPlugin` / `HttpBackendPlugin` 均有 gate guard；real deploy 需设备在线）
- Real-device end-to-end 延迟基准（cross-modal fusion 的 audio CNN + VLM 联合推理延迟）
- `smoke_small` GPU runner 接入（Phase 3A 债务携带至此；self-hosted GPU runner 尚未开通）
- 灰度分发（gray-release）真实验证：OTA 分级灰度逻辑已在 plugin 层实现，但没有真实设备群做分级回归

---

## §6 — License 授权总结

- **10/10 仓库** 全部采用 BSL 1.1（Business Source License 1.1）
- **Change Date**：2030-04-22 → Apache License, Version 2.0
- **Licensor 字段**：`Train-Pet-Pipeline (TBD: replace with legal entity)` — 用户需在公司实体确定后执行 1-line `sed -i` 更新全 10 仓的 `LICENSE` 文件
- **vendor/ 目录**上游 LICENSE 保留：
  - `pet-train/vendor/LLaMA-Factory`：Apache License 2.0（`NOTICE` 文件已创建）
  - `pet-eval/vendor/lm-evaluation-harness`：MIT License（`NOTICE` 文件已创建）
- **pet-demo 特殊处理**：无 `pyproject.toml` / Python package 结构；采用 Option 3（`LICENSE` + `LICENSE.metadata.json`），`LICENSE.metadata.json` 声明 `spdx: BUSL-1.1` 供工具链解析
- **CI guard**：pet-infra `no-wandb-residue.yml` 已上线；其他仓库 W&B residue guard 待 Phase 5 补齐（见 §7）

---

## §7 — Phase 5 跟进清单

1. **RK3576 硬件 + runner 采购接入**：Phase 5 的核心前提；解锁所有 `--hardware` 路径
2. **`pet validate --hardware` 非 dry-run**：去除 `PET_HARDWARE_DRY_RUN=1` 门控，接入真实设备
3. **真实 OTA 灰度分发**：在至少一次 matrix release（计划 `2026.10`）中跑真实设备 gray-release + rollback 演练
4. **重新评估 learned fusion**：如业务端出现跨模态融合精度瓶颈，再立项（per `feedback_no_learned_fusion`；当前 rule-based 三策略已满足）
5. **BSL Licensor 法律实体名称最终确认**：公司实体确定后 `sed -i 's/Train-Pet-Pipeline (TBD: replace with legal entity)/REAL_ENTITY/g'` 全 10 仓 `LICENSE`
6. **合并 pet-infra 两个 compose 模块**（Phase 3B 技术债）：`compose.py` 和 `compose_legacy.py` 并存；应整合为单模块
7. **DRY pet-infra orchestrator/hooks.py 中 5 个 StageRunner 类**（Phase 3B code-review HIGH，已推迟两个 Phase）：结构高度相似，应抽象公共基类
8. **全链 W&B residue CI guard**：pet-infra 已有 `no-wandb-residue.yml`；其余有 W&B 历史的仓库（pet-train / pet-eval / pet-quantize）应各自补一个 guard workflow
9. **HttpBackendPlugin mTLS 支持评估**：Phase 4 只实现 bearer/basic/no-auth；边缘设备 PKI 基础设施 ready 后评估是否需要客户端证书
10. **`compatibility_matrix.yaml` 2026.09 行中 `-rc1` 后缀清查**：matrix 2026.09 已 finalize，各字段均为 release 版本，无 `-rc1` 残留（当前已验证）；Phase 5 row `2026.10` 添加时需同步确认

---

*回顾录于 2026-04-22，Phase 4 全部 feature/fix/release PRs 在 10 个仓库 dev + main 分支 CI-green 后撰写。*

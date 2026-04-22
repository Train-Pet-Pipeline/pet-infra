---
name: 生态优化设计（Ecosystem Optimization）
description: Train-Pet-Pipeline 北极星 5/5 保持后的生态级优化 — 9 仓按依赖链 CTO 视角走读、沉淀可交接技术设计文档、统一依赖治理、偿还相关技术债；最终产出每仓 architecture.md + pet-infra OVERVIEW.md + 装序矩阵 + 跨仓 smoke CI；为租卡 E2E 验收做就绪
type: spec
status: draft
date: 2026-04-23
owner: pet-infra
scope: 9 仓（pet-schema / pet-infra / pet-data / pet-annotation / pet-train / pet-eval / pet-quantize / pet-ota / pet-id），不含 pet-demo
parent_spec: docs/superpowers/specs/2026-04-22-phase-4-software-completion-design.md
predecessor_retrospective: docs/retrospectives/2026-04-22-phase-4-retrospective.md
role_mandate: CTO / 技术 Leader 视角主导（见 §0）
---

# 生态优化设计

## 0. 背景与边界

### 0.1 现状

Phase 4 已于 2026-04-22 shipped：

- 全 10 仓 BSL 1.1；matrix `2026.09` final
- 北极星 §0.2.1 四维度 5/5
- 38 PR 全链 merged（dev + main）
- Phase 4 retrospective §7 列了 10 条 Phase 5 跟进清单（本轮按相关性裁决 4 条纳入）

技术功能层面已达成北极星指标，但生态层面存在三类实操问题：

1. **依赖治理执行不一致**（与 DEV_GUIDE §11 peer-dep 约定**文档滞后于实践**）
   - pet-schema pin 风格 3 种并存（硬 pin tag / 无 pin 靠 matrix / 完全不写）
   - pet-quantize / pet-ota 的 pet-infra 是硬 pin，直接违反 §11.1 peer-dep 约定
   - pet-ota 用 `pet-quantize>=1.0.0` 范围 pin，第三种完全不同的风格
   - 装序矩阵分散在 §11.4 / §11.4.3 / §11.6 三节，缺跨仓总览表
   - `compatibility_matrix.yaml` 是快照表不是约束表，无 CI 强制验证

2. **技术文档缺失**
   - 8 个仓（pet-schema / pet-data / pet-annotation / pet-train / pet-eval / pet-quantize / pet-ota / pet-id）**均无** `docs/architecture.md`
   - pet-infra 有 DEVELOPMENT_GUIDE 2745 行（规范源）+ retrospectives，但无本仓 `architecture.md` 也无系统级 `OVERVIEW.md`
   - 新人接手任一仓的模块开发，需要靠"读代码 + 问人"，onboarding 摩擦大

3. **Phase 3B 遗留技术债阻碍文档沉淀**
   - pet-infra 存在两个 compose 模块：`src/pet_infra/compose.py`（97 行，defaults-list 解析）+ `src/pet_infra/recipe/compose.py`（59 行，recipe 组装，import 前者）；职责有重叠，写 architecture.md 时要么解释 "为什么两个 compose"（债务延续）要么合并 — 对应 Phase 4 retro §7 #6（原 retro 误写为 `compose_legacy.py`，实际是 `recipe/compose.py`）
   - pet-infra `orchestrator/hooks.py` 5 个 StageRunner 类高度相似未 DRY（§7 #7）
   - pet-train / pet-eval / pet-quantize 缺 `no-wandb-residue.yml` CI guard（§7 #8）
   - 这些不清理，architecture.md 要么记录债务延续、要么描述理想态骗人

### 0.2 本轮范围（2026-04-23 brainstorming 对齐）

**生态优化 = 代码清理（按需） + 依赖治理 + 文档沉淀**，以 CTO 视角主导。

裁决原则：**"是否妨碍文档清晰度 / 依赖治理一致性"作为 scope 门槛**。

9 个仓按依赖链顺序逐一"关门再开下一仓"：

```
pet-schema → pet-infra → pet-data → pet-annotation → pet-train → pet-eval → pet-quantize → pet-ota → pet-id
```

每仓走 §2 定义的 9 步工作流（先优化到 CI 绿再写文档）；pet-infra 一仓处理最多子任务（compose 合并 + StageRunner DRY + 装序矩阵 + smoke CI + OVERVIEW.md）。

### 0.3 显式不在本轮范围（→ Phase 5 或 deferred）

引用 Phase 4 retrospective §7 十条跟进清单的裁决：

| # | 项 | 裁决 | 理由 |
|---|---|---|---|
| 1 | RK3576 硬件 + runner 采购接入 | **OUT** | Phase 5 硬件闭环前提 |
| 2 | `pet validate --hardware` 非 dry-run | **OUT** | 硬件闭环 |
| 3 | 真实 OTA 灰度分发演练 | **OUT** | 硬件闭环 |
| 4 | learned fusion 重评 | **OUT** | 业务触发，当前无需求（`feedback_no_learned_fusion`） |
| 5 | BSL Licensor 实体名最终确认 | **OUT** | 法律 admin，用户自行完成 |
| **6** | **pet-infra compose 合并** | **IN** | 阻碍 pet-infra architecture.md 清晰度 |
| **7** | **pet-infra StageRunner DRY** | **IN** | 同上 |
| **8** | **W&B residue guard 全链补齐** | **IN** | 依赖治理完整性 + 跨仓 CI 一致性 |
| 9 | HttpBackendPlugin mTLS 支持 | **OUT** | Phase 5 硬件 PKI |
| **10** | **matrix `-rc1` 约定文档化** | **IN (tiny)** | 进 OVERVIEW.md matrix 约定章节 |

其他显式不做：

- ❌ **架构级重写**（挪模块 / 改目录结构 / 跨仓重新划分职责）— 超出"生态优化"保守定位
- ❌ **pet-demo 任何改动** — `feedback_scope_exclude_pet_demo`，另一 agent 负责
- ❌ **租卡 session 本身** — 本轮交付"租卡前自检报告"，租卡是独立事件由用户触发
- ❌ **北极星四维度进一步提升** — 当前 5/5，本轮目标是"守住不退化"

### 0.4 North Star §0.2.1 守住承诺

| 维度 | Phase 4 收官 | 本轮目标 | 验证方式 |
|---|---|---|---|
| 可插拔性 | 5/5 | **5/5（守住）** | compose 合并 + StageRunner DRY 不改 registry / 插件接口；smoke CI 验证全链 plugin 可加载 |
| 灵活性 | 5/5 | **5/5（守住）** | 依赖治理只改 pin 形态 + 装序，不改 recipe / config 能力 |
| 可扩展性 | 5/5 | **5/5（守住）** | 装序矩阵表让新增仓的"接入成本"更可见（加分项，但评分不提升） |
| 可对比性 | 5/5 | **5/5（守住）** | OVERVIEW.md §6 北极星四维映射让下一任 tech lead 一眼看到支撑点 |

退化即失败。retrospective §3 逐维度自检 + 净影响评估。

---

## 1. 工作姿态（CTO / 技术 Leader 视角）★贯穿全文

本轮优化我的角色 = 承担 CTO / 技术 Leader 职责，不是被动执行者。

### 1.1 主动权

- **主动挑 issue**：走读不只找"明显坏的"，也找"技术 leader 才会注意到的"—— 命名不对应职责、公共 API 过宽、测试覆盖分布失衡、CI 缺关键 guard、onboarding 摩擦点
- **主动质疑**：findings 裁决阶段若我认为用户初判有误，明确标 `CTO-pushback` + 理由；不装乖
- **主动抬 scope**：若走读发现某项"现在做 ROI 显著高于留 Phase 5"，主动提议纳入，附 blast radius + ROI 分析
- **主动拒绝 scope**：用户中途提出改动若破坏本轮边界 / 违反北极星 / 有隐藏风险，明确说反对理由

### 1.2 判断基准（优先级降序）

1. 北极星 §0.2.1 四维度（不能退化）
2. 已建立的 feedback memory（no-hardcode / no-manual-workaround / refactor-no-legacy / endgame-thinking / ...）
3. 工程第一性原则（YAGNI / TDD / fix-not-bypass / SemVer）
4. onboarding 摩擦（新人接手任一模块多久能独立负责）
5. team velocity / maintainability（"6 个月后我们还会感谢这个设计吗"）

### 1.3 在各章节的具体落地

- §2 Step 3 走读 = **"CTO 走读"**（技术债轨迹 + onboarding 友好度 + pipeline 拖累点）
- §2 Step 4 findings 裁决附 **"CTO 视角附注"**（③ 类给"若删释放多少认知负荷"的定性评估）
- §3 architecture.md §8 已知复杂点 = **给未来 tech lead 写备忘录**（"什么情况下可重新审视"）
- §3 OVERVIEW.md §6 北极星映射 = **CTO 管理四维度的仪表盘**
- 封顶 retrospective 加章 **§7 "CTO 视角：本轮学到的"**

### 1.4 不变的东西

- 所有代码改动仍走 PR + CI + 自审门槛
- 不跳过 brainstorm / spec / plan 流程
- 重大 scope / 架构决策仍请用户拍板（只是主动给方案 + 带数据 + 有立场）

---

## 2. 总体交付物与全景

### 2.1 最终产物（9 仓 + pet-infra 封顶后）

1. **9 份本仓技术设计文档** — `<repo>/docs/architecture.md`
2. **1 份系统级总览** — `pet-infra/docs/architecture/OVERVIEW.md`
3. **依赖治理统一** — pet-schema / pet-infra pin 风格；pet-quantize / pet-ota peer-dep 修正；全链 W&B residue guard
4. **1 个新 CI workflow** — `pet-infra/.github/workflows/cross-repo-smoke-install.yml`（matrix 改动触发）
5. **3 个 W&B guard workflow** — pet-train / pet-eval / pet-quantize 各一份
6. **至少 3 仓版本 bump** — pet-infra / pet-quantize / pet-ota（其他按命中 ②/③ findings 决定）
7. **compatibility_matrix.yaml 新增行** — `2026.10-ecosystem-cleanup`
8. **1 份本轮 retrospective** — `pet-infra/docs/retrospectives/2026-XX-XX-ecosystem-optimization.md`
9. **MEMORY 更新** — 9 仓 status memory + 新建 `project_ecosystem_optimization.md`
10. **租卡前自检报告** — `pet-infra/docs/gpu-session-readiness-<date>.md`（或 retrospective 附录）

### 2.2 执行性约束（"不倒退"原则）

租卡是本轮完成后的独立验收事件，不是本轮交付物。本轮需保证：

- 每仓优化 PR 合并前 `make test` + `make lint` 全绿
- findings 分类表新增列 **"对既有 E2E 链路影响（影响 / 不影响 / 未知）"**
- 影响项裁决优先级最高
- 9 仓完成后，retrospective 记录"执行性基线"供租卡参考

### 2.3 全景流程

```
对齐（brainstorm 已完成 2026-04-23）
  ↓
写 spec（本文档）
  ↓
spec review loop（spec-document-reviewer）
  ↓
用户复核 spec
  ↓
writing-plans skill（细分每仓任务 + 依赖治理 plan）
  ↓
执行阶段（方案 X 交织型：9 仓依赖链顺序）
  ├─ pet-schema pass      → 基线 + findings + 裁决 + 精简 + architecture.md → PR → dev→main sync
  ├─ pet-infra pass       → 基线 + findings + compose 合并 + StageRunner DRY + 装序矩阵表 + smoke CI + OVERVIEW.md + architecture.md → PR 链 → tag v2.6.0
  ├─ pet-data pass        → ...
  ├─ pet-annotation pass  → ...
  ├─ pet-train pass       → + W&B guard 补齐
  ├─ pet-eval pass        → + W&B guard 补齐
  ├─ pet-quantize pass    → peer-dep 修正 + W&B guard + tag v2.1.0
  ├─ pet-ota pass         → peer-dep 修正 + pin 统一 + tag v2.2.0
  └─ pet-id pass          → architecture.md（独立工具定位说明）
  ↓
封顶：matrix 2026.10 行 + retrospective + 租卡自检报告 + MEMORY 刷新
  ↓
【停】等用户触发租卡 session（独立事件）
```

---

## 3. 每仓标准工作流（9 仓通用模板）

9 步工作流，**关门再开下一仓**。

### 3.1 Step 定义

| Step | 动作 | 退出条件 |
|---|---|---|
| 1 | 基线对齐 | `cd <repo> && git checkout dev && git fetch origin && git reset --hard origin/dev && conda activate pet-pipeline && make setup` |
| 2 | 基线体检 | `make test` + `make lint`；记录初始通过/失败/lint errors 数；基线不绿必须先修到绿 |
| 3 | CTO 走读 | 读 `src/` + `tests/` + `config/` + `.github/` + `pyproject.toml` + `Makefile`；产出 `findings-<repo>.md`（临时文件，不进 git），字段：`位置 \| 类别①/②/③ \| 对 E2E 影响 \| 推荐处理 \| 风险评估 \| CTO 附注` |
| 4 | findings 裁决 | 贴 findings 给用户；逐条拍板；我记录裁决结果 |
| 5 | 执行优化 | 按裁决顺序：(a) 级清理（auto） → ② 类修根因 → ③ 类裁决通过的改动；本仓相关依赖治理同步执行（§4 表）；每批独立 commit，body 写 rationale + findings ref |
| 6 | 执行性回归 | `make test` + `make lint` 必须绿；E2E 关键节点仓（train/eval/quantize）跑一次 mini smoke |
| 7 | 写 architecture.md | 按 §4 模板 9 章完整；pet-infra 一仓同时写 OVERVIEW.md |
| 8 | PR + 自审 + auto merge | `feature/eco-<repo>-<topic>` → dev；§6.4 自审清单全勾；CI 绿后 `gh pr merge --auto --squash` |
| 9 | 仓收尾 | dev → main sync PR；若 bump 则 tag；刷新 MEMORY `project_<repo>_status.md`；进下一仓 |

### 3.2 关键铁律（不可协商）

1. **Step 2 → Step 3**：基线不绿不允许走读（否则分不清"原本就坏"vs"我改坏"）
2. **Step 3 → Step 4**：findings 必须先提交裁决，禁止"走读边改"
3. **Step 6 → Step 7**：代码先全绿，文档描述终态
4. **Step 9 → 下一仓**：当前仓 dev→main sync 合并 + MEMORY 更新，才能开下一仓
5. **findings 分类永远 3 类**（①复杂必要 / ②简单有问题 / ③复杂没必要）；禁止混合标签

### 3.3 例外仓

- **pet-schema**（链首）：无上游 peer-dep，Step 5 不涉及依赖治理；其他步骤常规
- **pet-infra**（链第 2）：Step 5 最重 — compose 合并 + StageRunner DRY + 装序矩阵 + smoke CI + OVERVIEW.md；PR 数最多（预估 3–5 个 feature PR）；Step 7 同时写 `architecture.md` 和 `OVERVIEW.md`
- **pet-id**（链尾）：Step 3 走读确认与 peer-dep 体系无交集；architecture.md 明确声明 "独立 CLI 工具，matrix 登记仅作版本对齐"

---

## 4. 文档模板

### 4.1 本仓 `<repo>/docs/architecture.md` 模板

**长度**：按本仓复杂度自定（不设硬约束）。唯一标准：**"新人读完能独立负责本仓某个模块"**。

**固定 9 章**：

```markdown
# <repo> 技术设计文档

> 维护说明：代码变更影响本文档任一章节时，与代码在同 PR 内更新（feedback_devguide_sync）
> 最后对齐：<repo> vX.Y.Z / <date>

## 1. 仓库职责
   - 一句话定位
   - pipeline 依赖链中的位置（文字版小图）
   - 做什么 / 不做什么的明确边界

## 2. 输入输出契约
   - 上游来源（来自哪个仓的什么 schema / artifact，附 pet-schema 类型名）
   - 下游消费方（哪些仓以何种格式使用本仓输出）
   - 契约变更流程（通常：改 pet-schema → 全链 CI）

## 3. 架构总览
   - 顶层目录结构（src/ + tests/ + config + CI，各自职责）
   - 关键数据流（文字 / mermaid / ascii 图）
   - 启动入口（CLI / entry point / Makefile target）

## 4. 核心模块详解
   ≥ 3 个关键模块，每个给出：
   - 目的（为什么存在）
   - 关键接口（签名/约定，不粘源码）
   - 设计权衡（为什么是现在这个形状）
   - 潜在陷阱（新人容易踩的坑）

## 5. 扩展点
   - 本仓暴露的 registry / plugin / config hook 清单
   - "如何添加一个新的 <plugin 类型>" how-to（step-by-step，可跑）
   - 扩展点与北极星四维度对应关系

## 6. 依赖管理
   - 对上游依赖（pet-schema / pet-infra / 跨仓 plugin 源）
   - pin 方式（硬 pin tag / peer-dep / 无 pin）— 引用 OVERVIEW.md §4 装序矩阵
   - CI 装序步数（引用 OVERVIEW.md）
   - 第三方依赖的关键约束（版本范围 / 原因）

## 7. 本地开发与测试
   - `conda activate pet-pipeline` + `make setup` + `make test` + `make lint`
   - 本仓特有踩坑（env var / fixture 路径 / hardware 要求）
   - 测试分层（unit / integration / e2e 在哪 / 怎么跑子集）

## 8. 已知复杂点（复杂但必要）★ CTO 视角核心章节
   findings ① 类入账；每条写：
   - 位置（文件 / 模块）
   - 为什么复杂（设计时考虑的需求）
   - 删了会损失什么（具体能力 / 灵活性）
   - 不要轻易动（新人警示 + 重新审视的触发条件）

## 9. Phase 5+ Followups
   findings ③ 类未裁决删除 + 超范围发现 + 本仓独有债务；每条：
   - 简述
   - 触发条件（什么时候再处理）
   - 指向 retrospective 清单 #<n>（如有）
```

**质量门**（不是长度门）：

- §4 每个关键模块必须讲 **why / tradeoff / pitfall**，不只罗列 what
- §8 每条必须写 **"删了会损失什么"**
- §9 每条必须写 **"触发条件"**

### 4.2 `pet-infra/docs/architecture/OVERVIEW.md` 模板

**定位**：系统级总览 + 依赖治理集中点。长度按信息量自定。

**固定 8 章**：

```markdown
# Train-Pet-Pipeline 系统技术设计总览

> 维护说明：compatibility_matrix.yaml 加行 / 依赖治理规则改动必须同步本文档
> 最后对齐：matrix row <2026.XX> / <date>

## 1. Pipeline 全景
   - 9 仓 + pet-demo 整体定位图（mermaid / ascii）
   - 每仓一句话职责 + 链接到本仓 architecture.md
   - 数据流：raw → clean → labeled → trained → evaluated → quantized → OTA

## 2. 依赖关系图
   - 9 仓依赖图（箭头 = "依赖 / import 关系"）
   - pet-id 标为"独立工具，不参与 peer-dep 生态"
   - pet-demo 标为"另一 agent 负责，仅 matrix 登记"

## 3. 依赖治理约定（peer-dep + matrix 模型）
   - 为什么 peer-dep（Python 无原生 peer-dep，--no-deps 装序 workaround）
   - pet-schema / pet-infra pin 风格（本次统一后的定版）
   - 跨仓 plugin dep 约定（引用 DEV_GUIDE §11.6）
   - matrix 约定：无 -rc 后缀；每次 release 加一行；历史行降级为 archive

## 4. 装序矩阵表 ★依赖集中一处的核心落点
   | 仓 | peer-dep 列表 | 装序步数 | CI workflow | version assertion |
   | pet-infra | （自身）| 1 步 | - | - |
   | pet-data | pet-schema@tag, pet-infra（peer）| 4 步 | <path> | <cmd> |
   | pet-annotation | pet-schema@tag, pet-infra（peer）| 4 步 | <path> | <cmd> |
   | pet-train | pet-schema, pet-infra（peer）| 4 步 | <path> | <cmd> |
   | pet-eval | pet-schema, pet-infra, pet-train, pet-quantize | 6 步 | <path> | <cmd> |
   | pet-quantize | pet-schema, pet-infra（peer，已修）| 4 步 | <path> | <cmd> |
   | pet-ota | pet-schema, pet-infra（peer，已修）, pet-quantize | 5 步 | <path> | <cmd> |
   | pet-id | 无 pet-* 依赖 | 1 步 | - | - |

## 5. 跨仓 CI guard 清单
   - `schema-validation.yml`（pet-schema 改动 → 触发全链，已有）
   - `cross-repo-smoke-install.yml`（本次新增，matrix 改动触发）
   - `no-wandb-residue.yml`（pet-infra 已有；pet-train/eval/quantize 本次补齐）
   - 其他 repo-local CI 不在此列

## 6. 北极星四维度映射表 ★ CTO 仪表盘
   9 仓 × 4 维度矩阵，每格填"本仓对该维度的贡献点"
   - 让下一任 tech lead 一眼看到四维度当前由哪些代码支撑
   - 改动某仓时立刻知道会影响哪些维度

## 7. 新人上手路径
   - Day 0：读 DEVELOPMENT_GUIDE.md 目录 + 本文档
   - Day 1：clone 目标仓 + `conda activate pet-pipeline` + make setup + make test + 读本仓 architecture.md
   - Day 2–3：按本仓 §5 扩展点 how-to 跑一次 "添加 plugin" 练手
   - 跨仓贡献：回到本文档 §2 / §3 / §4

## 8. 本文档与 DEVELOPMENT_GUIDE.md 的分工
   - DEVELOPMENT_GUIDE = 规范源（怎么做 / 禁止什么 / 约定）
   - 本文档 = 架构源（是什么 / 为什么 / 依赖关系）
   - 两者交叉引用，不复制内容
```

### 4.3 格式约定

- 代码片段用 fenced code block 标语言（bash / python / yaml / toml）
- 依赖图 / 数据流用 mermaid `graph TD`（GitHub 原生渲染）
- 跨文档引用用相对路径（`../pet-schema/docs/architecture.md`），便于本地 clone 阅读

---

## 5. 依赖治理 5 条落地

### 5.1 治理项矩阵

| # | 项 | 落仓 | 改什么 | 改成什么 | 验证 |
|---|---|---|---|---|---|
| 1 | pet-quantize 的 pet-infra 从硬 pin 改 peer-dep | pet-quantize | `pyproject.toml` 删 `pet-infra @ git+...@v2.5.0`；`src/pet_quantize/_register.py` 加 fail-fast guard | 和 pet-data/annotation 一样的 peer-dep 形态 | CI 按 §11.4 4 步装序；本地 make test 绿 |
| 2 | pet-ota 的 pet-infra peer-dep 修正 + pet-quantize pin 风格统一 | pet-ota | `pyproject.toml` 删 `pet-infra @ git+...@v2.5.0`；`pet-quantize>=1.0.0` 改无 pin；`_register.py` 加 guard | peer-dep + 跨仓 plugin dep 无 pin | CI 按跨仓 plugin 装序（类似 pet-eval 5 步）；make test 绿 |
| 3 | pet-schema pin 风格全 9 仓统一 | pet-infra pass 决策 + 其他仓 pass 执行 | 见 §5.2 两选项 | 选 α（全硬 pin tag）或 β（全 peer-dep） | 装序矩阵表反映新约定 |
| 4 | pet-infra 补装序矩阵表 + 跨仓 smoke install CI | pet-infra | 新增 `OVERVIEW.md §4` + `.github/workflows/cross-repo-smoke-install.yml` | matrix 改动触发；job 对每仓跑"装 + `python -c "import pet_xxx"`" | workflow 首次运行绿 |
| 5 | W&B residue guard 补 pet-train / pet-eval / pet-quantize | 各自 pass | 每仓 `.github/workflows/no-wandb-residue.yml`（照抄 pet-infra） | 扫描 wandb / import wandb / WandB 模式，命中 fail | 首次 run 绿 |

### 5.2 第 3 条（pet-schema pin 风格）决策路径

在 pet-infra pass 执行时拍板。两选项数据：

**pet-schema 依赖现状（实测自 pyproject.toml）**：

| 状态 | 仓数 | 仓列表 |
|---|---|---|
| 硬 pin tag（`pet-schema @ git+...@vX.Y.Z`）| 4 | pet-infra, pet-data, pet-annotation, pet-quantize |
| 无 pin（`"pet-schema"`）| 2 | pet-train, pet-eval |
| 完全不依赖 pet-schema | 2 | pet-ota, pet-id |

- **选项 α（全硬 pin tag — 所有依赖 pet-schema 的仓统一硬 pin）**
  - 改动量：pet-train + pet-eval 改 pyproject.toml 两行加 tag；pet-ota / pet-id 不涉及（不依赖）；pet-schema bump 时 6 个依赖仓都要改 pin
  - 清晰度：新人看 pyproject.toml 直接知道吃哪版
  - 一致性：与 peer-dep 模式**略不一致**（pet-infra peer-dep，pet-schema 硬 pin）

- **选项 β（全 peer-dep 无 pin — 所有依赖 pet-schema 的仓无 pin，靠 matrix 锁）**
  - 改动量：4 仓（pet-infra/data/annotation/quantize）删 pyproject.toml pet-schema 行 + 每仓 `_register.py` 加 pet-schema fail-fast guard；pet-train/eval 已无 pin 无需动；pet-ota/id 不涉及；pet-schema bump 时仅改 matrix
  - 清晰度：需翻 matrix 才知道吃哪版（OVERVIEW §4 装序表补偿）
  - 一致性：与 peer-dep 模式**完全一致**

**初判（非最终）**：选项 β — 更统一 + 扩散更小。执行时用届时代码再给用户一次带数据的裁决请求（Q5 协议 ③ 类门）。

### 5.3 仓 pass 与依赖治理交织顺序

```
pet-schema pass     → 无治理动作（链首）
pet-infra pass      → 装序矩阵表 + smoke CI + pin 风格决策请求
pet-data pass       → 按决策调整 pet-schema pin（若选 β）
pet-annotation pass → 同上
pet-train pass      → 同上 + W&B guard
pet-eval pass       → 同上 + W&B guard
pet-quantize pass   → peer-dep 修正 + pet-schema pin 调整 + W&B guard
pet-ota pass        → peer-dep 修正 + pet-quantize pin 统一（pet-ota 不依赖 pet-schema）
pet-id pass         → 无治理动作（独立工具）
```

### 5.4 DEV_GUIDE §11 同步

治理执行完后，DEV_GUIDE §11 需同步更新（feedback_devguide_sync）：

- §11.1：把 pet-schema 明确列为 peer-dep（若选 β）或保留硬 pin 表述（若选 α）
- §11.2：pyproject.toml 示例反映最终决策
- §11.3：`_register.py` guard 模板若选 β 增加 pet-schema 分支
- §11.4 / §11.4.3 / §11.6：所有装序步数表格与 OVERVIEW §4 对齐，单向引用 OVERVIEW 为权威
- 这个同步放 pet-infra pass 内作为子任务

---

## 6. 版本 / PR / CI 约定

### 6.1 分支命名

- feature PR：`feature/eco-<repo>-<topic>`（例：`feature/eco-pet-infra-compose-merge`）
- dev→main sync：`sync/eco-<repo>-vX.Y.Z`
- 封顶 PR：`feature/eco-retrospective` + `sync/eco-phase-closing`

### 6.2 commit message

```
<type>(<repo>): <简要说明>

<rationale —— 为什么这么改；②/③ 类改动 >50 行必填>
<findings ref —— 指向 findings-<repo>.md 行号（若适用）>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

type ∈ `feat | fix | refactor | test | docs | chore | ci`

### 6.3 版本 bump（Q3 (a) 决议）

| 仓 | bump | 理由 |
|---|---|---|
| pet-schema | 视 findings 决定 | 若仅 ①/ 文档则不 bump；若有 schema 字段调整 minor |
| pet-infra | **2.5.0 → 2.6.0** minor | OVERVIEW + 装序矩阵 + smoke CI + compose 合并 + StageRunner DRY |
| pet-data | 视 findings 决定 | 纯文档 + (a) 级清理则不 bump |
| pet-annotation | 视 findings 决定 | 同上 |
| pet-train | **2.0.1 → 2.0.2** patch（至少） | W&B guard；若代码精简则升 minor |
| pet-eval | **2.2.0 → 2.2.1** patch（至少） | 同上 |
| pet-quantize | **2.0.1 → 2.1.0** minor | peer-dep 修正 + W&B guard |
| pet-ota | **2.1.0 → 2.2.0** minor | peer-dep 修正 + pin 风格统一 |
| pet-id | 视 findings 决定 | 独立工具，一般不 bump |

**bump 时机**：每仓 Step 9（dev→main sync）合并后立刻 tag。`compatibility_matrix.yaml` 新行 `2026.10-ecosystem-cleanup` **在全部 9 仓 tag 完毕后** 一次性写入（pet-infra 仓 final PR）。

### 6.4 PR 自审清单（合 dev 前我自检）

- [ ] CI 全绿（本仓 + 被触发下游 CI 若有）
- [ ] 本仓 `make test` + `make lint` 本地跑过（不只信 GH Actions）
- [ ] 改动符合 findings 裁决结果（③ 类 commit body 有 rationale + findings ref）
- [ ] 无 no-hardcode / no-manual-workaround / refactor-no-legacy 违反
- [ ] 若涉及依赖治理，装序矩阵表已同步
- [ ] 若有 E2E 影响风险，已跑 mini smoke 并记录
- [ ] PR description 有 Summary + Rationale + Test plan 三段

通过 → `gh pr merge --auto --squash`（Q4 (b) 决议）。

### 6.5 dev → main sync 节奏

- 单仓级：每仓 Step 9 做一次 sync，紧跟 tag
- 封顶级：全 9 仓 main 完成后，pet-infra 做 matrix 2026.10 行 + retrospective 的最终 PR 到 main
- **不做**：中途多仓集体 sync（除非 matrix 依赖到了）；避免 dev / main 长期分叉

### 6.6 CI 新增 guard 清单

| workflow | 仓 | 触发 | 作用 |
|---|---|---|---|
| `cross-repo-smoke-install.yml` | pet-infra | `docs/compatibility_matrix.yaml` push | 按最新 matrix 行对 9 仓跑跨仓装序 + import assert |
| `no-wandb-residue.yml` | pet-train | push / PR | 扫描 wandb 残留模式 |
| `no-wandb-residue.yml` | pet-eval | push / PR | 同上 |
| `no-wandb-residue.yml` | pet-quantize | push / PR | 同上 |

所有新 workflow 首次运行必须绿才算本仓 pass 完成。

### 6.7 失败处理（CI / 测试 fail）

- CI fail → 修根因，不绕过（`feedback_no_manual_workaround`）
- 测试 fail 且是本轮改动导致 → 回滚改动重裁决；预存在 flake → 新开 fix PR 修
- CI 装序 workflow 失败 → 装序矩阵表与实际不一致 → 以**行为为准**（feedback_devguide_sync）
- **禁止**：`--no-verify` / skip / `@pytest.mark.skip` 新增 / 注释测试 / 手动 patch 绕过

---

## 7. 出口验收与 retrospective

### 7.1 单仓 DoD（每仓 Step 9 判据）

- [ ] 基线测试 + 新增测试全绿（无 skip / xfail 新增）
- [ ] lint 清洁（ruff + mypy 无新增 error）
- [ ] findings 分类表全部有裁决（① 入 §8 / ② 已修 / ③ 已动或入 §9）
- [ ] `architecture.md` 9 章完整，用户抽查无意见
- [ ] 依赖治理本仓相关项已执行（§5 表）
- [ ] feature PR → dev 已合，CI 全绿
- [ ] dev → main sync PR 已合
- [ ] 若该仓 bump，tag vX.Y.Z 已推
- [ ] MEMORY `project_<repo>_status.md` 刷新
- [ ] 下游仓知晓本仓变更（matrix 记录或 OVERVIEW 更新）

### 7.2 全阶段 DoD

**代码 / 工程层**：

- [ ] 9 仓全部 §7.1 DoD 通过
- [ ] `compatibility_matrix.yaml` 新增 `2026.10-ecosystem-cleanup` 行
- [ ] 4 个新 CI workflow 首次运行全绿
- [ ] 装序矩阵表和实际 CI 装序 100% 一致（smoke CI 验证）
- [ ] 无 `--no-verify` / skip / manual patch / 硬编码新增违反

**文档层**：

- [ ] 9 份 `architecture.md` 就位
- [ ] `OVERVIEW.md` 完整（8 章）
- [ ] DEV_GUIDE §11 同步到与实际一致
- [ ] 所有文档交叉引用正确（相对路径 / 无死链）

**北极星四维度层**：

- [ ] Pluggability ≥ 3/5（本轮不退化）
- [ ] Flexibility ≥ 3/5（同）
- [ ] Extensibility ≥ 3/5（同）
- [ ] Comparability ≥ 3/5（同）
- retrospective 逐维度自检 + 净影响评估（提升 / 中性 / 小退化 + 理由）

**交付层**：

- [ ] retrospective 发布到 `pet-infra/docs/retrospectives/<date>-ecosystem-optimization.md` 并 merged 到 main
- [ ] MEMORY 新建 `project_ecosystem_optimization.md` 索引到 MEMORY.md
- [ ] 9 仓 status memory 更新
- [ ] 租卡前自检报告交付

### 7.3 retrospective 结构

参考 Phase 4 retrospective（160 行 / DoD 5/5）：

```
§1 — 代码交付（What Shipped）
    每仓改了什么 / 新增文档一览 / 新增 CI guard 一览
§2 — 最终版本表
    before / after 版本对照 + matrix 2026.10 行
§2b — CI 全绿验证
    每仓最终 CI 状态
§3 — 北极星 §0.2.1 四维度自检
    逐维度评分 + 净影响 + 理由
§4 — Drift / Execution-time 决策记录
    Q5 ③ 类裁决明细 / 超范围发现 / pet-schema pin 风格最终决策（α 或 β）
§5 — Findings 累计表
    按仓列出 ①/②/③ 类数量 + 典型条目
§6 — 依赖治理成果
    5 条逐条验收 / 装序矩阵表链接
§7 — CTO 视角：本轮学到的 ★ §1 新增章节
    - 哪些初判回头看是对的
    - 哪些裁决回头看值得重审
    - onboarding / team velocity 观察
    - 给下一任 tech lead 的备忘录
§8 — Phase 5+ 跟进清单
    合并 Phase 4 retro §7 遗留 + 本轮新增 + 租卡若发现回归的后续
§9 — 致谢 / 签署
```

### 7.4 租卡前自检报告

独立文件 `pet-infra/docs/gpu-session-readiness-<date>.md`（或 retrospective 附录）：

- 9 仓当前 CI 状态（tag + 最新 CI run 链接）
- conda `pet-pipeline` 环境 freeze 输出
- 已知可跑 recipe 清单：优化前后对照（哪些本来能跑仍能跑；哪些新加 / 改过需重验）
- 疑似风险点：②/③ 类改动涉及 registry / plugin / CLI / store 的清单（租卡重点盯）
- 租卡建议执行顺序：最简 smoke → 实际 training recipe → E2E

**不在本轮做**：租卡脚本 / recipe 配置。租卡是独立事件由用户触发。

### 7.5 收尾行为

retrospective merged 到 main 后，**停**。不自动触发租卡、不自动进 Phase 5（`feedback_phase3_autonomy`）。

---

## 8. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|
| 走读裁决"③ 类"轮次过多 → 进度慢 | 中 | 中 | 每仓裁决请求集中一次批量给用户；CTO 初判减少决策负担 |
| compose 合并 / StageRunner DRY 引入 regression | 中 | 高 | pet-infra pass 内测试覆盖是关键；mini E2E 在本仓 PR 合并前跑 |
| pet-schema pin 风格改动扩散到 9 仓 → PR 链长 | 高（若选 β） | 中 | 按每仓 pass 自然嵌入，不做单独"pin 统一 PR 扫描"；每仓 CI 验证 |
| smoke CI 首次运行暴露历史遗留不一致 | 中 | 低 | 优先级：以行为为准，修文档 / 修 matrix；不绕过 |
| W&B guard 在 pet-train / eval / quantize 历史代码扫出残留 | 中 | 低 | 残留 = 本仓 pass 的 ② 类入账；根治不 skip |
| 文档与代码 drift（写 architecture.md 时代码又变） | 低 | 低 | §3.2 铁律：Step 6 → Step 7 顺序；architecture.md 描述终态 |
| 用户中途提新 scope → 边界模糊 | 中 | 中 | §1.1 主动拒绝 scope 权限；按相关性裁决门 §0.2 |

---

## 9. 开放决策点

以下决策**不在 spec 阶段拍板**，执行阶段到相应时点时请示用户：

| # | 决策点 | 何时请示 | 选项 |
|---|---|---|---|
| 1 | pet-schema pin 风格 α vs β | pet-infra pass 执行时 | §5.2 两选项 |
| 2 | 各仓 ③ 类 findings 裁决 | 每仓 Step 4 | 每仓单独裁决 |
| 3 | ② 类修根因的 blast radius 超预期时 | 执行时 | 回滚重裁决 / 纳入本 pass / 降级 §9 |
| 4 | 超范围发现是否"主动抬 scope" | 走读时 | §1.1 CTO 主动权 + ROI 分析 |

---

## 10. Signoff — brainstorming 对齐记录（2026-04-23）

| 问题 | 决议 |
|---|---|
| Q1 仓范围与顺序 | (a) 9 仓按依赖链 `pet-schema → pet-infra → pet-data → pet-annotation → pet-train → pet-eval → pet-quantize → pet-ota → pet-id`；附加 "依赖集中一处对齐" 作为显式目标 |
| Q2 文档位置 | (a) 双层：每仓 `docs/architecture.md` + pet-infra `docs/architecture/OVERVIEW.md` 汇总 |
| Q3 版本策略 | (a) SemVer 老实 bump：仅动代码仓 bump，纯文档仓不 bump；matrix 新增 `2026.10-ecosystem-cleanup` 行 |
| Q4 PR review | (b) CTO 自审 + CI + `--auto --squash`（Phase 3A/3B/4 模式） |
| Q5 精简红线 | (a)+(b) 三类分类协议：① 保留 + §8 记录；② 修根因；③ 报告裁决；绝不默默动非平凡代码 |
| Q6 超范围发现 | (a') 相关性裁决法：§7 #6/#7/#8/#10 in；硬件/业务/法律 out；每仓先优化到 CI 全绿再写文档 |
| 执行策略 | 方案 X 交织型（per-repo 一站式） |
| CTO 视角 | 明确本轮以 CTO / 技术 Leader 视角主导（§1） |
| 租卡 | 独立事件，本轮只交付就绪度报告 |

---

## 11. 下一步

1. spec review loop — dispatch spec-document-reviewer subagent，修到 approved（最多 3 轮）
2. 用户复核 spec
3. 调 `superpowers:writing-plans` skill 写实现 plan
4. plan approved 后开始执行阶段（9 仓按依赖链顺序走）

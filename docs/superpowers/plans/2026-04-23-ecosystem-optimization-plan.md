# Ecosystem Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 CTO / 技术 Leader 视角对 Train-Pet-Pipeline 9 仓生态做系统化优化 — 每仓按依赖链顺序走读 + 分类 findings + 用户裁决 + 优化到 CI 绿 + 写 `architecture.md`；pet-infra 额外承担 compose 合并 / StageRunner DRY / 装序矩阵表 / 跨仓 smoke install CI / `OVERVIEW.md`；跨仓统一 pet-schema pin 风格 + pet-quantize/pet-ota peer-dep 修正 + 全链 W&B residue guard 补齐；封顶 matrix `2026.10-ecosystem-cleanup` + retrospective + GPU 租卡前自检报告，为用户租卡 E2E 验收就绪。

**Architecture:** 10 个顺序 Phase —— Phase 0 preflight；Phase 1–9 按依赖链每仓一个（pet-schema → pet-infra → pet-data → pet-annotation → pet-train → pet-eval → pet-quantize → pet-ota → pet-id）；Phase 10 ecosystem closeout。每仓 Phase 共享同一 9 步工作流模板 T1–T9（定义在 §"Per-Repo Workflow Template"），repo-specific 子任务在 T5（执行优化）和 T7（写文档）处叠加。方案 X 交织型：每仓一站式走完再开下一仓。CTO 视角贯穿：主动挑 issue + 带立场质疑 + ROI 分析抬/拒 scope。

**Tech Stack:** Python 3.11.x · conda env `pet-pipeline` · Pydantic v2 · mmengine.Registry · Hydra defaults-list + multirun · pytest + ruff + mypy · gh CLI · `gh pr merge --auto --squash` · BSL 1.1 · compatibility_matrix.yaml 为唯一版本真理源

**Hard constraints (项目 memory 强制)：**
- `feedback_refactor_no_legacy`：破坏性一次到位，不留兼容层
- `feedback_pr_workflow`：`feature/eco-* → dev → main`，不直接 push dev/main
- `feedback_env_naming`：共享 `pet-pipeline` conda env，不建 per-repo 环境
- `feedback_no_hardcode`：数值从 `params.yaml` / config 读，不硬编码
- `feedback_no_manual_workaround`：fail 修根因，禁止 `--no-verify` / skip / 注释测试 / 手动 patch 绕过
- `feedback_devguide_sync`：实现偏离 DEV_GUIDE 时同步更新文档
- `feedback_endgame_thinking`：沉默成本不计入；按终局决策
- `feedback_phase3_autonomy`：同 Phase 内不问"是否继续"；Phase 完成即停
- `CLAUDE.md`：主目录非 git 仓库；git 必须 cd 到子仓；所有 PR 要 CI 绿 + reviewer approve（pet-schema 2 位）

**Spec 依据：** `pet-infra/docs/superpowers/specs/2026-04-23-ecosystem-optimization-design.md`（brainstorm 2026-04-23 Q1–Q6 全部对齐）

---

## Global Phase Dependency Graph

```
Phase 0 — Preflight（基线验证 + 环境对齐 + spec/plan push）
  │
  ├──► Phase 1 — pet-schema pass  (T1–T9)
  │       │
  │       └──► Phase 2 — pet-infra pass (T1–T9 + compose 合并 + StageRunner DRY
  │                                      + 装序矩阵表 + smoke CI + OVERVIEW.md
  │                                      + pet-schema pin 风格决策请求 α/β
  │                                      + DEV_GUIDE §11 同步)
  │              │
  │              └──► Phase 3 — pet-data pass (T1–T9 + 按 pin 决策调整)
  │                     │
  │                     └──► Phase 4 — pet-annotation pass
  │                            │
  │                            └──► Phase 5 — pet-train pass (+ W&B guard)
  │                                   │
  │                                   └──► Phase 6 — pet-eval pass (+ W&B guard)
  │                                          │
  │                                          └──► Phase 7 — pet-quantize pass
  │                                                 (peer-dep 修正 + W&B guard + pin 调整)
  │                                                 │
  │                                                 └──► Phase 8 — pet-ota pass
  │                                                        (peer-dep 修正 + pet-quantize pin 统一)
  │                                                        │
  │                                                        └──► Phase 9 — pet-id pass (独立工具)
  │
  └──► Phase 10 — Ecosystem Closeout（matrix 2026.10 行 + retrospective
                                      + GPU 租卡就绪报告 + MEMORY 刷新）
```

**Branch naming：** `feature/eco-<repo>-<topic>`（feature → dev）；`sync/eco-<repo>-vX.Y.Z` or GH Actions auto（dev → main）；封顶 `feature/eco-retrospective` + `sync/eco-phase-closing`

**Auto-merge：** 每 PR 自审 + CI 绿 + `gh pr merge --auto --squash`（spec §6.4 / Q4(b) 决议）

**PR 数量粗估：** ~30–40 PRs 总计（pet-infra 单 Phase 最多，约 5–7；其他每 Phase 1–3；Phase 0/10 共约 5–8）

---

## Per-Repo Workflow Template（T1–T9）

**所有 Phase 1–9 共享此模板。** Phase 特定子任务在 T5 / T7 叠加，其他步骤不变。

### T1 — 基线对齐

- [ ] **Step T1.1：切换到 dev 并同步**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/<repo>
git fetch origin
git checkout dev
git reset --hard origin/dev
```
Expected：干净 working tree；`git branch --show-current` 输出 `dev`。

- [ ] **Step T1.2：conda 环境激活**

```bash
conda activate pet-pipeline
which python
```
Expected：Python 指向 pet-pipeline 环境。若未激活报 "CondaError: run conda activate pet-pipeline" 则先激活。

- [ ] **Step T1.3：setup**

```bash
make setup
```
Expected：exit 0；pip 装完（每仓的 editable install 按 DEV_GUIDE §11.4 装序，不要用 `pip install -e .[dev]` 直接绕过）。

### T2 — 基线体检

- [ ] **Step T2.1：跑测试并记录**

```bash
make test 2>&1 | tee /tmp/baseline-test-<repo>.log
```
Expected：全绿（通过数 N / 失败 0 / skip 数 M 记入 findings-<repo>.md 首行）。

- [ ] **Step T2.2：跑 lint 并记录**

```bash
make lint 2>&1 | tee /tmp/baseline-lint-<repo>.log
```
Expected：ruff + mypy exit 0。

- [ ] **Step T2.3：基线失败则先修**

If T2.1 或 T2.2 非绿：**停止**走读，先修基线（视为本仓首个 feature/fix PR，走 T8 流程），合并后才能进 T3。

### T3 — CTO 走读

- [ ] **Step T3.1：产出 findings-<repo>.md 临时文件**

```bash
touch /tmp/findings-<repo>.md
```

走读范围：
- `src/<package>/**` —— 主代码
- `tests/**` —— 测试分层与覆盖
- `config/` 或 `configs/` —— Hydra / YAML 配置
- `.github/workflows/` —— CI workflow
- `pyproject.toml` —— 依赖 + extras
- `Makefile` —— target 定义
- `README.md` —— 入口文档
- 本仓 `params.yaml`（若有）—— 数值源

findings 分类（spec §3.1 铁律）：

| 类别 | 含义 | 处理 |
|---|---|---|
| ① 复杂但必要 | 设计时考虑了 dev/工程/北极星维度需求 | 保留，入 architecture.md §8 |
| ② 简单但可能有问题 | 有 bug / 边缘 case / 违反约束（硬编码 / silent fallback / 无 test） | 修根因（spec §6.7）|
| ③ 复杂但没必要 | YAGNI 违反 / 过度泛化 / 可被简单替代 | 报告给用户裁决 |

findings 每条字段：`位置 | 类别 | 对 E2E 影响（影响/不影响/未知） | 推荐处理 | 风险评估 | CTO 附注`

- [ ] **Step T3.2：附 CTO 视角附注**

对每条 ③ 类，给一个"若删释放多少认知负荷"的定性评估（High / Medium / Low），帮用户决策。对每条 ① 类，写"删了会损失什么（具体能力/灵活性）"。

### T4 — findings 裁决（用户门）

- [ ] **Step T4.1：报告 findings 给用户**

把 findings-<repo>.md 内容贴到会话，让用户逐条拍板 ②/③ 类处理方案。① 类自动入 architecture.md §8，无需单独裁决。

- [ ] **Step T4.2：记录裁决结果**

在 findings-<repo>.md 末尾追加"Adjudication"段，记录每条 ③ 类的最终决定（执行 / 留 §9 / 纳入 §8 重分类）。

**Gate：** T4 完成前，T5 不启动。

### T5 — 执行优化

> 通用步骤（适用所有 repo），Phase-specific 叠加项见各 Phase 节。

- [ ] **Step T5.1：(a) 级自动清理**

按 ruff --fix + 人肉 grep 确认 unused imports / dead imports / 注释掉的旧代码 / `_deprecated` 残留。

```bash
ruff check --fix src/ tests/
git diff --stat
```

Commit：`refactor(<repo>): auto-cleanup dead imports and deprecated residue`

- [ ] **Step T5.2：② 类根因修复**

按 T4 裁决结果逐条修。每条独立 commit，body 写 rationale + findings ref。

- [ ] **Step T5.3：③ 类裁决通过的改动**

按 T4 裁决结果执行 `execute` 标签的条目。每条独立 commit，body 必写 rationale + findings ref（spec §6.2 强制）。

- [ ] **Step T5.4：repo-specific 子任务**

（各 Phase 单独列，此处占位。）

### T6 — 执行性回归

- [ ] **Step T6.1：测试回归**

```bash
make test
```
Expected：全绿；若回归必须先修（不允许 skip / xfail）。

- [ ] **Step T6.2：lint 回归**

```bash
make lint
```
Expected：exit 0。

- [ ] **Step T6.3：关键节点仓跑 mini E2E（视实际可用命令而定）**

**适用：** 仅 pet-train / pet-eval / pet-quantize 三仓（其他跳过 T6.3）。

**发现原则：** 实际 Makefile 目前只定义 `setup` / `test` / `lint` / `clean` 四个 target（CLAUDE.md 强制）；**没有预置 smoke 目标**，也**没有 `tests/fixtures/*_smoke.yaml` 预置 recipe**。T6.3 的 E2E 是**走读时识别 + 本仓已有测试集的子集**，命令由 T3 走读产出：

- pet-train 候选：`pytest tests/ -k 'smoke or integration or e2e' -v`（若有命中子集）；否则 `pytest tests/test_sft_trainer.py -v`（核心 trainer 测试走一遍）
- pet-eval 候选：`pytest tests/test_fusion_recipe.py tests/test_runners -v`（走读确认测试文件名后用实际路径）
- pet-quantize 候选：`pytest tests/test_noop_converter.py tests/test_plugin_register_noop.py -v`（零 SDK 依赖 + 不需硬件 runner）

**T3 走读阶段产出该仓 T6.3 的具体命令**，写入 findings-<repo>.md 的 "Mini E2E" 段。T6.3 执行时用该命令。

**若 T3 走读发现本仓没有合适的 mini E2E 候选且代码改动涉及 registry / plugin / CLI：** 作为 ② 类 findings 记入（"缺 mini E2E smoke 子集"），推荐处理 = 创建最小 smoke 目标 / 测试，由 T4 裁决是否本轮创建（一般 ✓：对租卡前自检有直接价值）。

- [ ] **Step T6.3 执行：**

```bash
<T3 走读确定的命令>  2>&1 | tail -40
```

Expected：exit 0；若是 pytest，全部绿。失败即 regression，回滚 T5 改动。

### T7 — 写 architecture.md

- [ ] **Step T7.1：创建 architecture.md**

按 spec §4.1 9 章模板写 `<repo>/docs/architecture.md`。

**质量门（非长度门）：**
- §4 每个关键模块必写 why / tradeoff / pitfall
- §8 每条 ① 类必写"删了会损失什么 + 重新审视的触发条件"
- §9 每条 ③ 未执行项必写"触发条件"
- 所有跨文档引用用相对路径

- [ ] **Step T7.2：自审 + 用户抽查**

我先 self-review 一遍（9 章完整 / 质量门满足），然后贴给用户抽查。用户无异议后进 T8。

### T8 — PR + 自审 + auto-merge

- [ ] **Step T8.1：创建 feature 分支**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/<repo>
git checkout -b feature/eco-<repo>-<topic>
# 若 T5 / T7 的 commit 在 dev 分支（不该发生，但防御），cherry-pick 过来
```

- [ ] **Step T8.2：push + 创建 PR**

```bash
git push -u origin feature/eco-<repo>-<topic>
gh pr create --base dev --title "eco(<repo>): <summary>" --body "$(cat <<'EOF'
## Summary
- <bullet 1>
- <bullet 2>

## Rationale
<为什么这么改；附 findings-<repo>.md 裁决链接>

## Test plan
- [x] make test 全绿
- [x] make lint 清洁
- [x] mini E2E（若适用）
- [x] ① 类已入 architecture.md §8
- [x] ② 类已修根因
- [x] ③ 类按裁决执行或留 §9

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step T8.3：PR 自审清单（spec §6.4）**

逐项勾：
- [ ] CI 全绿（本仓 + 被触发下游若有）
- [ ] 本地 `make test` + `make lint` 跑过（不信任只看 GH Actions）
- [ ] 改动符合 findings 裁决
- [ ] 无 no-hardcode / no-manual-workaround / refactor-no-legacy 违反
- [ ] 若涉及依赖治理，装序矩阵表已同步（pet-infra OVERVIEW §4）
- [ ] E2E 影响已验证（若适用）
- [ ] PR description 有 Summary + Rationale + Test plan

- [ ] **Step T8.4：auto-merge**

```bash
gh pr merge --auto --squash <PR#>
```

Expected：CI 绿后自动 squash merge 到 dev。

### T9 — 仓收尾

- [ ] **Step T9.1：dev → main sync PR**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/<repo>
git checkout dev && git pull --ff-only
gh pr create --base main --head dev --title "release(<repo>): sync dev→main v<new-version>" --body "Ecosystem optimization: <summary>"
gh pr merge --auto --squash <PR#>
```

- [ ] **Step T9.2：tag 新版本（若本仓 bump）**

参考 spec §6.3 版本表判断是否 bump。若 bump：

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/<repo>
git checkout main && git pull --ff-only
# 修 pyproject.toml 的 version 字段 → 新 version 应已在 T5 改过
git tag v<new-version>
git push origin v<new-version>
```

- [ ] **Step T9.3：更新 MEMORY**

编辑 `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/project_<repo>_status.md`：

- 把状态更新到新版本
- 记录本轮生态优化的关键改动（架构文档已建 / 依赖治理情况 / findings 统计）
- MEMORY.md 索引行同步更新

- [ ] **Step T9.4：Phase 完成验证**

逐项确认 spec §7.1 单仓 DoD 10 项全部 ✓，才进下一 Phase。

---

## Phase 0 — Preflight

### Task 0.1：跨仓干净状态验证

- [ ] **Step 0.1.1：验证 9 仓都在 dev 且干净**

```bash
for repo in pet-schema pet-infra pet-data pet-annotation pet-train pet-eval pet-quantize pet-ota pet-id; do
  echo "=== $repo ==="
  git -C /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo status --short
  git -C /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo fetch origin
  git -C /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo checkout dev
  git -C /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo pull --ff-only
done
```

Expected：每仓 status 干净、分支 dev、上游同步。pet-infra 应在 `feature/eco-spec` 分支（spec commit 所在），先切回 dev 再 pull。

- [ ] **Step 0.1.2：pet-infra 处理 spec 分支**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git checkout feature/eco-spec  # spec 分支
git push -u origin feature/eco-spec  # push spec 分支
gh pr create --base dev --title "docs(pet-infra): add ecosystem optimization spec + plan" --body "Spec + plan for 2026-04-23 ecosystem optimization phase. Passed spec-document-reviewer + plan-document-reviewer loops. Brainstorm Q1–Q6 aligned."
gh pr merge --auto --squash <PR#>  # 等 CI 绿 auto-merge
```

Expected：spec + plan PR merged 到 pet-infra dev。之后按 dev→main sync 在 Phase 10 或下一个合适时机做。

### Task 0.2：环境基线记录

- [ ] **Step 0.2.1：记录 conda 环境 freeze**

```bash
conda activate pet-pipeline
pip freeze > /tmp/eco-baseline-env.txt
```

保留此文件，Phase 10 GPU 租卡报告会对比。

- [ ] **Step 0.2.2：记录当前 matrix 2026.09 行**

```bash
grep -A 20 '2026.09' /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/docs/compatibility_matrix.yaml > /tmp/eco-baseline-matrix.txt
```

Phase 10 比对本轮 bump 后的差异。

### Task 0.3：记录 Phase 4 retro §7 待做项

- [ ] **Step 0.3.1：确认 §7 in-scope 项**

本轮 in scope（spec §0.3）：
- §7 #6 pet-infra compose 合并（实际是 `compose.py` + `recipe/compose.py`）
- §7 #7 pet-infra StageRunner DRY（5 类合并基类）
- §7 #8 W&B residue guard 补 pet-train / pet-eval / pet-quantize
- §7 #10 matrix `-rc` 约定文档化（进 OVERVIEW §3）

确认 pet-infra Phase 2 会承担 #6/#7/#10，pet-train/eval/quantize 各自 Phase 承担 #8。

### Task 0.4：Phase 0 commit

- [ ] **Step 0.4.1：commit preflight 产物**

Phase 0 不产生代码，只确认状态。不做额外 commit。

---

## Phase 1 — pet-schema Pass（链首，无依赖治理）

**pet-schema 特点：** 无上游 peer-dep；根契约；任何改动触发全链 CI；PR 需 2 位 reviewer approve（本轮 CTO 自审 + CI 绿 等效 approve，但需在 PR description 明确标注 "CTO-self-review per Q4(b) autonomous mode"）。

### Task 1.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（<repo> = `pet-schema`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 1.2：T3 CTO 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-schema 走读重点：
- `src/pet_schema/` Pydantic 模型（ModelCard / ExperimentRecipe / Annotation 四范式 / DpoPair / EdgeArtifact / DeploymentStatus）
- 字段完整性 vs 实际使用（是否有字段已添加但下游无消费）
- discriminator 实现（Phase 2 四范式）
- Alembic 迁移（不允许改，只能新增 — 走读只看不动）
- `_register.py`（若有，不太可能；pet-schema 是根）
- compose validator 逻辑（`model_validator(mode="after")`）

特别关注（基于 memory `project_pet_schema_status`）：
- v2.4.0 + `resolved_config_uri` 最新字段
- 四范式 discriminator 是否清晰、能否让新人看懂

### Task 1.3：T4 findings 裁决

- [ ] 执行 Template **T4.1 / T4.2**

### Task 1.4：T5 执行优化

- [ ] 执行 Template **T5.1 / T5.2 / T5.3**
- [ ] **Step T5.4 (pet-schema specific)：** 无（链首无依赖治理）

### Task 1.5：T6 回归

- [ ] 执行 Template **T6.1 / T6.2**（T6.3 不适用，pet-schema 无 E2E）

### Task 1.6：T7 写 architecture.md

- [ ] 执行 Template **T7.1 / T7.2**

pet-schema architecture.md 重点章节：
- §2 输入输出契约 —— 全仓下游列表（8 仓）+ 每个消费方用哪些类型
- §4 核心模块 —— ModelCard / ExperimentRecipe / Annotation 四范式 / DpoPair 各一节
- §5 扩展点 —— "如何添加一个新字段到 ModelCard" how-to
- §6 依赖管理 —— pet-schema 是根，对上游无依赖；说明 matrix 里本仓 pin 风格（选 β 则说 "peer-dep 由下游安装者按 matrix 装"，选 α 则说 "下游硬 pin 到本仓 tag"）—— pin 风格决策在 Phase 2 做，此处先写占位 "（见 Phase 2 pin 决策）"，Phase 2 完成后回填

### Task 1.7：T8 PR

- [ ] 执行 Template **T8.1 / T8.2 / T8.3 / T8.4**

Branch：`feature/eco-pet-schema-walkthrough`
PR title：`eco(pet-schema): CTO walkthrough + architecture.md`

### Task 1.8：T9 收尾

- [ ] 执行 Template **T9.1 / T9.2 / T9.3 / T9.4**

Version bump：视 findings 决定（spec §6.3）。若仅 ①/文档 → 不 bump。若 schema 字段调整（不太可能，因为那是 breaking）→ minor bump。

---

## Phase 2 — pet-infra Pass（最重，6 子任务叠加）

**pet-infra 特点：** 链第 2 位；**承载本轮最大工作量**；要完成 5 个 repo-specific 子任务 + 标准 T1–T9。此 Phase 预计产生 5–7 个 PR。

**Phase 2 repo-specific 子任务（均落在 T5.4）：**
- **2A：compose 模块合并**（retro §7 #6）
- **2B：StageRunner DRY 重构**（retro §7 #7）
- **2C：装序矩阵表 + smoke install CI workflow**（spec §4.1 治理第 4 条）
- **2D：pet-schema pin 风格 α/β 决策请求**（spec §5.2）
- **2E：OVERVIEW.md 撰写 + DEV_GUIDE §11 同步**（spec §5.4）

### Task 2.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-infra`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 2.2：T3 CTO 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-infra 走读重点：
- `src/pet_infra/` 全局：registry / plugin discovery / config / CLI / orchestrator
- `src/pet_infra/compose.py` + `src/pet_infra/recipe/compose.py` 两模块关系（confirm 重叠 / 导入链）
- `src/pet_infra/orchestrator/hooks.py` 5 个 StageRunner 类
- `src/pet_infra/storage/` 所有 backend（local / s3 / http）
- `src/pet_infra/experiment_logger/`（ClearML only，W&B 已清）
- `.github/workflows/` 所有现有 CI
- `docs/DEVELOPMENT_GUIDE.md` §11 依赖治理章节（走读时对比实际 pyproject / CI 是否一致）

### Task 2.3：T4 findings 裁决

- [ ] 执行 Template **T4.1 / T4.2**

裁决完后，2A / 2B 的具体范围应当由 findings 确认（裁决结果决定"合并到几个文件" / "DRY 抽象哪些共性"）。

### Task 2.4：T5.1 + T5.2 + T5.3 通用优化

- [ ] 执行 Template **T5.1 / T5.2 / T5.3**

### Task 2.5：T5.4(2A) compose 模块合并

- [ ] **Step 2A.1：分析两 compose 模块的职责分配**

```bash
wc -l src/pet_infra/compose.py src/pet_infra/recipe/compose.py
grep -n "def " src/pet_infra/compose.py src/pet_infra/recipe/compose.py
grep -rn "from pet_infra.compose\|from pet_infra.recipe.compose\|from pet_infra import compose" src/ tests/
```

Expected：列出两文件的函数签名 + 所有引用点。

- [ ] **Step 2A.2：确定合并方向**

两选项：
- α 合并到顶层 `compose.py`（`recipe/compose.py` 并入）
- β 合并到 `recipe/compose.py`（顶层 `compose.py` 删除）

决策原则：
- 哪个模块的现有引用点更少 → 删那个
- 合并后 import 路径尽量不变动外部（tests / 其他仓 若有引用）

我做初步判断后贴给用户确认选 α 还是 β。

- [ ] **Step 2A.3：写合并后的 compose 模块 test**

为合并后的所有函数写测试（TDD）；先确认现有测试覆盖的函数是否保留，缺失的补上。

```bash
pytest tests/recipe/test_compose.py tests/test_compose.py -v 2>&1 | tee /tmp/compose-before.log
```

- [ ] **Step 2A.4：执行合并**

按决策方向挪代码 + 更新 imports + 删除被合并文件。

```bash
git mv <source> <target>  # 或手动
ruff check --fix src/ tests/
```

- [ ] **Step 2A.5：回归测试**

```bash
pytest tests/ -v
```

Expected：之前覆盖的函数测试继续全绿；无 import error。若有 regression 回滚重做。

- [ ] **Step 2A.6：commit**

Branch：`feature/eco-pet-infra-compose-merge`
Message：
```
refactor(pet-infra): merge compose.py and recipe/compose.py into single module

Resolves Phase 4 retro §7 #6 (tech debt from Phase 3B). Two modules with overlapping
compose_recipe functions were inherited from Phase 3A Hydra migration; one imported
from the other. Consolidated into <chosen-path>.

findings ref: findings-pet-infra.md <line>
rationale: <merge direction choice reason>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 2.6：T5.4(2B) StageRunner DRY 重构

- [ ] **Step 2B.1：分析 5 个 StageRunner 类共性**

```bash
grep -n "class.*StageRunner" src/pet_infra/orchestrator/hooks.py
```

读这 5 个类的完整代码，找共性字段 + 共性方法 + 差异点。

- [ ] **Step 2B.2：设计 base class**

基于共性设计 `BaseStageRunner`（抽象类）；5 个具体类继承并 override 差异方法。

**防 over-engineering：** 如果共性 < 50%（即每个类独有代码占大头），DRY 反而增加理解成本 — 此时**不做 DRY**，只在 architecture.md §8 写清"为什么 5 个类不 DRY"。我会在走读时判断。

- [ ] **Step 2B.3：TDD — 先写 base class 测试**

```bash
pytest tests/orchestrator/test_base_stage_runner.py -v  # 初次运行应 fail
```

- [ ] **Step 2B.4：实现 base class + 重构 5 具体类**

每个具体类保留独有逻辑，共性进 base。

- [ ] **Step 2B.5：回归测试**

```bash
pytest tests/orchestrator/ -v
```

Expected：原 5 个类的测试全绿 + 新 base class 测试全绿。

- [ ] **Step 2B.6：commit**

Branch：`feature/eco-pet-infra-stage-runner-dry`
Message：
```
refactor(pet-infra): extract BaseStageRunner to DRY 5 StageRunner classes

Resolves Phase 4 retro §7 #7 (delayed for 2 phases). Common state + lifecycle
hooks extracted to BaseStageRunner; 5 concrete classes now override only
stage-specific methods.

findings ref: findings-pet-infra.md <line>
rationale: shared code coverage was X% — DRY profitable / (or) kept separate because common < 50%

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 2.7：T5.4(2C) 装序矩阵表 + 跨仓 smoke install CI

- [ ] **Step 2C.1：写 cross-repo-smoke-install.yml**

新文件 `pet-infra/.github/workflows/cross-repo-smoke-install.yml`：

```yaml
name: cross-repo-smoke-install
on:
  push:
    paths:
      - 'docs/compatibility_matrix.yaml'
  workflow_dispatch:

jobs:
  smoke-install:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        repo: [pet-data, pet-annotation, pet-train, pet-eval, pet-quantize, pet-ota, pet-id]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Parse latest matrix row
        id: matrix
        run: |
          python -c "
          import yaml
          data = yaml.safe_load(open('docs/compatibility_matrix.yaml'))
          latest = data['releases'][-1]
          for k, v in latest.items():
              if k.startswith('pet_'):
                  print(f'{k.upper()}={v}')
          " >> $GITHUB_OUTPUT
      - name: Install pet-infra (peer)
        run: |
          pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v${{ steps.matrix.outputs.PET_INFRA }}'
      - name: Install target repo
        run: |
          pip install 'pet-${{ matrix.repo }} @ git+https://github.com/Train-Pet-Pipeline/pet-${{ matrix.repo }}@v${{ steps.matrix.outputs[format('PET_{0}', replace(matrix.repo, '-', '_'))] }}' --no-deps
          pip install 'pet-${{ matrix.repo }} @ git+https://github.com/Train-Pet-Pipeline/pet-${{ matrix.repo }}@v${{ steps.matrix.outputs[format('PET_{0}', replace(matrix.repo, '-', '_'))] }}'
      - name: Version assertion
        run: |
          python -c "
          import pet_infra
          import importlib
          mod = importlib.import_module('pet_${{ matrix.repo }}'.replace('-', '_'))
          print(f'pet_infra={pet_infra.__version__}, pet_${{ matrix.repo }}={mod.__version__}')
          "
```

（具体 YAML 语法按实际 matrix 结构调整，在 T5.4(2E) 写 OVERVIEW §4 时二次核对一致。）

- [ ] **Step 2C.2：本地 act 或手动触发验证**

```bash
gh workflow run cross-repo-smoke-install.yml
```

Expected：7 个 matrix job 全绿。失败则修 YAML 表达式 / matrix 解析逻辑。

- [ ] **Step 2C.3：commit**

Branch：`feature/eco-pet-infra-smoke-install-ci`
Message：
```
ci(pet-infra): add cross-repo-smoke-install workflow (ecosystem gov #4)

Triggers on docs/compatibility_matrix.yaml push; installs pet-infra + each
downstream repo at matrix-pinned version; asserts imports succeed. Turns
compatibility_matrix.yaml from a snapshot table into an enforced constraint.

findings ref: spec §4.1 governance item #4

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 2.8：T5.4(2D) pet-schema pin 风格决策请求

- [ ] **Step 2D.1：对比实际代码与 spec §5.2 表**

```bash
for d in pet-schema pet-infra pet-data pet-annotation pet-train pet-eval pet-quantize pet-ota pet-id; do
  echo "=== $d ==="
  grep -n "pet-schema" /Users/bamboo/Githubs/Train-Pet-Pipeline/$d/pyproject.toml 2>/dev/null
done
```

确认 spec §5.2 表仍然准确（硬 pin 4 / 无 pin 2 / 不依赖 2）。

- [ ] **Step 2D.2：贴决策请求给用户**

贴 spec §5.2 两选项 + 当前代码实测表给用户，等用户拍板 α 或 β。我带 CTO 视角初判：β（与 peer-dep 模式一致 + bump 扩散小）。

**Gate：** 此决策在 2D.2 拍板后，Phase 3–8 的 T5.4 各 Phase-specific 子任务才能确定。

- [ ] **Step 2D.3：记录决策到 spec + retrospective 前置草稿**

用户拍板后，编辑 spec §5.2 把"初判（非最终）"段改为"最终决策"段。

### Task 2.9：T5.4(2E) OVERVIEW.md + DEV_GUIDE §11 同步

- [ ] **Step 2E.1：创建目录 + 写 OVERVIEW.md**

```bash
mkdir -p /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/docs/architecture
```

按 spec §4.2 8 章模板写 `pet-infra/docs/architecture/OVERVIEW.md`。

**质量门：**
- §1 pipeline 全景含 9 仓 + pet-demo（另 agent 负责，matrix 登记）
- §2 依赖关系图 用 mermaid `graph TD`（GitHub 原生渲染）
- §3 依赖治理约定 包含 pin 风格最终决策（α 或 β）
- §4 装序矩阵表 ★核心 —— 含 9 仓每仓的 peer-dep 列表 + 装序步数 + CI workflow 路径 + version assertion 命令
- §5 跨仓 CI guard 清单（4 个 workflow）
- §6 北极星四维映射 9×4 矩阵
- §7 新人上手路径
- §8 本文档与 DEV_GUIDE 分工

- [ ] **Step 2E.2：同步 DEV_GUIDE §11**

编辑 `pet-infra/docs/DEVELOPMENT_GUIDE.md` §11：
- §11.1：反映 pin 风格最终决策
- §11.2：pyproject.toml 示例改到最终形态
- §11.3：`_register.py` guard 模板（若选 β 增加 pet-schema 分支）
- §11.4 / §11.4.3 / §11.6：装序步数引用 OVERVIEW §4 为权威（避免重复，防 drift）

- [ ] **Step 2E.3：commit**

Branch：`feature/eco-pet-infra-overview-docs`
Message：
```
docs(pet-infra): add OVERVIEW.md + sync DEV_GUIDE §11 to ecosystem-optimized state

- New pet-infra/docs/architecture/OVERVIEW.md: system-level pipeline,
  dependency graph, install-order matrix, CI guards, North Star matrix
- DEV_GUIDE §11 now reflects pet-schema pin decision <α|β> and points to
  OVERVIEW §4 as canonical install-order source
- Resolves Phase 4 retro §7 #10 (matrix -rc convention documented in §3)

findings ref: spec §4.2 / §5.4
rationale: centralizes dependency governance in one authoritative doc

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 2.10：T6 回归

- [ ] 执行 Template **T6.1 / T6.2**（T6.3 pet-infra 不是 E2E 运行仓，跳过）

### Task 2.11：T7 写 pet-infra architecture.md

- [ ] 执行 Template **T7.1 / T7.2**（pet-infra 本仓 architecture.md）

pet-infra `docs/architecture.md` 重点章节：
- §4 核心模块 —— `registry / compose (合并后) / orchestrator (DRY 后) / storage / experiment_logger / cli`
- §5 扩展点 —— "如何添加一个新 storage backend / 新 plugin 类型"
- §8 已知复杂点 —— Hydra defaults-list + multirun 实现的微妙之处；registry 发现机制；若 2B 未 DRY 写清楚为什么不合
- §9 Followups —— 合入 retro §7 out-of-scope 项

### Task 2.12：T8 PR（所有前置 Phase 2 改动进 dev）

- [ ] 执行 Template **T8.1 / T8.2 / T8.3 / T8.4** × 每个 feature 分支

pet-infra Phase 2 预计 PR 链（顺序 merge）：
1. `feature/eco-pet-infra-compose-merge` → dev
2. `feature/eco-pet-infra-stage-runner-dry` → dev（依赖 1）
3. `feature/eco-pet-infra-smoke-install-ci` → dev
4. `feature/eco-pet-infra-overview-docs` → dev（依赖 2D 决策）
5. `feature/eco-pet-infra-architecture-md` → dev（依赖 1/2/3/4）
6. （可选）`feature/eco-pet-infra-findings-cleanup` → dev（若 T5.2/T5.3 改动较大，独立 PR）

### Task 2.13：T9 收尾 + bump v2.6.0

- [ ] 执行 Template **T9.1 / T9.2 / T9.3 / T9.4**

Version bump：**2.5.0 → 2.6.0** minor（spec §6.3）

- `pyproject.toml` version 改 2.6.0（在 T5.4 任一子任务 commit 里改）
- T9.1 dev→main sync PR
- T9.2 tag v2.6.0
- T9.3 更新 `project_pet_infra_status.md` + MEMORY.md 索引

---

## Phase 3 — pet-data Pass

**repo-specific 子任务：** 按 2D 决策调整 pet-schema pin（若选 β：删 pyproject pin + 加 _register.py guard；若选 α：保持现有硬 pin 不变，但对齐到最新 pet-schema tag）

### Task 3.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-data`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 3.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-data 走读重点：
- `src/pet_data/` 主代码（采集 / 清洗 / 增强 / 弱监督 / store.py / dedup.py）
- `_register.py` 现有 pet-infra guard（看模板）
- modality 维度（Phase 2 引入）
- Alembic 迁移 目录（已提交不可改）
- `pyproject.toml` 当前 pet-schema 硬 pin v2.0.0（落后于现 v2.4.0 → ② 类）

### Task 3.3：T4 裁决

- [ ] 执行 Template **T4.1 / T4.2**

### Task 3.4：T5 执行

- [ ] 执行 Template **T5.1 / T5.2 / T5.3**

- [ ] **Step T5.4(pet-data 3A) pet-schema pin 调整**

按 2D 决策：
- **若 β：** 删除 `pyproject.toml` 的 `pet-schema @ git+...@v2.0.0` 行；在 `src/pet_data/_register.py` 加 pet-schema fail-fast guard；修 CI workflow 装序增加 pet-schema 步骤
- **若 α：** 升级 `pet-schema @ git+...@v2.0.0` 到 `@v2.4.0`（当前最新）

TDD 步骤：
1. 先写一个测试验证 pet-schema 能 import（若 guard 生效，missing 情况 fail）
2. 实现改动
3. 跑测试

Commit：`refactor(pet-data): align pet-schema pin to matrix 2026.10 (<α|β>)`

### Task 3.5：T6 / T7 / T8 / T9

- [ ] 执行 Template **T6 / T7 / T8 / T9**

pet-data architecture.md 重点章节：
- §4 核心模块 —— collection / cleaning / augmentation / weak_supervision / store（只通过这操作 DB 的唯一入口）
- §5 扩展点 —— DATASETS registry 添加新数据源；modality 扩展
- §8 已知复杂点 —— dedup.py 不允许 skip 的理由；Alembic 迁移只能新增

Version bump：视 findings 决定（若仅 pin 调整 + 文档 → patch；若精简命中代码 → minor）

---

## Phase 4 — pet-annotation Pass

**repo-specific 子任务：** 同 Phase 3（pet-schema pin 按决策调整）

### Task 4.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-annotation`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 4.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-annotation 走读重点：
- `src/pet_annotation/` 四范式 annotator（llm / classifier / rule / human）
- DPO 对生成
- Label Studio integration（session auth E2E 已验证，memory `project_labelstudio_status`）
- 质检 / 人工审核流
- pet-schema v2.1.0 四表结构对齐

### Task 4.3：T4 / T5 / T6 / T7 / T8 / T9

- [ ] 执行 Template **T4 / T5 / T6 / T7 / T8 / T9**

- [ ] **Step T5.4(pet-annotation 4A) pet-schema pin 调整**（同 Phase 3 的 3A）

pet-annotation architecture.md 重点章节：
- §4 核心模块 —— 4 annotator plugin / DPO pair generator / Label Studio bridge
- §5 扩展点 —— "如何添加一个 new annotator_type plugin"（覆盖 llm/classifier/rule/human 之外）
- §8 已知复杂点 —— 四范式表拆分的理由（Phase 2 BREAKING）

Version bump：视 findings 决定

---

## Phase 5 — pet-train Pass

**repo-specific 子任务：**
- 5A：pet-schema pin 调整（若 α → 加 pin 到 v2.4.0；若 β → 保持现无 pin）
- 5B：补 W&B residue CI guard（retro §7 #8）

### Task 5.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-train`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 5.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-train 走读重点：
- `src/pet_train/` SFT / DPO / audio CNN trainer plugins
- `vendor/LLaMA-Factory` 源码（走读不动，只看约定）
- PANNs 零样本推理（pet-eval 跨仓引用）
- W&B 残留扫（清完但要确认 no-wandb-residue CI 本仓现状）
- pyproject.toml drift fix 历史（memory `project_pet_train_status`）

### Task 5.3：T4 / T5 基础

- [ ] 执行 Template **T4 / T5.1 / T5.2 / T5.3**

### Task 5.4：T5.4(5A) pet-schema pin 调整

- [ ] 按 2D 决策调整（同 Phase 3 的 3A）

### Task 5.5：T5.4(5B) 补 W&B residue CI guard

- [ ] **Step 5B.1：复制 pet-infra 的 no-wandb-residue.yml**

```bash
cp /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/.github/workflows/no-wandb-residue.yml \
   /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train/.github/workflows/no-wandb-residue.yml
```

- [ ] **Step 5B.2：调整 repo-specific 路径（若模板有 repo name 硬编码）**

检查 workflow 文件里是否有 "pet-infra" 字样；有则改为 "pet-train"。

- [ ] **Step 5B.3：push 前先本地扫**

```bash
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-train
grep -rn "wandb\|import wandb\|WandB\|wandbapi" src/ tests/ config/ --include='*.py' --include='*.yaml'
```

Expected：无命中（Phase 4 P1-F 已物理清除 memory `project_pet_train_status`）。若有命中，先修掉（② 类）。

- [ ] **Step 5B.4：触发 workflow 验证**

push 后手动触发：
```bash
gh workflow run no-wandb-residue.yml
```

Expected：绿。

- [ ] **Step 5B.5：commit**

Branch：`feature/eco-pet-train-wandb-guard`
Message：
```
ci(pet-train): add no-wandb-residue guard (retro §7 #8)

Mirrors pet-infra/.github/workflows/no-wandb-residue.yml. W&B physically
removed in Phase 4 P1-F; this guard prevents regression.

findings ref: spec §5.1 governance #5

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 5.6：T6 回归

- [ ] 执行 Template **T6.1 / T6.2**
- [ ] **Step T6.3 (pet-train)：** 跑 mini SFT smoke

```bash
make smoke-sft 2>&1 | tail -40
```

Expected：exit 0，artifact 落盘。失败即 regression。

### Task 5.7：T7 / T8 / T9

- [ ] 执行 Template **T7 / T8 / T9**

pet-train architecture.md 重点章节：
- §4 核心模块 —— SFT trainer / DPO trainer / audio CNN trainer / vendor LLaMA-Factory bridge
- §5 扩展点 —— TRAINERS registry 添加新 trainer；audio namespace 扩展
- §8 已知复杂点 —— LLaMA-Factory 源码 vendor 策略；PANNs 零样本推理跨仓依赖

Version bump：**2.0.1 → 2.0.2** patch（W&B guard CI-only）；若 findings 触发代码精简则 minor → 2.1.0

---

## Phase 6 — pet-eval Pass

**repo-specific 子任务：**
- 6A：pet-schema pin 调整（同 Phase 3）
- 6B：补 W&B residue CI guard（同 5B）

### Task 6.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-eval`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 6.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-eval 走读重点：
- `src/pet_eval/` 8 metric plugins + 2 evaluators + 3 fusion evaluators（Phase 4 新增）
- vendor `lm-evaluation-harness`（走读不动）
- 跨仓 plugin：`AudioEvaluator` 用 pet_train / `QuantizedVlmEvaluator` 用 pet_quantize（pyproject 已有无 pin 跨仓 runtime deps）
- 装序 6-step（最复杂）
- `pet-schema` 无 pin + `pet-train` / `pet-quantize` 无 pin 当前状态（spec §5.2 状态）

### Task 6.3：T4 / T5 / T6 / T7 / T8 / T9

- [ ] 执行 Template **T4 / T5 / T6 / T7 / T8 / T9**

- [ ] **Step T5.4(6A) pet-schema pin 调整**（同 Phase 3 的 3A）
- [ ] **Step T5.4(6B) 补 W&B residue CI guard**（同 Phase 5 的 5B）

- [ ] **Step T6.3 (pet-eval)：** 跑 3 evaluator 各一次（含 fusion dry-run）

```bash
pet eval --recipe tests/fixtures/eval_smoke.yaml --dry-run-hardware
```

Expected：exit 0；fusion 三策略（single_modal / and_gate / weighted）各产出 artifact。

pet-eval architecture.md 重点章节：
- §4 核心模块 —— 8 metric plugins / text/audio/quantized_vlm evaluators / 3 fusion evaluators
- §5 扩展点 —— EVALUATORS registry / METRICS registry 添加；fusion 策略扩展（rule-based only per `feedback_no_learned_fusion`）
- §8 已知复杂点 —— 跨仓 runtime import（pet_train/pet_quantize），6-step 装序原因；为什么不做 learned fusion

Version bump：**2.2.0 → 2.2.1** patch；若 findings 触发代码精简则 minor → 2.3.0

---

## Phase 7 — pet-quantize Pass

**repo-specific 子任务：**
- 7A：pet-infra 从硬 pin 改 peer-dep（治理项 #1，spec §5.1）
- 7B：pet-schema pin 调整（若 β → 保持硬 pin 但升级 tag；若 α → 保持硬 pin 升级 tag）
- 7C：补 W&B residue CI guard（同 5B）

### Task 7.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-quantize`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 7.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-quantize 走读重点：
- `src/pet_quantize/` 4 CONVERTERS plugin（rknn / rkllm / onnx / gguf）
- `inference/rkllm_runner.py`（被 pet-eval 跨仓 runtime 引用）
- 当前 pyproject 硬 pin pet-infra v2.5.0 **违反 peer-dep 约定**（治理 #1）
- hardware-dry-run 逻辑

### Task 7.3：T4 / T5 基础

- [ ] 执行 Template **T4 / T5.1 / T5.2 / T5.3**

### Task 7.4：T5.4(7A) pet-infra 改 peer-dep

- [ ] **Step 7A.1：删除 pyproject.toml pet-infra 硬 pin 行**

```bash
# 编辑 pet-quantize/pyproject.toml dependencies = [ ... ]
# 删除: "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v2.5.0",
```

- [ ] **Step 7A.2：核对已有 guard + 更新过期字段**

**现状（实测 2026-04-23）：** `src/pet_quantize/plugins/_register.py`（注意是嵌套在 `plugins/` 下，**不是 top-level**）已有 guard：

```python
# 当前实现
def register_all() -> None:
    try:
        import pet_infra  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "pet-quantize v2 requires pet-infra. Install via matrix row 2026.08."
        ) from e
    # ... 后续 import plugin 模块
```

**与 DEV_GUIDE §11.3 模板差异：**
1. guard 位于 `register_all()` 函数内（延迟到 plugin 注册时触发），**不是** 模板要求的"模块顶部、任何 import 之前"
2. raise 的是 `RuntimeError` 而不是模板的 `ImportError`
3. 错误消息引用 "matrix row 2026.08"（已过期，当前是 2026.09，本轮将推 2026.10）

**裁决（T4 gate 讨论 + 如果 T3 走读未单独记这条，在 T5.4 时补）：**
- **选项 X**（保守）：保持延迟模式 + RuntimeError 不动；**只**更新错误消息 "matrix row 2026.08" → "matrix row 2026.10"；**同时**更新 DEV_GUIDE §11.3 模板，承认延迟模式并列出两种变体（顶部 ImportError / register_all RuntimeError 各自适用场景）
- **选项 Y**（严格）：把 guard 移到模块顶部按 §11.3 模板严格实施；现有 register_all 内部 guard 删除；raise ImportError；matrix 字符串更新

初判（CTO 视角）：**选项 X** — 延迟模式已在生产多个版本无事故；顶部 guard 会让纯 import 都强制依赖 pet_infra（影响 IDE tooling / 静态分析工具直接读源码的场景）；选 X 既修 stale matrix 字段，又让 DEV_GUIDE 与实现对齐（feedback_devguide_sync 精神）。

**Gate：** 本步骤在 T3/T4 findings 阶段作为 ② 或 ③ 类登记，T4 用户裁决 X / Y。

- [ ] **Step 7A.3：更新 CI workflow 装序到 4 步（§11.4）**

编辑 `pet-quantize/.github/workflows/ci.yml`（或等价）：

```bash
# Step 1: install pet-infra peer (pinned to matrix row)
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.6.0'

# Step 2: editable install without re-resolving peers
pip install -e ".[dev]" --no-deps

# Step 3: re-resolve dev extras
pip install -e ".[dev]"

# Step 4: version assertion
python -c "import pet_infra; assert pet_infra.__version__.startswith('2.'), pet_infra.__version__"
```

- [ ] **Step 7A.4：更新 README Prerequisites 段**

按 DEV_GUIDE §11.2 模板加 "Prerequisites: pet-infra >= 2.6.0 must be installed first"

- [ ] **Step 7A.5：本地验证 fresh venv 装**

```bash
python -m venv /tmp/test-venv-pet-quantize && source /tmp/test-venv-pet-quantize/bin/activate
# 按 4 步装序
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.6.0'
pip install -e . --no-deps
pip install -e ".[dev]"
python -c "import pet_quantize; print(pet_quantize.__version__)"
deactivate
```

Expected：装完 import 无 error；pet-infra guard 未 trip。

- [ ] **Step 7A.6：verify forgot-to-install-pet-infra 场景 guard 生效**

```bash
python -m venv /tmp/test-venv-guard && source /tmp/test-venv-guard/bin/activate
pip install -e . --no-deps
python -c "import pet_quantize" 2>&1 | tee /tmp/guard-error.log
deactivate
```

Expected：stdout/stderr 含 "pet-quantize requires pet-infra to be installed first"。

- [ ] **Step 7A.7：commit**

Branch：`feature/eco-pet-quantize-peerdep-fix`
Message：
```
refactor(pet-quantize): migrate pet-infra dep from hardpin to peer-dep

Resolves spec §5.1 governance item #1. pet-infra hard-pin (@v2.5.0) violated
DEV_GUIDE §11.1 peer-dep convention and required same-PR changes across downstream
repos on each pet-infra bump. Now follows pet-data/pet-annotation pattern:
- pyproject.toml: pet-infra removed from dependencies
- _register.py: fail-fast guard added
- CI: 4-step install order per DEV_GUIDE §11.4
- README: Prerequisites section added

findings ref: spec §5.1 #1
rationale: consistency with peer-dep model; unblocks pet-infra's auto-bump

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 7.5：T5.4(7B) pet-schema pin 调整 + T5.4(7C) W&B guard

- [ ] 同 Phase 3 3A（pet-schema pin）
- [ ] 同 Phase 5 5B（W&B guard）

### Task 7.6：T6 回归

- [ ] 执行 Template **T6.1 / T6.2**
- [ ] **Step T6.3 (pet-quantize)：** dry-run 1 converter

```bash
pet quantize --recipe tests/fixtures/quantize_smoke.yaml --dry-run-hardware
```

Expected：exit 0；artifact 落盘。

### Task 7.7：T7 / T8 / T9

- [ ] 执行 Template **T7 / T8 / T9**

pet-quantize architecture.md 重点章节：
- §4 核心模块 —— 4 CONVERTERS plugin / rkllm_runner（跨仓被 pet-eval 引用）
- §5 扩展点 —— CONVERTERS registry 添加新量化格式
- §6 依赖管理 —— pet-infra 从本次改为 peer-dep；引用 OVERVIEW §4
- §8 已知复杂点 —— dry-run-hardware 机制；为什么 rkllm_runner 被 pet-eval 跨仓引用而不移到 pet-infra

Version bump：**2.0.1 → 2.1.0** minor（peer-dep 修正 + W&B guard + 文档）

---

## Phase 8 — pet-ota Pass

**repo-specific 子任务：**
- 8A：pet-infra 从硬 pin 改 peer-dep（治理项 #1）
- 8B：pet-quantize 从范围 `>=1.0.0` 改无 pin 跨仓 runtime（治理项 #2）

### Task 8.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-ota`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 8.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-ota 走读重点：
- `src/pet_ota/` OTA registry + backend plugins（Local / S3 / HTTP Phase 4 shipped）
- manifest / rollout / rollback 逻辑
- hardware-dry-run 路径
- 当前 pyproject：pet-infra 硬 pin ⚠️ + pet-quantize `>=1.0.0` 范围 ⚠️（2 种非标形态）

### Task 8.3：T4 / T5 基础

- [ ] 执行 Template **T4 / T5.1 / T5.2 / T5.3**

### Task 8.4：T5.4(8A) pet-infra 改 peer-dep

同 Phase 7 的 7A（流程相同，文件名换 pet-ota）。

**现状（实测 2026-04-23）：** `src/pet_ota/plugins/_register.py`（嵌套在 `plugins/` 下）同样已有 guard + 同样的过期字段："pet-ota v2 requires pet-infra. Install via matrix row 2026.08."

**Step 8A.1–8A.7：** 按 7A.1–7A.7 执行，所有 "pet-quantize" 替换为 "pet-ota"。T4 裁决选 X（保守：更新 matrix 字段 + 同步 DEV_GUIDE §11.3）或 Y（严格：移 guard 到模块顶部）— 两仓决策必须一致（不允许一仓 X 一仓 Y，生态优化目标是一致性）。

Branch：`feature/eco-pet-ota-peerdep-fix`

### Task 8.5：T5.4(8B) pet-quantize 改无 pin

- [ ] **Step 8B.1：修改 pyproject.toml**

```toml
# 原：
# "pet-quantize>=1.0.0",
# 改为无 pin（跨仓 runtime plugin dep）：
"pet-quantize",
```

- [ ] **Step 8B.2：CI 装序增加 pet-quantize 步骤**

按 DEV_GUIDE §11.6 跨仓 plugin dep 装序（5 步，类似 pet-eval 但只有 pet-quantize 一个跨仓 dep）：

```bash
# Step 1: pet-infra peer
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@v2.6.0'
# Step 2: pet-quantize peer
pip install 'pet-quantize @ git+https://github.com/Train-Pet-Pipeline/pet-quantize@v2.1.0'
# Step 3: editable install without re-resolving
pip install -e ".[dev]" --no-deps
# Step 4: re-resolve dev extras
pip install -e ".[dev]"
# Step 5: version assertion
python -c "import pet_infra, pet_quantize, pet_ota; assert pet_ota.__version__.startswith('2.')"
```

- [ ] **Step 8B.3：_register.py 加 pet-quantize guard（可选）**

如果 pet-ota 运行时真的 import pet_quantize（不只是 manifest 格式对接），则加 guard；否则 skip（不做 YAGNI 加法）。走读 T3 确定。

- [ ] **Step 8B.4：commit**

Branch：`feature/eco-pet-ota-quantize-pin-unify`
Message：
```
refactor(pet-ota): align pet-quantize dep to no-pin cross-repo plugin style

Resolves spec §5.1 governance item #2. pet-quantize was pinned as `>=1.0.0`
(the 3rd style among 9 repos). Now consistent with pet-eval's cross-repo
plugin pattern: no pin in pyproject, matrix-locked, CI 5-step install order.

findings ref: spec §5.1 #2
rationale: style unification across ecosystem; matrix remains single truth source

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 8.6：T6 / T7 / T8 / T9

- [ ] 执行 Template **T6 / T7 / T8 / T9**

pet-ota architecture.md 重点章节：
- §4 核心模块 —— OTA registry / 3 backend plugins / manifest / rollout
- §5 扩展点 —— OTA registry 添加新 backend（CDN / mTLS HTTP 等）
- §6 依赖管理 —— 本次从 2 种非标 pin 统一到 peer-dep（pet-infra）+ 无 pin（pet-quantize）；引用 OVERVIEW §4
- §8 已知复杂点 —— 灰度部署机制；rollback state 语义

Version bump：**2.1.0 → 2.2.0** minor

---

## Phase 9 — pet-id Pass（独立工具）

**repo-specific 子任务：** 无依赖治理（不依赖任何 pet-* 包）

### Task 9.1：T1 + T2 基线

- [ ] 执行 Template **T1.1 / T1.2 / T1.3**（`<repo>` = `pet-id`）
- [ ] 执行 Template **T2.1 / T2.2 / T2.3**

### Task 9.2：T3 走读

- [ ] 执行 Template **T3.1 / T3.2**

pet-id 走读重点：
- `src/pet_id_registry/` PetCard registry + petid CLI（register / identify / list / show / delete）
- `src/purrai_core/` 核心识别逻辑（detection / re-id / pose / narrative / tracker 的实现）
- 包结构：`pet_id_registry` 对外 CLI 入口；`purrai_core` 算法核心
- 5 个可选 extras（detector / reid / pose / narrative / tracker）对应 `purrai_core` 可选子模块
- 独立 CLI 工具，不 import 任何 pet-* 包（spec §5.2 实锤）

### Task 9.3：T4 / T5 / T6 / T7 / T8 / T9

- [ ] 执行 Template **T4 / T5 / T6 / T7 / T8 / T9**（T5.4 无子任务，T6.3 不适用）

pet-id architecture.md **必须包含**：
- §1 明确声明 "pet-id 是独立 CLI 工具，不参与 peer-dep 生态；matrix 登记仅作版本对齐"
- §2 输入输出契约 写清对 pet-* 无依赖；对外输出 PetCard（独立 pydantic model，不在 pet-schema）
- §3 架构总览 讲清 `pet_id_registry`（CLI 入口）vs `purrai_core`（算法核心）的分层关系
- §6 依赖管理 只列第三方（numpy / pydantic / cv2 / torch / ...）
- §8 已知复杂点 —— 5 个 extras 的取舍；为什么包结构是 `pet_id_registry` + `purrai_core` 而不是合成 `pet_id`

Version bump：视 findings 决定；独立工具一般不 bump（除非代码改动）

---

## Phase 10 — Ecosystem Closeout

### Task 10.1：更新 compatibility_matrix.yaml 新增 2026.10 行

- [ ] **Step 10.1.1：聚合各仓最终版本**

```bash
for d in pet-schema pet-infra pet-data pet-annotation pet-train pet-eval pet-quantize pet-ota pet-id; do
  echo "=== $d ==="
  grep "^version" /Users/bamboo/Githubs/Train-Pet-Pipeline/$d/pyproject.toml
done
```

记下每仓最终版本。

- [ ] **Step 10.1.2：编辑 matrix**

编辑 `pet-infra/docs/compatibility_matrix.yaml` 末尾追加新 release：

```yaml
  - release: "2026.10-ecosystem-cleanup"
    released: 2026-XX-XX
    phase: ecosystem-optimization
    pet_schema: "<final>"
    pet_infra: "2.6.0"
    pet_data: "<final>"
    pet_annotation: "<final>"
    pet_train: "<final>"
    pet_eval: "<final>"
    pet_quantize: "2.1.0"
    pet_ota: "2.2.0"
    pet_id: "<final>"
    pet_demo: "1.0.1"              # unchanged (另 agent 负责)
    clearml: ">=1.14,<2.0"
    mmengine_lite: ">=0.10,<0.12"
    hydra_core: ">=1.3,<1.4"
    rknn_toolkit2: "==2.0.0"
    rkllm_toolkit: "==1.2.0"
    notes: |
      Ecosystem optimization phase: per-repo CTO walkthrough + architecture docs
      (8 × architecture.md + OVERVIEW.md), dependency governance unified
      (pet-schema pin style <α|β>, pet-quantize/pet-ota peer-dep fix, W&B
      residue guard on all repos, cross-repo smoke install CI), Phase 4 retro
      §7 #6 #7 #8 #10 resolved.
```

- [ ] **Step 10.1.3：触发 smoke-install workflow 验证**

push 后 cross-repo-smoke-install workflow 应自动跑。

```bash
gh workflow run cross-repo-smoke-install.yml
```

Expected：7 个 matrix job 全绿（装序矩阵表 + 实际行为 100% 一致）。

- [ ] **Step 10.1.4：commit**

Branch：`feature/eco-matrix-2026.10`
Message：
```
docs(pet-infra): compatibility_matrix.yaml add 2026.10-ecosystem-cleanup row

Aggregates all final versions from ecosystem optimization phase. Triggers
cross-repo-smoke-install workflow for cross-repo install order verification.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### Task 10.2：写 retrospective

- [ ] **Step 10.2.1：创建 retrospective 文件**

```bash
touch /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/docs/retrospectives/2026-XX-XX-ecosystem-optimization.md
```

按 spec §7.3 9 章结构写：
- §1 代码交付（What Shipped）
- §2 最终版本表（before/after + matrix 2026.10 行）
- §2b CI 全绿验证
- §3 北极星四维度自检 + 净影响评估
- §4 Drift / Execution-time 决策（Q5 ③ 类裁决明细 / pet-schema pin α/β 最终决策）
- §5 Findings 累计表（按仓 ①/②/③ 数量 + 典型条目）
- §6 依赖治理成果（5 条逐条验收 + 装序矩阵表链接）
- §7 CTO 视角：本轮学到的 ★ spec §1 新增章节
- §8 Phase 5+ 跟进清单（合并 Phase 4 retro §7 遗留 + 本轮新增）
- §9 致谢 / 签署

- [ ] **Step 10.2.2：commit**

Branch：`feature/eco-retrospective`
Message：`docs(pet-infra): ecosystem optimization retrospective`

### Task 10.3：写 GPU 租卡前自检报告

- [ ] **Step 10.3.1：创建自检报告**

`pet-infra/docs/gpu-session-readiness-2026-XX.md`（或 retrospective 附录 §10）：

- 9 仓最终 CI 状态（tag + latest CI run links）
- conda `pet-pipeline` 环境 freeze 输出（对比 Phase 0 基线看 diff）
- 已知可跑 recipe 清单：before/after 对照
- 疑似风险点：②/③ 类改动涉及 registry / plugin / CLI / store 的清单（租卡盯）
- 租卡建议执行顺序：最简 smoke → 实际 training recipe → E2E

- [ ] **Step 10.3.2：commit**

同 Task 10.2 合 PR（`feature/eco-retrospective` 分支），或独立 `feature/eco-gpu-readiness` 分支（视内容长度）。

### Task 10.4：MEMORY 刷新

- [ ] **Step 10.4.1：新建 `project_ecosystem_optimization.md`**

```markdown
---
name: Ecosystem Optimization Complete
description: 生态优化完成 <date> — 9 仓每仓 architecture.md + OVERVIEW.md + 装序矩阵 + 依赖治理统一 + 4 CI guard；matrix 2026.10；retrospective 4 维 ≥ 3/5 保持 5/5；GPU 租卡就绪
type: project
---
生态优化收官 <date>。N PR 全 shipped；feature/eco-* → dev → main 全通；所有 tag + matrix + 新 CI + 新文档都在 main。

**最终版本表：** <聚合 matrix 2026.10>

**文档交付：** 8 份本仓 architecture.md + pet-infra architecture.md + OVERVIEW.md + DEV_GUIDE §11 同步到与 OVERVIEW 一致

**依赖治理成果：**
- pet-schema pin 风格：<α|β> 统一，全 <4|6> 仓生效
- pet-quantize / pet-ota：pet-infra 从硬 pin 改 peer-dep（§5.1 #1 / #2）
- pet-quantize range pin 统一（§5.1 #2）
- cross-repo-smoke-install.yml CI 首次运行绿
- W&B residue guard：pet-train/eval/quantize 各 1 份

**retrospective：** `pet-infra/docs/retrospectives/2026-XX-XX-ecosystem-optimization.md`

**GPU 租卡就绪：** `pet-infra/docs/gpu-session-readiness-2026-XX.md`（报告已交付）；等用户触发租卡 session。

**Phase 5 触发：** 等用户触发（retrospective §8 列了跟进清单）。
```

- [ ] **Step 10.4.2：更新 MEMORY.md 索引**

在 `/Users/bamboo/.claude/projects/-Users-bamboo-Githubs-Train-Pet-Pipeline/memory/MEMORY.md` 加一行：
```
- [Ecosystem Optimization](project_ecosystem_optimization.md) — 完成 <date>，9 仓 architecture.md + OVERVIEW + 依赖治理统一 + matrix 2026.10 + 租卡就绪
```

- [ ] **Step 10.4.3：9 仓 status memory 刷新**

对每仓 `project_<repo>_status.md`：
- 更新到最新版本
- 加一句 "生态优化 <date> 完成"

### Task 10.5：全阶段 DoD 验证

- [ ] **Step 10.5.1：逐项勾 spec §7.2 全阶段 DoD**

按 spec §7.2 四层（代码/工程 + 文档 + 北极星 + 交付）逐项勾。任一项不 ✓ 则回溯修到 ✓ 再进 10.6。

### Task 10.6：最终 dev→main sync

- [ ] **Step 10.6.1：各仓 dev→main sync（Phase 1–9 若未完成）**

遍历 9 仓，确认 dev 和 main 同步；未同步的仓开 `sync/eco-<repo>-vX.Y.Z` sync PR。

- [ ] **Step 10.6.2：pet-infra Phase 10 PR 链 dev→main**

matrix 2026.10 + retrospective + GPU readiness 的 PR 合到 dev 后，开 `sync/eco-phase-closing` → main。

### Task 10.7：Phase 收尾 + stop

- [ ] **Step 10.7.1：声明 ecosystem optimization 完成**

向用户汇报：
- PR 总数
- 9 仓最终版本
- retrospective 链接
- GPU 租卡报告链接
- **停下。** 不自动触发租卡、不自动进 Phase 5（`feedback_phase3_autonomy`）。

---

## 执行风险与缓解（复述 spec §8）

| 风险 | 缓解 |
|---|---|
| findings ③ 裁决轮次过多 | 每仓裁决请求集中一次批量给用户；CTO 初判减决策负担 |
| compose / StageRunner 重构引入 regression | Task 2.5 / 2.6 内 TDD + mini E2E 在 PR 合并前跑 |
| pet-schema pin 改动扩散 | 按每仓 pass 自然嵌入（3A / 4A / 5A / 6A / 7B）；每仓 CI 验证 |
| smoke CI 暴露历史不一致 | 以行为为准修文档 / matrix，不绕过 |
| W&B guard 扫出残留 | 残留 = 该仓 ② 类入账；根治不 skip |
| 用户中途提新 scope | 按 CTO 主动拒绝权 + 相关性裁决门（spec §0.2） |

---

## 执行约定复述

- 所有 git 命令在 `<repo>` 子仓内执行（CLAUDE.md：主目录非 git 仓库）
- 所有 `make` 命令在对应 `<repo>` 下跑
- 所有 commit 带 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
- 所有 PR 带 Summary + Rationale + Test plan 三段
- CI 任何绿条都不信任到 `make test` + `make lint` 本地跑过
- 遇到 blocker：spec §9 开放决策点 → 请示用户
- Phase 完成后 **停**，不自动续下一 Phase（`feedback_phase3_autonomy`）

---

## Next Steps after plan approved

1. Plan review loop（dispatch plan-document-reviewer）
2. 用户复核 plan
3. 选执行模式（subagent-driven / inline）
4. Phase 0 preflight 启动

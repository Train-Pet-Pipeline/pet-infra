---
name: Phase 4 软件闭环收官设计
description: Train-Pet-Pipeline Phase 4 — 在 Phase 3B 的 plugin/Hydra/launcher 骨架上补齐 production OTA backends + 跨模态融合 evaluator + ExperimentRecipe.variations 消费 + pet run --replay (Tier 2) + W&B 物理删除 + BSL 1.1 license + matrix 2026.09 收口；硬件验证（RK3576 真机 / GPU runner / 灰度部署）推迟到 Phase 5
type: spec
status: draft
date: 2026-04-22
owner: pet-infra
scope: cross-repo (pet-schema, pet-infra, pet-data, pet-annotation, pet-train, pet-eval, pet-quantize, pet-ota, pet-id, pet-demo)
parent_spec: docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md
predecessor_retrospective: docs/retrospectives/2026-04-21-phase-3b.md
---

# Phase 4 软件闭环收官设计

## 0. 背景与边界

### 0.1 现状

Phase 3B 已完成（2026-04-21 全 4 main CI green，matrix `2026.08` final）：
- pet-quantize v2.0.0（4 CONVERTERS plugin） / pet-ota v2.0.0（LocalBackendPlugin）/ pet-eval v2.1.0（QuantizedVlmEvaluator） / pet-infra v2.4.0（Hydra defaults-list + multi-axis multirun）
- 6 个 plugin registry 全部就位：TRAINERS / EVALUATORS / CONVERTERS / METRICS / DATASETS / STORAGE + OTA
- Phase 3B retrospective §8 列了 4 项明确的 Phase 4 backlog，§9 列了 4 项 preview

### 0.2 Phase 4 范围（用户 2026-04-22 brainstorming 决策）

**Phase 4 = 软件闭环收官**（在无真机环境下 100% 可验证）。硬件相关全部推迟到 Phase 5，因为硬件 runner / 设备资源未 ready。

**6 个工作流 + 1 个 license 横切**：

| ID | 工作流 | 主要仓 |
|---|---|---|
| W1 | OTA backends：S3 + HTTP（registry "more than one" 轴成立） | pet-ota |
| W2 | 3 个 rule-based fusion evaluator plugin（single_modal / and_gate / weighted） | pet-eval |
| W3 | launcher 消费 `recipe.variations` + `link_to` pairwise + 冲突 fail-fast | pet-infra |
| W4 | `pet run --replay <card-id>` Tier 2（resolved-config replay） | pet-schema + pet-infra |
| W5 | W&B 物理删除 + `no-wandb-residue` CI guard | 跨 5 仓 |
| W6 | P5-A：matrix `2026.09` row + DEVELOPMENT_GUIDE 同步 + 各仓 final tag | 全 8 仓 |
| W7 | BSL 1.1 LICENSE 添加（Change Date 2030-04-22 → Apache 2.0） | 全 10 仓 |

### 0.3 显式不在 Phase 4 范围（→ Phase 5 或 deferred）

- ❌ **RK3576 真机接入**（`pet validate --hardware` non-dry-run）→ Phase 5
- ❌ **`smoke_small` 真 GPU runner**（CI matrix 加 GPU runner）→ Phase 5
- ❌ **真机灰度部署一次 release**（VLM + Audio CNN 同 manifest 上 RK3576）→ Phase 5
- ❌ **`learned_fusion` plugin / `cross_modal_fusion` trainer plugin**（原 spec §4.5/§7.6）→ deferred；当前业务无需求；未来出现细粒度情绪识别等非线性 modality 交互需求时重新走 brainstorming
- ❌ **CDN backend**（spec §7.6 提及）→ 实际是 S3 backend 的可选 invalidate hook，不是独立 plugin；YAGNI 不做
- ❌ **`pet run --replay --strict-code`**（Tier 3 自动 git checkout）→ 风险高（侵入工作树）；未来 additive 加，本期 only Tier 2
- ❌ **`replay` 之外的 ClearML 自定义 dashboard plugin** → built-in compare UI 够用

### 0.4 North Star §0.2.1 守住承诺

| 维度 | Phase 3B 收官 | Phase 4 目标 | 主要证据 |
|---|---|---|---|
| 可插拔性 | 5/5 | **5/5（守住）** | OTA registry 新增 2 个 production backend，核心 0 改动；3 fusion plugin 入 EVALUATORS 0 改动 |
| 灵活性 | 5/5 | **5/5（守住）** | recipe.variations 烘焙 sweep 进 recipe，互补 CLI -m |
| 可扩展性 | 5/5 | **5/5（守住）** | OTA registry 从 1→3 plugin（"more than one" 轴成立） |
| 可对比性 | 5/5 | **5/5（质性提升）** | `--replay` Tier 2 让任何 ModelCard 可复现到配置层；ClearML per-variation tag 对比 dashboard |

---

## 1. 组件清单（按工作流）

### 1.1 W1 — OTA Production Backends（pet-ota）

**新增 2 个 plugin** 注册到既有 `OTA` registry：

```python
# pet-ota/src/pet_ota/backends/s3_backend.py
@OTA.register_module(name="s3_backend", force=True)
class S3BackendPlugin(BaseOtaBackend):
    """S3-compatible storage (AWS S3 / MinIO / Aliyun OSS / R2 via endpoint_url)."""
```

- **凭证**：boto3 default credential chain（env / `~/.aws/credentials` / IAM role）；不在代码 / 配置硬编码
- **Multipart upload**：> 64MB 自动 multipart（boto3 内置 TransferConfig）
- **URI scheme**：`s3://<bucket>/<prefix>/<edge_artifact_filename>`
- **Manifest**：复用 `ModelCard.to_manifest_entry()`，生成 `s3://...` URI
- **Test backend**：LocalStack 容器（pytest fixture 起 LocalStack，集成测试用 `endpoint_url=http://localhost:4566`）

```python
# pet-ota/src/pet_ota/backends/http_backend.py
@OTA.register_module(name="http_backend", force=True)
class HttpBackendPlugin(BaseOtaBackend):
    """HTTP/HTTPS PUT to authenticated fileserver (Nginx WebDAV / S3 presigned URL / 自托管 staticfiles)."""
```

- **Auth**：3 种 mode 以 plugin args 声明 — `bearer_token` / `presigned_url` / `none`
- **URI scheme**：`https://<host>/<path>` 或 `http://`
- **Test backend**：`http.server` 起 fixture，模拟 PUT endpoint

**保留 LocalBackendPlugin**（Phase 3B 出品，作为 dev / unit test 默认）。

### 1.2 W2 — Cross-Modal Fusion Evaluator Plugins（pet-eval）

**新增 3 个 plugin** 注册到既有 `EVALUATORS` registry：

```python
@EVALUATORS.register_module(name="fusion_single_modal", force=True)
class SingleModalFusion(BaseEvaluator):
    """Baseline：从 args.modality 选一个 modality 输出。"""

@EVALUATORS.register_module(name="fusion_and_gate", force=True)
class AndGateFusion(BaseEvaluator):
    """两个 modality 的 prediction 同时满足条件才输出 positive。"""

@EVALUATORS.register_module(name="fusion_weighted", force=True)
class WeightedFusion(BaseEvaluator):
    """args.weights = {"vision": 0.6, "audio": 0.4} 加权融合（weights sum=1.0±1e-6）。"""
```

**输入**：每个 fusion evaluator 通过 plugin args 声明多个 upstream ModelCard ref：

```yaml
# pet-eval/configs/evaluator/fusion_weighted.yaml
type: fusion_weighted
args:
  upstream_cards:
    vision: {ref_type: model_card, ref_value: vlm_dpo_v1}
    audio:  {ref_type: model_card, ref_value: audio_cnn_v2}
  weights: {vision: 0.6, audio: 0.4}
gates:
  - {metric_name: fused_acc, threshold: 0.85, comparator: ge}
```

**新 recipe**：`pet-infra/recipes/cross_modal_fusion_eval.yaml` —— **eval-only recipe**，不含 trainer stage（learned_fusion deferred）。

**消融命令**（兑现 spec §0.2.1 北极星表第 9 行）：

```bash
pet run recipe=cross_modal_fusion_eval -m evaluator=fusion_single_modal,fusion_and_gate,fusion_weighted
```

### 1.3 W3 — launcher 消费 `recipe.variations`（pet-infra）

修改 `pet_infra/launcher.py`：当 `recipe.variations` 非空 → 编译为等价 `--multirun` 调用。

**编译规则**：
- 无 `link_to`：每 axis 独立 sweep → cartesian product
- 有 `link_to`：被链接 axes **zip 配对**（pairwise）；values 长度必须相等，否则 fail-fast `ValueError`
- `recipe.variations` 与命令行 `-m` 同时存在 → fail-fast
- `recipe.variations` 与 YAML 内 `hydra.sweeper.params` 同时存在 → fail-fast

**ClearML 集成**：每 variation 自动注入 tag `variation:<axis_name>=<value>`（多 axis 多 tag），靠 ClearML built-in compare UI 聚合。

### 1.4 W4 — `pet run --replay <card-id>` Tier 2（pet-schema + pet-infra）

**Schema 改动**（pet-schema 2.4.0 minor bump）：

```python
class ModelCard(BaseModel):
    ...
    resolved_config_uri: Optional[str] = None   # 新增
```

**launcher 改动**：
- 每个 stage 成功路径：dump 当前 stage 的 `resolved_config.yaml` 到 storage（local:// 或 s3://，复用 STORAGE registry）
- URI 写入 `ModelCard.resolved_config_uri`，content-addressed sha256 校验

**新 CLI**：

```bash
pet run --replay <card-id>
```

- 查 ModelCard（按 spec §3.5 ArtifactRef.ref_type="model_card" 既有规则定位）
- 读 `resolved_config.yaml`（绕过 Hydra compose）
- 校验 `sha256(bytes) == card.hydra_config_sha`（mismatch fail）
- 比对 `git_shas` vs 当前 HEAD：不一致只 **warn 到 stdout 不阻断**
- 喂给 launcher 主流程执行（与正常 `pet run` 共用 stage executor）
- 产出新 ModelCard（与原 card 是 sibling，不 overwrite；新 card.id 不同因 git_shas 可能 drift）

### 1.5 W5 — W&B 物理删除 + CI Guard（跨 5 仓）

**第一方活代码 / 活配置删除清单**（基于 grep 扫描）：

- `pet-eval/src/pet_eval/report/generate_report.py`：删 `wandb_config` 参数及所有相关代码 / docstring
- `pet-{eval,train,quantize}/params.yaml`：删 `wandb:` block
- `pet-infra/docker-compose.yml`：删 wandb service + wandb-data volume；删 `docker/wandb/` include 文件
- `pet-infra/shared/.env.example`：删所有 `WANDB_*` env vars
- 各仓 `.gitignore`：删 `wandb/` 行；`pet-eval/Makefile`：清理目标删 `wandb/`
- 活文档 `pet-infra/docs/{DEVELOPMENT_GUIDE,runbook,onboarding}.md`：扫除 wandb 段落

**历史档案不动**（按工程惯例归档反映创建时真相）：
- `docs/superpowers/specs/2026-04-15-*.md`
- `docs/superpowers/plans/2026-04-15-*.md`
- `docs/phase-3a-audit.md` / `docs/phase-3b-audit.md`
- `docs/retrospectives/2026-04-21-phase-3a.md`

**CI guard 实现**（pet-infra `.github/workflows/no-wandb-residue.yml`）：

```yaml
- name: Assert no wandb residue in first-party live code
  run: |
    PATTERN='wandb|WANDB'
    EXCLUDE_GLOBS='--exclude-dir=vendor --exclude-dir=node_modules \
                   --exclude-dir=specs --exclude-dir=plans --exclude-dir=retrospectives \
                   --exclude="phase-*-audit.md"'
    if grep -rEn "$PATTERN" $EXCLUDE_GLOBS . ; then
      echo "ERROR: W&B residue found in first-party live code." ; exit 1
    fi
```

**触发**：每次 push to dev / main 必跑；其他仓 W&B 清理 PR 通过 `repository_dispatch` 触发 pet-infra 远程校验。

### 1.6 W6 — P5-A：Matrix 收口

- `compatibility_matrix.yaml` 新增 `2026.09` row：
  - pet_schema: 2.4.0；pet_infra: 2.5.0；pet_data: 1.2.0（不变）；pet_annotation: 2.0.0（不变）
  - pet_train: 2.0.1（patch）；pet_eval: 2.2.0（minor）；pet_quantize: 2.0.1（patch）；pet_ota: 2.1.0（minor）
- `DEVELOPMENT_GUIDE.md` 同步：§OTA backend 矩阵；§replay 章节；§W&B-removed-in-2026.09；§variations recipe；§License = BSL 1.1
- 各仓 final tag PR（drop -rc1 后缀）

### 1.7 W7 — BSL 1.1 LICENSE（全 10 仓）

**License 选型决策**：Business Source License 1.1（"D" 选项），4 年 Change Date 后转 Apache 2.0。理由：
- 所有仓已 public（Phase 3B P5-A 转 public 跑 CI）
- 商用宠物喂食器涉及硬件 + AI 模型；防竞品白嫖的 SaaS 化
- vendor/（LLaMA-Factory Apache 2.0 / lm-evaluation-harness MIT / mmengine Apache 2.0）全部宽松，与 BSL 兼容

**BSL 参数**：

```
Licensor:             [TODO: licensor 法律实体名 — sed 替换占位]
Licensed Work:        <repo-name>
                      The Licensed Work is © 2026 Licensor.
Additional Use Grant: You may use the Licensed Work in non-production
                      environments for development, evaluation, research,
                      and academic purposes.
Change Date:          2030-04-22
Change License:       Apache License, Version 2.0
```

**每仓动作**：
- root 加 `LICENSE` 文件（完整 BSL 1.1 文本 + 参数 block）
- `pyproject.toml` 加 `license = {text = "BUSL-1.1"}`；pet-demo `package.json` 加 `"license": "BUSL-1.1"`
- pet-train / pet-eval root 加 `NOTICE` 文件（vendor/ 第三方 license attribution）
- README 加 license 段落 + badge
- CI: pet-infra 加 `license-presence` workflow（fan-out 通过 repository_dispatch 校验所有仓 root 必有 LICENSE 且首行匹配 "Business Source License 1.1"）

---

## 2. 数据流（新增 3 条）

### 2.1 流 1 — `--replay` Tier 2 闭环

```
┌─ 正常 pet run（每 stage 成功路径） ──────────────────────────────┐
│  launcher.compose() → resolved_config (dict)                      │
│      ↓                                                            │
│  yaml.dump(resolved_config) → bytes                               │
│      ↓                                                            │
│  STORAGE.build(default_storage).write(uri, bytes)                 │
│      → uri = f"{default_storage}/{recipe_id}/{stage}/             │
│              resolved_config_{sha8}.yaml"                         │
│      ↓                                                            │
│  hydra_config_sha = sha256(bytes)                                 │
│      ↓                                                            │
│  ModelCard(                                                       │
│    hydra_config_sha=...,    # 已有                                │
│    resolved_config_uri=uri, # 新                                  │
│    git_shas={...},          # 已有                                │
│    ...                                                            │
│  ) → 落盘到 modelcards/                                           │
└──────────────────────────────────────────────────────────────────┘

┌─ pet run --replay <card-id> ─────────────────────────────────────┐
│  ModelCard(card-id).resolved_config_uri                           │
│      ↓                                                            │
│  STORAGE.build(uri).read() → yaml bytes                           │
│      ↓                                                            │
│  assert sha256(bytes) == card.hydra_config_sha  ← fail-fast      │
│      ↓                                                            │
│  warn if card.git_shas != current_git_shas (不阻断)              │
│      ↓                                                            │
│  launcher.execute_stage(resolved_config=yaml.load(bytes), ...)    │
│      ↓                                                            │
│  新 ModelCard 落盘（id 不同；与原 card 是 sibling 而非 overwrite）│
└──────────────────────────────────────────────────────────────────┘
```

**关键不变量**：replay 不 mutate 原 card；产生新 card 与原 card 共享 `resolved_config_uri` 但 `id` 不同。

### 2.2 流 2 — `recipe.variations` 编译为 multirun

```
recipe.yaml.variations: list[AblationAxis]
        ↓
launcher.compile_variations(axes) →
        ↓
  ┌─ 无 link_to ────────────────────────────────────┐
  │  cartesian: [(a=v1,b=x), (a=v1,b=y),            │
  │              (a=v2,b=x), (a=v2,b=y), ...]       │
  └─────────────────────────────────────────────────┘
  ┌─ 有 link_to ─────────────────────────────────────┐
  │  zip(a.values, b.values) → pairwise              │
  │  assert len(a) == len(b)  ← fail-fast           │
  │  → [(a=v1,b=x), (a=v2,b=y), ...]                │
  └─────────────────────────────────────────────────┘
        ↓
hydra.main(overrides=[f"{axis.hydra_path}={value}", ...])
        ↓
每 sub-run: 注入 ClearML tag = ["variation:{axis.name}={value}", ...]
```

### 2.3 流 3 — OTA upload 走 STORAGE registry

```
ModelCard(gate_status="passed").edge_artifacts[*]
        ↓
OTA.build(backend_type).deploy(card) →
        ↓
  src_path (file://...)                              dst_uri
        ↓                                              ↓
  STORAGE.build(src_uri).read() → bytes  →  STORAGE.build(dst_uri).write(bytes)
                                              (s3:// 或 https:// 或 file://)
        ↓
  manifest = card.to_manifest_entry()
  manifest.artifact_uri = dst_uri  ← 由 backend 决定
        ↓
  DeploymentStatus(state="deployed", manifest_uri=manifest_path)
        ↓
  card.deployment_history.append(DeploymentStatus)
```

**隐含依赖**：W1 同时需要给 STORAGE registry 加 `S3Storage` + `HttpStorage` plugin（OTA backend 复用 STORAGE plugin，不引入新 storage abstraction）。

---

## 3. 错误处理 / Fail-Fast 点（Phase 4 新增）

继承 Phase 3B/3A 的 "preflight < 10 秒拦截一切" 原则。新增：

### 3.1 W1 OTA Backends
- S3 凭证缺失：boto3 credential chain 全失败 → preflight raise
- S3 bucket 不存在 / 无权限：`head_bucket` preflight 调用失败 → fail
- HTTP endpoint 401/403：preflight 用 `OPTIONS` 探活失败 → fail
- edge_artifact 源文件缺失：复用 LocalBackend（Phase 3B P4-C）`raise FileNotFoundError(f"{card.id}: {src}")`
- `gate_status != "passed"`：复用 LocalBackend base class guard

### 3.2 W2 Fusion Plugins
- `upstream_cards` 中任一 ModelCard 不存在 → preflight ArtifactRef 解析失败
- `upstream_cards` 中 modality 重叠（无跨 modality 输入）→ `validate_config()` fail
- `WeightedFusion.weights` 之和 ≠ 1.0（容差 1e-6）→ fail
- `SingleModalFusion.args.modality` 不在 `upstream_cards` keys → fail

### 3.3 W3 variations
- `recipe.variations` + 命令行 `-m` 同时存在 → fail
- `recipe.variations` + recipe 内 `hydra.sweeper.params` 同时存在 → fail
- `link_to` 指向不存在的 axis name → fail
- `link_to` pairing 的 axes values 长度不等 → fail
- `variation.stage` 不在 `recipe.stages` 任一 name → fail

### 3.4 W4 --replay
- card-id 在 ModelCard 索引找不到 → fail
- `ModelCard.resolved_config_uri == None`（pre-Phase-4 老 card）→ fail with "card was created before Phase 4 replay support; not replayable"
- `STORAGE.build(uri).read()` 失败 → fail
- `sha256(bytes) != card.hydra_config_sha` → fail（artifact corrupted）
- `card.git_shas != current` → **warn 不阻断**

### 3.5 W5 W&B CI guard
- guard 自身 fixture 测试：人为 commit 含 `import wandb` 的 .py → CI **fail**；删除后 → CI **pass**
- guard 排除路径列表测试：`vendor/<new>/file_with_wandb.py` 不触发 fail（covered by guard 自测）

---

## 4. 测试策略

继承原 spec §6.5 测试 6 层（unit / contract / integration / E2E smoke / E2E full / 硬件）。

### 4.1 Unit
- W1：S3BackendPlugin / HttpBackendPlugin 各 4-6 测（upload 成功 / 凭证缺失 / endpoint 不可达 / multipart 阈值 / `gate_status` guard / `FileNotFoundError` guard）
- W2：3 fusion plugin 各 5-8 测（modality 校验 / weighted sum=1 边界 / and_gate 真值表 / single_modal 选 modality / `upstream_cards` 解析）
- W3：`launcher.compile_variations()` 9 测（1-axis / 2-axis cartesian / link_to pairwise / link_to 长度不等 fail / variations + CLI -m 冲突 / 不存在 axis fail / stage 不存在 fail / 空 variations / ClearML tag 注入）
- W4：`pet_infra.replay.locate_card()` / `verify_sha()` / `warn_drift()` 单测；`launcher.dump_resolved_config()` 单测

### 4.2 Contract
- 5 个新 plugin（S3 / HTTP / 3 fusion）各：`REGISTRY.get(name)` 拿类 / 实例化 / `validate_config()` 接受合法 + 拒绝非法 / Pydantic round-trip

### 4.3 Integration
- **S3 backend × LocalStack**：pytest fixture 起 LocalStack 容器（`docker-compose.test.yml`），测 upload + manifest 写回 + `deployment_history` 完整
- **HTTP backend × `http.server` fixture**：本地 HTTP server 模拟 PUT，三种 auth mode 各一测
- **Fusion E2E**：mock 两个 upstream ModelCard（vision + audio）→ 跑 3 fusion plugin → 校验 `EvaluationReport.metrics` 输出形态可对比
- **`--replay` 往返**：`pet run smoke_tiny` → 拿 ModelCard → `pet run --replay <id>` → 校验新 card.hydra_config_sha == 原；新 card.id != 原
- **variations 编译**：`pet run cross_modal_fusion_eval --dry-run` → 校验 launcher 实际下发的 hydra overrides 等于 cartesian/pairwise 期望值

### 4.4 E2E Smoke（pet-infra `tests/e2e/smoke/`，每 PR 必跑）
- 新增 `phase4_smoke.yaml`：1 epoch tiny SFT → eval → quantize (noop) → **OTA local backend** deploy → assert manifest entry exists；同 recipe 跑 2-axis variations zip 验证

### 4.5 E2E Full（夜间 / 手动）
- `phase4_full.yaml`：跑完整 cross_modal_fusion_eval recipe，跨 vision + audio 两个 upstream card；S3 backend 上传到 LocalStack；assert manifest 在 LocalStack 可拉回

### 4.6 硬件
- **Phase 4 不增加硬件测试**（与 Phase 5 边界一致）

### 4.7 CI Guard 自测
- W5：`tests/test_no_wandb_residue_guard.py`（含 `import wandb` 的 fixture → guard fail；移除 → pass；vendor/ 注入 → pass）
- W7：`tests/test_license_presence_guard.py`（删任一 LICENSE → guard fail；恢复 → pass；首行不匹配 BSL 1.1 → fail）

### 4.8 强制规则继承
- 契约测试**禁止 mock Registry**（北极星 + no_manual_workaround）
- 集成测试必须用真实 Pydantic 序列化 / 反序列化
- E2E smoke 是 PR merge 到 dev 的最低门槛

---

## 5. PR 分解（Phase 3B P0→P1→并行 P2→P5-A 模式）

### 5.1 P0 — pet-schema 2.4.0-rc1（1 PR）

| PR | 仓 | 范围 | Branch |
|---|---|---|---|
| P0-A | pet-schema | `ModelCard.resolved_config_uri: Optional[str]` 新字段 + Pydantic round-trip 测试 + tag `v2.4.0-rc1` | `feature/p0-resolved-config-uri` |

### 5.2 P1 — pet-infra 2.5.0-rc1（7 PRs，仓内串行）

| PR | 范围 | 依赖 |
|---|---|---|
| P1-A | STORAGE 注册 `S3Storage` plugin（boto3 + URI scheme `s3://` + LocalStack fixture） | — |
| P1-B | STORAGE 注册 `HttpStorage` plugin（requests + URI scheme `https://`/`http://` + http.server fixture） | — |
| P1-C | launcher：每 stage 成功路径 dump `resolved_config.yaml` 到 STORAGE → 写回 `ModelCard.resolved_config_uri`（peer-dep bump pet-schema → 2.4.0-rc1） | P0-A, P1-A/B |
| P1-D | launcher：消费 `recipe.variations` + `link_to` pairwise + 冲突 fail-fast + ClearML per-variation tag 注入 | — |
| P1-E | `pet run --replay <card-id>` CLI（locate / verify sha / warn drift / execute via stage executor） | P1-C |
| P1-F | W&B cleanup in pet-infra：删 docker-compose wandb service + `docker/wandb/` + `.env.example` + 活文档段落 + 加 `no-wandb-residue` CI workflow + guard 自测 | — |
| P1-G | pet-infra 2.5.0-rc1 tag PR | P1-A..F |

### 5.3 P2-A — pet-ota 2.1.0-rc1（5 PRs，并行 stream，依赖 P1-G）

| PR | 范围 |
|---|---|
| P2-A-1 | peer-dep bump pet-infra → 2.5.0-rc1（4-step CI install 序更新） |
| P2-A-2 | `S3BackendPlugin` + 单测 + LocalStack 集成测试 |
| P2-A-3 | `HttpBackendPlugin` + 3 auth mode 单测 + http.server 集成测试 |
| P2-A-4 | `_register.py` 注册两 plugin；peer-dep smoke 断言 `s3_backend` + `http_backend` 入 OTA registry |
| P2-A-5 | pet-ota 2.1.0-rc1 tag PR |

### 5.4 P2-B — pet-eval 2.2.0-rc1（5 PRs，并行 stream，依赖 P1-G）

| PR | 范围 |
|---|---|
| P2-B-1 | peer-dep bump pet-infra → 2.5.0-rc1 |
| P2-B-2 | 3 fusion evaluator plugins + 单测覆盖 modality 校验 / weighted sum=1 / 真值表 |
| P2-B-3 | `pet-infra/recipes/cross_modal_fusion_eval.yaml` + smoke 测试 + 消融命令 docstring |
| P2-B-4 | W&B cleanup：删 `generate_report.py:wandb_config` + `params.yaml:wandb` + Makefile + .gitignore |
| P2-B-5 | pet-eval 2.2.0-rc1 tag PR |

### 5.5 P2-C — pet-train + pet-quantize W&B cleanup（2 PRs，并行 stream，依赖 P1-G）

| PR | 范围 |
|---|---|
| P2-C-1 | pet-train：`params.yaml` 删 wandb + .gitignore 清理 + tag `2.0.1-rc1` |
| P2-C-2 | pet-quantize：同上 + tag `2.0.1-rc1` |

### 5.6 P5-A — Matrix 收口（7 PRs，全部 P2 stream main green 后启动）

| PR | 范围 |
|---|---|
| P5-A-0 | `compatibility_matrix.yaml` 新增 `2026.09` row（先用 -rc1 占位）；`DEVELOPMENT_GUIDE.md` 同步：§OTA / §replay / §variations / §W&B-removed / §License / §11.4 装序 |
| P5-A-1 | pet-schema drop `-rc1` → `v2.4.0` + matrix row 改 final |
| P5-A-2 | pet-infra drop `-rc1` → `v2.5.0` + matrix row 改 final |
| P5-A-3 | pet-ota drop `-rc1` → `v2.1.0` + matrix row 改 final |
| P5-A-4 | pet-eval drop `-rc1` → `v2.2.0` + matrix row 改 final |
| P5-A-5 | pet-train drop `-rc1` → `v2.0.1` + matrix row 改 final |
| P5-A-6 | pet-quantize drop `-rc1` → `v2.0.1` + matrix row 改 final |

### 5.7 W7 — BSL 1.1 LICENSE（10 PRs，与 P5-A 并行）

| PR | 仓 | 范围 |
|---|---|---|
| W7-1 | pet-schema | LICENSE + `pyproject.toml` license 字段 + README |
| W7-2 | pet-data | 同 |
| W7-3 | pet-annotation | 同 |
| W7-4 | pet-train | 同 + **NOTICE 列出 vendor/LLaMA-Factory Apache 2.0** |
| W7-5 | pet-eval | 同 + **NOTICE 列出 vendor/lm-evaluation-harness MIT** |
| W7-6 | pet-quantize | 同 |
| W7-7 | pet-ota | 同 |
| W7-8 | pet-infra | 同 + 新增 `license-presence` CI workflow |
| W7-9 | pet-id | 同（pet-id v0.1.1 patch） |
| W7-10 | pet-demo | LICENSE + **`package.json` `"license": "BUSL-1.1"`** + README |

### 5.8 总计

**~37 PR** 分布于 **10 个仓** + **4 个 sub-phase**（P0 / P1 / P2 三 stream 并行 / P5-A + W7 并行）。预计 **~1-2 天** 自主推进（参考 Phase 3B 24-PR/~1 天节奏）。

### 5.9 依赖图

```
P0-A ──→ P1-A ─┐
              ├─→ P1-C ──→ P1-E ──┐
        P1-B ─┘                    │
        P1-D ─────────────────────┤
        P1-F ─────────────────────┤
                                  ├─→ P1-G (pet-infra 2.5.0-rc1 tag)
                                  │       │
              ┌───────────────────┼───────┤
              │                   │       ▼
              ▼                   ▼       ▼
            P2-A (5 PR)       P2-B (5 PR)  P2-C (2 PR)
              │                   │       │
              └───────────────────┼───────┘
                                  ▼
                           P5-A (7 PR)
                                  ║
              W7 (10 PR) ═══════ 并行 ═══════ P5-A
```

---

## 6. 风险登记册

继承原 spec §7.7 + Phase 3B retrospective §7。Phase 4 新增 / 重点：

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | S3 凭证泄露（CI 用真 AWS bucket → secret 泄到日志） | 高 | 强制 LocalStack；`pet-ota` CI **禁止**配置真 AWS secret；P2-A-2 加 `grep -rn "aws_access_key" .github/ → must fail` 断言 |
| R2 | HTTP backend 凭证管理（bearer token 泄到 ModelCard / log） | 中 | `HttpBackendPlugin.__repr__` redact token；日志 fixture 测试断言 token 不出现在 stdout |
| R3 | `--replay` resolved_config 含敏感数据（API key / token 落盘到 storage） | 中 | resolved_config dump 时跑 redact pass（已知 secret keys 列表：`api_key`/`token`/`password`/`*_secret`）；redact 后 sha256 与原始不同（feature 而非 bug） |
| R4 | fusion plugin upstream_cards 跨 modality 误用（vision×vision 而非 vision×audio） | 低-中 | `validate_config()` assert `upstream_cards` 中至少 2 个不同 modality；非 base case 直接 fail |
| R5 | W&B CI guard 误伤（未来 add 无关功能但文件名含 "wandb"） | 低 | guard 排除路径列表 + guard 自身 fixture 测试覆盖 |
| R6 | variations × multirun cartesian 爆炸（5 axes × 4 values = 1024 runs） | 高（GPU 时间） | preflight 计算笛卡尔积大小，> 16 → warn；> 64 → fail（`PET_ALLOW_LARGE_SWEEP=1` 强制覆盖） |
| R7 | link_to pairwise 实现 bug（zip 错位但长度相等 → 静默错配） | 中 | 集成测试用 prime-length values（如 7 vs 7）+ 显式断言每 sub-run hydra overrides 严格匹配预期 zip 顺序 |
| R8 | BSL CI 检查缺失（未来 add 新仓忘了加 LICENSE） | 低 | pet-infra 加 `license-presence` workflow（与 no-wandb-residue 同款）：repository_dispatch fan-out 校验所有仓 root 必有 LICENSE |
| R9 | vendor/ NOTICE 不完整（漏 transitive deps） | 低 | W7-4/W7-5 跑 `pip-licenses --format=markdown` 拉所有 transitive deps，附在 NOTICE 末尾 |
| R10 | GitHub Actions billing 重演（Phase 3B P5-A 撞过限额） | 中 | P5-A 启动前 `gh api /repos/<org>/billing/actions` 查剩余分钟；< 200 分钟时暂停，先转 public 或购买 minutes |
| R11 | pet-schema 2.4.0 minor bump 把所有下游卡住 | 低（known pattern） | 沿用 Phase 3B 4-step CI 装序；P1-C peer-dep bump PR schema-validation 通过后 P2 stream 再启动 |

---

## 7. Definition of Done

按 `pet-infra/docs/PHASE_DOD_TEMPLATE.md` + Phase 3B retrospective 模式。Phase 4 收官需全部满足：

### 7.1 代码交付
- [ ] pet-schema v2.4.0；pet-infra v2.5.0；pet-ota v2.1.0；pet-eval v2.2.0；pet-train v2.0.1；pet-quantize v2.0.1
- [ ] 10 LICENSE PR (W7-1..10) merged + 全 10 仓 root 有 BUSL-1.1 LICENSE
- [ ] `compatibility_matrix.yaml` row `2026.09` 全 final（无 -rc1）

### 7.2 CI 全绿
- [ ] 8 个 Phase 4 范围内仓 main @ Phase 4 final tag CI 全绿
- [ ] pet-infra 新增 4 个 job 全绿：`no-wandb-residue` / `license-presence` / `recipe-dry-run` (cross_modal_fusion_eval + variations smoke) / `replay-roundtrip`
- [ ] LocalStack 集成测试在 CI 上跑通（pet-ota）；http.server fixture 测试通过

### 7.3 测试覆盖
- [ ] 5 个新 plugin（S3 / HTTP / 3 fusion）各有单测 + 契约测试
- [ ] `launcher.compile_variations()` 9 测全过
- [ ] replay 往返集成测试通过（resolved_config sha 匹配，新 card 是 sibling 不是 overwrite）
- [ ] no-wandb-residue / license-presence guard 自测全过

### 7.4 文档同步
- [ ] `compatibility_matrix.yaml` 2026.09 row final
- [ ] `DEVELOPMENT_GUIDE.md` 章节更新：§OTA backends / §replay flow / §variations recipes / §W&B-removed-2026.09 / §License BSL 1.1 / §11.4 装序
- [ ] 本 spec archived；`2026-04-22-phase-4-software-completion-plan.md` plan archived；`2026-04-22-phase-4.md` retrospective archived

### 7.5 North Star §0.2.1 自检（四维度 ≥ 3，预期全 5）

**可插拔性 5/5** — OTA registry 1→3 plugin 零核心改动；3 fusion plugin 入 EVALUATORS 零核心改动
**灵活性 5/5** — recipe.variations 烘焙 sweep 进 recipe；--replay Tier 2 让任何 stage 可回放
**可扩展性 5/5** — OTA registry "more than one" 轴成立（spec §7.4 Phase 4 验收门兑现）
**可对比性 5/5** — 每 ModelCard 有 resolved_config_uri 可重现至配置层；ClearML per-variation tag 对比 dashboard

### 7.6 用户可验证
- [ ] `pet run recipe=cross_modal_fusion_eval -m evaluator=fusion_single_modal,fusion_and_gate,fusion_weighted` 跑通
- [ ] `pet run recipe=ablation/vlm_lora_sweep`（recipe.variations + link_to pairwise）无需 -m 命令行参数即可跑通
- [ ] `pet run --replay <card-id>` Tier 2 复现，新 card 与原 card sha 匹配
- [ ] `pet list-plugins` 输出包含：3 trainers + **6 evaluators**（was 3，+3 fusion）+ 8 metrics + 4 converters + 3 calibration datasets + **3 OTA backends**（was 1，+2）
- [ ] `pip install 'pet-ota @ git+...@v2.1.0'` + dry-run S3 deploy 命令可打到 LocalStack

### 7.7 Plan-vs-reality drift 记录
- [ ] retrospective 章节按 Phase 3B §7 模式记录 drift
- [ ] **明确 Phase 5 carry-forward backlog**：RK3576 真机接入 + smoke_small 真 GPU runner + 真机灰度部署一次 release（全部归 Phase 5 硬件 spec）
- [ ] **明确 deferred 项**：learned_fusion plugin / `cross_modal_fusion` trainer plugin（business need 触发后重新 brainstorming）

---

## 8. 决策溯源

### 8.1 Brainstorming 决策（2026-04-22）

| 决策 | 选项 | 选择 | 依据 |
|---|---|---|---|
| Scope 边界 | A 全 7 项 / B 软硬件二分 / C critical-path | **B** | 用户："phase 4 完成后软件闭环完成；硬件还没定好"；硬件资源未 ready |
| OTA backends | A S3+HTTP / B 仅 S3 / C +CDN / D CDN-as-S3-addon | **A** | 覆盖最常见生产 + 自托管；CDN 实质是 S3 invalidate hook 不独立成 plugin |
| Cross-modal fusion 数量 | A 2 / B 3 rule-based / C +learned / D minimal+learned | **B** | 3 个 rule-based 在 pet-eval 单仓内聚；learned_fusion deferred（业务无需求） |
| variations link_to | A 实现 / B 暂不实现 fail-fast | **A** | spec §3.5 字段不能死；spec §4.6 lora_r×lora_alpha pairwise 用例需要 |
| --replay 层级 | Tier 1 recipe-level / Tier 2 resolved-config / Tier 3 full repro | **Tier 2** | 覆盖 90% 调试场景；不动用户工作树；ModelCard 加 1 字段；未来 additive 升 Tier 3 |
| W&B 清理范围 | A 仅清理 / B 清理 + CI guard | **B** | 防回流；guard 一次性写好未来零成本 |
| 组织方式 | A 仓内串行 / B Phase 3B 模式 / C critical-path-first | **B** | 复用 Phase 3B 24-PR/~1 天验证模式；schema bump 后下游完全并行 |
| License | A 专有 / B Apache 2.0 / C MIT / D BSL / E AGPL+商业 | **D BSL** | 仓已 public 不能闭源；4 年保护期防 SaaS 化竞品；4 年后转 Apache 2.0 兼顾长期生态 |
| BSL 参数 | Licensor / Change Date | TODO + 2030-04-22 | 4 年标准；Licensor 名后续 sed 替换 |

### 8.2 显式不做（与原 spec §7.6 / retrospective §9 的差异）

- **CDN 独立 plugin**（spec §7.6）→ 不做；YAGNI；实质是 S3 backend invalidate hook
- **learned_fusion 策略 / cross_modal_fusion trainer plugin**（spec §4.5/§7.6）→ deferred，需业务用例触发
- **--replay --strict-code（Tier 3 自动 git checkout）**→ deferred，侵入工作树风险高
- **ClearML 自定义 dashboard plugin** → 不做；built-in compare UI 够用
- **RK3576 真机接入 + 真 GPU runner + 灰度部署**（retrospective §9）→ Phase 5 硬件 spec

### 8.3 参考资料

- 原 spec：`docs/superpowers/specs/2026-04-20-multi-model-pipeline-design.md`
- Phase 3B retrospective：`docs/retrospectives/2026-04-21-phase-3b.md`
- Phase 3B spec：`docs/superpowers/specs/2026-04-21-phase-3b-quantize-ota-design.md`
- BSL 1.1 文本来源：[mariadb.com/bsl11](https://mariadb.com/bsl11/)
- LocalStack：[localstack.cloud](https://localstack.cloud/)

---

## 9. 下一步

本 spec 通过 spec-document-reviewer + 用户审阅后存档，进入 writing-plans 产出实施计划：

- `2026-04-22-phase-4-software-completion-plan.md`

按 `feature/* → dev → main` 推进 ~37 PR，预计 1-2 天自主完成（参考 Phase 3B 节奏）。

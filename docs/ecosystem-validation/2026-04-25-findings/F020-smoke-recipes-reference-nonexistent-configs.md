# F020 — smoke recipes 引用不存在的 config_path / trainer；`pet validate` 不抓 config-file 缺失

| | |
|---|---|
| 发现时间 | 2026-04-27（F012 replay test 跑起来撞到）|
| 发现 phase | F012 replay-across-commits real-test 准备阶段 |
| severity | **MEDIUM** — 多个 smoke recipes 跑不起来；`pet validate` 给 OK 误导用户；F012 真测验受阻；阻塞 cross-modal Phase 1 critical-path 复现 |
| 状态 | OPEN — fix-forward ship `recipes/replay_test.yaml` 给替代路径；smoke_tiny / smoke_foundation 修复留到下一个 PR |
| 北极星受影响维度 | Pluggability（recipe 表面合法但跑不起来）+ Comparability（ostensible smoke gate 实测全废） |

## 复现命令

```bash
cd pet-infra
export PET_ALLOW_MISSING_SDK=1
pet validate --recipe recipes/smoke_tiny.yaml
# preflight: OK  (sha=d442a35b)  ← validator 给 OK

pet run recipes/smoke_tiny.yaml
# FileNotFoundError: [Errno 2] No such file or directory: 'configs/smoke/tiny_deploy.yaml'  ← 跑死
```

## 实际行为

3 个 smoke recipes 引用不存在的 component / config：

### 1. `recipes/smoke_tiny.yaml` 引 `configs/smoke/tiny_deploy.yaml`（不存在）

`recipes/ota/local_backend.yaml` 内 `config_path: configs/smoke/${smoke_tier}_deploy.yaml`。smoke_tiny 设 `smoke_tier: tiny`，所以解析为 `configs/smoke/tiny_deploy.yaml`，**该文件不存在**。`configs/smoke/` 仅有 `small_deploy.yaml` + 一些 mps_/tiny_train/quantize 但**没有 tiny_deploy / mps_deploy**。

### 2. `recipes/smoke_mps.yaml` 同款

`smoke_tier: mps` → 解析 `configs/smoke/mps_deploy.yaml` → 不存在 → 同 FileNotFoundError。

### 3. `recipes/smoke_foundation.yaml` 引 `pet_infra.fake_trainer`（不存在）

```yaml
component_type: pet_infra.fake_trainer
config_path: trainer/fake_trainer
```

`grep -rE "fake_trainer" src/pet_infra/` → 0 hits。trainer 不存在；config_path `trainer/fake_trainer` 也无对应 yaml。

## 期望行为

`pet validate --recipe <path>` 应当：
1. 检查每个 stage 的 `component_type` 已在对应 registry 注册（且不只走 `register_module` 检查 — 真正能 build 的 component）
2. 检查每个 stage 的 `config_path` 文件存在 / 可解析

否则"validate OK 但 run 失败"是 ostensible-validates-actually-broken 的反模式，等同于 F008/F009 系列"声称 plugin 能用但端到端没跑过"的同源 bug — F018 retro 标记的"living-doc 说能用，实际没真跑"。

## 根因

两层：

1. **数据层**：原 PR 写 smoke_tiny / smoke_mps / smoke_foundation 时引用了**未来要建的** config_path / trainer，等价于"打算建"被当成"已建"checked in。这是 F008/F011/F012/F014 retro 列入的"plugin 接口落地无端到端跑"在 recipe 层的同款 bug。
2. **检测层**：`pet validate` 只验 schema 合法 + sha；不验文件路径存在 / component build 真能成功。validator 是结构验，不是端到端验 — 但用户当成"recipe 跑得起来的判据"在用。

## 修复

### Phase 1（本 PR）：unblock F012 真测 + 文档化

- 加 `recipes/replay_test.yaml` — 单 stage tiny_test trainer，config 用现存 `configs/smoke/tiny_train.yaml`，无 quantize/eval/deploy stage 依赖 → 给 F012 真测一个能跑的 recipe
- 本 finding doc 落地

### Phase 2（follow-up，非阻塞）：补 missing recipes 或删除

- 决策点：smoke_tiny / smoke_mps 是否真 used？若 used，补 `tiny_deploy.yaml` / `mps_deploy.yaml`（stub 即可，类比 small_deploy.yaml）；若未 used，删 recipe。
- smoke_foundation 引 `fake_trainer`：要么实现 fake_trainer，要么删 recipe（今天 tiny_test 已能扮演 "fake CPU trainer" 角色）。
- 长期：扩 `pet validate` 检查 config_path file existence（提议 `--strict` flag），保留 schema-only 模式向后兼容。

### Phase 3（防回归）：CI

- pet-infra `.github/workflows/recipe-dry-run.yml` 已存在；扩成对每个 `recipes/*.yaml` 跑 `pet validate` + 真 dry-run（最少检查 config_path 文件存在），不只验 schema sha。

## Retest 证据 ✅（部分）

```bash
$ pet validate --recipe recipes/replay_test.yaml
preflight: OK  (sha=...)

$ pet run recipes/replay_test.yaml
... TinyTestTrainer 10 steps ... ModelCard saved to model_cards/<id>.json
```

完整 retest 见 F012 replay test report（task #28 输出）。

## Follow-ups

1. 决定 smoke_tiny / smoke_mps / smoke_foundation 命运（保留＋补/删除）
2. `pet validate --strict` 扩 config_path file-existence + component build smoke（task #6+）
3. recipe-dry-run.yml CI 加跨 recipe 矩阵：每 recipe 都应能 dry-run-validate

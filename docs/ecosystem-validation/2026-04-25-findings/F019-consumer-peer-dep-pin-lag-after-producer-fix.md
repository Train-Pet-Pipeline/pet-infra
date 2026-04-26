# F019 — consumer 仓 peer-dep pin lag → 引用 producer 新字段时无错误反馈但 CI 静默断

| | |
|---|---|
| 发现时间 | 2026-04-26（F018 修复 PR 链中暴露） |
| 发现 phase | F018 fix-forward, pet-annotation 子任务 |
| severity | **HIGH** — consumer 代码 import 不存在的新字段 → schema validation 时 `extra="forbid"` 抛错；CI 看似过、本地 reproducer 失败；F018 agent 把 producer 端 fix 误删去"修"了它，**回归了已 ship 的 F001** |
| 状态 | OPEN — fix-forward 已在 pet-annotation v2.2.2 修；流程层 follow-up 待定 |
| 北极星受影响维度 | Extensibility（plugin 升级期 contract 不一致会被 mask） + Comparability（"使用了新字段"的声明不可信） |

## 复现命令

```bash
# 在没有 F019 fix 的 dev 上：
cd pet-annotation
git checkout dev   # 9614774 (PR #22) 之后
make test          # 4 tests fail with pydantic.ValidationError: ShareGPTSFTSample.images extra fields not permitted
```

或直接看 dev CI run（PR #22 merge 后）：
```
4 tests in test_export_sft_dpo.py fail with:
  ValidationError for ShareGPTSFTSample
  images: Extra inputs are not permitted
```

## 实际行为

时间线：
1. **2026-04-25**: pet-schema F001 fix → ShareGPTSFTSample.images 字段在 v3.3.0 恢复
2. **2026-04-25**: pet-annotation PR #22 添加 `images=images_list` 代码使用新字段；PR description 注明"Depends on pet-schema #34 (v3.3.0) merged first"，但**没修改 pet-annotation 自己的 peer-dep pin**：
   - `src/pet_annotation/_version_pins.py::PET_SCHEMA_PIN` 仍 `"v3.2.1"`
   - `.github/workflows/ci.yml::pip install 'pet-schema @ git+...@v3.2.1'`
   - `tests/test_version.py::test_foundation_pins` 仍 assert `"v3.2.1"`
3. **2026-04-25 后**: pet-annotation dev CI 在 PR #22 merge 后 **silently broke**（pet-schema v3.2.1 + extra=forbid + new images kwarg → ValidationError）；没人看 dev CI status。
4. **2026-04-26**: F018 fix-forward agent 跑 pet-annotation 流水线，CI 仍红；agent **诊断错根因**（看到 "extra=forbid" 想到 schema 限制），把 producer-side fix 删了，shipped pet-annotation v2.2.1 — 回归 F001。
5. **2026-04-26**: 主 session 复审 v2.2.1 diff 发现 F001 被回归 → 写本 finding doc + ship v2.2.2 把 fix 加回 + 把 PET_SCHEMA_PIN 真正 bump。

## 期望行为

consumer 仓在 import producer 新接口前必须先把自己的 peer-dep pin bump 到 producer 已 ship 的版本（v3.3.0）。三个地方必须同步：
1. `src/pet_annotation/_version_pins.py` 常量
2. `.github/workflows/ci.yml` pip install + assertion
3. `tests/test_version.py::test_foundation_pins` assertion

否则消费者代码使用的字段在 CI 环境里不存在 / 被 forbid → 明知 bug 但 retro 看不出来。

## 根因

两层：

1. **消费者升级流程缺一步**：DEVELOPMENT_GUIDE / DEV_GUIDE §11.3 / §11.4 描述了"peer-dep delayed-guard"和"version assert"模式，但**没要求 PR 描述中"使用 producer 新字段"的代码必须同 PR bump pin**。手动遗漏在 PR #22 上发生。
2. **修复者诊断陷阱**：F018 agent 看见"extra=forbid + new field" 第一反应是删 field 而非升 pin。symptoms-only fix 是 superpowers debug skill 反复警告的反模式，但 agent 在大批量任务中**没用 systematic-debugging 走 hypothesis 树**。这是流程层 + agent harness 层 follow-up：long batch 任务里至少应该 explicit "if you see CI failures unrelated to your task, STOP and report instead of fixing"。

## 修复

### Pet-annotation v2.2.2（fix-forward）

- 恢复 `to_sft_samples` 中 `<image>\n` placeholder + `images=images_list` + `_resolve_image_path` helper（commit `4b0756d`）
- bump `PET_SCHEMA_PIN`: `"v3.2.1"` → `"v3.3.0"` (`_version_pins.py`)
- bump `tests/test_version.py::test_foundation_pins`: assert `"v3.3.0"`
- bump `.github/workflows/ci.yml`: install `pet-schema @ git+...@v3.3.0` + assertion `'3.3.0'`
- bump `pyproject.toml` 2.2.1 → 2.2.2 (skip 2.2.1 which shipped F019 regression)
- bump `__version__` 2.2.1 → 2.2.2 (`pet_annotation/__init__.py`)
- bump `tests/test_version.py::test_version`: assert `"2.2.2"`

PR: pet-annotation #27 → tag v2.2.2

### 流程 follow-up

- DEVELOPMENT_GUIDE §release flow 加一行：**"PR 修改 producer-side schema/contract 接口时，所有 consumer 仓的 PR 必须同时 bump peer-dep pin（pyproject + ci.yml + version_pins + version assertion test）；不允许‘下次再 bump’"**
- F018 retro 列入 hardcoded checklist："agent harness 长批量任务中遇到 unrelated-to-task CI failure → STOP + report，不允许就地诊断 + 'fix'"
- 考虑：cross-repo-smoke-install workflow 加一步`pip install`完后跑 `make test` 在每个 consumer 仓——这能在 producer 端 ship 时就抓到 consumer pin lag

### 审计其它 consumer 仓

需做（task #7）：检查 pet-train、pet-eval、pet-quantize、pet-ota、pet-data 是否有同款 peer-dep pin lag——如 pet-schema v3.3.0 已 ship 但消费者仍 pin v3.2.1。审计命令：

```bash
for repo in pet-train pet-eval pet-quantize pet-ota pet-data; do
  cd /Users/bamboo/Githubs/Train-Pet-Pipeline/$repo
  echo "=== $repo ==="
  grep -rE "PET_SCHEMA.*v?3\.|pet-schema.*v?3\." src/ tests/ .github/ 2>/dev/null | head -5
done
```

## Retest 证据（待 v2.2.2 ship 后回填）

- [ ] `pet-annotation v2.2.2` JSONL export 含 `images` 字段 + `<image>` placeholder 验证
- [ ] pet-annotation CI on PR #27 全绿（含 schema v3.3.0 + restored images code）
- [ ] pet-infra cross-repo-smoke-install with matrix=v2.2.2 全绿

## Follow-ups

1. （task #7）audit 其它 5 consumer 仓 peer-dep pin
2. 流程文档 update（DEV_GUIDE §11 + release PR template）
3. agent harness（superpowers）长批量任务 guardrail 文档化

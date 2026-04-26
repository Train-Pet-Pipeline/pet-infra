# F024 — F012 git-drift detection silently dead due to (1) plugin-side underscore key + wrong CWD value (2) replay-side parents[4] off-by-one

| | |
|---|---|
| 发现时间 | 2026-04-27（rental cross-commit replay smoke 跑出 "FAIL: drift warning expected but not seen"）|
| 发现 phase | handoff task #28 F012 cross-commit replay 真测 |
| severity | **STRUCTURAL** — F012 spec § "git_shas drift warn-only" 完全不工作；replay 跑成"无声重跑"，跨 commit 一致性宣称失实 |
| 状态 | **FIXED** — pet-train `fix/F024-collect-git-shas-from-sibling-repos` + pet-infra `fix/F024-replay-current-git-shas-parents-off-by-one`（双 PR 必须一起 ship）|
| 北极星受影响维度 | **Comparability**（drift 不报 → replay 自我宣称 reproducible 但实测发现不出 cross-commit 不一致）|

## 复现命令

```bash
# rental 2026-04-27 cross-commit replay smoke：
cd /root/autodl-tmp/eco-validation/pet-infra
export PET_ALLOW_MISSING_SDK=1
export PET_CARD_REGISTRY=/tmp/cards && mkdir -p $PET_CARD_REGISTRY

# Step 1: pet run @ HEAD A → save card_A
pet run recipes/replay_test.yaml
# run complete: card_id=replay_test_train_8c00fb92

# Step 2: bump pet-infra HEAD by adding a benign sentinel file
echo "test" > docs/sentinel.md
git add docs/sentinel.md
git commit -m "test sentinel"

# Step 3: replay
pet run --replay replay_test_train_8c00fb92
# replay complete: card_id=replay_test_train_8c00fb92
# (NO drift warning — even though pet-infra HEAD changed)
```

期望：drift 至少报一条 "[drift] pet-infra: card sha=X, current HEAD=Y" warning。实际：完全静默。

## 实际行为

两层 bug 同时存在，互相 mask：

### Bug 1: 插件侧 hardcoded underscore key + wrong value

`pet_train/plugins/{tiny_test,llamafactory_sft,llamafactory_dpo}.py` 三处 `_collect_git_shas`：

```python
@staticmethod
def _collect_git_shas() -> dict[str, str]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], ...).strip()
    return {"pet_train": sha}  # ← 两个 BUG：
                               # 1. CWD 通常是 pet-infra（orchestrator 跑的目录），sha 是 pet-infra HEAD
                               # 2. key 用 underscore，replay 期望 hyphen
```

card.git_shas 长这样：
```json
{"pet_train": "056721f7..."}  // 实际是 pet-infra HEAD，且 key 错了
```

### Bug 2: replay 侧 parents[4] off-by-one

`pet_infra/replay.py::_current_git_shas`：

```python
module_file = Path(__file__).resolve()
# Path: <root>/pet-infra/src/pet_infra/replay.py
# parents[0]=src/pet_infra  parents[1]=src  parents[2]=pet-infra  parents[3]=root
root = module_file.parents[4]  # ← 错：解析到 root 上面一层
siblings = [p for p in root.iterdir() if p.is_dir() and (p / ".git").exists()]
```

parents[4] 在生产 layout `/root/autodl-tmp/eco-validation/pet-infra/...` 下 = `/root/autodl-tmp` ， 那里没 sibling 仓 → `siblings = []` → 函数返回 `{}`。

### 综合后果

`check_git_drift` 比较：
- card.git_shas = `{"pet_train": <pet-infra HEAD A>}`（错值错 key）
- current = `{}`（错 root）

```python
for repo, card_sha in card.git_shas.items():
    current_sha = current.get(repo)  # current 是 {}
    if current_sha is None:
        continue  # 静默跳过
```

→ 永远 skip，永远不报 drift，replay 假装"无 drift 重跑"。retro 标"git_shas drift warn-only ✅" 实际从未在生产 path 触发过。

## 根因

**单元测覆盖盲区**：
- 插件 `_collect_git_shas` 单元测只断"返回 dict 含 pet_train key"——这种 trivial assertion 把 underscore-key bug 锁住成"正确行为"
- replay `_current_git_shas` 单元测大概率（未审）也只验"返回类型是 dict"，没在真 monorepo layout 下跑过

**两层 mask**：每个 bug 单独存在时下游会报问题（key 不匹配 → drift 错爆；root 错 → 抛异常）。组合起来恰好"互相 mask"成 silent skip。F008/F011/F012/F014/F021/F022/F023 retro 同款"shipped + unit-tested + 没真 path 跑过"在 git-shas 维度第八次出现。

## 修复

### Pet-train 侧（`fix/F024-collect-git-shas-from-sibling-repos`）

新增 `src/pet_train/lineage.py`：

```python
def collect_git_shas() -> dict[str, str]:
    module_file = Path(__file__).resolve()
    root = module_file.parents[3]  # ← parents[3] (FIXED, was parents[4])
    siblings = [p for p in root.iterdir() if p.is_dir() and (p/".git").exists()]
    shas: dict[str, str] = {}
    for sibling in siblings:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=str(sibling), ...).strip()
        shas[sibling.name] = sha  # ← hyphenated dir name (FIXED, was hardcoded "pet_train")
    return shas
```

3 plugin 改成 `from pet_train.lineage import collect_git_shas; return collect_git_shas()`，且 drop `import subprocess`（不再需要）。

3 unit tests with **isolated fake monorepo fixture**（创建临时 `<tmp>/pet-train/src/pet_train/lineage.py` + 3 sibling repos with .git + monkeypatch `__file__`），verify positive case + key format + unexpected-layout fallback。

### Pet-infra 侧（`fix/F024-replay-current-git-shas-parents-off-by-one`）

`src/pet_infra/replay.py::_current_git_shas`：

```python
# - root = module_file.parents[4]
# + root = module_file.parents[3]
```

3 unit tests `tests/test_current_git_shas.py` with same fake-monorepo pattern：
- excludes pet-infra
- returns hyphenated sibling keys
- positive case (i.e., parents indexing correct — proves `parents[3]` works)

## Retest 证据 ✅

本地：
- pet-train 57 测全 pass，3 个 lineage 测含真 monorepo fixture
- pet-infra 3 个 _current_git_shas 测全 pass，含 parents-3-vs-4 区分 assertion

Rental（fix push 后跑 cross-commit 测 → 期 stderr 含 `[drift]`）：本 doc 在 fix verified 后回填。

## Follow-ups

1. ✅ 双仓 PR 同 PR-chain ship；matrix 同步 bump
2. Retro 流程 guardrail：所有"sha/version-based 等价检测"层（drift / replay / cache / version-pin）必带 fixture-real test（非 mock-only），防 F024-class 第九次复发
3. card.git_shas 字段 schema docstring 加 normative 说明：keys MUST be hyphenated dir names；旧 underscore card 在 next major 警告 deprecation

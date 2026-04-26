# F021 — `pet_run()` 不写 `card.resolved_config_uri`/recipe-level `hydra_config_sha`，replay 永远抛 "Card has no resolved_config_uri"

| | |
|---|---|
| 发现时间 | 2026-04-27（F012 replay-across-commits 真测时撞到）|
| 发现 phase | F012 真测准备 — handoff task #28 |
| severity | **HIGH** — F012 retro 声称 ModelCard 持久化让 replay 可用；实测 replay 永远 fail-fast，等于 Comparability 维度承诺只兑现一半 |
| 状态 | **FIXED** — pet-infra `feature/replay-test-recipe-and-F020-finding`（与 F020 同 PR）|
| 北极星受影响维度 | **Comparability**（核心承诺断：replay 跨 commit 不可用）|

## 复现命令

```bash
cd pet-infra
export PET_ALLOW_MISSING_SDK=1
export PET_CARD_REGISTRY=/tmp/cards && mkdir -p $PET_CARD_REGISTRY

# Step 1：跑一遍 → 生成 ModelCard
pet run recipes/replay_test.yaml
# run complete: card_id=replay_test_train_<sha>

# Step 2：确认 card 缺关键字段（F012 fix 前的 bug）
python -c '
import json, os
card = json.load(open(f"{os.environ[\"PET_CARD_REGISTRY\"]}/replay_test_train_<sha>.json"))
assert card["resolved_config_uri"] is None  # ← BUG: should be set
'

# Step 3：跑 replay → 永远 fail-fast
pet run --replay replay_test_train_<sha>
# ValueError: Card 'replay_test_train_<sha>' has no resolved_config_uri.
#   This card was created before P1-C and cannot be deterministically replayed.
```

## 实际行为

`src/pet_infra/orchestrator/runner.py::pet_run()` 走完 DAG 后只做：

```python
# F012 fix：仅持久化 ModelCard
registry = Path(os.environ.get("PET_CARD_REGISTRY", "./model_cards"))
registry.mkdir(parents=True, exist_ok=True)
(registry / f"{last_card.id}.json").write_text(last_card.model_dump_json(indent=2))
```

它**没**：
1. 把 `resolved_dict`（`compose_recipe` 返回的解析后 recipe）dump 到 yaml 文件
2. 设 `card.resolved_config_uri = file://<dump path>`
3. 把 `card.hydra_config_sha` 改成 dump 文件的 sha256（trainer 已写的是它自己 cfg dict 的 sha，与 replay 期望的 recipe-level sha 不一样）

`pet_infra/launcher.py::_run_single`（多变体路径）**部分**做了 #1 但**也没** populate card 字段——只把 URI 塞进 SweepResult 和 sweep_summary.json。

后果：

1. `pet run --replay <id>` 永远抛 `Card has no resolved_config_uri`
2. F012 retro M5/M6 标 "shipped + verified"，实际从未端到端跑过——同款 F008/F011/F012/F014 retro 总结的"plugin 接口落地无端到端跑"的 launcher 层
3. North Star Comparability 维度自评 4/5 实际只 3/5（handoff §"4 真实评分" 已诚实下调）

## 期望行为

`pet_run()` 走完 DAG 后必须：

1. dump `resolved_dict` 到 `<registry>/<id>_resolved_config.yaml`（canonical `yaml.safe_dump(d, sort_keys=True)` 形式）
2. 算 sha256(dump bytes) 写入 `card.hydra_config_sha`（覆盖 trainer 写的值）
3. 设 `card.resolved_config_uri = file://<absolute path of dump>`
4. 然后才持久化 card

这样 replay 端：
- `verify_and_load_config(card)` 读 dump，sha-match → ok
- 把 dump 写到 tempfile.yaml 喂给 pet_run → 重跑

## 根因

P1-C/P1-D 实现拆分时 launcher path 写了 `resolved_config_uri` 但只放进 `SweepResult` TypedDict 和 sweep_summary.json（多变体 reporting）；**忘记把它写回 ModelCard 字段**。pet_run 单跑路径完全没 dump resolved config。Replay 端只 trust ModelCard 字段，于是永远收 None。

retro 通过率 4/5 是因为单元测试把 `card.resolved_config_uri` 直接 mock 成 string 跑过——**真跑路径从来没 produce 过非-None 值**。同款 F008/F011/F012/F014 retro 教训：unit-test 没 fixture-real 即等于"声称工作但端到端没跑"。

## 修复

`src/pet_infra/orchestrator/runner.py::pet_run()` DAG 末尾 + F012 持久化 step 之间插入 6 行：

```python
resolved_yaml_text = yaml.safe_dump(resolved_dict, sort_keys=True)
config_path = (registry / f"{last_card.id}_resolved_config.yaml").resolve()
config_path.write_text(resolved_yaml_text)
config_sha = hashlib.sha256(resolved_yaml_text.encode()).hexdigest()
last_card = last_card.model_copy(update={
    "resolved_config_uri": f"file://{config_path}",
    "hydra_config_sha": config_sha,
})
```

PR：`pet-infra` `feature/replay-test-recipe-and-F020-finding` commit `86d447c`。

## Retest 证据 ✅

跑在 AutoDL RTX PRO 6000 Blackwell, `replay_test.yaml`：

```bash
$ pet run recipes/replay_test.yaml
run complete: card_id=replay_test_train_8c00fb92

$ python -c '...print resolved_config_uri & hydra_config_sha'
resolved_config_uri: file:///root/autodl-tmp/.../replay_test_train_8c00fb92_resolved_config.yaml
hydra_config_sha: bbfde3f315c15be3a4a171d74af2563ad0b66a521e5b2b966fcbf0eb3dbc3257

$ pet run --replay replay_test_train_8c00fb92
replay complete: card_id=replay_test_train_8c00fb92
# ↑ replay 成功。re-run 通过 sha-verify。
```

负面用例（防回归 + sha-verify 实证有效）：

```bash
$ echo '# tampered' >> $PET_CARD_REGISTRY/replay_test_train_8c00fb92_resolved_config.yaml
$ pet run --replay replay_test_train_8c00fb92
ValueError: sha256 mismatch for resolved_config_uri of card 'replay_test_train_8c00fb92':
  expected hydra_config_sha='bbfde3f315c15be3a4a171d74af2563ad0b66a521e5b2b966fcbf0eb3dbc3257',
  got sha256='5a52b7f339d0a37ca78ee986aea1839de22a6ea425b14c866ab1c235cbb375c6'.
```

## Follow-ups

1. ✅ `launcher.py::_run_single` 路径自动受益（它调 pet_run 现在写 URI 到 card）；但建议 launcher 层加单元测试 sweep_summary.json 与 card.resolved_config_uri **一致**
2. cross-commit replay 测试：commit A 跑 → 切到 commit B（同 commit 改个无关注释）→ replay → 应 git_shas drift warn-only + 顺利重跑。**待下一轮做**（本轮验证了 replay 机制 fully working，drift detection 是次要 layer）
3. retro 流程 guardrail：每个声称"shipped + verified"的 P-spec 任务必带 evidence link（commit + test 输出 + PR#）— 与 handoff §Step 4 提议同源
4. North Star Comparability 维度回填：本 finding fix shipped 后 4/5（之前 handoff 诚实降到 3/5；现在"replay 真测过"了）

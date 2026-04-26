# F023 — DPO rewards/{margins,chosen,rejected} 不在 `all_results.json`，F022 fix 抓不到 → 需读 `trainer_state.json::log_history`

| | |
|---|---|
| 发现时间 | 2026-04-27（F022 fix 后跑 video DPO smoke 立刻发现 rewards/* 全 None）|
| 发现 phase | handoff task #27 video E2E DPO 真测 |
| severity | **HIGH** — DPO 唯一有意义的 metrics（rewards/margins / chosen / rejected）丢失，eval gate 拿 train_loss 评 DPO 等于"评 SFT"，retro 自评 DPO 维度无证据可信 |
| 状态 | **FIXED** — pet-train `fix/F023-collect-dpo-rewards-from-trainer-state`（同 PR 含 SFT + DPO 双 wrapper 升级 + 2 测）|
| 北极星受影响维度 | **Comparability**（DPO 对比 SFT 的核心指标 rewards/margins 永远 = None）+ **Pluggability**（DPO trainer plugin 接口宣称返回 ModelCard with metrics，实测只有 train_loss）|

## 复现命令

```bash
# rental 2026-04-27 video E2E DPO smoke：
cd /root/autodl-tmp/eco-validation/pet-train
/root/miniconda3/envs/pet-pipeline/bin/python /tmp/run_video_dpo.py
# LF log per-step：rewards/margins=0.50, rewards/chosen=0.135, rewards/rejected=-0.366
# 但脚本最后 card.metrics.get('rewards/margins') 输出：
#   rewards/margins: None
# all metric keys: ['epoch', 'total_flos', 'train_loss', 'train_runtime', ...]
```

## 实际行为

LLaMA-Factory DPO trainer 输出多份文件：

| 文件 | 含 train_loss/aggregate? | 含 rewards/* per-step? |
|---|---|---|
| `all_results.json` | ✅ 仅 6 个 aggregate keys | ❌ |
| `train_results.json` | ✅ 子集 of all_results | ❌ |
| `trainer_log.jsonl` | ❌ per-step lines | ✅ 每步 |
| `trainer_state.json::log_history` | ❌ aggregate 在末尾 | ✅ 每步均含；末尾倒数第 2 entry 是最后训练步 |

F022 fix（`_collect_train_metrics` 只读 `all_results.json`）：

```python
# 旧：
return {k: float(v) for k, v in payload.items() if isinstance(v, (int, float))}
# 输出：{'epoch': 0.67, 'total_flos': ..., 'train_loss': 0.627,
#        'train_runtime': ..., 'samples_per_second': ..., 'steps_per_second': ...}
# 缺：rewards/margins, rewards/chosen, rewards/rejected, rewards/accuracies,
#    logps/chosen, logps/rejected, logits/chosen, logits/rejected
```

后果：DPO trained ModelCard 看上去只有 train_loss=0.627（与 SFT 同形态），无法证明 DPO 真在做"chosen/rejected 的 margins maximize"——eval / retro / ClearML 任何下游对比都失去 DPO 维度。

## 期望行为

`_collect_train_metrics` 应当：

1. 读 `all_results.json`（aggregate train_loss / runtime / epoch）
2. 读 `trainer_state.json::log_history`，**取最后一个含 rewards/* 或 logps/* 或 logits/* 的 entry**——那是最后一步的 final state
3. 二者 merge

## 根因

P5/P6 retro 标"DPO trainer plugin shipped"。F022 fix 只读 `all_results.json` 是因为单元测 fixture 用的就是 SFT-shape payload；**没人写过 DPO fixture**，所以 F022 单元测 100% pass + DPO rewards 永远 None 这个组合不会被任何自动测试 detected。

跟 F022 同款"unit-test 没 fixture-real 即等于声称工作但端到端没跑过"——retro 教训第二次出现。

## 修复

`_collect_train_metrics`（SFT + DPO 两 wrapper 同款实现）：

```python
def _collect_train_metrics(self) -> dict[str, float]:
    out_dir = Path(self._output_dir)
    metrics: dict[str, float] = {}
    # 1. aggregate
    for fname in ("all_results.json", "train_results.json"):
        p = out_dir / fname
        if p.exists():
            try:
                payload = json.loads(p.read_text())
                metrics.update({k: float(v) for k, v in payload.items()
                                if isinstance(v, (int, float)) and not isinstance(v, bool)})
            except (OSError, json.JSONDecodeError):
                pass
            break
    # 2. last-step rewards/logps/logits from trainer_state.json
    state_path = out_dir / "trainer_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except (OSError, json.JSONDecodeError):
            state = {}
        for entry in reversed(state.get("log_history", []) or []):
            step_metrics = {k: float(v) for k, v in entry.items()
                            if isinstance(v, (int, float)) and not isinstance(v, bool)
                            and (k.startswith("rewards/") or k.startswith("logps/") or k.startswith("logits/"))}
            if step_metrics:
                metrics.update(step_metrics)
                break
    return metrics
```

新增 2 测：DPO `test_collect_train_metrics_pulls_rewards_from_trainer_state`（fixture 内置 step1 + step5 + train summary 三 entries，验证最后步的 rewards/* 被抓且不混进 step1）；SFT `test_collect_train_metrics_no_rewards_for_sft`（SFT trainer_state 无 rewards/*，metrics 仅 aggregate）。

PR：pet-train `fix/F023-collect-dpo-rewards-from-trainer-state`（SFT 同款代码 — 因为 SFT 默认 log_history 无 rewards/* 所以 SFT 无副作用）。

## Retest 证据

本地：

```bash
$ pytest tests/plugins/test_llamafactory_*.py -q
..............                                                           [100%]
14 passed in 0.63s
```

Rental（fix push 后跑 video DPO smoke 验证 card.metrics["rewards/margins"] 真有值，本 doc 在 fix 验证后回填）。

## Follow-ups

1. ✅ 14 单元测 cover F022+F023 综合，含 DPO fixture（防 retro 教训第三次复发）
2. SFT wrapper 同款 fix 后无副作用（其 trainer_state.log_history 无 rewards/*），未来若 SFT 升 RM/PPO 阶段会自然受益
3. ClearML reporter 应被 audit 是否真把 ModelCard.metrics 的所有 keys forward 到 task — F023 修后下游 reporter 能拿到 rewards 但若 reporter 只 forward 一个固定 keys 子集，retro 依旧失真。需独立验

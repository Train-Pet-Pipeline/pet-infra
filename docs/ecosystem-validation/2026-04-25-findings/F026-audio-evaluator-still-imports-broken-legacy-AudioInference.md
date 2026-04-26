# F026 — pet-eval `audio_evaluator` 还在 import F008-broken `AudioInference`，PANNs 修了但消费端没切换

| | |
|---|---|
| 发现时间 | 2026-04-27（F008 retro audit — 检查 audio path orchestrator 端是否真用 PANNs）|
| 发现 phase | F018-F025 闭环后做"声称 vs 实际"audio modality 系统对照 |
| severity | **STRUCTURAL** — orchestrator audio eval path 永远跑不通官方 PANNs 权重；retro 标 "PANNs zero-shot ✅" 只是 stand-alone import 验证；recipe / `pet run` 走的是 broken legacy 类 |
| 状态 | **FIXED** — pet-eval `fix/F026-audio-evaluator-uses-broken-AudioInference` (default backend='panns', legacy 退化成 opt-in) |
| 北极星受影响维度 | **Pluggability**（生产者改了，消费者没切；plugin contract 实际 broken）+ **Comparability**（audio retro 数据全部来自 stand-alone 验证，与 orchestrator path 不一致） |

## 复现命令

```bash
# F008 fix shipped pet_train.audio.panns_inference_plugin.PANNsAudioInference
grep -nE "PANNsAudioInference|AudioInference" \
     pet-eval/src/pet_eval/plugins/audio_evaluator.py
# 输出（fix 之前）：
#   from pet_train.audio.inference import AudioInference  ← 用 broken 旧类
# 没有 PANNsAudioInference 引用
```

orchestrator 端跑 audio_eval recipe 会走 AudioInference → F008 retro 已加的"checkpoint arch drift warning"会爆，但 pipeline 整体仍 broken。

## 实际行为

F008 fix 的两次 commit：
1. `feat(pet-train): pluggable PANNsAudioInference plugin (F008) (#30)` — 加新类
2. `test(pet-train): F008 retro — log warning on checkpoint arch drift + regression test (#32)` — 给旧 AudioInference 加 drift warning

**没有第 3 次 commit** 把 pet-eval 的 AudioEvaluator 切换到新的 PANNs 类。所以：

- 单元测试 `test_audio_evaluator.test_cross_repo_import_succeeds` import `pet_train.audio.inference.AudioInference` → 永远 PASS（旧类还在）
- handoff retro "PANNs zero-shot 8/8 frames verified" — 实际走的是 stand-alone 直接 `from pet_train.audio.panns_inference_plugin import PANNsAudioInference; PANNsAudioInference().predict(audio)`，没经过 AudioEvaluator pipeline
- orchestrator `pet run cross_modal_fusion_eval.yaml` audio stage 调用 EVALUATORS.build({type: audio_evaluator}).run(...) → 进入 AudioInference → 旧类（如果有 checkpoint）必加载失败/数据错

## 期望行为

`AudioEvaluator.run` 默认应当用 PANNsAudioInference（with 官方 panns_inference 包）。Legacy mobilenetv2 应保留为 opt-in（`cfg["inference_backend"] = "legacy_mobilenetv2"`）以不破坏既有 unit-test fixture，但**默认走能跑的路径**。

## 根因

F008 retro 把"plugin 接口落地无端到端跑"列为系统教训第 1 次。F026 是同款教训第 10 次：消费者-生产者升级时**只升级生产者**，没有同 PR 改消费者绑定，下游 plugin contract 实质 broken 但 plug-shape 看起来 OK。

单元测试 strict 验证消费者侧"能 import legacy 类"，等于把 broken 状态锁住。fixture-real test（"创建 PANNsAudioInference 实例 + assert backend"）从未存在 → bug 永远不会被本仓 CI 捕获。

## 修复

`src/pet_eval/plugins/audio_evaluator.py` `run()` 增加 backend 分流：

```python
backend = (self._cfg.get("inference_backend") or "panns").lower()
if backend == "panns":
    from pet_train.audio.panns_inference_plugin import PANNsAudioInference
    inference = PANNsAudioInference(checkpoint_path=..., device=...)
elif backend in ("legacy_mobilenetv2", "mobilenetv2_legacy"):
    from pet_train.audio.inference import AudioInference
    inference = AudioInference(pretrained_path=..., device=..., sample_rate=...)
else:
    raise ValueError(f"AudioEvaluator unknown inference_backend={backend!r}; "
                     "valid: 'panns' (default) or 'legacy_mobilenetv2'")
predicted, actual = self._collect_predictions_and_labels(inference)
```

新增 4 测：
- `test_run_uses_panns_backend_by_default`：assert PANNs 类 called，legacy 类未 called
- `test_run_legacy_backend_opt_in`：assert opt-in 时 legacy called
- `test_run_unknown_backend_raises`：unknown backend 抛 ValueError
- existing `test_run_iterates_audio_files_and_computes_metrics` patch target 改成 PANNsAudioInference

PR：pet-eval `fix/F026-audio-evaluator-uses-broken-AudioInference`（已开 PR #44）。

## Retest 证据 ✅

本地：

```bash
$ pytest tests/test_plugins/test_audio_evaluator.py -q
.............                                                            [100%]
13 passed in 2.45s
```

含 backend-default 与 legacy-opt-in 双向 assertion，防 F026-class 复发。

Rental（fix push 后跑 audio_evaluator 真测时回填 — 验证 orchestrator path 真用 PANNs 类）。

## Follow-ups

1. ✅ 4 测在 pet-eval audio_evaluator
2. F008 / F026 同源教训：每次 plugin 接口 fix 必带"消费者 binding 同 PR 切换 + fixture-real test"，retro 流程文档化（pet-infra DEV_GUIDE §plugin-contract 增 sub-section）
3. Audio in-domain validation（F017 doc 已写）：下次 rental 用真 feeder-near-field 录音跑 AudioEvaluator with PANNs backend
4. 长期：legacy AudioInference 类应在 v3 major release 删除，代价是早期 unit-test fixture 失效；先 deprecation warning 一个 release

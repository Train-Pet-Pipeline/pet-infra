# F014 — pet-eval fusion evaluators registered but missing run() method

| | |
|---|---|
| 发现时间 | 2026-04-26 07:05 |
| 发现 phase | Phase 2.5 E3 / Phase 3.X1 |
| severity | **STRUCTURAL** — registered but unrunnable, 直接破坏 Pluggability |
| 状态 | **FIXED + commit pushed**（pet-eval fix/eco-validation-fusion-evaluator-run-method）|
| 北极星受影响维度 | **Pluggability + Comparability**（声称 fusion evaluator plugin 可被 orchestrator 调度，实际不可）|

## 复现命令

```bash
pet run pet-eval/recipes/cross_modal_fusion_eval.yaml
```

## 实际行为

```
AttributeError: 'WeightedFusionEvaluator' object has no attribute 'run'
```

`EvaluatorStageRunner.run()` (in pet-infra/orchestrator/hooks.py) 期望调 `plugin.run(input_card, recipe)`。但：
- `WeightedFusionEvaluator` 只有 `fuse(modality_scores: dict)`
- `AndGateFusionEvaluator` 同
- `SingleModalFusionEvaluator` 同
- 共同基类 `BaseFusionEvaluator` 是 ABC，只 abstract `fuse`，没 `run`

3 个 plugins 注册到 `EVALUATORS` registry 但**永远不能被 orchestrator 调度运行**。

## 期望行为

orchestrator 调 `plugin.run(input_card, recipe)` 时：
- 从 input_card.metrics 提取 modality scores
- 调 `self.fuse(modality_scores)`
- 返回带 `fused_score` 的新 ModelCard

## 根因

设计阶段（Phase 4 W2）只把 fusion evaluators 当作"纯函数"实现 — 缺 stage runner 接口。注册到 EVALUATORS 但没满足 EvaluatorStageRunner 调度合同。

直接违反 spec §1.3 不变量 #9 北极星 Pluggability：
> 新模型/新 modality 是否只加 plugin 不改核心？

实际：fusion plugin **不能**作为 stage 用，必须改 stage runner（核心）才能调度——是反例。

## 修复

`pet-eval/src/pet_eval/plugins/fusion/base.py` 给 `BaseFusionEvaluator` 加默认 `run()` 实现：
- 从 `input_card.metrics` 抽取 `modality_score:<name>` 前缀键
- 调 `self.fuse(modality_scores)`
- 返回 ModelCard 带 `metrics["fused_score"] = fused`
- 空 input → fused = 0.0（smoke 路径）

3 个子类（weighted/and_gate/single_modal）继承 base.run() 自动 work。

## Retest 证据 ✅

```bash
pet run recipes/cross_modal_fusion_eval.yaml
# →
E3 OK card.id: cross_modal_fusion_eval_eval_b61cb3a4
  fused_score: 0.0  # 预期，无 input scores
  arch: WeightedFusionEvaluator
```

variations sweep（推 component_type 切 3 plugin）也工作。

## Follow-ups

1. ✅ committed: pet-eval fix/eco-validation-fusion-evaluator-run-method (3cfc906)
2. PR review + merge
3. 加单测：`tests/plugins/test_fusion_run_method.py` 三 plugin 都被 EvaluatorStageRunner 调度成功
4. **重要架构 retro**：spec §3.5 E3 说"3 plugins 已注册"被 grep 验证为 ✅，但**实际可调度性没测**。建议 spec 测试方法升级：注册 ≠ 可用

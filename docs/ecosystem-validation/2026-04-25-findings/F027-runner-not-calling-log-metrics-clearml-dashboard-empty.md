# F027 — `runner.pet_run()` 不 call `log_metrics(card.metrics)` → ClearML dashboard 永远没 scalar 信号

| | |
|---|---|
| 发现时间 | 2026-04-27（F022/F023 fix retest 后审计 ClearML 流向）|
| 发现 phase | F022/F023 closeout audit — verify card.metrics 真到 ClearML dashboard |
| severity | **HIGH** — F022/F023 让 train_loss / rewards/* 进了 card.metrics，但 orchestrator 不 forward 到 ClearML 的 scalar reporter；ClearML dashboard 永远空，retro "ClearML 是 sole tracker" 名实不符 |
| 状态 | **FIXED** — pet-infra `fix/F027-runner-not-calling-log-metrics`（runner.py 4 行 + 2 unit test）|
| 北极星受影响维度 | **Comparability**（experiment-log scalars 是跨 run 比较核心；空 dashboard = 不可比）|

## 复现命令

```bash
# 静态证明：log_metrics 只有定义，没人 call
grep -rE "log_metrics" --include="*.py" pet-infra/src/
# pet_infra/experiment_logger/null_logger.py:    def log_metrics(...)
# pet_infra/experiment_logger/base.py:    def log_metrics(...)
# pet_infra/experiment_logger/clearml_logger.py:    def log_metrics(...)
# 三处都是 def，零 call 点。

grep -rE "experiment_logger\.log_metrics|\.log_metrics\(" --include="*.py" pet-infra/src/
# (empty)
```

## 实际行为

`pet_infra.orchestrator.runner.pet_run` DAG walk 末尾：

```python
if task_id is not None:
    card.clearml_task_id = task_id
experiment_logger.log_model_card(card)  # ← 只 attach 整张 card 当 config
cache.save(card_id, card.model_dump(mode="json"))
experiment_logger.finish("success")
```

`ClearMLLogger.log_model_card`：

```python
def log_model_card(self, card):
    self._task.connect_configuration(card.model_dump(mode="json"), name="model_card")
```

`task.connect_configuration` 把 card 整体当 hyperparameter / config blob 上传——可搜，但**不画图**。要画图（`task.get_logger().report_scalar`）必须走 `task.get_logger().report_scalar(...)` per metric——这是 `log_metrics` 内部做的：

```python
def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
    for k, v in metrics.items():
        self._task.get_logger().report_scalar(title=k, series=k, value=v, iteration=...)
```

但 `log_metrics` 从来没人 call。所以 ClearML web UI 上：

- `Configuration` 页 → 看到 `model_card` JSON blob 含 metrics（搜得到，看得到，但不分组）
- `Scalars` 页 → 空空如也

## 期望行为

每个 stage 跑完，orchestrator 应当：
1. 把 card.metrics 灌进 logger 的 scalar 接口 → ClearML scalars 页有 train_loss / rewards/margins 的曲线（or 单点）
2. 还应继续 attach 整张 card 当 config（已做）

两者并行，不冲突。

## 根因

P5/P6 retro 标 "ClearML 是 sole experiment tracker, ✅ MLflow / W&B 已 dropped"。但 **从未端到端验证 ClearML dashboard 真有数据**——只是抽象上"experiment_logger 接口齐了，方法都存在"。`log_metrics` 实现完整、单元测试 cover、但**生产路径下从无 call**。同款 F022/F023 retro "shipped + interface ready + path doesn't exercise it" — 第 11 次。

## 修复

`runner.py` DAG walk 在 `log_model_card` 后 + `cache.save` 前插 4 行：

```python
experiment_logger.log_model_card(card)
# F027 fix: also forward card.metrics to the logger as scalars so ClearML
# dashboard shows train_loss / rewards/margins / etc.
if card.metrics:
    experiment_logger.log_metrics(card.metrics)
cache.save(card_id, card.model_dump(mode="json"))
```

`if card.metrics:` 保护避免 ClearML "empty metrics" 噪音。

新增 2 测：
- `test_runner_calls_log_metrics_with_card_metrics`：assert log_metrics 被 call 且参数 = card.metrics
- `test_runner_skips_log_metrics_when_card_metrics_empty`：assert 空 metrics 时不 call

PR：pet-infra `fix/F027-runner-not-calling-log-metrics`（4 行代码 + 2 fixture-real-style test）。

## Retest 证据 ✅

本地：

```bash
$ pytest tests/orchestrator/test_runner_log_metrics.py -v
test_runner_calls_log_metrics_with_card_metrics PASSED
test_runner_skips_log_metrics_when_card_metrics_empty PASSED
2 passed in 0.65s
```

Rental（fix push 后跑真 SFT，启 ClearML offline mode，verify report_scalar 真触发；本 doc 在 verify 后回填）。

## Follow-ups

1. ✅ F027 fix shipped to dev via PR
2. retro `pet-infra DEV_GUIDE §experiment_logger`：补"orchestrator 必须 call log_metrics 一次 per stage"约定
3. 长期：考虑统一 stage-finish hook（`experiment_logger.log_stage_complete(card)` 内部 dispatch model_card + metrics）；现状 caller 必须知道两个调用，违反 single-responsibility
4. ClearML 真 dashboard 真测：下次 rental 跑 SFT with ClearML enabled → 截图 / scalar API verify

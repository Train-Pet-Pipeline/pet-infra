# F022 — pet-train llamafactory_sft / llamafactory_dpo wrappers 不抓 LF train metrics 进 ModelCard

| | |
|---|---|
| 发现时间 | 2026-04-27（video E2E SFT smoke 跑出）|
| 发现 phase | handoff task #27 video E2E pipeline 真测 — pet-annotation v2.2.2 export → pet-train SFT |
| severity | **STRUCTURAL** — ModelCard.metrics 永远 = {}，eval gate / ClearML 下游全无信号；声称的 train→eval 闭环根本没数据流过 |
| 状态 | **FIXED** — pet-train `fix/F022-llamafactory-sft-wrapper-not-capturing-metrics`（含 SFT + DPO 双修 + 6 tests）|
| 北极星受影响维度 | **Comparability**（card.metrics 是基础证据；空 dict 等于不可比）+ **Pluggability**（gate 拿不到 train_loss 就无法触发 short-circuit）|

## 复现命令

```bash
# rental session 2026-04-27 video E2E：
cd /root/autodl-tmp/eco-validation/pet-train
/root/miniconda3/envs/pet-pipeline/bin/python /tmp/run_video_sft.py
# LLaMA-Factory log 输出：
#   train_loss = 0.5181
#   train_runtime = 8.2567
# 但脚本最后 `print(card.metrics.get("train_loss", "N/A"))` 输出：
#   train_loss: N/A
```

## 实际行为

`pet_train.plugins.llamafactory_sft.LlamaFactorySFTTrainer.run()` 流程：

1. `from llamafactory.train.tuner import run_exp`
2. `run_exp(args=self._lf_args)` ← LF 跑完，写 `<output_dir>/all_results.json` + `train_results.json` + `trainer_log.jsonl` + `trainer_state.json`
3. `self._adapter_uri = f"file://{...}/adapter"`
4. `return self._build_model_card(...)` ← 直接返回新 card

`_build_model_card` 里：

```python
return ModelCard(
    ...
    checkpoint_uri=self._adapter_uri or "",
    ...
    metrics={},  # ← BUG，hardcoded 空 dict
    gate_status="pending",
    ...
)
```

`llamafactory_dpo.py` 同款（line 120 `metrics={}`）。

后果：

1. `ModelCard.metrics` = `{}` 永远；下游 eval gate `apply_gate(metrics, thresholds)` 永远拿不到 train_loss 等指标
2. ClearML 通过 `experiment_logger.log_model_card(card)` 记录的 metrics dict 是空的，与 LF 自己写的日志数据完全脱节
3. `pet run --replay` 重跑后两次 card.metrics 都是空 dict — 无法验证 reproducibility（"replay 出 train_loss 一致"无法检验）

## 期望行为

LF 写完结果后，wrapper 应当读 `<output_dir>/all_results.json`（fallback `train_results.json`）把所有数值字段（含 `train_loss`、`train_runtime`、`epoch`、`rewards/margins` 等）灌进 `ModelCard.metrics`。

## 根因

P5 retro 标"LlamaFactorySFTTrainer wrapper shipped with run_exp + ModelCard"。但 `metrics={}` 是 placeholder，从来没换成"读 all_results.json 并填回"的真实数据流。同款 F008/F011/F012/F014/F021 retro 的"plugin 接口落地无端到端跑"流程 bug：单元 test 验证 trainer 能 `register` + `_lf_args` 正确，但**没验证 card.metrics 真有内容**。

## 修复

`src/pet_train/plugins/llamafactory_sft.py` + `src/pet_train/plugins/llamafactory_dpo.py` 各加 `_collect_train_metrics()`：

```python
def _collect_train_metrics(self) -> dict[str, float]:
    out_dir = Path(self._output_dir)
    for fname in ("all_results.json", "train_results.json"):
        p = out_dir / fname
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return {
            k: float(v) for k, v in payload.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
    return {}
```

`run()` 末尾在 `_build_model_card` 之前 `self._metrics = self._collect_train_metrics()`，`_build_model_card` 把 `dict(self._metrics)` 灌进 ModelCard。

`__init__` 加 `self._metrics: dict[str, float] = {}`。

新增 6 测：

- SFT 三测：parses all_results.json / no-file → {} / falls back to train_results.json
- DPO 三测：parses all_results.json (含 rewards/margins / chosen / rejected) / no-file → {} / + 实际 fields 验证

PR：pet-train `fix/F022-llamafactory-sft-wrapper-not-capturing-metrics`（待 ship）。

## Retest 证据 ✅

本地：

```bash
$ pytest tests/plugins/test_llamafactory_sft.py tests/plugins/test_llamafactory_dpo.py -q
............                                                             [100%]
12 passed in 0.62s
```

Rental（fix push 后再跑 video SFT smoke 验证 card.metrics["train_loss"] 真有值；本 doc 在 fix push 时回填）。

## Follow-ups

1. ✅ tests/plugins/* 加 12 测，含 ruff + mypy clean
2. card.metrics 现含 LF 写的所有数值 keys（train_loss / train_runtime / epoch / total_flos / rewards/* / ...）；下一步可考虑 normalize：例如 `train_loss_final` 同步到 `pet_train.train_loss` 之类的 canonical name 给 gate 用
3. 同款检查：pet-train 还有别的 trainer 不？检查 tiny_test 是否有 metrics={...} placeholder（已检查 — tiny_test 正确填了 `train_loss=last_loss`）；audio inference plugin 是 inference path 不涉 train_loss
4. retro guardrail：每 trainer 加端到端 test fixture 跑真 mini-train + assert card.metrics non-empty（防 F022-class 复发）

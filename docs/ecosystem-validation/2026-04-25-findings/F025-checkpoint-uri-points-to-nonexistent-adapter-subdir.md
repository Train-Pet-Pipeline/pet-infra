# F025 — pet-train LF wrappers 写 `checkpoint_uri = .../adapter` 但 LF 实际不创建 `adapter/` 子目录 → 下游 inference / eval 静默回退到 base model

| | |
|---|---|
| 发现时间 | 2026-04-27（rental video E2E SFT smoke 后核对 sft-video/ 目录结构发现）|
| 发现 phase | F022 fix retest 后 → eval pipeline 准备 |
| severity | **STRUCTURAL** — silent finetune-disabled bug；checkpoint_uri 指向不存在路径；transformers/peft 加载失败时常 fallback 到 base model 不报错；eval 显示"reasonable" base-model 数据被当成 finetuned 表现 |
| 状态 | **FIXED** — pet-train `fix/F025-checkpoint-uri-points-to-nonexistent-adapter-subdir`（SFT + DPO 双 wrapper + unit test 验证 file existence）|
| 北极星受影响维度 | **Pluggability**（plugin 接口宣称返回 file:// URI to weights，URI 实际无效）+ **Comparability**（finetuned vs base 区分失效，retro 不可信）|

## 复现命令

```bash
# rental 2026-04-27：F022 fix 之后第一次能跑通 SFT
cd /root/autodl-tmp/eco-validation/pet-train
/root/miniconda3/envs/pet-pipeline/bin/python /tmp/run_video_sft.py
# === SFT complete ===
# train_loss: 0.5181813...
# checkpoint_uri: file:///root/autodl-tmp/eco-validation/runs/video-e2e/sft-video/adapter

ls /root/autodl-tmp/eco-validation/runs/video-e2e/sft-video/
# README.md adapter_config.json adapter_model.safetensors all_results.json
# chat_template.jinja checkpoint-8 merges.txt preprocessor_config.json
# special_tokens_map.json tokenizer.json tokenizer_config.json train_results.json
# trainer_log.jsonl trainer_state.json training_args.bin video_preprocessor_config.json
# vocab.json
# 注意：没有 'adapter' 子目录！

ls /root/autodl-tmp/eco-validation/runs/video-e2e/sft-video/adapter
# ls: cannot access ...: No such file or directory  ← BUG
```

## 实际行为

`pet_train/plugins/llamafactory_sft.py:99` & `pet_train/plugins/llamafactory_dpo.py:98`：

```python
run_exp(args=self._lf_args)
self._adapter_uri = f"file://{Path(self._output_dir).resolve()}/adapter"
                                                            ^^^^^^^
                                                            ← BUG
```

LLaMA-Factory `run_exp(stage="sft" or "dpo")` 配 `output_dir` 时，把 adapter weights 直接写到 `output_dir/adapter_model.safetensors`，**不**创建 `output_dir/adapter/` 子目录。

下游 `pet_eval.plugins.vlm_evaluator.VLMEvaluator.run`：

```python
model_path = self._cfg.get("model_path") or input_card.checkpoint_uri.replace("file://", "")
outputs = run_inference(model_path=model_path, ...)
```

`model_path = "<output_dir>/adapter"` 不存在。`transformers.AutoModelForCausalLM.from_pretrained` 在该路径下 fallback 加载行为视版本不同：
- 报 `OSError: ... not found` → 显式断（好）
- 或 fallback 加载 base model 静默继续（坏 — eval 出来的"finetuned 模型 metrics"实际是 base model）

实测过哪种？rental 之前 F022 之前 metrics 永远 = `{}`，所以 eval 从未真跑过。F022 之后 eval pipeline 是下一个要 retest 的 — F025 fix 必须在 retest 前 ship 否则 eval retest 看到的是错的数据。

## 期望行为

`checkpoint_uri = file://<output_dir>` （drop `/adapter` 后缀）。这与 LF 实际写入位置一致，下游 `from_pretrained(model_path)` 能找到 adapter_model.safetensors + adapter_config.json。

## 根因

P5 retro 标 "LlamaFactorySFTTrainer wrapper shipped"。这一行 `f"file://{...}/adapter"` 大概率是从早期 LF 版本（其 save_safetensors 行为可能写 adapter/ 子目录）抄来的，但当前 LF 0.9.4 实际写 output_dir 平铺。**没人写过 fixture-real test 验证 `Path(checkpoint_uri.replace('file://', '')) / 'adapter_model.safetensors'` 真的存在**。

同款 F008/F011/F012/F014/F021/F022/F023/F024 retro 教训："unit-test mock 路径，没真 path 做 file existence check"——第 9 次出现。

## 修复

`pet_train/plugins/llamafactory_sft.py` 和 `llamafactory_dpo.py` 各 1 行：

```python
# - self._adapter_uri = f"file://{Path(self._output_dir).resolve()}/adapter"
# + self._adapter_uri = f"file://{Path(self._output_dir).resolve()}"
```

新增 1 unit test `test_adapter_uri_points_to_output_dir`：
- stub `llamafactory.train.tuner.run_exp` 不真训练
- 写 fake `adapter_model.safetensors` 到 `tmp_path`
- 跑 `trainer.run(...)`
- assert `card.checkpoint_uri == f"file://{tmp_path}"`
- **assert `Path(urlparse(card.checkpoint_uri).path) / "adapter_model.safetensors"` 实际存在** ← fixture-real 验证防 F025 复发

PR：pet-train `fix/F025-checkpoint-uri-points-to-nonexistent-adapter-subdir`。

## Retest 证据 ✅

本地：

```bash
$ pytest tests/plugins/ -q
...............................                                          [100%]
31 passed in 1.02s
```

含 fixture-real existence assertion，确保任何未来对该路径的 silent regression 立刻爆。

Rental（fix push 后 vlm_evaluator 真测时回填 — 验证 `from_pretrained(checkpoint_uri)` 真加载到 SFT 训练的 adapter）。

## Follow-ups

1. ✅ fixture-real test in 4 仓 LF wrappers
2. retro 流程：所有 plugin 写 file:// URI 必带 unit test 验证目标路径 actually exists（防同款）
3. pet-eval `vlm_evaluator.run` 应 fail-fast 当 model_path 不存在（而不是依赖 transformers 隐式行为）— 单独 finding 候选

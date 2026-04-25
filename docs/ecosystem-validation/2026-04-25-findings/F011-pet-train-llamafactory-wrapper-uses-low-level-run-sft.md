# F011 — pet-train llamafactory_sft.py 调低层 `run_sft(**kwargs)` 而非 `run_exp(args)`

| | |
|---|---|
| 发现时间 | 2026-04-26 01:08 |
| 发现 phase | Phase 1.3 SFT — TypeError on run_sft |
| severity | **HIGH** — 阻塞 LLaMA-Factory SFT 全部用法 |
| 状态 | **FIXED on rental + commit pushed**（pet-train fix/eco-validation-llamafactory-run-exp 分支）|
| 北极星受影响维度 | Pluggability + Comparability |

## 复现命令

```bash
# 用 pet_run 启动 llamafactory_sft 插件
python -c "
import pet_train.plugins._register; pet_train.plugins._register.register_all()
from pet_infra.orchestrator.runner import pet_run
from pathlib import Path
pet_run(Path('recipes/.../sft.yaml'))
"
```

## 实际行为

```
File "pet_train/plugins/llamafactory_sft.py", line 74, in run
    run_sft(**self._lf_args)
TypeError: run_sft() got an unexpected keyword argument 'model_name_or_path'
```

`run_sft` (低层 workflow) 签名：
```python
def run_sft(
    model_args: ModelArguments,
    data_args: DataArguments,
    training_args: Seq2SeqTrainingArguments,
    finetuning_args: FinetuningArguments,
    generating_args: GeneratingArguments,
    callbacks: list[TrainerCallback] | None = None,
)
```

需要 5 个已 parsed 的 dataclass 参数，不接受 flat kwargs dict。

## 期望行为

`pet-train.LlamaFactorySFTTrainer.run()` 应调 `llamafactory.train.tuner.run_exp(args=dict)`，因为这是 LF 公开高层入口（接受 flat dict + 内部做 dataclass parsing）。

## 根因

pet-train 写 wrapper 时引用了 LF 内部 `run_sft`（vendor 内部 API），不是 `run_exp`（公开入口）。`_hydra_to_lf_args` 产出 LF YAML/CLI 风格的 flat dict，对 `run_sft` 不兼容。

## 修复

`pet-train/src/pet_train/plugins/llamafactory_sft.py` 改 2 行：

```python
# before
from llamafactory.train.sft.workflow import run_sft
run_sft(**self._lf_args)

# after
from llamafactory.train.tuner import run_exp
run_exp(args=self._lf_args)
```

同时 `_hydra_to_lf_args` 扩展支持透传可选 LF-native config keys（dataset_dir, template, cutoff_len, ...）。Map `precision` → bf16/fp16 booleans。Add `do_train: True` default.

## Retest 证据 ✅

rental 上 SFT 跑通：
- Qwen2-VL-2B-Instruct + LoRA r=16 + 30 Doubao samples
- 30 steps（3.8 epochs）
- **loss 0.4226 → 0.17** 单调下降
- 26 秒训练时间（RTX PRO 6000 Blackwell 96GB）
- 4.6 samples/sec
- checkpoint-30/ + adapter_model.safetensors + chat_template.jinja 全部 saved

## Follow-ups

1. ✅ commit pushed: pet-train fix/eco-validation-llamafactory-run-exp (665c68a)
2. PR review + merge to dev
3. 加单测 `tests/plugins/test_llamafactory_sft.py::test_run_uses_run_exp_not_run_sft`
4. **F008 与本 finding 关联**：spec T8 "LLaMA-Factory vendor 隔离" 仅检查 grep，不验真实 invocation；建议 retro 加强 vendor API contract 测试

# F013 — pet-train llamafactory wrapper hardcodes finetuning_type=lora

| | |
|---|---|
| 发现时间 | 2026-04-26 06:50 |
| 发现 phase | Phase 2.4 T2 (full-param SFT) |
| severity | HIGH — 阻塞全参 SFT |
| 状态 | **FIXED + commit pushed**（pet-train fix/eco-validation-llamafactory-run-exp）|
| 北极星受影响维度 | Flexibility — recipe 可配 finetuning_type 但 wrapper 不读 |

## 复现命令

```yaml
# recipe override
finetuning_type: full
```

```bash
pet run recipes/eco_validation_t2.yaml  # 期望全参 SFT
```

## 实际行为

LLaMA-Factory 仍走 LoRA 路径（虽然 logs 输出 lora_r/lora_alpha=0）— 因为 pet-train wrapper `_hydra_to_lf_args` 直接 hardcode `finetuning_type: "lora"`，根本没读 cfg 中的设置。

## 根因

`pet-train/src/pet_train/plugins/llamafactory_sft.py` line 47-48：
```python
"finetuning_type": "lora",  # hardcoded
"stage": "sft",
```
同样的 bug 在 `llamafactory_dpo.py` line 48。

## 修复

honor `cfg.get("finetuning_type", "lora")`；当 `full` 时不传 lora_rank/lora_alpha：

```python
ft_type = cfg.get("finetuning_type", "lora")
args = {..., "finetuning_type": ft_type, ...}
if ft_type == "lora":
    args["lora_rank"] = cfg["lora_r"]
    args["lora_alpha"] = cfg["lora_alpha"]
```

## Retest 证据 ✅

T2 全参 SFT on rental：
- Qwen2-VL-2B + finetuning_type=full + 30 samples + 30 steps
- **loss 0.17 → 0.05** monotonic
- 59 秒（vs LoRA 26s — 全参更慢但更深拟合）
- VRAM peak 适配 RTX PRO 6000 96GB
- T2 card.id 生成 + checkpoint saved

## Follow-ups

1. ✅ committed: pet-train fix/eco-validation-llamafactory-run-exp (cbd8994 + c44552a)
2. PR review + merge
3. 加单测 `tests/plugins/test_llamafactory_sft.py::test_finetuning_type_honored`

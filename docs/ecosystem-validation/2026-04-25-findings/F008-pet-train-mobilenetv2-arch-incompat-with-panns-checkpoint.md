# F008 — pet-train MobileNetV2AudioSet 架构与 PANNs 官方 checkpoint 不兼容

| | |
|---|---|
| 发现时间 | 2026-04-26 00:38 |
| 发现 phase | Phase 2.4 / T4 audio zero-shot inference |
| severity | **HIGH** — 阻塞 audio modality 端到端验证 |
| 状态 | OPEN（架构层面不兼容，rental 上无法绕过；defer Phase 5 修） |
| 北极星受影响维度 | **Pluggability + Comparability**（audio modality 宣称 zero-shot 实际无法用官方权重）|

## 复现

```bash
hf_home=/root/autodl-tmp/hf-cache
# 下载 PANNs MobileNetV2 官方权重
wget "https://zenodo.org/records/3987831/files/MobileNetV2_mAP%3D0.383.pth?download=1" \
  -O $hf_home/panns/MobileNetV2.pth
# 装配 pet-train AudioInference
python -c "
from pet_train.audio.inference import AudioInference
ai = AudioInference(pretrained_path=\"$hf_home/panns/MobileNetV2.pth\")
"
```

## 实际行为

```
RuntimeError: Error(s) in loading state_dict for MobileNetV2AudioSet:
  size mismatch for features.1.conv.0.weight:
    copying a param with shape torch.Size([32, 1, 3, 3]) from checkpoint,
    the shape in current model is torch.Size([96, 16, 1, 1]).
  size mismatch for features.1.conv.4.weight: ...
  ... (30+ size mismatches across all features.* layers)
```

## 期望行为

`AudioInference` 加载官方 PANNs MobileNetV2 权重成功，对 16kHz mono audio 输出 527 维 AudioSet logit + 5 类宠物聚合（DEV_GUIDE §2.5）。

## 根因

pet-train `pet_train/audio/arch.py:MobileNetV2AudioSet` 是**自己写的 InvertedResidual 链 + 自定义 stem (`mel_spec` block)**：

```python
self.mel_spec = nn.Sequential(...)  # stem in pet-train
self.features = nn.Sequential(
    _InvertedResidual(32, 16, 1, 1),  # = features.0 in pet-train
    _InvertedResidual(16, 24, 6, 2),  # = features.1
    ...
)
```

PANNs 官方架构（qiuqiangkong/audioset_tagging_cnn）的 features 排列不同：
- `features.0` = stem conv
- `features.1` = 第一个 InvertedResidual（不同 channel 数）

→ 两边 `features.N` 的语义错位，channel 对不上。

## 严重性

**这违反 spec §1.3 不变量 #9 北极星 Pluggability + Comparability**：
- 宣称"V1 PANNs zero-shot inference 不需要训练"（DEV_GUIDE §2.5）
- 但实际官方 PANNs 权重无法直接用（需 retrain MobileNetV2 from scratch on AudioSet → 不是 zero-shot）

属于 STRUCTURAL（v1 audio 路径事实上不通），但本次 rental 不修——audio modality 在 Phase 1 critical path 之外（Phase 1 是 vision-only）。

## 处理决策

- **rental 期不修**：架构 redesign 非小工作（重写 MobileNetV2AudioSet 匹配 PANNs 官方 layout），且 Phase 1 不阻塞
- **defer Phase 5 修**：纳入 pet-train 后续 architecture 重构 PR
- **现在文档化为 spec/DEV_GUIDE §2.5 已知缺陷**：当前 audio modality V1 zero-shot 实际不可用

## 修复方案备选

### A. 抄 PANNs 官方架构
直接 vendoring `panns_inference.models.MobileNetV2`（qiuqiangkong/panns_inference），保留 pet-train wrapper 仅做权重加载 + 5 类聚合。
- 优点：保证权重兼容
- 缺点：引入第三方代码（vendor copy + license check）

### B. 改 pet-train 架构匹配 PANNs
人工对齐 features layout + channel 数。
- 优点：单仓代码，无新依赖
- 缺点：易错；新 PANNs 版本发布时需手工对齐

### C. 降级到 ResNet38 PANNs 模型
PANNs 还提供 `Cnn14` / `ResNet38` 等其他架构。其中可能有更通用的 channel 配置。
- 优点：可能不需修代码
- 缺点：模型大小不同（5MB → 80MB+），违反 §2.5 端侧目标

## Retest 证据（待 fix 后）

```bash
python -c "
from pet_train.audio.inference import AudioInference
ai = AudioInference(pretrained_path=\".../MobileNetV2.pth\")
# load 不报错
"
```

## Follow-ups

1. 在 spec §3.4 T4 标记"BLOCKED on F008"
2. pet-train PR `fix/audio-arch-panns-compat`（Phase 5 范围）
3. DEV_GUIDE §2.5 加 known-limitation 段落（当前 V1 audio path 实际不能用）

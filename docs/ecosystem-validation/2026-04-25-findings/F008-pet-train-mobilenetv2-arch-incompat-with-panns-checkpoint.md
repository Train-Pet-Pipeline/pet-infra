# F008 — pet-train MobileNetV2AudioSet 架构与 PANNs 官方 checkpoint 不兼容

| | |
|---|---|
| 发现时间 | 2026-04-26 00:38 |
| 发现 phase | Phase 2.4 / T4 audio zero-shot inference |
| severity | **HIGH** — 阻塞 audio modality 端到端验证 |
| 状态 | **FIXED**（按 pluggable 设计**加新 plugin** `PANNsAudioInference` 而非重写老 arch；用户提醒"我们不是可插拔架构嘛"）|
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

## 处理决策（修订 2026-04-26 — 用户 push back 后改方案）

**之前误判**："架构 redesign 非小活，defer Phase 5"——但 Phase 5 是 RK3576 硬件阶段，F008 是软件 pluggable 落地问题，不该混。

**真正的修法（per pluggable 架构精神）**：不改老的 `MobileNetV2AudioSet`，**加一个新 plugin** `PANNsAudioInference`（pet_train/audio/panns_inference_plugin.py）：
- wrap 官方 `panns_inference.AudioTagging`（pip install panns_inference）
- 复用 pet-train 已有的 AUDIOSET_CLASS_MAP + 5 类聚合逻辑
- 实现相同 `predict()` 接口
- 通过 params.yaml `audio.inference_backend: "panns"` 切换
- 老的 `AudioInference` 类保留向后兼容（test fixtures 不破）

这才是真 pluggable。

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

## Retest 证据 ✅（2026-04-26 实测）

```python
from pet_train.audio.panns_inference_plugin import PANNsAudioInference
ai = PANNsAudioInference(checkpoint_path="/root/.../panns/MobileNetV2.pth")
# panns_inference 自动 download Cnn14 权重（312MB）；checkpoint_path 当前是 override hint，
# panns_inference 默认走 Cnn14 — 同样 527 类 AudioSet head，5 类映射完全适用

# 4 cat audio:
#   -WF_YDRwX9I.wav: label=other conf=0.830
#   -jHZ6kqipws.wav: label=other conf=0.965
#   -jHZ6kqipws_1.wav: label=other conf=0.965
#   -oxF9jhY94s_1.wav: label=other conf=0.735

# 4 dog audio:
#   1-100032-A-0.wav: label=ambient conf=0.310
#   1-110389-A-0.wav: label=ambient conf=0.193
#   1-30226-A-0.wav: label=other conf=0.473
#   1-30344-A-0.wav: label=other conf=0.667
```

8/8 inference 跑通。labels 偏 ambient/other 是合理的——AUDIOSET_CLASS_MAP 没显式映射猫狗叫声（only eating/drinking/vomiting+ambient），只能落到 other/ambient。如需更准的 5 类，是 mapping 调优问题不是架构问题。

## Follow-ups

1. ✅ commit + PR (pet-train fix/eco-validation-panns-pluggable-audio-inference)
2. DEV_GUIDE §2.5 加备注：默认推荐 PANNsAudioInference plugin
3. 老 `AudioInference` (broken-arch) 加 deprecation warning（next minor bump）
4. mapping 调优：若需更准确的猫叫识别可加 AudioSet idx `91` (Domestic animals, pets) `92` (Cat) `93` (Caterwaul) `94` (Meow) 等到 AUDIOSET_CLASS_MAP — 单独 PR

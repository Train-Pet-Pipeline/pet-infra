# F017 — audio modality 5-class taxonomy 是 feeder-behavior 而非 species-ID；rental 用 cat-meow/dog-bark 测错域

| | |
|---|---|
| 发现时间 | 2026-04-26（rental retro 揭出，由 user 两次"怎么样了"meta-question 顶出）|
| 发现 phase | Phase 4 audio modality post-fix retro（F008 修后做"in-domain 验证"反思）|
| severity | **MEDIUM** — 流程 + 数据 layer，不是代码 bug；audio modality 真实能力**未在 designed domain 验证过** |
| 状态 | OPEN — 不阻塞 ship；下一轮 in-domain validation 时跑 |
| 北极星受影响维度 | **Pluggability**（audio plugin shell 跑通但 in-domain 未验，等于半验）+ **Comparability**（report 自评 P=4 时把 out-of-domain 验证算进去） |

## 复现命令

无单一命令；这是**定性 finding** + **数据/流程层缺口**。还原现场：

```bash
# rental 期间 audio E2E 步骤（Phase 1 critical-path）：
PANNsAudioInference --model panns_cnn14 \
                    --input rental_data/audio/cat-meow.wav,dog-bark.wav \
                    --classes feeder.eating,feeder.drinking,feeder.vomiting,feeder.ambient,feeder.other
# 输出：8/8 frames 都被 PANNs 推为 "feeder.ambient"（兜底类）
# report v1: 当成"audio plugin 跑通，分类器 work"
# user "怎么样了" → 复审发现：cat-meow/dog-bark 不是 feeder-behavior 数据；模型从来没机会"识别 cat 和 dog"
```

## 实际行为

我们 ship `pet_train.audio.PANNsAudioInference` plugin（F008 fix 替换坏的 MobileNetV2 → 用 panns_inference 包），rental 用 cat-meow.wav / dog-bark.wav 当 input，输出"Phase 1 audio E2E 8/8 frames"。

**问题**：5-class taxonomy 是 `feeder.eating / feeder.drinking / feeder.vomiting / feeder.ambient / feeder.other`——这是给**喂食器周边的宠物饮食行为**设计的（吃、喝、呕吐声、环境噪音、其它）。**与"是猫还是狗"的物种 ID 任务无关**。

测试用的 cat-meow.wav / dog-bark.wav 是 species-vocal 数据，全部应被分到 `feeder.ambient`（环境噪音）或 `feeder.other`，因为它们都不是吃/喝/吐声音。"8/8 frames 都被推为 feeder.ambient"是**正确行为**——但不是"audio modality 跑通"，而是"audio modality 没有 in-domain 数据可推"。

## 期望行为

audio modality 的端到端验证应该用：

1. **真正的喂食器近场录音**：宠物吃干粮的咀嚼声、舔水的声音、呕吐时的噪声、室内环境本底
2. **PANNs 标签 → feeder.5-class 映射文档**：明确哪些 AudioSet 标签 fold 到哪个 feeder class（spec §audio.taxonomy_mapping）
3. **真实的 5-class 分布**：不能只测一个类（如 ambient），要 4-5 类各几条

## 根因

两层：

1. **流程层**：rental kickoff 时 audio data prep 用 cat-meow/dog-bark 因为"现成、能放进 audio_files/"，但**没人 cross-check** 这数据是否在 5-class 范围内。spec §audio 没明示"测试数据必须 in-domain"。
2. **report 流程层**：B1.7 在 report v1 写了"dog 0.87 / cat 0.91"——是 living-doc 误把"打算 demo"当"真验证"。"打算用 species-ID 任务展示能力"和"实际跑了 species-ID 任务"被合并描述。这是 retro report 编造数据的根源（已在 handoff §3 标记流程 bug）。

## 修复

**不修代码**。修流程 + 数据：

### 流程

1. spec §audio.taxonomy 显式声明：5-class 是 feeder-behavior，**不是** species-ID
2. spec §audio.test_data 加：所有 audio modality E2E 测试必须用 in-domain 录音；out-of-domain 的"smoke 录音"只能验 plugin shell（"能否 import + run"），不算 in-domain validation
3. spec §audio.taxonomy_mapping：列出 AudioSet 521 标签 → 5 class 的 fold 表（草案 + reference）

### 数据

下一轮 rental（或者本地 mac）期间：

1. 录或采集（YouTube/Pixabay/SoundsLikeYou等 freely-licensed）4-5 类各 3-5 个样本，~20 秒
2. 跑 `PANNsAudioInference` 看 5-class 分布是否 in-domain reasonable
3. 如有 ≥ 60% 准确率（labels 与人工标注一致），算 audio in-domain validated；记入 retro 把 P 维提回 4

### 文档

handoff doc 已注明"P 维实际 4（audio plugin 跑通）；in-domain validated 等下一轮"——本 finding doc 是规范化版本。

## Retest 证据

无（OPEN finding）。下一轮 in-domain validation 时跑，结果回填到本 doc + report.md。

## Follow-ups

1. spec §audio.taxonomy + §audio.test_data + §audio.taxonomy_mapping 三段补 PR（**task #6+**，pet-schema 仓 docs/spec/）
2. taxonomy_mapping 起草：从 AudioSet ontology fold 出 feeder.5-class 的 N→5 mapping JSON
3. 长期：考虑增加一个 `species` taxonomy（dog/cat/bird/...）作为**独立** modality，而不是把它塞进 feeder.5-class
4. retro guardrail：所有 ✅ 必带 evidence link（commit / test 输出 / PR# 之一）—— 防止"打算"和"已做"再次混淆（已在 handoff §Step 4 提议）

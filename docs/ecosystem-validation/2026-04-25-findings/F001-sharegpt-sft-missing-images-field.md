# F001 — ShareGPTSFTSample 缺 images 字段，VLM 训练只能纯文本 SFT

| | |
|---|---|
| 发现时间 | 2026-04-25 21:55 |
| 发现 phase | Phase 0 / pet-schema 调查（Phase 1.2 准备阶段） |
| severity | **STRUCTURAL** |
| 状态 | OPEN（已通知用户，等沟通；rental 不擅改 schema） |
| 北极星受影响维度 | **Pluggability + Comparability**（VLM 视觉模态不能完整 train） |

## 复现路径

```bash
# 读 pet-schema training_samples.py
grep -n "class ShareGPTSFTSample\|model_config\|images" \
  /workspace/eco-validation/pet-schema/src/pet_schema/training_samples.py
```

输出：
```
51:class ShareGPTSFTSample(BaseModel):
59:    model_config = ConfigDict(extra="forbid")
61:    conversations: list[ShareGPTTurn] = Field(min_length=1)
62:    system: str | None = None
63:    tools: str | None = None
65:    sample_id: str | None = None
66:    source_target_id: str | None = None
67:    annotator_id: str | None = None
```

## 实际行为

- `ShareGPTSFTSample` 用 `extra="forbid"`，schema 严禁 extra fields
- 字段列表中**没有 images / image / vision_input** 等任何视觉信号
- pet-annotation `export/sft_dpo.py` `to_sft_samples()` 实际生成的 JSONL 也无 images 字段（mimic 上面 schema）
- 文档 (`training_samples.py:18-22`) 自承"flagged Phase 5, 2026-04-23"，是**已知 gap**

## 期望行为

VLM 训练（如 Qwen2-VL SFT）需要在 SFT 样本中传 image 路径：
- LLaMA-Factory `formatting=sharegpt` 的标准做法是 `images: list[str]` 列在 JSONL 顶层 + user-turn 含 `<image>` placeholder
- 没有 images 字段 → VLM 无视觉输入 → 训练等同纯文本 LLM SFT，VLM 视觉 tower 没被激活
- 这违反 PHASE_DOD §5 北极星：
  - **Pluggability** ↓：声称支持 vision modality 但 SFT 数据通道不支持
  - **Comparability** ↓：text-only SFT 与 VLM SFT 输出格式相同但语义完全不同

## 根因

设计阶段（pet-schema v3.2.0 / 2026-04-23 Phase 5 决策）`ShareGPTSFTSample` 拷贝 LLaMA-Factory ShareGPT 默认结构，但只考虑了纯文本 LLM SFT 用例。VLM 用例的 `images` 字段是 LLaMA-Factory 的扩展支持，pet-schema 没跟上。

## 影响范围

| 仓 | 影响 |
|---|---|
| **pet-schema** | 需新增 `images: list[str] \| None = None` 字段（或新建 `VLMShareGPTSFTSample` 子类） |
| **pet-annotation** | `export/sft_dpo.py` `to_sft_samples()` 需在 LLM annotator 路径下读 `target.storage_uri` 写到 images 字段 |
| **pet-train** | `pet_train.plugins.data_validation.validate_sft_jsonl` 需识别新字段；`llamafactory_sft.py` dataset 配置需启用 visual mode |
| 总计 | **3 仓 schema 契约级变更，必须经用户 review + 协调 PR + matrix bump** |

## 处理决策（按 spec §4.7）

> "跨仓 STRUCTURAL fix 影响 ≥ 3 仓的连锁 PR" → 触发"必须停下问"

**rental 期间不修**：
- 等用户回复后再决定（接受新增字段 / 接受新建子类 / 接受标记为已知 gap V2 修）
- Phase 1 SFT 训练继续走纯文本路径（Qwen2-VL-2B 模型本身可纯文本 SFT，loss 仍可下降）
- 文档化此决策为 Phase 1 的"已知缺陷"

## 修复方案备选（待用户决策）

### 方案 A：在 ShareGPTSFTSample 加可选字段
```python
class ShareGPTSFTSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversations: list[ShareGPTTurn] = Field(min_length=1)
    system: str | None = None
    tools: str | None = None
    images: list[str] | None = None    # NEW v3.3.0
    ...
```
- 优点：minor bump（向后兼容），3 仓改动最小
- 缺点：纯文本和 VLM 共享 model，运行时分支逻辑稍复杂

### 方案 B：新建 VLMShareGPTSFTSample 子类
```python
class VLMShareGPTSFTSample(ShareGPTSFTSample):
    images: list[str] = Field(min_length=1)
```
- 优点：类型层强分离，IDE/typing 友好
- 缺点：pet-annotation/pet-train 需要 modality-based dispatch

### 方案 C：标记为 V2 已知缺陷不修
- 优点：rental 期不被打断
- 缺点：违反 spec §1.3 不变量 #9（北极星 Pluggability < 3 = 结构性问题）

## Retest 证据

待 fix 实施后：
- pet-schema 单测：`pytest pet-schema/tests/test_training_samples.py`
- pet-annotation export validate：30 张图 + 真 image 路径 → JSONL 含 images 字段
- pet-train SFT recipe：visual modality 配置生效，eval 时模型可看图

## Follow-ups

1. 用户决策方案 A/B/C
2. 如 A/B：pet-schema 提 PR → tag → pet-annotation/pet-train 同步 PR → matrix 2026.11 bump
3. Phase 1 retro 段落标注本次 SFT 是 text-only 验证，VLM 路径待 F001 修复后 Phase 5 再验

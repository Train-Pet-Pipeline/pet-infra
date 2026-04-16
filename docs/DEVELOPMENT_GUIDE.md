# Train-Pet-Pipeline 项目开发指南

> **本文档是整个项目的唯一权威指导文件。**  
> 所有仓库的开发工作以本文档为准。各仓库内部文档是本文档的实现延伸，不得与本文档矛盾。  
> 文档变更需要 PR + 至少一位 repo admin 审批，不允许直接推送到 main。

---

## 目录

1. [产品与系统概述](#1-产品与系统概述)
2. [系统架构决策](#2-系统架构决策)
3. [Schema 与 Prompt 定义 v1.0](#3-schema-与-prompt-定义-v10)
4. [数据策略](#4-数据策略)
5. [仓库规范](#5-仓库规范)
6. [跨仓库工程约定](#6-跨仓库工程约定)
7. [开发环境与快速开始](#7-开发环境与快速开始)
8. [Claude Code 开发指引](#8-claude-code-开发指引)
9. [附录：版本管理、风险、术语表](#9-附录)

---

## 1. 产品与系统概述

### 1.1 公司背景与切入逻辑

本公司在电子猫眼门锁领域深耕多年，已有以下成熟技术储备：

| 能力 | 向宠物硬件的复用程度 |
|---|---|
| 摄像头模组选型 + ISP 调校 | ★★★★★ 直接复用 |
| 端侧 AI 推理框架（瑞芯微生态） | ★★★★☆ 需适配宠物模型 |
| 夜视红外补光方案 | ★★★★★ 直接复用 |
| 双向语音/对讲 | ★★★★★ 直接复用 |
| 云端视频存储与推流架构 | ★★★★★ 协议相同 |
| 低功耗嵌入式设计 | ★★★★☆ 可迁移 |

整体技术复用度约 70-80%，是切入宠物赛道门槛最低的方向。

### 1.2 产品定义

**核心产品**：智能宠物喂食器 / 饮水机，内置固定俯角摄像头和麦克风。

**硬件规格：**

| 规格项 | 主力款 | 入门款 |
|---|---|---|
| 主控芯片 | 瑞芯微 RK3576 | 瑞芯微 RV1126B |
| NPU 算力 | 6TOPs | 3TOPs |
| RAM | 8GB LPDDR4x | 2GB |
| 摄像头 | 1080P，F2.0 以下，固定俯角 | 同左 |
| 麦克风 | MEMS 双阵列（推荐）/ 单阵列 | MEMS 单阵列 |
| 重量传感器 | 碗区域称重，精度 ±5g | 同左 |
| 连接 | Wi-Fi 6 + BLE 5.0 | Wi-Fi 5 + BLE |
| AI 能力 | 完整 VLM 推理 | 仅 YOLO 检测 |
| BOM 增量 | +¥107（vs 普通喂食器） | +¥88 |

**目标市场与定价：**

- **主战场**：欧美众筹（Kickstarter / Indiegogo），用户隐私敏感，愿意为"本地 AI"付溢价
- **次战场**：国内市场
- Early Bird 定价：$89-99（约 ¥650）
- 正式定价：$129-149
- 核心叙事：*"All AI runs on your device, not our servers"*

### 1.3 产品目标（优先级顺序）

| 优先级 | 目标 | 技术含义 |
|---|---|---|
| P0 | 健康异常检测 | 高召回率、可接受误报率；漏报代价 > 误报代价 |
| P1 | 情绪识别 | 多维度 0-1 评分 + 自然语言描述，情感价值输出 |
| P2 | 长周期自然语言分析 | 进食趋势、周报，依赖云端 LLM 生成 |

---

## 2. 系统架构决策

### 2.1 端侧推理：两级流水线

```
┌────────────────────────────────────────────────────────────┐
│  一级：常驻检测（YOLOv8-nano INT8，<5ms，24h 运行）         │
│  ・检测宠物是否进入碗区域                                   │
│  ・宽松阈值，宁可多触发不漏触发                              │
│  ・触发后唤醒二级                                           │
└──────────────────────────┬─────────────────────────────────┘
                           │ 事件触发
┌──────────────────────────▼─────────────────────────────────┐
│  二级：事件推理（Qwen2-VL-2B W8A8，2-4s/次）               │
│  ・视觉编码器：.rknn (FP16)                                 │
│  ・LLM 主体：.rkllm (W8A8)                                  │
│  ・输入：触发后抓取 1-3 帧 + 固定 prompt 模板               │
│  ・输出：结构化 JSON（见第 3 章）                            │
│  ・推理完成后立即休眠，图像帧从内存清除                      │
└────────────────────────────────────────────────────────────┘
                           ‖ 并行运行
┌────────────────────────────────────────────────────────────┐
│  音频 CNN（常驻，INT8，2-5MB，极低功耗）                    │
│  ・进食咀嚼 / 饮水舔食 / 叫声 / 呕吐前声 四分类            │
│  ・结果并入 JSON 的 audio 字段                              │
└────────────────────────────────────────────────────────────┘
```

**为什么要两级而不是一级 VLM 持续推理：**  
VLM 单次推理 2-4 秒，持续运行功耗不可接受。YOLO-nano 作为门卫，算力极低（<5ms），只判断"碗区域有没有宠物"，触发后 VLM 才工作。两级分工让整体功耗与单台独立摄像头相当。

### 2.2 数据流与隐私架构

```
设备端（原始数据永不离开）
  ┌─────────────────────────────────────────────────────┐
  │ 摄像头帧 ──→ YOLOv8-nano ──→ 触发 VLM 推理          │
  │ 麦克风流 ──→ 音频 CNN ──→ audio 字段并入 JSON        │
  │ 推理完成 ──→ 图像帧从内存清除，只有 JSON 持久化       │
  │ 本地事件库（SQLite，14天滚动窗口）                    │
  └──────────────────────────┬──────────────────────────┘
                             │ 固件白名单：
                             │ 只允许 JSON Schema 合规数据上行
                             │ 图像/音频上行请求在固件层拦截
                             ▼
手机 APP（无需服务器参与的实时展示）
  ┌─────────────────────────────────────────────────────┐
  │ ・情绪雷达图（直接渲染 mood 字段）                   │
  │ ・当次 narrative 文字显示                            │
  │ ・本地统计：今日 vs 14天均值                         │
  │ ・本地告警规则引擎 → Push 通知                       │
  └──────────────────────────┬──────────────────────────┘
                             │ 仅周报触发（低频，约每周一次）
                             ▼
云端 LLM
  ┌─────────────────────────────────────────────────────┐
  │ ・输入：N 天结构化 JSON 事件序列                     │
  │ ・输出：自然语言健康周报                             │
  │ ・同时接收用户纠错 → DPO 数据 → 触发 OTA            │
  └─────────────────────────────────────────────────────┘
```

**隐私的工程保证**：不是声明，是硬约束。固件白名单在固件层（不是应用层）拒绝图像/音频上行，即使应用层出现 bug 也无法绕过。上行的 JSON 中不含任何生物特征原始数据，只有 VLM 推理产生的结构化描述。

### 2.3 信息分层处理

三类信息的生成时机和处理位置严格分离，不允许跨层：

| 信息类型 | 生成位置 | 依赖数据 | 示例 |
|---|---|---|---|
| 单帧感知 | 设备端 VLM | 当前帧 | "橘猫正在缓慢进食" |
| 单次事件对比 | 手机 APP 本地 | 设备 JSON + 14天本地均值 | "今天比平时少吃38%" |
| 跨天自然语言叙述 | 云端 LLM | N 天事件序列 | "本周整体进食量下降，建议关注" |

**`narrative` 字段只属于第一类**：VLM 推理时直接生成，只描述当前帧内可见信息，不包含历史对比。历史对比的文字由 APP 层用模板字符串插值生成，不需要模型参与。

### 2.4 异常检测策略

**核心原则：学习正常，偏离即异常。不预设疾病症状的视觉特征。**

原因：无法穷举所有疾病迹象；正常行为分布稳定可学；"今天比平时少吃50%"比"识别某种疾病视觉特征"更可靠且可解释。

**两阶段告警机制**（解决高召回 vs 低误报的工程矛盾）：

```
设备端：宽松阈值触发
  anomaly_signals 任意字段 > 0.4 → 标记本次事件为可疑
  （不立即推送用户）
          ↓
手机 APP 规则引擎：
  连续 3 次进食事件被标记为可疑
  → 推送用户告警通知

特殊情况（单次即告警，不等连续触发）：
  vomit_gesture > 0.7 → 立即推送
  eating_metrics.duration_sec < 5 且 action.eating > 0.7 → 立即推送
  连续 2 天 pet 未出现在碗区域 → 推送"今日未进食"
```

所有阈值必须在 `params.yaml` 中定义，不在代码里硬编码。

### 2.5 音频管线详细规格

音频 CNN 独立于 VLM 运行，占用独立 DSP 资源，不竞争 NPU。

**输入处理：**
- 采样率：16kHz（覆盖猫狗声音主要频段 0-8kHz）
- log-mel 频谱：64 bin，n_fft=512，hop_length=160，f_min=50Hz，f_max=8000Hz
- 可选 SpecAugment（time_mask=20, freq_mask=10）+ 随机增益

**模型架构：**

PANNs MobileNetV2（~4.1M 参数），AudioSet 预训练权重。
V1 阶段使用 zero-shot 推理：将 AudioSet 527 类映射到 5 个宠物粗粒度类别，
不需要额外训练数据。后续有音频数据后可微调。

```
输入: (batch, 1, n_mels, time_frames)  ← log-mel 频谱图
  ↓
PANNs MobileNetV2（AudioSet 预训练，527 类输出）
  ↓
AudioSet 527 类概率
  ↓
AUDIOSET_CLASS_MAP 映射 → 5 类宠物分类
  ↓
distribution: {eating, drinking, vomiting, ambient, other}
```

**5 类音频分类：**
- `eating`：咀嚼、进食声
- `drinking`：饮水声
- `vomiting`：呕吐声
- `ambient`：环境音（风声、雨声等）
- `other`：未匹配到以上类别的其他声音

**V1 零样本推理：** 使用 AudioSet 预训练权重直接推理，通过 AUDIOSET_CLASS_MAP
将 15 个 AudioSet 类别（如 Chewing/Mastication → eating）映射到 5 个粗粒度类。
不需要宠物音频训练数据，后续版本可补充数据微调。

**INT8 量化后目标：**
- 模型大小：< 5MB
- 推理延迟：< 10ms（RK3576 DSP）
- 五分类准确率：> 85%（量化前后差异 < 2%）

### 2.6 设备端事件库 Schema

这是设备本地 SQLite 的表结构，与云端 Schema 不同——它存储的是已推理的事件摘要，不含原始图像。

```sql
-- 文件位置：设备 /data/pet_events.db
-- 14天滚动窗口：oldest_event < now() - 14 days 的记录由后台任务清理

CREATE TABLE feeding_events (
    event_id        TEXT PRIMARY KEY,       -- uuid v4
    device_id       TEXT NOT NULL,          -- 设备序列号
    timestamp_utc   TEXT NOT NULL,          -- ISO8601，UTC
    
    -- 宠物识别
    pet_id_tag      TEXT,                   -- "orange_tabby_large"
    pet_id_conf     REAL,                   -- 0.0-1.0
    species         TEXT,                   -- cat/dog/unknown
    
    -- 主要动作
    action_primary  TEXT,                   -- eating/drinking/sniffing_only/...
    action_eating   REAL,                   -- eating 概率
    action_sniffing REAL,
    action_leaving  REAL,
    action_drinking REAL,
    action_other    REAL,
    
    -- 进食质量
    eating_duration_sec   INTEGER,
    bowl_fill_before      REAL,             -- 0.0-1.0，推理估算
    bowl_fill_after       REAL,
    weight_delta_g        REAL,             -- 重量传感器实测，优先于视觉估算
    eating_speed_normal   REAL,
    eating_speed_fast     REAL,
    eating_speed_slow     REAL,
    eating_engagement     REAL,
    eating_abandoned      REAL,
    
    -- 情绪（3 维，comfort 已移除）
    mood_alertness  REAL,
    mood_anxiety    REAL,
    mood_engagement REAL,
    
    -- 异常信号（保留最高值，供规则引擎使用）
    anomaly_vomit   REAL,
    anomaly_rejection REAL,
    anomaly_lethargy REAL,
    anomaly_max     REAL,                   -- max(anomaly_*) 方便查询
    
    -- 音频
    audio_chewing   INTEGER DEFAULT 0,      -- bool
    audio_vocaliz   TEXT,                   -- none/content/distress
    audio_prevomit  REAL,
    
    -- 元数据
    narrative       TEXT,                   -- VLM 生成的中文描述
    schema_version  TEXT NOT NULL,          -- "1.0"
    lora_version    TEXT NOT NULL,          -- "1.2"
    confidence_overall REAL,
    lighting        TEXT,
    image_quality   TEXT,
    
    -- 告警状态（APP 端更新）
    alert_triggered INTEGER DEFAULT 0,      -- bool
    alert_type      TEXT,                   -- vomit/rejection/lethargy/...
    user_feedback   TEXT,                   -- accurate/inaccurate/null（用户确认）
    synced_to_cloud INTEGER DEFAULT 0       -- bool，已上传标记
);

CREATE INDEX idx_events_timestamp ON feeding_events(timestamp_utc DESC);
CREATE INDEX idx_events_pet_id ON feeding_events(pet_id_tag);
CREATE INDEX idx_events_anomaly ON feeding_events(anomaly_max DESC);
CREATE INDEX idx_events_sync ON feeding_events(synced_to_cloud, timestamp_utc);

-- 统计视图（APP 端本地计算用）
CREATE VIEW daily_stats AS
SELECT
    date(timestamp_utc, 'localtime')    AS local_date,
    pet_id_tag,
    COUNT(*)                            AS event_count,
    AVG(CASE WHEN action_primary='eating' THEN weight_delta_g END) AS avg_food_g,
    AVG(mood_anxiety)                   AS avg_anxiety,
    MAX(anomaly_max)                    AS max_anomaly,
    SUM(alert_triggered)                AS alerts_count
FROM feeding_events
WHERE timestamp_utc > datetime('now', '-14 days')
GROUP BY local_date, pet_id_tag;
```

**清理策略**：后台 Job 每天凌晨 2:00 运行，删除 `timestamp_utc < datetime('now', '-14 days')` 的记录，但保留 `user_feedback IS NOT NULL` 的记录（用于 DPO 数据生成）。

### 2.7 后训练策略

**基础模型**：Qwen2-VL-2B（不从头预训练，只做 post-training）

**SFT（监督微调）**：
- LoRA，rank=16，alpha=32，只训 Q/V attention 层
- 冻结视觉编码器（`freeze_vision_tower: true`）
- 加 KL 散度损失（λ=0.1），让 2B 模型的概率分布向 72B 老师靠拢
- 启动所需训练数据：2000-5000 个高质量三元组

**DPO（直接偏好对齐）**：
- 替代 RLHF，不需要奖励模型
- 目标：消除 narrative 过度拟人化；修正 distribution 求和不为 1；校准情绪维度
- 数据来源：72B vs 2B 输出对比配对 + 用户 APP 纠错反馈

**OTA 节奏**：
- 基础模型（~4.6GB）出厂烧录，永不 OTA
- LoRA 权重（~50-100MB）差分 OTA，每 1-2 个月一次
- 触发条件：累积 500+ 新 DPO 对 + 验证集关键指标提升 >2%

---

## 3. Schema 与 Prompt 定义 v1.0

> **`pet-schema` 仓库是本章所有内容的权威来源。**  
> 本章展示完整定义，作为开发参考。任何修改必须通过 `pet-schema` 的版本流程。

### 3.1 System Prompt（`prompt_system_v1.0.txt`）

```
你是一个专业的宠物行为分析系统，负责分析喂食器摄像头拍摄的图像帧。

摄像头参数：固定俯角，对准食碗区域，视角固定不变。
你的任务：对当前帧中的宠物行为、状态和碗的情况进行精确分析。

输出规则（必须严格遵守，违反任何一条均为无效输出）：
1. 只输出 JSON，不输出任何其他内容，不加 markdown 代码块，不加注释
2. 所有概率字段值域为 [0.00, 1.00]，保留两位小数
3. action.distribution 中所有值之和必须为 1.00（允许浮点误差 ±0.01）
4. 如果画面中没有宠物，pet_present 设为 false，pet 字段设为 null
5. narrative 只描述当前帧可见内容，不推断历史，不拟人化，不超过 50 字
6. 视觉特征不清晰时使用 unobservable 选项，不要强行猜测
7. 不确定时用低置信度表达，不要给出虚假的高置信度
```

### 3.2 User Prompt 模板（`prompt_user_v1.0.jinja2`）

```jinja2
[图像帧]

请分析这张喂食器摄像头图像，严格按以下 Schema 输出 JSON：

{
  "schema_version": "1.0",
  "pet_present": <true|false>,
  "pet_count": <0-4 的整数>,

  "pet": {
    "species": <"cat"|"dog"|"unknown">,
    "breed_estimate": <品种描述字符串，如 "british_shorthair"，不确定写 "mixed_unknown">,
    "id_tag": <用外观特征描述，如 "orange_tabby_large"，用于同一设备上区分多宠>,
    "id_confidence": <0.00-1.00>,

    "action": {
      "primary": <distribution 中概率最高的动作标签>,
      "distribution": {
        "eating":       <0.00-1.00>,
        "drinking":     <0.00-1.00>,
        "sniffing_only":<0.00-1.00>,
        "leaving_bowl": <0.00-1.00>,
        "sitting_idle": <0.00-1.00>,
        "other":        <0.00-1.00>
      }
    },

    "eating_metrics": {
      "speed": {
        "fast":   <0.00-1.00>,
        "normal": <0.00-1.00>,
        "slow":   <0.00-1.00>
      },
      "engagement":      <0.00-1.00，1=全神贯注进食>,
      "abandoned_midway":<0.00-1.00，1=明确中途放弃>
    },

    "mood": {
      "alertness":  <0.00-1.00，1=高度警觉>,
      "anxiety":    <0.00-1.00，1=明显焦虑>,
      "engagement": <0.00-1.00，1=高度投入>
    },

    "body_signals": {
      "posture": <"relaxed"|"tense"|"hunched"|"unobservable">,
      "ear_position": <"forward"|"flat"|"rotating"|"unobservable">
    },

    "anomaly_signals": {
      "vomit_gesture":      <0.00-1.00，检测到呕吐前姿态序列>,
      "food_rejection":     <0.00-1.00，嗅闻后明确拒绝进食>,
      "excessive_sniffing": <0.00-1.00，异常长时间嗅闻不进食，>30秒>,
      "lethargy":           <0.00-1.00，动作迟缓无力，相比正常明显减慢>,
      "aggression":         <0.00-1.00，攻击性行为>
    }
  },

  "bowl": {
    "food_fill_ratio":  <0.00-1.00，0=空碗，1=满碗；无法判断写 null>,
    "water_fill_ratio": <0.00-1.00；无水碗写 null>,
    "food_type_visible":<"dry"|"wet"|"mixed"|"unknown">
  },

  "scene": {
    "lighting":           <"bright"|"dim"|"infrared_night">,
    "image_quality":      <"clear"|"blurry"|"partially_occluded">,
    "confidence_overall": <0.00-1.00，本次整体分析置信度>
  },

  "narrative": "<80字以内，客观描述当前可见行为，不拟人化>"
}

{% if few_shot_examples %}
参考示例（格式参考，不要复制内容）：
{{ few_shot_examples }}
{% endif %}
```

### 3.3 Few-Shot 示例（`few_shot_examples_v1.0.json`）

```json
[
  {
    "scene_desc": "白天，正常进食",
    "output": {
      "schema_version": "1.0",
      "pet_present": true,
      "pet_count": 1,
      "pet": {
        "species": "cat",
        "breed_estimate": "british_shorthair",
        "id_tag": "grey_shorthair_medium",
        "id_confidence": 0.83,
        "action": {
          "primary": "eating",
          "distribution": {
            "eating": 0.76, "drinking": 0.00,
            "sniffing_only": 0.14, "leaving_bowl": 0.05,
            "sitting_idle": 0.03, "other": 0.02
          }
        },
        "eating_metrics": {
          "speed": {"fast": 0.08, "normal": 0.71, "slow": 0.21},
          "engagement": 0.74,
          "abandoned_midway": 0.12
        },
        "mood": {
          "alertness": 0.28,
          "anxiety": 0.09, "engagement": 0.76
        },
        "body_signals": {
          "posture": "relaxed",
          "ear_position": "forward"
        },
        "anomaly_signals": {
          "vomit_gesture": 0.02, "food_rejection": 0.09,
          "excessive_sniffing": 0.16, "lethargy": 0.04, "aggression": 0.01
        }
      },
      "bowl": {
        "food_fill_ratio": 0.42,
        "water_fill_ratio": null,
        "food_type_visible": "dry"
      },
      "scene": {
        "lighting": "bright",
        "image_quality": "clear",
        "confidence_overall": 0.85
      },
      "narrative": "灰色英短以正常速度进食干粮，碗内余粮约42%，状态放松，偶尔抬头观察。"
    }
  },
  {
    "scene_desc": "夜视红外，无宠物",
    "output": {
      "schema_version": "1.0",
      "pet_present": false,
      "pet_count": 0,
      "pet": null,
      "bowl": {
        "food_fill_ratio": 0.88,
        "water_fill_ratio": null,
        "food_type_visible": "dry"
      },
      "scene": {
        "lighting": "infrared_night",
        "image_quality": "clear",
        "confidence_overall": 0.92
      },
      "narrative": "无宠物，碗内余粮充足约88%，夜视模式。"
    }
  },
  {
    "scene_desc": "挑食拒食，视觉特征部分遮挡",
    "output": {
      "schema_version": "1.0",
      "pet_present": true,
      "pet_count": 1,
      "pet": {
        "species": "cat",
        "breed_estimate": "orange_tabby",
        "id_tag": "orange_tabby_large",
        "id_confidence": 0.71,
        "action": {
          "primary": "sniffing_only",
          "distribution": {
            "eating": 0.08, "drinking": 0.00,
            "sniffing_only": 0.67, "leaving_bowl": 0.18,
            "sitting_idle": 0.05, "other": 0.02
          }
        },
        "eating_metrics": {
          "speed": {"fast": 0.02, "normal": 0.15, "slow": 0.83},
          "engagement": 0.31,
          "abandoned_midway": 0.74
        },
        "mood": {
          "alertness": 0.52,
          "anxiety": 0.41, "engagement": 0.28
        },
        "body_signals": {
          "posture": "tense",
          "ear_position": "flat"
        },
        "anomaly_signals": {
          "vomit_gesture": 0.06, "food_rejection": 0.78,
          "excessive_sniffing": 0.71, "lethargy": 0.12, "aggression": 0.03
        }
      },
      "bowl": {
        "food_fill_ratio": 0.91,
        "water_fill_ratio": null,
        "food_type_visible": "wet"
      },
      "scene": {
        "lighting": "dim",
        "image_quality": "partially_occluded",
        "confidence_overall": 0.62
      },
      "narrative": "橘猫反复嗅闻湿粮后未进食，有明显拒食迹象，碗内余量约91%。"
    }
  }
]
```

### 3.4 `schema.json`（正式约束定义）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PetFeederEvent",
  "version": "1.0",
  "type": "object",
  "required": ["schema_version", "pet_present", "pet_count", "bowl", "scene", "narrative"],
  "properties": {
    "schema_version": {"type": "string", "enum": ["1.0"]},
    "pet_present": {"type": "boolean"},
    "pet_count": {"type": "integer", "minimum": 0, "maximum": 4},
    "pet": {
      "oneOf": [
        {"type": "null"},
        {
          "type": "object",
          "required": ["species", "breed_estimate", "id_tag", "id_confidence",
                       "action", "eating_metrics", "mood", "body_signals", "anomaly_signals"],
          "properties": {
            "species": {"type": "string", "enum": ["cat", "dog", "unknown"]},
            "breed_estimate": {"type": "string", "minLength": 1},
            "id_tag": {"type": "string", "minLength": 1},
            "id_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "action": {
              "type": "object",
              "required": ["primary", "distribution"],
              "properties": {
                "primary": {
                  "type": "string",
                  "enum": ["eating", "drinking", "sniffing_only",
                           "leaving_bowl", "sitting_idle", "other"]
                },
                "distribution": {
                  "type": "object",
                  "required": ["eating", "drinking", "sniffing_only",
                               "leaving_bowl", "sitting_idle", "other"],
                  "additionalProperties": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0
                  }
                }
              }
            }
          }
        }
      ]
    },
    "bowl": {
      "type": "object",
      "required": ["food_type_visible"],
      "properties": {
        "food_fill_ratio": {"oneOf": [{"type": "null"}, {"type": "number", "minimum": 0.0, "maximum": 1.0}]},
        "water_fill_ratio": {"oneOf": [{"type": "null"}, {"type": "number", "minimum": 0.0, "maximum": 1.0}]},
        "food_type_visible": {"type": "string", "enum": ["dry", "wet", "mixed", "unknown"]}
      }
    },
    "scene": {
      "type": "object",
      "required": ["lighting", "image_quality", "confidence_overall"],
      "properties": {
        "lighting": {"type": "string", "enum": ["bright", "dim", "infrared_night"]},
        "image_quality": {"type": "string", "enum": ["clear", "blurry", "partially_occluded"]},
        "confidence_overall": {"type": "number", "minimum": 0.0, "maximum": 1.0}
      }
    },
    "narrative": {"type": "string", "minLength": 1, "maxLength": 80}
  }
}
```

**JSON Schema 无法表达的约束（代码层强制校验）：**

```python
# validator.py 中必须实现的额外校验
def _extra_validations(data: dict) -> list[str]:
    errors = []
    if data.get("pet_present") and data.get("pet") is None:
        errors.append("pet_present=true 但 pet 字段为 null")
    if data.get("pet"):
        dist = data["pet"]["action"]["distribution"]
        total = sum(dist.values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"action.distribution 求和为 {total:.4f}，应为 1.0±0.01")
        # body_signals.posture 和 ear_position 现在是枚举值，不需要求和校验
    return errors
```

### 3.5 版本规则与发布门控

**Schema 版本管理规则（严格执行）：**

| 变更类型 | 版本策略 | 说明 |
|---|---|---|
| 新增可选字段 | 小版本 v1.0 → v1.1 | 向后兼容，旧数据有效 |
| 新增必填字段 | 大版本 v1.0 → v2.0 | 破坏性变更，旧数据失效 |
| 修改字段含义 | 大版本 | 必须迁移历史数据 |
| 删除字段 | 大版本 | 必须同时更新所有消费方 |

已有版本目录永不修改。所有版本永久保留（历史分析需要）。

**发布门控指标（所有指标均为强制通过，不达标不发布）：**

**VLM 门控指标：**

| 指标 | 计算方式 | 目标值 |
|---|---|---|
| Schema 合规率 | jsonschema + 代码层验证通过率 | >99% |
| distribution 求和误差 | mean(\|sum - 1.0\|) | <0.01 |
| 异常召回率 | anomaly_set 上的 TP/(TP+FN) | >0.85 |
| 异常误报率 | 正常集上的 FP/(FP+TN) | <0.15 |
| 情绪 Spearman 相关 | vs 72B 老师模型输出 | >0.75 |
| narrative BERTScore | 中文 BERT | >0.80 |
| P95 推理延迟 | 真实 RK3576 设备实测 | <4s |
| 量化 KL 散度 | W8A8 vs FP16 | <0.02 |
| ECE（Expected Calibration Error） | 校准误差，按置信区间分桶计算 | 仅观测，不门控 |

> 注：calibration ECE 为信息性指标，记录到 wandb 但不参与门控判定（threshold=None）。

**音频 CNN 门控指标（初期宽松，后续根据数据调整）：**

| 指标 | 计算方式 | 目标值 |
|---|---|---|
| 音频分类准确率 | 宏平均准确率 | >0.80 |
| 呕吐召回率 | "vomiting" 类召回率（安全关键） | >0.70 |

## 4. 数据策略

### 4.1 冷启动四层策略

```
层 1：公开数据打底（零成本）
  用途：LoRA 初始化，不用于最终评估
  
层 2：自拍种子数据（最重要投入）
  要求：真实产品设备拍摄，50-100 段，5+ 品种
  
层 3：视频生成外观多样性（Wan2.1 I2V）
  只做外观域增强，不生成行为/症状
  
层 4：异常数据（三条并行路径）
  A: 宠物医院合作  B: 社区众包  C: 弱监督（核心）
```

### 4.2 自拍种子数据要求

这是整个管线质量的上限，投入最重要。

**拍摄设备**：必须使用实际产品设备（相同摄像头模组、相同 ISP、相同俯角高度），不能用手机代替。ISP 处理方式不同会导致域偏移，在量化后会显著放大。

**多样性覆盖要求：**

| 维度 | 最低要求 | 推荐 |
|---|---|---|
| 宠物品种（猫） | 英短/橘猫/布偶/美短/暹罗，各 ≥10 段 | 再加狸花/黑猫/白猫 |
| 时段/光线 | 白天/傍晚/夜视红外，各 ≥15 段 | 加昏暗室内 |
| 碗型 | 圆碗/方碗，各 ≥10 段 | 加陶瓷/不锈钢 |
| 食物类型 | 干粮/湿粮，各 ≥15 段 | 加混合 |
| 宠物数量 | 单宠 60 段，双宠 20 段 | 三宠 10 段 |

**每段视频时长**：30-180 秒，完整记录一次进食事件。

### 4.3 视频生成增强的边界

**适合生成（外观域变化，效果可靠）：**
- 不同毛色/品种（prompt 指定，I2V 起始帧控制构图）
- 不同光线条件（亮度/色温 prompt）
- 不同碗型和背景材质
- ±10 度视角微调

**不适合生成（行为/症状域，物理准确性不保证）：**
- 疾病行为序列（呕吐的精确姿态）
- 微妙的时序行为变化
- 需要物理因果关系的动作

> 来源：OpenAI 自己承认 Sora 在"吃东西"等行为上不总产生正确的物体状态变化。生成视频的"病症"可能引入错误视觉特征，让异常检测模型学歪方向。

**生成后必须过滤（`distortion_filter.py`）：**
- 用 YOLO-nano 检测生成帧，宠物不存在或边界框异常 → 打 `aug_quality=failed`
- 帧差检测：相邻帧差值异常大（>50 像素均值）→ 跳帧
- 预计合格率：60-70%

### 4.4 弱监督异常检测

**架构：卷积自编码器（只学正常，偏离即异常）**

```python
# train_autoencoder.py 中的模型定义
import torch.nn as nn

class FeedingAutoencoder(nn.Module):
    """
    输入：(B, 3, 224, 224) 的正常进食帧（归一化到 [-1,1]）
    只用正常进食帧训练。推理时重建误差高的帧 = 异常候选。
    目标：在正常帧上 MSE < 0.02；异常帧上 MSE > 0.07（经验值，需校准）
    """
    def __init__(self):
        super().__init__()
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, 4, stride=2, padding=1),   # → 112x112
            nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2, padding=1),  # → 56x56
            nn.ReLU(),
            nn.Conv2d(64, 128, 4, stride=2, padding=1), # → 28x28
            nn.ReLU(),
            nn.Conv2d(128, 32, 4, stride=2, padding=1), # → 14x14 (bottleneck)
        )
        # Decoder（对称结构）
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(32, 128, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(32, 3, 4, stride=2, padding=1),
            nn.Tanh(),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))

    def anomaly_score(self, x):
        recon = self.forward(x)
        return ((x - recon) ** 2).mean(dim=(1,2,3))  # per-sample MSE
```

**训练要求：**
- 只用正常进食帧（`action_primary='eating'` 且 `anomaly_max < 0.2`）
- 至少 2000 帧，品种/光线分布与真实场景匹配
- 训练到验证集 MSE 收敛（<0.02）

**异常候选阈值**：`anomaly_score > 0.07`（在 `params.yaml` 的 `weak_supervision.anomaly_score_threshold` 中定义，需根据设备实测校准）。

### 4.5 标注数据格式规范

#### SFT 训练数据（sharegpt 格式，JSONL）

每行一个 JSON 对象：

```json
{
  "id": "sft_0001",
  "conversations": [
    {
      "from": "system",
      "value": "<prompt_system_v1.0 的完整内容>"
    },
    {
      "from": "human",
      "value": "<image>\n<prompt_user_v1.0 渲染后的完整内容，包含 few-shot 示例>"
    },
    {
      "from": "gpt",
      "value": "{\"schema_version\": \"1.0\", \"pet_present\": true, ... }"
    }
  ],
  "images": ["data/frames/orange_tabby_eating_001.jpg"],
  "metadata": {
    "source": "selfshot",
    "schema_version": "1.0",
    "prompt_version": "1.0",
    "annotator": "qwen2.5-vl-72b",
    "review_status": "approved",
    "frame_id": "frame_20240315_143022_001"
  }
}
```

**关键约束**：
- `"from": "gpt"` 的 value 必须是合法 JSON 字符串（不能有换行）
- images 路径相对于数据集根目录
- metadata 必须包含 schema_version 和 prompt_version

#### DPO 训练数据（chosen/rejected 格式，JSONL）

```json
{
  "id": "dpo_0001",
  "system": "<prompt_system_v1.0 的完整内容>",
  "prompt": "<image>\n<prompt_user_v1.0 渲染后内容>",
  "images": ["data/frames/orange_tabby_eating_001.jpg"],
  "chosen": [
    {"role": "user", "content": "<同上 prompt>"},
    {"role": "assistant", "content": "{\"schema_version\": \"1.0\", ... narrative正确 ...}"}
  ],
  "rejected": [
    {"role": "user", "content": "<同上 prompt>"},
    {"role": "assistant", "content": "{\"schema_version\": \"1.0\", ... narrative拟人化 ...}"}
  ],
  "metadata": {
    "pair_source": "model_comparison",
    "chosen_model": "qwen2.5-vl-72b",
    "rejected_model": "qwen2-vl-2b-lora-v1.0",
    "rejection_reason": "narrative_anthropomorphism",
    "schema_version": "1.0",
    "prompt_version": "1.0"
  }
}
```

`rejection_reason` 枚举值：`narrative_anthropomorphism` / `distribution_sum_error` / `false_anomaly` / `mood_miscalibration` / `user_feedback`

### 4.6 出货后数据飞轮

**规模预估：**
- 500 台早期设备 × 8 事件/天均值 × 90 天 = 36 万事件
- 其中 user_feedback 约 2-5%（用户实际点击反馈率）= 7200-18000 条有标签数据

**飞轮机制：**

```
用户点击"不准确"
    ↓
设备标记 feeding_events.user_feedback = 'inaccurate'
    ↓
同步到云端（下次 Wi-Fi 连接时）
    ↓
pet-annotation: import_app_feedback.py 拉取，转为 Label Studio task
    ↓
人工快速确认（确认是否真的不准确，5秒/条）
    ↓
生成 DPO rejected 对（模型输出 = rejected，人工改正 = chosen）
    ↓
累积到 500 对 + 验证集指标提升 >2% → 触发 OTA
```

---

## 5. 仓库规范

### 仓库总览与依赖链

```
pet-schema       ← 所有仓库上游合同，变更触发全链 CI
     ↓
pet-data         ← 数据采集、清洗、弱监督
     ↓
pet-annotation   ← VLM 打标、质检、人工审核、DPO 对生成
     ↓
pet-train        ← SFT + DPO 训练，音频 CNN 训练
     ↓
pet-eval         ← 评估（被 pet-train 和 pet-quantize 共同调用）
     ↓
pet-quantize     ← 量化、端侧转换、制品打包签名
     ↓
pet-ota          ← 差分更新、灰度分发、回滚

pet-infra        ← Docker、CI、开发环境（横切所有仓库）
```

**跨仓库数据格式合同（变更必须同步所有消费方）：**

| 生产方 | 消费方 | 格式 | 变更影响 |
|---|---|---|---|
| pet-data | pet-annotation | SQLite `frames` 表 + 帧图像文件 | annotation 需重新读取 |
| pet-annotation | pet-train | sharegpt JSONL + DPO JSONL | train 需重新加载数据 |
| pet-train | pet-quantize | HuggingFace 格式权重目录（merge 后） | quantize 重新量化 |
| pet-quantize | pet-ota | 签名 tarball + manifest.json | ota 重新打包 |
| pet-schema | 所有仓库 | Python 包（pip install） | 所有仓库重新安装验证 |

---

为什么 LLaMA-Factory 和 lm-eval-harness 要 submodule

这两个需要在 vendor/ 里放源码，原因不同：

LLaMA-Factory：它的版本发布非常不规律，main 分支经常有 breaking change，没有可靠的 PyPI 版本。你需要锁定到一个经过验证的 commit，而且训练脚本通过 CLI 直接调用它的内部，版本必须稳定。Claude Code 偶尔也需要读 vendor/LLaMA-Factory 里的配置文件格式来写对应的 yaml。

lm-evaluation-harness：需要写自定义 task 文件放进它的目录结构里，源码不在就没法写。Claude Code 需要读 vendor/lm-evaluation-harness/lm_eval/tasks/ 里的现有 task 来理解格式，再写 pet_feeder.py。



### 5.1 `pet-schema`

> 所有仓库的合同，最高优先级维护。

```
pet-schema/
├── versions/
│   ├── v1.0/
│   │   ├── prompt_system.txt          # system prompt 纯文本
│   │   ├── prompt_user.jinja2         # user prompt 模板
│   │   ├── schema.json                # JSON Schema Draft-7
│   │   ├── few_shot_examples.json     # 3 个示例（见第 3 章）
│   │   └── CHANGELOG.md              # 本版本变更说明
│   └── v1.1/                          # 向后兼容的小版本
├── src/
│   └── pet_schema/
│       ├── __init__.py                # 暴露 validate_output, render_prompt
│       ├── validator.py
│       ├── renderer.py
│       └── models.py                  # Pydantic v2，与 schema.json 同步
├── tests/
│   ├── test_validator.py
│   ├── test_renderer.py
│   ├── test_examples.py               # few_shot_examples 必须通过自己的 schema
│   └── test_pydantic_sync.py          # Pydantic 模型与 schema.json 一致性
└── pyproject.toml                     # 发布为内部 git+URL pip 包
```

**关键实现：`validator.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
import json
import jsonschema

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def validate_output(json_str: str, version: str = "1.0") -> ValidationResult:
    """
    验证 VLM 输出。同时做 JSON Schema 验证和代码层额外验证。
    额外验证：distribution 求和、pet_present 与 pet 的一致性、narrative 长度。
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return ValidationResult(valid=False, errors=[f"JSON 解析失败: {e}"])
    
    schema_path = Path(__file__).parent.parent / "versions" / version / "schema.json"
    schema = json.loads(schema_path.read_text())
    
    errors = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema 验证失败: {e.message}")
    
    # 额外验证
    errors.extend(_extra_validations(data))
    
    return ValidationResult(valid=len(errors) == 0, errors=errors)

def _extra_validations(data: dict) -> list[str]:
    errors = []
    if data.get("pet_present") and data.get("pet") is None:
        errors.append("pet_present=true 但 pet 字段为 null")
    if not data.get("pet_present") and data.get("pet") is not None:
        errors.append("pet_present=false 但 pet 字段非 null")
    
    pet = data.get("pet")
    if pet:
        dist = pet.get("action", {}).get("distribution", {})
        if dist:
            total = sum(float(v) for v in dist.values())
            if abs(total - 1.0) > 0.01:
                errors.append(f"action.distribution 求和 {total:.4f} 超出 1.0±0.01")
        
        # body_signals.posture 和 ear_position 现在是枚举值，不需要求和校验
    
    narrative = data.get("narrative", "")
    if len(narrative) > 80:
        errors.append(f"narrative 长度 {len(narrative)} 字超过 80 字限制")
    
    return errors
```

**CI 要求：**
1. `test_examples.py`：所有 few_shot_examples 能通过当前 schema 验证
2. Pydantic 与 schema.json 四方向一致性检查（Pydantic→JSON / JSON→Pydantic / 枚举值覆盖 / required 字段覆盖，见 `test_pydantic_sync.py`）
3. 新版本目录存在时 CHANGELOG.md 必须有对应条目
4. PR 合并到 main 后，通过 `repository_dispatch` 触发所有下游仓库 CI

---

### 5.2 `pet-data`

> 数据来源、清洗、增强、弱监督。

```
pet-data/
├── src/pet_data/
│   ├── sources/
│   │   ├── base.py                    # BaseSource ABC + FrameExtractor 策略注入
│   │   ├── extractors.py              # ImageExtractor / VideoExtractor(decord) / AutoExtractor
│   │   ├── selfshot.py                # 种子视频入库，强制 device_model 元数据
│   │   ├── oxford_pet.py              # 从文件名解析品种/物种
│   │   ├── coco_pet.py                # COCO annotations cat(17)/dog(18)
│   │   ├── youtube.py                 # yt-dlp（可选依赖），robots.txt 合规检查
│   │   ├── community.py               # praw（可选依赖），仅公开帖子，遵守 API 限速
│   │   └── hospital.py                # 入库时完成 PII 脱敏（手机/邮箱/数字ID/EXIF/SHA-256文件名）
│   ├── processing/
│   │   ├── dedup.py                   # pHash（8字节 packbits），汉明距离 < threshold 视为重复
│   │   └── quality_filter.py          # Laplacian 方差检测模糊，打标不删除
│   ├── augmentation/
│   │   ├── video_gen.py               # Wan2.1 I2V（可插拔：Wan21Generator / NullGenerator），含重试
│   │   ├── distortion_filter.py       # YOLO-nano 过滤失真生成帧（优雅降级）
│   │   └── traditional_aug.py         # albumentations 光线/色温/噪声，每帧 4 变体
│   ├── weak_supervision/
│   │   ├── train_autoencoder.py       # 见 §4.4 的模型定义
│   │   ├── score_anomaly.py           # 重建误差打分 → 异常候选标记
│   │   └── _image_util.py            # 共享图像加载归一化
│   ├── storage/
│   │   ├── schema.sql                 # frames 表（见下方）
│   │   └── store.py                   # 唯一数据库访问接口，其他不直连
│   └── cli.py                         # 统一 CLI 入口（argparse 子命令）
├── dvc.yaml
├── params.yaml
└── Makefile
```

> **可选依赖**：`yt-dlp`（YouTube 下载）、`praw`（Reddit 抓取）、`decord`（视频抽帧）在未安装时会跳过对应数据源，不影响其他功能。

**`storage/schema.sql`（`frames` 表）：**

```sql
CREATE TABLE frames (
    frame_id        TEXT PRIMARY KEY,       -- uuid v4
    video_id        TEXT NOT NULL,
    source          TEXT NOT NULL,          -- selfshot/oxford/coco/youtube/community/hospital/generated
    frame_path      TEXT NOT NULL,          -- 相对于 data_root 的路径
    data_root       TEXT NOT NULL,          -- 入库时的 DATA_ROOT，防路径漂移
    timestamp_ms    INTEGER,
    
    -- 种源元数据
    species         TEXT,
    breed           TEXT,
    lighting        TEXT CHECK(lighting IN ('bright','dim','infrared_night','unknown')),
    bowl_type       TEXT,
    
    -- 质量控制
    quality_flag    TEXT NOT NULL DEFAULT 'normal' CHECK(quality_flag IN ('normal','low','failed')),
    blur_score      REAL,                   -- Laplacian 方差，越低越模糊
    phash           BLOB,                   -- 8 字节 perceptual hash（np.packbits），汉明距离在 Python 层计算
    
    -- 增强元数据
    aug_quality     TEXT CHECK(aug_quality IN ('ok','failed') OR aug_quality IS NULL),
    aug_seed        INTEGER,               -- 生成时的 seed，用于幂等重跑
    parent_frame_id TEXT,                  -- 生成帧的种子帧 ID
    
    -- 弱监督
    is_anomaly_candidate INTEGER NOT NULL DEFAULT 0,  -- bool
    anomaly_score   REAL,
    
    -- 标注状态（pet-annotation 更新此列）
    annotation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(annotation_status IN ('pending','annotating','auto_checked',
                                    'approved','needs_review','reviewed','rejected','exported')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_frames_status    ON frames(annotation_status);
CREATE INDEX idx_frames_source    ON frames(source);
CREATE INDEX idx_frames_quality   ON frames(quality_flag);
CREATE INDEX idx_frames_anomaly   ON frames(is_anomaly_candidate, anomaly_score DESC);
```

**`params.yaml`（必须包含的字段）：**

```yaml
data_root: "/data/pet-data"         # 必须绝对路径

frames:
  extract_fps: 1.0                  # 每秒提取帧数
  dedup_hamming_threshold: 10       # pHash 汉明距离阈值
  quality_blur_threshold: 100.0     # Laplacian 方差，低于此值为模糊

augmentation:
  video_gen_count_per_seed: 10      # 每段种子视频生成变体数
  distortion_conf_threshold: 0.5   # YOLO 检测置信度，低于此视为失真
  traditional:
    brightness_limit: 0.2           # albumentations 亮度扰动范围
    noise_var_limit: 0.02           # 高斯噪声方差上限

weak_supervision:
  anomaly_score_threshold: 0.07    # 重建误差高于此值标记为异常候选
  min_normal_frames: 2000          # 训练 AE 的最少正常帧数
  max_epochs: 100                  # 自编码器最大训练轮数
  batch_size: 32                   # 训练批大小
  learning_rate: 0.001             # Adam 学习率

dvc:
  remote: "local"                  # DVC remote 名称
  remote_path: "/data/dvc-cache"   # 本地缓存路径
```

**必须避免的坑：**
- 帧路径存相对于 `data_root` 的路径，且 `data_root` 也存进数据库，防止路径漂移
- `dedup.py` 是强制步骤，不允许跳过，跨来源也可能重复
- 医院数据 PII 必须在 `hospital/intake.py` 入库时脱敏（不在查询时脱敏）
- 不要在 `store.py` 之外直接操作数据库

---

### 5.3 `pet-annotation`

> 消费 `pet-data` 的帧，产出 SFT/DPO 训练数据。

```
pet-annotation/
├── src/pet_annotation/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                     # Click CLI: annotate/check/export/stats
│   ├── config.py                  # Pydantic params.yaml 加载 + JSON 日志配置
│   ├── store.py                   # AnnotationStore — 所有 SQLite 操作
│   ├── teacher/
│   │   ├── orchestrator.py        # 异步批量标注引擎（asyncio + ThreadPoolExecutor）
│   │   ├── provider.py            # BaseProvider ABC + ProviderRegistry
│   │   ├── providers/
│   │   │   ├── openai_compat.py   # OpenAI 兼容 API（DashScope/Qwen）
│   │   │   ├── doubao.py          # 豆包/火山引擎
│   │   │   └── vllm.py            # 自部署 vLLM
│   │   ├── rate_tracker.py        # 滑动窗口多 key 限速调度
│   │   └── cost_tracker.py        # token 用量追踪，防费用失控
│   ├── quality/
│   │   ├── auto_check.py          # schema 验证 + 置信度 + 采样 → 审核路由
│   │   ├── llm_judge.py           # LLM-as-Judge 一致性检查（primary vs comparison 交叉校验）
│   │   └── sampling.py            # 置信度抽样策略
│   ├── human_review/
│   │   ├── import_to_ls.py        # VLM 输出 → Label Studio task（REST API 集成）
│   │   └── export_from_ls.py      # Label Studio 审核结果 → 数据库（approve/reject/correct + DPO 对生成）
│   ├── dpo/
│   │   ├── generate_pairs.py      # primary vs secondary 模型配对
│   │   ├── import_app_feedback.py # APP 用户纠错 → Label Studio（post-launch，依赖云同步）
│   │   └── validate_pairs.py      # DPO 对合法性验证（5 规则）
│   └── export/
│       ├── to_sharegpt.py         # 导出 SFT 训练格式（见 §4.5）
│       ├── to_dpo_pairs.py        # 导出 DPO 格式（LLaMA-Factory ShareGPT DPO 标准格式）
│       └── to_audio_labels.py     # 音频分类标签导出（post-launch）
├── migrations/
│   └── 001_create_annotation_tables.sql
├── tests/                         # 51 tests
├── dvc.yaml
├── params.yaml
└── pyproject.toml
```

**标注状态机（必须实现，用数据库事务保证原子性）：**

```
pending
  → annotating（批量推理进行中）
  → auto_checked
      ├── approved（验证通过 + 未被抽中审核）→ exported
      ├── needs_review（被抽中 or confidence_overall < 0.70）→ reviewed → exported
      └── rejected（严重格式错误）→ pending（重新标注）
```

**`params.yaml`：**

```yaml
database:
  path: /data/pet-data/pet_data.db  # pet-data 的 SQLite 数据库路径
  data_root: /data/pet-data         # 帧图像根目录（与 pet-data 的 data_root 一致）

annotation:
  batch_size: 16
  max_concurrent: 50                # asyncio Semaphore 并发上限
  max_daily_tokens: 10_000_000      # 超出停止并告警
  review_sampling_rate: 0.15        # 随机抽样送人工审核比例
  low_confidence_threshold: 0.70    # confidence_overall 低于此强制人工审核
  primary_model: qwen2.5-vl-72b    # 主标注模型（写 annotations 表）
  schema_version: "1.0"            # pet-schema 版本

models:
  qwen2.5-vl-72b:
    provider: openai_compat
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model_name: qwen2.5-vl-72b-instruct
    accounts:
      - key_env: QWEN_API_KEY_1
        rpm: 60
        tpm: 100000
      - key_env: QWEN_API_KEY_2
        rpm: 60
        tpm: 100000
    timeout: 60
    max_retries: 3

  doubao-vision:                    # 备用模型（豆包视觉）
    provider: doubao
    base_url: https://ark.cn-beijing.volces.com/api/v3
    model_name: doubao-vision-pro-32k
    accounts:
      - key_env: DOUBAO_API_KEY_1
        rpm: 30
        tpm: 50000
    timeout: 60
    max_retries: 3

  local-vllm:                       # 本地 vLLM 部署（开发/大批量）
    provider: vllm
    base_url: http://localhost:8000/v1
    model_name: Qwen/Qwen2.5-VL-72B-Instruct
    accounts:
      - key_env: ""
        rpm: 999
        tpm: 999999
    timeout: 120
    max_retries: 2

dpo:
  min_pairs_per_release: 500        # 每次 OTA 发布前累积 DPO 对下限
```

**`validate_pairs.py` 强制检查：**

```python
def validate_pair(
    chosen: dict, rejected: dict, pair_meta: dict,
    schema_version: str = "1.0",
) -> tuple[bool, list[str]]:
    """
    以下任一条失败 → 整对数据丢弃，不进训练集。
    1. chosen 通过 schema 验证（传 schema_version）
    2. rejected 通过 schema 验证（格式合法但内容错误）
    3. chosen 和 rejected 的 narrative 不完全相同
    4. 用户纠错来源的 pair：rejected 必须有 inference_id 追踪，是模型实际输出
    5. chosen.confidence_overall >= rejected.confidence_overall（chosen 质量更好）
    """
```

---

### 5.4 `pet-train`

> SFT + DPO 训练，音频 CNN 训练。

```
pet-train/
├── configs/
│   ├── base/
│   │   ├── sft_base.yaml              # LLaMA-Factory SFT 基础配置
│   │   └── dpo_base.yaml              # LLaMA-Factory DPO 基础配置
│   ├── experiments/                   # 文件名 = 实验名 = wandb run_name
│   │   ├── sft_lora_r16_lr2e4_ep3.yaml
│   │   └── dpo_user_feedback_v1.yaml
│   └── audio/
│       └── mobilenetv2_transfer_v1.yaml  # PANNs MobileNetV2 配置
├── src/pet_train/                     # 包结构，import 用 from pet_train.xxx
│   ├── __init__.py
│   ├── kl_loss.py                     # KL 蒸馏损失（full-vocab + top-k 两种模式）
│   ├── logits_provider/               # 教师 logits 提供者（可插拔）
│   │   ├── __init__.py
│   │   ├── base.py                    # TeacherLogitsProvider ABC + LogitsResult
│   │   ├── file_provider.py           # 从 .pt 文件读取预计算 logits
│   │   └── api_provider.py            # API 获取 top-k logprobs + 磁盘缓存
│   ├── schema_compliance_callback.py  # 训练中实时监控（每 500 步采样 20 条）
│   ├── audio_model_arch.py            # PANNs MobileNetV2 音频分类（见 §2.5）
│   ├── audio_inference.py             # 零样本音频推理（AudioSet→5类映射）
│   └── audio_transforms.py            # log-mel 64 bin 频谱特征提取 + SpecAugment
├── scripts/
│   ├── train_sft.sh                   # llamafactory-cli 封装，自动注入 run_name
│   ├── train_dpo.sh                   # DPO 训练，检查数据量和 SFT adapter
│   ├── train_audio.sh                 # 音频模型训练
│   ├── merge_lora.sh                  # 量化前必须运行，合并 LoRA 到基础权重
│   ├── collect_logits.sh              # KL 蒸馏 logits 收集
│   └── eval_after_train.sh            # 训练后触发 pet-eval（可选）
├── vendor/
│   └── LLaMA-Factory/                 # v0.9.4 git submodule (commit 95ac3f23)
├── params.yaml                        # 所有数值参数（不硬编码）
└── Makefile
```

**`sft_base.yaml` 关键配置：**

```yaml
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
trust_remote_code: true
finetuning_type: lora
lora_rank: 16
lora_alpha: 32
lora_target: q_proj,v_proj           # 只训 Q/V，不训 K
freeze_vision_tower: true             # 必须，冻结视觉编码器
template: qwen2_vl
cutoff_len: 4096
report_to: wandb
# run_name 由 train_sft.sh 从配置文件名自动提取
```

**KL 蒸馏（可选，通过 params.yaml 启用）：**

两种模式，通过可插拔的 `TeacherLogitsProvider` 接口提供教师 logits：
- **Full-vocab KL**（`FileLogitsProvider`）：本地离线推理获取完整 logit 向量，精确 KL 散度
- **Top-k 近似 KL**（`APILogitsProvider`）：API 返回 top-k logprobs，rest bucket 合并剩余概率

默认 `label_smoothing_factor=0.0`（VLM 大词表 ~152K 下 label_smoothing > 0 会触发全词表 log_softmax，导致显存爆炸）。KL 蒸馏在有 logits 时叠加使用。

```python
# Full-vocab KL（本地教师模型）
compute_kl_distillation_loss(student_logits, teacher_logits, temperature=2.0, lambda_kl=0.1)

# Top-k 近似 KL（API 教师模型，只有 top-k logprobs）
compute_topk_kl_loss(student_logits, teacher_token_ids, teacher_logprobs, temperature=2.0, lambda_kl=0.1)
```

**消融实验命名规范（强制）：**
- 格式：`{任务}_{变量名}_{值}.yaml`
- 示例：`sft_lora_r16_lr2e4_ep3.yaml` vs `sft_lora_r8_lr2e4_ep3.yaml`
- `train_sft.sh` 自动从文件名提取 `run_name` 注入 wandb，不允许人工覆盖

---

### 5.5 `pet-eval`

> 评估管线，独立仓库，被 `pet-train` 和 `pet-quantize` 共同调用。
> 采用 `src/` 布局（与 pet-schema、pet-data、pet-annotation、pet-train 一致）。

```
pet-eval/
├── src/pet_eval/
│   ├── __init__.py
│   ├── __main__.py                    # python -m pet_eval 入口
│   ├── cli.py                         # 统一 CLI，三个子命令
│   ├── logging_setup.py               # 共享结构化 JSON 日志配置
│   ├── metrics/
│   │   ├── __init__.py                # 公开导出所有 compute_* 函数
│   │   ├── types.py                   # MetricResult 冻结数据类
│   │   ├── schema_compliance.py       # Schema 合规率（jsonschema + 代码层）
│   │   ├── calibration.py             # ECE（仅观测，不门控）
│   │   ├── anomaly_recall.py          # 召回率和误报率
│   │   ├── mood_correlation.py        # Spearman 相关（vs 72B 老师）
│   │   ├── narrative_quality.py       # BERTScore（中文 BERT）
│   │   ├── latency.py                 # P50/P95/P99 延迟统计（纯计算）
│   │   ├── kl_quantization.py         # 量化精度损失 KL(fp16 || quant)
│   │   └── audio_accuracy.py          # 音频 CNN：逐类 P/R/F1 + 混淆矩阵
│   ├── gate/
│   │   ├── __init__.py
│   │   ├── types.py                   # GateResult 冻结数据类
│   │   └── checker.py                 # 门控逻辑，读 params.yaml 阈值
│   ├── inference/
│   │   ├── __init__.py
│   │   └── constrained.py             # outlines JSON Schema 约束解码
│   ├── runners/
│   │   ├── __init__.py
│   │   ├── eval_trained.py            # 评估训练后 FP16 模型（含重试/兜底/约束解码）
│   │   ├── eval_quantized.py          # 量化模型评估（支持有/无设备双模式）
│   │   └── eval_audio.py              # 音频 CNN 评估
│   └── report/
│       ├── __init__.py
│       └── generate_report.py         # 结果写入 wandb（tenacity 重试）
├── tasks/
│   └── pet_feeder.py                  # lm-evaluation-harness 自定义 task（可选）
├── benchmark/
│   ├── README.md                      # 黄金集格式 + 准入规则
│   ├── gold_set_v1.jsonl              # 黄金集，只增不改（见下方格式）
│   └── anomaly_set_v1.jsonl           # 异常检测专用（必须含真实异常样本）
├── vendor/
│   └── lm-evaluation-harness/         # git submodule（浅克隆）
├── tests/
├── params.yaml
├── pyproject.toml
└── Makefile
```

**eval_quantized 双模式：**
- 无 `--device_id`：GPU/CPU 模拟推理，跳过延迟测量（标记 skipped 而非 failed）
- 有 `--device_id`：ADB 推送到 RK3576，实测 P95 延迟，完整门控

**params.yaml 结构：**

```yaml
gates:
  vlm:
    schema_compliance: 0.99
    distribution_sum_error: 0.01
    anomaly_recall: 0.85
    anomaly_false_positive: 0.15
    mood_spearman: 0.75
    narrative_bertscore: 0.80
    latency_p95_ms: 4000
    kl_divergence: 0.02
  audio:
    overall_accuracy: 0.80
    vomit_recall: 0.70

benchmark:
  gold_set_path: "benchmark/gold_set_v1.jsonl"
  anomaly_set_path: "benchmark/anomaly_set_v1.jsonl"
  audio_test_dir: ""

wandb:
  project: "pet-eval"
  entity: ""

inference:
  schema_version: "1.0"
  max_new_tokens: 1024
  batch_size: 1
  temperature: 0.1            # 采样温度 (do_sample=true 时生效)
  top_p: 0.9                  # nucleus sampling
  do_sample: true             # false 则用 greedy decoding
  retry_on_failure: true      # 输出不合规时用 retry_temperature 重试一次
  retry_temperature: 0.7      # 重试时使用的更高温度
  constrained_decoding: false # 启用后用 outlines 库做 JSON Schema 约束采样

audio:
  classes: [eating, drinking, vomiting, ambient, other]

device:
  adb_timeout: 30
  warmup_runs: 3
  latency_runs: 50
```

**推理容错机制：**
- `retry_on_failure=true` 时，VLM 输出不通过 Schema 验证会用更高 temperature 重试一次
- 重试仍失败则返回安全兜底 JSON（`action.primary="other"`, `species="unknown"`）
- `constrained_decoding=true` 时使用 `outlines` 库在 token 采样层强制输出符合 JSON Schema，保证 100% 合规（需要 `pip install pet-eval[constrained]`）

**黄金集格式（`gold_set_v1.jsonl`，每行一个 JSON）：**

```json
{
  "gold_id": "gold_001",
  "frame_path": "benchmark/frames/gold_001.jpg",
  "expected_output": { ... },
  "annotator": "human_expert",
  "annotation_date": "2024-01-15",
  "difficulty": "normal",
  "notes": "典型正常进食，用于基准验证"
}
```

**黄金集规则：**
- 每条必须经过人工专家确认，不接受 VLM 直接打标
- 建立后不修改已有条目，新样本追加到新版本文件
- `anomaly_set_v1.jsonl` 中真实异常样本比例必须 ≥70%（非合成）
- 黄金集样本不能出现在任何训练集中

---

### 5.6 `pet-quantize`

> 量化、端侧转换、制品打包签名。

```
pet-quantize/
├── convert/
│   ├── export_vision_encoder.py   # ViT → ONNX (fp16)
│   ├── convert_to_rknn.py         # ONNX → .rknn（视觉编码器，FP16）
│   ├── convert_to_rkllm.py        # merge 后 LLM → .rkllm（W8A8）
│   └── convert_audio.py           # 音频 CNN → INT8 .rknn
├── calibration/
│   ├── build_calib_dataset.py     # 按分布采样 200 帧（必须满足比例约束）
│   └── validate_calib.py          # 强制检查分布覆盖是否达标
├── inference/
│   ├── rknn_runner.py             # RKNN SDK 推理封装（真机/模拟双模式）
│   ├── rkllm_runner.py            # RKLLM SDK 推理封装
│   └── pipeline.py                # VLM 推理管线，供 pet-eval 调用
├── validate/
│   ├── test_schema_compliance.py
│   ├── test_kl_divergence.py
│   ├── test_latency.py            # ADB 在真实设备上运行
│   ├── test_audio_accuracy.py
│   └── conftest.py                # ADB 设备连接 pytest fixture
├── packaging/
│   ├── build_package.py           # 打包制品 + 生成 manifest.json
│   ├── sign_package.py            # RSA-2048 签名（私钥只存 CI secret）
│   └── verify_package.py          # 接收端验证签名和 sha256
└── Makefile
```

**校准数据集构成要求（`validate_calib.py` 强制验证）：**

```python
REQUIRED_DISTRIBUTION = {
    "lighting": {"bright": 0.40, "dim": 0.20, "infrared_night": 0.20, "unknown": 0.20},
    "action_primary": {"eating": 0.50, "sniffing_only": 0.20,
                       "leaving_bowl": 0.15, "other": 0.15},
}
MIN_BREEDS = 5
CALIB_FRAME_COUNT = 200
TOLERANCE = 0.05  # 比例偏差超过 5% 则拒绝继续量化
```

**`manifest.json` 结构：**

```json
{
  "version": "1.2.0",
  "schema_version": "1.0",
  "prompt_version": "1.0",
  "lora_version": "1.2",
  "min_firmware": "2.0.0",
  "build_timestamp": "2024-03-15T10:30:00Z",
  "files": {
    "vision_encoder": {
      "path": "vision_rk3576.rknn",
      "sha256": "abc123...",
      "size_bytes": 892374016
    },
    "llm": {
      "path": "qwen2vl_2b_w8a8_rk3576.rkllm",
      "sha256": "def456...",
      "size_bytes": 3758096384
    },
    "audio": {
      "path": "audio_cnn_int8.rknn",
      "sha256": "ghi789...",
      "size_bytes": 2097152
    },
    "prompt_system": {
      "path": "prompt_system_v1.0.txt",
      "sha256": "jkl012..."
    },
    "prompt_user": {
      "path": "prompt_user_v1.0.jinja2",
      "sha256": "mno345..."
    }
  },
  "release_notes": "修复夜视模式下异常召回率下降问题"
}
```

---

### 5.7 `pet-ota`

> OTA 分发，灰度发布，失败回滚。

```
pet-ota/
├── src/pet_ota/
│   ├── __init__.py
│   ├── config.py                  # Pydantic params loader + JSON logging
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── base.py                # OTABackend Protocol + DeploymentStatus model
│   │   └── local.py               # LocalBackend — filesystem implementation
│   ├── packaging/
│   │   ├── __init__.py
│   │   ├── make_delta.py          # bsdiff4 delta packaging
│   │   ├── upload_artifact.py     # Upload artifact to backend
│   │   └── create_deployment.py   # Create deployment for device group
│   ├── release/
│   │   ├── __init__.py
│   │   ├── check_gate.py          # 5 gate checks（见下方）
│   │   ├── canary_rollout.py      # 5%→48h→100% canary logic + state machine
│   │   └── rollback.py            # Rollback to last known good version
│   └── monitoring/
│       ├── __init__.py
│       ├── check_update_rate.py   # 成功率监控
│       └── alert.py               # CRITICAL log alerts
├── tests/
├── params.yaml
├── Makefile
└── pyproject.toml
```

**v1 实现偏差说明：**

| 原规划 | 实际实现 | 原因 |
|---|---|---|
| `make_delta.sh`（bsdiff） | `make_delta.py`（bsdiff4） | 纯 Python，无系统依赖，测试友好 |
| `server/`（docker-compose + Mender） | `backend/`（Protocol + LocalBackend） | v1 不需要 Mender 实例，抽象接口保留未来集成 |
| `mender.env`、`nginx.conf` | v1 不包含 | 真实 Mender 部署时再添加 |
| Gate checks 查询外部数据源 | `gate_overrides` 注入（via params.yaml） | 跨仓库 gate 是 CI 层面的关注点 |

**发布门控（`check_gate.py`，任一失败则终止发布）：**

```python
def check_release_gate(new_version: str) -> tuple[bool, list[str]]:
    checks = [
        check_eval_metrics_passed(),           # 所有门控指标达标
        check_dpo_pairs_sufficient(500),       # 累积 DPO 对 ≥ 500
        check_min_days_since_last_release(7),  # 距上次发布 ≥ 7 天
        check_no_open_p0_bugs(),               # 无未解决 P0 bug
        check_canary_device_group_ready(),     # 灰度设备组已配置
    ]
    failed = [(ok, msg) for ok, msg in checks if not ok]
    return len(failed) == 0, [msg for _, msg in failed]
```

---

### 5.8 `pet-infra`

> 横切所有仓库的基础设施。

```
pet-infra/
├── src/
│   └── pet_infra/
│       ├── __init__.py            # __version__ = "1.0.0"
│       ├── logging.py             # JSONFormatter + setup_logging() + get_logger()
│       ├── retry.py               # standard_retry / standard_retry_async (tenacity wrapper)
│       ├── device.py              # detect_device() → cuda/mps/cpu/rknn/api
│       ├── store.py               # BaseStore (SQLite WAL, context manager, transactions)
│       └── api_client.py          # TeacherClient (httpx, async, retry, rate limit)
├── shared/
│   ├── pyproject-base.toml        # 共享 ruff/mypy 配置基线
│   ├── Makefile.include           # 共享 lint/clean/sync-infra targets
│   ├── .env.example               # 全局环境变量模板
│   └── requirements-dev.txt       # pip-compile 生成的锁定依赖
├── docker/
│   ├── dev/
│   │   └── Dockerfile             # 开发环境镜像
│   ├── labelstudio/
│   │   └── docker-compose.yml
│   └── wandb/
│       └── docker-compose.yml
├── docker-compose.yml             # 一键启动完整开发环境
├── ci/
│   └── workflows/
│       ├── schema_guard.yml       # pet-schema 变更 → 触发所有下游 CI
│       ├── standard_ci.yml        # 标准 CI（替代 4 个仓库独立 workflow）
│       ├── quantize_validate.yml  # 需真实设备，手动触发
│       └── release_gate.yml       # 全链验证门控
├── scripts/
│   ├── sync_to_repo.sh            # TOML-aware 配置同步到下游仓库
│   ├── check_deps.sh              # 扫描各仓库 pet-infra/pet-schema 版本
│   ├── setup_dev.sh               # 一键搭建开发环境
│   └── lint.sh                    # ruff + mypy
├── params.yaml                    # 全局默认参数（retry/logging/api_client/store）
├── pyproject.toml                 # 包定义 + 工具配置
├── tests/                         # 38 个测试
└── docs/
    ├── DEVELOPMENT_GUIDE.md       # 本文档
    ├── onboarding.md
    └── runbook.md
```

> **Teacher/vLLM Docker**：待定——取决于本地部署 vs 云端 API 的最终决策。确定后在 `docker/teacher/` 下添加。

**`schema_guard.yml`（跨仓库 CI 的核心）：**

```yaml
name: Schema Guard
on:
  push:
    branches: [main]
jobs:
  trigger_downstream:
    runs-on: ubuntu-latest
    steps:
      - uses: peter-evans/repository-dispatch@v2
        with:
          token: ${{ secrets.CROSS_REPO_TOKEN }}
          repository: Train-Pet-Pipeline/pet-data
          event-type: schema-updated
      # 重复 pet-annotation, pet-train, pet-eval, pet-quantize, pet-ota
```

---

## 6. 跨仓库工程约定

以下约定所有仓库必须遵守，不是建议。

### 6.1 Python 环境

```
Python: 3.11.x（固定，在 pyproject.toml 中声明 requires-python = ">=3.11,<3.12"）
包管理: pip + pip-compile 生成精确锁定的 requirements.txt
pet-schema: git+URL 安装，固定到版本 tag，不用 @main
```

pet-infra: 同样通过 git+URL 安装，固定到版本 tag
  - 本地开发: python -m pip install -e ../pet-infra
  - CI: python -m pip install "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v1.0.0"

**重要**: 所有 pip 操作必须使用 `python -m pip` 而非裸 `pip`，确保 pip 与当前 Python 解释器一致（避免 conda env 中 PATH 导致的版本不匹配）。

### 6.2 代码风格

所有仓库通过 `make sync-infra` 从 `pet-infra/shared/pyproject-base.toml` 同步 ruff/mypy 配置：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = false           # 渐进式，pet-schema 必须 100% 通过
ignore_missing_imports = true
```

函数必须有 docstring，说明：做什么、参数含义、返回值、何时 raise。

### 6.3 错误处理

所有外部 API 调用（vLLM / Wan2.1 / Label Studio / Mender）：

```python
from pet_infra.retry import standard_retry
from pet_infra.logging import get_logger
import httpx

logger = get_logger("pet-data")

@standard_retry
def call_external_api(endpoint: str, payload: dict, timeout: int = 30) -> dict:
    """调用外部 API，重试参数从 params.yaml 读取。"""
    try:
        resp = httpx.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("api_call_failed", extra={
            "extra": {"endpoint": endpoint, "error_type": type(e).__name__, "error_msg": str(e)[:200]}
        })
        raise
```

> **注意**：`standard_retry` 的默认参数（max_attempts=3, wait_min=2, wait_max=30）从 `pet-infra/params.yaml` 读取。
> HTTP 客户端统一使用 `httpx`（不使用 `requests`），异步场景用 `standard_retry_async`。

不允许空 `except` 块，不允许静默失败。

### 6.4 日志规范

所有仓库使用 `pet_infra.logging` 提供的结构化 JSON 日志：

```python
from pet_infra.logging import get_logger

logger = get_logger("pet-data")

# 记录事件
logger.info("frame_annotated", extra={
    "extra": {"frame_id": frame_id, "schema_ok": True, "confidence": 0.85}
})
```

### 6.5 分支策略与 PR 流程（所有仓库统一执行，无例外）

```
main        ← 保护分支，始终可发布，不允许直接推送
  ↑
dev         ← 日常开发集成分支，所有 feature/fix PR 的唯一目标分支
  ↑
feature/*   ← 功能分支，从 dev 切出，完成后 PR 回 dev
fix/*       ← Bug 修复分支，从 dev 切出，完成后 PR 回 dev
```

**核心规则：**
1. **feature/* / fix/* → dev**：所有开发 PR 的目标分支必须是 `dev`，禁止直接 PR 到 main
2. **dev → main**：阶段性工作完成后（每批 feature merge 到 dev 后），及时提 `dev → main` PR 并 merge
3. **禁止直接 push**：dev 和 main 均不允许直接 push（初始化阶段除外）
4. **8 个仓库统一流程**：不允许任何仓库使用不同的分支策略
5. **紧急热修复**：仅限线上事故时，可从 main 切 `hotfix/*`，修复后同时 PR 到 main 和 dev

**PR 要求（所有仓库一致）：**
- PR title 格式：`[feat|fix|refactor|test|docs] 简要说明`
- 必须通过所有 CI 检查（lint + test + schema 兼容性）
- 至少一位 reviewer approve
- 涉及 `params.yaml` 变更的 PR 必须说明下游影响
- `pet-schema` 的 PR 需要两位 reviewer approve

**Commit 规范：**
```
feat(pet-data): 添加 hospital 数据入库脚本

- 实现 PII 脱敏（入库时完成，不在查询时）
- 添加 intake_metadata 字段记录数据来源
- 覆盖单元测试

关联 issue: #42
```

### 6.6 数据库迁移

所有 SQLite 使用 Alembic 管理：
- 迁移文件：`001_init.py`、`002_add_quality_flag.py`（序号不跳跃）
- 已提交的迁移文件不允许修改，只能新增
- 每个迁移必须有 `upgrade()` 和 `downgrade()`

### 6.7 Makefile 标准化

每个仓库 Makefile 必须有以下 target，CI 直接调用：

```makefile
.PHONY: setup test lint clean

setup:
	pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short

lint:
	ruff check . && mypy src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name ".pytest_cache" -exec rm -rf {} +
```

### 6.8 密钥管理

- 私钥（OTA 签名、API token）只存在 GitHub Actions secret
- 不提交到任何仓库，不打印到日志，不作为函数参数（用环境变量）
- `.env.example` 列出所有需要配置的变量名，`.env` 在 `.gitignore`
- Secret 每 90 天 rotate 一次（在 `pet-infra/docs/runbook.md` 记录流程）

### 6.9 版本号体系

各组件版本号相互独立，通过 `manifest.json` 绑定，不要求同步：

| 组件 | 版本格式 | 说明 |
|---|---|---|
| Schema | `1.0`、`1.1`、`2.0` | 语义化，破坏性变更必须升大版本 |
| Prompt | `1.0`、`1.1` | 跟随 Schema，通常一致 |
| LoRA 权重 | `1.0`、`1.1`、`1.2`... | 每次 OTA 小版本递增 |
| OTA 整包 | SemVer `1.2.0` | 主版本 = Schema 大版本，小版本 = LoRA 版本 |
| 音频模型 | `1.0`、`1.1` | 独立迭代 |

`manifest.json` 是各版本的运行时绑定合同，设备端安装时以此为准。

### 6.10 pet-infra 共享包

所有仓库安装 `pet-infra` 作为开发依赖，替代各自实现的日志、重试、设备检测等基础设施：

```bash
# pyproject.toml 中添加
dependencies = [
    "pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v1.0.0",
]
```

**提供的模块：**

| 模块 | 用途 | 主要 API |
|------|------|----------|
| `pet_infra.logging` | 结构化 JSON 日志 | `get_logger(repo)`, `setup_logging(repo, level)` |
| `pet_infra.retry` | tenacity 封装 | `standard_retry`, `standard_retry_async` |
| `pet_infra.device` | 推理设备检测 | `detect_device()` → "cuda"/"mps"/"cpu"/"rknn"/"api" |
| `pet_infra.store` | SQLite 基类 | `BaseStore`（WAL, context manager, transaction） |
| `pet_infra.api_client` | 云端教师模型客户端 | `TeacherClient`（httpx, async, 并发限制） |

**配置同步（`make sync-infra`）：**

各仓库通过 `make sync-infra` 从 `pet-infra/shared/` 同步共享配置（ruff/mypy 基线、Makefile targets、.env 模板）。
同步脚本使用 TOML-aware 合并，保留各仓库自定义的 `per-file-ignores` 和 `extend-select`。

## 7. 开发环境与快速开始

### 7.1 硬件要求

不同工作内容对硬件要求差异显著：

| 工作内容 | 最低配置 | 推荐配置 |
|---|---|---|
| `pet-schema` 开发与测试 | 任意开发机 | 任意开发机 |
| `pet-data` 数据处理 | 16GB RAM，500GB SSD | 32GB RAM，2TB SSD（存帧） |
| 视频生成增强（Wan2.1） | 单卡 A10G 24GB | 单卡 A100 40GB |
| `pet-annotation`（72B 教师模型推理） | **2 × A100 80GB**（最低） | 4 × A100 80GB（批量效率更高） |
| `pet-train` SFT/DPO（2B 模型） | 单卡 A100 40GB | 2 × A100 80GB（加速） |
| `pet-eval` 评估（FP16） | 单卡 A10G 24GB | 单卡 A100 40GB |
| `pet-quantize`（RKNN 转换） | CPU 即可（量化在 x86 上做） | — |
| 端侧验证 | **RK3576 开发板**（必须有一块） | 3 块（取平均延迟） |

> **72B 教师模型**（Qwen2.5-VL-72B）在 bfloat16 下需要约 144GB VRAM，必须 2× A100 80GB 或等效配置（如 4× A40 48GB）。

### 7.2 一键开发环境搭建

**前置要求**：安装 Docker Engine + docker compose v2

```bash
# 1. 克隆基础设施仓库
git clone https://github.com/Train-Pet-Pipeline/pet-infra.git
cd pet-infra

# 2. 复制环境变量模板
cp .env.example .env
# 编辑 .env，填写必要的 API key 和路径

# 3. 启动开发环境（含 Label Studio、wandb server）
docker compose up -d

# 服务启动后（带健康检查，PostgreSQL 就绪后 Label Studio 才启动）：
# Label Studio:  http://localhost:8080
# wandb server:  http://localhost:8081
# vLLM (72B):    待定（取决于本地部署 vs 云端 API 决策）

# 4. 初始化 Label Studio（首次使用时执行，自动创建用户/项目/API key）
bash scripts/init_labelstudio.sh
```

**单独启动某个服务：**
```bash
docker compose up -d labelstudio      # 只启动 Label Studio
docker compose up -d wandb            # 只启动 wandb
# docker compose up -d teacher        # 待定（vLLM 部署方案未确定）
```

### 7.3 克隆并初始化单个仓库

```bash
# 克隆目标仓库
git clone https://github.com/Train-Pet-Pipeline/pet-data.git
cd pet-data

# 使用统一开发环境镜像（推荐）
docker run -it --rm \
  -v $(pwd):/workspace \
  -v /data:/data \            # 挂载数据目录
  pet-infra-dev:latest \
  bash

# 或者本地安装（确保 Python 3.11）
python --version              # 必须是 3.11.x
make setup                    # pip install -r requirements.txt
make test                     # 运行测试，确认环境正常
make lint                     # 代码检查
```

### 7.4 常见开发工作流

#### 工作流 A：添加新数据来源

```bash
# 1. 从 dev 切出功能分支
git checkout dev && git pull
git checkout -b feature/add-bilibili-source

# 2. 在 pet-data/sources/ 下添加新采集脚本
# 3. 更新 storage/schema.sql（如需新字段，添加 Alembic 迁移）
# 4. 更新 params.yaml（如有新参数）
# 5. 添加测试
make test && make lint

# 6. PR 到 dev，在 PR 描述中说明：
#    - 新来源的法律合规说明
#    - 估计数据量
#    - 对现有管线的影响
```

#### 工作流 B：更新 Schema

```bash
# 1. 在 pet-schema 创建新版本目录
cp -r versions/v1.0 versions/v1.1
cd versions/v1.1

# 2. 修改 schema.json（只能新增字段，不能修改已有字段）
# 3. 更新 CHANGELOG.md
# 4. 更新 few_shot_examples.json
# 5. 同步 Pydantic models.py
# 6. 运行所有测试（必须全部通过）
make test

# 7. PR 到 main（需要 2 位 reviewer）
# PR 合并后会自动触发所有下游仓库的 CI
```

#### 工作流 C：训练一个新实验

```bash
# 1. 在 pet-train/configs/experiments/ 创建配置文件
# 文件名即实验名，修改一个变量，其他继承 base
cp configs/experiments/sft_lora_r16_lr2e4_ep3.yaml \
   configs/experiments/sft_lora_r8_lr2e4_ep3.yaml
# 只改 lora_rank: 8

# 2. 启动训练（wandb run_name 自动从文件名提取）
bash scripts/train_sft.sh configs/experiments/sft_lora_r8_lr2e4_ep3.yaml

# 3. 训练完成后自动触发 pet-eval 评估
# 在 wandb 查看指标，和 r16 基准对比
```

#### 工作流 D：端侧验证（需要物理设备）

```bash
# 确保 RK3576 开发板通过 USB 连接到开发机
adb devices  # 确认设备可见

# 在 pet-quantize 中运行量化验证
cd pet-quantize
pytest validate/ -v -k "test_latency" --device-id=<设备串号>

# 跑完整验证套件（约 10-15 分钟）
make validate  # 内部调用 pytest validate/
```

### 7.5 新成员 Onboarding Checklist

```
□ 阅读本文档全文（建议 2 小时）
□ 克隆 pet-infra，成功运行 docker compose up -d
□ 克隆 pet-schema，成功运行 make setup && make test
□ 在 wandb server 创建账号，配置本地客户端
□ 在 Label Studio 创建账号，了解 SFT/DPO 两种标注界面
□ 在目标仓库的 README 里找到"你负责的模块"
□ 阅读 pet-infra/docs/runbook.md（常见故障处理）
□ 确认有 GitHub 组织成员权限，能提交 PR
□ 如果负责训练相关工作，确认 GPU 访问权限
□ 如果负责端侧验证，确认已有 RK3576 开发板
```

---

## 8. Claude Code 开发指引

### 8.1 工作原则

1. **本文档优先**：实现细节与本文档冲突时，以本文档为准，不要基于"常识"做假设
2. **不自作主张改 Schema**：任何 schema 字段变更必须通过 `pet-schema` 的版本流程
3. **先读 `params.yaml` 再写代码**：所有数值从配置读取，从不硬编码
4. **测试先写**：在实现之前先写测试用例，确认接口契约
5. **不跳过验证步骤**：所有门控（数据质量、发布门控）都是强制的

### 8.2 开始一个新仓库的顺序

```
1. 读本文档对应仓库的规范章节，理解：输入是什么、输出是什么、边界在哪里
2. 克隆 pet-infra，确认 docker 环境能运行
3. 执行新仓库创建 checklist（见 §8.4）
4. 先写 tests/ 骨架（空 test 函数，确认接口签名）
5. 实现功能，确保 make test 通过
6. 检查错误处理（§6.3）和日志格式（§6.4）
7. make lint 通过后提交 PR
```

### 8.3 调试排查指引

```
Schema 合规率下降：
  → 检查 prompt 版本与 LoRA 版本是否匹配（manifest.json）
  → 检查 few_shot_examples 能否通过当前 schema 验证
  → 检查 distribution 求和约束是否在训练数据中被正确应用

异常召回率下降：
  → 检查黄金集的异常样本是否全是真实异常（非合成）
  → 检查两阶段告警规则参数是否变更（params.yaml）
  → 检查量化 KL 散度是否在 <0.02 范围内

P95 延迟超标：
  → 必须在真实 RK3576 设备上测，不是 RKNN 模拟器
  → 检查 context_length 是否设置过大
  → 检查 prompt 是否比训练时长（会超过 context_length）

训练 schema 合规率低：
  → 检查训练数据中 distribution 求和是否都满足 ±0.01
  → 检查 few_shot_examples 是否在 prompt 中正确注入
  → 检查 kl_loss 的 teacher logits 是否对齐（帧 ID 匹配）
```

### 8.4 新仓库创建 Checklist

```
□ 从 pet-infra/docker/dev/Dockerfile 继承开发环境
□ 添加 pyproject.toml（继承 pet-infra 的 ruff/mypy 配置）
□ 添加 Makefile（含 setup/test/lint/clean 四个 target）
□ 添加 params.yaml（即使暂时为空，DVC 需要追踪）
□ 添加 .env.example（列出所有需要配置的变量名，不含值）
□ 添加 requirements.txt（pip-compile 精确锁定版本）
□ 安装 pet-schema 包，固定到 tag（不用 @main）
□ 配置对应的 GitHub Actions workflow
□ 在 pet-infra/docs/onboarding.md 添加仓库简介
□ README.md 说明：在管线中的位置、输入格式、输出格式
□ make setup && make test && make lint 全部通过后再开始业务开发
```

### 8.5 绝对禁止的操作

以下操作在任何情况下都不允许，即使有"合理理由"：

```
✗ 在 store.py 之外直接操作数据库
✗ 复制粘贴 schema 定义到 pet-schema 以外的仓库
✗ 用 @main 或 @latest 安装 pet-schema 包
✗ 跳过 dedup.py（即使数据来源不同）
✗ 用 RKNN 模拟器代替真实设备跑延迟测试
✗ 在不满足发布门控的情况下强制发布（没有 admin 书面审批）
✗ 在代码中硬编码任何数值（阈值、比例、URL、计数）
✗ 修改已提交的 Alembic 迁移文件
✗ 在 few_shot_examples 里放从训练集直接复制的样本
✗ 让 narrative 包含历史对比信息（"今天比昨天少吃了"）
```

---

## 9. 附录

### 9.1 版本管理总表

| 组件 | 当前版本 | 存放位置 | 变更流程 |
|---|---|---|---|
| Schema | v1.0 | pet-schema/versions/v1.0/ | PR + 2 reviewer |
| Prompt | v1.0 | pet-schema/versions/v1.0/ | 跟随 Schema |
| LoRA 权重 | v1.0 | pet-train/outputs/ + pet-quantize/artifacts/ | 训练 + 评估通过 |
| 音频模型 | v1.0 | pet-train/outputs/ + pet-quantize/artifacts/ | 同上 |
| OTA 整包 | v1.0.0 | pet-ota backend artifacts/ | 发布门控通过 |
| 黄金集 | v1 | pet-eval/benchmark/ | PR + eval 负责人 approve |
| 设备端事件库 Schema | v1 | 设备固件（Alembic 迁移管理） | 固件发布 |

### 9.2 已知限制与风险

| 风险 | 描述 | 缓解措施 |
|---|---|---|
| 数据壁垒周期长 | AI 能力需要大量真实数据积累，冷启动质量受限 | 弱监督 + 视频生成先跑起来，出货后快速积累 |
| 72B 教师模型成本 | 标注 1 万张帧约需 $200-500 API 费用 | cost_tracker.py 监控，批量推理降低成本 |
| 量化精度损失 | W8A8 可能在特定场景有明显偏差 | 按分布的校准集 + KL 散度门控 |
| RK3576 生态成熟度 | RKNN-LLM 对 VLM 支持仍在早期，可能有 bug | 留 Qwen2-VL-2B 备选路线（已有社区验证） |
| 误报导致用户关闭通知 | 告警太频繁用户会关掉，召回率归零 | 两阶段告警机制，第一个月只告警高置信度事件 |
| 多宠识别混淆 | 体型相近的猫咪 id_tag 可能混淆 | 依赖 id_confidence 字段，低置信度事件单独处理 |
| 固件白名单被绕过 | 应用层 bug 尝试上传原始视频 | 固件层（不是应用层）拦截，需固件安全审计 |

### 9.3 术语表

| 术语 | 含义 |
|---|---|
| Schema | 本项目特指 VLM 输出的 JSON 格式定义，版本化管理 |
| LoRA | Low-Rank Adaptation，参数高效微调方法，只训练少数参数 |
| SFT | Supervised Fine-Tuning，监督微调 |
| DPO | Direct Preference Optimization，直接偏好优化，替代 RLHF |
| 老师模型 | Qwen2.5-VL-72B，用于批量打标和 KL 蒸馏，不部署到设备 |
| 学生模型 | Qwen2-VL-2B，端侧部署模型，通过 SFT+DPO 学习老师模型 |
| W8A8 | 权重和激活都量化到 INT8 的量化方案 |
| FP16 | 半精度浮点，视觉编码器使用的精度 |
| KL 散度 | Kullback-Leibler Divergence，衡量两个概率分布的差异 |
| 黄金集 | Gold Set，人工专家标注的评估数据集，永不用于训练 |
| 数据飞轮 | 用户使用产生数据 → 数据改进模型 → 模型改善产品 → 吸引更多用户的正向循环 |
| 弱监督 | Weak Supervision，利用未标注数据（只用正常样本）进行异常检测 |
| 两阶段告警 | 端侧低阈值标记 + 连续 N 次确认才推送用户，平衡召回率和误报率 |
| 灰度发布 | Canary Release，先推 5% 设备观察，再逐步扩大到全量 |
| manifest.json | OTA 包的元数据文件，绑定所有组件的版本和 sha256 |
| 数据血缘 | Data Lineage，记录每条数据的来源、处理过程，用于排查问题 |
| 感知哈希 | pHash（Perceptual Hash），用于检测相似图像的去重算法 |
| ECE | Expected Calibration Error，模型置信度校准误差 |

### 9.4 外部依赖版本锁定表

在各仓库 `requirements.txt` 中需要固定以下关键依赖的主版本：

| 依赖 | 固定策略 | 原因 |
|---|---|---|
| `vllm` | `==0.x.y`（固定 patch） | API 在 minor 版本间可能 breaking |
| `LLaMA-Factory` | git commit hash | 无 semver，API 不稳定 |
| `rknn-toolkit2` | `==2.x.y` | 官方工具，不定期 breaking |
| `rknn-llm` | `==1.x.y` | 同上 |
| `transformers` | `>=4.44,<5.0` | 4.44 引入 Qwen2-VL 支持 |
| `pydantic` | `>=2.0,<3.0` | v2 API 与 v1 不兼容 |
| `label-studio` | docker image tag 固定 | 避免数据库 schema 变化 |
| `wandb` | `>=0.16,<1.0` | 稳定 API |
| `torch` | `==2.x.y`（固定 patch） | CUDA 兼容性 |

### 9.5 快速参考：关键阈值

所有阈值的权威来源是各仓库的 `params.yaml`，此处仅作参考：

| 参数 | 默认值 | 位置 | 说明 |
|---|---|---|---|
| `dedup_hamming_threshold` | 10 | pet-data | pHash 汉明距离，低于此视为重复 |
| `quality_blur_threshold` | 100.0 | pet-data | Laplacian 方差，低于此为模糊 |
| `anomaly_score_threshold` | 0.07 | pet-data | AE 重建误差，高于此为异常候选 |
| `review_sampling_rate` | 0.15 | pet-annotation | 随机送人工审核比例 |
| `low_confidence_threshold` | 0.70 | pet-annotation | 强制人工审核的 confidence 下限 |
| `max_daily_tokens` | 10,000,000 | pet-annotation | 每日 token 用量上限 |
| `min_pairs_per_release` | 500 | pet-annotation/ota | OTA 发布前 DPO 对最低数量 |
| `anomaly_alert_threshold` | 0.40 | 设备固件 | 端侧标记可疑事件的阈值 |
| `vomit_immediate_threshold` | 0.70 | 设备固件 | 单次即告警的 vomit_gesture 阈值 |
| `consecutive_alert_count` | 3 | 手机 APP | 连续 N 次可疑才推送用户 |
| `calib_frame_count` | 200 | pet-quantize | 量化校准帧数 |
| `lora_rank` | 16 | pet-train | LoRA 秩，base 配置 |
| `lambda_kl` | 0.1 | pet-train | KL 蒸馏损失权重 |

---

*文档版本：2.0*  
*状态：正式发布*  
*维护规则：变更需要 PR + 至少一位 repo admin 审批，不允许直接推送到 main*  
*下次计划审查：产品首批出货后 30 天*


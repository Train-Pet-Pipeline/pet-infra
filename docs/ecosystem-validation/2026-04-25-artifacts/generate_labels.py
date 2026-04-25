"""为 30 张图生成 SFT 标签 + 5 对 DPO 标签，输出 JSONL。

Claude Opus 4.7（多模态）作为 annotator_id="claude-opus-4-7"，按 DEV_GUIDE §3 schema 输出。
mimic pet_annotation.export.sft_dpo.to_sft_samples 的 ShareGPTSFTSample 格式。

KNOWN GAP（写为 finding F001）：ShareGPTSFTSample.model_config="forbid" + 无 images 字段
→ 生成的 JSONL 是纯文本 SFT，VLM 视觉信号无法直接 train（Qwen2-VL 走 text-only path）。
后续 finding F001 会评估架构是否需要扩展 schema 加 images 字段（Phase 5）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# pet-schema imports — fail fast if not installed
from pet_schema import DPOSample, ShareGPTSFTSample, ShareGPTTurn

OUT_DIR = Path(os.environ.get("ECO_OUT_DIR", "/root/autodl-tmp/eco-validation"))
SFT_PATH = OUT_DIR / "sft_v1.jsonl"
DPO_PATH = OUT_DIR / "dpo_v1.jsonl"

ANNOTATOR_ID = "claude-opus-4-7"
SCHEMA_VERSION = "1.0"

SYSTEM_PROMPT = """你是一个专业的宠物行为分析系统，负责分析喂食器摄像头拍摄的图像帧。

摄像头参数：固定俯角，对准食碗区域，视角固定不变。
你的任务：对当前帧中的宠物行为、状态和碗的情况进行精确分析。

输出规则（必须严格遵守，违反任何一条均为无效输出）：
1. 只输出 JSON，不输出任何其他内容，不加 markdown 代码块，不加注释
2. 所有概率字段值域为 [0.00, 1.00]，保留两位小数
3. action.distribution 中所有值之和必须为 1.00（允许浮点误差 ±0.01）
4. 如果画面中没有宠物，pet_present 设为 false，pet 字段设为 null
5. narrative 只描述当前帧可见内容，不推断历史，不拟人化，不超过 50 字
6. 视觉特征不清晰时使用 unobservable 选项，不要强行猜测
7. 不确定时用低置信度表达，不要给出虚假的高置信度"""

USER_PROMPT_TEMPLATE = """[图像帧]

请分析这张喂食器摄像头图像，严格按 schema 输出 JSON。"""


def label_no_pet(narrative: str, lighting: str = "bright", quality: str = "clear", conf: float = 0.95) -> dict:
    """画面无宠物（标题卡 / 空场景 / 文字屏 / 人物为主）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "pet_present": False,
        "pet_count": 0,
        "pet": None,
        "bowl": {"food_fill_ratio": None, "water_fill_ratio": None, "food_type_visible": "unknown"},
        "scene": {"lighting": lighting, "image_quality": quality, "confidence_overall": conf},
        "narrative": narrative,
    }


def label_with_pet(  # noqa: PLR0913
    *,
    species: str,
    breed: str,
    id_tag: str,
    id_conf: float,
    action_dist: dict,
    eating_speed: dict | None = None,
    engagement: float = 0.30,
    abandoned: float = 0.0,
    alertness: float = 0.50,
    anxiety: float = 0.20,
    pet_engagement: float = 0.40,
    posture: str = "relaxed",
    ear: str = "forward",
    anomaly: dict | None = None,
    bowl_food: float | None = None,
    bowl_water: float | None = None,
    food_type: str = "unknown",
    lighting: str = "bright",
    quality: str = "clear",
    conf: float = 0.80,
    narrative: str = "",
    pet_count: int = 1,
) -> dict:
    primary = max(action_dist.items(), key=lambda kv: kv[1])[0]
    if eating_speed is None:
        eating_speed = {"fast": 0.10, "normal": 0.20, "slow": 0.10}  # low totals when not eating
    if anomaly is None:
        anomaly = {
            "vomit_gesture": 0.02,
            "food_rejection": 0.05,
            "excessive_sniffing": 0.05,
            "lethargy": 0.10,
            "aggression": 0.05,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "pet_present": True,
        "pet_count": pet_count,
        "pet": {
            "species": species,
            "breed_estimate": breed,
            "id_tag": id_tag,
            "id_confidence": id_conf,
            "action": {"primary": primary, "distribution": action_dist},
            "eating_metrics": {
                "speed": eating_speed,
                "engagement": engagement,
                "abandoned_midway": abandoned,
            },
            "mood": {
                "alertness": alertness,
                "anxiety": anxiety,
                "engagement": pet_engagement,
            },
            "body_signals": {"posture": posture, "ear_position": ear},
            "anomaly_signals": anomaly,
        },
        "bowl": {
            "food_fill_ratio": bowl_food,
            "water_fill_ratio": bowl_water,
            "food_type_visible": food_type,
        },
        "scene": {"lighting": lighting, "image_quality": quality, "confidence_overall": conf},
        "narrative": narrative,
    }


# ============================================================================
# 30 张图标签（按 manifest 顺序）
# ============================================================================

LABELS: dict[str, dict] = {
    # ----- cat_images（15 张）-----
    "cat_images/clip_0000_f00.jpg": label_with_pet(
        species="cat", breed="gray_tabby", id_tag="gray_tabby_collar_studio",
        id_conf=0.90,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.10, alertness=0.60, anxiety=0.15, pet_engagement=0.30,
        posture="relaxed", ear="forward",
        narrative="灰色虎斑猫工作室肖像，戴白领与彩色领带，无碗。",
    ),
    "cat_images/clip_0000_f00_1.jpg": label_no_pet(
        narrative="室内场景以人为主，墙上有猫画像，无活体宠物。",
    ),
    "cat_images/clip_0000_f00_10.jpg": label_with_pet(
        species="cat", breed="tuxedo_shorthair", id_tag="black_white_floor",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.10,
                     "leaving_bowl": 0.0, "sitting_idle": 0.10, "other": 0.80},
        engagement=0.20, alertness=0.70, pet_engagement=0.55,
        posture="relaxed", ear="forward",
        narrative="黑白家猫俯卧在木地板，旁边白色塑料圆形玩具。",
    ),
    "cat_images/clip_0000_f00_11.jpg": label_with_pet(
        species="cat", breed="mixed_unknown", id_tag="gray_blur_outdoor",
        id_conf=0.30, conf=0.40, quality="blurry",
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.0, "other": 1.0},
        engagement=0.10, alertness=0.50, anxiety=0.30, pet_engagement=0.30,
        posture="unobservable", ear="unobservable",
        lighting="dim",
        narrative="模糊运动镜头，灰猫穿过户外草地，细节难辨。",
    ),
    "cat_images/clip_0000_f00_12.jpg": label_no_pet(
        narrative="纯黑屏文字卡片，介绍 Bengal 猫，无图像内容。",
        lighting="dim", quality="clear", conf=0.99,
    ),
    "cat_images/clip_0000_f00_13.jpg": label_with_pet(
        species="cat", breed="long_haired_mix", id_tag="rooftop_two_cats",
        id_conf=0.55, pet_count=2,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.05,
                     "leaving_bowl": 0.0, "sitting_idle": 0.75, "other": 0.20},
        engagement=0.15, alertness=0.70, anxiety=0.20, pet_engagement=0.40,
        posture="relaxed", ear="forward", lighting="dim",
        narrative="两只长毛猫在城市屋顶上，背景为远处建筑物。",
    ),
    "cat_images/clip_0000_f00_14.jpg": label_with_pet(
        species="cat", breed="bengal_or_tabby", id_tag="tabby_door_stretch",
        id_conf=0.75,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.0, "other": 1.0},
        engagement=0.20, alertness=0.85, anxiety=0.15, pet_engagement=0.75,
        posture="tense", ear="forward",
        narrative="虎斑猫站立后腿，前爪扒着白色房门，主动行为。",
    ),
    "cat_images/clip_0000_f00_15.jpg": label_with_pet(
        species="cat", breed="brown_tabby", id_tag="tabby_sleeping_bed",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.95, "other": 0.05},
        engagement=0.05, alertness=0.05, anxiety=0.05, pet_engagement=0.05,
        posture="relaxed", ear="flat",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.0,
            "lethargy": 0.50, "aggression": 0.0,
        },
        lighting="dim",
        narrative="棕色虎斑猫闭眼睡觉，侧躺在床上人手臂旁。",
    ),
    "cat_images/clip_0000_f00_16.jpg": label_with_pet(
        species="cat", breed="orange_tabby", id_tag="ginger_planter_dig",
        id_conf=0.80,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.40,
                     "leaving_bowl": 0.0, "sitting_idle": 0.10, "other": 0.50},
        engagement=0.30, alertness=0.65, anxiety=0.10, pet_engagement=0.65,
        posture="tense", ear="forward",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.20,
            "lethargy": 0.0, "aggression": 0.0,
        },
        narrative="橘色虎斑猫站在花盆里嗅探土壤，户外场景。",
    ),
    "cat_images/clip_0000_f00_17.jpg": label_no_pet(
        narrative="米色背景标题卡 \"7 Sounds Cats Make\"，无活宠。",
    ),
    "cat_images/clip_0000_f00_18.jpg": label_no_pet(
        narrative="室内客厅空场景，电视与酒架，无宠物可见。",
    ),
    "cat_images/clip_0000_f00_19.jpg": label_with_pet(
        species="cat", breed="white_longhair", id_tag="white_cat_woods",
        id_conf=0.45, conf=0.50, quality="blurry",
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.10, "other": 0.90},
        engagement=0.15, alertness=0.65, anxiety=0.30, pet_engagement=0.60,
        posture="tense", ear="unobservable", lighting="dim",
        narrative="森林环境中白色长毛猫攀爬在长满苔藓的岩石上。",
    ),
    "cat_images/clip_0000_f00_2.jpg": label_with_pet(
        species="cat", breed="tuxedo_shorthair", id_tag="tuxedo_indoor_alert",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.55, "other": 0.45},
        engagement=0.10, alertness=0.85, anxiety=0.15, pet_engagement=0.50,
        posture="relaxed", ear="forward",
        narrative="黑白家猫俯卧地板，头部抬起向左方注视，警觉。",
    ),
    "cat_images/clip_0000_f00_20.jpg": label_with_pet(
        species="cat", breed="brown_tabby", id_tag="tabby_window_watch",
        id_conf=0.80,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.60, "other": 0.40},
        engagement=0.10, alertness=0.85, anxiety=0.15, pet_engagement=0.60,
        posture="relaxed", ear="forward",
        narrative="虎斑白爪猫戴蓝色项圈，趴在窗边凝视外侧花卉。",
    ),
    "cat_images/clip_0000_f00_21.jpg": label_with_pet(
        species="cat", breed="mixed_two_cats", id_tag="gray_white_plus_tabby_bed",
        id_conf=0.80, pet_count=2,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.05, alertness=0.55, anxiety=0.10, pet_engagement=0.30,
        posture="relaxed", ear="forward", lighting="dim",
        narrative="灰白与棕虎斑两只猫并排趴在条纹床罩上，头部相邻。",
    ),
    # ----- dog_images（15 张）-----
    "dog_images/hf_000000.png": label_with_pet(
        species="dog", breed="brown_lab_mix", id_tag="brown_dog_kennel",
        id_conf=0.70,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.0, "other": 1.0},
        engagement=0.20, alertness=0.65, anxiety=0.45, pet_engagement=0.40,
        posture="tense", ear="flat", lighting="dim",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.0,
            "lethargy": 0.20, "aggression": 0.05,
        },
        narrative="棕色拉布拉多混血站立于铁笼内，目视镜头。",
    ),
    "dog_images/hf_000001.png": label_with_pet(
        species="dog", breed="tricolor_puppy", id_tag="puppy_held_shelter",
        id_conf=0.75,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.30, "other": 0.70},
        engagement=0.20, alertness=0.55, anxiety=0.35, pet_engagement=0.30,
        posture="relaxed", ear="flat",
        narrative="黑白棕三色小狗被人抱在胸前，收容所背景。",
    ),
    "dog_images/hf_000002.png": label_with_pet(
        species="dog", breed="brown_shorthair", id_tag="brown_dog_lying",
        id_conf=0.70,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.10, alertness=0.40, anxiety=0.30, pet_engagement=0.25,
        posture="relaxed", ear="flat", lighting="dim",
        narrative="棕色短毛犬侧卧白色台阶上，铁丝网背景，环境暗淡。",
    ),
    "dog_images/hf_000003.png": label_with_pet(
        species="dog", breed="black_longhair_small", id_tag="black_fluffy_floor",
        id_conf=0.65,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.20, "other": 0.80},
        engagement=0.15, alertness=0.60, anxiety=0.25, pet_engagement=0.40,
        posture="relaxed", ear="forward",
        narrative="黑色长毛小型犬站立水泥地，旁有人腿，待领养场景。",
    ),
    "dog_images/hf_000004.png": label_with_pet(
        species="dog", breed="greyhound_mix", id_tag="greyhound_treat",
        id_conf=0.80,
        action_dist={"eating": 0.05, "drinking": 0.0, "sniffing_only": 0.55,
                     "leaving_bowl": 0.0, "sitting_idle": 0.15, "other": 0.25},
        eating_speed={"fast": 0.10, "normal": 0.30, "slow": 0.20},
        engagement=0.65, alertness=0.80, anxiety=0.10, pet_engagement=0.85,
        posture="relaxed", ear="forward",
        narrative="棕色灰猎犬张嘴吐舌，主人手中持零食在前方诱导。",
    ),
    "dog_images/hf_000005.png": label_with_pet(
        species="dog", breed="shepherd_puppy", id_tag="puppy_cage_sit",
        id_conf=0.75,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.10, alertness=0.55, anxiety=0.35, pet_engagement=0.20,
        posture="relaxed", ear="forward",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.0,
            "lethargy": 0.10, "aggression": 0.0,
        },
        narrative="棕黑色牧羊犬幼崽坐在铁笼内，吐舌喘气。",
    ),
    "dog_images/hf_000006.png": label_with_pet(
        species="dog", breed="pitbull_mix", id_tag="brindle_white_face",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.20, "other": 0.80},
        engagement=0.40, alertness=0.85, anxiety=0.15, pet_engagement=0.75,
        posture="relaxed", ear="forward",
        narrative="灰白比特犬混血特写，吐舌张嘴，正面注视镜头。",
    ),
    "dog_images/hf_000007.png": label_with_pet(
        species="dog", breed="shepherd_puppy_brown", id_tag="brown_puppy_portrait",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.95, "other": 0.05},
        engagement=0.10, alertness=0.50, anxiety=0.25, pet_engagement=0.30,
        posture="relaxed", ear="flat",
        narrative="棕色幼犬端坐，黑色面罩，头微歪正视相机。",
    ),
    "dog_images/hf_000008.png": label_with_pet(
        species="dog", breed="yellow_lab", id_tag="yellow_lab_walked",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.05,
                     "leaving_bowl": 0.0, "sitting_idle": 0.15, "other": 0.80},
        engagement=0.30, alertness=0.65, anxiety=0.10, pet_engagement=0.55,
        posture="relaxed", ear="flat",
        narrative="黄色拉布拉多戴红色牵引绳被人遛在草地上，精神良好。",
    ),
    "dog_images/hf_000009.png": label_with_pet(
        species="dog", breed="golden_retriever_puppy", id_tag="golden_puppy_held",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.10, alertness=0.45, anxiety=0.25, pet_engagement=0.30,
        posture="relaxed", ear="flat",
        narrative="金色金毛幼犬被人抱起，毛茸茸双耳下垂，注视镜头。",
    ),
    "dog_images/hf_000010.png": label_with_pet(
        species="dog", breed="tricolor_shepherd", id_tag="tricolor_cage_lying",
        id_conf=0.65,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.85, "other": 0.15},
        engagement=0.05, alertness=0.40, anxiety=0.40, pet_engagement=0.20,
        posture="hunched", ear="flat", lighting="dim",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.0,
            "lethargy": 0.40, "aggression": 0.0,
        },
        narrative="黑棕白三色牧羊犬蜷缩铁笼角落，神情消极。",
    ),
    "dog_images/hf_000011.png": label_with_pet(
        species="dog", breed="yellow_lab", id_tag="yellow_lab_panting",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.10, "other": 0.90},
        engagement=0.40, alertness=0.85, anxiety=0.10, pet_engagement=0.70,
        posture="relaxed", ear="forward",
        narrative="黄色拉布拉多正面站立，长舌外伸喘气，戴紫色项圈。",
    ),
    "dog_images/hf_000012.png": label_with_pet(
        species="dog", breed="brown_senior_mix", id_tag="brown_dog_indoor",
        id_conf=0.70,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.90, "other": 0.10},
        engagement=0.05, alertness=0.30, anxiety=0.15, pet_engagement=0.20,
        posture="relaxed", ear="flat", lighting="dim",
        anomaly={
            "vomit_gesture": 0.0, "food_rejection": 0.0, "excessive_sniffing": 0.0,
            "lethargy": 0.50, "aggression": 0.0,
        },
        narrative="棕红色老年犬侧卧室内沙发旁，眼神反光，安静休息。",
    ),
    "dog_images/hf_000013.png": label_with_pet(
        species="dog", breed="pitbull_white_brown", id_tag="pitbull_smile_indoor",
        id_conf=0.85,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.0,
                     "leaving_bowl": 0.0, "sitting_idle": 0.55, "other": 0.45},
        engagement=0.50, alertness=0.85, anxiety=0.10, pet_engagement=0.85,
        posture="relaxed", ear="forward",
        narrative="白色比特犬戴红色项圈，咧嘴露牙吐舌，神态愉快。",
    ),
    "dog_images/hf_000014.png": label_with_pet(
        species="dog", breed="large_brown_white", id_tag="large_dog_leashed",
        id_conf=0.75,
        action_dist={"eating": 0.0, "drinking": 0.0, "sniffing_only": 0.10,
                     "leaving_bowl": 0.0, "sitting_idle": 0.10, "other": 0.80},
        engagement=0.30, alertness=0.65, anxiety=0.20, pet_engagement=0.55,
        posture="relaxed", ear="flat", quality="blurry", conf=0.70,
        narrative="大型棕白狗站立草坪与人互动，旁有人手持牵绳。",
    ),
}


def make_sft_sample(rel_path: str, label: dict) -> dict:
    """Wrap label as ShareGPTSFTSample (mimic pet_annotation.export.sft_dpo)."""
    sample_id = rel_path.replace("/", "__").rsplit(".", 1)[0]
    sample = ShareGPTSFTSample(
        conversations=[
            ShareGPTTurn(**{"from": "system", "value": SYSTEM_PROMPT}),
            ShareGPTTurn(**{"from": "human", "value": USER_PROMPT_TEMPLATE}),
            ShareGPTTurn(**{"from": "gpt", "value": json.dumps(label, ensure_ascii=False)}),
        ],
        sample_id=sample_id,
        source_target_id=sample_id,
        annotator_id=ANNOTATOR_ID,
    )
    # validate (matches pet-annotation exporter pattern)
    ShareGPTSFTSample.model_validate(sample.model_dump(by_alias=True))
    return sample.model_dump(by_alias=True)


def make_dpo_pair(rel_path: str, chosen_label: dict, rejected_label: dict) -> dict:
    """Create DPOSample with chosen=high-quality / rejected=lower-quality response."""
    sample_id = rel_path.replace("/", "__").rsplit(".", 1)[0]
    pair = DPOSample(
        prompt=SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE,
        chosen=json.dumps(chosen_label, ensure_ascii=False),
        rejected=json.dumps(rejected_label, ensure_ascii=False),
        sample_id=sample_id,
        chosen_annotator_id="claude-opus-4-7",
        rejected_annotator_id="claude-opus-4-7-degraded",
    )
    DPOSample.model_validate(pair.model_dump())
    return pair.model_dump()


def make_degraded_label(label: dict) -> dict:
    """Generate a 'rejected' (lower-quality) variant: bump confidences too high + drop narrative."""
    out = json.loads(json.dumps(label))  # deep copy
    if out.get("pet"):
        out["pet"]["id_confidence"] = min(1.0, out["pet"]["id_confidence"] + 0.15)
        out["pet"]["mood"]["alertness"] = min(1.0, out["pet"]["mood"]["alertness"] + 0.20)
    out["scene"]["confidence_overall"] = min(1.0, out["scene"]["confidence_overall"] + 0.15)
    out["narrative"] = (out["narrative"] or "") + "（推断）"  # 加拟人化推断 — 违反规则 5
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # SFT
    samples = [make_sft_sample(p, lbl) for p, lbl in LABELS.items()]
    with SFT_PATH.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"SFT: {len(samples)} samples → {SFT_PATH}")

    # DPO — 选 5 张含宠物的图（信息丰富才有 chosen/rejected 区分）
    dpo_targets = [
        "cat_images/clip_0000_f00.jpg",
        "cat_images/clip_0000_f00_14.jpg",
        "dog_images/hf_000004.png",
        "dog_images/hf_000010.png",
        "dog_images/hf_000013.png",
    ]
    pairs = [make_dpo_pair(p, LABELS[p], make_degraded_label(LABELS[p])) for p in dpo_targets]
    with DPO_PATH.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"DPO: {len(pairs)} pairs → {DPO_PATH}")


if __name__ == "__main__":
    main()

# Phase 2 债务还清设计

**日期**：2026-04-21
**作者**：Claude (Opus 4.7) + 用户共同 brainstorming
**上游 spec**：`2026-04-20-multi-model-pipeline-design.md`（North Star §0.2.1）
**状态**：草案 → 等 spec review + 用户复核

## 背景

Phase 2（pet-data v1.1.0 + pet-annotation v1.1.0 + pet-infra v2.1.0）shipped 2026-04-21 之后，对照上游 spec 新增的 §0.2.1 North Star（"所有决策的唯一标尺"）做复盘，识别出 2 条真欠债：

- **DEBT-1**：pet-annotation 按 modality 拆成 `vision_annotations` / `audio_annotations` 两张表，违反 "新 modality 不改 schema" 原则；且更深的问题是**拆分轴错了**——两张表实际承载的是 LLM 风格 vs. classifier 风格标注，未来"同 modality 多 annotator 范式"（如 audio 既可 CNN 也可 Whisper+LLM）无法表达。
- **DEBT-2**：pet-data / pet-annotation 的 `pyproject.toml` 硬 pin `pet-infra @ git+…@v2.0.0`，违反 "compatibility_matrix 是版本治理真理源"。pet-infra 每次 bump 都被迫连锁改下游 pin；pet-infra CI 被迫用 `--force-reinstall --no-deps` workaround 绕开。

（原 DEBT-3 "migration trigger 挪到应用层" 经核查为记忆错误——不变量本来就守在数据层 CHECK constraint，已撤销。）

## §1 总体原则

按 **γ 顺序 + 破坏性重构不留旧代码**：

- compatibility_matrix 成为**唯一** pin 真理源；pet-infra 可自由演进
- annotation 表按 **annotator 范式**（capability）拆而非按 modality 拆
- 破坏性一律 major bump；**不写数据迁移脚本**（fixture-only 数据源）
- spec §3.3 Annotation 契约 + §7.3 Phase 2 交付 + 新增 §2.6 依赖治理同步修订

**受影响仓库与版本**

| 仓库 | 现版本 | 还债后 | 类型 |
|---|---|---|---|
| pet-schema | v2.0.0 | v2.1.0 | minor（加 4 子类，替换旧 2 子类） |
| pet-data | v1.1.0 | v1.2.0 | minor（去 pin） |
| pet-annotation | v1.1.0 | **v2.0.0** | **major（schema drop + rebuild）** |
| pet-infra | v2.1.0 | v2.2.0 | minor（CI + docs + matrix） |

`compatibility_matrix.yaml` 新增 release `2026.06` = schema 2.1.0 / infra 2.2.0 / data 1.2.0 / annotation 2.0.0

## §2 Annotation 四范式表设计（DEBT-1 核心）

pet-schema 新增 4 个 Pydantic 子类继承 `BaseAnnotation`，按 **annotator 范式** discriminator：

| Pydantic 类 | SQL 表 | 关键字段（非空） | 代表 annotator |
|---|---|---|---|
| `LLMAnnotation` | `llm_annotations` | `prompt_hash`, `raw_response`, `parsed_output` (JSONB), `modality` | VLM (Qwen2-VL), Whisper+LLM, text-LLM |
| `ClassifierAnnotation` | `classifier_annotations` | `predicted_class`, `class_probs` (JSONB), `logits` (nullable), `modality` | audio CNN, image classifier, sensor NN |
| `RuleAnnotation` | `rule_annotations` | `rule_id`, `rule_output` (JSONB), `modality` | 启发式、阈值规则 |
| `HumanAnnotation` | `human_annotations` | `reviewer`, `decision`, `notes`, `modality` | 人工审核、DPO 选择 |

**共通字段**（每张表都有）：
```
annotation_id, target_id, modality, schema_version, created_at, storage_uri
```
- `target_id` = 被标注对象 ID（frame_id / audio_sample_id / sensor_sample_id 通用，不再按 modality 分列名）
- `modality` 是 attribute 列（**不是** discriminator）——每张表天然容纳任意 modality

**SQL 约束**
- `CHECK modality IN ('vision','audio','sensor','multimodal')`
- `schema_version` 默认 `"2.1.0"`
- 组合 UNIQUE `(target_id, annotator_id, prompt_hash)` / `(target_id, annotator_id)` 防重复标注

**反模式守护**：infra 代码（registry/adapter/dataset plugin）**只按 `annotator_type` 路由**，不 branch 在 `modality`；新 modality = Pydantic enum 加一个值 + 各表 CHECK 加一枚举项 + 0 Python 改动；新 annotator 范式 = 加一张表 + 一个 Pydantic 子类 + 一个 plugin key。

**Pydantic discriminator 换轴**

```python
# 旧（被还债删除）
Annotation = Annotated[VisionAnnotation | AudioAnnotation, Discriminator("modality")]

# 新
class BaseAnnotation(BaseModel):
    annotation_id: str
    target_id: str
    annotator_type: Literal["llm", "classifier", "rule", "human"]  # 扩大语义
    annotator_id: str           # ModelCard.id 或 reviewer id
    modality: Modality          # 被标注对象的模态，attribute
    schema_version: str
    created_at: datetime
    storage_uri: Optional[str]

class LLMAnnotation(BaseAnnotation):
    annotator_type: Literal["llm"] = "llm"
    prompt_hash: str
    raw_response: str
    parsed_output: dict         # JSONB — 各 modality 的结构化输出（vision 用 PetFeederEvent，audio 用 AudioCaption 等，Pydantic 子子类由各 modality 决定）

class ClassifierAnnotation(BaseAnnotation):
    annotator_type: Literal["classifier"] = "classifier"
    predicted_class: str
    class_probs: dict[str, float]
    logits: Optional[list[float]]

class RuleAnnotation(BaseAnnotation):
    annotator_type: Literal["rule"] = "rule"
    rule_id: str
    rule_output: dict

class HumanAnnotation(BaseAnnotation):
    annotator_type: Literal["human"] = "human"
    reviewer: str
    decision: str
    notes: Optional[str]

Annotation = Annotated[
    LLMAnnotation | ClassifierAnnotation | RuleAnnotation | HumanAnnotation,
    Discriminator("annotator_type"),
]
```

**注意语义迁移**：
- 旧 `annotator_type="vlm"` → 新 `"llm"`（扩大：不只是 VLM，任何 LLM 标注）
- 旧 `annotator_type="cnn"` → 新 `"classifier"`（扩大：不只是 CNN，任何分类器）

## §3 peer-dep 模式（DEBT-2 核心）

**pet-data / pet-annotation `pyproject.toml`**：删除 `pet-infra @ git+…@v2.0.0`，不再在 `[project.dependencies]` 里声明 pet-infra（peer dep）。

**README 加 Prerequisites 段**：`pet-infra >= 2.x must be installed first (see compatibility_matrix.yaml for the pinned tag).`

**`_register.py` fail-fast 守卫**：

```python
try:
    import pet_infra  # noqa: F401
except ImportError as e:
    raise ImportError(
        "pet-data requires pet-infra to be installed first. "
        "Install via 'pip install pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<tag>' "
        "using the tag pinned in pet-infra/docs/compatibility_matrix.yaml."
    ) from e
```

**三仓 CI 装序统一**（写进 pet-infra `DEVELOPMENT_GUIDE.md`）：

```bash
pip install 'pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra@<matrix_tag>'
pip install -e . --no-deps
python -c "import pet_infra; assert pet_infra.__version__.startswith(('2.',))"
```

**pet-infra `plugin-discovery.yml` 回滚**：删除 `--force-reinstall --no-deps`，改为 "装 pet-infra editable → 装下游 `--no-deps` → 跑 `pet list-plugins`"。workflow 从 ~30 行回归到 ~15 行。

**DEVELOPMENT_GUIDE 新增 §11 "依赖治理与 peer-dep 约定"**（内容：compatibility_matrix 作真理源 / 下游不 pin 上游 / CI 装序模板 / conda env `pet-pipeline` 预装 pet-infra）。

## §4 PR 编排（5 条 PR 链 · γ 顺序）

每条走 `feature/* → dev → main`；独立绿方可进下一条。

| # | 仓库 | Branch | 改动 | 版本 | 依赖 |
|---|---|---|---|---|---|
| **0** | pet-infra | `feature/phase-2-debt-repayment-design` | **本 design doc + spec §3.3 / §7.3 / 新增 §2.6 修订** | — | 无（第一个 merge） |
| **1** | pet-infra | `feature/peer-dep-convention` | DEVELOPMENT_GUIDE §11 peer-dep 约定 + `install-order-smoke.yml` 新 workflow；**暂不删** plugin-discovery 的 workaround（下游还有 pin） | — | 依赖 #0 |
| **2** | pet-data | `feature/pet-infra-peer-dep` | 删 pet-infra 硬 pin + `_register.py` fail-fast + CI 装序 + README Prerequisites | **v1.2.0** | 依赖 #1 |
| **3** | pet-schema | `feature/annotation-four-paradigms` | 加 4 Pydantic 子类 + 删旧 `VisionAnnotation/AudioAnnotation` + SCHEMA_VERSION 2.1.0 | **v2.1.0** | 无（可与 #2 并行） |
| **4** | pet-annotation | `feature/four-paradigm-tables` | 去 pet-infra pin + fail-fast + migration 004（drop 旧 2 表 → create 4 范式表）+ `adapter.py` 按 annotator_type 路由 + 4 plugin key（`pet_annotation.llm/classifier/rule/human`）+ CLI + 删全部旧测试 | **v2.0.0** | 依赖 #3（import 新 Pydantic）+ #1 |
| **5** | pet-infra | `feature/matrix-2026.06` | compatibility_matrix 加 `2026.06` + plugin-discovery.yml 装序改 matrix tag + 删 workaround + DEVELOPMENT_GUIDE §10 同步 4 范式 + bump v2.2.0 + tag release | **v2.2.0** | 依赖 #2/#3/#4 |

**注释**：
- 把原计划的"pet-annotation 中间版 v1.2.0（只去 pin）"**合进 #4 一次性发 v2.0.0**（feedback_refactor_no_legacy：不留中间过渡版本）
- #1 暂不删 workaround：因为 #2/#3/#4 还没 merge 前，下游老 tag 的 git-URL pin 还生效；#5 才最终清理
- #2 和 #3 无依赖可并行启动

## §5 测试策略

**pet-schema（#3）**
- 每个新 Pydantic 子类 3 类测试：`test_<class>_roundtrip`（JSON dump/load 守恒）、`test_<class>_required_fields`（缺必填抛 ValidationError）、`test_<class>_modality_enum`（非法值被拒）
- `test_annotation_discriminator`：`Annotation.model_validate({"annotator_type":"llm",...})` 路由到 `LLMAnnotation`
- 全链 CI（repository_dispatch）自动验证 pet-data/pet-annotation 未引用被删的旧符号

**pet-annotation（#4）**
- `tests/test_four_paradigm_tables.py`：4 张表各一个 insert + select roundtrip + CHECK 约束负例
- `tests/test_adapter_routing.py`：给定 `annotator_type` 路由到正确表；未知类型 fail-fast
- `tests/test_plugin_keys.py`：4 个 `DATASETS.module_dict` 键可发现
- `tests/test_cli_annotator_dispatch.py`：CLI `--annotator=llm --modality=audio` 路由到 `llm_annotations`
- **旧测试直接删**（test_store.py 里引用旧 VisionAnnotationRow 等），不做兼容保留
- 新 fixture factory：`conftest.py` 提供 `llm_annotation_factory()` 等 4 个工厂

**pet-data（#2）**
- `tests/test_peer_dep_fail_fast.py`：monkeypatch `sys.modules["pet_infra"] = None` → `import pet_data._register` 抛 friendly ImportError

**pet-infra（#1 + #5）**
- #1 新 `.github/workflows/install-order-smoke.yml`：起 clean docker → 按 DEVELOPMENT_GUIDE §11 装序装 → `pet list-plugins --json` 断言 Phase 2 keys 都在
- #5 `tests/test_compat_matrix.py` 加 `test_matrix_has_2026_06_release`

**跨仓集成**
- `pet-infra/tests/integration/test_phase2_smoke.py` 更新：dataset keys 预期值从 `pet_annotation.vision_annotations/audio_annotations` 改为 4 个新 key

## §6 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| pet-schema bump 触发全链 CI 一片红 | 下游回滚代价高 | #3 合并前本地 `pip install -e` 三仓跑 pytest 预演；#3 合并后 annotation CI 红是预期直到 #4 merge，文档明示 |
| 忘装 pet-infra 的 dev 被 fail-fast 挡但不知怎么修 | 体验差 | fail-fast 错误信息带 install 命令；conda env `pet-pipeline` 已预装覆盖 95% 场景 |
| pet-infra `plugin-discovery.yml` 删 workaround 后老 tag 还在 matrix 测 | 老 tag CI 红 | #5 matrix 同步改 downstream tag 到 v1.2.0/v2.0.0；不测老 tag |
| annotation v2.0.0 破坏所有现存 dbfile | 本地 DB 失效 | README 明写"v2.0.0 需重建 annotation DB"；提供 `scripts/reset_db.sh` |
| 外部消费者（pet-train/pet-eval/GPU 实验代码）引用 `VisionAnnotation` / `AudioAnnotation` | import 断 | grep 全 monorepo 确认无残留引用；pet-train/pet-eval 尚未用 Phase 2 annotation（Phase 3/4 才接入）；pet-demo 不在 scope |
| #3 review 卡住阻塞 #4 | 还债停滞 | #1/#2 可先推不依赖 #3；#3 单 PR 改动小易审；兜底：把 4 子类先以 flat module 形式加、占位通过 CI、再单独 PR 完善 |
| 四范式表在某未来场景反而阻碍（如出现"LLM+classifier 混合输出"模型） | Phase 4/5 二次重构 | 设计反复验过三种扩展路径：新 modality / 新 annotator 范式 / 同 modality 多范式 — 均零 schema 变更。真出现"混合"场景时，一个 annotation row 里 `annotator_type="llm"` 存主输出、relations 表链接 `classifier` row 作辅助输出；仍零 schema 变更 |

## §7 Definition of Done

本次还债完成 = 以下全部满足：

- [ ] 本 design doc 在 pet-infra main（PR #0 merged）
- [ ] spec §3.3 / §7.3 / 新 §2.6 修订在 main（同 #0）
- [ ] 5 条 PR 链（#1-#5）全部 merge 到各自 main
- [ ] 三仓 tag 已发：pet-schema `v2.1.0` / pet-data `v1.2.0` / pet-annotation `v2.0.0` / pet-infra `v2.2.0`
- [ ] compatibility_matrix `2026.06` release 行已提交并被 `test_compat_matrix.py` 断言
- [ ] pet-infra `plugin-discovery.yml` 里**不再**有 `--force-reinstall --no-deps` 残留
- [ ] pet-annotation 源码里**不再**引用 `vision_annotations` / `audio_annotations` 任一旧表名
- [ ] pet-schema 源码里**不再**导出 `VisionAnnotation` / `AudioAnnotation` 符号
- [ ] pet-data/pet-annotation `pyproject.toml` 里**不再**声明 `pet-infra` 依赖
- [ ] DEVELOPMENT_GUIDE §10 已更新到 4 范式表；§11（peer-dep 约定）已新增
- [ ] memory `project_multi_model_refactor.md` 标注还债完成，下一步 Phase 3
- [ ] DEBT-4（Phase 3 plan DoD 加 North Star 自检）保留待 Phase 3 启动时执行

## §8 出本 spec 后的下一步

1. dispatch `spec-document-reviewer` 审本 design doc → 修到 ✅
2. 请用户复审本文档 → 获批
3. 调 `superpowers:writing-plans` 产出 5 条 PR 的详细实施 plan（每条 PR 内部 TDD 步骤）
4. 调 `superpowers:subagent-driven-development` 按 plan 执行

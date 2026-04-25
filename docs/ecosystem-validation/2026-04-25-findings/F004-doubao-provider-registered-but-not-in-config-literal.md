# F004 — Doubao provider 注册但 LLMAnnotatorConfig 的 Literal 拒绝它

| | |
|---|---|
| 发现时间 | 2026-04-25 22:05 |
| 发现 phase | Phase 1.2 准备 / pet-annotation config 检查 |
| severity | **HIGH**（pet-annotation 内部不一致，影响 Pluggability 但不阻塞当前测试） |
| 状态 | OPEN — 工作绕过用 `provider: openai_compat` + Doubao endpoint；fix 走 B-batch PR |
| 北极星受影响维度 | Pluggability |

## 复现路径

```bash
# 1. 看 provider 注册表
grep "register_provider" /workspace/eco-validation/pet-annotation/src/pet_annotation/teacher/provider.py
# → register_provider("openai_compat", ...) / register_provider("doubao", ...) / register_provider("vllm", ...)

# 2. 看配置 schema
grep "Literal" /workspace/eco-validation/pet-annotation/src/pet_annotation/config.py
# → provider: Literal["openai_compat", "vllm"]

# 3. 用 doubao 配置 → ValidationError
python -c "
from pet_annotation.config import LLMAnnotatorConfig
LLMAnnotatorConfig(id='x', provider='doubao', base_url='https://ark...', model_name='x')
"
# → pydantic.ValidationError: provider Literal['openai_compat', 'vllm']
```

## 实际行为

`LLMAnnotatorConfig` 验证拒绝 `provider="doubao"`，即使 `provider.py` 已注册 DoubaoProvider 类。

## 期望行为

`LLMAnnotatorConfig.provider` Literal 应当包含 `"doubao"`，否则注册"doubao" provider 没有意义。

## 根因

pet-annotation 有两处 provider 知识：
1. `teacher/provider.py` 通用注册表 — 含 doubao / openai_compat / vllm
2. `config.py LLMAnnotatorConfig.provider` Literal — 只列 openai_compat / vllm

**两者未同步**。注册表是动态的（运行时可加 provider），但 Literal 是 hard-coded。Doubao 漏列说明添加 DoubaoProvider 时只改了 provider.py 没改 config.py。

`orchestrator._build_provider()` 也只处理 `vllm` vs OAI-compat 两路（doubao 走 fall-through 到 OAI-compat 因为 DoubaoProvider 继承 OAI-compat 且无 override）。

所以 DoubaoProvider 类目前事实上**无独立行为**，registered 但永远不会被独立 instantiate。

## 修复

最简 fix：

```python
# config.py line 75
class LLMAnnotatorConfig(BaseModel):
    ...
    provider: Literal["openai_compat", "vllm", "doubao"]  # add "doubao"
```

也需在 orchestrator `_build_provider()` 加显式 doubao 分支：

```python
if llm_cfg.provider == "doubao":
    return DoubaoProvider(...)
```

否则即使 Literal 接受 doubao，instantiate 出来还是普通 OpenAICompatProvider — 名义上"支持 doubao" 但行为未差异化。

## 工作绕过（rental 期）

Doubao API 端点本身就是 OpenAI-compat（`https://ark.cn-beijing.volces.com/api/v3/`），所以**直接配 `provider: openai_compat`** 就能用 Doubao。这不算"绕过"——它是 Doubao 的标准对接方式。Phase 1.2 就这样跑，Phase 2 A1 也用同样配置。

```yaml
llm:
  annotators:
    - id: "doubao-seed-2-0-lite"
      provider: "openai_compat"
      base_url: "https://ark.cn-beijing.volces.com/api/v3"
      model_name: "doubao-seed-2-0-lite-260215"
      api_key: <env>
```

## Retest 证据

- 临时（rental 期）：Phase 1.2 用 OAI-compat 走通 → Doubao 标 30 张图 ✅（待跑）
- 正式 fix（B-batch PR）：
  - pet-annotation `pytest tests/test_config.py::test_llm_annotator_doubao` 新增
  - retest Phase 1.2 用 `provider: doubao`（不再绕道 openai_compat） → 同样产出 ✅

## Follow-ups

1. rental 末 B-batch：`fix/pet-annotation-add-doubao-to-literal` PR
2. 如选不做 fix（doubao provider 完全冗余），删除 doubao.py + provider.py 中的 register_provider 注册 — 让架构一致（"我们不支持 doubao 独立 provider"）
3. 上面两个选择影响 pet-annotation v2.2.0 minor bump 决策

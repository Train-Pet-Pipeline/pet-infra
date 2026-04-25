# F012 — `pet run` 不持久化 ModelCard 到 ./model_cards/，replay 永远找不到

| | |
|---|---|
| 发现时间 | 2026-04-26 01:30 |
| 发现 phase | Phase 1.7 replay |
| severity | **HIGH** — replay claim 与实际行为不符（北极星 Comparability ↓） |
| 状态 | OPEN |
| 北极星受影响维度 | Comparability + Flexibility |

## 复现命令

```bash
pet run recipes/eco_validation_phase1_b56.yaml   # 跑通 train+quantize+ota
ls ./model_cards/                                  # → 空
pet run --replay <card_id>                         # → FileNotFoundError
```

## 实际行为

`pet_infra.orchestrator.runner.pet_run()` 返回 ModelCard 对象但**不写到 `./model_cards/<card_id>.json`**。replay 模块默认查找 `./model_cards/{card_id}.json`，永远找不到。

## 期望行为

成功的 `pet run` 应当把最终 ModelCard 持久化到 `./model_cards/{card_id}.json`（或 PET_CARD_REGISTRY 指定路径），让后续 `pet run --replay <card_id>` 直接可用。

## 根因

`pet_run()` 返回 card 但不持久化。只有 `launcher.py:_run_one()` (用于 multirun launches) 在 `out_dir/card.json` 写一份 — 这不是 replay 期望的位置。

## 修复

`pet_infra/orchestrator/runner.py` 的 `pet_run()` 末尾加：

```python
from pet_infra.replay import _DEFAULT_REGISTRY  # or env var
import os
registry = Path(os.environ.get("PET_CARD_REGISTRY", _DEFAULT_REGISTRY))
registry.mkdir(parents=True, exist_ok=True)
(registry / f"{final_card.id}.json").write_text(
    final_card.model_dump_json(indent=2)
)
```

加 1 处 ~5 行。

## 配套：resolved_config_uri 也需 pet_run 写

deterministic replay 需 ModelCard.resolved_config_uri 字段（指向 pet_run 写的 resolved config dump）。launcher.py:140-146 已实现这逻辑，但只在 multirun 路径。`pet_run()` 直接调用时同样需要。

## Retest（fix 后）

```bash
pet run recipes/.../small.yaml
ls ./model_cards/   # → smoke_small.json
pet run --replay smoke_small --dry-run   # → "replay complete: card_id=..."
```

## Workaround（rental 期）

手工写 ModelCard.json 到 model_cards/ 后调 replay()。但 resolved_config_uri 仍需配套保存。

## Follow-ups

1. B-batch PR `fix/pet-infra-pet-run-persist-modelcard`
2. 加单测 `tests/test_orchestrator/test_runner.py::test_pet_run_persists_card`
3. 与 F009（discover_plugins）一起做 1 个 PR — 都改 `pet_run()` 入口

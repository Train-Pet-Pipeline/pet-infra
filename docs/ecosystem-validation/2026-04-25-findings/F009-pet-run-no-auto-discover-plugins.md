# F009 — `pet run` 不自动 discover plugins，第三方仓 trainer 无法被找到

| | |
|---|---|
| 发现时间 | 2026-04-26 00:55 |
| 发现 phase | Phase 1.3 / pet run eco_validation_phase1.yaml |
| severity | **HIGH** — fresh user 用法上的隐性失败 |
| 状态 | OPEN（rental 工作绕过：pre-import 各仓 register_all；正式 fix 走 B-batch PR） |
| 北极星受影响维度 | Pluggability + Flexibility |

## 复现命令

```bash
# Fresh env，9 仓 editable 装好后立即跑
pet run recipes/eco_validation_phase1.yaml
```

## 实际行为

```
pet_infra.orchestrator.hooks.run() raises:
LookupError: TRAINERS['llamafactory_sft'] not registered
```

虽然 pet-train 已 editable 装、entry-point 配置正常，但 pet-infra `cli.run_cmd` 不在 normal 路径调用 `discover_plugins()`，导致下游 plugins 不被注册。

## 期望行为

`pet run` 应在执行前自动调 `discover_plugins()` 一次（或 lazy first-access on registry）。否则 fresh user 必须知道：
```python
import pet_train.plugins._register; register_all()
import pet_eval.plugins._register; register_all()
... 7 仓
```
才能让 `pet run` 工作。

## 根因

`pet-infra/src/pet_infra/cli.py:run_cmd` 的 normal-path（line 145+）直接进 `pet_run()` 没 discover。
对照 `replay` 路径（line 233+）有显式 `discover_plugins()` 调用 → 不一致。

## 修复

`run_cmd` 在 line 152 之后（pet_run import 之后，invoke 之前）加：

```python
from pet_infra.plugins.discover import discover_plugins
discover_plugins()
```

成本：1 行。性能影响：discover 是 import time 一次性，整个进程不重复跑。

## Workaround（rental 期）

我们手工预 import 6 个仓的 `_register.register_all()` 后用 `pet_run()` 直接函数调用，bypass `pet run` CLI。

## Retest（待 fix 后）

```bash
pet run recipes/eco_validation_phase1.yaml
# 期望：trainer SFT 启动而不是 LookupError
```

## Follow-ups

1. B-batch PR `fix/pet-infra-cli-auto-discover-plugins`
2. 加单测：`tests/test_cli.py::test_run_cmd_auto_discovers_plugins`
3. 文档化：DEV_GUIDE §1.3 plugin discovery 流程图

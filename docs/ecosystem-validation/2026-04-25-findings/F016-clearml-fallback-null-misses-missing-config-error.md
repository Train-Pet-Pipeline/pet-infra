# F016 — pet-infra ClearML `on_unavailable=fallback_null` 漏掉 `MissingConfigError`

| | |
|---|---|
| 发现时间 | 2026-04-26 |
| 发现 phase | Phase 2.8 I5 ClearML offline + saas-fail 验证 |
| severity | **HIGH** — 文档化的 fallback_null 契约在 ctor 层未生效 |
| 状态 | **FIXED + regression test 已加** |
| 北极星受影响维度 | **Flexibility**（experiment_logger 故障注入设计意图被破坏）|

## 复现

```python
from pet_infra.experiment_logger.clearml_logger import ClearMLLogger
import os
for k in ["CLEARML_API_HOST", "CLEARML_API_ACCESS_KEY", "CLEARML_API_SECRET_KEY"]:
    os.environ.pop(k, None)
log = ClearMLLogger(
    mode="saas",
    api_host="http://does-not-exist.invalid:9999",
    on_unavailable="fallback_null",
    project="test",
)
log.start(recipe=None, stage="_probe")
```

## 实际行为

```
clearml.backend_api.session.session.MissingConfigError:
It seems ClearML is not configured on this machine!
```

**Exception 直接 raise 出来**——`fallback_null` 策略未生效。

## 期望行为

按 `OnUnavailable = Literal["strict", "fallback_null", "retry"]` 文档：
- `fallback_null`：unreachable 时切到 NullLogger，return None
- 不应该向上抛异常

## 根因

`ClearMLLogger.start()` 的 except clause 太窄：

```python
except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
    return self._handle_unavailable(e)
```

`clearml.backend_api.session.session.MissingConfigError` 继承自 `Exception` 不在以上 4 类——直接 leak。同样 leak 的可能还有 `clearml.utilities.proxy_object.UnsupportedKeyError` 等 clearml-side 配置错误。

设计意图是"ClearML 不可用就 fallback"——"不可用"包括**没配置**（dev / CI 环境常见），不只是"网络断"。

## 修复

```python
except Exception as e:
    # F016: catch broadly so fallback_null also handles MissingConfigError
    # and any other clearml-side init failure (not just network).
    return self._handle_unavailable(e)
```

`_handle_unavailable` 内部已经按 policy 分支：
- `strict` → re-raise
- `fallback_null` → log warning + return None
- `retry` → re-raise（retry 已在 _init_task 用 tenacity 包了）

所以广泛 catch 安全。

## Retest 证据 ✅

```bash
$ python -c "..."
fallback_null path now: task_id=None (None=NullLogger fallback OK)
log._task = None (None=fallback OK)

$ pytest tests/experiment_logger/test_clearml_logger.py -q
............... 14 passed in 0.45s
```

新加 `test_fallback_null_handles_missing_config_error` regression test 用 stand-in
`MissingConfigError(Exception)` 模拟 clearml 行为，避免依赖真实 clearml package。

## 设计反思

文档化 contract 应有 **policy contract test**：
- `strict` → ANY exception re-raise
- `fallback_null` → ANY exception → NullLogger
- `retry` → 重试 N 次后 re-raise

之前测试只覆盖 `ConnectionError` 单一路径——典型"happy path test，corner-case absent"。

## Follow-ups

- ✅ 修代码 + 加 regression test
- ⚠️ 类似的窄 catch 模式应该 audit 整个 codebase——是否还有其他"假装能 fallback 实际不能"的 case

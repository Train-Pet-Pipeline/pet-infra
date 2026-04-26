# F015 — pet-id `make test` 因 optional extras 未装而 collection error

| | |
|---|---|
| 发现时间 | 2026-04-26 07:50 |
| 发现 phase | Phase 2.9 ID3 capability test |
| severity | MEDIUM — fresh user 跑 `make test` 必然失败 |
| 状态 | **FIXED + commit pushed**（pet-id `fix/eco-validation-pet-id-tests-skip-optional-deps`） |
| 北极星受影响维度 | — |

## 复现命令

```bash
git clone https://github.com/Train-Pet-Pipeline/pet-id
cd pet-id && make setup && make test
```

## 实际行为

```
ImportError while loading conftest 'tests/backends/test_yolov10_detector.py'
ModuleNotFoundError: No module named 'ultralytics'
ERROR tests/backends/test_yolov10_detector.py
ERROR tests/backends/test_bytetrack_tracker.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
========================= 2 skipped, 2 errors in 2.61s =========================
make: *** [Makefile:7: test] Error 2
```

## 期望行为

`make test` 应当 pass（或者 skip optional-dep tests）— 不应当因 optional dep 缺失而 fail。

## 根因

pet-id `pyproject.toml` 把 ultralytics + boxmot 等放 `[project.optional-dependencies] detector / tracker`，base `make test`（`pip install -e ".[dev]"`）不装 optional extras。但 `tests/backends/test_yolov10_detector.py` 顶层 `from purrai_core.backends.yolov10_detector import YOLOv10Detector` 触发 ultralytics import → collection error。

## 修复

两个 test 文件顶层加 `pytest.importorskip("ultralytics")` / `pytest.importorskip("boxmot")`：

```python
import pytest
pytest.importorskip("ultralytics")  # F015 fix
from purrai_core.backends.yolov10_detector import YOLOv10Detector
```

## Retest 证据 ✅

```bash
$ cd pet-id && make test
...
======================== 82 passed, 4 skipped in 8.93s =========================
```

base test 全过 + 2 个 backend 模块 4 个 test 优雅 skip。

## Follow-ups

1. ✅ commit + PR pet-id `fix/eco-validation-pet-id-tests-skip-optional-deps`
2. 加 `make test-all` target（装 `[all]` extras 然后跑全测）— 给开发者完整覆盖路径
3. CI ci.yml 也用 importorskip 同样适用

# pet-infra v1.0 设计文档

> 日期：2026-04-15
> 状态：已批准
> 范围：pet-infra 核心构建 + 全链路接入（pet-schema ~ pet-ota）

## 1. 概述

pet-infra 是 Train-Pet-Pipeline 的横切基础设施仓库，职责：

- **Python 包**：提供跨仓库共享的工程工具代码（logging、retry、设备检测、数据库基类、API client）
- **配置源**：维护 ruff/mypy、Makefile、dev 依赖的统一配置，各仓库通过 `make sync-infra` 同步
- **Docker 基础设施**：标准化开发环境、Label Studio、W&B
- **CI 模板**：提供 workflow 模板供各仓库复制调整
- **文档**：onboarding 指南、运维手册

### 与 pet-schema 的边界

| pet-schema | pet-infra |
|------------|-----------|
| 数据合同：Pydantic model、JSON schema、prompt 模板 | 工程基础设施：Docker、CI、lint、logging、retry |
| "数据长什么样" | "代码怎么跑起来" |
| 变更影响业务逻辑 | 变更影响构建/测试/部署方式 |

## 2. 目录结构

```
pet-infra/
├── src/pet_infra/                  # Python 包
│   ├── __init__.py
│   ├── logging.py                  # JSON structured logger
│   ├── retry.py                    # tenacity 标准配置封装
│   ├── device.py                   # CPU/GPU/MPS/API 后端检测
│   ├── store.py                    # 数据库访问基类
│   └── api_client.py              # 云端 teacher API 统一封装
├── shared/                         # 配置文件源（sync-infra 拉取）
│   ├── pyproject-base.toml         # ruff/mypy 共享配置
│   ├── Makefile.include            # 共享 Makefile targets
│   ├── requirements-dev.txt        # 共享开发依赖
│   └── .env.example                # 全局环境变量模板
├── docker/
│   ├── dev/
│   │   └── Dockerfile              # 统一开发环境镜像
│   ├── labelstudio/
│   │   └── docker-compose.yml
│   └── wandb/
│       └── docker-compose.yml
├── docker-compose.yml              # 根级一键启动
├── ci/
│   └── workflows/                  # CI workflow 模板（各仓库复制到自己的 .github/workflows/）
│       ├── schema_guard.yml        # pet-schema 专用：跨仓库 dispatch
│       ├── standard_ci.yml         # 通用 lint+test（合并了 data_pipeline/annotation_check/train_eval）
│       ├── quantize_validate.yml   # 需要真实设备，手动触发
│       └── release_gate.yml        # 发布前检查
├── scripts/
│   ├── setup_dev.sh                # 开发环境一键搭建
│   ├── lint.sh                     # ruff + mypy 封装
│   ├── check_deps.sh               # 跨仓库版本检查
│   └── sync_to_repo.sh             # sync-infra 实现
├── docs/
│   ├── DEVELOPMENT_GUIDE.md        # 已有，需更新
│   ├── onboarding.md               # 新成员上手指南
│   └── runbook.md                  # 运维排障手册
├── tests/                          # pet-infra 包测试
├── pyproject.toml                  # 包定义
├── params.yaml                     # 配置参数
├── Makefile
└── .github/
    └── workflows/
        └── ci.yml                  # 自身 CI
```

## 3. Python 包：`src/pet_infra/`

### 3.1 `logging.py` — JSON Structured Logger

- 基于 stdlib `logging` + 自定义 `JSONFormatter`
- 自动注入 `ts`、`level`、`repo` 字段
- 用法：`from pet_infra.logging import get_logger`
- 输出：`{"ts": "...", "level": "INFO", "repo": "pet-data", "event": "frame_annotated", ...}`

### 3.2 `retry.py` — Tenacity 标准配置

- 指数退避 2-30s，max 3 次
- 可选参数覆盖默认值
- 用法：`from pet_infra.retry import standard_retry`

### 3.3 `device.py` — 设备/后端检测

- 检测顺序：CUDA → MPS → CPU
- 额外支持 `"rknn"`（检测 `rknn_toolkit2`）和 `"api"` 作为 inference backend
- 通过环境变量 `INFERENCE_BACKEND` 可强制指定（优先级高于自动检测）
- 用法：`from pet_infra.device import detect_device`
- 返回值：`"cuda"` / `"mps"` / `"cpu"` / `"rknn"` / `"api"`
- 注：`"rknn"` 用于端侧推理（RK3576），训练/评估场景下通常为 cuda/mps/cpu

### 3.4 `store.py` — 数据库访问基类

- 默认引擎：SQLite（通过 `sqlite3` stdlib）
- 封装：连接管理（context manager）、事务（自动 commit/rollback）、基本 CRUD 模式
- 各仓库的 store.py 继承 `BaseStore`，提供 db_path 参数
- 与 Alembic 迁移集成：BaseStore 初始化时检查 migration 版本一致性
- 用法：`from pet_infra.store import BaseStore`

### 3.5 `api_client.py` — 云端 Teacher API 封装

- 统一接口：发送 prompt → 获取 teacher 回答（+ 可选 logprobs）
- 集成 `standard_retry`（自动重试 + HTTP 429 时尊重 `Retry-After` header）
- 可配置并发数上限（默认 10），防止 rate limit 和成本失控
- 支持多种 backend（OpenAI 兼容 API、vLLM 本地 API），通过统一接口切换
- HTTP client 统一使用 `httpx`（异步支持、现代 API）。DEVELOPMENT_GUIDE 中 `requests` 示例需同步更新
- 用法：`from pet_infra.api_client import TeacherClient`

### 3.6 版本与公共 API

- 版本定义在 `pyproject.toml` 的 `[project] version` 字段
- `__init__.py` 导出 `__version__`，供 `check_deps.sh` 比对已安装版本与最新 tag
- **向后兼容策略**：v1.x 不破坏已有公共 API；破坏性变更需 v2.0。公共 API 定义为五个模块的所有导出符号

### 包依赖

- 必须依赖：`tenacity`
- 可选依赖组 `[gpu]`：`torch`（device.py）
- 可选依赖组 `[api]`：`httpx`（api_client.py）
- 开发依赖组 `[dev]`：pytest、ruff、mypy（与 `shared/requirements-dev.txt` 保持一致，由 `pip-compile` 生成）
- 不引入其他重依赖

## 4. 共享配置与同步机制

### 4.1 `shared/` 目录

**`pyproject-base.toml`**：
```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = false
ignore_missing_imports = true
```

**`Makefile.include`**：共享 `lint`、`clean`、`sync-infra` targets。`setup` 和 `test` 各仓库自定义。
- 本地开发：`include ../pet-infra/shared/Makefile.include`（假设同级目录 checkout）
- CI 环境：`sync_to_repo.sh` 会将 Makefile.include 复制到仓库根目录，CI 步骤先 clone pet-infra 再运行 sync

**`requirements-dev.txt`**：由 `pip-compile` 从 `pyproject.toml` 的 `[dev]` extras 生成，保持与包定义一致。包含 pytest、ruff、mypy、tenacity 等。

**`.env.example`**：全局跨仓库环境变量模板（DB paths、API endpoints 等）。各仓库的 `.env.example` 在此基础上追加仓库特有变量。

### 4.2 `sync_to_repo.sh`

执行三件事：
1. 将 `pyproject-base.toml` 中 ruff/mypy 配置合并到当前仓库的 `pyproject.toml`（使用 `tomli`/`tomli_w` 解析，只覆盖 `[tool.ruff]` 和 `[tool.mypy]` 段；仓库可在 `[tool.ruff.per-file-ignores]` 或 `extend-select` 中添加自定义规则，sync 不会触碰这些段）
2. 检查 pet-schema 和 pet-infra 依赖是否落后最新 tag，输出警告
3. 改动体现在 git diff 中，不自动 commit

## 5. Docker 基础设施

### 5.1 `docker/dev/Dockerfile`

- 基于 Python 3.11 slim
- 预装 ruff、mypy、pytest、pip-compile 等开发工具
- 预装 pet-schema + pet-infra 包
- 不含 torch/vllm 等重依赖（各仓库按需装）

### 5.2 `docker/labelstudio/docker-compose.yml`

- Label Studio 服务 + PostgreSQL 后端
- 持久化卷存储标注数据

### 5.3 `docker/wandb/docker-compose.yml`

- W&B 本地 server（可选，也可用云端）

### 5.4 `docker-compose.yml`（根级）

- `docker compose up -d` 一键启动全部服务
- 可选择性启动单个服务（如 `docker compose up dev`）
- 挂载：`/workspace`（代码）、`/data`（共享数据）

### 5.5 Teacher/vLLM

暂不构建。72B 模型本地部署方案未定（可能走云端 API 蒸馏），确定后以独立 PR 补充。

> **与 DEVELOPMENT_GUIDE 的偏差**：DEVELOPMENT_GUIDE 5.8 节定义了 `docker/teacher/Dockerfile`，但实际开发中 teacher 部署方案尚未确定。本轮实现中将更新 DEVELOPMENT_GUIDE，将 teacher 相关部分标记为"待定——取决于本地部署 vs 云端 API 的最终决策"。

## 6. CI 工作流

### 6.1 策略

- CI workflow 放在各自仓库的 `.github/workflows/`
- pet-infra 的 `ci/workflows/` 提供模板参考（各仓库复制到自己的 `.github/workflows/` 后按需调整）
- DEVELOPMENT_GUIDE 原定 6 个独立 workflow，本设计合并为：`standard_ci.yml`（通用 lint+test，替代 data_pipeline/annotation_check/train_eval）+ `quantize_validate.yml`（需真实设备）+ `schema_guard.yml` + `release_gate.yml`。理由：各仓库 CI 步骤高度相似（lint→test），差异通过 params 和 pytest markers 区分，无需为每仓库单独维护 workflow
- 设备自适应：检测 runner 有无 GPU，自动跳过 `@pytest.mark.gpu` 测试

### 6.2 模板

**`schema_guard.yml`**（放入 pet-schema 仓库）：
- 触发：pet-schema main push
- 动作：`repository_dispatch` 到所有下游仓库
- 需要 `CROSS_REPO_TOKEN` secret

**`standard_ci.yml`**（各仓库通用，合并了原 data_pipeline/annotation_check/train_eval）：
- 触发：push to dev/main, PR to dev/main, repository_dispatch
- 步骤：checkout → setup Python 3.11 → install deps → ruff → mypy → pytest
- 特殊逻辑：pet-train 完成后可通过 `repository_dispatch` 自动触发 pet-eval CI

**`quantize_validate.yml`**（pet-quantize 专用）：
- 手动触发（workflow_dispatch），需要真实 RK3576 设备的 self-hosted runner
- 延迟测试、模型精度验证

**`release_gate.yml`**（发布前检查）：
- 手动触发（workflow_dispatch）
- 全量测试 + check_deps.sh + 兼容性报告

### 6.3 各仓库 CI 配置

| 仓库 | Workflow |
|------|----------|
| pet-schema | `schema_guard.yml` + `standard_ci.yml` |
| pet-data ~ pet-ota | `standard_ci.yml` + `repository_dispatch` 触发器 |
| pet-infra | 自身 `ci.yml` |

## 7. Scripts

### 7.1 `setup_dev.sh`

- 检查前置条件（Python 3.11、docker compose、git）
- Clone 所有仓库（如不存在）
- 各仓库 `make setup`
- 提示配置 `.env`
- 验证：各仓库 `make lint && make test`

### 7.2 `lint.sh`

- `ruff check . && mypy src/`
- 各仓库 Makefile 的 lint target 调用此脚本

### 7.3 `check_deps.sh`

- 扫描 `../pet-*/pyproject.toml`
- 报告 pet-schema 和 pet-infra 版本
- 对比最新 git tag，落后则警告
- 输出格式：表格

## 8. Docs

### 8.1 `onboarding.md`

- 前置条件清单
- 一步步 clone → setup → 跑通测试
- 指向 DEVELOPMENT_GUIDE 的深入阅读建议
- 常见 FAQ

### 8.2 `runbook.md`

- 常见问题与解决方案
- Secret 轮换流程（90 天周期）
- 紧急回滚步骤

### 8.3 测试策略（pet-infra 自身）

- `tests/test_logging.py`：验证 JSONFormatter 输出格式、字段完整性
- `tests/test_retry.py`：mock 外部调用，验证重试次数和退避行为
- `tests/test_device.py`：mock torch 可用性，验证检测逻辑各分支
- `tests/test_store.py`：使用内存 SQLite（`:memory:`），验证 CRUD 和事务
- `tests/test_api_client.py`：mock HTTP 响应，验证重试、429 处理、并发限制
- CI 中不需要 GPU，所有测试通过 mock 覆盖

### 8.4 `DEVELOPMENT_GUIDE.md` 更新

- 补充 pet-infra 包使用说明
- 补充 `make sync-infra` 流程
- 更新 pet-infra 目录结构
- Teacher/vLLM 部分标记为"待定"
- HTTP client 示例从 `requests` 统一为 `httpx`

## 9. 全链路接入

### 9.1 各仓库统一改动（pet-data ~ pet-ota）

1. `pyproject.toml` 加依赖 `pet-infra @ git+https://...@v1.0.0`
2. `Makefile` 加 `include ../pet-infra/shared/Makefile.include`
3. 替换自建 logger → `from pet_infra.logging import get_logger`
4. 替换自建 retry → `from pet_infra.retry import standard_retry`
5. 替换自建设备检测 → `from pet_infra.device import detect_device`（如有）
6. 删除重复的 Makefile target（lint/clean）
7. 删除自建 ruff/mypy 配置
8. 加 `.github/workflows/ci.yml`
9. 加 `repository_dispatch` 触发器

### 9.2 pet-schema 额外改动

- 加 `.github/workflows/schema_guard.yml`
- 加 `.github/workflows/ci.yml`
- 配置 `CROSS_REPO_TOKEN` secret

## 10. 版本与发布策略

### 发布方式

- 本地开发：`pip install -e ../pet-infra`
- CI / 正式依赖：`pet-infra @ git+https://github.com/Train-Pet-Pipeline/pet-infra.git@v1.0.0`
- 与 pet-schema 保持一致的发布模式

### 版本保鲜机制

1. **语义化版本 + 兼容范围约束**（`~=1.0`）
2. **`check_deps.sh` 检查版本新鲜度**：落后 1 minor 警告，落后 1 major 失败
3. **`schema_guard.yml` 触发链**：上游发版 → dispatch → 下游 CI 自动验证
4. **`make sync-infra` 同步时顺带检查版本**

### 发布顺序

1. pet-infra 完成 → tag v1.0.0
2. pet-schema 加 schema_guard → tag v1.1.0
3. pet-data ~ pet-ota 逐个接入 → 各自 minor bump
4. 全链路验证：改 pet-schema → 观察 dispatch 触发下游 CI

## 11. 优先级

1. **Python 包优先**：`src/pet_infra/` 五个模块，所有仓库的基础依赖
2. **Onboarding 环境**：Docker dev 环境、setup_dev.sh、onboarding.md
3. **共享配置与同步**：shared/ 目录 + sync_to_repo.sh + check_deps.sh
4. **CI 模板**：schema_guard + standard_ci + quantize_validate + release_gate
5. **全链路接入**：各仓库替换自建代码、加 CI workflow
6. **Teacher 待定**：72B 本地部署 vs 云端 API 确定后再建

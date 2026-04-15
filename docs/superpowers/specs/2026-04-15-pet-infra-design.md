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
│   └── templates/                  # CI workflow 模板
│       ├── schema_guard.yml        # pet-schema 专用
│       ├── standard_ci.yml         # 标准 lint+test
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
- 额外支持 `"api"` 作为 inference backend（通过环境变量 `INFERENCE_BACKEND=api` 指定）
- 用法：`from pet_infra.device import detect_device`
- 返回值：`"cuda"` / `"mps"` / `"cpu"` / `"api"`

### 3.4 `store.py` — 数据库访问基类

- 封装连接管理、事务、基本 CRUD 模式
- 各仓库的 store.py 继承 `BaseStore`
- 用法：`from pet_infra.store import BaseStore`

### 3.5 `api_client.py` — 云端 Teacher API 封装

- 统一接口：发送 prompt → 获取 teacher 回答（+ 可选 logprobs）
- 集成 `standard_retry`（自动重试 + rate limit 处理）
- 支持多种 backend（OpenAI 兼容 API、vLLM 本地 API）
- 用法：`from pet_infra.api_client import TeacherClient`

### 包依赖

- 必须依赖：`tenacity`
- 可选依赖：`torch`（device.py）、`httpx`（api_client.py）
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

**`requirements-dev.txt`**：pytest、ruff、mypy、tenacity 等共享开发依赖。

**`.env.example`**：全局环境变量模板（API keys、paths 等变量名，无实际值）。

### 4.2 `sync_to_repo.sh`

执行三件事：
1. 将 `pyproject-base.toml` 中 ruff/mypy 配置合并到当前仓库的 `pyproject.toml`（只覆盖工具配置段）
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

## 6. CI 工作流

### 6.1 策略

- CI workflow 放在各自仓库的 `.github/workflows/`
- pet-infra 的 `ci/templates/` 提供模板参考
- 各仓库复制模板后按需调整
- 设备自适应：检测 runner 有无 GPU，自动跳过 `@pytest.mark.gpu` 测试

### 6.2 模板

**`schema_guard.yml`**（放入 pet-schema 仓库）：
- 触发：pet-schema main push
- 动作：`repository_dispatch` 到所有下游仓库
- 需要 `CROSS_REPO_TOKEN` secret

**`standard_ci.yml`**（各仓库通用）：
- 触发：push to dev/main, PR to dev/main, repository_dispatch
- 步骤：checkout → setup Python 3.11 → install deps → ruff → mypy → pytest

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

### 8.3 `DEVELOPMENT_GUIDE.md` 更新

- 补充 pet-infra 包使用说明
- 补充 `make sync-infra` 流程
- 更新 pet-infra 目录结构
- Teacher/vLLM 部分标记为"待定"

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

1. **Onboarding 优先**：Docker dev 环境、setup_dev.sh、onboarding.md 先行
2. **CI 跟进**：schema_guard + standard_ci 模板
3. **Teacher 待定**：72B 本地部署 vs 云端 API 确定后再建

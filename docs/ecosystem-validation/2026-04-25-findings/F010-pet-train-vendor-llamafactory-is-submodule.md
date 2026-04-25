# F010 — pet-train `vendor/LLaMA-Factory` 实际是 submodule（与 docs 矛盾）

| | |
|---|---|
| 发现时间 | 2026-04-26 00:57 |
| 发现 phase | Phase 1.3 SFT — `ModuleNotFoundError: No module named 'llamafactory'` |
| severity | MEDIUM — docs misleading + 安装流程缺一步 |
| 状态 | **FIXED on rental**（`git submodule update --init` + `pip install -e ./vendor/LLaMA-Factory`）；正式 fix 走 B-batch（更新 docs + bootstrap） |
| 北极星受影响维度 | — |

## 复现

```bash
git clone https://github.com/Train-Pet-Pipeline/pet-train.git
cd pet-train && pip install -e ".[dev]"
python -c "from llamafactory.train.tuner import run_exp"
# → ModuleNotFoundError: No module named 'llamafactory'
```

## 根因

`.gitmodules` 显示 vendor/LLaMA-Factory 是 git submodule（指向 hiyouga/LLaMA-Factory.git），不是 vendored copy。

但：
- `pet-infra/docs/gpu-session-readiness-2026-04.md §4.1` 写"pet-train vendors LLaMA-Factory under `vendor/LLaMA-Factory/` (not a submodule)"
- 用户 memory `feedback_no_manual_workaround` 关联的 V1 部署文档假设它是 vendored
- pet-train pyproject 没把 LLaMA-Factory 列入 dev install dependencies（也没 `[tool.setuptools.packages.find]` 包含 vendor/）

普通 `pip install -e .[dev]` 不会装 LF。fresh clone + install 后，`from llamafactory ...` 必然失败。

## 修复

### 选 A：保持 submodule + 修 docs/bootstrap
- 更新 `gpu-session-readiness-2026-04.md` 移除 "not a submodule" 错描述
- pet-train `Makefile setup` target 加 `git submodule update --init --recursive vendor/LLaMA-Factory && pip install -e ./vendor/LLaMA-Factory`
- bootstrap_rental.sh 同步加这 2 行

### 选 B：vendor 真正 vendoring（drop submodule）
- 把 LLaMA-Factory 源码复制进 pet-train（accepting forking maintenance burden）
- 更新 pyproject `packages.find` 包含 vendor/
- 优点：clone 即用；缺点：新 LF 版本需手工 sync

### 选 C：pip dependency
- pet-train pyproject [project.dependencies] 加 `llamafactory @ git+https://...@<pin>`
- 优点：标准 pip 流程；缺点：失去 vendor 局部修改的能力（如未来定制 LF）

按 spec §4.6：
- 测试精神：A 修流程（rental 已解决）符合 zero-bypass
- 北极星：A 不影响；B 加 vendoring burden 减 Pluggability；C 让 pet-train 不再控制 LF 版本
- 工程：A 最小变更，符合 YAGNI

**推荐 A**。已在 rental 上手工执行；正式 fix 走 PR。

## Retest（fix 完）

```bash
git clone .../pet-train.git
cd pet-train && make setup  # 应自动 init + install LF
python -c "from llamafactory.train.tuner import run_exp; print('OK')"
```

## Follow-ups

1. B-batch PR `fix/pet-train-makefile-init-llama-factory-submodule` + bootstrap_rental.sh 同步
2. PR 修 gpu-session-readiness-2026-04.md "not a submodule" 错描述
3. CI 加 fresh-clone 测试（bootstrap 在 fresh image 跑通）

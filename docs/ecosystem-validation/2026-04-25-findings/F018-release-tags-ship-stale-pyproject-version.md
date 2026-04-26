# F018 — release tag 装出来 `importlib.metadata.version()` 返回旧版本（pyproject.toml 未 bump）

| | |
|---|---|
| 发现时间 | 2026-04-26（rental 续卡 session） |
| 发现 phase | Post-rental followup；`pet-infra/.github/workflows/cross-repo-smoke-install.yml` regression |
| severity | **STRUCTURAL** — `importlib.metadata.version()` 返回错误值，跨仓 version-pin 检查会被悄悄旁路；release tag 与 PEP 621 metadata 失同步是 ecosystem 完整性失守 |
| 状态 | OPEN — fix-forward 走 5 仓 patch release + 9 仓 prevention guard |
| 北极星受影响维度 | Extensibility（plugin 间 version probe 不可信）+ Comparability（artifact 版本号说谎） |

## 复现命令

```bash
# pet-id v0.2.1 为例：
pip install "pet-id @ git+https://github.com/Train-Pet-Pipeline/pet-id@v0.2.1"
python -c "import importlib.metadata as im; print(im.version('pet-id'))"
# 实际：0.2.0  ← 与 tag 不符
# 期望：0.2.1
```

或离线：

```bash
cd pet-id && git show v0.2.1:pyproject.toml | grep '^version'
# version = "0.2.0"  ← BUG
```

## 实际行为

5 仓共 7 个 release tag 的 `pyproject.toml::project.version` 与 tag 名不一致：

| repo | tag | tag 上 pyproject | 应为 |
|---|---|---|---|
| pet-id | v0.2.1 | 0.2.0 | 0.2.1 |
| pet-annotation | v2.2.0 | 2.1.1 | 2.2.0 |
| pet-train | v2.1.0 | 2.0.2 | 2.1.0 |
| pet-train | v2.2.0 | 2.0.2 | 2.2.0 |
| pet-eval | v2.4.0 | 2.3.0 | 2.4.0 |
| pet-infra | v2.7.0 | 2.6.0 | 2.7.0 |
| pet-infra | v2.8.0 | 2.6.0 | 2.8.0 |

后果在 `pet-infra/.github/workflows/cross-repo-smoke-install.yml` 中显形 — install matrix 期望 `pet-id==0.2.1`，但 `importlib.metadata.version("pet-id")` 返回 `0.2.0`。run 24944289481（PR #89）4/8 矩阵 job FAIL：

```
FAIL: pet-id=='0.2.0' but matrix pin is '0.2.1'
FAIL: pet-train=='2.0.2' but matrix pin is '2.2.0'
FAIL: pet-eval=='2.3.0' but matrix pin is '2.4.0'
FAIL: pet-annotation=='2.1.1' but matrix pin is '2.2.0'
```

正确的 4 仓（pet-schema / pet-data / pet-quantize / pet-ota）通过 — 它们的 release PR 历史上恰好一直 bump 了 pyproject。

## 期望行为

每个 release tag 应满足 `pyproject.toml::project.version == git_tag_name.lstrip('v')`。这是 PEP 621 / PyPA 标准约定，也是 `importlib.metadata.version()` 唯一正确数据源。

## 根因

两层失守：

1. **流程层**：F008–F016 一轮 14 个修复全是源码 fix，release PR 走 dev → main 路径时无人 bump pyproject。CI 也无 guard 在 release PR 或 tag push 上拦住 stale pyproject。
2. **检测层**：`cross-repo-smoke-install.yml` 是唯一现存能抓到这个的 CI，但它只跑在 pet-infra 仓，且依赖 `compatibility_matrix.yaml` 已被同步更新；matrix 不更新整条链就盲。

更深一层：F008–F016 的 retro 已经标记"plugin 接口落地时没真实跑过就发布"是结构性流程 bug；F018 是同款流程 bug 的另一面 — release artifact 没 verify 就发布了。

## 修复

**Fix-forward** 而非 re-tag（tag immutable 是契约；不能把别人已 pull 的 v0.2.1 改语义）。

### Per-repo: bump pyproject + ship 新 patch tag

| repo | 旧 tag | 新 tag | pyproject 改动 |
|---|---|---|---|
| pet-id | v0.2.1 | v0.2.2 | 0.2.0 → 0.2.2 |
| pet-annotation | v2.2.0 | v2.2.1 | 2.1.1 → 2.2.1 |
| pet-train | v2.2.0 | v2.2.2 | 2.0.2 → 2.2.2（注：v2.2.1 release PR #33 已 merge to main 但同样 stale，跳号到 v2.2.2 一并修） |
| pet-eval | v2.4.0 | v2.4.1 | 2.3.0 → 2.4.1 |
| pet-infra | v2.8.0 | v2.9.0 | 2.6.0 → 2.9.0（PR #89 增量补丁） |

### 防回归：每仓加 `.github/workflows/release-version-consistency.yml`

trigger:
- `push: tags: ['v*']` — tag 推上来必须立刻验证 pyproject 匹配
- `pull_request: branches: [main]` — release PR 标题含 `release(repo): vX.Y.Z` 时验证 pyproject 已 bump 至 vX.Y.Z

实现一句话 bash：`python - <<EOF; import tomllib; assert tomllib.load(open('pyproject.toml','rb'))['project']['version'] == os.environ['EXPECTED']; EOF`

部署 9 仓：5 broken 仓和 patch release PR 一起 ship；4 correct 仓单独走 guard-only 小 PR。

### compatibility_matrix.yaml 增量

`docs/compatibility_matrix.yaml` 2026.11 行刷新到新 patch tag（v0.2.2 / v2.2.1 / v2.2.2 / v2.4.1 / v2.9.0）。

## Retest 证据（待补）

待 PR chain 全 ship 后回填：
- [ ] 每仓 `pip install <repo>@v<new>` 后 `importlib.metadata.version()` 与 tag 一致
- [ ] pet-infra `cross-repo-smoke-install` on dev 全绿
- [ ] `release-version-consistency.yml` 在 pet-infra 首仓 dry-run 通过

## Follow-ups

1. 把 release PR template 加一行 "**[ ] pyproject.toml::project.version bumped to match release tag**" — DEVELOPMENT_GUIDE §release flow 同步
2. 此 finding 与 retro 已标记的"plugin 接口落地无端到端跑"是同源流程 bug — 下一次 retro 把"release artifact 自验证"列入 hardcoded checklist
3. 长期：考虑 `setuptools-scm` 等动态 version 方案（pyproject.toml 直接从 git tag 派生），从根本上消除 drift；当前 fix 是流程兜底，不是数据消除

# F002 — AutoDL 默认 .condarc 用废弃 tuna pkgs/free + libmamba solver 触发 conda 24.4 崩溃

| | |
|---|---|
| 发现时间 | 2026-04-25 21:40 |
| 发现 phase | Phase 0 / step 0.2 conda env 创建 |
| severity | LOW（rental 环境问题，非生态 bug） |
| 状态 | **FIXED**（bootstrap_rental.sh 加自检 + 重写 .condarc） |
| 北极星受影响维度 | — |

## 复现命令

rental 上 fresh user：

```bash
cat ~/.condarc   # 含 anaconda/pkgs/free（已废弃）
/root/miniconda3/bin/conda create -n pet-pipeline python=3.11 -y
```

## 实际行为

```
INFO conda.gateways.repodata:conda_http_errors(244): Unable to retrieve repodata
  (response: 404) for https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/linux-64/current_repodata.json
JSONDecodeError: Expecting value: line 1 column 1 (char 0); got ""
AttributeError: type object 'Solver' has no attribute 'user_agent'
An unexpected error has occurred. Conda has prepared the above report.
```

## 期望行为

`conda create` 应当成功，使用现存的 main channel。

## 根因

1. AutoDL 镜像默认 `~/.condarc` 中包含 `https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/`，此频道 2024 年起已被 Anaconda 弃用，tuna 镜像随之 404
2. conda 24.4.0 默认 `solver=libmamba` 但当前镜像未装 libmamba 后端 → fallback 路径触发 `Solver.user_agent` AttributeError
3. 错误链显示 conda 内部 JSONDecodeError 但未告知用户真实原因（"frequently disabled channel" 应当 graceful fallback）

## 修复

bootstrap_rental.sh step 0.2 增加自检：
- 若 `~/.condarc` 含 `anaconda/pkgs/free` → 重写为只用 pkgs/main + 强制 `solver: classic`
- conda create 加 `CONDA_NO_PLUGINS=true` 防止 libmamba 残留

commit: `feat(pet-infra): apply bootstrap fixes from F002+F003 findings`

## Retest 证据

修复后再跑 bootstrap step 0.2：

```bash
$ CONDA_NO_PLUGINS=true conda create -n pet-pipeline python=3.11 -y
...
Executing transaction: ...working... done
#
# To activate this environment, use
#     $ conda activate pet-pipeline
```
✅ 干净通过。

## 不修生态本身

此问题属于 AutoDL rental 环境配置缺陷，不在 pet-* 9 仓 scope 内。pet-infra 唯一可做的就是**在 bootstrap 脚本里自检+绕开**，已完成。

## Follow-ups

无 — rental 结束后不需要进一步动作。

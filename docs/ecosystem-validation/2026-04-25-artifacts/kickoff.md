# Rental Kickoff Cheatsheet — 2026-04-25

> rental 启动后按此 sheet 一键开干；不需要重读 spec / plan。
> 全部 step 完成后进 plan Part B Phase 1。

---

## 0. 用户在本地（laptop）准备

```bash
# 0.a 确保 select_data_subset.py 已在本地跑过，manifest 在 pet-infra repo 内
ls /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra/docs/ecosystem-validation/2026-04-25-artifacts/data-subset-manifest.json

# 0.b push feature 分支到远端
cd /Users/bamboo/Githubs/Train-Pet-Pipeline/pet-infra
git push -u origin feature/eco-validation-design-2026-04-25

# 0.c 准备 rental 凭证：
#   - GH_TOKEN (gh auth token 或 PAT，repo scope)
#   - ANTHROPIC_API_KEY
```

---

## 1. SSH 进 rental + 准备 env vars

```bash
# rental 上：
export GH_TOKEN=<your-github-pat>
export ANTHROPIC_API_KEY=<your-anthropic-key>
export WORKSPACE=/workspace
export HF_HOME=$WORKSPACE/hf-cache
```

> 注意：env var 永远 `export`，**绝不**写到 git tracked 文件。`echo $ANTHROPIC_API_KEY` 也不要打全。

---

## 2. 拉 pet-infra（拿到 plan + bootstrap script）

```bash
mkdir -p $WORKSPACE && cd $WORKSPACE
git clone "https://x-access-token:${GH_TOKEN}@github.com/Train-Pet-Pipeline/pet-infra.git"
cd pet-infra
git checkout feature/eco-validation-design-2026-04-25
```

---

## 3. 跑 bootstrap

```bash
bash docs/ecosystem-validation/2026-04-25-artifacts/bootstrap_rental.sh 2>&1 | tee /tmp/bootstrap.log
```

预期：约 15-30 min，最后一行 `bootstrap COMPLETE`。

---

## 4. 把数据子集 scp 到 rental

```bash
# 在本地 laptop（不是 rental）：
scp -r /Users/bamboo/Githubs/Purr-Sight/data \
    user@<rental-ip>:/workspace/raw_data/raw

# 改 manifest 用相对路径校验：rental 上跑 verify
cd /workspace/pet-infra
PET_DATA_ROOT=/workspace/raw_data/raw python -c "
import json, hashlib
from pathlib import Path
m = json.load(open('docs/ecosystem-validation/2026-04-25-artifacts/data-subset-manifest.json'))
root = Path('/workspace/raw_data/raw')
n = 0
for s in m['samples']:
    p = root / s['rel_path']
    assert p.exists(), p
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == s['sha256'], (p, h, s['sha256'])
    n += 1
print(f'verified {n} samples sha256 match')
"
```

> 决策：如 scp 太慢/不便，可直接在 rental 上 `git clone https://github.com/Bambooshooting/Purr-Sight.git` 然后用相同 manifest verify（前提 Purr-Sight 是 public repo）。

---

## 5. 启动 Phase 1 — 按 plan Part B 顺序执行

打开 `docs/ecosystem-validation/2026-04-25-plan.md` Part B Phase 1 → 步骤 B1.1-B1.7 顺序执行。

每步完成：
1. 把 log 摘录 append 到 `docs/ecosystem-validation/2026-04-25-report.md` 对应章节
2. `git add docs/ecosystem-validation/`
3. `git commit -m "phase1.X: <step name> done"`
4. 后台 cron 每 15 分钟自动 push（不用手动 push）

---

## 6. 收尾

按 plan Part C 走（C1 北极星自评 / C2 retro / C3 B-batch PR / C4 通知用户）。

最后一步：用户操作关闭 rental 实例（节流费用）。

---

## 紧急情况

- **Bootstrap fail at step X.Y**：log 复制 → 写 finding `F00X-bootstrap-X-Y.md` → 30 min 内不能修则按 plan §5.3 "fail-fast 退租"
- **rental 实例突然终止**：cron 已每 15 分钟 push；最坏丢 15 min 工作；重新 ssh 进来从最近 commit 接着干
- **Anthropic API 调用失败**：先 retry → 切 Doubao（改 params.yaml） → 写 finding

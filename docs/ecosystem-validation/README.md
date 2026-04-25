# Ecosystem Validation 索引

每次"在卡上跑一遍真实生态"的实战验证记录。每次一组以日期前缀命名的同名文件。

---

## 2026-04-25 — 第一次完整生态实战验证

主目的：**Hardening 主**（zero-bypass / find→fix→retest）+ Acceptance 副 + Exploration 副。
范围：CUDA 训练 / eval 路径全 9 仓；不覆盖 RK3576 端侧（Phase 5 待硬件）。

| 文档 | 用途 | 状态 |
|---|---|---|
| [2026-04-25-design.md](2026-04-25-design.md) | 设计 spec（critic review 2 轮通过：APPROVED-WITH-FIXES → 已应用） | READY-FOR-USER-REVIEW |
| [2026-04-25-plan.md](2026-04-25-plan.md) | 实施计划（critic v2 review APPROVED-WITH-FIXES → 已应用） | READY-FOR-USER-REVIEW |
| 2026-04-25-report.md | 实战 living doc（rental 期间持续追加） | TBD |
| [2026-04-25-findings/](2026-04-25-findings/) | 每个 finding 单文件 | 0 |
| [2026-04-25-artifacts/](2026-04-25-artifacts/) | data manifest / loss curve / metric 截图 | 0 |

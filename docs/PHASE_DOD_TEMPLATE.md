# Phase DoD Template v1

任何 Phase/子 Phase 结束前必须逐项勾选：

## 1. 代码交付
- [ ] 所有 PR merged 到 main
- [ ] 所有仓库 tag 到 matrix 行锁定版本
- [ ] compatibility_matrix.yaml 新行已提交

## 2. CI 全绿
- [ ] plugin-discovery / integration-smoke / compatibility-matrix-smoke

## 3. 测试
- [ ] 单测覆盖新 plugin
- [ ] smoke recipe 三档（tiny/mps/small）至少 tiny 在 PR gate 绿

## 4. 文档同步
- [ ] DEVELOPMENT_GUIDE.md 对应章节更新
- [ ] matrix_history 追加发布条目

## 5. North Star §0.2.1 自检（DEBT-4）
四维度各打分（1-5）并给证据：
- [ ] 可插拔性（Pluggability）：新模型/新 modality 是否只加 plugin 不改核心？
- [ ] 灵活性（Flexibility）：配置能否纯 Hydra override 不改代码？
- [ ] 可扩展性（Extensibility）：新增 registry 成员是否无需改 orchestrator？
- [ ] 可对比性（Comparability）：同一 recipe 切不同 plugin 指标同格式？

任一维度 < 3 分本 Phase 不通过，必须 rework。

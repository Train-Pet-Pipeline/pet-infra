# 2026-04-27 续租 session — rental retest evidence artifacts

> 这些工件在 rental shutdown 前从 AutoDL 卡上拉下来，作为 F021/F022/F023/F024/F025/F026/F027 的 **真测 evidence**，绑定到本仓 git 历史防丢失。

## 目录结构

```
clearml-evidence/    F022 + F027 ClearML scalar 真出图
sft-evidence/        SFT 真训 LF outputs（F022 metric capture 数据源）
dpo-evidence/        DPO 真训 LF outputs（F023 rewards 数据源）
replay-evidence/     F012/F021 replay + F024 drift cards
vlmeval-evidence/    VLMEval real eval gold set + 60 sample full SFT JSONL
```

## clearml-evidence/

| 文件 | 内容 |
|---|---|
| `clearml_lf_train_loss.png` | LF SFT 8 步 train/loss 曲线（0.59→0.38 真在学）+ Summary aggregate=0.5182 dashed |
| `clearml_lf_sft_curves.png` | 4-panel：train/loss + grad_norm + learning_rate（cosine） + epoch |
| `clearml_F027_tiny_test.png` | tiny_test trainer 单点 train_loss=0.957（F027 fix 最初验证）|
| `clearml_system_monitor.png` | CPU/GPU/memory 系统监控（ClearML 自动采集）|
| `clearml_LF_SFT_with_per_step.zip` | ClearML offline session — task 元数据 + log + metrics.jsonl，可 import 到真 ClearML server 看 web UI |

证 F022（card.metrics 抓 train_loss）+ F027（runner 把 metrics forward 到 ClearML scalar reporter）端到端工作。

## sft-evidence/

| 文件 | 用途 |
|---|---|
| `sft_clearml_all_results.json` | LF 输出的 aggregate metrics — F022 fix 读这个 |
| `sft_clearml_trainer_state.json` | 含 log_history per-step 数据 — F023 fix 读这个 |

## dpo-evidence/

| 文件 | 用途 |
|---|---|
| `dpo_all_results.json` | DPO aggregate（无 rewards/*）|
| `dpo_trainer_state.json` | log_history 含 step 5 末态 rewards/margins=0.502, rewards/chosen=0.135, rewards/rejected=-0.366 — **F023 fix 抓这里** |

## replay-evidence/

| 文件 | 用途 |
|---|---|
| `cards/replay_test_train_8c00fb92.json` | F021 fix verified — `resolved_config_uri` + `hydra_config_sha` 真填了 |
| `cards/replay_test_train_8c00fb92_resolved_config.yaml` | 对应 resolved recipe yaml；replay 用 sha256 校验它 |
| `F024-drift-cards/` | F024 cross-commit drift test 的 card — git_shas 真有 9 仓 hyphenated keys |

## vlmeval-evidence/

| 文件 | 用途 |
|---|---|
| `gold_set_v2.jsonl` | 5 sample 手挑 gold set（doubao 标的）— VLMEval real eval 喂入 |
| `sft_v2_60samples.jsonl` | 60 sample 全集（30 doubao + 30 claude）— F019 验证 `images` 字段 60/60 populated 的源 |

## Reproduce 关键命令

ClearML SFT smoke：
```bash
# 在 rental 同等环境
export CLEARML_OFFLINE_MODE=1
python -c "from clearml import Task; Task.set_offline(True); Task.init(project_name='pet-pipeline', task_name='smoke')"
# 然后跑 LF SFT with report_to=clearml
```

VLMEval real eval：
```bash
pet run recipes/replay_test.yaml  # 或 LF SFT recipe → 产生 trained adapter
# 然后传 card.checkpoint_uri (post F025) 给 vlm_evaluator + gold_set_v2.jsonl
```

详见 `docs/ecosystem-validation/2026-04-25-report.md` Part B。

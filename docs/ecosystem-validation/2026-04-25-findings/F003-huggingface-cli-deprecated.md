# F003 — `huggingface-cli` 命令已 deprecated，需用 `hf`

| | |
|---|---|
| 发现时间 | 2026-04-25 21:48 |
| 发现 phase | Phase 0 / step 0.4.7 HF model preload |
| severity | MEDIUM（bootstrap 脚本错） |
| 状态 | **FIXED**（bootstrap_rental.sh step 0.4.7 改用 `hf` 命令） |
| 北极星受影响维度 | — |

## 复现命令

```bash
huggingface-cli download Qwen/Qwen2-VL-2B-Instruct --local-dir $HF_HOME/qwen2vl2b
```

## 实际行为

```
[90mHint: Examples:
  hf auth login
  hf download unsloth/gemma-4-31B-it-GGUF
  hf upload my-cool-model . .
  ...
[0m
```

命令"成功"但什么也没下载（旧 cli 已变成 stub 打印 hint 转引导用户用新命令）。

## 期望行为

下载到 `$HF_HOME/qwen2vl2b/` 含 `*.safetensors` 模型权重。

## 根因

`huggingface_hub >= 0.27` 把 `huggingface-cli` 命名改为 `hf`（2025 Q1 重构）。bootstrap_rental.sh 写的时候参考了老文档/老脚本，没跟上。

## 修复

bootstrap_rental.sh step 0.4.7：
- `huggingface-cli download ...` → `hf download ...`
- 增加 `pip install --quiet 'huggingface_hub[cli]>=0.27'` 保证 `hf` 可用
- 加判断：若已有 `*.safetensors` 跳过

commit: `feat(pet-infra): apply bootstrap fixes from F002+F003 findings`

## Retest 证据

修复后再跑 step 0.4.7：

```bash
$ hf download Qwen/Qwen2-VL-2B-Instruct --local-dir /root/autodl-tmp/hf-cache/qwen2vl2b
Fetching 14 files: 100%|██████████| 14/14 [...]
$ ls /root/autodl-tmp/hf-cache/qwen2vl2b/*.safetensors
model-00001-of-00002.safetensors
model-00002-of-00002.safetensors
```

## Follow-ups

无 — bootstrap 已是 idempotent，下次跑就走 `hf`。

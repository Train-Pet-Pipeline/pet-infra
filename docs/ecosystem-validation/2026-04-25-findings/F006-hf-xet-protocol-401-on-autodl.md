# F006 — HF xet protocol 401 Unauthorized on AutoDL turbo proxy

| | |
|---|---|
| 发现时间 | 2026-04-25 23:00 |
| 发现 phase | Phase 0 / step 0.4.7 HF 模型预下载（重试中） |
| severity | LOW（rental 环境 / 第三方 deps，非生态 bug；workaround 已就绪） |
| 状态 | **WORKED-AROUND**（`HF_HUB_DISABLE_XET=1` + 普通 HTTP fallback） |
| 北极星受影响维度 | — |

## 复现命令

```bash
source /etc/network_turbo  # AutoDL 学术加速
pip install hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1
hf download Qwen/Qwen2-VL-2B-Instruct --local-dir <path>
```

## 实际行为

```
RuntimeError: Data processing error: File reconstruction error: CAS Client Error: Request error:
HTTP status client error (401 Unauthorized), domain:
https://cas-server.xethub.hf.co/v1/reconstructions/b9fa8...
```

## 期望行为

下载完成 4GB safetensors。

## 根因

HF Hub 的新 xet 协议（CAS-based content-addressable storage，2025 年 Q3 推出）需访问 `cas-server.xethub.hf.co`。AutoDL 学术加速代理（`/etc/network_turbo` 设置 `http_proxy=http://10.37.1.23:12798`）转发到 xethub 域名时返回 401（推测：代理没配 xethub 白名单或 auth 头被剥）。

## Workaround

```bash
export HF_HUB_DISABLE_XET=1   # 走传统 HTTP 而非 xet
unset HF_HUB_ENABLE_HF_TRANSFER  # 同时关 hf_transfer 因为它强依赖 xet
hf download ...
```

## 不修生态本身

属 AutoDL 环境 / huggingface_hub 第三方依赖问题。pet-infra 唯一可做的：bootstrap_rental.sh step 0.4.7 加上 `HF_HUB_DISABLE_XET=1` 默认设置，让所有 AutoDL rental 跑通。

## Follow-ups

- B-batch fix：bootstrap_rental.sh export `HF_HUB_DISABLE_XET=1`
- 上游报 bug 给 AutoDL：学术加速代理缺 xethub 转发
- 文档化为 rental 已知坑（ecosystem-validation README）

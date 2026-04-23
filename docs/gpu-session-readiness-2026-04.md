# GPU Rental Session — Readiness Report

**Date:** 2026-04-23
**Matrix release:** `2026.10-ecosystem-cleanup`
**Ecosystem state:** post-Phase-9 (all 9 repos tagged + synced dev↔main)
**Author:** Claude Opus 4.7 + user

---

## 1 — Ecosystem snapshot

### Per-repo versions (from `compatibility_matrix.yaml:2026.10-ecosystem-cleanup`)

| Repo | Version | Tag on main | CI status |
|---|---|---|---|
| pet-schema | 3.2.1 | v3.2.1 | green |
| pet-infra | 2.6.0 | v2.6.0 | green (+ Phase 10 PR chain below) |
| pet-data | 1.3.0 | v1.3.0 | green |
| pet-annotation | 2.1.1 | v2.1.1 | green |
| pet-train | 2.0.2 | v2.0.2 | green |
| pet-eval | 2.3.0 | v2.3.0 | green |
| pet-quantize | 2.1.0 | v2.1.0 | green |
| pet-ota | 2.2.0 | v2.2.0 | green |
| pet-id | 0.2.0 | v0.2.0 | green (first-ever CI shipped Phase 9) |

Cross-repo smoke install (matrix 2026.10 end-to-end install order contract):
**7/7 matrix jobs green** on `feature/eco-matrix-2026.10` workflow_dispatch
(<https://github.com/Train-Pet-Pipeline/pet-infra/actions/runs/24825933856>).

---

## 2 — Local conda `pet-pipeline` env — freeze highlights

Captured on MacOS darwin 25.3.0 with torch 2.11.0 + MPS backend available; GPU rental session expected to target CUDA-backed torch.

### Key ecosystem deps in current env

```
pet-infra @ git+...@cd3f60d  (ahead of v2.6.0 main — ecosystem sweep was tagged during the session; local env tracks dev)
pet-eval / pet-train / pet-quantize / pet-ota / pet-id — editable installs, not in pip freeze
pet-data / pet-annotation / pet-schema — mixed install modes

torch==2.11.0
torchaudio==2.11.0
torchvision==0.26.0
transformers==4.57.6
accelerate==1.9.0
pydantic==2.12.5
numpy==2.2.6
scipy==1.15.3
clearml==1.18.0
hydra-core==1.3.2
mmengine-lite==0.10.7
mmpose==1.3.2
torchreid==0.2.5
boxmot==18.0.0
ultralytics==8.4.37
```

### Drift from Phase 0 baseline

- `torch` 2.8/2.9 → **2.11.0** (pet-eval + pet-train + pet-quantize declared `>=2.1`, so no constraint violation; Phase 5 GPU session must verify 2.11 works on the rented H100/A100/etc.).
- `transformers` 4.37 → **4.57.6** (pet-eval declared `>=4.37` so OK; Phase 5 hardware bring-up for Qwen2-VL should re-verify against the latest transformers API).
- `pydantic` 2.0/2.5 → **2.12.5** (no deprecation warnings from our models in current tests).
- `rknn-toolkit2` / `rkllm` — NOT installed locally; both CI envs use `PET_ALLOW_MISSING_SDK=1`. **Rental target likely also lacks RK SDKs** (they're vendor-specific to Rockchip boards, not Nvidia). The rental session is expected to focus on the **CUDA training/eval path**, not on RK quantization.

---

## 3 — Known-good recipes (runnable before rental)

Each of these should be smoke-runnable on the rental GPU **immediately** after `pip install`ing the matrix 2026.10 row + CUDA torch. If any of them fails on the rental, stop and report instead of working around.

| Recipe | Repo | Command | Covers |
|---|---|---|---|
| `smoke_foundation.yaml` | pet-infra | `pet run smoke_foundation --dry-run` | Stage DAG composition + compose merge |
| `cross_modal_fusion_eval.yaml` | pet-eval | `pet run cross_modal_fusion_eval` | 3 fusion evaluators end-to-end (**verified in Phase 6 ⑧ commit: `configs/fusion/weighted.yaml` exists and loads**) |
| SFT tiny trainer | pet-train | `pet run tiny_test` (plugin `tiny_test`) | CPU-only smoke; no rental needed to verify |
| Audio eval | pet-eval | `pytest tests/test_plugins/test_audio_evaluator.py -v` | Cross-repo runtime: pet_train.audio.inference |
| Quantize noop | pet-quantize | `pytest tests/test_noop_converter.py -v` | CONVERTERS registry contract |
| OTA local backend | pet-ota | `pytest tests/plugins/backends/ -v` | 3 OTA backends (moto + in-process HTTP) |

---

## 4 — Suspected risk spots (rental gotchas)

### 4.1 pet-train: LLaMA-Factory vendor

pet-train vendors LLaMA-Factory under `vendor/LLaMA-Factory/` (not a submodule). Fresh clone on the rental needs to pull the whole repo, not a shallow clone. `make setup` handles this via `pip install -e ".[dev]"`; don't `git clone --depth 1`.

### 4.2 pet-eval: 4-repo install order

pet-eval requires pet-schema + pet-infra + pet-train + pet-quantize **installed first** before `pip install pet-eval`. The 6-step CI order in `pet-eval/.github/workflows/ci.yml` is the contract. **Don't `pip install pet-eval` in an empty env** — it will fail at pet-train (which isn't on PyPI).

### 4.3 pet-quantize: RK SDK missing — set `PET_ALLOW_MISSING_SDK=1`

Rental GPU won't have `rknn-toolkit2` or `rkllm`. pet-quantize's `plugins/_register.py` raises on missing SDK unless this env var is set. Phase 7 ⑫ bonus fix made the `test_plugin_register_missing_sdk.py` regex match either SDK (rknn OR rkllm first).

### 4.4 Peer-dep last-wins re-pinning

pet-eval + pet-quantize + pet-ota's CI contains a Step-7 `--upgrade --force-reinstall --no-deps` of pet-schema + pet-infra because pet-quantize transitively pulls older pins. On the rental, replicate that step manually (or run the CI workflow locally via `act`).

### 4.5 pet-ota `quantize_validate.yml` (NOT a rental concern but note it)

Fixed in Phase 7 finding ② ③ — the workflow now calls `pytest src/pet_quantize/validate/ --device-id <serial>` and renamed input to `device_id`. **Phase-5 hardware bring-up on a real rk3576** is when this gets exercised; rental GPU session does NOT cover it.

---

## 5 — Recommended rental session order

1. **Bootstrap + verify env integrity** (30 min)
   - Clone 9 repos; `cd pet-infra && make setup`; `pip install 'pet-infra @ git+…@v2.6.0'`.
   - Run `cross-repo-smoke-install.yml` pattern locally across the 7 matrix repos. This catches any rental-specific install friction before burning rental hours on real training.

2. **Unit + integration tests** (15–30 min)
   - Every repo's `make test`. Goal: confirm baseline green on CUDA torch 2.11 (the matrix says `>=2.1`, so should be fine, but verify before assuming).

3. **Tiny training smoke** (30 min)
   - `pet run tiny_test` from pet-train. CPU-only trainer intended for exactly this pre-flight. ~2 min run.

4. **Real SFT recipe** (hours, depends on dataset size)
   - Use the mainline SFT recipe that was exercised on the prior RTX 5090 session (see `project_gpu_experiment` memory). **5 bugs were fixed** during that session; they should all still be fixed in the matrix 2026.10 pins. First sign of regression → stop, diff the fix commits, don't work around.

5. **E2E train → eval → quantize** (only if SFT green)
   - The `project_experiment_goal` memory pinned this as the end state.
   - quantize path will skip-with-warning because of missing RK SDKs; that's expected.

6. **W&B residue smoke** (2 min)
   - Every repo now has `no-wandb-residue.yml` guard. Confirm it passes on the rental's clone (should be idempotent).

---

## 6 — Phase-5 hardware session — NOT in scope of this rental

RK3576 validation (`quantize_validate.yml` against a real rk3576 ADB device) was deferred from Phase 4 retro §7 #1. This rental is **CUDA training / eval** only. Hardware items to keep deferred:

- RK3576 unit + self-hosted GitHub Actions runner.
- `pet_ota.release.canary_rollout` against actual devices.
- Real-hardware latency P95 numbers (current matrix has `latency_p95_ms: 4000` as a threshold target, not measurement).

Trigger conditions for Phase 5 are still:
1. RK3576 unit procured.
2. Self-hosted runner labeled `[self-hosted, rk3576]` online.
3. User explicit go-ahead.

---

## 7 — Sign-off checklist (user fills in during rental)

- [ ] Rental provider + GPU type + session ID: `________`
- [ ] CUDA torch version installed: `________`
- [ ] Matrix 2026.10 install order replicated cleanly: ✅ / ❌
- [ ] Every repo's `make test` green on the rental: ✅ / ❌
- [ ] `pet run tiny_test` green: ✅ / ❌
- [ ] SFT recipe green (with expected loss curve): ✅ / ❌
- [ ] Eval recipe against the trained checkpoint: ✅ / ❌
- [ ] Anomalies / bugs caught (record here — to be fixed in a post-rental phase, NOT in the rental session):
  - `________`

---

## Appendix A — Cross-repo smoke install CI fix (Phase 10 latent bugs)

**Context:** Phase 10 triggered `cross-repo-smoke-install.yml` for the first end-to-end validation; 3 latent workflow bugs surfaced and were fixed root-cause-in-phase (not deferred). All 7 matrix jobs green after the fix.

| Bug | Root cause | Fix |
|---|---|---|
| A | Parser heredoc uses `import yaml`; PyYAML not installed in base Python | Added `pip install --disable-pip-version-check pyyaml` step before parse |
| B | `pet_schema.__version__` doesn't exist (pet-schema's `__init__.py` doesn't export it) | Switched both "peer import check" and "version assert" to `importlib.metadata.version()` — works without `__version__` attribute |
| C | `pet-eval`'s 2nd-pass `pip install` tries to resolve `pet-train` + `pet-quantize` from PyPI (they're private git-only repos) | Added pet-eval-specific preinstall steps that fetch pet-train + pet-quantize from git at matrix pins before pet-eval's 2nd pass |

Verification: workflow_dispatch on `feature/eco-matrix-2026.10` → run 24825933856 → **7/7 green**.

**This is the kind of issue Phase-10 was meant to catch.** The workflow existed since Phase 2 but had never been triggered end-to-end (its `paths:` filter only fires on matrix changes, and matrix hadn't been updated in between). If we had deferred the fix to a "report" instead of fixing root-cause, the next matrix bump on the next ecosystem pass would have re-surfaced the same 3 bugs.

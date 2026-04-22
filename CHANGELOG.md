# Changelog

All notable changes to `pet-infra` are documented here.
Versions follow [Semantic Versioning](https://semver.org/) with `-rc<N>` suffixes for release candidates.

## 2.5.0-rc1 — 2026-04-22

### Added
- `S3Storage` plugin (P1-A) — boto3-backed, scheme `s3://`. Supports read/write/exists/iter_prefix.
- `HttpStorage` plugin (P1-B) — read-only CDN/static-server backend, schemes `http://` and `https://`. Bearer token + basic auth supported.
- Launcher dumps the resolved Hydra config per variation; `SweepResult.resolved_config_uri` is a `file://` URI to `<run_dir>/resolved_config.yaml` (P1-C).
- `LocalStorage` now also handles the `file://` scheme so launcher-emitted URIs round-trip through the STORAGE registry (P1-E).
- `ExperimentRecipe.variations` cartesian launcher with `link_to` co-iteration; ClearML per-variation tag injection of the form `variation:<axis>=<value>` (P1-D).
- Cartesian sweep preflight: warn at `>16` combinations, fail at `>64`; `PET_ALLOW_LARGE_SWEEP=1` env override (P1-D).
- `pet run --replay <card-id>` Tier-2 deterministic replay CLI (P1-E). sha256 fail-fast against `ModelCard.hydra_config_sha`; `git_shas` drift is warn-only.
- `--dry-run` flag on `pet run` (active when `--replay` is set; prints resolved YAML and exits 0) (P1-E).
- `no-wandb-residue` CI guard workflow (`.github/workflows/no-wandb-residue.yml`); positive-list scan of live code, configs, and active operational docs (P1-F).

### Changed
- `pet-schema` peer-dep pin already at `git+...@v2.4.0-rc1` (carried from P0-A; no change in this RC).
- `shared/.env.example`: replaced `WANDB_API_KEY` / `WANDB_PROJECT` with `CLEARML_API_HOST` / `CLEARML_API_ACCESS_KEY` / `CLEARML_API_SECRET_KEY` (P1-F).
- `docs/DEVELOPMENT_GUIDE.md`: 14 wandb references replaced with ClearML equivalents; W&B removal notice added (P1-F).
- `docs/onboarding.md`, `docs/runbook.md`: W&B onboarding/runbook entries replaced with ClearML equivalents (P1-F).

### Removed
- `wandb` Docker Compose service and `wandb-data` volume (P1-F).
- All live W&B prose and env-var defaults (P1-F). Historical specs/plans/audits/retrospectives intentionally retained as frozen records.

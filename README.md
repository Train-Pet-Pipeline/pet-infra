# pet-infra

Shared infrastructure for Train-Pet-Pipeline: Docker, CI, development environment (cross-cutting all repos).

## Recent (2026-04-27 续租 cycle)

- **v2.9.5** — docs patch: Part B final report, DEV_GUIDE §11.8 retro guardrail, and PR template rollout to all 9 repos.
- **v2.9.4** — F027 ClearML metrics forwarding + matrix 2026.11 bump.
- **v2.9.3** — F024 replay parents fix + F025/F026 finding docs.
- **v2.9.2** — F023 DPO reward collection fix.
- **v2.9.1** — F022 LLaMA-Factory metric capture fix.

Full finding docs at [`docs/ecosystem-validation/2026-04-25-findings/F017-F027`](docs/ecosystem-validation/2026-04-25-findings/). See DEV_GUIDE §11.8 for the retro guardrail (fixture-real test requirement introduced after this finding chain).

## Prerequisites

**pet-schema** is a peer dependency (β style per DEV_GUIDE §11). You must install it separately
before installing pet-infra, using the version pinned in `docs/compatibility_matrix.yaml`:

```bash
pip install 'pet-schema @ git+https://github.com/Train-Pet-Pipeline/pet-schema@<tag>'
pip install -e ".[dev]"
```

The shared `pet-pipeline` conda environment already provides pet-schema; no extra step is needed
when using that environment.

## License

This project is licensed under the [Business Source License 1.1](LICENSE) (BSL 1.1).
On **2030-04-22** it converts automatically to the Apache License, Version 2.0.

> Note: BSL 1.1 is **source-available**, not OSI-approved open source.
> Production / commercial use requires a separate commercial license.

![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1-blue.svg)

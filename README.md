# pet-infra

Shared infrastructure for Train-Pet-Pipeline: Docker, CI, development environment (cross-cutting all repos).

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

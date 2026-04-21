# ClearML Self-Hosted Docker Stack

## Purpose

Self-hosted ClearML server for teams that do not want to use ClearML SaaS.

**Local development default is `mode="offline"`** — no docker stack needed.
Offline mode writes artifacts and metrics to `~/.clearml/cache/` and is suitable
for solo dev and CI runs that do not need a shared experiment server.

This stack is for teams that want:
- A shared experiment server on-premise or in a private cloud
- Persistent cross-run comparison, artifact storage, and model registry

ClearML SaaS (`app.clear.ml`) is an alternative that also requires no self-hosting.

## Ports (spec §4.4)

| Service    | Port | Description         |
|------------|------|---------------------|
| webserver  | 8080 | Web UI              |
| apiserver  | 8008 | REST API            |
| fileserver | 8081 | Artifact file store |

## First-Time Setup

```bash
# Start the stack
make clearml-up

# Wait ~60s for services to be ready, then open:
# http://localhost:8080

# Register an admin account in the web UI.
# Navigate to: Settings → Workspace → Create new credentials
# Copy the Access Key and Secret Key.

# Copy and populate the env file:
cp docker/clearml/.env.example .env
# Edit .env: fill in CLEARML_API_ACCESS_KEY and CLEARML_API_SECRET_KEY

# Generate ~/.clearml/clearml.conf:
clearml-init
# Provide: http://localhost:8008 (API), http://localhost:8080 (web),
#          http://localhost:8081 (files), and your access/secret keys.
```

After `clearml-init`, set `mode="self_hosted"` (and `api_host` matching your
`CLEARML_API_HOST_URL`) in the ClearMLLogger config, or pass env vars directly.

## Starting and Stopping

```bash
make clearml-up    # docker compose up -d
make clearml-down  # docker compose down
```

Logs:

```bash
cd docker/clearml && docker compose logs -f apiserver
```

## Relationship to Python Plugin Discovery (§11)

The docker stack is independent of the Python peer-dep / plugin-discovery
mechanism. `ClearMLLogger` talks to the stack via the `CLEARML_API_HOST`
environment variable (set automatically when `mode="saas"` connects to
`app.clear.ml`, or when `mode="self_hosted"` and `api_host` is non-empty).

The stack does NOT need to be running for:
- `mode="offline"` (all local, no network calls)
- `mode="saas"` (talks to `app.clear.ml` directly)

## Volume Backup

Data is stored in named Docker volumes. To back up:

```bash
# Replace <vol> with: clearml-data, mongo-data, es-data, or clearml-files
docker run --rm \
  -v <vol>:/src \
  -v $(pwd)/backup:/dst \
  alpine tar czf /dst/<vol>.tar.gz -C /src .
```

To restore, reverse the tar command into the volume.

## Volumes

| Volume        | Contents                              |
|---------------|---------------------------------------|
| clearml-data  | API server state and task metadata    |
| mongo-data    | MongoDB database files                |
| es-data       | Elasticsearch indices                 |
| clearml-files | Uploaded artifacts and model files    |

## Troubleshooting

- **elasticsearch fails to start**: may need `vm.max_map_count=262144` on Linux.
  Run `sudo sysctl -w vm.max_map_count=262144` on the host.
- **webserver shows "connecting..."**: apiserver takes ~30-60s on first start.
  Check `docker compose logs apiserver`.
- **Port conflict**: edit `docker-compose.yml` left-hand ports if 8080/8008/8081
  are in use on your machine.

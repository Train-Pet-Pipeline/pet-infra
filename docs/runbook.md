# Ops Runbook

## Common Issues

### `make setup` fails

**Symptom:** pip-compile errors or missing system packages.

```
# Regenerate lock file
pip-compile requirements.in -o requirements.txt
# Then retry
make setup
```

If a system package is missing (e.g. `libpq-dev` for psycopg2), install it first:

```bash
sudo apt-get install -y libpq-dev build-essential
```

---

### Lint fails after `sync_to_repo.sh`

**Symptom:** `ruff` or `mypy` errors appear only after syncing shared configs.

1. Check which config was updated: `git diff ../pet-infra/shared/`
2. Run lint locally to see the exact violations: `make lint`
3. Fix violations in the target repo — do not edit the shared config.
4. If the shared config change is wrong, open a PR on `pet-infra` to fix it there.

---

### Schema version mismatch

**Symptom:** `ImportError` or `ValidationError` mentioning pet-schema.

```bash
# Check installed version
pip show pet-schema

# Check what the repo expects
grep pet-schema requirements.txt
```

Upgrade or downgrade to match the pinned tag. Never use `@main`.

If you need a new schema feature, update `pet-schema`, tag it, then bump all consumers in a coordinated PR.

---

### Docker won't start

**Symptom:** `docker compose up` exits immediately or port conflict.

```bash
# Check which process owns the port
lsof -i :8080

# Bring down stale containers
docker compose down -v

# Rebuild images
docker compose build --no-cache

# Check logs
docker compose logs labelstudio
```

For permission errors on volumes:

```bash
docker volume rm pet-infra_labelstudio-data pet-infra_labelstudio-pg
docker compose up
```

---

### DB locked / migration conflict

**Symptom:** `alembic.util.exc.CommandError: Can't locate revision` or SQLite lock errors.

- Never modify existing migration files — only add new ones.
- To fix a bad migration, write a new migration that reverts the change.

```bash
# Check current revision
alembic current

# Show migration history
alembic history --verbose

# Upgrade to latest
alembic upgrade head
```

For SQLite lock in tests: ensure no other process has the DB open.

---

### CI fails on `repository_dispatch`

**Symptom:** Downstream repo CI triggered by pet-schema push but fails with auth error.

1. Verify `CROSS_REPO_TOKEN` secret is set in both the triggering repo and the target repo org settings.
2. Token must have `repo` scope for private repos.
3. Check the `peter-evans/repository-dispatch@v2` step logs in pet-schema CI.
4. Re-run the failed workflow manually from the GitHub Actions UI.

---

## Secret Rotation (90-day cycle)

Secrets to rotate every 90 days:

| Secret | Where used | Steps |
|---|---|---|
| `CROSS_REPO_TOKEN` | All repos CI | Generate new PAT → update in GitHub org secrets → verify schema guard CI |
| `CLEARML_API_ACCESS_KEY` / `CLEARML_API_SECRET_KEY` | pet-train, pet-eval | Rotate in ClearML settings → update in repo secrets |
| `LABEL_STUDIO_TOKEN` | pet-annotation | Rotate in Label Studio → update in repo secrets |
| `DB_URL` / DB password | pet-data, pet-annotation | Rotate DB password → update connection string in secrets |

After rotating `CROSS_REPO_TOKEN`, trigger a test dispatch:

```bash
gh workflow run schema_guard.yml --repo Train-Pet-Pipeline/pet-schema
```

---

## Emergency Rollback

### Single repo rollback

```bash
# Find the last known-good tag or commit
git log --oneline -20

# Create a revert PR targeting dev
git checkout -b fix/emergency-revert-<repo>
git revert <bad-commit-sha> --no-edit
git push -u origin fix/emergency-revert-<repo>
gh pr create --base dev --title "fix(<repo>): emergency revert <bad-commit-sha>"
```

For OTA-deployed artifacts, use the `pet-ota` rollback endpoint:

```bash
python -m pet_ota.rollback --device-group all --to-version <previous-version>
```

### pet-schema cascade rollback

A bad pet-schema merge can break all downstream repos simultaneously.

1. Revert the bad commit on pet-schema main (requires 2 reviewer approvals).
2. Tag the revert commit: `git tag v<prev>-revert && git push --tags`
3. In each downstream repo, pin back to the previous schema tag in `requirements.txt`.
4. Open a coordinated PR across all repos — use the `release_gate.yml` workflow to validate before merging.
5. Monitor CI across all repos from the GitHub org Actions tab.

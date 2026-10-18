# LiteLLM update safety gate

## Decision: keep production manual

The 2026-10-18 evaluation did **not** enable a LiteLLM updater or change its production image. WUD automatic deployment remains limited to cAdvisor and Node Exporter. PostgreSQL and every other service remain excluded.

The proposed `main-stable` digest resolves to LiteLLM **1.106.0**, not a small rebuild of the installed **1.82.3**. The candidate was pulled by immutable digest and booted against an isolated, restored copy of the production database. Its migration tool found 213 migrations and applied pending migrations successfully. Internal readiness, liveliness, and authenticated `/v1/models` requests returned HTTP 200. No provider inference was attempted: the rehearsal network had no external egress. Expected cost-map DNS warnings fell back to the packaged local cost map; these are not evidence of a production networking problem.

Candidate: `ghcr.io/berriai/litellm@sha256:032817a17e58103834385125db8be1bdb20a5acb12c3cbf540b6705e1f6e2706`.

Release notes: https://github.com/BerriAI/litellm/releases/tag/v1.106.0 (published 2026-10-18). These include migration recovery changes and breaking behavior changes, including disabling stdio MCP servers by default. A successful smoke test is not proof of application-level backwards compatibility.

### Why unattended updates are blocked

- No recurring, fail-closed database backup is coupled to each WUD update. A one-time dump is insufficient for future floating-tag updates.
- The installed WUD 9.3.0 hook manager supports Docker `exec` hooks and chained triggers. Its Docker proxy deliberately has `EXEC=0`. Enabling arbitrary container exec just to run `pg_dump` would broaden the current trust boundary and is not part of this rollout.
- WUD's Compose `.back` file and old-container rollback do **not** reverse PostgreSQL migrations. The candidate actually migrated the rehearsal database, so this is an observed risk rather than a hypothetical one.

Before enabling automation, design and approve a fixed-purpose backup gate with durable restricted storage, explicit failure propagation before container replacement, retention, and a tested database-plus-image recovery path. Then use a separate `INCLUDEBYDEFAULT=false` LiteLLM trigger with `AUTO=false`, a narrowly writable app-only definition directory, and exact association checks. Do not mount the whole existing LiteLLM stack writable or opt its `db`/`prometheus` services in. After a fresh backup, verify a real production update manually before enabling `AUTO=true`.

## Verified backup

Run the reviewed helper explicitly as an administrator on the Docker VM:

```sh
python3 /home/corwin/Documents/docker-lab-server/litellm/backup.py
```

This is a manual tool, **not** an installed privileged service, sudo allowlist, or scheduled pre-update hook. It creates `/var/backups/litellm/<UTC timestamp>/` with mode 700 and private files with mode 600. It saves a custom-format database dump, the Compose definition, ignored `.env`, private container recovery metadata, and an immutable-image Compose override. Never commit or publish that directory.

The helper restores the dump into an isolated PostgreSQL container using the **same installed PostgreSQL image ID**, no published ports, no network, and disposable tmpfs storage. It compares every public table's row count with production before and after the dump; if writes occur during the window, it fails instead of claiming an exact comparison. It removes only its own test container afterward. See `wud/litellm-evaluation.json` for actual executed backup and rehearsal evidence.

Existing database credentials were moved from the tracked Compose definition to ignored mode-600 `.env` without changing their values or recreating either production container. They already existed in Git history; this change does not erase that history or rotate credentials. Schedule a separate coordinated rotation if required.

## Recovery runbook (destructive steps not exercised on production)

1. Disable the LiteLLM automatic trigger if one is ever introduced. Stop only the LiteLLM app and stop/drain any other writers to its database. Record the chosen backup directory and read its `verification.json`; require `restore_verified=true` and verify the dump checksum. Preserve the failed database separately before overwriting it.
2. To undo migrations, restore the **entire database**, not just the image. With all writers stopped, use PostgreSQL's administrative connection to database `postgres` to terminate remaining sessions on `litellm`, drop database `litellm`, and recreate it with owner `llmproxy`. This deliberately destroys post-backup data and requires a conscious recovery decision. Do not delete/recreate the PostgreSQL container or its volume.
3. Feed `database.dump` to `docker exec -i litellm-db-1 pg_restore -U llmproxy -d litellm --exit-on-error --no-owner --no-privileges`. The isolated restore drill exercised this exact restore format and options. Review errors before proceeding.
4. Restore the saved `.env` and definition if configuration changed. From the LiteLLM directory, use `/snap/bin/docker compose -p litellm -f docker-compose.yml -f <backup>/rollback.override.json up -d --no-deps --no-build --pull never litellm`. The override pins the original immutable image, which must still exist locally; do not prune recovery images. This command targets only the app, never PostgreSQL or Prometheus.
5. Check Docker health, `/health/readiness`, `/health/liveliness`, authenticated `/v1/models`, a deliberately approved inference request, and database contents before reopening traffic. Container health does not validate every stored model/provider integration.

Only the isolated dump/restore and candidate migration/API rehearsal were executed. No destructive recovery, production image replacement, provider billing call, or automatic LiteLLM rollout was performed.

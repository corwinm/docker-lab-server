# LiteLLM backup-gated updates

## Current deployment (2026-11-15)

Production remains **1.107.0**, from a verified unattended October update. The app
fragment currently uses `main-stable`, as persisted by WUD; it is not pinned to
the old digest mentioned in the historical rollout below. The installed local
image ID is `sha256:c7cafa430f1079e934a41bea54910df49936d9238d32236eca3afaa2142965a0`.
GHCR removed its historical index, so retained local images/backups are important.
See [registry workaround, native 48h image-age delay and TLS blocker](../wud/README.md#registry-retention-workaround-and-native-48h-delay-2026-11-15).
No app/database update was performed during this maintenance.

## Historical deployed decision (2026-10-18)

Production LiteLLM was updated through WUD from **1.82.3 to 1.106.0** after an isolated migration rehearsal, authenticated backup/restore proof, and a real fail-closed WUD transaction test. The app-only image fragment is pinned to `main-stable@sha256:032817a17e58103834385125db8be1bdb20a5acb12c3cbf540b6705e1f6e2706`. PostgreSQL remains on its existing PostgreSQL 16 image and container; Prometheus and all unapproved services are unchanged.

The separate `dockercompose.litellm` trigger is default-excluded and scoped only to `litellm-litellm-1`. Its synchronous global HTTP pre-hook must finish a durable backup and isolated restore verification before WUD starts its Compose transaction. Only the app-image fragment directory is writable by this trigger; the database, application secrets and full stack definition are not mounted into WUD. Exporter automation remains separate.

See `../wud/litellm-rollout.json`, `litellm-negative.json`, `litellm-update.json`, and the earlier `litellm-evaluation.json` for sanitized execution evidence. The update returned HTTP 200, replaced the app, completed migrations and passed readiness, liveliness, authenticated model listing (111 models), and Docker health. Unauthenticated model listing returned 401. No provider inference or billing call was made. Production schema changed from 58 tables/257 rows to 98 tables/369 rows, including migration bookkeeping.

**Remaining operational issues:** normal public HTTPS probes failed because the presented certificate is expired; TLS verification was not bypassed, and Traefik was not changed. Direct authenticated application probes succeeded. PostgreSQL reports an existing collation-version mismatch (database 2.36 versus installed library 2.41); no collation rebuild, database upgrade or unrelated repair was attempted. These are not claims of successful public-route acceptance.

Release behavior: 1.106.0 disables stdio MCP servers by default. The production MCP server table contained zero rows and there were no MCP environment overrides, so no configured stdio integration was identified. This is not an exhaustive provider compatibility test. Release notes: https://github.com/BerriAI/litellm/releases/tag/v1.106.0.

## Fixed-purpose gate

`litellm-backup-gate.service` installs root-owned code at `/usr/local/lib/litellm-backup/{gate.py,backup.py}` and binds only `172.26.0.1:9843`. It accepts POST `/backup` only from the internal WUD network with the ignored root-only bearer token, exact app identity and the expected pre-hook context. It accepts no shell commands, executable names, backup paths or arbitrary targets. Wrong auth/path/target each returned 403. WUD's socket proxy retains `EXEC=0`.

The gate returns 200 only after the helper reports `restore_verified=true`. Any backup, restore, row-count, free-space or deadline failure returns 503 and forbids replacement. In the real negative test, stopping only the gate caused the pending genuine app update to return 500; every container ID/image/state and the app image fragment stayed identical. The gate was restarted immediately afterward. The successful production update invoked a fresh backup at `/var/backups/litellm/20261018T173803Z` before replacing the app.

The helper requires root/no arguments and creates `/var/backups/litellm/<UTC timestamp>/` with mode 700 and files with mode 600. It saves the custom-format dump, full Compose definition, app-image fragment, ignored `.env`, private container recovery metadata and immutable old-image override. It restores into disposable tmpfs using the **installed PostgreSQL image ID**, no network or published ports, and `wud.watch=false`; it compares all public table row counts before/after and removes its own probe. Concurrent writes cause failure rather than a false exact-restore claim. Counts use a single `psql` exec per snapshot to avoid repeated Snap startup overhead. Files and directory entries are fsynced before acknowledgement.

The helper enforces a 450-second deadline, the HTTP gate 480 seconds and the WUD hook 510 seconds. It requires 2 GiB free on the backup filesystem. Backups and old images are **not automatically pruned**: retain the pre-migration recovery point and review retention manually. Exhausted storage fails closed. Never publish this backup directory. No broad sudo permission or Docker exec access was added to WUD. Snap Docker cannot execute under `NoNewPrivileges=true`; that incompatible setting was omitted after reproduction while retaining the unit's other sandbox controls.

Installation changes to root-owned code, unit or token must be administrative and reviewed. Source edits do not automatically change installed code. Keep the token in `/etc/litellm-backup/token` (root-owned mode 600) and the matching WUD bearer setting only in ignored mode-600 `wud/.env`. Do not put either value in commands, examples or Git.

Existing database credentials were externalized without rotation or rewriting existing Git history. Historical committed credentials require a separate coordinated rotation if desired.

## Database-plus-image recovery (destructive production restore not exercised)

1. Disable `WUD_TRIGGER_DOCKERCOMPOSE_LITELLM_AUTO`, recreate only WUD, and verify the live trigger is disabled. Stop only the LiteLLM app and drain all other database writers. Choose a backup whose `verification.json` has `restore_verified=true`, verify the dump checksum, and preserve the failed database separately before overwriting it.
2. A container/image rollback does **not** undo migrations. With all writers stopped, connect administratively to database `postgres`, terminate remaining `litellm` sessions, drop database `litellm`, and recreate it owned by `llmproxy`. This intentionally discards all post-backup data and requires an explicit recovery decision. Do not remove the database container or volume.
3. Restore the full dump with `/snap/bin/docker exec -i litellm-db-1 pg_restore -U llmproxy -d litellm --exit-on-error --no-owner --no-privileges < <backup>/database.dump`. This restore format/options were exercised only in isolated restore containers.
4. Restore the saved `.env`, full definition and `app/docker-compose.yml`. Snap Compose cannot read definitions directly under `/var/backups`; copy the saved `rollback.override.json` to an ignored root-owned mode-600 file `litellm/recovery.override.back` inside the checkout. From `litellm/`, run `/snap/bin/docker compose -p litellm -f docker-compose.yml -f recovery.override.back up -d --no-deps --no-build --pull never litellm`. The immutable original image must still exist locally. Never prune recovery images.
5. Verify health, readiness, liveliness, authenticated model listing, database contents and separately approved provider behavior before reopening traffic. Verify public TLS normally; do not disable certificate checks. Remove only the temporary override when recovery is complete. Re-enable automation only after resolving the failed update and rechecking associations.

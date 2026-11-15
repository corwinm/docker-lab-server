# WUD: Docker VM updates

WUD scans running containers hourly and sends batched Discord notifications once per detected update. Automatic deployment is explicitly opt-in: **cAdvisor and Node Exporter** include `dockercompose.exporters`; only the **LiteLLM app** includes the separate backup-gated `dockercompose.litellm` trigger. Databases, other applications, routing services, WUD itself and stopped containers remain manual.

## Automatic exporter updates

The Docker Compose trigger has `INCLUDEBYDEFAULT=false`, backups and health-gated rollback enabled, and image pruning disabled. It updates only the opted-in services and persists their new image versions in `../monitoring/docker-compose.yml`. Both exporters have health checks; Node Exporter probes its metrics endpoint. Stable version tags are selected, excluding prereleases.

The monitoring project now runs from this checkout, not the older `/home/corwin/docker-lab-server` checkout. Do not deploy that stale checkout over it. WUD mounts the monitoring directory and the app-image-only `../litellm/app` directory writable for version changes and adjacent `.back` rollback files. These runtime backups are ignored by Git. Review and commit future version changes deliberately; WUD never pushes Git changes.

WUD's Docker socket proxy is isolated on an internal network and has no published port. Container/image writes and network access are enabled because updates require them; other endpoint groups and exec are disabled. **This is not a per-container authorization firewall:** the deployment allowlist is enforced by WUD's trigger associations, not Docker permissions. Treat WUD and its authenticated admin API as privileged. Never add an update label to another service without approval.

Backups taken before enabling automation are under `/var/backups/wud-auto-t5kUIVkj`. WUD preserves the old container until replacement health succeeds, then removes the archive; previous images are retained. Compose rollback copies are `monitoring/docker-compose.yml.back`. For manual recovery, first disable the exporter trigger, restore the backed-up monitoring definition, then run `docker compose -p monitoring -f monitoring/docker-compose.yml up -d` from the repository root.

## Dashboard and credentials

The dashboard binds only to 127.0.0.1:3001. From the Mac:

```sh
ssh -N -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -J pi@192.168.1.2 -L 3001:127.0.0.1:3001 corwin@192.168.1.44
```

Open http://localhost:3001. Username is corwin. Bootstrap credentials and the Discord webhook URL are stored only in ignored mode-600 `.env`; retrieve credentials privately, never through chat. Change the bootstrap password through your WUD profile. Preserve ignored `store/` SQLite state during upgrades. `.env.example` contains blank secret fields, not working credentials.

Notifications use Discord #home. A real WUD notification was read back there during setup. Notifications do not mean an application was deployed: only the two approved exporters and backup-gated LiteLLM app have update triggers.

## Retired projects

Watchtower and ExcaliDash Compose definitions were removed from the repository. Their stopped containers and ExcaliDash data remain untouched. Retired definitions are archived under `/var/backups/retired-compose-epovH6wo`. OptiPlex's Scrypted updater is unchanged.

## Verification

WUD performed a real cAdvisor update from v0.60.5 to v0.60.6, persisted the Compose version, and accepted the healthy replacement. Node Exporter v1.12.1 was already current. Trigger association checks ensure only those two services receive the exporter updater. Both metrics endpoints and WUD health are verified after activation.

On this Snap Docker host, `no-new-privileges` prevented the socket-proxy entrypoint from executing; the option was omitted after reproducing that failure. The isolated proxy network remains in place.

## Backup-gated LiteLLM automation

The approved app-only rollout completed through WUD from 1.82.3 to 1.106.0. `dockercompose.litellm` is default-excluded, AUTO=true, backup/health rollback enabled and prune=false. Its synchronous HTTP pre-hook must successfully dump and restore-check PostgreSQL before every transaction; the HTTP trigger itself remains AUTO=false/default-excluded. The proxy retains EXEC=0. Only the app-image fragment is writable, not PostgreSQL or Prometheus. All eight monitored containers were checked; exactly the two exporters and LiteLLM app have updater associations.

A genuine available update returned HTTP 500 with the gate stopped; every container ID/image/state and the image fragment remained identical. After gate restart, a fresh backup preceded a real successful update. Readiness, liveliness, authenticated model listing and Docker health passed, with no provider inference. The source image fragment was explicitly pinned to the deployed immutable digest after the first digest-only update retained its floating tag. WUD never commits or pushes Git changes.

Public HTTPS acceptance is not green: the certificate is expired. TLS verification was not bypassed and Traefik was unchanged. PostgreSQL reports an existing collation mismatch. See [gate and DB-plus-image recovery](../litellm/README.md), [rollout evidence](litellm-rollout.json), [negative transaction](litellm-negative.json), [successful update](litellm-update.json) and [prior rehearsal](litellm-evaluation.json).

## Registry retention workaround and native 48h delay (2026-11-15)

The installed LiteLLM 1.107.0 image remains unchanged (local image ID
`sha256:c7cafa430f1079e934a41bea54910df49936d9238d32236eca3afaa2142965a0`).
Its historical GHCR index and platform manifests now return HTTP 404, while the
current `main-stable` tag resolves. WUD 9.3.0 otherwise aborts discovery when it
tries to resolve that deleted installed index. This is not an application outage.

`build-scanner-override.py` generates ignored `Docker.js.back` from the **locally
installed pinned WUD image**, validates its exact source SHA-256, and applies one
narrow scanner change. The generated file is mounted read-only into WUD. Rebuild
it before recreating WUD on another host:

```sh
cd wud
python3 build-scanner-override.py /snap/bin/docker
/snap/bin/docker compose config --quiet
/snap/bin/docker compose up -d --no-deps --pull never wud
/snap/bin/docker exec -i wud-wud-1 node < test-scanner-override.js
```

Only a 404 resolving **the installed LiteLLM index** on `ghcr.public` invokes the
workaround. It fetches the successfully resolved candidate's platform manifest
and compares its config digest with Docker's installed image ID. Equal config
identities are current; different identities retain the old repo digest as the
local comparison identity. The result still contains the candidate **manifest**
digest, never a config digest. Other images, candidate failures, auth failures,
rate limiting and unverifiable identities still fail discovery. No remote image
is pulled or application container recreated by discovery. This is a local
version-bound workaround, not an upstream WUD fix; review/remove it on WUD upgrade.

The watcher now has `WUD_WATCHER_VM_DELAY=48h`; all eight monitored entries inherit
it, with no label overrides. Native WUD measures **candidate image creation age**,
not publication time or time first seen. Missing or invalid candidate timestamps
**do not cool down**; this is not a fail-closed quarantine or a vulnerability scan.
It suppresses update availability and associated notifications during cooling.
The current LiteLLM candidate was created `2026-11-12T01:27:10.886Z`, so its 48h
window ended `2026-11-14T01:27:10.886Z`: it is already eligible, not cooling.
Deterministic tests of the actual installed WUD model prove suppression before
48h, eligibility at/after 48h, unchanged candidates, and missing/invalid dates.

During maintenance both Compose updater triggers were temporarily AUTO=false.
They return to AUTO=true only after scoped associations, discovery, delay tests
and backup-gate health are checked. The exact automatic allowlist remains
`cadvisor`, `node_exporter`, `litellm-litellm-1`; other five monitored containers
remain notification-only. LiteLLM's source now explicitly selects the already
effective persisted `batch` mode; its synchronous backup hook is unchanged.

WUD's unattended October update persisted `main-stable` in the writable app
fragment. That deliberate drift is retained and committed; do not pin it to the
newly discovered candidate or to the now-deleted historical index. A floating
source tag is not an immutable recovery guarantee. Recover using the retained
local image ID and private DB-plus-image backup procedure.

### Public TLS blocker

The presented LiteLLM certificate expired `2026-10-16T22:52:19Z`. Normal verified
HTTPS still fails. Traefik logs show Cloudflare DNS-challenge renewal failure
(403/9109 invalid access token); a read-only Cloudflare token verification also
returned HTTP 401 / code 1000, `Invalid API Token`. The ignored source token and
running token match, so this is not stale Compose environment drift. Renewal
requires a valid authorized Cloudflare token with the existing DNS challenge
permissions. No token rotation, ACME store modification, routing restart, image
upgrade, or TLS-verification bypass for application acceptance was attempted.
See `registry-cooldown-verification.json` for sanitized maintenance evidence.

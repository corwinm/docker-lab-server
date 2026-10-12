# WUD: Docker VM updates

WUD scans running containers hourly and sends batched Discord notifications once per detected update. Automatic deployment is explicitly opt-in: **only cAdvisor and Node Exporter** include `dockercompose.exporters`. All other applications, databases, routing services, WUD itself, and stopped containers remain manual.

## Automatic exporter updates

The Docker Compose trigger has `INCLUDEBYDEFAULT=false`, backups and health-gated rollback enabled, and image pruning disabled. It updates only the opted-in services and persists their new image versions in `../monitoring/docker-compose.yml`. Both exporters have health checks; Node Exporter probes its metrics endpoint. Stable version tags are selected, excluding prereleases.

The monitoring project now runs from this checkout, not the older `/home/corwin/docker-lab-server` checkout. Do not deploy that stale checkout over it. WUD mounts only the monitoring directory writable for version changes and adjacent `.back` rollback files. These runtime backups are ignored by Git. Review and commit future version changes deliberately; WUD never pushes Git changes.

WUD's Docker socket proxy is isolated on an internal network and has no published port. Container/image writes and network access are enabled because updates require them; other endpoint groups and exec are disabled. **This is not a per-container authorization firewall:** the deployment allowlist is enforced by WUD's trigger associations, not Docker permissions. Treat WUD and its authenticated admin API as privileged. Never add an update label to another service without approval.

Backups taken before enabling automation are under `/var/backups/wud-auto-t5kUIVkj`. WUD preserves the old container until replacement health succeeds, then removes the archive; previous images are retained. Compose rollback copies are `monitoring/docker-compose.yml.back`. For manual recovery, first disable the exporter trigger, restore the backed-up monitoring definition, then run `docker compose -p monitoring -f monitoring/docker-compose.yml up -d` from the repository root.

## Dashboard and credentials

The dashboard binds only to 127.0.0.1:3001. From the Mac:

```sh
ssh -N -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -J pi@192.168.1.2 -L 3001:127.0.0.1:3001 corwin@192.168.1.44
```

Open http://localhost:3001. Username is corwin. Bootstrap credentials and the Discord webhook URL are stored only in ignored mode-600 `.env`; retrieve credentials privately, never through chat. Change the bootstrap password through your WUD profile. Preserve ignored `store/` SQLite state during upgrades. `.env.example` contains blank secret fields, not working credentials.

Notifications use Discord #home. A real WUD notification was read back there during setup. Notifications do not mean an application was deployed: only the two approved exporters have an update trigger.

## Retired projects

Watchtower and ExcaliDash Compose definitions were removed from the repository. Their stopped containers and ExcaliDash data remain untouched. Retired definitions are archived under `/var/backups/retired-compose-epovH6wo`. OptiPlex's Scrypted updater is unchanged.

## Verification

WUD performed a real cAdvisor update from v0.60.5 to v0.60.6, persisted the Compose version, and accepted the healthy replacement. Node Exporter v1.12.1 was already current. Trigger association checks ensure only those two services receive the exporter updater. Both metrics endpoints and WUD health are verified after activation.

On this Snap Docker host, `no-new-privileges` prevented the socket-proxy entrypoint from executing; the option was omitted after reproducing that failure. The isolated proxy network remains in place.

#!/usr/bin/env python3
"""Manual pre-upgrade backup and isolated PostgreSQL 16 restore verification.
Run as root on the Docker VM. Does not deploy or restore production.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import subprocess
import time

D = '/snap/bin/docker'
REPO = Path('/home/corwin/Documents/docker-lab-server')

def docker(*args, **kwargs):
    return subprocess.run([D, *args], check=True, capture_output=True, timeout=30, **kwargs).stdout

def counts(name):
    # One exec per snapshot avoids repeated Snap startup overhead per table.
    sql = "SELECT format('SELECT json_build_array(%L, count(*)) FROM public.%I;', tablename, tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename\n\\gexec\n"
    output = docker('exec', '-i', name, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'llmproxy', '-d', 'litellm', '-At', input=sql.encode())
    return dict(json.loads(line) for line in output.decode().splitlines())

def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise SystemExit('Requires root and no arguments')
    def expired(*_):
        raise TimeoutError('Backup deadline exceeded')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(450)
    if shutil.disk_usage('/var/backups').free < 2 * 1024**3:
        raise RuntimeError('At least 2 GiB backup free space required')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest = Path('/var/backups/litellm') / stamp
    dest.mkdir(parents=True, mode=0o700)
    before = counts('litellm-db-1')
    state = json.loads(docker('inspect', 'litellm-litellm-1', 'litellm-db-1'))
    (dest/'containers.private.json').write_text(json.dumps(state))
    app_image = json.loads(docker('image', 'inspect', state[0]['Image']))[0]
    refs = [ref for ref in app_image.get('RepoDigests', []) if ref.startswith('ghcr.io/berriai/litellm@')]
    if not refs:
        raise RuntimeError('No immutable LiteLLM recovery image reference')
    (dest/'rollback.override.json').write_text(json.dumps({'services': {'litellm': {'image': refs[0], 'pull_policy': 'never'}}}, indent=2)+'\n')
    for name in ['docker-compose.yml', '.env']:
        shutil.copyfile(REPO/'litellm'/name, dest/name)
    if (REPO/'litellm/app/docker-compose.yml').exists():
        (dest/'app').mkdir(mode=0o700)
        shutil.copyfile(REPO/'litellm/app/docker-compose.yml', dest/'app/docker-compose.yml')
    dump = docker('exec', 'litellm-db-1', 'pg_dump', '-U', 'llmproxy', '-d', 'litellm', '-Fc')
    (dest/'database.dump').write_bytes(dump)
    image = state[1]['Image']
    probe = 'litellm-restore-check-'+stamp.lower()
    try:
        docker('run', '-d', '--name', probe, '--network', 'none', '--label', 'wud.watch=false', '--tmpfs', '/var/lib/postgresql/data:rw,size=512m', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-e', 'POSTGRES_USER=llmproxy', '-e', 'POSTGRES_DB=litellm', image)
        for _ in range(60):
            p = subprocess.run([D, 'exec', probe, 'pg_isready', '-U', 'llmproxy', '-d', 'litellm'], capture_output=True)
            if p.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Isolated restore database did not become ready')
        docker('exec', '-i', probe, 'pg_restore', '-U', 'llmproxy', '-d', 'litellm', '--exit-on-error', '--no-owner', '--no-privileges', input=dump)
        restored = counts(probe)
        after = counts('litellm-db-1')
        if before != restored or before != after:
            raise RuntimeError('Row counts changed during backup or restore did not match; retry at a quiet boundary')
        report = {'backup': str(dest), 'dump_bytes': len(dump), 'sha256': hashlib.sha256(dump).hexdigest(), 'tables': len(restored), 'rows': sum(restored.values()), 'restore_verified': True, 'app_image': state[0]['Image'], 'db_image': image, 'production_db_id': state[1]['Id']}
        (dest/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
        # Flush private recovery files and directory entries before acknowledging WUD.
        for path in dest.rglob('*'):
            if path.is_file():
                with path.open('rb') as f:
                    os.fsync(f.fileno())
        for path in [dest/'app', dest, dest.parent]:
            if path.exists():
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        print(json.dumps(report))
    finally:
        subprocess.run([D, 'rm', '-f', '-v', probe], capture_output=True, check=False)

if __name__ == '__main__':
    main()

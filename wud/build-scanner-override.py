#!/usr/bin/env python3
"""Build the narrow WUD 9.3.0 override from the pinned image; fail on upstream drift."""
import hashlib
import pathlib
import subprocess
import sys
EXPECTED = "87313ab18e7a3a9e76fb47dc3cb25ff30df6c65cc798f2cc5cc206e0a2fbd6ae"
IMAGE = "getwud/wud:9.3.0@sha256:58b1d93ab3b752ef83125b39d014dde8fadbed5be0cf6fbdee9ffa8d2ca72b32"
OLD = """                    const digestV2 = await registryProvider.getImageManifestDigest(imageToGetDigestFrom, container.image.digest.repo);
                    container.image.digest.value = digestV2.digest;"""
NEW = """                    try {
                        const digestV2 = await registryProvider.getImageManifestDigest(imageToGetDigestFrom, container.image.digest.repo);
                        container.image.digest.value = digestV2.digest;
                    }
                    catch (error) {
                        // Local workaround for GHCR retention deleting LiteLLM's installed index.
                        // Never hide a candidate failure, auth/rate-limit error, or another image's error.
                        if (error?.response?.status !== 404 ||
                            container.image.registry.name !== 'ghcr.public' ||
                            container.image.name !== 'berriai/litellm') {
                            throw error;
                        }
                        const candidateManifest = await registryProvider.callRegistry({
                            image: imageToGetDigestFrom,
                            url: `${imageToGetDigestFrom.registry.url}/${imageToGetDigestFrom.name}/manifests/${remoteDigest.digest}`,
                            headers: { Accept: 'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json' },
                        });
                        const configDigest = candidateManifest?.config?.digest;
                        const localImage = await this.dockerApi.getImage(container.image.id).inspect();
                        if (!/^sha256:[a-f0-9]{64}$/.test(configDigest || '') ||
                            localImage.Id !== container.image.id ||
                            !/^sha256:[a-f0-9]{64}$/.test(localImage.Id || '')) {
                            throw new Error('Cannot verify candidate/local config identity after historical-manifest 404');
                        }
                        // Config identity proves equality without re-fetching the removed index.
                        // For different configs retain the installed repo identity (not a config digest).
                        container.image.digest.value = configDigest === localImage.Id
                            ? remoteDigest.digest
                            : container.image.digest.repo;
                        logContainer.info('Historical LiteLLM manifest unavailable; compared candidate config against installed Docker image ID');
                    }"""
def apply(source):
    if hashlib.sha256(source.encode()).hexdigest() != EXPECTED or source.count(OLD) != 1:
        raise ValueError("Pinned WUD scanner source mismatch; review before rebuilding")
    return source.replace(OLD, NEW)
if __name__ == "__main__":
    docker = sys.argv[1] if len(sys.argv) > 1 else "/snap/bin/docker"
    source = subprocess.check_output([docker, "run", "--rm", "--pull", "never", "--label", "wud.watch=false", "--network", "none", "--entrypoint", "cat", IMAGE, "/home/node/app/dist/watchers/providers/docker/Docker.js"], text=True)
    target = pathlib.Path(__file__).with_name("Docker.js.back")
    target.write_text(apply(source))
    print("Built", target.name, hashlib.sha256(target.read_bytes()).hexdigest())

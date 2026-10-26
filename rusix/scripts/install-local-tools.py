#!/usr/bin/env python3
"""Extract packages pinned by pacman's existing database into the workspace.

No package hooks, system installation, database refresh, or sudo invocation.
The reviewed package lock is tracked at rusix/docs/packages.lock.
"""
import hashlib
import subprocess
import urllib.request

from rusix_paths import resolve_paths

paths = resolve_paths()
cache = paths.output / ".tools/packages"
dest = paths.tools
cache.mkdir(parents=True, exist_ok=True)
dest.mkdir(parents=True, exist_ok=True)
for line in (paths.project / "docs/packages.lock").read_text().splitlines():
    name, version, digest, url = line.split()
    if not url.startswith("https://") or len(digest) != 64:
        raise ValueError(f"Invalid package manifest entry: {name}")
    archive = cache / url.rsplit("/", 1)[1]
    print(f"Installing locally: {name} {version}", flush=True)
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".partial")
        urllib.request.urlretrieve(url, partial)
        partial.rename(archive)
    if hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != digest:
        raise ValueError(f"Checksum mismatch: {archive}")
    subprocess.run(["bsdtar", "-xf", str(archive), "-C", str(dest),
                    "--no-same-owner"], check=True)
print("Local packages extracted; no host package state was changed.")

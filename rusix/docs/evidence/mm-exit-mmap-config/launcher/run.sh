#!/usr/bin/env bash
# Disabled until root reviews the final clean routing checkpoint.
set -euo pipefail
ready=1
source_commit=8ec785568045a3cd2245e87d1854a7f5ab664ef3
base=/home/aaron/code/rusix
source_tree="$base/linux-mm-exit-mmap"
draft="$base/linux-out/mm-exit-mmap-config-draft"
out="$base/linux-out/mm-exit-mmap-config-001"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
[[ "$ready" == 1 && "$source_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'Final routing checkpoint/root approval pending' >&2; exit 2; }
[[ $(git -C "$source_tree" rev-parse HEAD) == "$source_commit" ]]
[[ -z $(git -C "$source_tree" status --porcelain) && ! -e "$out" ]]
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
mkdir "$out"
owned_cidfile="$out/container.cid"
finish() {
 status=$?
 trap - EXIT INT TERM
 if [[ -f "$owned_cidfile" ]]; then
  cid=$(cat "$owned_cidfile")
  if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then
   docker inspect "$cid" > "$out/container-inspect.json" 2> "$out/container-inspect.stderr" || status=1
   docker rm -f "$cid" >/dev/null 2>&1 || true
  fi
 fi
 printf '%s\n' "$status" > "$out/launcher.exit"
 exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' "$source_commit" > "$out/source.commit"
printf '%s\n' "$image" > "$out/image-id.txt"
sha256sum "$draft/run.sh" "$draft/check.py" "$draft/archive-inputs.py" "$draft/README.md" > "$out/launcher.sha256"
git -C "$source_tree" archive --format=tar "$source_commit" > "$out/source.tar"
sha256sum "$out/source.tar" > "$out/source-archive.sha256"
mkdir "$out/source" "$out/tmp" "$out/builds"
tar --no-same-owner --same-permissions -xf "$out/source.tar" -C "$out/source"
python3 -B "$draft/archive-inputs.py" --archive "$out/source.tar" --source "$out/source" --output "$out/archive-inputs.json"
docker image inspect "$image" > "$out/image-inspect.json"
# Snapshot is immutable to the container. No heavy-work lock is required for
# this explicitly authorized 1CPU/1GiB config-only job; no mutable source mount.
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --cidfile "$owned_cidfile" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 1g --memory-swap 1g --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$out/source,dst=/src,readonly" \
 --mount "type=bind,src=$draft,dst=/check,readonly" \
 --mount "type=bind,src=$out/archive-inputs.json,dst=/archive-inputs.json,readonly" \
 --mount "type=bind,src=$out/builds,dst=/out" \
 --mount "type=bind,src=$out/tmp,dst=/scratch" \
 --env TMPDIR=/scratch --env PYTHONDONTWRITEBYTECODE=1 \
 --env "RUSIX_CONFIG_SOURCE=$source_commit" --workdir /src "$image" \
 bash -c 'set -euo pipefail; dpkg-query -W > /out/packages.lock; clang --version > /out/clang-version.log; rustc --version --verbose > /out/rustc-version.log; bindgen --version > /out/bindgen-version.log; make --version > /out/make-version.log; python3 -B /check/check.py' \
 > "$out/container.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$out/container.exit"
[[ "$status" == 0 ]]
sha256sum -c "$out/launcher.sha256" > "$out/launcher-after.log"

#!/usr/bin/env bash
# PREPARED ONLY. Parent may launch after the serial pipeline and source freeze.
set -euo pipefail
source_tree=/home/aaron/code/rusix/linux-brd-owner
scripts=/home/aaron/code/rusix/linux-out/brd-owner-nosysfs-draft
output=${1:-/home/aaron/code/rusix/linux-out/lts-brd-owner-nosysfs-001}
image=sha256:0e0cfd724bde5c2a81cee61210c2a14a66ea72f679e1308125825e0463c67937
# Same serialization domain as the standard BRD/RCU matrices.
exec 9>/home/aaron/code/rusix/linux-out/.wait-owner-remaining.lock
flock -n 9 || { echo 'Another local kernel matrix holds the build lock.' >&2; exit 2; }
python3 - <<'PYIDLE'
import json, subprocess
ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
if ids:
    for container in json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)):
        for mount in container.get('Mounts', []):
            if mount.get('Destination') == '/src' and mount.get('Source', '').startswith('/home/aaron/code/rusix/linux'):
                raise SystemExit('Another kernel verification container is active')
PYIDLE
[[ ! -e "$output" && ! -L "$output" ]] || { echo 'Refusing existing output.' >&2; exit 2; }
[[ -c /dev/kvm ]] || { echo 'KVM required.' >&2; exit 2; }
[[ -z $(git -C "$source_tree" status --porcelain) ]] || { echo 'Freeze clean source first.' >&2; exit 2; }
revision=$(git -C "$source_tree" rev-parse HEAD)
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
mkdir "$output"
mkdir "$output/logs"
printf '%s\n' "$image" > "$output/logs/container-image-id.txt"
printf '%s\n' "$revision" > "$output/logs/launch-source.commit"
sha256sum "$scripts/run.sh" "$scripts/inner.sh" > "$output/logs/launcher.sha256"
set +e
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  --cpus 2 --memory 5g --memory-swap 5g --user "$(id -u):$(id -g)" \
  --device /dev/kvm --group-add "$(stat -c %g /dev/kvm)" \
  --mount type=bind,src=/home/aaron/code/rusix/linux/.git,dst=/home/aaron/code/rusix/linux/.git,readonly \
  --mount "type=bind,src=$source_tree,dst=/src,readonly" \
  --mount "type=bind,src=$scripts,dst=/plan,readonly" \
  --mount "type=bind,src=$output,dst=/out" \
  --env RUSIX_OUTPUT_ROOT=/out --env RUSIX_TOOLS_ROOT=/opt/no-local-overrides \
  --env RUSIX_QEMU_ACCEL=kvm --env "EXPECTED_SOURCE=$revision" \
  --workdir /src "$image" bash /plan/inner.sh > "$output/logs/container.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$output/logs/container.exit"
[[ "$status" == 0 ]] || exit "$status"
[[ $(cat "$output/logs/nosysfs.exit") == 0 ]]
[[ -s "$output/logs/nosysfs-result.txt" ]]
[[ $(git -C "$source_tree" rev-parse HEAD) == "$revision" ]]
[[ -z $(git -C "$source_tree" status --porcelain) ]]
sha256sum -c "$output/logs/launcher.sha256" > "$output/logs/launcher-after.log"

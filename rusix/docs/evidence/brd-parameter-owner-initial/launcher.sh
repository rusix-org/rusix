#!/usr/bin/env bash
# Prepared only: parent starts after wait-owner publication and BRD owner rebase.
set -euo pipefail
source_tree=/home/aaron/code/rusix/linux-brd-owner
output_root=/home/aaron/code/rusix/linux-out
outputs=(lts-brd-owner-kunit-001 lts-brd-owner-ext4-c-001 lts-brd-owner-ext4-rust-001)
profiles=(completion-rust brd-ext4-fixed-c brd-ext4-rust)
base_image=sha256:0e0cfd724bde5c2a81cee61210c2a14a66ea72f679e1308125825e0463c67937
ext4_image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
images=("$base_image" "$ext4_image" "$ext4_image")

# Share the remaining-matrix lock: no overlap with session 55629 or its successors.
exec 9>"$output_root/.wait-owner-remaining.lock"
flock -n 9 || { echo 'Wait-owner remaining matrix is still active.' >&2; exit 2; }
require_ready() {
    python3 - "$output_root" "$source_tree" <<'PYREADY'
import json, subprocess, sys
from pathlib import Path
out, source = Path(sys.argv[1]), sys.argv[2]
revisions = set()
for phase in ('debug', 'plain', 'ext4', 'server'):
    attempt = '002' if phase == 'debug' else '001'
    for kind in ('c', 'rust'):
        logs = out / f'lts-wait-owner-{phase}-{kind}-{attempt}' / 'logs'
        for marker in ('container.exit', 'ci.exit'):
            assert (logs / marker).read_text().strip() == '0', f'Unfinished wait-owner {phase}/{kind}'
        for status in logs.rglob('*.exit'):
            assert status.read_text().strip() == '0', f'Failed status {status}'
        builds = list(logs.glob('ci-*-build.*'))
        assert len(builds) == 1 and (builds[0] / 'build.exit').read_text().strip() == '0'
        revision = (logs / 'launch-source.commit').read_text().strip()
        assert (builds[0] / 'source-after.commit').read_text().strip() == revision
        assert not (builds[0] / 'source-after.status').read_bytes()
        revisions.add(revision)
assert len(revisions) == 1, 'Wait-owner matrix source mismatch'
def git(*args):
    return subprocess.check_output(['git', '-C', source, *args], text=True).strip()
main = git('rev-parse', 'rusix/main')
assert main == git('rev-parse', 'origin/rusix/main'), 'Publish local main before owner verification'
subprocess.run(['git', '-C', source, 'merge-base', '--is-ancestor', next(iter(revisions)), main], check=True)
subprocess.run(['git', '-C', source, 'merge-base', '--is-ancestor', main, 'HEAD'], check=True)
ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
if ids:
    for container in json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)):
        for mount in container.get('Mounts', []):
            assert not (mount.get('Destination') == '/src' and
                        mount.get('Source', '').startswith('/home/aaron/code/rusix/linux')), 'Another kernel verification container active'
PYREADY
}
require_ready

[[ -c /dev/kvm ]] || { echo 'KVM is required; no TCG fallback.' >&2; exit 2; }
[[ -z $(git -C "$source_tree" status --porcelain) ]] || { echo 'Source must be clean.' >&2; exit 2; }
source_revision=$(git -C "$source_tree" rev-parse HEAD)
# Preflight every output before starting any build, with no success reuse.
for i in "${!outputs[@]}"; do
    output="$output_root/${outputs[$i]}"
    python3 - "$output" "${profiles[$i]}" "${images[$i]}" <<'PY'
import hashlib, json, sys
from pathlib import Path
output, profile, image = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert {p.name for p in (output / 'logs').iterdir()} == {'cache-provenance.json', 'container-image-id.txt'}, 'Refusing reused/in-progress logs'
assert {p.name for p in (output / 'builds').iterdir()} == {f'ci-{profile}'}, 'Unexpected build/guest fixture'
assert not any((output / 'tmp').iterdir()), 'Output temporary directory is not fresh'
provenance = json.loads((output / 'logs/cache-provenance.json').read_text())
assert provenance['status'] == 'PREPARED_NOT_RUN'
assert provenance['destination_profile'] == profile
assert provenance['runtime_container_image'] == image
assert (output / 'logs/container-image-id.txt').read_text().strip() == image
for name, expected in provenance['copied_artifact_sha256'].items():
    with (output / name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, name
PY
    [[ $(docker image inspect --format '{{.Id}}' "${images[$i]}") == "${images[$i]}" ]]
done

# Sequential execution: one container, two CPUs and at most 5 GiB at a time.
for i in "${!outputs[@]}"; do
    output="$output_root/${outputs[$i]}"
    profile="${profiles[$i]}"
    image_id="${images[$i]}"
    [[ $(git -C "$source_tree" rev-parse HEAD) == "$source_revision" ]]
    [[ -z $(git -C "$source_tree" status --porcelain) ]]
    # noclobber provides a per-output launch claim even if another launcher races.
    require_ready
    (set -o noclobber; printf '%s\n' "$source_revision" > "$output/logs/launch-source.commit")
    git -C "$source_tree" rev-parse rusix/main > "$output/logs/launch-main.commit"
    args=(--env RUSIX_OUTPUT_ROOT=/out --env RUSIX_TOOLS_ROOT=/opt/no-local-overrides
          --env RUSIX_QEMU_ACCEL=kvm)
    if [[ "$profile" == brd-ext4-* ]]; then
        args+=(--env "RUSIX_EXT4_IMAGE_ID=$image_id")
    fi
    set +e
    docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
      --cpus 2 --memory 5g --memory-swap 5g --user "$(id -u):$(id -g)" \
      --device /dev/kvm --group-add "$(stat -c %g /dev/kvm)" \
      --mount type=bind,src=/home/aaron/code/rusix/linux/.git,dst=/home/aaron/code/rusix/linux/.git,readonly \
      --mount "type=bind,src=$source_tree,dst=/src,readonly" \
      --mount "type=bind,src=$output,dst=/out" \
      "${args[@]}" --workdir /src "$image_id" \
      bash rusix/ci/run.sh "$profile" > "$output/logs/container.log" 2>&1
    status=$?
    set -e
    printf '%s\n' "$status" > "$output/logs/container.exit"
    [[ "$status" == 0 ]] || { tail -60 "$output/logs/container.log" >&2; exit "$status"; }
    [[ $(cat "$output/logs/ci.exit") == 0 ]]
    [[ $(git -C "$source_tree" rev-parse HEAD) == "$source_revision" ]]
    [[ -z $(git -C "$source_tree" status --porcelain) ]]
done

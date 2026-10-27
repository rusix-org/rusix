#!/usr/bin/env bash
# Disabled until root review. Compile/readelf only; never execute guest binaries.
set -euo pipefail
base=/home/aaron/code/rusix
draft="$base/linux-out/vma-modify-fixtures-compile-final-draft"
source_tree="$base/linux-mm-copy-vma"
out="$base/linux-out/vma-modify-fixtures-compile-002"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
exec 9>"$base/linux-out/.vma-modify-fixture-compile.lock"
flock -n 9 || { echo 'Fixture compile already active' >&2; exit 2; }
python3 -B "$draft/preflight.py" --require-fresh > /dev/null
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
mkdir "$out"
finish_owned() {
 status=$?
 trap - EXIT INT TERM
 if [[ -f "$out/container.cid" ]]; then
  cid=$(cat "$out/container.cid")
  if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then
   docker inspect "$cid" > "$out/container-inspect.json" 2> "$out/container-inspect.stderr" || true
   docker rm -f "$cid" >/dev/null 2>&1 || true
  fi
 fi
 for name in init probe; do
  if [[ -f "$out/artifacts/$name" ]]; then chmod 0644 "$out/artifacts/$name"; fi
 done
 printf '%s\n' "$status" > "$out/launcher.exit"
 exit "$status"
}
trap finish_owned EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$out/evidence" "$out/artifacts" "$out/tmp"
cp -a "$draft/fixture" "$out/fixture"
cp "$draft/fixture-review.json" "$out/fixture/fixture-review.json"
python3 -B "$draft/preflight.py" > "$out/source-before.json"
sha256sum "$draft/run.sh" "$draft/preflight.py" "$draft/compile.py" "$draft/fixture-review.json" "$draft/README.md" > "$out/launcher.sha256"
docker image inspect "$image" > "$out/image-inspect.json"
printf '%s\n' "$image" > "$out/image-id.txt"
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --cidfile "$out/container.cid" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 1g --memory-swap 1g --pids-limit 128 --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$source_tree,dst=/source,readonly" \
 --mount "type=bind,src=$out/fixture,dst=/fixture,readonly" \
 --mount "type=bind,src=$draft/compile.py,dst=/compile.py,readonly" \
 --mount "type=bind,src=$out/evidence,dst=/out/evidence" \
 --mount "type=bind,src=$out/artifacts,dst=/out/artifacts" \
 --mount "type=bind,src=$out/tmp,dst=/out/tmp" --env TMPDIR=/out/tmp \
 "$image" python3 -B /compile.py > "$out/container.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$out/container.exit"
sha256sum -c "$out/launcher.sha256" > "$out/launcher-after.log"
python3 -B "$draft/preflight.py" > "$out/source-after.json"
cmp "$out/source-before.json" "$out/source-after.json"
exit "$status"

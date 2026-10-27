#!/bin/bash
set -euo pipefail
out=/home/aaron/code/rusix/linux-out/dup-mmap-constant-selection-001
source=/home/aaron/code/rusix/linux-mm-dup-mmap
old=/home/aaron/code/rusix/linux-out/dup-mmap-verification-001/rust
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
cleanup() { if [[ -f "$out/container.cid" ]]; then docker rm -f "$(cat "$out/container.cid")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker image inspect "$image" > "$out/image-inspect.json"
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --cidfile "$out/container.cid" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 2g --memory-swap 2g --pids-limit 128 --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$source,dst=/src,readonly" \
 --mount "type=bind,src=$old,dst=/out,readonly" \
 --mount "type=bind,src=$out/evidence,dst=/evidence" \
 --mount "type=bind,src=$out/tmp,dst=/tmp" --env PYTHONDONTWRITEBYTECODE=1 \
 "$image" bash -c 'set -euo pipefail
for tool in llvm-nm llvm-objdump llvm-ar llvm-readobj; do "$tool" --version > "/evidence/$tool-version.log"; done
python3 -B /src/rusix/scripts/verify-dup-mmap.py objects --profile mm-dup-mmap-rust --source /src --build /out/builds/ci-mm-dup-mmap-rust --evidence /evidence > /evidence/dup-mmap-selection.json
' > "$out/container.log" 2>&1
status=$?
printf '%s\n' "$status" > "$out/container.exit"
if [[ -f "$out/container.cid" ]]; then docker inspect "$(cat "$out/container.cid")" > "$out/container-inspect.json"; fi
exit "$status"

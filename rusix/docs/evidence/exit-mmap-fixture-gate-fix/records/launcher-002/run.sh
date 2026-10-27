#!/usr/bin/env bash
set -euo pipefail
base=/home/aaron/code/rusix
draft="$base/linux-out/exit-mmap-fixture-gate-reinspection-002-draft"
output="$base/linux-out/exit-mmap-fixture-gate-reinspection-002"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
python3 - "$draft" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);r=json.loads((p/'ready.json').read_text());assert r['enabled'] is True,'Read-only inspection awaits root review'
for name,value in r['draft_sha256'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==value,name
PY
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
common=$(git -C "$base/linux-mm-exit-mmap" rev-parse --path-format=absolute --git-common-dir)
mkdir "$output"
mkdir "$output/tmp"
cidfile="$output/container.cid"
cleanup() { if [[ -f "$cidfile" ]]; then local cid; cid=$(cat "$cidfile"); if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi; fi; }
trap cleanup EXIT
set +e
timeout --signal=TERM --kill-after=30s 5m docker run --cidfile "$cidfile" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 2g --memory-swap 2g --pids-limit 128 --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$common,dst=$common,readonly" \
 --mount "type=bind,src=$base/linux-mm-exit-mmap,dst=$base/linux-mm-exit-mmap,readonly" \
 --mount "type=bind,src=$base/linux-mm-exit-mmap-fix,dst=$base/linux-mm-exit-mmap-fix,readonly" \
 --mount "type=bind,src=$base/linux-out/mm-exit-mmap-verification-001/kunit-c,dst=$base/linux-out/mm-exit-mmap-verification-001/kunit-c,readonly" \
 --mount "type=bind,src=$draft,dst=$draft,readonly" \
 --mount "type=bind,src=$output,dst=$output" \
 --env "TMPDIR=$output/tmp" --env PYTHONDONTWRITEBYTECODE=1 \
 --env "RUSIX_PINNED_POSTCHECK_IMAGE=$image" --workdir "$base/linux-mm-exit-mmap" \
 "$image" python3 -B "$draft/reinspect.py" > "$output/result.json" 2> "$output/stderr.log"
status=$?
set -e
printf '%s\n' "$status" > "$output/inspection.exit"
if [[ -f "$cidfile" ]]; then docker inspect "$(cat "$cidfile")" > "$output/container-inspect.json"; fi
exit "$status"

#!/usr/bin/env bash
set -euo pipefail
base=/home/aaron/code/rusix
out="$base/linux-out/vma-lifecycle-gate-fix-001"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges --read-only --cpus 1 --memory 2g --memory-swap 2g --pids-limit 128 --user "$(id -u):$(id -g)" --mount "type=bind,src=$base/linux-vma-lifecycle,dst=/src,readonly" --mount "type=bind,src=$base/linux-out/vma-lifecycle-verification-001/rust,dst=/out,readonly" --mount "type=bind,src=$out,dst=/recheck" --env PYTHONDONTWRITEBYTECODE=1 --env TMPDIR=/recheck/tmp --workdir /src "$image" python3 -B /src/rusix/scripts/verify-vma-lifecycle.py objects --profile vma-lifecycle-rust --source /src --build /out/builds/ci-vma-lifecycle-rust --evidence /recheck/reinspection > "$out/actual-selection.json" 2> "$out/actual-selection.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$out/actual-selection.exit"
exit "$status"

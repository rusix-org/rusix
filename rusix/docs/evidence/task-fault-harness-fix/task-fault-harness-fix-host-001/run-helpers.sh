#!/bin/bash
set -euo pipefail
out=/home/aaron/code/rusix/linux-out/task-fault-harness-fix-host-001
fixture=/home/aaron/code/rusix/linux-task-faults/rusix/tests/task-construction-faults
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
cleanup() {
    if [[ -f "$out/helper.cid" ]]; then
        cid=$(cat "$out/helper.cid")
        docker rm -f "$cid" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --rm --cidfile "$out/helper.cid" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 512m --memory-swap 512m --pids-limit 128 --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$fixture/control_io.rs,dst=/control_io.rs,readonly" \
 --mount "type=bind,src=$fixture/guard.rs,dst=/guard.rs,readonly" \
 --mount "type=bind,src=$out,dst=/out" --env TMPDIR=/out/tmp \
 "$image" bash -c 'set -euxo pipefail
mkdir /out/tmp
/usr/bin/rustc --version --verbose > /out/rustc-version.log
/usr/bin/rustc --edition 2021 --test /control_io.rs -o /out/control-io-unit
/out/control-io-unit
/usr/bin/rustc --edition 2021 --test /guard.rs -o /out/guard-unit
/out/guard-unit
' > "$out/helper.log" 2>&1
status=$?
printf '%s\n' "$status" > "$out/helper.exit"
exit "$status"

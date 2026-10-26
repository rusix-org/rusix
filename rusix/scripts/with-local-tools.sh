#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -e "$root/linux/.git" && -e "$root/../../linux/.git" ]]; then
    root=$(cd -- "$root/../.." && pwd)
fi
export PATH="$root/.tools/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$root/.tools/root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$@"

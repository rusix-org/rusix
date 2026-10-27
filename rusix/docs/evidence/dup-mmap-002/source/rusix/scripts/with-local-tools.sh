#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/repo-paths.sh"
if [[ -d "$RUSIX_TOOLS_ROOT/usr/bin" ]]; then
    export PATH="$RUSIX_TOOLS_ROOT/usr/bin:$PATH"
fi
if [[ -d "$RUSIX_TOOLS_ROOT/usr/lib" ]]; then
    export LD_LIBRARY_PATH="$RUSIX_TOOLS_ROOT/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec "$@"

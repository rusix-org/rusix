#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Source this file; resolve paths without changing the caller's working directory.
rusix_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || return 1
RUSIX_SOURCE=$(cd -- "$rusix_script_dir/../.." && pwd -P) || return 1
rusix_git_root=$(git -C "$RUSIX_SOURCE" rev-parse --show-toplevel) || return 1
rusix_git_root=$(cd -- "$rusix_git_root" && pwd -P) || return 1
if [[ "$rusix_git_root" != "$RUSIX_SOURCE" ]]; then
    echo 'rusix scripts must live in the Git root at rusix/scripts.' >&2
    return 1
fi
RUSIX_PROJECT="$RUSIX_SOURCE/rusix"
# realpath -m accepts paths that do not exist yet, resolves symlink parents,
# and interprets relative overrides against the caller's current directory.
RUSIX_OUTPUT_ROOT=$(realpath -m -- "${RUSIX_OUTPUT_ROOT:-${RUSIX_SOURCE}-out}") || return 1
RUSIX_TOOLS_ROOT=$(realpath -m -- "${RUSIX_TOOLS_ROOT:-$RUSIX_OUTPUT_ROOT/.tools/root}") || return 1
export RUSIX_SOURCE RUSIX_PROJECT RUSIX_OUTPUT_ROOT RUSIX_TOOLS_ROOT
unset rusix_script_dir rusix_git_root

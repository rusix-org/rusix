#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -d "$root/linux/.git" && -d "$root/../../linux/.git" ]]; then
    root=$(cd -- "$root/../.." && pwd)
fi
test -d "$root/linux/.git" || { echo 'Linux checkout is missing' >&2; exit 1; }
mkdir -p "$root/linux/rusix/docs" "$root/linux/rusix/scripts"
cp "$root/AGENTS.md" "$root/PROGRESS.md" "$root/linux/rusix/"
cp "$root/docs/ROADMAP.md" "$root/linux/rusix/docs/"
cp "$root/scripts/sync-project-docs.sh" "$root/linux/rusix/scripts/"

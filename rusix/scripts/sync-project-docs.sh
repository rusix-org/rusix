#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -e "$root/linux/.git" && -e "$root/../../linux/.git" ]]; then
    root=$(cd -- "$root/../.." && pwd)
fi
test -e "$root/linux/.git" || { echo 'Linux checkout is missing' >&2; exit 1; }
mkdir -p "$root/linux/rusix/docs" "$root/linux/rusix/scripts" "$root/linux/rusix/configs"
mkdir -p "$root/linux/rusix/tests"
cp "$root/AGENTS.md" "$root/PROGRESS.md" "$root/README.md" "$root/linux/rusix/"
cp "$root/docs/"*.md "$root/linux/rusix/docs/"
cp "$root/scripts/"*.sh "$root/linux/rusix/scripts/"
cp "$root/scripts/"*.py "$root/linux/rusix/scripts/"
cp "$root/docs/"*.lock "$root/linux/rusix/docs/"
cp "$root/configs/"*.config "$root/linux/rusix/configs/"
cp "$root/tests/"*.rs "$root/linux/rusix/tests/"
cp "$root/tests/"*.py "$root/linux/rusix/tests/"
if [[ -d "$root/docs/evidence" ]]; then
    mkdir -p "$root/linux/rusix/docs/evidence"
    cp -R "$root/docs/evidence/." "$root/linux/rusix/docs/evidence/"
fi

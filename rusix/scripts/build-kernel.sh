#!/usr/bin/env bash
# Configure and build the small x86_64 KUnit kernel. Run one build per output dir.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -e "$root/linux/.git" && -e "$root/../../linux/.git" ]]; then
    root=$(cd -- "$root/../.." && pwd)
fi
if [[ $# != 1 || ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash scripts/build-kernel.sh BUILD_NAME' >&2
    exit 2
fi
name=$1
out="$root/builds/$name"
if [[ -n $(git -C "$root/linux" status --porcelain) ]]; then
    echo 'Commit or otherwise resolve source changes before a recorded build.' >&2
    exit 1
fi
cmp "$root/configs/x86_64-kunit.config" "$root/linux/rusix/configs/x86_64-kunit.config"
cmp "${BASH_SOURCE[0]}" "$root/linux/rusix/scripts/build-kernel.sh"
mkdir -p "$out" "$root/logs" "$root/builds/tmp"
export TMPDIR="$root/builds/tmp"
# flock protects this script's callers; never run another make in this output
# directory manually while the script is active.
exec 9>"$out/.rusix-build.lock"
flock -n 9 || { echo "Build already active in $out" >&2; exit 1; }
evidence=$(mktemp -d "$root/logs/$name-build.XXXXXXXX")
echo "Build evidence: $evidence"
{
    git -C "$root/linux" rev-parse HEAD
    git -C "$root/linux" status --short
    rustc --version --verbose
    clang --version
    bash "$root/scripts/with-local-tools.sh" bindgen --version
    bash "$root/scripts/with-local-tools.sh" ld.lld --version
} > "$evidence/environment.log"
bash "$root/scripts/with-local-tools.sh" make -C "$root/linux" O="$out" LLVM=1 \
    KCONFIG_ALLCONFIG="$root/configs/x86_64-kunit.config" allnoconfig \
    > "$evidence/config.log" 2>&1
while IFS= read -r setting; do
    [[ "$setting" == CONFIG_*=* ]] || continue
    if ! grep -qxF "$setting" "$out/.config"; then
        echo "Kconfig did not retain requested setting: $setting" >&2
        exit 1
    fi
done < "$root/configs/x86_64-kunit.config"
cp "$out/.config" "$evidence/config"
set +e
bash "$root/scripts/with-local-tools.sh" make -C "$root/linux" O="$out" LLVM=1 \
    -j2 bzImage > "$evidence/build.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$evidence/build.exit"
if [[ $status != 0 ]]; then
    tail -40 "$evidence/build.log" >&2
    exit "$status"
fi
sha256sum "$out/.config" "$out/arch/x86/boot/bzImage" > "$evidence/build.sha256"
echo "Built $out/arch/x86/boot/bzImage"

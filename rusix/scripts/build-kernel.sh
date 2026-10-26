#!/usr/bin/env bash
# Configure and build the small x86_64 KUnit kernel. Run one build per output dir.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/repo-paths.sh"
if [[ $# != 1 || ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash rusix/scripts/build-kernel.sh BUILD_NAME' >&2
    exit 2
fi
name=$1
source_commit=$(git -C "$RUSIX_SOURCE" rev-parse HEAD)
out="$RUSIX_OUTPUT_ROOT/builds/$name"
if [[ -n $(git -C "$RUSIX_SOURCE" status --porcelain) ]]; then
    echo 'Commit or otherwise resolve source changes before a recorded build.' >&2
    exit 1
fi
mkdir -p "$out" "$RUSIX_OUTPUT_ROOT/logs" "$RUSIX_OUTPUT_ROOT/builds/tmp"
export TMPDIR="$RUSIX_OUTPUT_ROOT/builds/tmp"
# flock protects this script's callers; never run another make in this output
# directory manually while the script is active.
exec 9>"$out/.rusix-build.lock"
flock -n 9 || { echo "Build already active in $out" >&2; exit 1; }
evidence=$(mktemp -d "$RUSIX_OUTPUT_ROOT/logs/$name-build.XXXXXXXX")
echo "Build evidence: $evidence"
{
    printf '%s\n' "$source_commit"
    git -C "$RUSIX_SOURCE" status --short
    rustc --version --verbose
    clang --version
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" bindgen --version
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" ld.lld --version
} > "$evidence/environment.log"
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" make -C "$RUSIX_SOURCE" O="$out" LLVM=1 \
    KCONFIG_ALLCONFIG="$RUSIX_PROJECT/configs/x86_64-kunit.config" allnoconfig \
    > "$evidence/config.log" 2>&1
while IFS= read -r setting; do
    [[ "$setting" == CONFIG_*=* ]] || continue
    if ! grep -qxF "$setting" "$out/.config"; then
        echo "Kconfig did not retain requested setting: $setting" >&2
        exit 1
    fi
done < "$RUSIX_PROJECT/configs/x86_64-kunit.config"
cp "$out/.config" "$evidence/config"
set +e
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" make -C "$RUSIX_SOURCE" O="$out" LLVM=1 \
    -j2 bzImage > "$evidence/build.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$evidence/build.exit"
if [[ $status != 0 ]]; then
    tail -40 "$evidence/build.log" >&2
    exit "$status"
fi
git -C "$RUSIX_SOURCE" status --porcelain > "$evidence/source-after.status"
git -C "$RUSIX_SOURCE" rev-parse HEAD > "$evidence/source-after.commit"
if [[ -s "$evidence/source-after.status" || $(cat "$evidence/source-after.commit") != "$source_commit" ]]; then
    echo 'Source changed during the build; its result is not verified.' >&2
    exit 1
fi
sha256sum "$out/.config" "$out/arch/x86/boot/bzImage" > "$evidence/build.sha256"
echo "Built $out/arch/x86/boot/bzImage"

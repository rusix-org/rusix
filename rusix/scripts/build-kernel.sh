#!/usr/bin/env bash
# Configure and build an x86_64 verification kernel. Run one build per output dir.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/repo-paths.sh"
profile=kunit
if [[ ${1:-} == --profile ]]; then
    profile=${2:-}
    [[ $# -ge 2 ]] || exit 2
    shift 2
fi
case "$profile" in
    kunit|brd|server) ;;
    *) echo 'Profile must be kunit, brd or server.' >&2; exit 2 ;;
esac
config="$RUSIX_PROJECT/configs/x86_64-$profile.config"
if [[ $# != 1 || ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash rusix/scripts/build-kernel.sh [--profile kunit|brd|server] BUILD_NAME' >&2
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
printf '%s\n' "$profile" > "$evidence/profile.txt"
{
    printf '%s\n' "$source_commit"
    git -C "$RUSIX_SOURCE" status --short
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" rustc --version --verbose
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" clang --version
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" bindgen --version
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" ld.lld --version
} > "$evidence/environment.log"
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" make -C "$RUSIX_SOURCE" O="$out" LLVM=1 \
    KCONFIG_ALLCONFIG="$config" allnoconfig \
    > "$evidence/config.log" 2>&1
while IFS= read -r setting; do
    if [[ "$setting" =~ ^#\ (CONFIG_[A-Z0-9_]+)\ is\ not\ set$ ]]; then
        if grep -q "^${BASH_REMATCH[1]}=" "$out/.config"; then
            echo "Kconfig enabled excluded setting: ${BASH_REMATCH[1]}" >&2
            exit 1
        fi
        continue
    fi
    [[ "$setting" == CONFIG_*=* ]] || continue
    if ! grep -qxF "$setting" "$out/.config"; then
        echo "Kconfig did not retain requested setting: $setting" >&2
        exit 1
    fi
done < "$config"
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
if [[ "$profile" == brd ]]; then
    # This profile currently establishes the unchanged C driver baseline.
    git -C "$RUSIX_SOURCE" diff --exit-code \
        2926d88bb7fc4608fd942453d929c39e4e5ec006 -- drivers/block/brd.c \
        > "$evidence/brd-reference.diff"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
        "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
    grep -E '(^|/)brd\.o$' "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only \
        "$out/vmlinux" > "$evidence/kernel-symbols.tmp"
    awk '$3 == "brd_submit_bio" { print }' "$evidence/kernel-symbols.tmp" \
        > "$evidence/brd-symbols.txt"
    rm -- "$evidence/kernel-symbols.tmp"
    [[ $(wc -l < "$evidence/brd-symbols.txt") == 1 ]] || {
        echo 'Expected exactly one C BRD submission symbol.' >&2; exit 1;
    }
    {
        echo 'implementation=brd-c'
        cat "$evidence/brd-objects.txt" "$evidence/brd-symbols.txt"
        sha256sum "$RUSIX_SOURCE/drivers/block/brd.c" "$out/drivers/block/brd.o"
    } > "$evidence/selection.log"
fi
git -C "$RUSIX_SOURCE" status --porcelain > "$evidence/source-after.status"
git -C "$RUSIX_SOURCE" rev-parse HEAD > "$evidence/source-after.commit"
if [[ -s "$evidence/source-after.status" || $(cat "$evidence/source-after.commit") != "$source_commit" ]]; then
    echo 'Source changed during the build; its result is not verified.' >&2
    exit 1
fi
sha256sum "$out/.config" "$out/arch/x86/boot/bzImage" "$out/vmlinux" > "$evidence/build.sha256"
if grep -qx 'CONFIG_VMLINUX_MAP=y' "$out/.config"; then
    sha256sum "$out/vmlinux.map" >> "$evidence/build.sha256"
fi
echo "Built $out/arch/x86/boot/bzImage"

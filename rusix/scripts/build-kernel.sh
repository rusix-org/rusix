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
    kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server) ;;
    *) echo 'Profile must be kunit, brd, brd-rust, brd-kunit, brd-ext4-c, brd-ext4-rust, core-ext4-c, core-ext4-rust, completion-c, completion-rust, completion-plain-c, completion-plain-rust or server.' >&2; exit 2 ;;
esac
config="$RUSIX_PROJECT/configs/x86_64-$profile.config"
if [[ $# != 1 || ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash rusix/scripts/build-kernel.sh [--profile kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server] BUILD_NAME' >&2
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
if [[ "$profile" == brd || "$profile" == brd-ext4-c ]]; then
    # This profile currently establishes the unchanged C driver baseline.
    git -C "$RUSIX_SOURCE" diff --exit-code \
        2926d88bb7fc4608fd942453d929c39e4e5ec006 -- drivers/block/brd.c \
        > "$evidence/brd-reference.diff"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
        "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
    grep -E '(^|/)brd\.o$' "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only \
        "$out/vmlinux" > "$evidence/kernel-symbols.tmp"
    if grep -q 'brd_rust' "$evidence/kernel-symbols.tmp"; then
        echo 'Rust BRD symbols remain linked in the C profile.' >&2; exit 1;
    fi
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
if [[ "$profile" == brd-rust || "$profile" == brd-kunit || "$profile" == brd-ext4-rust || "$profile" == core-ext4-c || "$profile" == core-ext4-rust || "$profile" == completion-c || "$profile" == completion-rust || "$profile" == completion-plain-c || "$profile" == completion-plain-rust || "$profile" == server ]]; then
    git -C "$RUSIX_SOURCE" diff --exit-code \
        2926d88bb7fc4608fd942453d929c39e4e5ec006 -- drivers/block/brd.c \
        > "$evidence/brd-reference.diff"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
        "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
    grep -E '(^|/)brd_rust\.o$' "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only --demangle \
        "$out/vmlinux" > "$evidence/kernel-symbols.tmp"
    if grep -Eq ' brd_submit_bio$' "$evidence/kernel-symbols.tmp"; then
        echo 'C BRD submission remains linked in the Rust profile.' >&2; exit 1;
    fi
    grep -E 'brd.*Device.*Operations.*submit' "$evidence/kernel-symbols.tmp" \
        > "$evidence/brd-symbols.txt"
    rm -- "$evidence/kernel-symbols.tmp"
    {
        echo 'implementation=brd-rust'
        cat "$evidence/brd-objects.txt" "$evidence/brd-symbols.txt"
        sha256sum "$RUSIX_SOURCE/drivers/block/brd_rust.rs" \
            "$RUSIX_SOURCE/drivers/block/brd_rust/store.rs" \
            "$out/drivers/block/brd_rust.o" "$out/drivers/block/brd_rust/params.o"
    } > "$evidence/selection.log"
fi

# Bind completion selection to the linked scheduler archive and defining object.
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
    "$out/kernel/sched/built-in.a" > "$evidence/scheduler-archive.txt"
if grep -qx 'CONFIG_RUSIX_COMPLETION_RUST=y' "$out/.config"; then
    completion_impl=rust
    completion_object="$out/kernel/sched/completion_rust.o"
    grep -E '(^|/)completion_rust\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/completion-objects.txt"
else
    completion_impl=c
    completion_object="$out/kernel/sched/build_utility.o"
    if grep -Eq '(^|/)completion_rust\.o$' "$evidence/scheduler-archive.txt"; then
        echo 'Rust completion object linked in the C selection.' >&2; exit 1;
    fi
    grep -E '(^|/)build_utility\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/completion-objects.txt"
fi
wait_symbols=(wait_for_completion wait_for_completion_timeout
    wait_for_completion_io wait_for_completion_io_timeout
    wait_for_completion_interruptible wait_for_completion_interruptible_timeout
    wait_for_completion_killable wait_for_completion_killable_timeout
    wait_for_completion_state)
for item in "$completion_object" "$out/vmlinux"; do
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only "$item" \
        > "$evidence/completion-symbols.tmp"
    printf '%s\n' "$item" >> "$evidence/completion-symbols.txt"
    for symbol in complete complete_all complete_on_current_cpu try_wait_for_completion completion_done "${wait_symbols[@]}"; do
        awk -v symbol="$symbol" '$2 == "T" && $3 == symbol { print }' \
            "$evidence/completion-symbols.tmp" > "$evidence/completion-current.txt"
        [[ $(wc -l < "$evidence/completion-current.txt") == 1 ]] || {
            echo "Expected one global $symbol definition in $item" >&2; exit 1;
        }
        cat "$evidence/completion-current.txt" >> "$evidence/completion-symbols.txt"
    done
done
# The final nm input above is vmlinux. Preserve __sched placement used by wchan.
python3 - "$evidence/completion-symbols.tmp" "${wait_symbols[@]}" \
    > "$evidence/completion-wait-sections.txt" <<'PYSECTIONS'
import sys
from pathlib import Path
symbols = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = int(fields[0], 16)
start, end = symbols['__sched_text_start'], symbols['__sched_text_end']
for name in sys.argv[2:]:
    address = symbols[name]
    if not start <= address < end:
        raise SystemExit(f'{name} outside scheduler text: {address:x}')
    print(f'{name}={address:x} sched-range=[{start:x},{end:x})')
PYSECTIONS
rm -- "$evidence/completion-symbols.tmp" "$evidence/completion-current.txt"
{
    printf 'implementation=completion-%s\n' "$completion_impl"
    cat "$evidence/completion-objects.txt" "$evidence/completion-symbols.txt"
    sha256sum "$RUSIX_SOURCE/kernel/sched/completion.c" "$completion_object"
    if [[ "$completion_impl" == rust ]]; then
        sha256sum "$RUSIX_SOURCE/kernel/sched/completion_rust.rs" \
            "$RUSIX_SOURCE/kernel/sched/completion_rust/wait.rs" \
            "$RUSIX_SOURCE/rust/helpers/raw_spinlock.c" \
            "$RUSIX_SOURCE/rust/helpers/signal.c" "$RUSIX_SOURCE/rust/helpers/task.c"
    fi
} > "$evidence/completion-selection.log"

# The selected swait slice shares the completion option but has its own object.
if [[ "$completion_impl" == rust ]]; then
    swait_object="$out/kernel/sched/swait_rust.o"
    grep -E '(^|/)swait_rust\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/swait-objects.txt"
else
    swait_object="$out/kernel/sched/build_utility.o"
    if grep -Eq '(^|/)swait_rust\.o$' "$evidence/scheduler-archive.txt"; then
        echo 'Rust swait object linked in C selection.' >&2; exit 1;
    fi
    grep -E '(^|/)build_utility\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/swait-objects.txt"
fi
for item in "$swait_object" "$out/vmlinux"; do
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only "$item" \
        > "$evidence/swait-symbols.tmp"
    printf '%s\n' "$item" >> "$evidence/swait-symbols.txt"
    for symbol in __init_swait_queue_head __prepare_to_swait __finish_swait swake_up_locked swake_up_all_locked \
        swake_up_one swake_up_all prepare_to_swait_exclusive prepare_to_swait_event finish_swait; do
        awk -v symbol="$symbol" '$2 == "T" && $3 == symbol { print }' \
            "$evidence/swait-symbols.tmp" > "$evidence/swait-current.txt"
        [[ $(wc -l < "$evidence/swait-current.txt") == 1 ]] || {
            echo "Expected one global $symbol definition in $item" >&2; exit 1;
        }
        cat "$evidence/swait-current.txt" >> "$evidence/swait-symbols.txt"
    done
done
rm -- "$evidence/swait-symbols.tmp" "$evidence/swait-current.txt"
{
    printf 'implementation=swait-%s\n' "$completion_impl"
    cat "$evidence/swait-objects.txt" "$evidence/swait-symbols.txt"
    sha256sum "$RUSIX_SOURCE/kernel/sched/swait.c" "$swait_object"
    if [[ "$completion_impl" == rust ]]; then
        sha256sum "$RUSIX_SOURCE/kernel/sched/swait_rust.rs" \
            "$RUSIX_SOURCE/rust/helpers/swait.c"
    fi
} > "$evidence/swait-selection.log"

# The selected wake slice shares the completion option but has its own object.
if [[ "$completion_impl" == rust ]]; then
    wake_object="$out/kernel/sched/wait_rust.o"
    grep -E '(^|/)wait_rust\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/wake-objects.txt"
else
    wake_object="$out/kernel/sched/build_utility.o"
    if grep -Eq '(^|/)wait_rust\.o$' "$evidence/scheduler-archive.txt"; then
        echo 'Rust wake object linked in C selection.' >&2; exit 1;
    fi
    grep -E '(^|/)build_utility\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/wake-objects.txt"
fi
for item in "$wake_object" "$out/vmlinux"; do
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only "$item" \
        > "$evidence/wake-symbols.tmp"
    printf '%s\n' "$item" >> "$evidence/wake-symbols.txt"
    for symbol in __wake_up __wake_up_on_current_cpu __wake_up_locked __wake_up_locked_key \
        __wake_up_sync_key __wake_up_locked_sync_key __wake_up_sync; do
        awk -v symbol="$symbol" '$2 == "T" && $3 == symbol { print }' \
            "$evidence/wake-symbols.tmp" > "$evidence/wake-current.txt"
        [[ $(wc -l < "$evidence/wake-current.txt") == 1 ]] || {
            echo "Expected one global $symbol definition in $item" >&2; exit 1;
        }
        cat "$evidence/wake-current.txt" >> "$evidence/wake-symbols.txt"
    done
done
rm -- "$evidence/wake-symbols.tmp" "$evidence/wake-current.txt"
{
    printf 'implementation=wake-%s\n' "$completion_impl"
    cat "$evidence/wake-objects.txt" "$evidence/wake-symbols.txt"
    sha256sum "$RUSIX_SOURCE/kernel/sched/wait.c" "$wake_object"
    if [[ "$completion_impl" == rust ]]; then
        sha256sum "$RUSIX_SOURCE/kernel/sched/wait_rust.rs" \
            "$RUSIX_SOURCE/rust/helpers/wait_policy.c"
    fi
} > "$evidence/wake-selection.log"

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

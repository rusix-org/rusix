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
    kunit|brd|brd-fixed-c|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-fixed-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server|server-c|task-construction-c|task-construction-rust|mm-construction-c|mm-construction-rust|mm-release-c|mm-release-rust|mm-copy-c|mm-copy-rust|mm-dup-mmap-c|mm-dup-mmap-rust) ;;
    *) echo 'Profile must be kunit, brd, brd-fixed-c, brd-rust, brd-kunit, brd-ext4-c, brd-ext4-fixed-c, brd-ext4-rust, core-ext4-c, core-ext4-rust, completion-c, completion-rust, completion-plain-c, completion-plain-rust, server, server-c, task-construction-c, task-construction-rust, mm-construction-c, mm-construction-rust, mm-release-c, mm-release-rust, mm-copy-c, mm-copy-rust, mm-dup-mmap-c or mm-dup-mmap-rust.' >&2; exit 2 ;;
esac
config="$RUSIX_PROJECT/configs/x86_64-$profile.config"
if [[ "$profile" == server-c ]]; then
    config="$RUSIX_PROJECT/configs/x86_64-server.config"
fi
if [[ $# != 1 || ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash rusix/scripts/build-kernel.sh [--profile kunit|brd|brd-fixed-c|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-fixed-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server|server-c|task-construction-c|task-construction-rust|mm-construction-c|mm-construction-rust|mm-release-c|mm-release-rust|mm-copy-c|mm-copy-rust|mm-dup-mmap-c|mm-dup-mmap-rust] BUILD_NAME' >&2
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
if [[ "$profile" == server || "$profile" == server-c ]]; then
    python3 "$RUSIX_PROJECT/scripts/server_target.py" materialize \
        --source "$config" --profile "$profile" --evidence "$evidence"
    config="$evidence/config-input"
fi
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
# A fixed-C oracle must be explicitly selected; it cannot masquerade as baseline.
if [[ "$profile" == brd-fixed-c || "$profile" == brd-ext4-fixed-c ]]; then
    grep -qx 'CONFIG_RUSIX_BRD_C_PARAMETER_FIX=y' "$out/.config" || exit 1
    if grep -qx 'CONFIG_RUSIX_BRD_RUST=y' "$out/.config"; then exit 1; fi
elif grep -qx 'CONFIG_RUSIX_BRD_C_PARAMETER_FIX=y' "$out/.config"; then
    echo 'Fixed C oracle selected outside its explicit verification profile.' >&2; exit 1
fi
if [[ "$profile" != mm-release-c && "$profile" != mm-release-rust ]] && \
    grep -qx 'CONFIG_RUSIX_MM_RELEASE_TEST=y' "$out/.config"; then
    echo 'MM release fixture selected outside its explicit verification profiles.' >&2
    exit 1
fi
cp "$out/.config" "$evidence/config"
if [[ "$profile" == task-construction-c || "$profile" == task-construction-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-task-construction.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/task-config-before.json"
fi
if [[ "$profile" == mm-construction-c || "$profile" == mm-construction-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-construction.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-config-before.json"
fi
if [[ "$profile" == mm-release-c || "$profile" == mm-release-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-release.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-release-config-before.json"
fi
if [[ "$profile" == mm-copy-c || "$profile" == mm-copy-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-copy.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-copy-config-before.json"
fi
if [[ "$profile" == mm-dup-mmap-c || "$profile" == mm-dup-mmap-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-dup-mmap.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/dup-mmap-config-before.json"
fi
if [[ "$profile" == server || "$profile" == server-c ]]; then
    python3 "$RUSIX_PROJECT/scripts/server_target.py" verify \
        --source "$RUSIX_PROJECT/configs/x86_64-server.config" --profile "$profile" \
        --evidence "$evidence" --resolved "$out/.config"
fi
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
if [[ "$profile" == brd || "$profile" == brd-ext4-c || "$profile" == brd-fixed-c || "$profile" == brd-ext4-fixed-c ]]; then
    # The pristine reference gate applies even when a separate fixed oracle is built.
    git -C "$RUSIX_SOURCE" diff --exit-code \
        2926d88bb7fc4608fd942453d929c39e4e5ec006 -- drivers/block/brd.c \
        > "$evidence/brd-reference.diff"
    brd_impl=brd-c
    brd_object=brd.o
    oracle="$RUSIX_PROJECT/reference/brd-parameter-fix"
    if [[ "$profile" == brd-fixed-c || "$profile" == brd-ext4-fixed-c ]]; then
        brd_impl=brd-c-parameter-fix
        brd_object=brd_parameter_fixed.o
        python3 "$RUSIX_PROJECT/scripts/generate-brd-parameter-oracle.py" \
            --source "$RUSIX_SOURCE/drivers/block/brd.c" --manifest "$oracle/manifest.json" \
            --output "$out/drivers/block/brd_parameter_fixed.c" --check \
            > "$evidence/brd-oracle-verification.log"
        cp "$oracle/manifest.json" "$evidence/brd-oracle-manifest.json"
        python3 - "$out" <<'PYBRDCOMMAND'
import re
import sys
from pathlib import Path
build = Path(sys.argv[1])
command = (build / 'drivers/block/.brd_parameter_fixed.o.cmd').read_text()
name = re.findall(r'-DKBUILD_MODNAME=([^ ]+)', command.splitlines()[0])
if len(name) != 1 or name[0].strip("'").replace(chr(92), '') != '"brd"':
    raise SystemExit('Fixed C oracle lost the exact brd parameter prefix')
sources = re.findall(r'^source_[^ ]+ := (.+)$', command, re.MULTILINE)
if len(sources) != 1:
    raise SystemExit('Missing/duplicate fixed C oracle compilation source')
source = Path(sources[0])
if not source.is_absolute():
    source = build / source
if source.resolve() != (build / 'drivers/block/brd_parameter_fixed.c').resolve():
    raise SystemExit('Fixed C oracle object compiled a different source')
PYBRDCOMMAND
        cp "$out/drivers/block/.brd_parameter_fixed.o.cmd" "$evidence/brd-oracle-command.cmd"
    fi
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
        "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
    grep -Fx "$out/drivers/block/$brd_object" "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
    [[ $(wc -l < "$evidence/brd-objects.txt") == 1 ]] || {
        echo 'Expected exactly one selected C BRD archive object.' >&2; exit 1;
    }
    if grep -E '(^|/)(brd\.o|brd_parameter_fixed\.o|brd_rust([/.]|$))' "$evidence/block-archive.txt" \
        | grep -Fvx "$out/drivers/block/$brd_object"; then
        echo 'Unexpected BRD implementation in C oracle archive.' >&2; exit 1;
    fi
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
        printf 'implementation=%s\n' "$brd_impl"
        cat "$evidence/brd-objects.txt" "$evidence/brd-symbols.txt"
        sha256sum "$RUSIX_SOURCE/drivers/block/brd.c" "$out/drivers/block/$brd_object"
        if [[ "$brd_impl" == brd-c-parameter-fix ]]; then
            sha256sum "$RUSIX_PROJECT/scripts/generate-brd-parameter-oracle.py" \
                "$oracle/manifest.json" "$oracle/baseline.patch" "$oracle/upstream-proposal.patch" \
                "$out/drivers/block/brd_parameter_fixed.c" "$out/drivers/block/.brd_parameter_fixed.o.cmd"
        fi
    } > "$evidence/selection.log"
fi
if [[ "$profile" == brd-rust || "$profile" == brd-kunit || "$profile" == brd-ext4-rust || "$profile" == core-ext4-c || "$profile" == core-ext4-rust || "$profile" == completion-c || "$profile" == completion-rust || "$profile" == completion-plain-c || "$profile" == completion-plain-rust || "$profile" == server || "$profile" == server-c || "$profile" == task-construction-c || "$profile" == task-construction-rust || "$profile" == mm-construction-c || "$profile" == mm-construction-rust || "$profile" == mm-release-c || "$profile" == mm-release-rust || "$profile" == mm-copy-c || "$profile" == mm-copy-rust || "$profile" == mm-dup-mmap-c || "$profile" == mm-dup-mmap-rust ]]; then
    git -C "$RUSIX_SOURCE" diff --exit-code \
        2926d88bb7fc4608fd942453d929c39e4e5ec006 -- drivers/block/brd.c \
        > "$evidence/brd-reference.diff"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-ar t \
        "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
    grep -E '(^|/)brd_rust\.o$' "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
    [[ $(wc -l < "$evidence/brd-objects.txt") == 1 ]] || {
        echo 'Expected exactly one Rust BRD archive object.' >&2; exit 1;
    }
    if grep -Eq '(^|/)(brd\.o|brd_parameter_fixed\.o|brd_rust/params\.o)$' "$evidence/block-archive.txt"; then
        echo 'C BRD or parameter adapter object remains selected.' >&2; exit 1;
    fi
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only --demangle \
        "$out/vmlinux" > "$evidence/kernel-symbols.tmp"
    if grep -Eq ' brd_submit_bio$' "$evidence/kernel-symbols.tmp"; then
        echo 'C BRD submission remains linked in the Rust profile.' >&2; exit 1;
    fi
    grep -E 'brd.*Device.*Operations.*submit' "$evidence/kernel-symbols.tmp" \
        > "$evidence/brd-symbols.txt"
    rm -- "$evidence/kernel-symbols.tmp"
    python3 "$RUSIX_PROJECT/scripts/verify-brd-parameter-owner.py" \
        --object "$out/drivers/block/brd_rust.o" --vmlinux "$out/vmlinux" \
        --config "$out/.config" > "$evidence/brd-parameter-ownership.json"
    {
        echo 'implementation=brd-rust'
        cat "$evidence/brd-objects.txt" "$evidence/brd-symbols.txt" \
            "$evidence/brd-parameter-ownership.json"
        sha256sum "$RUSIX_SOURCE/drivers/block/brd_rust.rs" \
            "$RUSIX_SOURCE/drivers/block/brd_rust/store.rs" \
            "$RUSIX_SOURCE/drivers/block/brd_rust/params.rs" \
            "$RUSIX_SOURCE/rust/bindings/builtin_init_helper.h" \
            "$RUSIX_SOURCE/rust/bindings/lib.rs" "$RUSIX_SOURCE/rust/Makefile" \
            "$RUSIX_PROJECT/scripts/verify-brd-parameter-owner.py" \
            "$RUSIX_PROJECT/scripts/measure-kernel-languages.py" \
            "$out/rust/bindings/builtin_init_generated.rs" \
            "$out/rust/bindings/.builtin_init_generated.rs.cmd" \
            "$out/rust/bindings/bindings_generated.rs" "$out/drivers/block/brd_rust.o"
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
    for symbol in __init_waitqueue_head add_wait_queue add_wait_queue_exclusive \
        add_wait_queue_priority add_wait_queue_priority_exclusive remove_wait_queue \
        __wake_up __wake_up_on_current_cpu __wake_up_locked __wake_up_locked_key \
        __wake_up_sync_key __wake_up_locked_sync_key __wake_up_sync \
        prepare_to_wait prepare_to_wait_exclusive prepare_to_wait_event \
        finish_wait autoremove_wake_function wait_woken \
        woken_wake_function woken_wake_bit_function do_wait_intr do_wait_intr_irq; do
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

# Wait-bit ownership/policy has seventeen named definitions, including init.
bit_symbols=(__var_wake_key wake_bit_function __wait_on_bit __wait_on_bit_lock
    bit_wait bit_wait_io bit_wait_timeout out_of_line_wait_on_bit
    out_of_line_wait_on_bit_timeout out_of_line_wait_on_bit_lock
    wait_bit_init bit_waitqueue __var_waitqueue __wake_up_bit wake_up_bit
    init_wait_var_entry wake_up_var)
bit_sched_symbols=(__wait_on_bit __wait_on_bit_lock bit_wait bit_wait_io bit_wait_timeout
    out_of_line_wait_on_bit out_of_line_wait_on_bit_timeout out_of_line_wait_on_bit_lock)
if [[ "$completion_impl" == rust ]]; then
    bit_object="$out/kernel/sched/wait_bit_rust.o"
    grep -E '(^|/)wait_bit_rust\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/wait-bit-objects.txt"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only \
        "$out/kernel/sched/build_utility.o" > "$evidence/wait-bit-c-symbols.txt"
    for symbol in "${bit_symbols[@]}"; do
        if awk -v symbol="$symbol" '$2 == "T" && $3 == symbol { found=1 } END { exit !found }' \
            "$evidence/wait-bit-c-symbols.txt"; then
            echo "C wait-bit definition remains selected: $symbol" >&2; exit 1;
        fi
    done
else
    bit_object="$out/kernel/sched/build_utility.o"
    if grep -Eq '(^|/)wait_bit_rust\.o$' "$evidence/scheduler-archive.txt"; then
        echo 'Rust wait-bit object linked in C selection.' >&2; exit 1;
    fi
    grep -E '(^|/)build_utility\.o$' "$evidence/scheduler-archive.txt" \
        > "$evidence/wait-bit-objects.txt"
fi
[[ $(wc -l < "$evidence/wait-bit-objects.txt") == 1 ]] || {
    echo 'Expected one selected wait-bit object.' >&2; exit 1;
}
for item in "$bit_object" "$out/vmlinux"; do
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-nm --defined-only "$item" \
        > "$evidence/wait-bit-symbols.tmp"
    printf '%s\n' "$item" >> "$evidence/wait-bit-symbols.txt"
    for symbol in "${bit_symbols[@]}"; do
        awk -v symbol="$symbol" '$2 == "T" && $3 == symbol { print }' \
            "$evidence/wait-bit-symbols.tmp" > "$evidence/wait-bit-current.txt"
        [[ $(wc -l < "$evidence/wait-bit-current.txt") == 1 ]] || {
            echo "Expected one global $symbol definition in $item" >&2; exit 1;
        }
        cat "$evidence/wait-bit-current.txt" >> "$evidence/wait-bit-symbols.txt"
    done
done
# Verify both defining-object section and linked scheduler-text interval.
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" llvm-objdump --syms "$bit_object" \
    > "$evidence/wait-bit-object-sections.txt"
python3 - "$evidence/wait-bit-symbols.tmp" "$evidence/wait-bit-object-sections.txt" \
    "${bit_sched_symbols[@]}" > "$evidence/wait-bit-scheduler-sections.txt" <<'PYBITSECTIONS'
import sys
from pathlib import Path
symbols = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = int(fields[0], 16)
object_lines = [line.split() for line in Path(sys.argv[2]).read_text().splitlines()]
start, end = symbols['__sched_text_start'], symbols['__sched_text_end']
for name in sys.argv[3:]:
    matches = [fields for fields in object_lines if fields and fields[-1] == name]
    if len(matches) != 1 or '.sched.text' not in matches[0]:
        raise SystemExit(f'{name} missing/duplicate or outside object .sched.text')
    address = symbols[name]
    if not start <= address < end:
        raise SystemExit(f'{name} outside linked scheduler text: {address:x}')
    print(f'{name} object=.sched.text address={address:x} sched-range=[{start:x},{end:x})')
PYBITSECTIONS
# Inspect real ELF storage/sections in both configurations. The !LOCKDEP key can
# be zero-sized/eliminated, so only debug configurations require key storage.
python3 - "$bit_object" "$out/vmlinux" "$out/kernel/sched/build_utility.o" \
    "$out/.config" "$out/rust/bindings/bindings_generated.rs" "$completion_impl" \
    > "$evidence/wait-bit-ownership.txt" <<'PYBITOWNER'
import re
import struct
import sys
from pathlib import Path

class Elf:
    def __init__(self, path):
        self.path = path
        self.data = Path(path).read_bytes()
        if self.data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', self.data, 18)[0] != 62:
            raise SystemExit('Wait-bit storage proof requires x86_64 little-endian ELF64')
        offset = struct.unpack_from('<Q', self.data, 40)[0]
        stride, count, names = struct.unpack_from('<HHH', self.data, 58)
        if stride != 64 or not count or names >= count:
            raise SystemExit('Unsupported ELF section table')
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, offset + i * stride)
                         for i in range(count)]
        name_section = self.sections[names]
        name_data = self.data[name_section[4]:name_section[4] + name_section[5]]
        self.section_names = [self.string(name_data, section[0]) for section in self.sections]
        self.symbols = []
        for section in self.sections:
            if section[1] != 2:  # SHT_SYMTAB, not dynsym duplicates.
                continue
            if section[9] != 24 or section[5] % 24:
                raise SystemExit('Unexpected ELF symbol stride')
            strings = self.sections[section[6]]
            strings = self.data[strings[4]:strings[4] + strings[5]]
            for pos in range(section[4], section[4] + section[5], 24):
                name, info, _, index, address, size = struct.unpack_from('<IBBHQQ', self.data, pos)
                if index:
                    self.symbols.append(dict(name=self.string(strings, name), kind=info & 15,
                                             index=index, address=address, size=size))

    @staticmethod
    def string(data, offset):
        return data[offset:data.index(b'\0', offset)].decode()

    def one(self, predicate, description):
        found = [symbol for symbol in self.symbols if predicate(symbol)]
        if len(found) != 1:
            raise SystemExit(f'{self.path}: expected one {description}, found {len(found)}')
        return found[0]

    def named(self, name):
        return self.one(lambda symbol: symbol['name'] == name, name)

    def section(self, symbol):
        index = symbol['index']
        if index >= len(self.sections):
            raise SystemExit(f'No real section for {symbol["name"]}')
        return self.section_names[index], self.sections[index]

selected, linked, alternative = [Elf(path) for path in sys.argv[1:4]]
config = Path(sys.argv[4]).read_text().splitlines()
bindings = Path(sys.argv[5]).read_text()
implementation = sys.argv[6]
def constant(name):
    values = re.findall(r'pub const ' + name + r': [^=]+ = ([0-9]+);', bindings)
    if len(values) != 1:
        raise SystemExit(f'Missing/duplicate generated C layout constant {name}')
    return int(values[0])

alignment = constant('RUSIX_WAIT_BIT_TABLE_ALIGNMENT')
head_size = constant('RUSIX_WAIT_BIT_HEAD_SIZE')
if alignment <= 0 or alignment & (alignment - 1) or head_size <= 0:
    raise SystemExit('Invalid generated C table layout')
init_start = linked.named('__init_begin')['address']
init_end = linked.named('__init_end')['address']
if init_start >= init_end:
    raise SystemExit('Invalid linked init interval')
for elf in (selected, linked):
    initializer = elf.named('wait_bit_init')
    section_name, section = elf.section(initializer)
    if section_name != '.init.text' or initializer['kind'] != 2 or not section[2] & 4:
        raise SystemExit('wait_bit_init must be executable .init.text')
    if elf is linked and not init_start <= initializer['address'] < init_end:
        raise SystemExit('Linked wait_bit_init lies outside init memory')
    rust = implementation == 'rust'
    table = elf.one(lambda symbol: symbol['kind'] == 1 and
                    (('BIT_WAIT_TABLE' in symbol['name']) if rust else
                     symbol['name'] == 'bit_wait_table'), 'selected wait table')
    table_section, table_header = elf.section(table)
    if table['size'] != 256 * head_size or table['address'] % alignment:
        raise SystemExit('Wait table size/address disagrees with configured C layout')
    if not table_header[2] & 1 or table_header[8] < alignment:
        raise SystemExit('Wait table must be writable and cacheline aligned')
    if elf is selected and table_section != '.data..cacheline_aligned':
        raise SystemExit('Defining wait table lost baseline cacheline data section')
    if table_section.startswith('.init') or (elf is linked and
            table['address'] < init_end and table['address'] + table['size'] > init_start):
        raise SystemExit('Wait table must survive init memory reclamation')
    if rust and any(symbol['name'] == 'bit_wait_table' for symbol in elf.symbols):
        raise SystemExit('C wait table remains in Rust selection')
    if not rust and any('BIT_WAIT_TABLE' in symbol['name'] for symbol in elf.symbols):
        raise SystemExit('Rust wait table remains in C selection')
    print(f'{elf.path}: table={table["name"]} section={table_section} '
          f'address={table["address"]:x} size={table["size"]} alignment={alignment} '
          f'head-size={head_size}; init={initializer["address"]:x} section={section_name}')
    if rust and 'CONFIG_LOCKDEP=y' in config:
        key = elf.one(lambda symbol: symbol['kind'] == 1 and
                      'BIT_WAIT_CLASS' in symbol['name'], 'permanent lockdep key')
        key_section, key_header = elf.section(key)
        if not key['size'] or not key_header[2] & 1 or key_section.startswith('.init'):
            raise SystemExit('Lockdep key must have permanent writable storage')
        if elf is linked and key['address'] < init_end and key['address'] + key['size'] > init_start:
            raise SystemExit('Lockdep key overlaps init memory')
        print(f'{elf.path}: key={key["name"]} section={key_section} '
              f'address={key["address"]:x} size={key["size"]}')
if implementation == 'rust' and any(symbol['name'] in ('bit_wait_table', 'var_wake_function')
                                    for symbol in alternative.symbols):
    raise SystemExit('C wait-bit storage/private callback remains selected')
if 'CONFIG_LOCKDEP=y' not in config:
    print('LOCKDEP=n: no storage or distinct identity required for empty key type')
PYBITOWNER
rm -- "$evidence/wait-bit-symbols.tmp" "$evidence/wait-bit-current.txt"
{
    printf 'implementation=wait-bit-%s\n' "$completion_impl"
    cat "$evidence/wait-bit-objects.txt" "$evidence/wait-bit-symbols.txt" \
        "$evidence/wait-bit-scheduler-sections.txt" "$evidence/wait-bit-ownership.txt"
    sha256sum "$RUSIX_SOURCE/kernel/sched/wait_bit.c" "$bit_object"
    if [[ "$completion_impl" == rust ]]; then
        sha256sum "$RUSIX_SOURCE/kernel/sched/wait_bit_rust.rs" \
            "$RUSIX_SOURCE/kernel/sched/wait_bit_rust/time.rs" \
            "$RUSIX_SOURCE/rust/helpers/wait_bit_policy.c" \
            "$RUSIX_SOURCE/include/linux/rusix_wait_bit_types.h" \
            "$out/rust/bindings/bindings_generated.rs"
    fi
} > "$evidence/wait-bit-selection.log"

if [[ "$profile" == task-construction-c || "$profile" == task-construction-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-task-construction.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/task-config-after.json"
    python3 "$RUSIX_PROJECT/scripts/preprocess-task-construction.py" \
        --build "$out" --evidence "$evidence"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" python3 \
        "$RUSIX_PROJECT/scripts/verify-task-construction.py" objects \
        --profile "$profile" --source "$RUSIX_SOURCE" --build "$out" \
        --evidence "$evidence" > "$evidence/task-selection.json"
fi
if [[ "$profile" == mm-construction-c || "$profile" == mm-construction-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-construction.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-config-after.json"
    python3 "$RUSIX_PROJECT/scripts/preprocess-mm-construction.py" \
        --build "$out" --evidence "$evidence"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" python3 \
        "$RUSIX_PROJECT/scripts/verify-mm-construction.py" objects \
        --profile "$profile" --source "$RUSIX_SOURCE" --build "$out" \
        --evidence "$evidence" > "$evidence/mm-selection.json"
fi
if [[ "$profile" == mm-release-c || "$profile" == mm-release-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-release.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-release-config-after.json"
    python3 "$RUSIX_PROJECT/scripts/preprocess-mm-release.py" \
        --build "$out" --evidence "$evidence"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" python3 \
        "$RUSIX_PROJECT/scripts/verify-mm-release.py" objects \
        --profile "$profile" --source "$RUSIX_SOURCE" --build "$out" \
        --evidence "$evidence" > "$evidence/mm-release-selection.json"
fi
if [[ "$profile" == mm-copy-c || "$profile" == mm-copy-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-mm-copy.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/mm-copy-config-after.json"
    python3 "$RUSIX_PROJECT/scripts/preprocess-mm-copy.py" \
        --build "$out" --evidence "$evidence"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" python3 \
        "$RUSIX_PROJECT/scripts/verify-mm-copy.py" objects \
        --profile "$profile" --source "$RUSIX_SOURCE" --build "$out" \
        --evidence "$evidence" > "$evidence/mm-copy-selection.json"
fi

if [[ "$profile" == mm-dup-mmap-c || "$profile" == mm-dup-mmap-rust ]]; then
    python3 "$RUSIX_PROJECT/scripts/verify-dup-mmap.py" config \
        --profile "$profile" --config "$out/.config" --source "$RUSIX_SOURCE" \
        > "$evidence/dup-mmap-config-after.json"
    # Preserve the actual inherited fork-copy proof as well as the mmap proof.
    # Each parser uses its own saved compiler command and fresh .i output.
    python3 "$RUSIX_PROJECT/scripts/preprocess-mm-copy.py" \
        --build "$out" --evidence "$evidence"
    python3 "$RUSIX_PROJECT/scripts/preprocess-dup-mmap.py" \
        --build "$out" --evidence "$evidence"
    bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" python3 \
        "$RUSIX_PROJECT/scripts/verify-dup-mmap.py" objects \
        --profile "$profile" --source "$RUSIX_SOURCE" --build "$out" \
        --evidence "$evidence" > "$evidence/dup-mmap-selection.json"
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

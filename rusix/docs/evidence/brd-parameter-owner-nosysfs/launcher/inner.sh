#!/usr/bin/env bash
set -euo pipefail
source /src/rusix/scripts/repo-paths.sh
out=/out/builds/brd-owner-nosysfs
evidence=/out/logs/nosysfs-build
mkdir -p "$out" "$evidence" /out/tmp
export TMPDIR=/out/tmp
trap 'printf "%s\n" "$?" > /out/logs/nosysfs.exit' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
[[ $(git -C /src rev-parse HEAD) == "$EXPECTED_SOURCE" ]]
[[ -z $(git -C /src status --porcelain) ]]
export KBUILD_BUILD_TIMESTAMP="$(git -C /src show -s --format=%cD HEAD)"
export SOURCE_DATE_EPOCH="$(git -C /src show -s --format=%ct HEAD)"
export KBUILD_BUILD_USER=rusix KBUILD_BUILD_HOST=ci KBUILD_BUILD_VERSION=1
printf '%s\n' "$EXPECTED_SOURCE" > "$evidence/source.commit"
cp /opt/rusix/packages.lock /opt/rusix/toolchain.log "$evidence/"
bash /src/rusix/scripts/check-toolchain.sh > "$evidence/preflight.log" 2>&1
cp /src/rusix/configs/x86_64-completion-rust.config "$evidence/canonical.config"
make -C /src O="$out" LLVM=1 KCONFIG_ALLCONFIG="$evidence/canonical.config" allnoconfig \
  > "$evidence/base-config.log" 2>&1
cp "$out/.config" "$evidence/before.config"
/src/scripts/config --file "$out/.config" --disable SYSFS
cp "$out/.config" "$evidence/requested.config"
make -C /src O="$out" LLVM=1 olddefconfig > "$evidence/olddefconfig.log" 2>&1
cp "$out/.config" "$evidence/config"
python3 - "$evidence" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
def settings(text):
    out={}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            k,v=line.split('=',1);out[k]=v
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            out[line.split()[1]]='n'
    return out
before=settings((p/'before.config').read_text());after=settings((p/'config').read_text())
assert before.get('CONFIG_SYSFS')=='y'
assert after.get('CONFIG_SYSFS')=='n'
required=('EXPERT','RUST','RUSIX_BRD_RUST','RUSIX_COMPLETION_RUST','KUNIT','SMP',
          'BLK_DEV_RAM','SERIAL_8250_CONSOLE','DEBUG_KERNEL','PROVE_LOCKING',
          'PROVE_RAW_LOCK_NESTING','DEBUG_ATOMIC_SLEEP','DEBUG_LIST','LIST_HARDENED')
for name in required: assert after.get('CONFIG_'+name)=='y',name
for name in ('MODULES','RUSIX_BRD_C_PARAMETER_FIX'):
    assert after.get('CONFIG_'+name,'n')=='n',name
for name in ('BLK_DEV_RAM_COUNT','BLK_DEV_RAM_SIZE','NR_CPUS'):
    assert after.get('CONFIG_'+name)==before.get('CONFIG_'+name),name
(p/'derivation.json').write_text(json.dumps({'request':'scripts/config --disable SYSFS; make olddefconfig',
  'base_profile':'completion-rust','resolved_differences':{k:[before.get(k,'n'),after.get(k,'n')]
    for k in sorted(before.keys()|after.keys()) if before.get(k,'n')!=after.get(k,'n')},
  'sha256':{f:hashlib.sha256((p/f).read_bytes()).hexdigest() for f in
    ('canonical.config','before.config','requested.config','config')}},indent=2)+'\n')
PY
set +e
make -C /src O="$out" LLVM=1 -j2 bzImage > "$evidence/build.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$evidence/build.exit"
[[ "$status" == 0 ]] || exit "$status"
if grep -Eiq 'warning:|error:|objtool:' "$evidence/build.log"; then
    echo 'Build diagnostics rejected; retain complete log.' >&2; exit 1
fi
llvm-ar t "$out/drivers/block/built-in.a" > "$evidence/block-archive.txt"
grep -E '(^|/)brd_rust\.o$' "$evidence/block-archive.txt" > "$evidence/brd-objects.txt"
[[ $(wc -l < "$evidence/brd-objects.txt") == 1 ]]
if grep -Eq '(^|/)brd\.o$|brd_parameter_fixed\.o$|brd_rust/params\.o$' "$evidence/block-archive.txt"; then
    echo 'Unexpected C BRD storage/implementation retained.' >&2; exit 1
fi
python3 /src/rusix/scripts/verify-brd-parameter-owner.py \
  --object "$out/drivers/block/brd_rust.o" --vmlinux "$out/vmlinux" --config "$out/.config" \
  > "$evidence/brd-parameter-owner.json"
llvm-nm --undefined-only "$out/drivers/block/brd_rust.o" > "$evidence/brd-undefined.txt"
if grep -Eq ' (kernel_param_(un)?lock|rusix_brd_params_(un)?lock)$' "$evidence/brd-undefined.txt"; then
    echo 'SYSFS=n Rust BRD retained parameter lock call.' >&2; exit 1
fi
find "$out/rust/bindings" -maxdepth 1 -type f -name '*builtin_init*' -print \
  > "$evidence/builtin-binding-files.txt"
while IFS= read -r file; do sha256sum "$file"; done < "$evidence/builtin-binding-files.txt" \
  > "$evidence/builtin-bindings.sha256"
[[ -s "$evidence/builtin-bindings.sha256" ]]
sha256sum "$out/.config" "$out/arch/x86/boot/bzImage" "$out/vmlinux" \
  "$out/drivers/block/brd_rust.o" > "$evidence/build.sha256"
bash /src/rusix/scripts/boot-kunit.sh --brd "$out" brd-owner-nosysfs-combined
bash /src/rusix/scripts/boot-kunit.sh --completion "$out" brd-owner-nosysfs-core
sha256sum -c "$evidence/build.sha256" > "$evidence/inputs-after.log"
[[ $(git -C /src rev-parse HEAD) == "$EXPECTED_SOURCE" ]]
[[ -z $(git -C /src status --porcelain) ]]
git -C /src rev-parse HEAD > "$evidence/source-after.commit"
git -C /src status --porcelain > "$evidence/source-after.status"
printf '%s\n' 'PASS: SYSFS=n full kernel, BRD ELF ownership/no-lock-call proof, combined and isolated KUnit; no sysfs userspace claim.' \
  > /out/logs/nosysfs-result.txt

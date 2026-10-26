# BRD parameter ownership

Status: verified at `a39d03eb165b` on built-in x86_64. Fixed C and Rust each
pass 32 storage/userspace boots; 76 combined and 67 isolated core cases pass.
[Standard evidence](../../docs/evidence/brd-parameter-owner/manifest.json) binds
the metadata/object proofs to the actual kernels. A separate SYSFS=n build and
the same KUnit inventories pass with the debug/core settings retained and no
parameter-lock references in the BRD object
([evidence](../../docs/evidence/brd-parameter-owner-nosysfs/manifest.json)).
This is separate from [ADR 0003](../../docs/adr/0003.md)'s normalization correction.

Rust owns `rusix_brd_rd_nr`, `rd_size` and `rusix_brd_max_part`, preserving their
C scalar widths, alignment and externally referenced names. Private opaque
storage exposes no safe references across C access. The existing C parameter
operations still parse and print values; this migration does not redesign them.

The inspected [upstream parameter API](https://github.com/torvalds/linux/blob/21a7f44fd0765fcc5194130b28767786eba1d1e7/rust/kernel/module_param.rs)
uses SetOnce, rejects repeated assignments and has no sysfs getter. Its metadata
wrapper pattern is useful, but importing that storage/parser contract would
change BRD behavior. This migration keeps its wrapper private and retains the
original parameter operations; no upstream acceptance is claimed.

Three naturally aligned `__param` records preserve builtin `brd.` names, null
module owner, permissions 0444, level -1, flags zero and the original int/ulong
operations. Six module-information strings and the legacy `ramdisk_size=` setup
record retain their content and section lifetimes. The original adapter source
remains as an unlinked reference; selection must reject its object and wrappers.

Normal initialization uses the original global parameter mutex through a
private guard that cannot move between tasks. Without SYSFS, locking remains the
original no-op and the caller must have exclusive initialization access. The
legacy callback writes storage only during exclusive boot parsing. The approved
normalization and both typed/legacy parser behavior are unchanged.

`obs_kernel_param` is hidden by init.h in MODULE context. A separate, narrowly
allowlisted bindgen translation unit undefines MODULE last and includes canonical
init.h. Existing global module bindings remain unchanged; Rust does not copy the
C layout manually. Dependency tracking must regenerate both the binding and its
consumer when relevant headers/configuration change.

## Verification

The object/link gate must establish scalar ownership and writable permanent
storage, parameter/legacy metadata contents and addresses, alignment and init
lifetimes. Compare against the original C metadata rather than symbol counts
alone. No executable C parameter adapter may remain selected.

The existing 26 boundary/default/legacy parameter boots remain. Three additional
boots check last-write-wins for rd_nr, rd_size and max_part, following the pinned
C parser's sequential assignments. All 29 inspect exact sysfs names and regular
file modes, then registration, device mapping, independent I/O and capacity.
Together with block, ext4/consumer and partition boots, that is 32 per selected
driver. Matching C/Rust fixtures and configurations remain required.

The SYSFS=n derivation disables SYSFS and its KERNFS dependency; it does not
claim no-sysfs userspace coverage. Generic kernel parameter parsing,
printing, mutexes, block/page services and the rest of the C core remain kernel
rewrite dependencies; this migration only removes BRD-owned C storage/adapters.

The first build at `2048c42d9096` exposed bindgen's `str_` field name and three
unnecessary-unsafe warnings. The corrected runs are diagnostic-free;
[initial failure evidence](../../docs/evidence/brd-parameter-owner-initial/manifest.json)
preserves the generated binding and logs.

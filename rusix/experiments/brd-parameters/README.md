# BRD parameter ownership

Status: Rust storage/metadata and expanded guest tests are implemented and
independently reviewed; all twelve host gate suites pass. Kernel build and
runtime verification remain pending. This is separate from the
approved normalization correction in [ADR 0003](../../docs/adr/0003.md).

Rust owns `rusix_brd_rd_nr`, `rd_size` and `rusix_brd_max_part`, preserving their
C scalar widths, alignment and externally referenced names. Private opaque
storage exposes no safe references across C access. The existing C parameter
operations still parse and print values; this migration does not redesign them.

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

KUnit and a separate SYSFS=n build must cover the remaining conditional path.
Record actual results here before promotion. Generic kernel parameter parsing,
printing, mutexes, block/page services and the rest of the C core remain kernel
rewrite dependencies; this migration only removes BRD-owned C storage/adapters.

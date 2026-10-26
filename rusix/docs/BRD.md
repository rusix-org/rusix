# BRD migration contract and ownership proposal

**Status: initial C baseline verified; Rust design only, no Rust BRD implementation.**
The reference is `drivers/block/brd.c` at upstream
`21a7f44fd0765fcc5194130b28767786eba1d1e7`. Paths below are relative to the
Git root. The six-case VM probe passed at project source `976e2de80`; see the
[baseline evidence](evidence/brd-c-baseline/manifest.json) and `rusix/PROGRESS.md`. The full required outcome remains [Phase 1](PHASE1.md).

## Behavior to preserve

| Area | Pinned C behavior and boundary |
| --- | --- |
| Submission | `brd_submit_bio` is a synchronous bio-based callback, not a blk-mq queue. Each bio completes exactly once, including allocation failures. |
| Sparse reads | An absent backing page reads as zero without allocating a page. |
| Writes | Allocate zeroed backing pages as needed; preserve bytes outside the write. `brd_rw_bvec` caps each transfer at both the bio-page and backing-page boundary, then advances the bio iterator. |
| Insertion | `brd_insert_page` compares against an empty xarray entry. Concurrent first writers share the winning page; the losing allocation is released. |
| Allocation | Page allocation uses `GFP_NOWAIT` for `REQ_NOWAIT`, otherwise `GFP_NOIO`, plus zero/highmem flags. Xarray allocation receives the same NOWAIT/NOIO policy. `ENOMEM` under NOWAIT becomes would-block; other failures become I/O errors. |
| Discard | `brd_do_discard` removes only fully covered backing pages. Partial first/last pages retain their contents. Repeating discard of a hole does not decrement accounting again. |
| Lifetime | Lookup takes a page reference under RCU and revalidates the entry. Discard removes the index reference; an in-flight operation may keep the old page alive. No whole-bio atomicity is promised. |
| Geometry | Capacity is `rd_size * 2` sectors; the parameter is in KiB. Physical block size and discard granularity are `PAGE_SIZE`; queue features include synchronous completion and NOWAIT. |
| Registration | Preserve RAMDISK_MAJOR, `ramN`, `rd_nr`, `rd_size`, `max_part`, partition/minor normalization, `rd`/major aliases, and built-in `ramdisk_size=`. Access to a device node can instantiate another disk through the registered probe. |
| Accounting | Debugfs `ramdisk_pages/ramN` counts pages currently indexed by the device, not all still-live pages after concurrent discard. Compare it after operations settle. |
| Teardown | Unregister discovery, remove disks, release disk references and backing pages, then release device state. Rust must prove callback quiescence before freeing that state. |

BRD delegates request validation and generic device behavior to the surrounding
block layer. Contract tests should distinguish its behavior from upstream block
validation, including capacity bounds and operation filtering. Inspect
`block/fops.c`, `block/blk-core.c`, `include/linux/bio.h`, and
`include/linux/blkdev.h` when defining the submission abstraction.

Pinned `brd_init` ignores individual `brd_alloc` errors while creating the initial
devices. Capture this behavior under allocation injection before deciding whether
to change it. Initialization fixes must be explicit semantic changes, not hidden
inside translation. Likewise, inspect each registration/debugfs failure path;
copying its control flow alone does not establish sound Rust ownership.

## First C baseline probe

`rusix/tests/brd-contract/probe.c` is a purpose-built VM init, not the ordinary
Linux userspace required by P1-04. The initial profile uses x86_64, 4 KiB pages,
two CPUs, and one built-in 64 MiB C RAM disk. The six named checks are:

- `geometry`: capacity and logical/physical block sizes.
- `sparse_read`: untouched data is zero and sparse reads do not populate storage.
- `crossing_write`: direct I/O with different buffer/device page offsets,
  preserving surrounding bytes across backing-page boundaries.
- `discard_edges`: full-page removal with partial-edge preservation and repeated
  discard behavior.
- `concurrent_insert`: coordinated writers update disjoint sectors in fresh
  pages; both sectors survive. This tests insertion competition without imposing
  unsupported whole-write atomicity.
- `accounting`: settled indexed-page counts agree with populated/discarded pages.

The runner must require all cases exactly once, reject failure/missing/duplicate
results and kernel diagnostics, and bind the tested image/configuration to clean
source build evidence. Passing these cases would establish only this C baseline;
Rust parity requires executing the same workload against a selected Rust driver.

## Proposed backing-store ownership

Use an `XArray<Arc<PageSlot>>`, with a pinned page lock in each `PageSlot` owning
one `Page`. This is a proposal to review and compile, not a proven implementation.
The existing pieces support the outline:

- `rust/kernel/sync/arc.rs` implements `ForeignOwnable` for `Arc`, returns an
  `ArcBorrow` when borrowed, and can create an owned `Arc` from that borrow.
  Kernel `Arc` pins its allocation; `UniqueArc` supports pin initialization.
- `rust/kernel/xarray.rs` owns inserted values and releases them on removal/drop.
  Clone the operation's Arc while holding its guard, then release the index lock.
- `rust/kernel/page.rs` owns an allocated page and frees it on Drop. Do not add a
  second independent page ownership/refcount scheme around that owner.

Allocate the page and slot outside locks. The page uses NOIO/NOWAIT with
`__GFP_ZERO | __GFP_HIGHMEM`; slot metadata uses NOIO/NOWAIT **without HIGHMEM**,
which is invalid for kmalloc-like allocations. The public Rust flag set currently
omits typed `GFP_NOIO`; add that narrow allocation interface before using it.

A new xarray insert-if-absent operation is required. `Guard::store` can release
the lock while allocating and replaces any existing value, so lookup followed by
store can destroy a concurrent writer's insertion. The pinned
`__xa_insert` already supplies conditional insertion through `__xa_cmpxchg_raw`
and is present in generated bindings. Prefer a narrow `Guard::insert` returning
`Result<(), StoreError<T>>`: transfer candidate ownership on success and return
it on any error, including `EBUSY`. It may release/reacquire the lock to allocate
but returns with the guard held. BRD can borrow and clone the winner on `EBUSY`
before releasing that guard. Never reconstruct an owned Arc from an entry still
owned by the array. A generic `EBUSY` must not imply `get().is_some()`: reserved
entries reject insertion but appear empty to normal lookup. BRD uses
`AllocKind::Alloc` with no reservations. Preserve the foreign-pointer alignment
and ownership rules of the existing abstraction.

For a transfer, release the index lock before acquiring the slot lock. Hold the
slot lock only across the bounded page access; never allocate or acquire the
index lock while holding it. Prove callback interrupt/preemption contexts before
choosing plain `SpinLock` versus an interrupt-safe variant. A spinlock is not a
sleeping mutex, but its permitted contexts still matter, including RT builds.

Discard removes the index Arc and decrements the indexed-page counter while
holding the index lock. In-flight Arc owners keep the detached page alive; a later
write can populate a new page at that index. Freeing detached slots outside the
index lock may shorten its hold time, provided accounting and lifetime rules are
preserved. After device removal has quiesced callbacks, release the xarray and
remaining device ownership. Its Drop is not itself proof of quiescence.

The slot introduces an additional allocation, Arc operations and lock contention.
Measure these costs against the Phase 1 memory/performance budget and inject
failure at both page and metadata allocations. Do not assume the budget passes.

## Unsafe boundaries still requiring proof

The slot lock can exclude overlapping accesses to the private backing page.
It does **not** by itself make a bio buffer exclusive or race-free. Direct I/O
can pin userspace pages that userspace can still access (`block/fops.c`). The
existing `Page::read_raw` and `write_raw` use `copy_nonoverlapping`; their raw
pointer arguments do not waive Rust's validity, overlap or race requirements.
A borrowed bio page's lifetime is therefore insufficient justification for making
an exclusive slice or performing an ordinary Rust copy. Review a transfer
primitive appropriate for concurrently accessible bio memory, prove backing/bio
non-aliasing or handle aliases, and keep mappings scoped to the executing task.
No safe bio-copy API should be exposed until these conditions are established.

The remaining enabling interfaces are substantive:

- Bio-based disk registration with matching queue limits, major/minor policy,
  parameters, on-demand discovery, initialization rollback and deregistration.
  Current `rust/kernel/block.rs` exposes mq; its disk builder invokes
  `__blk_mq_alloc_disk`, so using it would change the submission model.
- A submitted-bio abstraction with validated segment iteration, bounded advance,
  status mapping and exactly-once completion. Completion must consume access to
  the bio; device state must outlive every callback and cleanup path.
- The conditional xarray operation and allocation flag above, plus a reviewed
  backing/bio transfer abstraction. C helpers may expose inline/macro boundaries;
  driver ownership, data-path decisions and lifecycle policy belong in Rust.

## Remaining verification

Before calling this a migrated driver, add paired C/Rust coverage for allocation
injection and deterministic NOWAIT errors, overlapping I/O/discard lifetimes,
capacity edges, parameters/partitions and on-demand creation, memory pressure,
initialization failure, busy removal and repeated module load/use/unload. Use
supported memory instrumentation and lockdep with demonstrated coverage.

The ordinary userspace/ext4 workload, built-in/module x86_64 and arm64 matrix,
controlled performance measurements, reproducible environment/CI and an upstream
semantic-change rehearsal remain separate mandatory Phase 1 gates. Neither this
design nor six passing baseline tests would complete any of those broader gates.

# BRD migration contract and ownership

Reference: `drivers/block/brd.c` at Linux 6.18.58,
`2926d88bb7fc4608fd942453d929c39e4e5ec006`. Paths below are relative to the
Git root. [Progress](../PROGRESS.md) records executed checks;
[Phase 1](PHASE1.md) defines delivery gates.

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

## Shared block contract probe

`rusix/tests/brd-contract/probe.c` is a purpose-built VM init, not the ordinary
Linux userspace required by Phase 1a. Both profiles use x86_64, 4 KiB pages,
two CPUs, and one built-in 64 MiB RAM disk. The six named checks are:

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
source build evidence. The same unchanged executable runs against the selected
C and Rust implementations; broader filesystem and hardening gates are separate.

## Backing-store ownership

The store uses `XArray<Arc<PageSlot>>`, with a pinned page lock in each `PageSlot`
owning one `Page`. Its ownership builds on these existing interfaces:

- `rust/kernel/sync/arc.rs` implements `ForeignOwnable` for `Arc`, returns an
  `ArcBorrow` when borrowed, and can create an owned `Arc` from that borrow.
  Kernel `Arc` pins its allocation; `UniqueArc` supports pin initialization.
- `rust/kernel/xarray.rs` owns inserted values and releases them on removal/drop.
  Clone the operation's Arc while holding its guard, then release the index lock.
- `rust/kernel/page.rs` owns an allocated page and frees it on Drop. Do not add a
  second independent page ownership/refcount scheme around that owner.

Allocate the page and slot outside locks. The page uses NOIO/NOWAIT with
`__GFP_ZERO | __GFP_HIGHMEM`; slot metadata uses NOIO/NOWAIT **without HIGHMEM**,
which is invalid for kmalloc-like allocations. A synchronous `alloc::with_noio`
closure applies NOIO to nested allocations without exposing an escaping guard;
NOWAIT requests retain their explicit nonblocking flags.

`Guard::insert` supplies insert-if-absent. `Guard::store` can release
the lock while allocating and replaces any existing value, so lookup followed by
store can destroy a concurrent writer's insertion. The pinned
`__xa_insert` already supplies conditional insertion through `__xa_cmpxchg_raw`
and is present in generated bindings. The narrow `Guard::insert` returns
`Result<(), StoreError<T>>`: transfer candidate ownership on success and return
it on any error, including `EBUSY`. It may release/reacquire the lock to allocate
but returns with the guard held. BRD can borrow and clone the winner on `EBUSY`
before releasing that guard. Never reconstruct an owned Arc from an entry still
owned by the array. A generic `EBUSY` must not imply `get().is_some()`: reserved
entries reject insertion but appear empty to normal lookup. BRD uses
`AllocKind::Alloc` with no reservations. Preserve the foreign-pointer alignment
and ownership rules of the existing abstraction. Audit upstream entry/preload
work informed this adaptation; its allocator dependencies are described below.

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

The implementation adds these transitional interfaces:

- Bio-based disk registration with matching queue limits, major/minor policy,
  parameters, on-demand discovery, initialization rollback and deregistration.
  `block::bio_disk` uses `__blk_alloc_disk`; the inherited mq builder uses
  `__blk_mq_alloc_disk` and would change the submission model.
- A submitted-bio abstraction with validated segment iteration, bounded advance,
  status mapping and exactly-once completion. Completion must consume access to
  the bio; device state must outlive every callback and cleanup path.
- The conditional xarray operation and allocation scope above, plus a reviewed
  backing/bio transfer abstraction. C helpers may expose inline/macro boundaries;
  driver ownership, data-path decisions and lifecycle policy belong in Rust.

## Upstream work to evaluate first

Checked 2026-10-25. The upstream `rust-next` head matches our engineering pin.
The following are proposals/author branches, not claims of merged approval:

| Need | Existing work | Required review |
| --- | --- | --- |
| Conditional xarray insertion | [Entry/preload v5, 12 patches, 2026-09-02](https://lore.kernel.org/r/20260902-xarray-entry-send-v5-0-d18adae40708@kernel.org) | Allocation/sheaf dependencies, lock-drop semantics and whether the entry API covers BRD without a competing local API. |
| NOIO policy | [Task-scoped allocation v2, 2026-06-05](https://lists.openwall.net/linux-kernel/2026/06/05/1016) supersedes the flag-only proposal | [Review objections](https://lists.openwall.net/linux-kernel/2026/06/06/240) include generator/async lifetime and LIFO safety. |
| Bio/page access | [rnull completion v2, 83 patches, 2026-06-09](https://patchew.org/linux/20260609-rnull-v6-19-rc5-send-v2-0-82c7404542e2@kernel.org/) and [SafePage v2](https://lists.openwall.net/linux-kernel/2026/06/05/1251) | Transfer races/aliasing, ownership and dependencies. Bio iteration there serves mq requests; it does not establish non-MQ disk registration. |

The author's `rnull-v7.1-rc2` tree was inspected at
`5e0226dac3526872d23c0b1a771ccd0502852b6b`. Its block API exports `bio`,
`mq`, `badblocks` and `error`; no bio-based disk builder was found. Compare the
applicable patches against the adopted LTS before importing them. Preserve
authorship and review context, and test any adaptation rather than assuming an
unmerged series is sound. Generic interfaces should be suitable for upstream
review even though this project's long-term direction is governed by ADR 0002.

## Remaining verification

[Paired q35 verification](evidence/brd-q35/manifest.json) at `9d1c1ca5dd` passes
block6, ext4 six cases, six parameter/on-demand boots and partition5 (including
clipped writes). Each fixture archive is identical across C/Rust; configs differ
only in BRD selection. This does not resolve the negative-parameter exception
below or retire the remaining C boundaries.
Phase 1b adds paired allocation injection and deterministic NOWAIT errors,
overlapping I/O/discard lifetimes, memory pressure, initialization failure,
busy removal and repeated module load/use/unload. Use
supported memory instrumentation and lockdep with demonstrated coverage.

Expanded architecture/module coverage, controlled performance and a chosen
upstream-fix port remain subject to the 1a/1b split in [PHASE1.md](PHASE1.md).
Hosted CI is disabled by execution policy; these local results do not complete
those broader gates.

## LTS implementation candidate

The initial implementation lives in `drivers/block/brd_rust.rs` and its `store`
module. `RUSIX_BRD_RUST` selects it for built-in 64-bit configurations; the original
C source remains unchanged. `block::bio` owns completion and bounded segments;
`block::bio_disk` retains typed state through final disk release. The sparse store
uses Arc-owned, zeroed pages, conditional insertion and per-page locking.

The generic xarray addition wraps the LTS's existing `__xa_insert`: importing the
entry/preload proposal would also import unrelated allocator machinery. NOIO uses
a synchronous closure with a private save/restore guard, avoiding an escaping
async guard. These are local adaptations, not upstream-approved interfaces.

Executing C boundaries are explicitly retained: block-core allocation/publication,
xarray and lock/page primitives, debugfs, parameter metadata and inline wrappers.
Bio payload copies/zeroing use C highmem primitives because externally mutable
userspace pages cannot safely become ordinary Rust references. No helper implements
BRD request policy or sparse-store ownership. Removing these boundaries requires
migration of their owning core abstractions.

On the declared 64-bit targets, positive `max_part` inputs from 2^30 through
INT_MAX preserve the pinned narrowing to INT_MIN, signed clamp comparison,
parameter sysfs value and major registration. Their unsigned probe divisor is
0x80000000; disk creation rejects the minor count, and opening ram0 returns
ENXIO. The paired q35 high-positive guest case verifies these observations;
it avoids the C failure path's dangling debugfs counter.
Negative inputs instead narrow to zero in C, producing a zero divisor in its
on-demand probe. Rust retains an initialization-time EINVAL guard for this
undefined-behavior boundary. That guard also changes pre-fault initialization
observations; this narrow exception remains disclosed rather than being called
full negative-parameter parity. Values outside the `int` parser range continue
to use the shared C parameter parser's existing rejection behavior.
Built-in operation is the only selectable mode until module lifetime is audited.

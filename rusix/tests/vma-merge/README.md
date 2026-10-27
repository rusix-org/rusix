# Native merge transaction fixture

Source-only candidate based on `7b2d7dc500f4b0586b8d53bb631a2abae6d0e2e3`.
No configuration, compiler, kernel or VM result exists. The exact eighteen KUnit
case names are in [cases.json](cases.json), recorded before implementation.
`CONFIG_RUSIX_VMA_MERGE_TEST` is default-off, depends on KUNIT=y and the
modification chain, and is independent of the merge selector for paired testing.
No verification profile or runtime gate accepts this fixture yet.

Each case owns a private kthread, mm, native mappings and optional file. Setup
uses real fixed vm_mmap placements: R/RX/R ranges plus 64 separated filler VMAs.
Every actual VMA must exclude WRITE, ACCOUNT, LOCKED/LOCKONFAULT, HUGETLB and
PFN/MIXED flags, including fillers and file mappings. MAP_NORESERVE alone is
never accepted as proof. Native anon_vma_prepare produces a real singular ancestry
chain without page faults; counters are read under the anon root lock.

The test-only vma.c dispatcher calls actual existing/new/expand/shrink entries.
A complete expected topology is constructed before invocation. It checks exact
live identity/ranges/offsets/flags/file/ops, map_count and unchanged policy VM
counters before applying predeclared native caller vm_stat_account deltas. Tree
accounting is then checked independently. It never repairs an arbitrary result.
Failure paths preserve original topology/counters; only existing-range promises
original-start cursor restoration. Direct expansion clone failure preserves its
initial state, unlike later preallocation failure. Raw before/after observations
and hook counters are emitted to KUnit logs.

Two test-only native failure sites match current worker, mm and exact dst/src or
maple cursor, under a static spinlocked registry. The worker serialization mutex
prevents overlapping fixture arms. Anon allocation injection denies both genuine
NOWAIT and KERNEL attempts inside anon_vma_clone, then follows native cleanup.
Maple injection requires a positive node request and no cached storage, enters
native allocation error, and observes actual preallocate destruction/reset.
An allocation-free path is a failure to reach the case, never forcibly converted
into an error. No global pressure/debugfs setting, fake clone errno, invented anon
object or host model is used. All native hook calls compile out with TEST off.

Cases cover clone failure and clone-success/preallocation-failure with reporting
and silent OOM, direct expansion's early failure, shrink preallocation failure,
close-hook refusal/both-to-left reduction, unrestricted both-side retirement and
four matching success controls. Native close callbacks must not run during merge;
file reference/count/topology changes establish the removal observation without
dereferencing retired VMAs. The fixture does not claim exact allocator-free counts,
partial multi-chain clone cleanup, all seventeen policies, optional configurations
or concurrency. Those require their own gates and real userspace consumers.

Completion publishes worker observations. Timeout retains worker/callback refs.
Uncertain topology/accounting/ownership retains native objects rather than guessing
cleanup. On success, mmput completes native teardown, a retained mmgrab protects
storage, and adopted lazy-TLB refs are not assumed exhausted. A private file must
have exactly one retained reference before __fput_sync; callbacks retain fixture
storage until synchronous final release. No global flush or forced worker stop.
Real unlink clears destination anon_vma; the baseline host VMA test's dummy unlink
pointer assertion is deliberately not copied.

Before compilation: independently review native lifetime/locking, the two hooks,
expected topology/accounting and exact case dispatch. Then add strict actual
selection/fixture ownership and runtime gates in a separate change, resolving
real config/API/allocator reachability without relaxing these assertions.

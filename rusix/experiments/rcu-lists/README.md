# RCU callback-list policy

Status: implementation and ten tests are under review; fourteen host gate
scripts pass. Kernel builds and runtime parity have not run yet.
The reference is Linux 6.18.58 `kernel/rcu/rcu_segcblist.c`, retained unchanged.
This slice translates all 25 external definitions: four simple-list operations
and 21 segmented-list operations. Tree RCU, Tree SRCU and their C-owned state
remain consumers. No RCU divergence point is declared.

## Scope and ownership

The new selector is default-off, initially restricted to the built-in x86_64
Tree RCU configuration without callback offloading (RCU_NOCB_CPU). Separate
C/Rust debug and plain profiles keep the established Rust core and BRD selected;
only the callback-list implementation differs within each pair. Tests have their
own selector so production configurations do not include fixtures.

Both list types contain pointers to their own head or callback next fields.
Initialize at the final address and retain containers and callbacks while any
interior pointer can remain live. Rust must not move initialized list values,
borrow shared C storage as Rust references, or copy entire foreign structures.
Per-CPU IRQ exclusion, SRCU locks and CPU-hotplug exclusion are distinct caller
contracts, not one universal queue lock. Existing layouts remain transitional.

## Shared-memory boundary

Rust owns list policy, segment selection, pointer-graph decisions and sequence
arithmetic. Typed C primitives preserve the reference's plain versus marked
loads and stores; raw Rust pointer projection must not introduce a hidden load.
This includes shared callback links, head/tail slots, counts, flags and sequence
fields. Tracepoints can directly copy segment counts and sequences; disabling
NOCB alone does not justify racing ordinary Rust stores.

The ordered total-length update remains one C primitive containing the exact
before barrier, update and after barrier. Its zero transitions govern whether
rcu_barrier must wait for callbacks, including module-code lifetime. Keep this
ordering intact; volatile access or an unreviewed Rust atomic overlay is not an
equivalent replacement. Warn-once sites and the CPUs-held assertion also retain
their original C diagnostics. These executing primitives are unfinished Rust
work and must be inventoried, not hidden as completed policy.

## Semantics that tests must preserve

- Total length includes callbacks extracted for invocation; it can differ from
  both an empty head and the sum of linked segment lengths.
- Initialization ORs ENABLED into existing flags and leaves sequence fields
  untouched. Only nonempty WAIT and NEXT_READY sequence slots are meaningful.
- Simple enqueue does not clear the new node's next pointer. Flush replaces the
  destination and preserves a nonzero source count while replacing a callback.
- Extraction does not subtract total length. Done reinsertion clears the source
  head/tail but preserves its count; pending reinsertion leaves its descriptor
  unchanged. Transferred descriptors are not independent owning queues.
- Entrainment can be necessary with positive total length and an empty head.
  Advance/accelerate retain segment boundaries and unsigned wraparound ordering.
- Merge requires CPU-hotplug exclusion, discards pending grace-period progress,
  and resets the source. Never move a self-referential temporary during merge.

## Required evidence and subsequent ownership

Use the same bounded literal fixtures against C and Rust: labelled callback
identities, exact tail slots, counts, meaningful sequence values and flags.
Avoid bytewise structure comparisons, uninitialized reads, invalid-pointer
traversal or a second implementation disguised as the test oracle. Add real
call_rcu/rcu_barrier and SRCU consumers; outstanding callback storage and task
references must survive controller timeouts. Blocking barriers belong to retained
workers with bounded controller observation and a final VM watchdog.
The literal inventory contains eight list-state cases plus two real-consumer
cases. Dedicated profiles require 86 combined cases (nine BRD, 67 core, ten RCU),
then 67 isolated core cases and ten isolated RCU cases. Missing, skipped,
duplicate, failed or unexpected cases cannot satisfy the gate.

Prove exclusive selection of every definition and inspect the compiled ordering
primitives. Paired runtime tests cannot alone prove weak-memory ordering. Keep
existing storage/userspace gates, then test the declared server configuration
and refresh its language inventory before promotion. NOCB, actual hotplug stress
and broader ordering stress require separate evidence.

Next replace direct C inline/trace access with explicit operation boundaries,
then migrate callback-batch ownership/invocation and per-CPU RCU state. Grace-
period coordination, C storage, header-inline execution and primitive adapters
remain part of the full kernel rewrite.

## Production integration profiles

`rcu-list-ext4-c` and `rcu-list-ext4-rust` keep Rust BRD and the Rust wait/core
policy on both sides, disable KUnit/RCU fixtures, and change only the RCU-list
selector. Each runs the block contract,29 parameter variants, partition probe
and ext4/wake/locked consumers (32 guest boots). `rcu-list-server-c` and
`rcu-list-server-rust` derive from the declared server fragment, preserve its
Rust BRD/core choices, and change the same RCU selector. They run twelve
filesystem/wake/locked consumers and same-build language measurement. Existing
server/core comparison profiles retain their original meaning.

These are verification profiles, not a changed server default. Production
selection rejects fixture objects and requires all25 definitions in the selected
object and linked kernel; guest runners revalidate the retained proof and input
hashes before launching. Host profile tests do not establish runtime compatibility.

When only the reviewed integration tooling changes after a KUnit run,
`verify-rcu-list-continuity.py --source CHECKOUT --baseline KUNIT_COMMIT
--candidate INTEGRATION_COMMIT` checks ancestry and an exact changed-file allowlist,
including unchanged kernel/fixture sources and existing KUnit profiles/gates.
Optional `--evidence DEBUG_MANIFEST --evidence PLAIN_MANIFEST` also rechecks those
archives. Original KUnit evidence remains attributed to its original revision;
new integration runs must identify their own clean source/config/scripts. The
continuity record does not assert byte-identical images or substitute for review
of changed build/routing scripts. A kernel, fixture or existing-profile change
fails this boundary and requires fresh affected verification.

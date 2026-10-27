# Constructor allocation-failure candidate

**Diagnostic kernel and runtime attribution remain unverified.** The paired diagnostic pipeline is implemented,
but has no accepted runtime failure coverage. The existing production transaction at policy base
`8fd3defabb841083192cd1d9c4eb1cde83027579` is unchanged. Separate
`x86_64-task-construction-fault-{c,rust}.config` fragments add diagnostic-only
fault injection and tracing. The normal server remains DEBUG_FS=n. The fault profiles use separate build/VM routing; ordinary task profiles retain
their original gates.

`controller.rs` is intended for the pinned static Rust toolchain; `worker.c` for
static x86_64 GCC. Neither may run on the host. The guarded `init.rs` mounts proc, sysfs, debugfs and tracefs, sets
comm `rusix-faultinit`, then directly spawns the controller. Exact cmdline tokens `rusix.task_faults=1` and `no_hash_pointers` are required; conflicting pointer-hashing options are rejected. This changes only the disposable guest. Controller
requires parent PID1; worker separately checks token/name. Worker path is
`/fault-worker`; the reviewed calibration packet's TSV is `/calibration.tsv`.
Python is host-only: no Python guest/rootfs is introduced.

## Implemented acquisition

Controller owns one trace instance and three dynamic return probes. It refuses
existing same-name probes/instance and enabled slab-cache injection flags.
Per-worker traces include task-slab alloc/free, page failure decision and actual
allocator return, child-publication events, ARM/DISARM markers and stack traces.
The successful nth0 control captures allocation stacks as well as the injected
runs. Required exact input event formats are retained. Probe and ring-buffer loss
counters accompany every attempt. The run emits hex-encoded artifacts and
`RUSIX_TASK_FAULT_CAPTURE_COMPLETE`, **never a runtime PASS**.

Each worker pre-opens and touches buffers, handshakes readiness, arms its own
fail-nth with a raw pwrite syscall, executes raw fork, saves errno, reads back and
disarms with raw syscalls before parsing/retry/reporting. It stays alive until
controller acknowledgement, retaining its PID/PGID through capture/failure
cleanup. Children exit23 and are boundedly reaped; a disarmed retry must succeed.
Controller is a child subreaper, kills only its owned group on timeout, and bounds
reaping; a stuck kernel remains subject to an external VM watchdog.

Capability prefilters matter: per-task fail-nth bypasses generic probability,
times and task-filter. Slab case selects only task_struct and disables page
capability with min-order UINT_MAX. Page sweep deselects every slab cache and
uses order>=2, with a required compiled copy_process stack range. All changed
knobs are read back and restored; owned tracing is explicitly removed before
capture completion. Each control command is preformatted and submitted by one
write; short writes fail without replaying a partial command. Errors include
operation/path context. The controller captures one uninjected control, slab nth1,
and page nth1..16. Unsupported/merged slab flags, missing symbols, failed
readbacks or partial setup fail closed. No live stack cache is flushed.

## Calibration is a prerequisite, not supplied proof by assertion

There is intentionally no fabricated calibration file. `generate-task-fault-calibration.py` derives candidate sites from the actual
fault-profile ELF. Ambiguous/missing sites stop before boot. The uninjected
guest attempt must independently demonstrate both selected callsite frames. TSV fields are
schema=1, policy_base, build_source (the future fault commit), implementation,
notes_hex, range_symbol, range_start, range_end, slab_frame and stack_frame.
Fields are tab separated. Source base and actual build source are distinct.
After matching kernel notes, the guest captures complete `/proc/kallsyms` through
EOF, with a 16 MiB bound, as `runtime-kallsyms`. The host separately binds
unique selected text names and addresses to the verified ELF, then derives the
printed extent from the next distinct core address, preserving first-alias
selection. Appended module/BPF/kprobe inventories do not participate in core
ordering. This does not replace ELF `st_size` or allocation return-PC checks.
The exact native unhashed-pointer banner is required and bound to the recorded
`lib/vsprintf.c`; pointer placeholders remain failures.
The guest matches complete running `/sys/kernel/notes` bytes and the live
required-range symbol address. Range end and callsite attribution are subsequently
checked against actual linked ELF by the host, not trusted from these strings.

Host `validate-task-fault-trace.py` consumes a JSON packet with policy_base,
build_source and hashed inputs named vmlinux, config, symbols, disassembly, notes
and calibration.tsv. Each input has path and SHA256. It regenerates symbols with
`llvm-nm -S --defined-only`, disassembly with
`llvm-objdump -d --no-show-raw-insn`, and extracts `.notes` to a temporary copy
beside the packet. Actual symbol sizes/ranges and call instructions must explain
the exact captured return PC. Supported slab site is a direct canonical allocator
call or a call to the exact slab adapter ending in its allocator tail jump;
stack site must directly call the canonical page allocator. Other compiler forms
fail until reviewed, not auto-approved. It also requires a successful calibration
trace containing both exact allocation frames. Ordinary stack trace instances
print saved return PCs unchanged; no guessed minus-one offset is accepted.

The kernel's page-allocation tracepoint is bypassed by early fault injection;
it cannot prove this failure. The parser instead requires injected order2 decision,
exact stack-call frame, allocator NULL return and matching successful task-slab
allocation/rollback free before syscall ENOMEM. Slab failure requires null
allocation at its exact frame without an acquired task allocation. Missing,
misordered, foreign-actor, lost or ambiguous records cannot establish either case.
Parent survival and matched slab cleanup are limited evidence, not observation
of all possible parent-stack accesses or a proof of no leaks.

## Remaining integration and limits

Pending: pinned compilation, actual linked-site discovery and event-schema
validation, paired C/Rust VM runs and real fault-site results. No packet may be
fabricated to bypass these. The runner now binds build selection/config/source,
ELF notes and static fixture identity; decodes an exact 97-artifact inventory;
rejects kernel diagnostics and incomplete cleanup/PID1 status; and rechecks all
source, kernel and guest inputs after execution.
The parser CLI's PASS means only captured-record attribution after ELF checks;
it is not sufficient for accepting a run without the external VM/source gates.

Thirteen host parser tests use explicitly synthetic text to reject wrong sites,
rollback pointer mismatch, missing/reordered markers, probe/trace loss, failed
retry, child publication and arbitrary non-call PCs. They do not establish
compiled or runtime behavior. `PROGRESS.md` records the current evidence level.

Calibration requires constructor-chain frame owners and a unique qualifying
allocator call in each owner; ambiguous inlined sites fail until instruction
arguments/source mapping can distinguish them. The VM launcher explicitly uses
`nokaslr`: exact linked/live address checks reject relocation. Each capture
label must match its requested fail-nth value and use a distinct worker PID.


## Local paired execution (pending)

Run the diagnostic C profile first, then Rust, with the same pinned fixture image
and build resources. Each uses `test-task-faults-vm.py BUILD LABEL
--build-evidence PROOF`; fresh labels are mandatory. The build proof must come
from `task-construction-fault-c` or `task-construction-fault-rust` at the exact
current clean commit. Both run the same uninjected control, task-slab nth1 and
stack nth1..16 sweep. Then run `compare-task-fault-runs.py --c C_RUN_EVIDENCE --rust
RUST_RUN_EVIDENCE`. It rechecks captured attribution, linked calibration and
artifact hashes, and requires identical source/guest/tool/image identities with
only the constructor selector differing in resolved configs. Retain original
build and fixture output paths until this check finishes. When C and Rust ran in
separate containers mounted at `/out`, pass `--c-output-root C_HOST_OUTPUT
--rust-output-root RUST_HOST_OUTPUT --source-root CHECKOUT` to the comparator,
using the exact pinned build container for postchecks. Host LLVM may produce
different disassembly text. Only the expected ELF filename heading follows the
explicit path remap; file format and instructions must remain identical. Only `/out` and `/src`
are remapped; all artifact hashes are still verified. The pair gate also requires
identical compiled init/controller/worker binaries, exact QEMU arguments and both
resolved diagnostic configs. Calibration and initramfs bytes appropriately differ.

The runner generates calibration before compiling fixtures, preserving unsupported
compiler-form failures. KVM is required; the guest has two CPUs, 512 MiB, no NIC,
and a 300-second timeout with a five-second kill grace. The controller restores
owned fault knobs and removes its tracing state before emitting capture completion;
PID1 emits its terminal marker only after successful controller exit. Worker
failures, missing artifacts, trace/probe loss, absent attributable stack failure,
or an expired VM timeout cannot pass. Eleven additional synthetic host tests cover
callsite discovery and transport strictness, including the 15-byte task-name guard.

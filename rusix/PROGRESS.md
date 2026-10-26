# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations; eighteen generic wait entries now pass parity too.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust BRD each pass block6, ext4 userspace6, six parameter variants and partition5. Four identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Core and shared queue policy | At `ca91adc60e13`, C/Rust debug and plain pairs each pass 53 combined (44 core + nine BRD), then 44 isolated core on q35/KVM SMP2. All 14 completion, 10 swait and 18 generic wait definitions link exclusively. Zero skips or compiler/objtool diagnostics. [Evidence](docs/evidence/wait-lifecycle/manifest.json). |
| Ordinary-userspace integration | Same source, Rust BRD in both; only core selection differs. Both pass nine block/ext4/parameter/partition boots, including six filesystem and four pipe/poll/epoll/eventfd cases. Identical fixtures; no compiler diagnostics. [Evidence](docs/evidence/wait-lifecycle-ext4/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray insertion,
NOIO scope, completion/swait policy and generic wait initialization, enrollment,
prepare/finish, removal and callback traversal.
The [core migration record](experiments/completion/README.md) owns storage,
locking/lifetime contracts, test inventory and remaining C boundaries. Selection
remains default-off and builtin-only; known incompatible counter-access drivers
are excluded.

Declared x86_64 server measurement at `7effedcbb1bf`: executable C
**5,753,281 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,049**, unknown **0**.
[Measurement](docs/evidence/lts-target/manifest.json). This predates the core
migration, includes inherited Rust infrastructure, and is neither a completion
percentage nor server runtime evidence. That target selects Rust BRD/C completion.

Five new lifecycle cases establish real descheduled workers, exclusive token
handoffs, signal/nonmatching wake handling, original macro condition precedence,
timeout cleanup and repeated preparation. Scheduler samples establish state at
observation, not causation by a later wake. Callbacks retain fixture ownership
through return; completion acknowledgment is not a thread join.

Next migrate the WOKEN handshake and bit-wait policy, then locked interruptible
waits with blocked consumers. The [wait record](experiments/wait/README.md) owns
mixed-access and lifetime contracts. WOKEN/bit-wait handoffs and POLLFREE races
remain unverified.
Forced diagnostic failures, detached-batch races, untimed signal paths, deadline
races and broader IRQ coverage remain open. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b. Phase 1a still needs the provisional BRD
invalid-parameter exception, parameter adapters and review gates; [BRD.md](docs/BRD.md).

Failures are retained, including the [wake pointer-conversion compile error](docs/evidence/wait-wake/manifest.json),
the [plain-profile configuration refusal](docs/evidence/swait-init/manifest.json)
(EXPERT forces DEBUG_KERNEL; corrected before compilation), [wait bringup](docs/evidence/completion-wait-initial/manifest.json),
[status test compilation](docs/evidence/completion-status/manifest.json),
[q35 bringup](docs/evidence/q35-bringup/manifest.json) and the initial
[swait/ext4 fixture staging refusal](docs/evidence/swait-ext4/manifest.json).
Raw logs/binaries remain in `linux-out/<run>`; manifests record source/config/tool
identities and hashes. [Verification index](docs/VERIFICATION.md) preserves earlier
milestones without attributing their results to newer source.

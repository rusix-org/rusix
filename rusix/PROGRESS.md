# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust BRD each pass block6, ext4 userspace6, six parameter variants and partition5. Four identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Core and shared queue policy | C/Rust debug at `61882366fe7e` and plain at `9bba720b206b` each pass 39 combined (30 core + nine BRD), then 30 isolated core on q35/KVM SMP2. Only two plain-profile config fragments differ between revisions; production/tests are identical. All 14 completion and 10 swait definitions link exclusively. Zero skips or compiler/objtool diagnostics. [Evidence](docs/evidence/swait-init/manifest.json). |
| Ordinary-userspace integration | At `9bba720b206b`, Rust BRD in both; only completion/swait selection differs. Both pass nine block/ext4/parameter/partition boots with identical fixtures and no compiler diagnostics. KUnit disabled. [Evidence](docs/evidence/swait-init-ext4/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray insertion,
NOIO scope, completion policy and shared/generic swait enrollment/wakeup.
The [core migration record](experiments/completion/README.md) owns storage,
locking/lifetime contracts, test inventory and remaining C boundaries. Selection
remains default-off and builtin-only; known incompatible counter-access drivers
are excluded. The initializer now verifies final caller lock metadata, raw wait
type, queue self-links and IRQ preservation in instrumented and plain profiles.

Declared x86_64 server measurement at `7effedcbb1bf`: executable C
**5,753,281 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,049**, unknown **0**.
[Measurement](docs/evidence/lts-target/manifest.json). This predates the core
migration, includes inherited Rust infrastructure, and is neither a completion
percentage nor server runtime evidence. That target selects Rust BRD/C completion.

Next migrate generic wait.c callback traversal and wake wrappers, then reduce
C lock/list/scheduler dependencies. Reviewed implementation and synthetic-test
drafts remain outside Git at `linux-out/wait-policy-draft` and
`linux-out/wait-policy-tests-draft`; they are unbuilt and unverified.
Forced diagnostic failures, detached-batch races, untimed signal paths, deadline
races and broader IRQ coverage remain open. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b. Phase 1a still needs the provisional BRD
invalid-parameter exception, parameter adapters and review gates; [BRD.md](docs/BRD.md).

Failures are retained, including the [plain-profile configuration refusal](docs/evidence/swait-init/manifest.json)
(EXPERT forces DEBUG_KERNEL; corrected before compilation), [wait bringup](docs/evidence/completion-wait-initial/manifest.json),
[status test compilation](docs/evidence/completion-status/manifest.json),
[q35 bringup](docs/evidence/q35-bringup/manifest.json) and the initial
[swait/ext4 fixture staging refusal](docs/evidence/swait-ext4/manifest.json).
Raw logs/binaries remain in `linux-out/<run>`; manifests record source/config/tool
identities and hashes. [Verification index](docs/VERIFICATION.md) preserves earlier
milestones without attributing their results to newer source.

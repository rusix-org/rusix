# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and nine swait operations have verified
opt-in Rust implementations.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust BRD each pass block6, ext4 userspace6, six parameter variants and partition5. Four identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Core and shared queue policy | At `e7b7b9a94103`, C/Rust each pass 38 combined cases (29 core + nine BRD), then 29 isolated core cases on q35/KVM SMP2. BUG, lockdep/raw-lock nesting, atomic-sleep and list validation enabled. All14 completion and9 swait definitions link exclusively; blocking entries stay in scheduler text. Zero skips or compiler/objtool diagnostics. [Evidence](docs/evidence/swait-wrappers/manifest.json). |
| Ordinary-userspace integration | Same `e7b7b9a94103` source, Rust BRD in both; only completion/swait selection differs. Both pass nine block/ext4/parameter/partition boots with identical fixtures and no compiler diagnostics. KUnit disabled. [Evidence](docs/evidence/swait-wrappers-ext4/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray insertion,
NOIO scope, completion policy and shared/generic swait enrollment/wakeup.
The [core migration record](experiments/completion/README.md) owns storage,
locking/lifetime contracts, test inventory and remaining C boundaries. Selection
remains default-off and builtin-only; known incompatible counter-access drivers
are excluded. The latest queue slice adds 412 lines of Rust implementation and
725 lines of Rust tests relative to the previous published completion checkpoint.

Declared x86_64 server measurement at `7effedcbb1bf`: executable C
**5,753,281 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,049**, unknown **0**.
[Measurement](docs/evidence/lts-target/manifest.json). This predates the core
migration, includes inherited Rust infrastructure, and is neither a completion
percentage nor server runtime evidence. That target selects Rust BRD/C completion.

Next: migrate swait initialization with raw-lock class/name and debug/nondebug
checks, then reduce C lock/list/scheduler dependencies. A reviewed, unbuilt draft
is staged outside Git at `linux-out/swait-init-draft`; it is not current source.
Forced diagnostic failures, detached-batch races, untimed signal paths, deadline
races and broader IRQ coverage remain open. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b. Phase 1a still needs the provisional BRD
invalid-parameter exception, parameter adapters and review gates; [BRD.md](docs/BRD.md).

Failures are retained, including [wait bringup](docs/evidence/completion-wait-initial/manifest.json),
[status test compilation](docs/evidence/completion-status/manifest.json),
[q35 bringup](docs/evidence/q35-bringup/manifest.json) and the initial
[swait/ext4 fixture staging refusal](docs/evidence/swait-ext4/manifest.json).
Raw logs/binaries remain in `linux-out/<run>`; manifests record source/config/tool
identities and hashes. [Verification index](docs/VERIFICATION.md) preserves earlier
milestones without attributing their results to newer source.

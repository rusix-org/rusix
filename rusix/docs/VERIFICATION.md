# Verification index

Results apply only to their recorded source/configuration. Historical engineering
results use `21a7f44`; LTS results are explicitly identified below.
Current work and remaining gates: [progress](../PROGRESS.md), [Phase 1](PHASE1.md).

| Record | Verified scope |
| --- | --- |
| [Integer square root](history/2026-10-25-int-sqrt-verification.md) | Clean C/Rust x86_64 comparison: matching configs, 26 VM tests each; host differential and i686 ABI checks. [Raw evidence](evidence/int-sqrt/manifest.json). |
| [Repository relocation](evidence/repository-layout/manifest.json) | Fresh renamed checkout builds and passes 26 VM tests with tracked scripts. |
| [C BRD baseline](evidence/brd-c-baseline/manifest.json) | Historical C-only six-case probe on x86_64 SMP. |
| [LTS baseline](evidence/lts-baseline/manifest.json) | Signed 6.18.58 provenance, 24 required math cases and six C BRD cases. |
| [Rust BRD](evidence/brd-rust-initial/manifest.json) | Selected Rust implementation passes the identical six-case block probe. |
| [BRD ownership](evidence/brd-ownership/manifest.json) | Nine in-kernel policy/ownership cases, zero skips. |
| [Ordinary ext4](evidence/brd-ext4/manifest.json) | Six cases each on C/Rust, same source and byte-identical userspace initramfs. |
| [Bit-wait policy](evidence/wait-bit/manifest.json) | Ten bit-wait definitions and eight scheduler sections selected; C/Rust debug and plain pairs each pass 57 core + nine BRD, then 57 isolated core cases. Initial FFI-alias compile failure retained. |
| [Bit-wait/ext4](evidence/wait-bit-ext4/manifest.json) | Same corrected source passes nine boots each with identical fixtures, including six ext4 and four poll-consumer cases. |
| [WOKEN handshake](evidence/wait-woken/manifest.json) | Twenty-one generic wait entries selected; C/Rust debug and plain pairs each pass 48 core + nine BRD cases, then 48 isolated core. Four WOKEN cases cover latch, timeout, blocked consumer and key filtering. Compiled barrier primitives recorded. |
| [WOKEN/ext4](evidence/wait-woken-ext4/manifest.json) | Same source passes nine boots each, including six ext4 and four poll-consumer cases with identical fixtures. |
| [Wait lifecycle](evidence/wait-lifecycle/manifest.json) | Eighteen generic wait entries selected; C/Rust debug and plain pairs each pass 44 core + nine BRD cases, then 44 isolated core. Real blocked-worker handoffs, signal/timeout cleanup and prepare/finish contracts verified. |
| [Lifecycle/ext4](evidence/wait-lifecycle-ext4/manifest.json) | Same source passes nine boots each, including six ext4 and four poll-consumer cases with identical fixtures. |
| [Wait enrollment](evidence/wait-enrollment/manifest.json) | Thirteen generic wait entries selected; C/Rust debug and plain pairs each pass 39 core + nine BRD cases, then 39 isolated core. Priority order, rejection side effects, poison removal and constructor metadata verified. |
| [Enrollment/ext4](evidence/wait-enrollment-ext4/manifest.json) | Same source passes nine boots each, including six ext4 and four poll-consumer cases with identical fixtures. |
| [Generic wake traversal](evidence/wait-wake/manifest.json) | Seven wake wrappers selected; C/Rust debug and plain pairs each pass 35 core + nine BRD cases, then 35 isolated core. Initial compile failure retained. |
| [Wake/ext4 integration](evidence/wait-wake-ext4/manifest.json) | Nine boots each; includes six ext4 and four pipe/poll/epoll/eventfd cases with identical fixtures. |
| [Swait initializer](evidence/swait-init/manifest.json) | All ten swait entry points selected; C/Rust debug and plain configurations each pass 30 core + nine BRD cases and 30 isolated core cases. Initial configuration refusal retained. |
| [Swait initializer/ext4](evidence/swait-init-ext4/manifest.json) | Both implementations pass all nine userspace/contract boots with identical fixtures. |
| [Generic swait wrappers](evidence/swait-wrappers/manifest.json) | Nine swait and fourteen completion entries selected; paired instrumented 29 core + nine BRD cases, then 29 isolated core cases. |
| [Generic swait/ext4](evidence/swait-wrappers-ext4/manifest.json) | Same source passes all nine userspace/contract boots per implementation with identical fixtures. |
| [Shared swait policy](evidence/swait-debug/manifest.json) | Four shared policies selected in Rust; paired instrumented 26 core + nine BRD cases, then 26 isolated core cases. |
| [Swait/ext4 integration](evidence/swait-ext4/manifest.json) | Same source passes nine boots each with identical fixtures; initial fixture staging failure retained. |
| [Completion/ext4 integration](evidence/completion-ext4/manifest.json) | Rust BRD in both; C/Rust completion selection alone differs; both pass nine ordinary-userspace/contract boots with identical fixtures. |
| [Rust completion status/signals](evidence/completion-status/manifest.json) | All fourteen entry points selected; paired 21 core and nine BRD cases, including dedicated-thread signals and competing consumers. |
| [Rust completion waits](evidence/completion-wait/manifest.json) | Three signaling and nine blocking wait entry points selected exclusively; C/Rust each pass 16 core and nine BRD cases on q35/KVM, no compiler warnings. |
| [Rust completion signaling](evidence/completion-current-cpu/manifest.json) | All three signaling entry points selected exclusively; C/Rust each pass 12 core and nine BRD cases on q35/KVM. |
| [Completion scouting](evidence/completion-kernel/manifest.json) | Five C behavior tests and one Rust-owned/C-visible layout test pass; no production core replacement. |

Use [contributor commands](../CONTRIBUTING.md) for new runs. Historical commands
and warnings remain in the linked records. Module/CRC, other architectures,
performance and broad configuration compatibility require separate evidence.

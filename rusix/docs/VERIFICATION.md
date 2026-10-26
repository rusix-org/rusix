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
| [Rust completion waits](evidence/completion-wait/manifest.json) | Three signaling and nine blocking wait entry points selected exclusively; C/Rust each pass 16 core and nine BRD cases on q35/KVM, no compiler warnings. |
| [Rust completion signaling](evidence/completion-current-cpu/manifest.json) | All three signaling entry points selected exclusively; C/Rust each pass 12 core and nine BRD cases on q35/KVM. |
| [Completion scouting](evidence/completion-kernel/manifest.json) | Five C behavior tests and one Rust-owned/C-visible layout test pass; no production core replacement. |

Use [contributor commands](../CONTRIBUTING.md) for new runs. Historical commands
and warnings remain in the linked records. Module/CRC, other architectures,
performance and broad configuration compatibility require separate evidence.

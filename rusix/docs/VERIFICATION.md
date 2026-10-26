# Verification index

Results apply only to their recorded source/configuration. Existing kernel
results use engineering baseline `21a7f44`; they do not validate Linux 6.18.58.
Current work and remaining gates: [progress](../PROGRESS.md), [Phase 1](PHASE1.md).

| Record | Verified scope |
| --- | --- |
| [Integer square root](history/2026-10-25-int-sqrt-verification.md) | Clean C/Rust x86_64 comparison: matching configs, 26 VM tests each; host differential and i686 ABI checks. [Raw evidence](evidence/int-sqrt/manifest.json). |
| [Repository relocation](evidence/repository-layout/manifest.json) | Fresh renamed checkout builds and passes 26 VM tests with tracked scripts. |
| [C BRD baseline](evidence/brd-c-baseline/manifest.json) | Six cases on x86_64 SMP; no Rust BRD implementation. |

Use [contributor commands](../CONTRIBUTING.md) for new runs. Historical commands
and warnings remain in the linked records. Module/CRC, other architectures,
performance and broad configuration compatibility require separate evidence.

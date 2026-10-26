# rusix

An experimental, incremental Rust rewrite of the Linux kernel, with the longer
term goal of migrating the remaining operating-system components to Rust.

**Direction: Linux-compatible externally, Rust-native internally.** Preserve
behavior at migration boundaries, then replace internal C interfaces as related
components become complete Rust subsystems.

This is **Phase 0 integration bootstrap**, not completed Phase 1 or a production
kernel. The
first integer-square-root replacement has passed recorded C/Rust x86_64 kernel
comparisons. Most of the kernel remains C; module, architecture, workload, and
performance coverage is still being developed. Read the evidence and limitations
before drawing compatibility conclusions.

- [Project entry point and setup](rusix/README.md)
- [Accepted architecture decision](rusix/docs/ARCHITECTURE.md)
- [Full roadmap](rusix/docs/ROADMAP.md)
- [Published bootstrap audit](rusix/docs/AUDIT-PHASE0.md)
- [Exact Phase 1 target and exit gates](rusix/docs/PHASE1.md)
- [Progress and outstanding work](rusix/PROGRESS.md)
- [Migration contracts](rusix/docs/MIGRATIONS.md)
- [Verification evidence](rusix/docs/VERIFICATION.md)
- [Contributing](rusix/CONTRIBUTING.md)
- [Initial publication gate](rusix/docs/PUBLICATION.md)

This repository retains Linux source history, licensing, attribution, and its
original [README](README). rusix-specific documentation lives under `rusix/`.
See [COPYING](COPYING) and [LICENSES](LICENSES/) for the inherited license terms;
preserve per-file SPDX identifiers and attribution.

The development tools currently expect a workspace containing this checkout as
`linux/`. Follow the contributor setup instructions rather than assuming a
standalone Cargo project. Test experimental kernels in isolated VMs, not on the
host machine.
